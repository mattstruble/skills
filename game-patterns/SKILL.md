---
name: game-patterns
description: Consult this skill when making game architecture decisions, choosing how to structure game systems, or asking which pattern fits a problem. Also trigger when designing entity/component systems, input handling, game state machines, event/messaging systems, object pooling, spatial queries, or scripting/modding support. NOT for engine-specific implementation (see godot, love2d, unity). NOT for general software design outside game development (see software-design).
---

# Game Programming Patterns

Engine-agnostic pattern reference for game systems. Synthesized from Nystrom's *Game Programming Patterns* (gameprogrammingpatterns.com).

**Relationship to engine skills**: This skill provides the *why* and *when*. Your engine skill (e.g., godot, love2d) provides the idiomatic *how*. When both fire, the engine skill takes precedence on implementation details — use this skill to understand which pattern to reach for, then let the engine skill guide the concrete code.

---

## Pattern Selection by Problem

### "I need to decouple things"

| Problem | Pattern |
|---|---|
| Game systems (physics, audio, AI) shouldn't know about each other | **Component** — split entity behavior into isolated domain objects |
| One system needs to react to events in another without coupling | **Observer** — subject notifies listeners without knowing who they are |
| Systems need to communicate but shouldn't be directly wired | **Event Queue** — buffer events; consumers pull when ready |
| A subsystem needs a global access point but Singleton is too rigid | **Service Locator** — register/retrieve services through a central registry |

### "I need to structure entity behavior"

| Problem | Pattern |
|---|---|
| Entity has distinct modes (idle, attacking, dead) with different behavior | **State** — FSM where each state owns its transitions and behavior |
| Many entity types share behavior but differ in data (e.g., enemy stats) | **Type Object** — define a "type" object that instances share |
| Entities need per-frame update logic without a massive switch | **Update Method** — each entity owns an `update()` called by the game loop |
| Subclasses need safe access to a large set of engine operations | **Subclass Sandbox** — base class exposes protected primitives; subclasses compose them |

### "I need to handle input or actions"

| Problem | Pattern |
|---|---|
| Input needs to be rebindable, undoable, or replayable | **Command** — encapsulate each action as an object with `execute()`/`undo()` |
| Need to drive AI and player with the same action interface | **Command** — AI emits Command objects; same executor handles both |

### "I need performance"

| Problem | Pattern |
|---|---|
| Frequent allocation/deallocation of short-lived objects (bullets, particles) | **Object Pool** — pre-allocate a fixed pool; recycle instead of free |
| Spatial queries (collision, visibility, range checks) are too slow | **Spatial Partition** — grid, quadtree, or BSP to limit candidates |
| Derived data is expensive to recompute every frame | **Dirty Flag** — mark stale, recompute lazily only when needed |
| Many objects share identical data (same sprite, same mesh) | **Flyweight** — share the immutable data; store only per-instance delta |
| Cache misses are killing performance in hot loops | **Data Locality** — restructure data for sequential memory access (SoA) |

### "I need scripting or data-driven behavior"

| Problem | Pattern |
|---|---|
| Designers need to define behavior without recompiling | **Bytecode** — compile behavior to a simple VM; interpret at runtime |
| Need to spawn entities from data (JSON, prefabs) | **Prototype** — clone a template object; or use it as a data-driven archetype |
| Need pluggable algorithms (pathfinding strategies, AI behaviors) | **Strategy** — swap algorithm implementations behind a common interface |
| Need to add behavior to objects at runtime without subclassing | **Decorator** — wrap objects to layer on additional behavior |
| Need a consistent way to create families of objects | **Factory** — centralize construction logic; decouple callers from concrete types |

### "I need to manage time and sequencing"

| Problem | Pattern |
|---|---|
| Game must run at consistent speed across hardware | **Game Loop** — fixed-update with variable render; decouple sim from display |
| Two buffers must swap atomically (graphics, physics state) | **Double Buffer** — write to back buffer; swap at frame boundary |

---

## All 23 Patterns — Quick Reference

### Design Patterns Revisited

**Command** — Encapsulates a request as an object. Enables rebindable input, undo/redo stacks, replay systems, and AI-driven actors. Reach for it whenever you need to parameterize, queue, or reverse actions. See `references/design-patterns-revisited.md`.

**Flyweight** — Shares a single copy of immutable data across many instances. Use when thousands of objects (trees, tiles, bullets) share identical intrinsic state. The shared object is stateless; per-instance data stays separate. See `references/design-patterns-revisited.md`.

**Observer** — Subject maintains a list of listeners and notifies them on events. Decouples producers (physics, gameplay) from consumers (UI, achievements, audio). Watch for the lapsed-listener problem in GC languages. See `references/design-patterns-revisited.md`.

**Prototype** — Clone an existing object to create new ones. In games, most useful as a data-driven archetype pattern: a JSON "template" object that instances copy from. Less useful as a pure OOP pattern. See `references/design-patterns-revisited.md`.

**Singleton** — Ensures one instance with global access. Widely overused in games. Prefer Service Locator or dependency injection. Use Singleton only when the single-instance constraint is a genuine invariant, not just convenience. See `references/design-patterns-revisited.md`.

