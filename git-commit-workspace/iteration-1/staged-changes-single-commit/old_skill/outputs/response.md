# Git Commit Response (Old Skill — Baseline)

## Step 1: Detect repo conventions

No `.commitlintrc`, `.czrc`, or `CONTRIBUTING.md` found in this simulated repo. No prior `git log` to reference. Defaulting to conventional commit format.

## Step 2: Assess the working tree

```
$ git status
On branch main
Changes to be committed:
  (use "git restore --staged <file>..." to unstage)
        modified:   src/payments/webhook.py
        modified:   src/payments/models.py
```

Staged files exist — work only with these two files. Write a single commit.

## Step 3: Analyze the changes

```
$ git diff --cached
diff --git a/src/payments/webhook.py b/src/payments/webhook.py
index abc1234..def5678 100644
--- a/src/payments/webhook.py
+++ b/src/payments/webhook.py
@@ -1,10 +1,45 @@
+import stripe
+from .models import WebhookEvent, Order
+
+def handle_stripe_webhook(request):
+    payload = request.body
+    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
+
+    try:
+        event = stripe.Webhook.construct_event(
+            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
+        )
+    except stripe.error.SignatureVerificationError:
+        return HttpResponse(status=400)
+
+    if event['type'] == 'payment_intent.succeeded':
+        payment_intent = event['data']['object']
+        order_id = payment_intent['metadata'].get('order_id')
+
+        # Idempotency: skip if already processed
+        if WebhookEvent.objects.filter(stripe_event_id=event['id']).exists():
+            return HttpResponse(status=200)
+
+        order = Order.objects.get(id=order_id)
+        order.status = 'paid'
+        order.save()
+
+        WebhookEvent.objects.create(
+            stripe_event_id=event['id'],
+            event_type=event['type'],
+            processed=True,
+        )
+
+    return HttpResponse(status=200)

diff --git a/src/payments/models.py b/src/payments/models.py
index 1111111..2222222 100644
--- a/src/payments/models.py
+++ b/src/payments/models.py
@@ -10,3 +10,12 @@
+
+class WebhookEvent(models.Model):
+    stripe_event_id = models.CharField(max_length=255, unique=True)
+    event_type = models.CharField(max_length=100)
+    processed = models.BooleanField(default=False)
+    created_at = models.DateTimeField(auto_now_add=True)
+
+    class Meta:
+        indexes = [models.Index(fields=['stripe_event_id'])]
```

**Analysis:**

- `src/payments/webhook.py`: New handler for Stripe's `payment_intent.succeeded` event. Validates the webhook signature to prevent spoofing, checks idempotency via `WebhookEvent` lookup, updates the matching order's status to `paid`, and records the processed event.
- `src/payments/models.py`: New `WebhookEvent` model that tracks processed Stripe events (stores event ID, type, processed flag, and timestamp) to support idempotent webhook handling.

**Intent:** This is a new capability — Stripe payment webhook handling didn't exist before. Both files serve the same logical feature: receiving and processing `payment_intent.succeeded` events from Stripe.

**Type:** `feat` — new behavior introduced.

**Scope:** `payments` — both files live in `src/payments/`.

**Subject line draft:**
`feat(payments): handle Stripe payment_intent.succeeded webhook`

The subject is self-sufficient. No body needed — the intent is clear from the subject and the trade-offs (signature validation, idempotency via `WebhookEvent`) are standard patterns rather than non-obvious design decisions that would confuse a future reader.

## Commit message

```
feat(payments): handle Stripe payment_intent.succeeded webhook
```

---

*This is a single commit covering both files — they implement the same logical change (the webhook handler and the model it depends on belong together).*
