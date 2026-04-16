---
name: godot
description: Use when working on any Godot 4.x development — writing or reviewing .gd files, designing scene trees, implementing game systems in GDScript, structuring Godot projects, or asking about nodes, signals, AutoLoads, Resources, or the Godot editor. Also trigger when implementing game patterns (Observer, State, Command, etc.) in a Godot project — this skill takes precedence over game-patterns for Godot-specific implementation. NOT for engine-agnostic pattern theory (see game-patterns). NOT for Love2D (see love2d). NOT for shaders or visual effects (see godot-shader).
---

# Godot 4.x Development

Godot 4.x (baseline: 4.6) with GDScript. All code examples target GDScript — not C#. This skill is for a hobbyist developer; prefer engine-native features over custom implementations.

## References

| Reference | When to read it |
|---|---|
| [`references/scene-architecture.md`](references/scene-architecture.md) | Node selection, scene splitting decisions, large project layout, composition patterns |
| [`references/gdscript-patterns.md`](references/gdscript-patterns.md) | Signal bus, state machine, resource config, coroutines, typed arrays, advanced GDScript |
| [`references/godot-pattern-mappings.md`](references/godot-pattern-mappings.md) | Full GDScript implementations of all 23 game patterns with Godot-idiomatic code |

---

## Scene Architecture

**The scene tree is a composition hierarchy, not an inheritance hierarchy.** Each scene is a reusable unit. Prefer many small, focused scenes over one large scene.

**Scene vs Node vs Resource — pick one:**
- **Scene** (`.tscn`): reusable entity with its own lifecycle — enemies, UI panels, projectiles, pickups. Instantiate with `preload().instantiate()`.
- **Node** (inline in parent scene): structural grouping with no independent reuse — a `HBoxContainer` holding buttons, a `Marker2D` for spawn points.
- **Resource** (`.tres` / `.res`): pure data with no scene presence — item stats, weapon configs, level data. Extend `Resource` and use `@export`.

**Flat over deep.** A node tree 4+ levels deep is a design smell. If you're writing `get_node("../../Player/Stats")`, the scene needs restructuring. Pass references via `@export` or signals instead.

**File naming:** `snake_case` for all directories, scenes, and scripts in Godot 4. Name scripts and scenes after the scene's root node (`player.tscn` + `player.gd`).

**Split a scene when:**
- It's reused in multiple parent scenes
- It has its own independent state and lifecycle
- It exceeds ~20 nodes
- Different team members (or future you) need to edit it independently

**Composition pattern:** Give complex entities capabilities via child nodes with scripts, not inheritance chains.

```gdscript
# Player scene tree — each child is a focused capability node
Player (CharacterBody2D)
├── HealthComponent (Node)       # handles HP, death signal
├── HurtboxComponent (Area2D)    # detects incoming damage
├── StateMachine (Node)          # drives behavior states
├── AnimationPlayer
└── Sprite2D
```

Each component script is self-contained. `HealthComponent` emits `died` — the parent doesn't need to know who's listening.

**Scene instancing:**

```gdscript
const BulletScene: PackedScene = preload("res://scenes/bullet.tscn")

func _shoot() -> void:
    var bullet: Bullet = BulletScene.instantiate()
    bullet.direction = aim_direction
    get_tree().current_scene.add_child(bullet)  # add to scene root, not self
```

Use `preload` for scenes known at compile time. Use `load` only for paths determined at runtime from a fixed, trusted list — never pass user-provided strings directly to `load()`.

---

## GDScript Idioms

### Script File Ordering

Follow this order in every `.gd` file:

```gdscript
# 1. class_name / extends
# 2. ## docstring
# 3. signals
# 4. enums
# 5. constants
# 6. @export vars
# 7. public vars
# 8. private vars (_prefix)
# 9. @onready vars
# 10. _init / _ready / _enter_tree
# 11. _process / _physics_process / _unhandled_input
# 12. signal callbacks (_on_*)
# 13. public methods
# 14. private methods (_prefix)
```

### Signals