**State** — Finite state machine where each state is an object that owns its behavior and transitions. Eliminates sprawling `if/switch` chains in entity update logic. Hierarchical and pushdown variants handle nested states and modal UIs. See `references/design-patterns-revisited.md`.

### Sequencing Patterns

**Double Buffer** — Maintains two buffers; one is written while the other is read. Prevents tearing in rendering and physics. **Engine note**: your engine almost certainly implements this — understand it for debugging, don't implement it from scratch. See `references/sequencing.md`.

**Game Loop** — The heartbeat of every game: process input → update → render, decoupled from hardware speed. Fixed-update with variable render is the gold standard. **Engine note**: your engine owns this loop — understand it to use `_process` vs `_physics_process` correctly. See `references/sequencing.md`.

**Update Method** — Each entity owns an `update(dt)` method called once per frame. Simple, universal, but watch for order-of-update dependencies and the cost of virtual dispatch on thousands of objects. See `references/sequencing.md`.

### Behavioral Patterns

**Bytecode** — Compiles behavior into instructions for a simple virtual machine. Use when designers need to author behavior without recompiling, or when sandboxing untrusted scripts. High implementation cost — only justified for moddable games or complex scripting needs. See `references/behavioral.md`.

**Subclass Sandbox** — Base class exposes a rich set of protected operations; subclasses implement behavior by composing them. Keeps subclasses from reaching into engine internals directly. Good for spell/ability systems with many variants. See `references/behavioral.md`.

**Type Object** — Separates "what kind of thing" from "this specific thing." A `Monster` instance holds a pointer to a `MonsterType` that defines stats, AI, and sprites. Enables data-driven entity definitions without a class per type. See `references/behavioral.md`.

### Decoupling Patterns

**Component** — Splits a monolithic entity class into isolated domain components (physics, rendering, AI, input). Each component knows its domain; the entity is a thin container. Foundation of ECS architectures. **Engine note**: Unity's `GetComponent`, Godot's node tree, and Bevy's ECS all implement this. See `references/decoupling.md`.

**Event Queue** — Decouples event producers from consumers in time, not just structure. Events are buffered; consumers process them at their own pace. Solves the "slow observer" problem and enables cross-thread communication. See `references/decoupling.md`.

**Service Locator** — A registry that maps service interfaces to concrete implementations. Provides global access without hard-coding dependencies. Better than Singleton because the implementation is swappable (useful for null/test services). See `references/decoupling.md`.

### Optimization Patterns

**Data Locality** — Restructures data for cache-friendly sequential access. Array-of-Structs → Struct-of-Arrays. Critical in hot loops (particle updates, physics ticks). **Engine note**: ECS engines (Bevy, Unity DOTS) enforce this automatically. See `references/optimization.md`.

**Dirty Flag** — Tracks whether derived data is stale. Recomputes only when the source data has changed and the derived value is actually needed. Use for world transforms, pathfinding caches, UI layout. See `references/optimization.md`.

**Object Pool** — Pre-allocates a fixed array of objects; "allocates" by marking one active, "frees" by marking it inactive. Eliminates heap churn for short-lived objects. Essential for bullets, particles, audio sources. See `references/optimization.md`.

**Spatial Partition** — Divides space into a structure (grid, quadtree, BSP, k-d tree) to reduce collision/query candidates from O(n²) to O(n log n) or better. Choose based on object density and movement frequency. See `references/optimization.md`.

### Additional Patterns

**Factory** — Centralizes object construction. Decouples callers from concrete types; enables construction from data (string → class). Use when construction logic is complex or needs to vary. See `references/additional-patterns.md`.

**Strategy** — Swaps algorithm implementations behind a common interface. Use for pluggable AI behaviors, pathfinding algorithms, or serialization formats. Lighter than full inheritance hierarchies. See `references/additional-patterns.md`.

**Decorator** — Wraps an object to add behavior without subclassing. Use for composable item enchantments, status effects, or logging wrappers. Watch for deep wrapper chains becoming hard to debug. See `references/additional-patterns.md`.

---

## Engine-Handles-This Flags

These patterns are worth understanding conceptually, but you should not implement them from scratch when using a game engine:

- **Game Loop** — Godot: `_process`/`_physics_process`. Unity: `Update`/`FixedUpdate`. Love2d: `love.update`.
- **Double Buffer** — Handled by the renderer. Understand it to debug vsync/tearing issues.
- **Component** — Godot nodes, Unity components, Bevy ECS. Use the engine's system; don't roll your own.
- **Data Locality** — Unity DOTS/ECS, Bevy ECS enforce this. In other engines, be aware of cache effects in hot loops.

---

## References

| File | Contents |
|---|---|
| `references/design-patterns-revisited.md` | Command, Flyweight, Observer, Prototype, Singleton, State |
| `references/sequencing.md` | Double Buffer, Game Loop, Update Method |
| `references/behavioral.md` | Bytecode, Subclass Sandbox, Type Object |
| `references/decoupling.md` | Component, Event Queue, Service Locator |
| `references/optimization.md` | Data Locality, Dirty Flag, Object Pool, Spatial Partition |
| `references/additional-patterns.md` | Factory, Strategy, Decorator |
