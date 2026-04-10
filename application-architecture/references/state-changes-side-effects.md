# State Changes and Side Effects

How the system handles writes, reactions, and derived state.

## Unit of Work

**What it is**: Tracks objects affected by a business transaction and coordinates
writing changes to the database as a single atomic operation. It knows which
objects are new, modified, or deleted, and flushes them all at commit time.

**When to use**:
- Multiple objects change in a single operation and must commit or fail together
- Need to minimize database round trips by batching writes

**When NOT to use**:
- Your ORM already implements Unit of Work (most do -- SQLAlchemy's Session,
  Hibernate's Session, Entity Framework's DbContext). Don't rebuild what exists.
- Single-object updates that don't need transactional grouping

**Pseudocode**:
```
class UnitOfWork:
    new_objects: List
    dirty_objects: List
    removed_objects: List

    function register_new(obj):
        self.new_objects.append(obj)

    function register_dirty(obj):
        self.dirty_objects.append(obj)

    function register_removed(obj):
        self.removed_objects.append(obj)

    function commit():
        begin_transaction()
        for obj in self.new_objects: insert(obj)
        for obj in self.dirty_objects: update(obj)
        for obj in self.removed_objects: delete(obj)
        commit_transaction()

// Usage
uow = UnitOfWork()
order = Order.create(customer, items)
uow.register_new(order)
customer.debit(order.total)
uow.register_dirty(customer)
uow.commit()  // single transaction
```

**In practice**: you almost never write a Unit of Work from scratch. The pattern
matters because it explains what your ORM's session/context is doing, and why
you should commit once at the end of a request, not after every individual save.

---

## Domain Events

**What it is**: When something significant happens in the domain, the domain
object raises an event. Other parts of the system listen for these events and
react. The event producer doesn't know who's listening or what they do.

**When to use**:
- A state change should trigger independent side effects (send email, update
  cache, notify another service, update a read model)
