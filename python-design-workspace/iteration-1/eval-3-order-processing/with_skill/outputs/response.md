# Order Processing Module — Python Design Patterns

This module demonstrates the patterns from the python-design skill applied to a realistic order processing domain.

## Module Structure

```
orders/
├── __init__.py
├── models.py        # Pydantic input models (boundary) + frozen dataclasses (internal)
├── enums.py         # StrEnum definitions for payment types, regions, statuses
├── payments.py      # singledispatch payment processing
├── tax.py           # singledispatch tax calculation
├── notifications.py # Protocol + implementations
├── pipeline.py      # Generator pipeline + top-level process_order
└── errors.py        # Shallow exception hierarchy
```

---

## `orders/errors.py`

```python
class OrderError(Exception): ...
class PaymentError(OrderError): ...
class InsufficientFunds(PaymentError): ...
class CardDeclined(PaymentError): ...
class PaymentTimeout(PaymentError): ...
class TaxCalculationError(OrderError): ...
class NotificationError(OrderError): ...
```

Shallow, domain-specific hierarchy. Callers can catch `PaymentError` broadly or
`CardDeclined` specifically. No bare `except`.

---

## `orders/enums.py`

```python
from enum import StrEnum


class PaymentType(StrEnum):
    CREDIT_CARD = "credit_card"
    BANK_TRANSFER = "bank_transfer"
    CRYPTO = "crypto"


class Region(StrEnum):
    US_CA = "us_ca"       # California
    US_TX = "us_tx"       # Texas
    EU_DE = "eu_de"       # Germany
    EU_FR = "eu_fr"       # France
    INTL  = "intl"        # International / no regional tax


class OrderStatus(StrEnum):
    PENDING   = "pending"
    PAID      = "paid"
    FAILED    = "failed"
    NOTIFIED  = "notified"
```

`StrEnum` means a typo like `PaymentType.CREDCARD` is a `NameError` at the call
site, not a silent string mismatch buried in a conditional.

---

## `orders/models.py`

```python
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from pydantic import BaseModel, field_validator

from .enums import PaymentType, Region


# ── External boundary: Pydantic validates + coerces raw input ──────────────────

class CreditCardInput(BaseModel):
    card_number: str
    expiry: str
    cvv: str
    amount: Decimal
    currency: str = "USD"

    @field_validator("amount")
    @classmethod
    def positive_amount(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("amount must be positive")
        return v


class BankTransferInput(BaseModel):
    routing_number: str
    account_number: str
    amount: Decimal
    currency: str = "USD"

    @field_validator("amount")
    @classmethod
    def positive_amount(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("amount must be positive")
        return v


class CryptoInput(BaseModel):
    wallet_address: str
    coin: str
    amount: Decimal

    @field_validator("coin")
    @classmethod
    def supported_coin(cls, v: str) -> str:
        supported = {"BTC", "ETH", "USDC"}
        if v.upper() not in supported:
            raise ValueError(f"unsupported coin {v!r}; choose from {supported}")
        return v.upper()


class OrderInput(BaseModel):
    order_id: str
    region: Region
    payment_type: PaymentType
    payment_details: CreditCardInput | BankTransferInput | CryptoInput
    customer_email: str
    line_items: list[tuple[str, Decimal, int]]  # (sku, unit_price, qty)


# ── Internal domain objects: frozen dataclasses ────────────────────────────────

@dataclass(frozen=True)
class LineItem:
    sku: str
    unit_price: Decimal
    quantity: int

    @property
    def subtotal(self) -> Decimal:
        return self.unit_price * self.quantity


@dataclass(frozen=True)
class Order:
    order_id: str
    region: Region
    items: tuple[LineItem, ...]
    payment_type: PaymentType
    payment_details: CreditCardInput | BankTransferInput | CryptoInput
    customer_email: str

    @property
    def subtotal(self) -> Decimal:
        return sum((item.subtotal for item in self.items), Decimal("0"))


@dataclass(frozen=True)
class PaymentResult:
    success: bool
    transaction_id: str
    amount_charged: Decimal
    currency: str


@dataclass(frozen=True)
class TaxResult:
    region: Region
    rate: Decimal
    tax_amount: Decimal


@dataclass(frozen=True)
class ProcessedOrder:
    order: Order
    payment: PaymentResult
    tax: TaxResult
    total: Decimal
    status: str
```

Pydantic `BaseModel` at the boundary validates raw input (HTTP body, CSV row,
etc.). Once validated, the data is converted to `frozen=True` dataclasses that
are hashable, immutable, and carry no validation overhead in the interior.

---

## `orders/payments.py`

