# Data Access Strategy

How the application reads and writes persistent data.

## Direct ORM / Query Builder

**What it is**: Use the ORM or query builder directly in application code. No
additional abstraction layer.

**When it fits**:
- Schema maps closely to domain model
- Queries are simple and don't duplicate
- Small codebase, single developer or small team
- Prototyping / early-stage products

**When it breaks down**:
- Query logic duplicates across the codebase
- Business logic becomes entangled with query syntax
- Testing requires a database for every test

**Pseudocode**:
```
function get_active_orders(customer_id):
    return db.query(
        "SELECT * FROM orders WHERE customer_id = ? AND status = 'active'",
        customer_id
    )
```

Nothing wrong with this until `WHERE status = 'active'` appears in 15 places
and the definition of "active" changes.

---

## Active Record

**What it is**: Each domain object wraps a database row and knows how to persist
itself. The object contains data, business logic, and CRUD operations.

**When it fits**:
- Domain objects map 1:1 to database tables
- Business logic per entity is limited
- Framework provides Active Record out of the box (Rails, Django models)

**When it breaks down**:
- Domain model diverges from database schema
- Business logic grows complex -- the class becomes a kitchen sink of rules and
  queries
- Testing domain logic requires a database because persistence is coupled in

**Pseudocode**:
```
class Order(ActiveRecord):
    table = "orders"

    function place():
        self.validate()
        self.status = "placed"
        self.save()  // persistence method on the domain object

    function cancel():
        if self.status != "placed":
            raise InvalidStateError
        self.status = "cancelled"
        self.save()
```

The model knows how to save itself. Clean for simple cases, problematic when
`Order` grows to 30 methods mixing business logic with query logic.

---

## Repository

**What it is**: A collection-like interface that mediates between the domain model
and the data mapping layer. Domain objects don't know about persistence.

**When it fits**:
- Complex domain model with rich business logic
- Domain logic must be testable without a database
- Query specifications need to be composed or reused
- Multiple storage backends (e.g., database + cache + search index)

**When it breaks down**:
- Domain is simple CRUD -- Repository becomes a pass-through wrapper around the
  ORM
- Repository accumulates every query the application needs, becoming a God
  interface
- One method per query pattern defeats the purpose -- use specifications or
  query objects instead

**Pseudocode**:
```
interface OrderRepository:
    function find_by_id(id: OrderId) -> Order
    function find_active_for_customer(customer_id: CustomerId) -> List[Order]
    function save(order: Order)
    function remove(order: Order)

// Implementation lives in the infrastructure layer
class SqlOrderRepository implements OrderRepository:
    function find_by_id(id: OrderId) -> Order:
        row = db.query("SELECT ... WHERE id = ?", id)
        return OrderMapper.to_domain(row)

    function save(order: Order):
        row = OrderMapper.to_row(order)
        db.upsert("orders", row)
```

**Repository vs. DAO**: A Repository speaks the domain language (find active
orders for customer). A DAO speaks the database language (select where status
equals). Repository is a higher-level abstraction that may compose multiple data
access calls.

---

## Data Mapper

**What it is**: A layer that transfers data between domain objects and the
database, keeping them ignorant of each other. The domain model has no
persistence knowledge. The database schema has no knowledge of the domain.

**When it fits**:
- Domain schema diverges from database schema
- Need full independence between domain model evolution and database evolution
- Complex object graphs that don't map cleanly to tables

**When it breaks down**:
- Schema is simple and maps 1:1 to domain -- mapping layer adds ceremony
- Most ORMs (SQLAlchemy, Hibernate) *are* Data Mappers -- don't build one on
  top

**Note**: If your ORM supports mapping configuration (like SQLAlchemy's classical
mapping), you already have a Data Mapper. The pattern is about the *concept* of
separating domain from persistence, which mature ORMs implement for you.

**Pseudocode**:
```
// Domain object -- no persistence awareness
class Order:
    id: OrderId
    customer_id: CustomerId
    items: List[LineItem]
    total: Money

// Mapper -- translates between domain and database
class OrderMapper:
    function to_domain(row: DatabaseRow) -> Order:
        return Order(
            id=OrderId(row["id"]),
            customer_id=CustomerId(row["customer_id"]),
            items=self.item_mapper.to_domain_list(row["id"]),
            total=Money(row["total_cents"], row["currency"])
        )

    function to_row(order: Order) -> DatabaseRow:
        return {
            "id": order.id.value,
            "customer_id": order.customer_id.value,
            "total_cents": order.total.cents,
            "currency": order.total.currency
        }
```

---

## Gateway

**What it is**: An object that encapsulates access to an external system or
resource. One Gateway per external dependency.

**When it fits**:
- Wrapping a third-party API (payment processor, email service, external data
  source)
- Wrapping a specific infrastructure concern (file system, message queue)
- Want to test code that depends on external systems

**When it breaks down**:
- Wrapping an internal dependency you'll never swap -- just call it directly
- Gateway accumulates business logic that should live in the domain

**Pseudocode**:
```
interface PaymentGateway:
    function authorize(amount: Money, method: PaymentMethod) -> AuthorizationId
    function capture(auth_id: AuthorizationId) -> CaptureResult
    function refund(capture_id: CaptureId, amount: Money) -> RefundResult

class StripePaymentGateway implements PaymentGateway:
    function authorize(amount: Money, method: PaymentMethod) -> AuthorizationId:
        response = stripe_client.payment_intents.create(
            amount=amount.cents,
            currency=amount.currency,
            payment_method=method.stripe_id
        )
        return AuthorizationId(response.id)
```

**Gateway vs. Repository**: Gateway wraps *access to a resource*. Repository
provides *a collection of domain objects*. A Repository might use a Gateway
internally, but they solve different problems.

---

## Table Data Gateway

**What it is**: A single object that handles all data access for one database
table. Unlike Active Record, the gateway is separate from the domain objects.

**When it fits**:
- Reporting or analytics queries that don't map to domain objects
- Bulk operations where OO domain mapping adds overhead
- Integrating with legacy databases where you need procedural access

**When it breaks down**:
- Mixing Table Data Gateway with Domain Model patterns creates confusion about
  where data access lives

**Pseudocode**:
```
class OrderGateway:
    function find_all_for_customer(customer_id) -> List[Row]:
        return db.query(
            "SELECT * FROM orders WHERE customer_id = ?", customer_id
        )

    function insert(customer_id, items, total) -> int:
        return db.execute(
            "INSERT INTO orders (customer_id, total) VALUES (?, ?)",
            customer_id, total
        )

    function monthly_revenue_report(year, month) -> List[Row]:
        return db.query(
            "SELECT ... GROUP BY ... WHERE year = ? AND month = ?",
            year, month
        )
```

---

## Choosing: A Flowchart

```
Using an ORM with simple, non-duplicating queries?
├─ YES -> Use ORM directly. Stop.
└─ NO
    Does domain map 1:1 to tables with light business logic?
    ├─ YES -> Active Record (or ORM models with methods).
    └─ NO
         Is this for reporting/bulk operations, not domain logic?
         ├─ YES -> Table Data Gateway.
         └─ NO
              Do you need domain logic testable without a database?
              ├─ NO -> Data Mapper (your ORM likely is one). Stop.
              └─ YES -> Repository over Data Mapper.
                   Is this an external system, not a database?
                   └─ YES -> Gateway.
```
