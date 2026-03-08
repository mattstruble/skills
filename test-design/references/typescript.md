# TypeScript Testing Patterns

Concrete patterns for applying the Test Desiderata in TypeScript/JavaScript, using Jest or Vitest.

## Anti-Pattern Examples

### Asserting defaults
```typescript
// Bad: testing that an object has the defaults you just defined
const user = new User();
expect(user.name).toBe("");
expect(user.age).toBe(0);
expect(user.active).toBe(false);
expect(user.role).toBe("user");
```
Instead, test the behavior that *depends* on those defaults.

### Echo-back assertions
```typescript
// Low value: just checking the function echoes your inputs back
const sub = service.createSubscription("user-1", PlanType.BASIC);
expect(sub.userId).toBe("user-1");   // you just passed this in
expect(sub.plan).toBe(PlanType.BASIC); // you just passed this in
```
Instead, assert on derived state: `sub.status`, `sub.expiresAt`, whether a charge was recorded.

### Over-mocking with jest.fn()
```typescript
// Bad: mocking everything and verifying calls
const mockDb = { save: jest.fn(), find: jest.fn() };
const mockEmailer = { send: jest.fn() };
const service = new OrderService(mockDb, mockEmailer);

service.process(order);

expect(mockDb.save).toHaveBeenCalledWith(order);
expect(mockDb.save).toHaveBeenCalledTimes(1);
expect(mockEmailer.send).toHaveBeenCalledWith(expect.objectContaining({ to: order.email }));
```
The `toHaveBeenCalledWith` / `toHaveBeenCalledTimes` family makes tests mirrors of the implementation. If you rename `save` to `persist`, or add a caching layer, these tests break -- but they'd still pass if `save` silently did nothing.

### Testing private methods
```typescript
// Bad: accessing private methods via bracket notation or casting
const result = (service as any)._hashPassword("secret");
expect(result).toContain(":");

// Also bad: testing internal utility functions that aren't exported
import { validateEmail } from "../src/user-service"; // internal helper
expect(validateEmail("foo@bar.com")).toBe(true);
```
Test these through the public API that uses them.

## Preferred Patterns

### Fakes over mocks for stateful collaborators
```typescript
class FakeUserRepository implements UserRepository {
  private users = new Map<string, User>();

  async findByEmail(email: string): Promise<User | null> {
    return [...this.users.values()].find(u => u.email === email) ?? null;
  }

  async save(user: User): Promise<User> {
    this.users.set(user.id, user);
    return user;
  }

  // Test helper — not part of the interface
  getAll(): User[] {
    return [...this.users.values()];
  }
}
```
Tests verify that data persisted and is retrievable -- not that `save` was called.

For **simple stateless interfaces**, a plain object with jest.fn() returning canned values is fine:
```typescript
const stubTaxProvider: TaxProvider = {
  getRate: jest.fn().mockReturnValue(0.10),
};
```

### Factory functions
```typescript
function makeUser(overrides: Partial<User> = {}): User {
  return {
    id: "user-1",
    email: "alice@example.com",
    username: "alice",
    isVerified: true,
    passwordHash: "hashed",
    createdAt: new Date(),
    ...overrides,
  };
}

function makeService(deps: Partial<ServiceDeps> = {}) {
  const repo = deps.repo ?? new FakeUserRepository();
  const emailer = deps.emailer ?? new FakeEmailService();
  const audit = deps.audit ?? new FakeAuditLogger();
  return { service: new UserService(repo, emailer, audit), repo, emailer, audit };
}
```
Tests only specify what's relevant to the scenario:
```typescript
const { service, repo } = makeService();
const result = await service.register(makeUser({ email: "new@test.com" }));
```

### Arrange-Act-Assert with clear separation
```typescript
test("upgrade charges prorated amount", async () => {
  // Arrange
  const { service, gateway } = makeService();
  await service.createSubscription("user-1", PlanType.BASIC);

  // Act
  await service.upgrade("user-1", PlanType.PRO);

  // Assert — check the outcome, not the call
  expect(gateway.charges).toHaveLength(2);
  const proration = gateway.charges[1].amount;
  expect(proration).toBeGreaterThan(0);
  expect(proration).toBeLessThan(PLAN_PRICES[PlanType.PRO]);
});
```

### Behavioral test names
```typescript
// Good: name says what broke
test("expired subscription blocks access", ...);
test("immediate cancel triggers refund for paid plan", ...);
test("locked account rejects correct password", ...);

// Bad: name says what was called
test("checkLimit returns false", ...);
test("cancel test 3", ...);
```

### Describe blocks for organization
```typescript
describe("UserService", () => {
  describe("register", () => {
    test("persists user to repository", async () => { ... });
    test("sends verification email", async () => { ... });
    test("rejects duplicate email", async () => { ... });
  });

  describe("login", () => {
    test("returns session token for valid credentials", async () => { ... });
    test("locks account after 5 failed attempts", async () => { ... });
  });
});
```
Group by *behavior*, not by method. Each `describe` block represents a capability.

### Jest/Vitest-specific tips
- Use `expect(fn).toThrow(/pattern/)` with a regex so failures are specific
- Use `expect(value).toBeCloseTo(expected, decimals)` for floating-point comparisons
- Use `test.each` when testing the same behavior across multiple inputs (validation rules), but don't use it to conflate unrelated scenarios
- Prefer `beforeEach` for creating fresh fakes per test. Avoid `beforeAll` for mutable state -- it creates hidden coupling between tests.
- Use `jest.useFakeTimers()` / `vi.useFakeTimers()` when testing time-dependent behavior instead of relying on real clocks
- Avoid `jest.mock()` at module level for dependencies you control -- use dependency injection and fakes instead. Reserve `jest.mock()` for third-party modules you can't inject.
- For async code, always `await` assertions or return the promise. Unawaited assertions silently pass.
