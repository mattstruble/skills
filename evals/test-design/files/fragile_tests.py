"""Tests for DiscountEngine — these tests are fragile and break on every refactor."""

import pytest
from unittest.mock import MagicMock, patch, call


class TestDiscountEngine:
    def setup_method(self):
        self.mock_repo = MagicMock()
        self.mock_cache = MagicMock()
        self.mock_logger = MagicMock()
        self.mock_event_bus = MagicMock()
        self.engine = DiscountEngine(
            self.mock_repo, self.mock_cache, self.mock_logger, self.mock_event_bus
        )

    def test_apply_percentage_discount(self):
        self.mock_repo.find_discount.return_value = Discount(
            id="d1", type="percentage", value=10, min_order=0, active=True
        )
        self.mock_cache.get.return_value = None

        result = self.engine.apply("d1", order_total=100.00)

        self.mock_repo.find_discount.assert_called_once_with("d1")
        self.mock_cache.get.assert_called_once_with("discount:d1")
        self.mock_cache.set.assert_called_once_with("discount:d1", result, ttl=300)
        self.mock_logger.info.assert_called_once()
        self.mock_event_bus.publish.assert_called_once_with(
            "discount.applied", {"discount_id": "d1", "amount": 10.0}
        )
        assert result.original == 100.00
        assert result.discount_amount == 10.0
        assert result.final == 90.0

    def test_apply_fixed_discount(self):
        self.mock_repo.find_discount.return_value = Discount(
            id="d2", type="fixed", value=15, min_order=50, active=True
        )
        self.mock_cache.get.return_value = None

        result = self.engine.apply("d2", order_total=100.00)

        self.mock_repo.find_discount.assert_called_once_with("d2")
        self.mock_cache.get.assert_called_once_with("discount:d2")
        self.mock_cache.set.assert_called_once()
        self.mock_logger.info.assert_called()
        self.mock_event_bus.publish.assert_called_once()
        assert result.original == 100.00
        assert result.discount_amount == 15.0
        assert result.final == 85.0

    def test_discount_below_minimum(self):
        self.mock_repo.find_discount.return_value = Discount(
            id="d3", type="fixed", value=15, min_order=50, active=True
        )
        self.mock_cache.get.return_value = None

        with pytest.raises(OrderBelowMinimumError):
            self.engine.apply("d3", order_total=30.00)

        self.mock_repo.find_discount.assert_called_once_with("d3")
        self.mock_logger.warning.assert_called_once()
        self.mock_event_bus.publish.assert_not_called()

    def test_inactive_discount(self):
        self.mock_repo.find_discount.return_value = Discount(
            id="d4", type="percentage", value=10, min_order=0, active=False
        )
        self.mock_cache.get.return_value = None

        with pytest.raises(DiscountInactiveError):
            self.engine.apply("d4", order_total=100.00)

        self.mock_repo.find_discount.assert_called_once_with("d4")
        self.mock_logger.warning.assert_called_once()

    def test_cached_discount(self):
        cached = Discount(
            id="d1", type="percentage", value=10, min_order=0, active=True
        )
        self.mock_cache.get.return_value = cached

        result = self.engine.apply("d1", order_total=100.00)

        self.mock_cache.get.assert_called_once_with("discount:d1")
        self.mock_repo.find_discount.assert_not_called()
        assert result.final == 90.0

    def test_discount_not_found(self):
        self.mock_repo.find_discount.return_value = None
        self.mock_cache.get.return_value = None

        with pytest.raises(DiscountNotFoundError):
            self.engine.apply("d99", order_total=100.00)

        self.mock_repo.find_discount.assert_called_once_with("d99")

    def test_percentage_discount_caps_at_order_total(self):
        self.mock_repo.find_discount.return_value = Discount(
            id="d5", type="percentage", value=150, min_order=0, active=True
        )
        self.mock_cache.get.return_value = None

        result = self.engine.apply("d5", order_total=50.00)

        assert result.final == 0.0
        assert result.discount_amount == 50.0
