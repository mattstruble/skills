# Git Commit Message — Simulated Eval

## Simulated `git diff --cached`

```diff
diff --git a/src/payments/models.py b/src/payments/models.py
index a3b2c1d..e7f8a09 100644
--- a/src/payments/models.py
+++ b/src/payments/models.py
@@ -1,5 +1,6 @@
 from django.db import models
+import uuid
 
 class Order(models.Model):
     status = models.CharField(max_length=50)
@@ -10,3 +11,15 @@ class Order(models.Model):
     def __str__(self):
         return f"Order {self.id}"
+
+class WebhookEvent(models.Model):
+    """Tracks processed Stripe webhook events to prevent duplicate handling."""
+    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
+    stripe_event_id = models.CharField(max_length=255, unique=True, db_index=True)
+    event_type = models.CharField(max_length=100)
+    processed_at = models.DateTimeField(auto_now_add=True)
+    payload = models.JSONField()
+
+    class Meta:
+        ordering = ['-processed_at']
+
+    def __str__(self):
+        return f"WebhookEvent {self.stripe_event_id} ({self.event_type})"

diff --git a/src/payments/webhook.py b/src/payments/webhook.py
index 0c1d2e3..f4a5b67 100644
--- a/src/payments/webhook.py
+++ b/src/payments/webhook.py
@@ -1,8 +1,49 @@
 import stripe
+import logging
 from django.http import HttpResponse
+from django.views.decorators.csrf import csrf_exempt
+from django.views.decorators.http import require_POST
 from django.conf import settings
+from .models import Order, WebhookEvent
+
+logger = logging.getLogger(__name__)
 
+@csrf_exempt
+@require_POST
 def stripe_webhook(request):
-    pass
+    payload = request.body
+    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
+
+    try:
+        event = stripe.Webhook.construct_event(
+            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
+        )
+    except ValueError:
+        logger.warning("Invalid Stripe webhook payload")
+        return HttpResponse(status=400)
+    except stripe.error.SignatureVerificationError:
+        logger.warning("Invalid Stripe webhook signature")
+        return HttpResponse(status=400)
+
+    if event['type'] == 'payment_intent.succeeded':
+        return handle_payment_intent_succeeded(event)
+
+    return HttpResponse(status=200)
+
+
+def handle_payment_intent_succeeded(event):
+    payment_intent = event['data']['object']
+    stripe_event_id = event['id']
+
+    # Idempotency: skip if already processed
+    if WebhookEvent.objects.filter(stripe_event_id=stripe_event_id).exists():
+        logger.info("Skipping duplicate webhook event %s", stripe_event_id)
+        return HttpResponse(status=200)
+
+    WebhookEvent.objects.create(
+        stripe_event_id=stripe_event_id,
+        event_type=event['type'],
+        payload=event,
+    )
+
+    order_id = payment_intent.get('metadata', {}).get('order_id')
+    if order_id:
+        Order.objects.filter(id=order_id).update(status='paid')
+        logger.info("Order %s marked as paid via webhook %s", order_id, stripe_event_id)
+
+    return HttpResponse(status=200)
```

## Skill Workflow Applied

### Step 1: Detect repo conventions
No repo-specific convention files detectable. No existing `git log` history available. Defaulting to conventional commits format.

### Step 2: Assess working tree
Staged files exist (`src/payments/webhook.py`, `src/payments/models.py`). Single commit path — work only with staged changes.

### Step 3: Analyze the changes

**`src/payments/webhook.py`** (modified):
- Implements `stripe_webhook` view (previously a stub/pass)
- Validates Stripe webhook signature using `stripe.Webhook.construct_event`
- Rejects invalid payload (400) and invalid signature (400)
- Routes `payment_intent.succeeded` events to a dedicated handler
- `handle_payment_intent_succeeded`: checks for duplicate event via `WebhookEvent`, records the event, updates `Order.status` to `'paid'`

**`src/payments/models.py`** (modified):
- Adds `WebhookEvent` model to track processed Stripe events
- Fields: UUID primary key, `stripe_event_id` (unique + indexed for fast dedup lookup), `event_type`, `processed_at`, `payload`
- Serves the idempotency check in the webhook handler

**Intent:** These two changes implement a single cohesive feature — Stripe webhook handling with idempotent event processing. `WebhookEvent` exists solely to support the handler; they cannot be separated meaningfully. One `feat(payments):` commit is correct.

**Scope:** Both files are under `src/payments/` → scope `payments`.

**Type:** `feat` — new capability (webhook handling) that didn't exist before.

**Body decision:** The idempotency design (storing events to deduplicate Stripe retries) is a non-obvious architectural choice worth surfacing in the body. A future reader might otherwise wonder why `WebhookEvent` exists or whether the dedup logic is intentional.

### Step 5: Commit message

```
feat(payments): handle Stripe payment_intent.succeeded webhook

Validates the Stripe signature before processing, then updates the
order status to 'paid'. Stores each processed event in WebhookEvent
to prevent duplicate handling if Stripe retries delivery.
```

---

## Final Commit Message

```
feat(payments): handle Stripe payment_intent.succeeded webhook

Validates the Stripe signature before processing, then updates the
order status to 'paid'. Stores each processed event in WebhookEvent
to prevent duplicate handling if Stripe retries delivery.
```