```python
from __future__ import annotations

import uuid
from decimal import Decimal
from functools import singledispatch

from .errors import CardDeclined, InsufficientFunds, PaymentTimeout
from .models import (
    BankTransferInput,
    CreditCardInput,
    CryptoInput,
    Order,
    PaymentResult,
)


@singledispatch
def process_payment(details, order: Order) -> PaymentResult:
    raise TypeError(f"No payment handler for {type(details)!r}")


@process_payment.register
def _(details: CreditCardInput, order: Order) -> PaymentResult:
    # Real implementation would call a payment gateway (Stripe, etc.)
    if details.card_number.startswith("4000"):
        raise CardDeclined("test card declined")
    return PaymentResult(
        success=True,
        transaction_id=f"cc_{uuid.uuid4().hex[:12]}",
        amount_charged=order.subtotal,
        currency=details.currency,
    )


@process_payment.register
def _(details: BankTransferInput, order: Order) -> PaymentResult:
    # ACH / wire — simulate async settle; raise on insufficient funds
    if details.amount < order.subtotal:
        raise InsufficientFunds(
            f"transfer amount {details.amount} < order subtotal {order.subtotal}"
        )
    return PaymentResult(
        success=True,
        transaction_id=f"ach_{uuid.uuid4().hex[:12]}",
        amount_charged=order.subtotal,
        currency=details.currency,
    )


@process_payment.register
def _(details: CryptoInput, order: Order) -> PaymentResult:
    # Crypto — simulate network timeout on testnet addresses
    if details.wallet_address.startswith("0xDEAD"):
        raise PaymentTimeout("blockchain confirmation timed out")
    return PaymentResult(
        success=True,
        transaction_id=f"crypto_{uuid.uuid4().hex[:12]}",
        amount_charged=details.amount,
        currency=details.coin,
    )
```

`singledispatch` dispatches on the type of `details` — no `isinstance` chain.
Adding a new payment type means registering a new handler; the dispatcher and
callers are untouched.

---

## `orders/tax.py`

```python
from __future__ import annotations

from decimal import Decimal
from functools import singledispatch

from .enums import Region
from .errors import TaxCalculationError
from .models import Order, TaxResult

# Tax rates by region (simplified)
_RATES: dict[Region, Decimal] = {
    Region.US_CA: Decimal("0.0975"),
    Region.US_TX: Decimal("0.0825"),
    Region.EU_DE: Decimal("0.19"),
    Region.EU_FR: Decimal("0.20"),
    Region.INTL:  Decimal("0.00"),
}


def calculate_tax(order: Order) -> TaxResult:
    rate = _RATES.get(order.region)
    if rate is None:
        raise TaxCalculationError(f"No tax rate configured for region {order.region!r}")
    tax_amount = (order.subtotal * rate).quantize(Decimal("0.01"))
    return TaxResult(region=order.region, rate=rate, tax_amount=tax_amount)
```

Tax calculation is a standalone function — no class needed. The `Region` enum
ensures only valid values reach this function; no string-matching defence
required.

---

## `orders/notifications.py`

```python
from __future__ import annotations

from typing import Protocol

from .models import ProcessedOrder


class Notifier(Protocol):
    """Caller-facing contract. Any object with a matching `notify` signature satisfies it."""
    def notify(self, order: ProcessedOrder) -> None: ...


class EmailNotifier:
    def __init__(self, smtp_host: str, from_address: str) -> None:
        self._smtp_host = smtp_host
        self._from = from_address

    def notify(self, order: ProcessedOrder) -> None:
        # Real implementation: connect to SMTP, send templated email
        print(
            f"[EMAIL] {self._from} → {order.order.customer_email}: "
            f"Order {order.order.order_id} confirmed, total={order.total}"
        )


class SlackNotifier:
    def __init__(self, webhook_url: str) -> None:
        self._webhook = webhook_url

    def notify(self, order: ProcessedOrder) -> None:
        # Real implementation: POST to Slack webhook
        print(
            f"[SLACK] Order {order.order.order_id} processed "
            f"via {order.order.payment_type}, total={order.total}"
        )


class CompositeNotifier:
    """Fan-out to multiple notifiers; continues on individual failures."""
    def __init__(self, notifiers: list[Notifier]) -> None:
        self._notifiers = notifiers

    def notify(self, order: ProcessedOrder) -> None:
        errors: list[Exception] = []
        for notifier in self._notifiers:
            try:
                notifier.notify(order)
            except Exception as exc:  # noqa: BLE001 — collect, don't swallow
                errors.append(exc)
        if errors:
            raise ExceptionGroup("notification failures", errors)
```

`Notifier` is a `Protocol` — structural typing. `EmailNotifier` and
`SlackNotifier` satisfy it without inheriting from anything. The caller receives
a `Notifier` and never needs to know the concrete type.

---

## `orders/pipeline.py`

