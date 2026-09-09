# Module Patterns

---

## Domain-Aligned Structure

Module structure should match domain structure, not implementation structure.

**Before (implementation-aligned):**

```
app/
  models/
    user.py
    order.py
    payment.py
  services/
    user.py
    order.py
    payment.py
  handlers/
    user.py
    order.py
    payment.py
```

**After (domain-aligned):**

```
app/
  users/
    models.py
    service.py
    api.py
  orders/
    models.py
    service.py
    api.py
  payments/
    models.py
    service.py
    api.py
```

**Why:** When you need to change how "orders" work, everything is in one
place. Implementation-aligned structures scatter a single domain concept
across three directories — every change touches three folders and requires
navigating between them. Domain-aligned structures keep related code
together, matching how engineers think about changes: "I need to modify
the orders feature," not "I need to modify the models layer."

---

## Dependency Direction as Design

Dependencies flow in one direction. Each layer imports from layers below,
never above.

```
API / Handlers
      ↓
Services / Use Cases
      ↓
Domain / Models
      ↓
Infrastructure (DB, HTTP clients, queues)
```

**Test it mechanically:**

```bash
# Domain should never import from handlers
grep -r 'from app.handlers import' app/domain/
# Should return nothing

# Services should never import from API layer
grep -r 'from app.api import' app/services/
# Should return nothing
```

If domain imports from handlers, the dependency direction is inverted —
core business logic is coupled to a delivery mechanism. Changing the API
framework would require rewriting domain code.

**Inversion signals:** If a lower layer needs to trigger behavior in a
higher layer, use dependency inversion — define an interface (protocol or
ABC) in the lower layer and implement it in the higher layer. The lower
layer depends on the abstraction; the higher layer provides the
implementation.

```python
# domain/notifications.py — defines what it needs
class OrderNotifier(Protocol):
    def order_placed(self, order: Order) -> None: ...

# api/email_notifier.py — provides the implementation
class EmailOrderNotifier:
    def order_placed(self, order: Order) -> None:
        send_email(order.customer.email, "Order confirmed", ...)
```
