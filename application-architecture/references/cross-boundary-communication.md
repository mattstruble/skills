# Cross-Boundary Communication

How data crosses process, service, or team boundaries.

## Data Transfer Object (DTO)

**What it is**: A simple object that carries data between processes. Contains no
business logic -- just fields and serialization. Its purpose is to decouple the
internal domain model from the external contract.

**When to use**:
- Data crosses a network boundary (API response, message, event payload)
- Internal model contains fields the consumer shouldn't see
- Internal model structure shouldn't dictate the API contract
- Multiple consumers need different views of the same data

**When NOT to use**:
- Internal model and external contract are identical (no transformation needed)
- Single-process application where function parameters suffice

**Design principles**:
- **DTOs serve the consumer**: design them around what the caller needs, not
  what the database returns.
- **Flat over nested**: minimize nesting depth. Deep DTO hierarchies re-create
  the internal model's shape.
- **Version-friendly**: DTOs are your versioning surface. Adding optional fields
  is backward-compatible. Removing fields is not.

**Pseudocode**:
```
// Internal domain model -- rich, behavioral
class Order:
    id: OrderId
    customer: Customer
    items: List[LineItem]
    internal_notes: string       // should not leak to external consumers
    cost_breakdown: CostBreakdown // internal accounting detail

// DTO -- flat, consumer-oriented
class OrderResponse:
    order_id: string
    customer_name: string
    item_count: int
    total: string       // "149.99 USD" -- formatted for display
    status: string
    placed_at: string   // ISO 8601

// Mapper -- translates domain to DTO
function to_order_response(order: Order) -> OrderResponse:
    return OrderResponse(
        order_id=order.id.value,
        customer_name=order.customer.name,
        item_count=len(order.items),
        total=order.total.format(),
        status=order.status.value,
        placed_at=order.placed_at.isoformat()
    )
```

---

## Remote Facade

**What it is**: A coarse-grained interface over fine-grained internal operations,
designed to minimize network round trips. Each facade method represents a
complete use case, not a CRUD operation on a single entity.

**When to use**:
- Fine-grained internal API would require multiple network calls for a single
  user action
- External clients need a simple interface that hides internal complexity
- Reducing chattiness between distributed systems

**When NOT to use**:
- The facade starts accumulating business logic (it should delegate, not decide)
- Internal API is already coarse-grained

**Pseudocode**:
```
// Without facade: client makes 4 network calls
customer = api.get_customer(id)
orders = api.get_customer_orders(id)
recommendations = api.get_recommendations(id)
loyalty_points = api.get_loyalty_points(id)

// With facade: client makes 1 network call
class CustomerDashboardFacade:
    function get_dashboard(customer_id) -> CustomerDashboard:
        customer = customer_service.find(customer_id)
        orders = order_service.recent_for(customer_id)
        recommendations = recommendation_engine.for_customer(customer_id)
        points = loyalty_service.balance(customer_id)

        return CustomerDashboard(
            customer=to_customer_summary(customer),
            recent_orders=to_order_summaries(orders),
            recommendations=to_product_cards(recommendations),
            loyalty_points=points
        )
```

---

## Anti-Corruption Layer (ACL)

**What it is**: A translation layer between your model and an external system's
model. It prevents external concepts, naming conventions, and structures from
leaking into your domain.

**When to use**:
- Integrating with a legacy system that uses different terminology
- Consuming a third-party API whose model clashes with yours
- Merging with another team's service that models the same concepts differently

**When NOT to use**:
- The external system uses the same model as yours -- translation adds no value
- You control the external system and can change it to match

**Components**:
- **Translator**: converts between external and internal representations
- **Facade**: simplifies the external system's complex API
- **Adapter**: conforms the external system's interface to the interface your
  domain expects

**Pseudocode**:
```
// External system uses different terms and structure
// Their "Contract" = our "Order"
// Their "Counterparty" = our "Customer"
// Their "Instrument" = our "Product"

class LegacySystemAdapter:
    legacy_client: LegacyApiClient

    function find_customer_orders(customer_id: CustomerId) -> List[Order]:
        // Translate our terms to their terms
        counterparty_ref = self.translate_customer_id(customer_id)

        // Call external system in its language
        contracts = self.legacy_client.get_contracts(
            counterparty_ref=counterparty_ref,
            contract_type="PURCHASE"
        )

        // Translate their response to our domain
        return [self.translate_contract_to_order(c) for c in contracts]

    function translate_contract_to_order(contract) -> Order:
        return Order(
            id=OrderId(contract.contract_ref),
            customer_id=self.translate_counterparty(contract.counterparty),
            items=self.translate_instruments(contract.instruments),
            total=Money(contract.notional_amount, contract.settlement_currency),
            status=self.translate_status(contract.lifecycle_state)
        )
```

The rest of your code never sees "Contract", "Counterparty", or "Instrument".
The ACL absorbs the mismatch so your domain stays clean.

---

## Choosing: A Flowchart

```
Is the data crossing a process/network boundary?
├─ NO -> Direct function calls. No DTOs needed.
└─ YES
    Does the internal model differ from what the consumer needs?
    ├─ NO -> Pass the model directly (but watch for future divergence).
    └─ YES -> Use DTOs.
         Does the consumer need multiple fine-grained operations combined?
         ├─ YES -> Remote Facade that assembles DTOs from multiple sources.
         └─ NO -> Direct DTO mapping.
              Is the external system using a different model/terminology?
              ├─ YES -> Anti-Corruption Layer wrapping the external system.
              └─ NO -> Gateway is sufficient.
```
