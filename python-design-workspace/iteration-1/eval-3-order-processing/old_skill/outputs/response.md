# Order Processing Module — Python Design Patterns

Using the skill guidance, here is a complete module structure applying the recommended Python patterns.

---

## Module Structure

```
orders/
├── __init__.py
├── models.py        # Domain objects (frozen dataclasses + enums)
├── tax.py           # Tax calculation (standalone functions)
├── payment.py       # Payment processing (singledispatch)
├── notifications.py # Notification sending (standalone functions)
└── processor.py     # Top-level orchestration
```

---

## `orders/models.py` — Domain Objects

```python
from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum


class PaymentType(StrEnum):
    CREDIT_CARD = "credit_card"
    BANK_TRANSFER = "bank_transfer"
    CRYPTO = "crypto"


class OrderStatus(StrEnum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    FAILED = "failed"


class Region(StrEnum):
    US = "us"
    EU = "eu"
    APAC = "apac"


@dataclass(frozen=True)
class LineItem:
    product_id: str
    quantity: int
    unit_price: Decimal


@dataclass(frozen=True)
class Order:
    order_id: str
    region: Region
    payment_type: PaymentType
    items: tuple[LineItem, ...]
    status: OrderStatus = OrderStatus.PENDING

    @property
    def subtotal(self) -> Decimal:
        return sum(item.unit_price * item.quantity for item in self.items)


@dataclass(frozen=True)
class ProcessedOrder:
    order: Order
    tax_amount: Decimal
    total: Decimal
    status: OrderStatus
    notification_sent: bool
```

---

## `orders/tax.py` — Tax Calculation

Tax rates are standalone functions operating on domain objects.

```python
from decimal import Decimal
from .models import Order, Region

_TAX_RATES: dict[Region, Decimal] = {
    Region.US:   Decimal("0.08"),
    Region.EU:   Decimal("0.20"),
    Region.APAC: Decimal("0.10"),
}


def get_tax_rate(region: Region) -> Decimal:
    return _TAX_RATES[region]


def calculate_tax(order: Order) -> Decimal:
    rate = get_tax_rate(order.region)
    return (order.subtotal * rate).quantize(Decimal("0.01"))
```

---

## `orders/payment.py` — Payment Processing with `singledispatch`

Different payment types handled via dispatch rather than `isinstance` chains.

```python
from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal
from functools import singledispatch
from pydantic import BaseModel, field_validator

from .models import OrderStatus, PaymentType


# --- Pydantic models at the external boundary ---

class CreditCardPayload(BaseModel):
    card_number: str
    expiry: str
    cvv: str
    amount: Decimal

    @field_validator("card_number")
    @classmethod
    def validate_card_number(cls, v: str) -> str:
        digits = v.replace(" ", "").replace("-", "")
        if not digits.isdigit() or len(digits) != 16:
            raise ValueError("card_number must be 16 digits")
        return digits


class BankTransferPayload(BaseModel):
    account_number: str
    routing_number: str
    amount: Decimal


class CryptoPayload(BaseModel):
    wallet_address: str
    currency: str
    amount: Decimal

    @field_validator("wallet_address")
    @classmethod
    def validate_wallet(cls, v: str) -> str:
        if len(v) < 26:
            raise ValueError("wallet_address too short")
        return v


# --- Internal domain representation ---

@dataclass(frozen=True)
class PaymentResult:
    success: bool
    transaction_id: str | None
    status: OrderStatus
    message: str


# --- Dispatch ---

@singledispatch
def process_payment(payload) -> PaymentResult:
    raise NotImplementedError(f"No payment handler for {type(payload)}")


@process_payment.register
def _(payload: CreditCardPayload) -> PaymentResult:
    # Call credit card gateway
    transaction_id = f"cc-{payload.card_number[-4:]}"
    return PaymentResult(
        success=True,
        transaction_id=transaction_id,
        status=OrderStatus.CONFIRMED,
        message="Credit card charged successfully",
    )


@process_payment.register
def _(payload: BankTransferPayload) -> PaymentResult:
    transaction_id = f"bt-{payload.account_number[-6:]}"
    return PaymentResult(
        success=True,
        transaction_id=transaction_id,
        status=OrderStatus.CONFIRMED,
        message="Bank transfer initiated",
    )


@process_payment.register
def _(payload: CryptoPayload) -> PaymentResult:
    transaction_id = f"crypto-{payload.wallet_address[:8]}"
    return PaymentResult(
        success=True,
        transaction_id=transaction_id,
        status=OrderStatus.CONFIRMED,
        message=f"{payload.currency} payment received",
    )


def make_payment_payload(
    payment_type: PaymentType,
    raw: dict,
) -> CreditCardPayload | BankTransferPayload | CryptoPayload:
    """Validation boundary: raw external input → typed payload."""
    match payment_type:
        case PaymentType.CREDIT_CARD:
            return CreditCardPayload(**raw)
        case PaymentType.BANK_TRANSFER:
            return BankTransferPayload(**raw)
        case PaymentType.CRYPTO:
            return CryptoPayload(**raw)
```