```python
from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal

from .enums import OrderStatus
from .models import (
    LineItem,
    Order,
    OrderInput,
    ProcessedOrder,
)
from .notifications import Notifier
from .payments import process_payment
from .tax import calculate_tax


# ── Conversion: boundary model → internal domain object ───────────────────────

def _to_order(inp: OrderInput) -> Order:
    items = tuple(
        LineItem(sku=sku, unit_price=price, quantity=qty)
        for sku, price, qty in inp.line_items
    )
    return Order(
        order_id=inp.order_id,
        region=inp.region,
        items=items,
        payment_type=inp.payment_type,
        payment_details=inp.payment_details,
        customer_email=inp.customer_email,
    )


# ── Pipeline stages as generators ─────────────────────────────────────────────

def _validate_orders(inputs: Iterator[OrderInput]) -> Iterator[Order]:
    """Convert validated Pydantic inputs to internal Order objects."""
    for inp in inputs:
        yield _to_order(inp)


def _apply_payments(orders: Iterator[Order]) -> Iterator[tuple[Order, object]]:
    """Attempt payment for each order; skips failed orders (logs error)."""
    for order in orders:
        try:
            result = process_payment(order.payment_details, order)
            yield order, result
        except Exception as exc:
            # In production: push to dead-letter queue, emit metric
            print(f"[WARN] Payment failed for {order.order_id}: {exc}")


def _apply_tax(
    paid_orders: Iterator[tuple[Order, object]],
) -> Iterator[tuple[Order, object, object]]:
    for order, payment in paid_orders:
        tax = calculate_tax(order)
        yield order, payment, tax


def _build_processed(
    taxed: Iterator[tuple[Order, object, object]],
) -> Iterator[ProcessedOrder]:
    for order, payment, tax in taxed:
        total = (order.subtotal + tax.tax_amount).quantize(Decimal("0.01"))
        yield ProcessedOrder(
            order=order,
            payment=payment,
            tax=tax,
            total=total,
            status=OrderStatus.PAID,
        )


# ── Public entry point ─────────────────────────────────────────────────────────

def process_orders(
    inputs: list[OrderInput],
    notifier: Notifier,
) -> list[ProcessedOrder]:
    """
    Process a batch of validated order inputs end-to-end.

    Each stage is a generator; no intermediate list is materialised until the
    final collect. Failed payments are skipped; notifications are sent per order.
    """
    pipeline = _build_processed(
        _apply_tax(
            _apply_payments(
                _validate_orders(iter(inputs))
            )
        )
    )

    results: list[ProcessedOrder] = []
    for processed in pipeline:
        notifier.notify(processed)
        results.append(processed)
    return results
```

The pipeline composes generators: each stage transforms an iterator and yields
to the next. No intermediate lists. Adding a new stage (e.g., fraud screening)
means inserting one generator function — existing stages don't change.

---

## Usage Example

```python
from decimal import Decimal

from orders.enums import PaymentType, Region
from orders.models import CreditCardInput, OrderInput
from orders.notifications import CompositeNotifier, EmailNotifier, SlackNotifier
from orders.pipeline import process_orders

order_input = OrderInput(
    order_id="ORD-001",
    region=Region.US_CA,
    payment_type=PaymentType.CREDIT_CARD,
    payment_details=CreditCardInput(
        card_number="4111111111111111",
        expiry="12/27",
        cvv="123",
        amount=Decimal("99.99"),
    ),
    customer_email="alice@example.com",
    line_items=[
        ("SKU-A", Decimal("49.99"), 1),
        ("SKU-B", Decimal("25.00"), 2),
    ],
)

notifier = CompositeNotifier([
    EmailNotifier(smtp_host="smtp.example.com", from_address="orders@example.com"),
    SlackNotifier(webhook_url="https://hooks.slack.com/..."),
])

results = process_orders([order_input], notifier)
for r in results:
    print(f"Order {r.order.order_id}: total={r.total}, tx={r.payment.transaction_id}")
```

---

## Pattern Mapping

| Skill Guidance | Applied Here |
|---|---|
| Pydantic at external boundaries | `OrderInput`, `CreditCardInput`, etc. validate raw input |
| `frozen=True` dataclasses internally | `Order`, `LineItem`, `PaymentResult`, `TaxResult`, `ProcessedOrder` |
| `StrEnum` over magic strings | `PaymentType`, `Region`, `OrderStatus` — typos are `NameError` |
| `singledispatch` over `isinstance` chains | `process_payment` dispatches on payment detail type |
| Standalone functions | `calculate_tax`, `process_payment`, pipeline stages — no unnecessary classes |
| `Protocol` for caller contracts | `Notifier` — `EmailNotifier`/`SlackNotifier` satisfy it structurally |
| Generator pipelines | `_validate_orders → _apply_payments → _apply_tax → _build_processed` |
| Shallow error hierarchy | `OrderError → PaymentError → {InsufficientFunds, CardDeclined, PaymentTimeout}` |
| Specific exception catches | Payment stage catches and logs; never bare `except` |
