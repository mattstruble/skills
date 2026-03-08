# Go Testing Patterns

Concrete patterns for applying the Test Desiderata in Go, using the standard `testing` package and optionally `testify`.

## Anti-Pattern Examples

### Asserting defaults
```go
// Bad: testing that a struct has its zero values
user := User{}
assert.Equal(t, "", user.Name)
assert.Equal(t, 0, user.Age)
assert.False(t, user.Active)
assert.Equal(t, "user", user.Role) // this one IS a default, but tests the definition not behavior
```
Instead, test the behavior that *depends* on those defaults.

### Echo-back assertions
```go
// Low value: checking the function echoes inputs back
sub, _ := service.CreateSubscription("user-1", PlanBasic)
assert.Equal(t, "user-1", sub.UserID)   // you just passed this in
assert.Equal(t, PlanBasic, sub.Plan)      // you just passed this in
```
Instead, assert on derived state: `sub.Status`, `sub.ExpiresAt`, whether a charge was recorded in the fake.

### Over-mocking with generated mocks
```go
// Bad: asserting on internal calls with mockery/gomock
mockRepo.EXPECT().Save(gomock.Any()).Times(1).Return(nil)
mockEmailer.EXPECT().Send(gomock.Eq(user.Email), gomock.Any()).Times(1)

service.Register(input)

// These assertions verify implementation, not outcomes
```
The `EXPECT().Times(1)` and argument matchers make tests mirrors of the implementation. Use fakes for stateful collaborators instead.

### Testing unexported functions directly
```go
// Bad: testing internal helpers (only possible from same package)
func Test_hashPassword(t *testing.T) {
    result := hashPassword("secret")
    assert.Contains(t, result, ":")
}

func Test_isValidEmail(t *testing.T) {
    assert.True(t, isValidEmail("foo@bar.com"))
}
```
Test these through the exported API that uses them. If the logic is complex enough to need direct tests, it should be its own package with exported functions.

## Preferred Patterns

### Fakes over mocks for stateful collaborators
```go
// FakeUserRepo satisfies the UserRepository interface with in-memory storage.
type FakeUserRepo struct {
    users map[string]*User
}

func NewFakeUserRepo() *FakeUserRepo {
    return &FakeUserRepo{users: make(map[string]*User)}
}

func (r *FakeUserRepo) FindByEmail(email string) (*User, error) {
    for _, u := range r.users {
        if u.Email == email {
            return u, nil
        }
    }
    return nil, nil
}

func (r *FakeUserRepo) Save(u *User) error {
    r.users[u.ID] = u
    return nil
}

// Test helper — not part of the interface
func (r *FakeUserRepo) GetAll() []*User {
    result := make([]*User, 0, len(r.users))
    for _, u := range r.users {
        result = append(result, u)
    }
    return result
}
```
Tests verify that data persisted and is retrievable -- not that `Save` was called.

For **simple stateless interfaces**, a struct with a fixed return value is fine:
```go
type StubTaxProvider struct {
    Rate float64
}

func (s StubTaxProvider) GetRate(state, category string) float64 {
    return s.Rate
}
```

### Factory functions (constructor helpers)
```go
func makeService(t *testing.T, opts ...func(*testDeps)) (*UserService, *testDeps) {
    t.Helper()
    deps := &testDeps{
        repo:   NewFakeUserRepo(),
        email:  &FakeEmailService{},
        audit:  &FakeAuditLogger{},
    }
    for _, opt := range opts {
        opt(deps)
    }
    svc := NewUserService(deps.repo, deps.email, deps.audit)
    return svc, deps
}

func makeProduct(opts ...func(*Product)) Product {
    p := Product{
        SKU:      "WIDGET",
        Name:     "Widget",
        Price:    1000, // cents
        Category: "general",
        WeightLb: 1.0,
    }
    for _, opt := range opts {
        opt(&p)
    }
    return p
}
```
Tests only specify what's relevant:
```go
svc, deps := makeService(t)
p := makeProduct(func(p *Product) { p.Price = 5000 })
```

### Table-driven tests
Go's table-driven pattern naturally supports the composable property. Use it when testing the same behavior across multiple inputs:
```go
func TestRegistrationValidation(t *testing.T) {
    tests := []struct {
        name     string
        username string
        email    string
        password string
        wantErr  string
    }{
        {"short username", "ab", "a@b.com", "Str0ng!Pass", "username must be at least 3"},
        {"invalid email", "alice", "not-email", "Str0ng!Pass", "invalid email"},
        {"weak password", "alice", "a@b.com", "weak", "password must be at least 8"},
    }
    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            svc, _ := makeService(t)
            _, err := svc.Register(tt.username, tt.email, tt.password)
            require.Error(t, err)
            assert.Contains(t, err.Error(), tt.wantErr)
        })
    }
}
```
Each subtest is isolated via `t.Run`. Don't put unrelated scenarios in the same table just to reduce lines.

### Subtests for behavioral grouping
```go
func TestUserService(t *testing.T) {
    t.Run("Register", func(t *testing.T) {
        t.Run("persists user to repository", func(t *testing.T) {
            svc, deps := makeService(t)
            _, err := svc.Register("alice", "alice@example.com", "Str0ng!Pass")
            require.NoError(t, err)

            found, _ := deps.repo.FindByEmail("alice@example.com")
            assert.NotNil(t, found)
        })

        t.Run("sends verification email", func(t *testing.T) {
            svc, deps := makeService(t)
            svc.Register("alice", "alice@example.com", "Str0ng!Pass")

            assert.Contains(t, deps.email.VerificationsSent, "alice@example.com")
        })
    })
}
```

### Behavioral test names
```go
// Good: name says what broke
t.Run("expired subscription blocks access", ...)
t.Run("immediate cancel triggers refund for paid plan", ...)
t.Run("locked account rejects correct password", ...)

// Bad: name says what was called
t.Run("TestCheckLimit", ...)
t.Run("cancel3", ...)
```

### Go-specific tips
- Use `t.Helper()` in factory functions so test failures point to the calling test, not the helper
- Use `t.Parallel()` for independent tests to catch shared-state bugs and speed up the suite
- Use `t.Cleanup()` for teardown instead of `defer` when you need cleanup to run after subtests complete
- Prefer `require.NoError(t, err)` (stops on failure) over `assert.NoError(t, err)` (continues) when subsequent assertions depend on the operation succeeding. A nil-pointer panic from a failed operation is confusing.
- Use `testify/assert` for readable assertions, but avoid `testify/mock` for the same reasons you'd avoid gomock -- it encourages mock-call verification. Write fakes instead.
- For time-dependent tests, accept a `clock` interface or `func() time.Time` instead of calling `time.Now()` directly
- Use `_test.go` suffix for test files. Use `_test` package suffix (e.g., `package user_test`) to enforce testing through the public API, which naturally prevents testing unexported functions.
- For integration tests that need external resources, use `testcontainers-go` or build tags (`//go:build integration`) to separate them from unit tests
