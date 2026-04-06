"""
Payment processing module with production-ready error handling and observability.

Validates payment method, charges via payment gateway, updates order status,
and sends confirmation email — with structured logging at every stage.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import re
import time
import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Optional

import structlog

# ---------------------------------------------------------------------------
# Logger configuration
#
# Log level is read from the LOG_LEVEL environment variable so it can be
# adjusted without redeployment.  Only allowlisted values are accepted;
# anything else silently falls back to INFO to prevent attribute-access
# gadget abuse via getattr on the logging module.
# ---------------------------------------------------------------------------

_ALLOWED_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
_raw_level = os.environ.get("LOG_LEVEL", "INFO").upper()
_LOG_LEVEL = _raw_level if _raw_level in _ALLOWED_LOG_LEVELS else "INFO"

structlog.configure(
    wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, _LOG_LEVEL)),
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)

_base_logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Log pseudonymisation
#
# customer_id may be PII (email, phone, government ID).  We bind a keyed
# HMAC truncated to 16 hex chars instead of the raw value so logs are
# useful for correlation without exposing the identifier itself.
# Set LOG_PSEUDONYM_KEY to a 32-byte hex secret in production.
# ---------------------------------------------------------------------------

_raw_key = os.environ.get("LOG_PSEUDONYM_KEY", "")
try:
    _LOG_PSEUDONYM_KEY: bytes = bytes.fromhex(_raw_key) if _raw_key else bytes(32)
except ValueError:
    _LOG_PSEUDONYM_KEY = bytes(32)
    logging.warning(
        "LOG_PSEUDONYM_KEY is not valid hex; falling back to zero key — "
        "set a proper 32-byte hex secret in production"
    )


def _pseudonymize(value: str) -> str:
    """Return a 16-char HMAC-SHA256 pseudonym for a PII identifier."""
    return hmac.new(_LOG_PSEUDONYM_KEY, value.encode(), hashlib.sha256).hexdigest()[:16]


# ---------------------------------------------------------------------------
# User-facing error messages
#
# Internal exception messages may contain gateway URLs, SQL fragments, or
# other system details.  Never surface str(exc) to callers; use this table
# to map error_code → safe user message instead.
# ---------------------------------------------------------------------------

_USER_MESSAGES: dict[str, str] = {
    "VALIDATION_FAILED": "The payment request contained invalid fields.",
    "CARD_DECLINED": "Your payment was declined. Please try a different payment method.",
    "GATEWAY_TIMEOUT": "Payment service temporarily unavailable. Please try again.",
    "GATEWAY_ERROR": "Payment service temporarily unavailable. Please try again.",
    "GATEWAY_UNEXPECTED_ERROR": "An unexpected error occurred. Please contact support.",
    "DB_ERROR": (
        "Payment captured but order record update failed — "
        "please contact support with your transaction ID."
    ),
    "DB_UNEXPECTED_ERROR": (
        "Payment captured but order record update failed — "
        "please contact support with your transaction ID."
    ),
}

_DEFAULT_USER_MESSAGE = "An unexpected error occurred. Please contact support."


def _safe_message(error_code: str) -> str:
    """Return a safe user-facing message for the given error code."""
    return _USER_MESSAGES.get(error_code, _DEFAULT_USER_MESSAGE)


# ---------------------------------------------------------------------------
# Domain types
# ---------------------------------------------------------------------------


class PaymentMethod(str, Enum):
    """Supported payment method types."""

    CREDIT_CARD = "credit_card"
    DEBIT_CARD = "debit_card"
    BANK_TRANSFER = "bank_transfer"
    DIGITAL_WALLET = "digital_wallet"


class OrderStatus(str, Enum):
    """Lifecycle states for an order."""

    PENDING = "pending"
    PAID = "paid"
    FAILED = "failed"
    REFUNDED = "refunded"


@dataclass
class PaymentRequest:
    """Validated input for a single payment attempt."""

    order_id: str
    customer_id: str
    amount: Decimal
    currency: str
    payment_method: PaymentMethod
    payment_token: str  # Tokenised card/wallet reference — never raw PAN


@dataclass
class PaymentResult:
    """Outcome of a payment attempt.

    ``error_code``/``error_message`` are set only when ``success=False``.
    ``warning_code``/``warning_message`` are set when ``success=True`` but a
    non-fatal operational issue occurred (e.g., charge captured but DB write
    failed).  Ops must reconcile via ``transaction_id`` when ``warning_code``
    is set.
    ``retryable`` is ``True`` when the failure is transient and safe to retry.
    """

    success: bool
    order_id: str
    transaction_id: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    warning_code: Optional[str] = None
    warning_message: Optional[str] = None
    retryable: bool = False
    stages_completed: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class PaymentError(Exception):
    """Base class for all payment-processing errors."""

    def __init__(self, message: str, error_code: str) -> None:
        super().__init__(message)
        self.error_code = error_code


class ValidationError(PaymentError):
    """Payment request failed pre-charge validation."""


class GatewayError(PaymentError):
    """Payment gateway returned an error or was unreachable."""

    def __init__(self, message: str, error_code: str, retryable: bool = False) -> None:
        super().__init__(message, error_code)
        self.retryable = retryable


class GatewayDeclineError(GatewayError):
    """Gateway processed the request but the issuer declined.

    Declines are never retryable — the issuer made a definitive decision.
    """

    def __init__(self, message: str, error_code: str) -> None:
        # retryable is always False for declines; hard-coded to prevent
        # subclasses or callers from accidentally treating a decline as
        # a transient failure.
        super().__init__(message, error_code, retryable=False)


class DatabaseError(PaymentError):
    """Order-status update failed."""


class NotificationError(PaymentError):
    """Confirmation email could not be sent (non-fatal)."""


# ---------------------------------------------------------------------------
# Collaborator interfaces (inject real implementations in production)
# ---------------------------------------------------------------------------


class PaymentGateway:
    """Thin wrapper around the external payment gateway SDK."""

    def charge(self, request: PaymentRequest) -> str:
        """Attempt charge; return transaction_id on success.

        Raises:
            GatewayDeclineError: Issuer declined the charge.
            GatewayError: Network / gateway-side failure.
        """
        raise NotImplementedError


class OrderRepository:
    """Persistence layer for order records."""

    def update_status(
        self,
        order_id: str,
        status: OrderStatus,
        transaction_id: Optional[str] = None,
    ) -> None:
        """Persist the new order status.

        Raises:
            DatabaseError: Write failed.
        """
        raise NotImplementedError


class EmailService:
    """Outbound email delivery."""

    def send_confirmation(
        self, customer_id: str, order_id: str, transaction_id: str
    ) -> None:
        """Send payment confirmation email.

        Raises:
            NotificationError: Delivery failed.
        """
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

_SUPPORTED_CURRENCIES = {"USD", "EUR", "GBP", "CAD", "AUD"}
_MAX_AMOUNT = Decimal("999999.99")
_ID_RE = re.compile(r"^[A-Za-z0-9_\-]{1,64}$")
_TOKEN_RE = re.compile(r"^[A-Za-z0-9_\-]{8,256}$")


def _validate_request(request: PaymentRequest) -> None:
    """Raise ValidationError for any malformed or out-of-range field."""
    errors: list[str] = []

    if not isinstance(request.order_id, str) or not _ID_RE.match(request.order_id):
        errors.append("order_id must be 1–64 alphanumeric/dash/underscore characters")

    if not isinstance(request.customer_id, str) or not _ID_RE.match(
        request.customer_id
    ):
        errors.append(
            "customer_id must be 1–64 alphanumeric/dash/underscore characters"
        )

    if not isinstance(request.amount, Decimal) or not request.amount.is_finite():
        errors.append("amount must be a finite decimal number")
    elif request.amount <= Decimal("0"):
        errors.append(f"amount must be positive, got {request.amount}")
    elif request.amount > _MAX_AMOUNT:
        errors.append(f"amount {request.amount} exceeds maximum {_MAX_AMOUNT}")

    if request.currency not in _SUPPORTED_CURRENCIES:
        errors.append(
            f"currency '{request.currency}' not supported; "
            f"accepted: {sorted(_SUPPORTED_CURRENCIES)}"
        )

    if not isinstance(request.payment_token, str) or not _TOKEN_RE.match(
        request.payment_token
    ):
        errors.append(
            "payment_token format is invalid (8–256 alphanumeric/dash/underscore)"
        )

    if errors:
        raise ValidationError(
            f"Payment request invalid: {'; '.join(errors)}",
            error_code="VALIDATION_FAILED",
        )


# ---------------------------------------------------------------------------
# Core processor
# ---------------------------------------------------------------------------


class PaymentProcessor:
    """Orchestrates validation → charge → DB update → email confirmation."""

    def __init__(
        self,
        gateway: PaymentGateway,
        order_repo: OrderRepository,
        email_service: EmailService,
    ) -> None:
        self._gateway = gateway
        self._order_repo = order_repo
        self._email_service = email_service

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process_payment(self, request: PaymentRequest) -> PaymentResult:
        """Process a payment end-to-end.

        Always returns a PaymentResult — never raises.  Internal exceptions
        are caught, logged, and translated into the result's fields.

        PII policy: customer_id is pseudonymised before binding to the logger;
        raw payment_token is never logged.
        """
        correlation_id = str(uuid.uuid4())

        # Bind request context once; all subsequent log calls on `log`
        # automatically include these fields.  customer_id is pseudonymised
        # to avoid PII in log aggregators.  We use safe fallbacks for fields
        # that may be invalid types so the bind itself never raises.
        try:
            customer_ref = _pseudonymize(
                request.customer_id
                if isinstance(request.customer_id, str)
                else str(request.customer_id)
            )
            payment_method_val = (
                request.payment_method.value
                if isinstance(request.payment_method, PaymentMethod)
                else str(request.payment_method)
            )
            log = _base_logger.bind(
                correlation_id=correlation_id,
                order_id=request.order_id,
                customer_ref=customer_ref,
                amount=str(request.amount),
                currency=request.currency,
                payment_method=payment_method_val,
            )
        except Exception:
            log = _base_logger.bind(correlation_id=correlation_id)

        log.info("payment_started")

        result = PaymentResult(success=False, order_id=request.order_id)

        # ── Stage 1: Validate ──────────────────────────────────────────
        try:
            _validate_request(request)
        except ValidationError as exc:
            log.warning(
                "payment_validation_failed",
                error_code=exc.error_code,
                reason=str(exc),
            )
            result.error_code = exc.error_code
            result.error_message = _safe_message(exc.error_code)
            # Only attempt to mark the order failed if we have a valid order_id;
            # if order_id itself was the invalid field there is no record to update.
            if isinstance(request.order_id, str) and _ID_RE.match(request.order_id):
                self._try_mark_order_failed(request.order_id, log)
            return result
        except Exception as exc:
            log.error(
                "payment_validation_unexpected_error",
                reason=str(exc),
                exc_info=True,
            )
            result.error_code = "VALIDATION_FAILED"
            result.error_message = _safe_message("VALIDATION_FAILED")
            return result

        log.info("payment_validation_passed")
        result.stages_completed.append("validation")

        # ── Stage 2: Charge ────────────────────────────────────────────
        # Log entry AND exit with duration so degradation is visible before
        # it becomes an outage.
        log.info("gateway_charge_calling", gateway=type(self._gateway).__name__)
        charge_start = time.monotonic()
        transaction_id: Optional[str] = None
        try:
            transaction_id = self._gateway.charge(request)
            charge_ms = round((time.monotonic() - charge_start) * 1000, 1)
            log.info(
                "gateway_charge_succeeded",
                transaction_id=transaction_id,
                duration_ms=charge_ms,
            )
        except GatewayDeclineError as exc:
            charge_ms = round((time.monotonic() - charge_start) * 1000, 1)
            log.warning(
                "gateway_charge_declined",
                error_code=exc.error_code,
                reason=str(exc),
                duration_ms=charge_ms,
            )
            result.error_code = exc.error_code
            result.error_message = _safe_message(exc.error_code)
            self._try_mark_order_failed(request.order_id, log)
            return result
        except GatewayError as exc:
            charge_ms = round((time.monotonic() - charge_start) * 1000, 1)
            log.error(
                "gateway_charge_failed",
                error_code=exc.error_code,
                retryable=exc.retryable,
                reason=str(exc),
                duration_ms=charge_ms,
                exc_info=True,
            )
            result.error_code = exc.error_code
            result.error_message = _safe_message(exc.error_code)
            result.retryable = exc.retryable
            self._try_mark_order_failed(request.order_id, log)
            return result
        except Exception as exc:
            charge_ms = round((time.monotonic() - charge_start) * 1000, 1)
            # Unexpected exception from the gateway SDK.  We cannot know
            # whether the charge was captured; do NOT mark the order FAILED
            # (that would be incorrect if the charge succeeded).  Log at
            # CRITICAL so ops can investigate and reconcile.
            log.critical(
                "gateway_charge_unexpected_error",
                reason=str(exc),
                duration_ms=charge_ms,
                action_required="verify_charge_status",
                exc_info=True,
            )
            result.error_code = "GATEWAY_UNEXPECTED_ERROR"
            result.error_message = _safe_message("GATEWAY_UNEXPECTED_ERROR")
            return result

        result.stages_completed.append("charge")
        result.transaction_id = transaction_id

        # ── Stage 3: Update order status ───────────────────────────────
        log.info("order_status_update_calling", new_status=OrderStatus.PAID.value)
        db_start = time.monotonic()
        try:
            self._order_repo.update_status(
                request.order_id,
                OrderStatus.PAID,
                transaction_id=transaction_id,
            )
            db_ms = round((time.monotonic() - db_start) * 1000, 1)
            log.info(
                "order_status_update_succeeded",
                new_status=OrderStatus.PAID.value,
                transaction_id=transaction_id,
                duration_ms=db_ms,
            )
        except DatabaseError as exc:
            db_ms = round((time.monotonic() - db_start) * 1000, 1)
            # Money has left the customer's account but we couldn't record it.
            # Log at CRITICAL so on-call is paged; do NOT return failure to the
            # caller — the charge succeeded and a retry would double-charge.
            log.critical(
                "order_status_update_failed_after_charge",
                error_code=exc.error_code,
                transaction_id=transaction_id,
                reason=str(exc),
                duration_ms=db_ms,
                action_required="manual_reconciliation",
                exc_info=True,
            )
            result.success = True
            result.warning_code = exc.error_code
            result.warning_message = _safe_message(exc.error_code)
            self._try_send_confirmation(request, transaction_id, log)
            return result
        except Exception as exc:
            db_ms = round((time.monotonic() - db_start) * 1000, 1)
            log.critical(
                "order_status_update_unexpected_error_after_charge",
                transaction_id=transaction_id,
                reason=str(exc),
                duration_ms=db_ms,
                action_required="manual_reconciliation",
                exc_info=True,
            )
            result.success = True
            result.warning_code = "DB_UNEXPECTED_ERROR"
            result.warning_message = _safe_message("DB_UNEXPECTED_ERROR")
            self._try_send_confirmation(request, transaction_id, log)
            return result

        result.stages_completed.append("order_update")

        # ── Stage 4: Send confirmation email ──────────────────────────
        # Email failure is non-fatal: the payment succeeded and the order is
        # recorded.  Log the failure and continue.
        self._try_send_confirmation(request, transaction_id, log)

        result.success = True
        log.info(
            "payment_completed",
            transaction_id=transaction_id,
            stages=result.stages_completed,
        )
        return result

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _try_mark_order_failed(self, order_id: str, log: structlog.BoundLogger) -> None:
        """Best-effort: mark the order as FAILED in the DB.

        Swallows all exceptions so the caller's error path is not disrupted.
        """
        log.info("order_status_update_calling", new_status=OrderStatus.FAILED.value)
        start = time.monotonic()
        try:
            self._order_repo.update_status(order_id, OrderStatus.FAILED)
            duration_ms = round((time.monotonic() - start) * 1000, 1)
            log.info(
                "order_status_update_succeeded",
                new_status=OrderStatus.FAILED.value,
                duration_ms=duration_ms,
            )
        except DatabaseError as exc:
            duration_ms = round((time.monotonic() - start) * 1000, 1)
            log.error(
                "order_status_update_failed",
                new_status=OrderStatus.FAILED.value,
                error_code=exc.error_code,
                reason=str(exc),
                duration_ms=duration_ms,
                exc_info=True,
            )
        except Exception as exc:
            duration_ms = round((time.monotonic() - start) * 1000, 1)
            log.error(
                "order_status_update_unexpected_error",
                new_status=OrderStatus.FAILED.value,
                reason=str(exc),
                duration_ms=duration_ms,
                exc_info=True,
            )

    def _try_send_confirmation(
        self,
        request: PaymentRequest,
        transaction_id: str,
        log: structlog.BoundLogger,
    ) -> None:
        """Best-effort: send confirmation email; log but never raise on failure."""
        # customer_ref is already bound to the logger context; no need to
        # repeat it here — doing so would create a duplicate field and would
        # re-expose the raw customer_id if this method were ever called with
        # a context-stripped logger.
        log.info("confirmation_email_calling", transaction_id=transaction_id)
        start = time.monotonic()
        try:
            self._email_service.send_confirmation(
                request.customer_id,
                request.order_id,
                transaction_id,
            )
            duration_ms = round((time.monotonic() - start) * 1000, 1)
            log.info(
                "confirmation_email_sent",
                transaction_id=transaction_id,
                duration_ms=duration_ms,
            )
        except NotificationError as exc:
            duration_ms = round((time.monotonic() - start) * 1000, 1)
            log.warning(
                "confirmation_email_failed",
                error_code=exc.error_code,
                reason=str(exc),
                duration_ms=duration_ms,
                exc_info=True,
            )
        except Exception as exc:
            duration_ms = round((time.monotonic() - start) * 1000, 1)
            log.warning(
                "confirmation_email_unexpected_error",
                reason=str(exc),
                duration_ms=duration_ms,
                exc_info=True,
            )
