"""Tests for payment_processor.py (with-skill version)."""

from __future__ import annotations

import os
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
import structlog
import structlog.testing

from payment_processor import (
    DatabaseError,
    EmailService,
    GatewayDeclineError,
    GatewayError,
    NotificationError,
    OrderRepository,
    OrderStatus,
    PaymentGateway,
    PaymentMethod,
    PaymentProcessor,
    PaymentRequest,
    ValidationError,
    _validate_request,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def make_request(**overrides) -> PaymentRequest:
    defaults = dict(
        order_id="order-123",
        customer_id="cust-456",
        amount=Decimal("99.99"),
        currency="USD",
        payment_method=PaymentMethod.CREDIT_CARD,
        payment_token="tok-test-abc123",
    )
    defaults.update(overrides)
    return PaymentRequest(**defaults)


def make_processor(
    gateway=None, order_repo=None, email_service=None
) -> PaymentProcessor:
    gateway = gateway or MagicMock(spec=PaymentGateway)
    order_repo = order_repo or MagicMock(spec=OrderRepository)
    email_service = email_service or MagicMock(spec=EmailService)
    return PaymentProcessor(gateway, order_repo, email_service)


# ---------------------------------------------------------------------------
# Validation unit tests
# ---------------------------------------------------------------------------


class TestValidateRequest:
    def test_valid_request_passes(self):
        _validate_request(make_request())  # no exception

    def test_invalid_order_id_chars_fails(self):
        with pytest.raises(ValidationError, match="order_id"):
            _validate_request(make_request(order_id="order 123"))  # space not allowed

    def test_empty_order_id_fails(self):
        with pytest.raises(ValidationError, match="order_id"):
            _validate_request(make_request(order_id=""))

    def test_order_id_too_long_fails(self):
        with pytest.raises(ValidationError, match="order_id"):
            _validate_request(make_request(order_id="x" * 65))

    def test_invalid_customer_id_fails(self):
        with pytest.raises(ValidationError, match="customer_id"):
            _validate_request(make_request(customer_id="cust@456"))

    def test_zero_amount_fails(self):
        with pytest.raises(ValidationError, match="amount must be positive"):
            _validate_request(make_request(amount=Decimal("0")))

    def test_negative_amount_fails(self):
        with pytest.raises(ValidationError, match="amount must be positive"):
            _validate_request(make_request(amount=Decimal("-1")))

    def test_amount_over_maximum_fails(self):
        with pytest.raises(ValidationError, match="exceeds maximum"):
            _validate_request(make_request(amount=Decimal("1000000")))

    def test_nan_amount_fails(self):
        with pytest.raises(ValidationError, match="finite"):
            _validate_request(make_request(amount=Decimal("NaN")))

    def test_infinite_amount_fails(self):
        with pytest.raises(ValidationError, match="finite"):
            _validate_request(make_request(amount=Decimal("Infinity")))

    def test_unsupported_currency_fails(self):
        with pytest.raises(ValidationError, match="not supported"):
            _validate_request(make_request(currency="JPY"))

    def test_invalid_payment_token_fails(self):
        with pytest.raises(ValidationError, match="payment_token"):
            _validate_request(make_request(payment_token="short"))  # < 8 chars

    def test_payment_token_with_spaces_fails(self):
        with pytest.raises(ValidationError, match="payment_token"):
            _validate_request(make_request(payment_token="tok test abc123"))

    def test_multiple_errors_reported_together(self):
        with pytest.raises(ValidationError) as exc_info:
            _validate_request(make_request(order_id="", amount=Decimal("-5")))
        msg = str(exc_info.value)
        assert "order_id" in msg
        assert "amount must be positive" in msg


# ---------------------------------------------------------------------------
# PaymentProcessor integration tests
# ---------------------------------------------------------------------------


class TestProcessPaymentSuccess:
    def test_happy_path_returns_success(self):
        gateway = MagicMock(spec=PaymentGateway)
        gateway.charge.return_value = "txn-789"
        processor = make_processor(gateway=gateway)

        result = processor.process_payment(make_request())

        assert result.success is True
        assert result.transaction_id == "txn-789"
        assert result.error_code is None
        assert result.warning_code is None
        assert set(result.stages_completed) >= {"validation", "charge", "order_update"}

    def test_happy_path_updates_order_to_paid(self):
        gateway = MagicMock(spec=PaymentGateway)
        gateway.charge.return_value = "txn-789"
        order_repo = MagicMock(spec=OrderRepository)
        processor = make_processor(gateway=gateway, order_repo=order_repo)

        processor.process_payment(make_request())

        order_repo.update_status.assert_called_once_with(
            "order-123", OrderStatus.PAID, transaction_id="txn-789"
        )

    def test_happy_path_sends_confirmation_email(self):
        gateway = MagicMock(spec=PaymentGateway)
        gateway.charge.return_value = "txn-789"
        email_service = MagicMock(spec=EmailService)
        processor = make_processor(gateway=gateway, email_service=email_service)

        processor.process_payment(make_request())

        email_service.send_confirmation.assert_called_once_with(
            "cust-456", "order-123", "txn-789"
        )


class TestProcessPaymentValidationFailure:
    def test_validation_failure_returns_error_result(self):
        processor = make_processor()
        result = processor.process_payment(make_request(order_id="bad id!"))

        assert result.success is False
        assert result.error_code == "VALIDATION_FAILED"
        assert result.transaction_id is None

    def test_validation_failure_error_message_is_safe(self):
        """error_message must not contain raw exception internals."""
        processor = make_processor()
        result = processor.process_payment(make_request(order_id="bad id!"))

        # Should be the safe user-facing message, not str(exc)
        assert "invalid fields" in result.error_message

    def test_validation_failure_with_invalid_order_id_does_not_call_db(self):
        """When order_id itself is invalid there is no record to mark failed."""
        order_repo = MagicMock(spec=OrderRepository)
        processor = make_processor(order_repo=order_repo)

        processor.process_payment(make_request(order_id="bad id!"))

        order_repo.update_status.assert_not_called()

    def test_validation_failure_with_valid_order_id_marks_order_failed(self):
        """When order_id is valid but another field fails, mark the order failed."""
        order_repo = MagicMock(spec=OrderRepository)
        processor = make_processor(order_repo=order_repo)

        processor.process_payment(make_request(amount=Decimal("-1")))

        order_repo.update_status.assert_called_once_with(
            "order-123", OrderStatus.FAILED
        )

    def test_validation_failure_does_not_call_gateway(self):
        gateway = MagicMock(spec=PaymentGateway)
        processor = make_processor(gateway=gateway)

        processor.process_payment(make_request(amount=Decimal("-1")))

        gateway.charge.assert_not_called()


class TestProcessPaymentGatewayFailure:
    def test_gateway_decline_returns_error_result(self):
        gateway = MagicMock(spec=PaymentGateway)
        gateway.charge.side_effect = GatewayDeclineError(
            "Card declined", "CARD_DECLINED"
        )
        processor = make_processor(gateway=gateway)

        result = processor.process_payment(make_request())

        assert result.success is False
        assert result.error_code == "CARD_DECLINED"
        assert result.retryable is False

    def test_gateway_decline_error_message_is_safe(self):
        gateway = MagicMock(spec=PaymentGateway)
        gateway.charge.side_effect = GatewayDeclineError(
            "Internal gateway detail: card BIN 411111 blocked", "CARD_DECLINED"
        )
        processor = make_processor(gateway=gateway)

        result = processor.process_payment(make_request())

        assert "BIN" not in result.error_message
        assert "411111" not in result.error_message

    def test_gateway_decline_marks_order_failed(self):
        gateway = MagicMock(spec=PaymentGateway)
        gateway.charge.side_effect = GatewayDeclineError(
            "Card declined", "CARD_DECLINED"
        )
        order_repo = MagicMock(spec=OrderRepository)
        processor = make_processor(gateway=gateway, order_repo=order_repo)

        processor.process_payment(make_request())

        order_repo.update_status.assert_called_once_with(
            "order-123", OrderStatus.FAILED
        )

    def test_gateway_error_returns_error_result(self):
        gateway = MagicMock(spec=PaymentGateway)
        gateway.charge.side_effect = GatewayError(
            "Timeout", "GATEWAY_TIMEOUT", retryable=True
        )
        processor = make_processor(gateway=gateway)

        result = processor.process_payment(make_request())

        assert result.success is False
        assert result.error_code == "GATEWAY_TIMEOUT"

    def test_gateway_error_retryable_flag_surfaced_in_result(self):
        """retryable=True must be visible to callers via PaymentResult."""
        gateway = MagicMock(spec=PaymentGateway)
        gateway.charge.side_effect = GatewayError(
            "Timeout", "GATEWAY_TIMEOUT", retryable=True
        )
        processor = make_processor(gateway=gateway)

        result = processor.process_payment(make_request())

        assert result.retryable is True

    def test_gateway_error_non_retryable_flag_surfaced_in_result(self):
        gateway = MagicMock(spec=PaymentGateway)
        gateway.charge.side_effect = GatewayError(
            "Permanent failure", "GATEWAY_ERROR", retryable=False
        )
        processor = make_processor(gateway=gateway)

        result = processor.process_payment(make_request())

        assert result.retryable is False

    def test_gateway_error_marks_order_failed(self):
        gateway = MagicMock(spec=PaymentGateway)
        gateway.charge.side_effect = GatewayError("Timeout", "GATEWAY_TIMEOUT")
        order_repo = MagicMock(spec=OrderRepository)
        processor = make_processor(gateway=gateway, order_repo=order_repo)

        processor.process_payment(make_request())

        order_repo.update_status.assert_called_once_with(
            "order-123", OrderStatus.FAILED
        )

    def test_unexpected_gateway_exception_returns_error_result(self):
        """Non-GatewayError exceptions from the gateway must not propagate."""
        gateway = MagicMock(spec=PaymentGateway)
        gateway.charge.side_effect = RuntimeError("SDK internal crash")
        processor = make_processor(gateway=gateway)

        result = processor.process_payment(make_request())

        assert result.success is False
        assert result.error_code == "GATEWAY_UNEXPECTED_ERROR"

    def test_unexpected_gateway_exception_does_not_propagate(self):
        gateway = MagicMock(spec=PaymentGateway)
        gateway.charge.side_effect = ConnectionError("network down")
        processor = make_processor(gateway=gateway)

        # Must not raise
        result = processor.process_payment(make_request())
        assert result is not None


class TestProcessPaymentDatabaseFailure:
    def test_db_failure_after_charge_still_returns_success(self):
        """Charge succeeded — returning failure would cause a double-charge on retry."""
        gateway = MagicMock(spec=PaymentGateway)
        gateway.charge.return_value = "txn-789"
        order_repo = MagicMock(spec=OrderRepository)
        order_repo.update_status.side_effect = DatabaseError(
            "DB unavailable", "DB_ERROR"
        )
        processor = make_processor(gateway=gateway, order_repo=order_repo)

        result = processor.process_payment(make_request())

        assert result.success is True
        assert result.transaction_id == "txn-789"
        # error_code must be None — only warning_code is set for partial success
        assert result.error_code is None
        assert result.warning_code == "DB_ERROR"

    def test_db_failure_after_charge_still_attempts_email(self):
        gateway = MagicMock(spec=PaymentGateway)
        gateway.charge.return_value = "txn-789"
        order_repo = MagicMock(spec=OrderRepository)
        order_repo.update_status.side_effect = DatabaseError(
            "DB unavailable", "DB_ERROR"
        )
        email_service = MagicMock(spec=EmailService)
        processor = make_processor(
            gateway=gateway, order_repo=order_repo, email_service=email_service
        )

        processor.process_payment(make_request())

        email_service.send_confirmation.assert_called_once()

    def test_unexpected_db_exception_after_charge_returns_success(self):
        """Unexpected DB exceptions must not propagate when charge already captured."""
        gateway = MagicMock(spec=PaymentGateway)
        gateway.charge.return_value = "txn-789"
        order_repo = MagicMock(spec=OrderRepository)
        order_repo.update_status.side_effect = RuntimeError("ORM crash")
        processor = make_processor(gateway=gateway, order_repo=order_repo)

        result = processor.process_payment(make_request())

        assert result.success is True
        assert result.warning_code == "DB_UNEXPECTED_ERROR"

    def test_db_failure_marking_order_failed_does_not_propagate(self):
        """_try_mark_order_failed must swallow all exceptions."""
        gateway = MagicMock(spec=PaymentGateway)
        gateway.charge.side_effect = GatewayDeclineError("Declined", "CARD_DECLINED")
        order_repo = MagicMock(spec=OrderRepository)
        order_repo.update_status.side_effect = RuntimeError("DB exploded")
        processor = make_processor(gateway=gateway, order_repo=order_repo)

        # Must not raise even though both gateway and DB failed
        result = processor.process_payment(make_request())
        assert result.success is False

    def test_unexpected_db_exception_in_mark_failed_does_not_propagate(self):
        gateway = MagicMock(spec=PaymentGateway)
        gateway.charge.side_effect = GatewayError("Timeout", "GATEWAY_TIMEOUT")
        order_repo = MagicMock(spec=OrderRepository)
        order_repo.update_status.side_effect = ConnectionError("DB gone")
        processor = make_processor(gateway=gateway, order_repo=order_repo)

        result = processor.process_payment(make_request())
        assert result.success is False


class TestProcessPaymentEmailFailure:
    def test_email_failure_does_not_affect_success_result(self):
        gateway = MagicMock(spec=PaymentGateway)
        gateway.charge.return_value = "txn-789"
        email_service = MagicMock(spec=EmailService)
        email_service.send_confirmation.side_effect = NotificationError(
            "SMTP timeout", "EMAIL_FAILED"
        )
        processor = make_processor(gateway=gateway, email_service=email_service)

        result = processor.process_payment(make_request())

        assert result.success is True
        assert result.transaction_id == "txn-789"

    def test_unexpected_email_exception_does_not_propagate(self):
        """Any exception from EmailService must be swallowed."""
        gateway = MagicMock(spec=PaymentGateway)
        gateway.charge.return_value = "txn-789"
        email_service = MagicMock(spec=EmailService)
        email_service.send_confirmation.side_effect = RuntimeError("SMTP crash")
        processor = make_processor(gateway=gateway, email_service=email_service)

        result = processor.process_payment(make_request())

        assert result.success is True

    def test_email_failure_order_still_marked_paid(self):
        gateway = MagicMock(spec=PaymentGateway)
        gateway.charge.return_value = "txn-789"
        order_repo = MagicMock(spec=OrderRepository)
        email_service = MagicMock(spec=EmailService)
        email_service.send_confirmation.side_effect = NotificationError(
            "SMTP timeout", "EMAIL_FAILED"
        )
        processor = make_processor(
            gateway=gateway, order_repo=order_repo, email_service=email_service
        )

        processor.process_payment(make_request())

        order_repo.update_status.assert_called_once_with(
            "order-123", OrderStatus.PAID, transaction_id="txn-789"
        )


class TestLogging:
    """Verify key structured log events using structlog.testing.capture_logs().

    capture_logs() captures events as structured dicts regardless of output
    configuration, making assertions format-independent and reliable across
    structlog versions and output targets.
    """

    def test_happy_path_logs_payment_started_and_completed(self):
        gateway = MagicMock(spec=PaymentGateway)
        gateway.charge.return_value = "txn-789"
        processor = make_processor(gateway=gateway)

        with structlog.testing.capture_logs() as logs:
            processor.process_payment(make_request())

        events = [l["event"] for l in logs]
        assert "payment_started" in events
        assert "payment_completed" in events

    def test_validation_failure_logs_warning(self):
        processor = make_processor()

        with structlog.testing.capture_logs() as logs:
            processor.process_payment(make_request(order_id="bad id!"))

        events = [l["event"] for l in logs]
        assert "payment_validation_failed" in events

    def test_gateway_decline_logs_warning(self):
        gateway = MagicMock(spec=PaymentGateway)
        gateway.charge.side_effect = GatewayDeclineError("Declined", "CARD_DECLINED")
        processor = make_processor(gateway=gateway)

        with structlog.testing.capture_logs() as logs:
            processor.process_payment(make_request())

        events = [l["event"] for l in logs]
        assert "gateway_charge_declined" in events

    def test_logs_include_correlation_id(self):
        gateway = MagicMock(spec=PaymentGateway)
        gateway.charge.return_value = "txn-789"
        processor = make_processor(gateway=gateway)

        with structlog.testing.capture_logs() as logs:
            processor.process_payment(make_request())

        assert all("correlation_id" in l for l in logs)

    def test_logs_include_duration_for_gateway_call(self):
        gateway = MagicMock(spec=PaymentGateway)
        gateway.charge.return_value = "txn-789"
        processor = make_processor(gateway=gateway)

        with structlog.testing.capture_logs() as logs:
            processor.process_payment(make_request())

        succeeded = next(l for l in logs if l["event"] == "gateway_charge_succeeded")
        assert "duration_ms" in succeeded

    def test_payment_token_not_logged(self):
        gateway = MagicMock(spec=PaymentGateway)
        gateway.charge.return_value = "txn-789"
        processor = make_processor(gateway=gateway)

        with structlog.testing.capture_logs() as logs:
            processor.process_payment(make_request(payment_token="tok-secret-xyz123"))

        for log_entry in logs:
            for value in log_entry.values():
                assert "tok-secret-xyz123" not in str(value)

    def test_raw_customer_id_not_logged(self):
        """customer_id must be pseudonymised — raw value must not appear in any log."""
        gateway = MagicMock(spec=PaymentGateway)
        gateway.charge.return_value = "txn-789"
        processor = make_processor(gateway=gateway)

        with structlog.testing.capture_logs() as logs:
            processor.process_payment(make_request(customer_id="cust-456"))

        for log_entry in logs:
            for value in log_entry.values():
                assert "cust-456" not in str(value)

    def test_gateway_error_retryable_logged(self):
        """retryable flag must appear in the gateway_charge_failed log event."""
        gateway = MagicMock(spec=PaymentGateway)
        gateway.charge.side_effect = GatewayError(
            "Timeout", "GATEWAY_TIMEOUT", retryable=True
        )
        processor = make_processor(gateway=gateway)

        with structlog.testing.capture_logs() as logs:
            processor.process_payment(make_request())

        failed = next(l for l in logs if l["event"] == "gateway_charge_failed")
        assert failed["retryable"] is True

    def test_db_failure_after_charge_logs_critical(self):
        gateway = MagicMock(spec=PaymentGateway)
        gateway.charge.return_value = "txn-789"
        order_repo = MagicMock(spec=OrderRepository)
        order_repo.update_status.side_effect = DatabaseError("DB down", "DB_ERROR")
        processor = make_processor(gateway=gateway, order_repo=order_repo)

        with structlog.testing.capture_logs() as logs:
            processor.process_payment(make_request())

        events = [l["event"] for l in logs]
        assert "order_status_update_failed_after_charge" in events

    def test_internal_error_details_not_in_result_error_message(self):
        """Raw exception messages must not reach PaymentResult.error_message."""
        gateway = MagicMock(spec=PaymentGateway)
        gateway.charge.side_effect = GatewayError(
            "Internal: endpoint https://gw.internal/charge returned 503",
            "GATEWAY_ERROR",
        )
        processor = make_processor(gateway=gateway)

        result = processor.process_payment(make_request())

        assert "https://gw.internal" not in result.error_message
        assert "503" not in result.error_message
