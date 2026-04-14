# Additional Patterns

Patterns from the broader software design canon that appear frequently in game development.

---

## Factory

**Intent**: Centralize object construction logic, decoupling callers from concrete types and enabling construction from data.

**Problem**: Spawning game objects requires knowing their concrete types. When you have 50 enemy types, every spawner must `#include` every enemy header. Adding a new type requires modifying spawner code. You want to spawn enemies from a string name loaded from a data file.

**Solution**: A factory centralizes construction. Callers pass a type identifier; the factory returns the appropriate object.

**Simple factory function**:
```cpp
Entity* createEnemy(const std::string& type, Vector3 pos) {
    if (type == "goblin")    return new Goblin(pos);
    if (type == "skeleton")  return new Skeleton(pos);
    if (type == "troll")     return new Troll(pos);
    return nullptr;
}
```

**Registry-based factory** (preferred for extensibility):
```cpp
class EntityFactory {
    using Creator = std::function<Entity*(Vector3)>;
    std::unordered_map<std::string, Creator> creators;
public:
    void registerType(const std::string& name, Creator creator) {
        creators[name] = creator;
    }

    Entity* create(const std::string& name, Vector3 pos) {
        auto it = creators.find(name);
        if (it == creators.end()) return nullptr;
        return it->second(pos);
    }
};

// Registration (at startup or via static initializers):
factory.registerType("goblin",   [](Vector3 p) { return new Goblin(p); });
factory.registerType("skeleton", [](Vector3 p) { return new Skeleton(p); });

// Usage:
Entity* e = factory.create(jsonData["type"], spawnPos);
```

**Abstract Factory**: A family of related factories that produce compatible objects. Use when you need to swap entire sets of objects (e.g., different enemy tiers, different UI themes).

**Trade-offs**:
- Simple factory functions are fine for small, stable type sets.
- Registry factories enable data-driven spawning and modding but add indirection.
- Error handling: what happens when an unknown type is requested? Return null, throw, or return a "missing" placeholder.
- Factories don't solve ownership — decide whether the factory or the caller owns the returned object.

**Game applications**: Enemy/item/projectile spawning from data files, UI widget construction, level object instantiation, save/load (reconstruct objects from serialized type names), modding systems.

**Engine note**: Godot's `load()` + `instantiate()` is a factory. Unity's `Instantiate(prefab)` is a factory. Unreal's `SpawnActor<T>`. In scripting, factories are often just functions that return configured scene instances.

---

## Strategy

**Intent**: Define a family of algorithms, encapsulate each one, and make them interchangeable — letting the algorithm vary independently from the clients that use it.

**Problem**: An enemy needs different pathfinding algorithms depending on context (A* for open areas, flow fields for crowds, simple chase for short distances). Hardcoding the algorithm in the enemy class makes it impossible to swap without modifying the class.

**Solution**: Define a strategy interface. Each algorithm is a concrete strategy. The context holds a reference to the current strategy and delegates to it.

```cpp
class PathfindingStrategy {
public:
    virtual ~PathfindingStrategy() {}
    virtual Path findPath(Vector3 from, Vector3 to, const World& world) = 0;
};

class AStarPathfinding : public PathfindingStrategy {
public:
    Path findPath(Vector3 from, Vector3 to, const World& world) override {
        // A* implementation
    }
};

class FlowFieldPathfinding : public PathfindingStrategy {
public:
    Path findPath(Vector3 from, Vector3 to, const World& world) override {
        // Flow field implementation
    }
};

class Enemy {
    PathfindingStrategy* pathfinder;
public:
    Enemy(PathfindingStrategy* strategy) : pathfinder(strategy) {}

    void setStrategy(PathfindingStrategy* s) { pathfinder = s; }

    void update(const World& world) {
        Path path = pathfinder->findPath(position, target, world);
        followPath(path);
    }
};

// Swap at runtime based on context:
if (enemyCount > 50)
    enemy->setStrategy(new FlowFieldPathfinding());
else
    enemy->setStrategy(new AStarPathfinding());
```