---

## `orders/notifications.py` — Notifications

```python
from .models import Order, OrderStatus, ProcessedOrder


def _subject_for_status(status: OrderStatus) -> str:
    match status:
        case OrderStatus.CONFIRMED:
            return "Your order has been confirmed"
        case OrderStatus.FAILED:
            return "There was a problem with your order"
        case OrderStatus.PENDING:
            return "Your order is pending"


def build_notification(processed: ProcessedOrder) -> dict:
    return {
        "order_id": processed.order.order_id,
        "subject": _subject_for_status(processed.status),
        "total": str(processed.total),
        "status": str(processed.status),
    }


def send_notification(processed: ProcessedOrder) -> bool:
    payload = build_notification(processed)
    # Send via email/SMS/webhook — stubbed here
    print(f"[notify] {payload['subject']} — order {payload['order_id']}")
    return True
```

---

## `orders/errors.py` — Shallow Error Hierarchy

```python
class OrderError(Exception): ...
class PaymentError(OrderError): ...
class TaxError(OrderError): ...
class NotificationError(OrderError): ...
```

---

## `orders/processor.py` — Orchestration

```python
from decimal import Decimal

from .errors import PaymentError
from .models import Order, OrderStatus, ProcessedOrder
from .payment import make_payment_payload, process_payment
from .tax import calculate_tax
from .notifications import send_notification


def process_order(order: Order, payment_raw: dict) -> ProcessedOrder:
    tax = calculate_tax(order)
    total = order.subtotal + tax

    try:
        payload = make_payment_payload(order.payment_type, payment_raw)
        result = process_payment(payload)
    except (ValueError, Exception) as exc:
        raise PaymentError(f"Payment failed for order {order.order_id}") from exc

    processed = ProcessedOrder(
        order=order,
        tax_amount=tax,
        total=total,
        status=result.status,
        notification_sent=False,
    )

    sent = send_notification(processed)

    return ProcessedOrder(
        order=order,
        tax_amount=tax,
        total=total,
        status=result.status,
        notification_sent=sent,
    )
```

---

## Usage Example

```python
from decimal import Decimal
from orders.models import LineItem, Order, PaymentType, Region
from orders.processor import process_order

order = Order(
    order_id="ord-001",
    region=Region.US,
    payment_type=PaymentType.CREDIT_CARD,
    items=(
        LineItem("sku-abc", 2, Decimal("49.99")),
        LineItem("sku-xyz", 1, Decimal("19.99")),
    ),
)

result = process_order(order, {
    "card_number": "4111111111111111",
    "expiry": "12/26",
    "cvv": "123",
    "amount": order.subtotal,
})

print(result.total, result.status)
```

---

## Pattern Summary

| Pattern used | Where applied | Why |
|---|---|---|
| `StrEnum` | `PaymentType`, `OrderStatus`, `Region` | Prevents typos, enables exhaustive matching |
| `@dataclass(frozen=True)` | `Order`, `LineItem`, `ProcessedOrder`, `PaymentResult` | Immutable domain objects |
| Pydantic `BaseModel` | `CreditCardPayload`, `BankTransferPayload`, `CryptoPayload` | Validate raw external input at the boundary |
| `singledispatch` | `process_payment` | Dispatch by type without `isinstance` chains |
| `match`/`case` | `make_payment_payload`, `_subject_for_status` | Exhaustive structural matching on enums |
| Shallow error hierarchy | `OrderError` → `PaymentError` etc. | Specific catch sites without deep inheritance |
| Standalone functions | `calculate_tax`, `send_notification`, `build_notification` | Operations on data, not methods on objects |
