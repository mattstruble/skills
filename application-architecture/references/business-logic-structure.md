# Business Logic Structure

How to organize the code that implements business rules.

## Transaction Script

**What it is**: A procedure that handles a single request from start to finish.
Each operation gets its own function that reads data, applies rules, and writes
results.

**When it fits**:
- Few business rules per operation
- Rules don't interact across operations
- Team is small or unfamiliar with OO modeling
- Rapid prototyping where speed of delivery matters more than structure

**When it breaks down**:
- Duplication: two scripts implement the same validation differently
- Conditionals: a script has deeply nested if/else for different cases
- Testing: the script is hard to test because business logic mixes with data
  access

**Pseudocode**:
```
function place_order(customer_id, items):
    customer = db.find_customer(customer_id)
    if customer.is_suspended:
        raise CustomerSuspendedError

    total = sum(item.price * item.quantity for item in items)
    if total > customer.credit_limit:
        raise CreditLimitExceededError

    order_id = db.insert_order(customer_id, items, total)
    db.update_customer_balance(customer_id, total)
    email.send_confirmation(customer.email, order_id)
    return order_id
```

Everything lives in one function. Simple, readable, obvious. The problem starts
when `place_order` grows to 200 lines with 15 conditional branches.

---

## Domain Model

**What it is**: An object model where domain concepts (Order, Customer, Money)
carry both data and behavior. Business rules live on the objects they govern.

**When it fits**:
- Complex rules that interact across entities
- Rules that change at different rates (pricing logic vs. fulfillment logic)
- Multiple ways to trigger the same business rules (API, batch, event)

**When it breaks down**:
- Domain is genuinely simple (CRUD with validation) -- the model adds ceremony
  without value
- Team has no experience with domain modeling -- risk of anemic models that are
  worse than Transaction Script

**Pseudocode**:
```
class Order:
    items: List[LineItem]
    customer: Customer
    status: OrderStatus

    function place():
        customer.validate_can_order()
        self.validate_items()
        self.total = self.calculate_total()
        customer.reserve_credit(self.total)
        self.status = OrderStatus.PLACED

    function calculate_total() -> Money:
        subtotal = sum(item.total() for item in self.items)
        return self.customer.pricing_tier.apply_discount(subtotal)

class LineItem:
    product: Product
    quantity: int
    unit_price: Money

    function total() -> Money:
        return self.unit_price * self.quantity
```

Business rules live on the objects they govern. `Order` knows how to place
itself. `Customer` knows its credit rules. `LineItem` knows how to calculate its
total.

---

## Service Layer

**What it is**: A thin layer of services that defines the application's operations
and coordinates between domain objects, infrastructure, and cross-cutting concerns
(transactions, authorization, logging).

**When it fits**:
- Multiple interfaces (API, CLI, queue consumer) need the same operations
- Operations require transaction coordination across multiple domain objects
- Cross-cutting concerns (auth, logging, metrics) need a single place to live

**When it breaks down**:
- The service layer accumulates business logic that should be in domain objects
  ("anemic domain model")
- Only one interface exists -- the service layer becomes a pass-through

**What a Service Layer is NOT**: It is not the place for business rules. Business
rules belong in the Domain Model. The Service Layer orchestrates: it calls domain
objects, manages transactions, and dispatches infrastructure side effects. If your
service methods are full of if/else business logic, the logic has leaked out of
the domain.

**Pseudocode**:
```
class OrderService:
    order_repo: OrderRepository
    payment_gateway: PaymentGateway
    event_bus: EventBus

    function place_order(command: PlaceOrderCommand) -> OrderId:
        // Service Layer coordinates, doesn't decide
        customer = self.customer_repo.find(command.customer_id)
        order = Order.create(customer, command.items)
        order.place()  // business logic lives in the domain

        self.order_repo.save(order)
        self.payment_gateway.authorize(order.total, customer.payment_method)
        self.event_bus.publish(OrderPlaced(order.id))
        return order.id
```

The service method is a recipe: create, validate (via domain), save, pay,
notify. No business decisions.

---

## Hexagonal Architecture (Ports and Adapters)

**What it is**: The domain and application logic sit at the center, communicating
with the outside world through ports (interfaces) and adapters (implementations).
Inbound adapters (HTTP controller, CLI, queue consumer) drive the application.
Outbound adapters (database, email, external API) are driven by the application.

**When it fits**:
- Domain logic must be testable without infrastructure
- Multiple inbound adapters (web, CLI, event handler)
- Multiple outbound adapters (swap databases, switch email providers)
- Long-lived application where infrastructure will change

**When it breaks down**:
- Single adapter per port with no plans for more -- you're building interfaces
  no one else will implement
- Simple CRUD with no domain logic to protect from infrastructure

**Pseudocode**:
```
// Port (interface) -- defined by the domain
interface OrderRepository:
    function find(id: OrderId) -> Order
    function save(order: Order)

// Adapter (implementation) -- lives outside the domain
class SqlOrderRepository implements OrderRepository:
    function find(id: OrderId) -> Order:
        row = db.query("SELECT ... WHERE id = ?", id)
        return Order.reconstitute(row)

    function save(order: Order):
        db.execute("INSERT ...", order.to_row())

// Application service uses the port, not the adapter
class PlaceOrderHandler:
    order_repo: OrderRepository  // port, not SqlOrderRepository

    function handle(command: PlaceOrderCommand):
        ...
```

The domain never imports anything from the infrastructure layer. All
dependencies point inward.

---

## Choosing: A Flowchart

```
Is business logic simple CRUD with <5 rules?
├─ YES -> Transaction Script. Stop.
└─ NO
    Are rules complex, with entities interacting?
    ├─ NO -> Transaction Script, but watch for duplication.
    └─ YES -> Domain Model.
         Do multiple interfaces need the same operations?
         ├─ NO -> Domain Model is sufficient. Service Layer optional.
         └─ YES -> Add a Service Layer over the Domain Model.
              Must domain logic be fully decoupled from infrastructure?
              ├─ NO -> Service Layer + Domain Model. Stop.
              └─ YES -> Hexagonal Architecture.
```