**Functional variant** (preferred in modern languages):
```cpp
// In C++, use std::function instead of a class hierarchy:
using PathFn = std::function<Path(Vector3, Vector3, const World&)>;

class Enemy {
    PathFn pathfinder;
public:
    Enemy(PathFn fn) : pathfinder(fn) {}
    void setStrategy(PathFn fn) { pathfinder = fn; }
};

// Usage:
Enemy e([](auto from, auto to, auto& w) { return astar(from, to, w); });
```

**Relationship to Component**: Strategy is stateless (encapsulates an algorithm); Component is stateful (encapsulates a domain with data). A physics component is a Component; a sorting algorithm is a Strategy.

**Trade-offs**:
- Overkill for algorithms that never change — just call the function directly.
- Strategy objects are often stateless; consider using function pointers or lambdas instead of classes.
- If strategies need to communicate with each other or share state, consider a different pattern.

**Game applications**: Pathfinding algorithms, AI decision-making (aggressive vs. defensive), sorting/rendering strategies, input handling (keyboard vs. gamepad vs. AI), serialization formats.

**Engine note**: In Godot, passing a `Callable` achieves the same result. In Unity, delegates and `Action<T>` serve as lightweight strategies. GDScript's first-class functions make the functional variant natural.

---

## Decorator

**Intent**: Attach additional behavior to an object dynamically by wrapping it in a decorator object that implements the same interface.

**Problem**: A sword can be enchanted with fire damage, then with poison, then with a speed bonus. Modeling every combination as a subclass (`FirePoisonSpeedSword`) is combinatorially explosive. You want to compose effects at runtime.

**Solution**: Define a component interface. The base object implements it. Each decorator wraps another object implementing the same interface, adding behavior before or after delegating.

```cpp
class Weapon {
public:
    virtual ~Weapon() {}
    virtual int  getDamage() const = 0;
    virtual void onHit(Entity& target) = 0;
};

class Sword : public Weapon {
public:
    int  getDamage() const override { return 10; }
    void onHit(Entity& target) override { /* basic hit */ }
};

// Decorator base — wraps another Weapon
class WeaponDecorator : public Weapon {
protected:
    Weapon* wrapped;
public:
    WeaponDecorator(Weapon* w) : wrapped(w) {}
};

class FireEnchantment : public WeaponDecorator {
public:
    FireEnchantment(Weapon* w) : WeaponDecorator(w) {}
    int getDamage() const override { return wrapped->getDamage() + 5; }
    void onHit(Entity& target) override {
        wrapped->onHit(target);
        target.applyBurning(3.0f);  // add fire effect
    }
};

class PoisonEnchantment : public WeaponDecorator {
public:
    PoisonEnchantment(Weapon* w) : WeaponDecorator(w) {}
    int getDamage() const override { return wrapped->getDamage(); }
    void onHit(Entity& target) override {
        wrapped->onHit(target);
        target.applyPoison(10.0f);
    }
};

// Compose at runtime:
Weapon* mySword = new PoisonEnchantment(
                      new FireEnchantment(
                          new Sword()));
// getDamage() = 15, onHit() applies fire + poison
```

**Trade-offs**:
- Deep decorator chains are hard to debug — you can't easily inspect what's wrapped inside.
- Each decorator adds an indirection (virtual call). For performance-critical paths, consider a flat list of effects instead.
- Identity: `mySword` is a `PoisonEnchantment`, not a `Sword`. Type checks (`dynamic_cast`) break down.
- **Alternative for status effects**: a flat list of effect objects on the entity, each with an `apply(entity, dt)` method. Simpler, more inspectable, easier to serialize.

**Game applications**: Item enchantments, status effects (burning, poisoned, slowed), UI component composition (scrollable + bordered + shadowed panel), logging/profiling wrappers, network message transformations.

**Engine note**: In Godot, composing nodes achieves similar results without the wrapper pattern. In Unity, multiple `MonoBehaviour` components on a `GameObject` compose behavior. The flat-list-of-effects approach is often more practical than classical Decorator in game engines.