Signals decouple emitters from listeners. The emitter knows nothing about who's listening.

```gdscript
# Declaration — always type parameters
signal health_changed(new_health: int, max_health: int)
signal died

# Emit
health_changed.emit(current_health, max_health)

# Connect in _ready — prefer Callable syntax
func _ready() -> void:
    $HealthComponent.health_changed.connect(_on_health_changed)
    $HealthComponent.died.connect(_on_player_died)

func _on_health_changed(new_health: int, max_health: int) -> void:
    $HUD.update_health_bar(new_health, max_health)
```

**Use signals when:** a child needs to notify its parent, or two siblings need to communicate without direct references. **Use direct calls when:** a parent calls a method on a child it owns — that's normal control flow, not coupling.

**Signal bus (EventBus AutoLoad):** For truly global events (game over, scene transition, achievement unlocked), a signal bus AutoLoad is appropriate. See `references/gdscript-patterns.md`.

**Naming conventions:**
- **Signals:** past tense (`moved`, `died`). Append `_started`/`_finished` for process signals (`talk_started`, `talk_finished`).
- **Booleans:** prefix with `is_`, `can_`, or `has_` (`is_active`, `can_jump`, `has_key`).
- **Methods:** don't repeat the class name in arguments — `Inventory.add(item)` not `Inventory.add_item(item)`.

### Exports and Resources

```gdscript
# Basic exports
@export var speed: float = 200.0
@export var max_health: int = 100
@export var projectile_scene: PackedScene

# Custom Resource for data — define once, reuse everywhere
class_name WeaponData extends Resource
@export var damage: int = 10
@export var fire_rate: float = 0.5
@export var projectile_scene: PackedScene

# Use it
@export var weapon: WeaponData  # assign .tres in editor
```

Custom Resources are the right tool for item databases, enemy stats, level configs — anything that's data, not behavior.

### Static Typing

Always use type hints. Prefer `:=` (type inference) when the right-hand side makes the type obvious. Use explicit annotation when the compiler can't infer.

```gdscript
# Inference — type is obvious from the right-hand side
var speed := 200.0
var direction := Vector2.ZERO
var timer := Timer.new()
```

```gdscript
# Explicit — compiler can't infer (Variant returns, typed arrays, PackedScene.instantiate())
var text: String = array.pop_back()
var enemy: Enemy = EnemyScene.instantiate()
var enemies: Array[Enemy] = []
var damage_values: Array[int] = [10, 20, 30]
```

```gdscript
# Bad — no types at all
var speed = 200
func take_damage(amount):
    health -= amount

# Good — typed variable and typed parameters/return
var speed: float = 200.0
func take_damage(amount: int) -> void:
    health -= amount
    health_changed.emit(health, max_health)
```

Use `class_name` to make custom types available project-wide without `preload`.

### AutoLoads

AutoLoads are project-wide singletons. Use them sparingly.

**Appropriate AutoLoad uses:**
- Signal bus / EventBus (global events)
- SceneManager (scene transitions)
- AudioManager (global audio)
- SaveManager (save/load)

**Avoid AutoLoad for:** anything a scene can own and pass down. If only two scenes need to share data, pass it via `@export` or a signal — not a global.

```gdscript
# EventBus.gd — AutoLoad
signal game_over(winner: String)
signal score_changed(new_score: int)
```

### Groups

Groups are lightweight tags for cross-cutting concerns. Avoid `get_node` path gymnastics.

```gdscript
# Tag nodes in editor or via code
add_to_group("enemies")

# Query from anywhere
func _on_explosion() -> void:
    for enemy in get_tree().get_nodes_in_group("enemies"):
        (enemy as Enemy).stun()
```

### Coroutines and `await`

```gdscript
# Wait for signal
await get_tree().create_timer(2.0).timeout

# Wait for animation
$AnimationPlayer.play("death")
await $AnimationPlayer.animation_finished

# Sequence with await
func _die() -> void:
    died.emit()
    $AnimationPlayer.play("death")
    await $AnimationPlayer.animation_finished
    queue_free()
```