- Side effects should not be coupled to the core operation (adding a new side
  effect shouldn't require modifying the domain logic)
- Different bounded contexts need to react to the same event

**When NOT to use**:
- The "event" is really just a synchronous function call within the same module.
  If there's one handler and it's in the same process, just call the function.
- Debugging event chains is significantly harder than debugging direct calls.
  Don't add events for elegance.

**Pseudocode**:
```
class Order:
    events: List[DomainEvent]

    function place():
        // ... business logic ...
        self.status = OrderStatus.PLACED
        self.events.append(OrderPlaced(
            order_id=self.id,
            customer_id=self.customer_id,
            total=self.total,
            placed_at=now()
        ))

// Event handlers -- separate concerns, decoupled from Order
class SendConfirmationEmail:
    function handle(event: OrderPlaced):
        email.send_order_confirmation(event.customer_id, event.order_id)

class UpdateInventory:
    function handle(event: OrderPlaced):
        for item in event.items:
            inventory.reserve(item.product_id, item.quantity)

class NotifyWarehouse:
    function handle(event: OrderPlaced):
        warehouse_queue.enqueue(FulfillmentRequest(event.order_id))
```

**Event dispatch timing**: Dispatch events after the transaction commits, not
during. If the transaction rolls back, the events should never have been sent.
Collect events on the domain object, then dispatch after the Unit of Work
commits.

---

## CQRS (Command Query Responsibility Segregation)

**What it is**: Separate the read model from the write model. Commands (writes)
go through the domain model. Queries (reads) go through a separate, optimized
read model that may have a different schema, different storage, or be
denormalized for performance.

**When to use**:
- Read and write patterns are fundamentally different (many reads, few writes,
  or vice versa)
- Read model needs denormalization that would complicate the write model
- Read and write scaling requirements differ significantly

**When NOT to use**:
- Read and write models are the same shape. CQRS adds two models and
  synchronization complexity. If the same model serves both, it's not worth it.
- Small application where a single model and a few database views suffice

**Pseudocode**:
```
// Write side -- domain model, full business rules
class PlaceOrderHandler:
    function handle(command: PlaceOrderCommand):
        order = Order.create(command.customer_id, command.items)
        order.place()
        order_repo.save(order)
        event_bus.publish(order.events)

// Read side -- denormalized, optimized for queries
class OrderReadModel:
    order_id: string
    customer_name: string
    item_count: int
    total_display: string
    status: string

class OrderDashboardQuery:
    function recent_orders(customer_id) -> List[OrderReadModel]:
        return read_db.query(
            "SELECT * FROM order_dashboard WHERE customer_id = ? "
            "ORDER BY placed_at DESC LIMIT 20",
            customer_id
        )

// Synchronization: event handler updates the read model
class OrderReadModelUpdater:
    function handle(event: OrderPlaced):
        read_db.upsert("order_dashboard", {
            "order_id": event.order_id,
            "customer_name": event.customer_name,
            "item_count": event.item_count,
            "total_display": event.total.format(),
            "status": "placed"
        })
```

**CQRS does not require Event Sourcing.** These are orthogonal patterns. You can
have CQRS with a traditional relational database and simple event-based sync.

---

## Event Sourcing

**What it is**: Instead of storing the current state of an entity, store the
sequence of events that led to the current state. The event log is the source of
truth. Current state is derived by replaying events.

**When to use**:
- Complete audit trail is a business requirement (financial transactions, legal,
  compliance)
- Need to reconstruct the state of any entity at any point in time
- Domain naturally fits as a sequence of events (ledger, order lifecycle, game
  moves)
- Events are the primary integration mechanism with other systems

**When NOT to use**:
- Audit trail is a nice-to-have, not a business requirement. The complexity cost
  is enormous: event schema evolution, snapshot management, eventually consistent
  read models, replay performance.
- Domain state is naturally "current" (user profile, settings, preferences).
  Event-sourcing a user profile means replaying 50 events to show a name.

**Pseudocode**:
```
// Events -- immutable facts about what happened
class AccountOpened: { account_id, owner_id, opened_at }
class MoneyDeposited: { account_id, amount, deposited_at }
class MoneyWithdrawn: { account_id, amount, withdrawn_at }

// Aggregate rebuilt from events
class BankAccount:
    function apply(event):
        match event:
            case AccountOpened: self.balance = Money(0, "USD")
            case MoneyDeposited: self.balance = self.balance.add(event.amount)
            case MoneyWithdrawn: self.balance = self.balance.subtract(event.amount)

    function withdraw(amount: Money):
        if self.balance < amount:
            raise InsufficientFundsError
        self.record(MoneyWithdrawn(self.id, amount, now()))

// Event Store
class EventStore:
    function load(aggregate_id) -> List[Event]:
        return db.query(
            "SELECT * FROM events WHERE aggregate_id = ? ORDER BY sequence",
            aggregate_id
        )

    function save(aggregate_id, new_events, expected_version):
        // Optimistic concurrency: fail if version changed
        if current_version(aggregate_id) != expected_version:
            raise ConcurrencyConflictError
        for event in new_events:
            db.insert("events", aggregate_id, event, next_sequence())

// Rebuilding state
function load_account(account_id) -> BankAccount:
    events = event_store.load(account_id)
    account = BankAccount()
    for event in events:
        account.apply(event)
    return account
```

**Snapshots**: for aggregates with many events, periodically save a snapshot of
the current state. Load the latest snapshot, then replay only events after it.

**Event schema evolution**: events are immutable, but your code evolves. You need
a strategy for handling old event formats: upcasting (transform old events to
new format on read) or versioned event handlers.

---

## Choosing: An Escalation Ladder

```
Single-table writes with no downstream effects?
├─ YES -> Direct ORM transactions. Stop.
└─ NO
    Multiple objects must commit atomically?
    ├─ YES -> Unit of Work (your ORM probably does this).
    └─ ALSO: state changes trigger independent side effects?
         ├─ YES -> Add Domain Events.
         └─ NO -> Unit of Work alone is sufficient.
              Read and write models fundamentally differ?
              ├─ YES -> CQRS (separate read/write models).
              └─ NO -> Domain Events without CQRS.
                   Must reconstruct state at any historical point?
                   ├─ YES -> Event Sourcing (event log is source of truth).
                   └─ NO -> CQRS with traditional persistence.
```

**The complexity tax**: each step on this ladder adds significant operational
complexity. Event Sourcing in particular requires event store infrastructure,
snapshot management, event schema versioning, and eventually consistent read
models. Don't escalate without a concrete business requirement driving it.
