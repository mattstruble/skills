---
name: logging
description: Use when writing a new service, adding error handling, implementing observability, or any time logging comes up. Also trigger when the user is debugging a production issue and wishes they had more context, when they ask what to log, when they're adding try/catch blocks, when they mention correlation IDs or request tracing, or when they're building anything that will run in production. Logging is massively undervalued — apply this skill proactively whenever the code being written will need to be operated or debugged later, even if the user doesn't explicitly ask about logging.
---

# Logging

Logging is one of the highest-leverage investments in a codebase, and one of the most neglected. Schools don't teach it. Most tutorials skip it. Then a service breaks at 2am and you're staring at a stack trace with no context.

The goal of logging is **operability**: the ability to understand what your system is doing, after the fact, without a debugger attached.

Use language-agnostic pseudocode in all examples unless the user specifies a language.

---

## What to Log

### Log all branches, not just the entry point

The most common logging mistake is logging only at the start of a function. When something goes wrong, you need to know *which path* was taken.

```
# Poor: you know the request arrived, nothing else
function handle_payment(order):
    log.info("handling payment", order_id=order.id)
    if order.total == 0:
        return skip_payment(order)       # silent
    if order.payment_method == "credit":
        return charge_card(order)        # silent
    return charge_wallet(order)          # silent

# Better: each branch is observable
function handle_payment(order):
    log.info("handling payment", order_id=order.id, total=order.total,
             method=order.payment_method)
    if order.total == 0:
        log.info("skipping payment: zero total", order_id=order.id)
        return skip_payment(order)
    if order.payment_method == "credit":
        log.info("charging card", order_id=order.id)
        return charge_card(order)
    log.info("charging wallet", order_id=order.id)
    return charge_wallet(order)
```

### Log enough context to reproduce — but not sensitive data

Errors without context are nearly useless. Log the state that led to the error — not just the message. But never log credentials, tokens, passwords, payment card numbers, or raw PII. Log identifiers (user_id, order_id) that let you look up sensitive data through secure channels — not the sensitive data itself.

```
# Safe: log identifiers
log.error("payment failed", user_id=user.id, order_id=order.id)

# Dangerous: log raw object state (may contain secrets, PII, tokens)
log.error("payment failed", user=user, order=order)
```

```
# Poor: you know it failed, you don't know why
try:
    result = process(item)
catch Exception as e:
    log.error("processing failed", error=e)

# Better: log identifiers and safe fields alongside the error
try:
    result = process(item)
catch Exception as e:
    log.error("processing failed",
              error=e,
              item_id=item.id,
              item_type=item.type,
              retry_count=item.retry_count)
```

### Log entry/exit of significant operations

For operations that take meaningful time or have side effects (DB writes, external API calls, queue publishes), log both entry and exit with duration.

```
log.debug("calling payment gateway", gateway=gateway.name, amount=order.total)
start = now()
response = gateway.charge(order)
log.info("payment gateway responded",
         gateway=gateway.name,
         status=response.status,
         duration_ms=elapsed(start))
```

---

## Log Levels

Use levels consistently so you can filter noise in production:

| Level | When to use |
|-------|-------------|
| **DEBUG** | Detailed internal state, decision points, loop iterations. Off in production by default. |
| **INFO** | Normal operations worth recording: requests received, jobs completed, config loaded. |
| **WARN** | Something unexpected happened but the system recovered. Worth investigating later. |
| **ERROR** | Something failed and requires attention. Include full context. |

A useful heuristic: if you'd want to see it during a production incident, it's INFO or higher. If you'd only want it when actively debugging a specific issue, it's DEBUG.

---

## Correlation IDs

In any system with multiple services or concurrent requests, logs from a single operation get scattered. Correlation IDs tie them together.

**Assign a correlation ID at the entry point** (HTTP request, queue message, job start) and propagate it through every downstream call and log line.

```
# Entry point: assign or accept a correlation ID
function handle_request(request):
    correlation_id = request.header("X-Correlation-ID") or generate_uuid()
    context.set("correlation_id", correlation_id)
    log.info("request received", correlation_id=correlation_id,
             path=request.path, method=request.method)
    start = now()
    response = route(request)
    log.info("request complete", correlation_id=correlation_id,
             status=response.status, duration_ms=elapsed(start))
    return response

# Downstream: pull from context, pass to log and outbound calls
function fetch_user(user_id):
    correlation_id = context.get("correlation_id")
    log.debug("fetching user", correlation_id=correlation_id, user_id=user_id)
    response = user_service.get(user_id,
                                headers={"X-Correlation-ID": correlation_id})
    ...
```

Now you can grep all logs for a single correlation ID and reconstruct exactly what happened for one request.

---

## Dynamic Log Level Control

Hardcoded log levels mean you either drown in DEBUG noise or fly blind in production. The fix: make log levels adjustable at runtime without redeployment.

**Minimum viable approach:** read the log level from an environment variable or config file that can be updated without restart.

**Better:** expose an admin endpoint or feature flag that changes the level per-service or per-user. The debug flag must be controlled by operators or admins -- not user-settable. A user-controllable debug flag is an information disclosure risk.

```
# Per-user debug logging: use a request-scoped logger, not a global set_level
# WRONG: logger.set_level(DEBUG)  -- mutates shared state, races with other requests
# RIGHT: create a request-scoped logger with the appropriate level
function handle_request(request):
    user_id = authenticate(request)
    if debug_flag_enabled_for(user_id):
        request_logger = logger.with_level(DEBUG)
    else:
        request_logger = logger.with_level(INFO)
    request_logger.info("handling request", user_id=user_id)
    ...
```

Per-user debug logging lets you turn on verbose output for a specific user reporting a bug, without flooding logs for everyone else. Use request-scoped or context-local loggers -- never mutate a shared logger's level in a concurrent server.

When reviewing a production incident, always ask: "Would dynamic log levels have helped here?" If the answer is yes, add runtime level control as part of the fix — not just the immediate bug.

---

## Structured Logging

Prefer key=value pairs or JSON over interpolated strings. Structured logs are searchable and parseable by log aggregation tools.

```
# Hard to query
log.info(f"User {user_id} placed order {order_id} for ${total}")

# Easy to query: filter by user_id, order_id, or total range
log.info("order placed", user_id=user_id, order_id=order_id, total=total)
```

---

## The Cultural Point

Logging is treated as an afterthought in most codebases because it's invisible when it works and painful only when it's missing — and by then, you're in an incident. The engineers who invest in logging early are the ones who sleep through incidents that would wake others up.

Good logging is a form of respect: for your future self, for your teammates, and for the users depending on your system.

Treat it like a first-class concern from the start.
