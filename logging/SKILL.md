---
name: logging
description: You MUST apply this skill proactively when writing any code that will run in production — services, workers, queue consumers, schedulers, API servers (FastAPI, Flask, Django, gRPC), or any server-side code. Also trigger when adding error handling, implementing observability, adding try/catch blocks, mentioning correlation IDs or request tracing, or debugging a production issue where more context would help. Apply even when the user doesn't explicitly ask about logging — logging is massively undervalued. NOT for log aggregation infrastructure (see grafana-loki), query syntax (see logql), or reviewing existing logging code in PRs (see code-reviewer).
---

# Logging

Logging is how you see what your system did after the fact, without a debugger attached. It's the difference between resolving an incident in minutes and staring at a stack trace wishing you'd logged more.

The natural instinct is to treat logging as an afterthought — bolt it onto error handlers, rank it last in code review fix lists, add it "later." That instinct is wrong. Logging is a first-class design concern. Build it into the normal flow of the code, not just the failure path.

Match the user's language. If no language is specified or implied, use Python.

---

## Log the happy path, not just errors

The biggest gap in most logging: every error branch has a log line, but successful operations are silent. When investigating an incident, you need to see what the system *did*, not just what broke. If only failures are visible in logs, you can't distinguish "no traffic" from "everything worked fine."

Log the *outcome* of each significant operation — request handled, job completed, payment processed. One INFO line per significant operation on the happy path.

```python
# Gap: success is invisible
@app.route("/orders/<int:order_id>")
def get_order(order_id):
    order = db.get(order_id)
    if order is None:
        log.warning("order_not_found", order_id=order_id)
        return {"error": "not found"}, 404
    return serialize(order), 200  # silent — was this endpoint even called?

# Fixed: normal flow is observable
@app.route("/orders/<int:order_id>")
def get_order(order_id):
    order = db.get(order_id)
    if order is None:
        log.warning("order_not_found", order_id=order_id)
        return {"error": "not found"}, 404
    log.info("order_retrieved", order_id=order_id, status=order.status)
    return serialize(order), 200
```

This extends to branches too — log which path was taken through conditional logic, not just the entry point:

```python
def handle_payment(order):
    log.info("payment_started", order_id=order.id, total=order.total,
             method=order.payment_method)
    if order.total == 0:
        log.info("payment_skipped_zero_total", order_id=order.id)
        return skip_payment(order)
    if order.payment_method == "credit":
        log.info("charging_card", order_id=order.id)
        return charge_card(order)
    log.info("charging_wallet", order_id=order.id)
    return charge_wallet(order)
```

## Use structured logging consistently

Pick one format for the entire codebase and stick with it. Mixing %-interpolation, f-strings, and `extra={}` dicts across files makes logs harder to query, not easier.

Use keyword arguments that produce key-value pairs a log aggregator can filter on. The specific library (structlog, stdlib with a JSON formatter, etc.) matters less than consistency.

```python
# Inconsistent — three formats in one codebase, none queryable the same way
logger.info("User %s placed order %s", user_id, order_id)
logger.info(f"User {user_id} placed order {order_id}")
logger.info("order placed", extra={"user_id": user_id})

# Consistent — every log line is structured and queryable the same way
log.info("order_placed", user_id=user_id, order_id=order_id, total=total)
```

## Always include a correlation ID

Not just when the architecture is "obviously" distributed. Any request that touches a database, an API, or a queue benefits from a correlation ID. It costs one line at the entry point and pays back every time you trace a request through logs.

Generate it at the entry point. Bind it to the logger context so it appears in every subsequent log line automatically. Pass it in headers to downstream services.

```python
def handle_request(request):
    correlation_id = request.headers.get("X-Correlation-ID") or str(uuid4())
    log = logger.bind(correlation_id=correlation_id)
    log.info("request_received", method=request.method, path=request.path)
    # all subsequent calls using `log` include correlation_id automatically
```

## Log entry AND exit of external calls, with duration

When an external call fails, you need to know what was attempted, not just that something failed. When it succeeds, you still need the duration — that's how you spot degradation before it becomes an outage.

```python
# Gap: only failures are visible, no timing data
try:
    response = client.get(url, timeout=10)
except RequestException as e:
    log.error("shipping_api_failed", error=str(e))
    return {}

# Fixed: entry, exit, and duration are all observable
log.info("shipping_api_calling", url=url, tracking_number=tracking)
start = time.monotonic()
try:
    response = client.get(url, timeout=10)
    response.raise_for_status()
    duration_ms = (time.monotonic() - start) * 1000
    log.info("shipping_api_responded", status=response.status_code,
             duration_ms=round(duration_ms, 1))
    return response.json()
except RequestException as e:
    duration_ms = (time.monotonic() - start) * 1000
    log.warning("shipping_api_failed", error=str(e),
                duration_ms=round(duration_ms, 1))
    return {}
```

## In code reviews, treat missing logging as a production-readiness issue

Missing logging is an operability gap, not a nice-to-have. When reviewing code for production, rank logging alongside error handling — both affect your ability to operate and debug the system.

Flag these specifically:
- Endpoints or jobs with no logging on the success path
- External calls with no entry/exit logging or timing
- Error handlers that log the exception but not the state that led to it
- Request-handling code with no correlation ID

## Make log levels adjustable at runtime

Hardcoded log levels mean you either drown in noise or fly blind. At minimum, read the level from a config that can change without redeployment. Better: expose a mechanism to adjust per-service or per-user.

Per-user debug logging is especially powerful for production debugging — turn on verbose output for one user reporting a bug without flooding everyone else's logs. Use request-scoped loggers; never mutate shared logger state in a concurrent server.

```python
def handle_request(request):
    user_id = authenticate(request)
    if debug_enabled_for(user_id):
        req_log = logger.bind(correlation_id=corr_id).with_level(DEBUG)
    else:
        req_log = logger.bind(correlation_id=corr_id)
    req_log.info("request_received", user_id=user_id)
```

When reviewing a production incident, ask: "Would adjustable log levels have helped here?" If yes, add runtime level control as part of the fix.

---

## What not to log

- **Secrets and PII.** Never log credentials, tokens, passwords, or payment card numbers. Log identifiers (user_id, order_id) that let you look up sensitive data through secure channels.
- **Every loop iteration.** Log the loop's start, end, and count — not every step.
- **Redundant context.** If a correlation ID is bound to the logger, don't repeat it in the message string.

```python
# Dangerous: may contain secrets, PII, tokens
log.error("payment_failed", user=user, order=order)

# Safe: log identifiers only
log.error("payment_failed", user_id=user.id, order_id=order.id,
          payment_method=order.payment_method)
```
