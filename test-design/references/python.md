# Python Testing Patterns

Concrete patterns for applying the Test Desiderata in Python, using pytest.

## Anti-Pattern Examples

### Asserting defaults
```python
# Bad: testing that a dataclass has the defaults you just defined
user = User()
assert user.name == ""
assert user.age == 0
assert user.active == False
assert user.role == "user"
```
Instead, test the behavior that *depends* on those defaults.

### Echo-back assertions
```python
# Low value: just checking the function echoes your inputs back
sub = service.create_subscription("user-1", PlanType.BASIC)
assert sub.user_id == "user-1"   # you just passed this in
assert sub.plan == PlanType.BASIC  # you just passed this in
```
Instead, assert on derived state: `sub.status`, `sub.expires_at`, whether a charge was recorded.

### Over-mocking with unittest.mock
```python
# Bad: mocking every collaborator and asserting on calls
def test_process_order(mock_db, mock_cache, mock_emailer, mock_logger):
    service = OrderService(mock_db, mock_cache, mock_emailer, mock_logger)
    service.process(order)
    mock_db.save.assert_called_once_with(order)
    mock_emailer.send.assert_called_once()
```
The `assert_called_once_with` / `assert_called` family makes tests mirrors of the implementation. Use fakes for stateful collaborators instead.

### Testing private methods
```python
# Bad: testing internal helpers directly
def test_hash_password(self):
    result = service._hash_password("secret")
    assert ":" in result

def test_is_valid_email(self):
    assert service._is_valid_email("foo@bar.com") is True
```
Test these through the public API that uses them (e.g., `register()`, `login()`).

## Preferred Patterns

### Fakes over mocks for stateful collaborators
```python
class FakeUserRepository:
    """In-memory fake that satisfies the UserRepository protocol."""
    def __init__(self):
        self._users: dict[str, User] = {}

    def find_by_email(self, email: str) -> User | None:
        return next((u for u in self._users.values() if u.email == email), None)

    def save(self, user: User) -> User:
        self._users[user.id] = user
        return user
```
Tests verify that data persisted and is retrievable -- not that `save` was called.

For **simple stateless interfaces** (e.g., a tax rate lookup), a stub or `MagicMock` returning canned values is fine:
```python
class StubTaxProvider:
    def __init__(self, rate=Decimal("0.10")):
        self._rate = rate
    def get_rate(self, state: str, category: str) -> Decimal:
        return self._rate
```

### Factory functions
```python
VALID_PASSWORD = "Str0ng!Pass"

def make_service(
    *,
    repo=None, email=None, audit=None,
) -> tuple[UserService, FakeUserRepository, FakeEmailService, FakeAuditLogger]:
    repo = repo or FakeUserRepository()
    email = email or FakeEmailService()
    audit = audit or FakeAuditLogger()
    return UserService(repo, email, audit), repo, email, audit

def make_product(
    sku="WIDGET", name="Widget", price=Decimal("10.00"), **overrides,
) -> Product:
    defaults = dict(sku=sku, name=name, price=price, category="general", weight_lbs=1.0)
    defaults.update(overrides)
    return Product(**defaults)
```
Tests only specify what's relevant to the scenario.

### Arrange-Act-Assert with clear separation
```python
def test_upgrade_charges_prorated_amount(self):
    # Arrange
    service, gateway, _, _ = make_service()
    service.create_subscription("user-1", PlanType.BASIC)

    # Act
    service.upgrade("user-1", PlanType.PRO)

    # Assert — check the *outcome* (a charge was recorded), not the call
    assert len(gateway.charges) == 2
    _, proration = gateway.charges[1]
    assert 0 < proration < PLAN_PRICES[PlanType.PRO]
```

### Behavioral test names
```python
# Good: name says what broke
def test_expired_subscription_blocks_access(): ...
def test_immediate_cancel_triggers_refund_for_paid_plan(): ...
def test_locked_account_rejects_correct_password(): ...

# Bad: name says what was called
def test_check_limit_returns_false(): ...
def test_cancel_3(): ...
```

### pytest-specific tips
- Use `pytest.raises(ValueError, match="...")` with a match pattern so failures are specific
- Use `pytest.approx()` or `Decimal` for floating-point comparisons
- Parametrize with `@pytest.mark.parametrize` when testing the same behavior across multiple inputs (e.g., validation rules), but don't parametrize unrelated scenarios just to reduce line count
- Prefer plain factory functions over `@pytest.fixture` when the setup is simple and you want explicit control. Fixtures shine for expensive shared resources (database connections, temp directories), not for building test objects.
- Use `conftest.py` for fixtures shared across multiple test modules, but keep it small -- a conftest with 200 lines of fixtures is hard to navigate
