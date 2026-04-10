# Domain Modeling

How to represent domain concepts in code.

## Value Object

**What it is**: A small, immutable object defined entirely by its attributes. Two
Value Objects with the same attributes are equal, regardless of identity. They
have no lifecycle -- they're created, used, and discarded.

**Examples**: Money (amount + currency), DateRange (start + end), EmailAddress,
Temperature, GPS Coordinates, PercentageDiscount.

**Key properties**:
- **Immutable**: once created, never changes. Operations return new instances.
- **Equality by value**: Money(100, "USD") == Money(100, "USD") regardless of
  which instance.
- **Self-validating**: constructor enforces invariants. An invalid Value Object
  cannot exist.
- **Side-effect free**: methods return new values, never modify state.

**When to extract a Value Object**:
- A primitive (string, int, float) has validation rules or formatting logic
- The same group of fields appears together repeatedly
- You're passing primitives between functions and adding validation at each call
  site

**Pseudocode**:
```
class Money:
    amount: Decimal  // immutable
    currency: string  // immutable

    constructor(amount: Decimal, currency: string):
        if amount < 0:
            raise InvalidMoneyError("Amount cannot be negative")
        if currency not in VALID_CURRENCIES:
            raise InvalidCurrencyError(currency)
        self.amount = amount
        self.currency = currency

    function add(other: Money) -> Money:
        if self.currency != other.currency:
            raise CurrencyMismatchError
        return Money(self.amount + other.amount, self.currency)

    function multiply(factor: Decimal) -> Money:
        return Money(self.amount * factor, self.currency)

    function equals(other: Money) -> bool:
        return self.amount == other.amount and self.currency == other.currency
```

**Primitive obsession** is the main signal that Value Objects are missing. When
you see `price: float` paired with `currency: str` appearing together in
multiple places, that's a Value Object waiting to be extracted.

---

## Entity

**What it is**: An object with a distinct identity that persists through state
changes. Two Entities with the same attributes but different IDs are different
objects. They have a lifecycle (created, modified, archived/deleted).

**Examples**: User, Order, Account, Product, Shipment.

**Key properties**:
- **Identity**: equality based on ID, not attributes. Two users with the same
  name are different users.
- **Mutable state**: can change over time while maintaining identity.
- **Business rules**: encapsulates rules that govern its own state transitions.

**Pseudocode**:
```
class Order:
    id: OrderId                    // identity
    customer_id: CustomerId
    items: List[LineItem]
    status: OrderStatus
    placed_at: Timestamp | null

    function place():
        if self.items is empty:
            raise EmptyOrderError
        if self.status != OrderStatus.DRAFT:
            raise InvalidStateTransition(self.status, "placed")
        self.status = OrderStatus.PLACED
        self.placed_at = now()

    function cancel():
        if self.status not in [OrderStatus.PLACED, OrderStatus.CONFIRMED]:
            raise InvalidStateTransition(self.status, "cancelled")
        self.status = OrderStatus.CANCELLED

    function equals(other: Order) -> bool:
        return self.id == other.id  // identity, not attributes
```

---

## Aggregate

**What it is**: A cluster of Entities and Value Objects treated as a single unit
for data changes. One Entity is the **Aggregate Root** -- all external access
goes through it. The root enforces consistency invariants for the entire cluster.

**When to use**:
- Multiple objects must stay consistent within a single transaction
- External code should not directly modify internal objects

**Boundary rules**:
1. **External references only to the root**: other code holds a reference to the
   Aggregate Root, never to internal objects.
2. **Internal objects referenced by identity from outside**: if you need to refer
   to a LineItem from outside the Order, use its ID, not a direct object
   reference.
3. **Single transaction per aggregate**: one aggregate = one transactional
   boundary. Cross-aggregate consistency is eventual, not immediate.
4. **Keep aggregates small**: include only what must be consistent in a single
   transaction.

**The most common mistake**: making aggregates too large. If `Order` contains
`Customer` contains `Address` contains `Country`, your aggregate is too big.
Ask: "Must these be consistent in a single transaction?" An Order needs
consistent LineItems. It does not need the Customer's current address to be
consistent with the order total. Reference Customer by ID.

**Pseudocode**:
```
// Order is the Aggregate Root
class Order:
    id: OrderId
    items: List[LineItem]    // internal to aggregate
    status: OrderStatus

    function add_item(product_id: ProductId, quantity: int, unit_price: Money):
        // Root enforces invariants for the whole aggregate
        existing = self.find_item(product_id)
        if existing:
            existing.increase_quantity(quantity)
        else:
            self.items.append(LineItem(product_id, quantity, unit_price))
        self.recalculate_total()

    function remove_item(product_id: ProductId):
        self.items = [i for i in self.items if i.product_id != product_id]
        self.recalculate_total()

// LineItem is internal -- never accessed directly from outside the aggregate
class LineItem:
    product_id: ProductId
    quantity: int
    unit_price: Money

    function total() -> Money:
        return self.unit_price.multiply(self.quantity)
```

**Cross-aggregate references**: Orders reference Customers by `CustomerId`, not
by holding a `Customer` object. This keeps aggregates independent and allows
them to be stored, loaded, and transacted separately.

---

## Special Case (Null Object)

**What it is**: A subclass that provides default behavior for a special condition,
eliminating conditional logic (especially null checks) in calling code.

**When to use**:
- The same null/missing/unknown check appears in multiple places
- A "missing" or "unknown" variant has well-defined default behavior

**When NOT to use**: when the "missing" case genuinely requires different control
flow (e.g., redirect to login, return 404). Special Case works when the missing
case has *behavior*, not when it signals an error.

**Pseudocode**:
```
interface Customer:
    function name() -> string
    function discount_rate() -> Decimal
    function is_eligible_for_credit() -> bool

class RealCustomer implements Customer:
    function name() -> string: return self._name
    function discount_rate() -> Decimal: return self._tier.rate
    function is_eligible_for_credit() -> bool: return self._credit_score > 600

class MissingCustomer implements Customer:
    function name() -> string: return "Guest"
    function discount_rate() -> Decimal: return Decimal("0")
    function is_eligible_for_credit() -> bool: return false

// Calling code -- no null checks
function apply_discount(customer: Customer, total: Money) -> Money:
    rate = customer.discount_rate()
    return total.multiply(1 - rate)
```