---

## Pattern Mapping (Quick Reference)

**This skill takes precedence over game-patterns for Godot implementation.** When both fire, use the Godot-native approach below. For full GDScript implementations, see `references/godot-pattern-mappings.md`.

| Pattern | Godot Approach | Note |
|---|---|---|
| **Observer** | Signals | Built-in; always prefer over manual observer lists |
| **Singleton** | AutoLoad | Register in Project Settings → AutoLoad |
| **State** | Custom state nodes + StateMachine node | Child nodes per state; `AnimationTree` for animation states |
| **Command** | `Callable` + Array buffer | Store `Callable` objects; call `.call()` to execute |
| **Factory** | `PackedScene.instantiate()` | `preload` the scene; factory node manages spawning |
| **Strategy** | Swappable Resource or script | `@export var strategy: Resource`; duck-typed or typed |
| **Decorator** | Child node wrapping behavior | Add/remove child nodes at runtime |
| **Service Locator** | AutoLoad with fallback | AutoLoad provides service; swap implementation at runtime |
| **Event Queue** | Array + `_process` drain | Buffer events in Array; drain one per frame or in batch |
| **Component** | Child nodes with scripts | Each child = one capability; communicate via signals |
| **Prototype** | `resource.duplicate()` | `Resource.duplicate(true)` for deep copy |
| **Flyweight** | Shared `Resource` | Multiple nodes share one `Resource` instance |
| **Object Pool** | Node pool with `visible = false` | Disable/re-enable nodes instead of `queue_free`/`instantiate` |
| **Double Buffer** | Two arrays, swap each frame | Manual; rarely needed — Godot's rendering handles most cases |
| **Game Loop** | Built-in (`_process`, `_physics_process`) | Override `_process(delta)` — engine owns the loop |
| **Update Method** | `_process(delta)` / `_physics_process(delta)` | Use `_physics_process` for physics; `_process` for visuals |
| **Spatial Partition** | `Area2D`/`Area3D` + physics layers | Use collision layers/masks before writing custom grids |
| **Dirty Flag** | `@export` setter with dirty bool | `set(value): _dirty = true; _data = value` |
| **Data Locality** | `TileMapLayer`, `MultiMeshInstance3D` | Engine handles; use these nodes for large uniform sets |
| **Bytecode** | GDScript itself / `Expression` class | `Expression.parse()` for runtime-evaluated expressions |
| **Subclass Sandbox** | Base script + `class_name` | Extend base class; override `_execute()` hook |
| **Type Object** | Custom `Resource` subclass | Each "type" is a `.tres` file; behavior via exported data |

---

## Common Pitfalls

**Signal spaghetti:** When every node connects to every other node, tracing behavior becomes impossible. Keep signal connections local — a node connects to its own children's signals in `_ready`. For cross-scene events, route through an EventBus AutoLoad, not direct cross-scene connections.

**AutoLoad abuse:** AutoLoads are globals. Globals make code hard to test and reason about. Before adding an AutoLoad, ask: can this data live in a scene and be passed down? If yes, do that.

**Deep node path coupling:** `get_node("../../HUD/HealthBar")` breaks whenever the tree changes. Instead: pass references via `@export`, use signals to communicate upward, or use groups for cross-cutting queries.

**Skipping static types:** Untyped GDScript loses editor autocompletion, misses type errors until runtime, and makes refactoring painful. Type everything — variables, parameters, return types.

**Overusing `_process`:** `_process` runs every frame. For things that only change on events (health bar, score display), connect to a signal instead. For timers, use `Timer` nodes or `get_tree().create_timer()`. Reserve `_process` for things that genuinely need per-frame updates (movement, continuous animation).

**Returning mid-function:** Use `return` only at the start (guard clause) or end of a function. Mid-function returns hide control flow and make methods harder to trace.

**Using `null` when a typed default exists:** Prefer `Vector2.ZERO`, `""`, `[]`, or `.new()` over `null`. Null checks proliferate and mask missing initialization. Use `null` only when the engine API forces it.
