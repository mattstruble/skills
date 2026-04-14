# Godot Pattern Mappings

Full GDScript implementations of all 23 game patterns. This skill takes precedence over game-patterns for Godot-specific implementation.

## Table of Contents

- [Patterns with Packt GDScript examples](#patterns-with-packt-gdscript-examples): Singleton, Observer, Factory, State, Command, Strategy, Decorator, Service Locator, Event Queue
- [Remaining patterns](#remaining-patterns): Component, Prototype, Flyweight, Object Pool, Double Buffer, Game Loop, Update Method, Spatial Partition, Dirty Flag, Data Locality, Bytecode, Subclass Sandbox, Type Object

---

## Patterns with Packt GDScript Examples

### Singleton → AutoLoad

**Godot approach:** Register a script in Project Settings → AutoLoad. Godot instantiates it at startup and makes it globally accessible by name.

```gdscript
# autoloads/game_manager.gd
extends Node

var score: int = 0
var lives: int = 3
var current_level: int = 1

signal score_changed(new_score: int)

func add_score(points: int) -> void:
    score += points
    score_changed.emit(score)

func reset() -> void:
    score = 0
    lives = 3
    current_level = 1
```

Access anywhere: `GameManager.add_score(100)`

**When to use built-in:** Always — AutoLoad is the canonical Godot singleton.
**Common mistake:** Using AutoLoad for data that only 2-3 scenes need. Pass it via `@export` instead.

---

### Observer → Signals

**Godot approach:** Signals are first-class. No manual observer list needed.

```gdscript
# health_component.gd — the subject
class_name HealthComponent extends Node

signal health_changed(new_health: int, max_health: int)
signal died

@export var max_health: int = 100
var current_health: int

func _ready() -> void:
    current_health = max_health

func take_damage(amount: int) -> void:
    current_health = max(0, current_health - amount)
    health_changed.emit(current_health, max_health)
    if current_health <= 0:
        died.emit()
```

```gdscript
# player.gd — the observer
func _ready() -> void:
    $HealthComponent.health_changed.connect(_on_health_changed)
    $HealthComponent.died.connect(_on_died)

func _on_health_changed(new_health: int, max_health: int) -> void:
    $HUD/HealthBar.value = float(new_health) / float(max_health)

func _on_died() -> void:
    EventBus.player_died.emit()
    _play_death_animation()
```

**When to use built-in:** Always — signals are Godot's observer pattern.
**Common mistake:** Connecting signals in `_process` (creates duplicate connections). Connect once in `_ready`.

---

### Factory → PackedScene.instantiate()

**Godot approach:** A spawner node holds a `PackedScene` reference and instantiates on demand.

```gdscript
# enemy_spawner.gd
class_name EnemySpawner extends Node2D

@export var enemy_scenes: Array[PackedScene] = []
@export var spawn_interval: float = 2.0

var _timer: float = 0.0

func _process(delta: float) -> void:
    _timer += delta
    if _timer >= spawn_interval:
        _timer = 0.0
        spawn_random_enemy()

func spawn_random_enemy() -> Node:
    if enemy_scenes.is_empty():
        return null
    var scene: PackedScene = enemy_scenes.pick_random()
    var enemy: Node = scene.instantiate()
    enemy.global_position = global_position
    get_parent().add_child(enemy)
    return enemy

func spawn_enemy_at(scene: PackedScene, position: Vector2) -> Node:
    var enemy: Node = scene.instantiate()
    enemy.global_position = position
    get_parent().add_child(enemy)
    return enemy
```

**When to use built-in:** `PackedScene.instantiate()` is always the right tool. For pooling, see Object Pool below.
**Common mistake:** Adding instantiated nodes as children of the spawner. Add them to the level/scene root so they aren't freed when the spawner is freed.

---

### State → State Node Pattern

**Godot approach:** Each state is a `Node` with a script. A `StateMachine` node manages transitions. See `gdscript-patterns.md` for the full implementation.

```gdscript
# player_run_state.gd
class_name PlayerRunState extends State

@export var player: CharacterBody2D
@export var animated_sprite: AnimatedSprite2D  # wire in editor, not get_node path
@export var idle_state: State
@export var jump_state: State

const SPEED: float = 200.0

func enter() -> void:
    if animated_sprite:
        animated_sprite.play("run")

func physics_update(delta: float) -> void:
    var direction: float = Input.get_axis("move_left", "move_right")
    player.velocity.x = direction * SPEED
    player.move_and_slide()

func get_transition() -> State:
    if Input.get_axis("move_left", "move_right") == 0.0:
        return idle_state
    if Input.is_action_just_pressed("jump"):
        return jump_state
    return null
```

**When to use built-in:** `AnimationTree` with `AnimationStateMachine` for animation-only state. Custom state nodes for behavior state. Use both together — AnimationTree drives visuals, custom StateMachine drives logic.
**Common mistake:** Putting all state logic in one giant `match` block in `_process`. This doesn't scale past 3-4 states.

---

### Command → Callable Buffer

**Godot approach:** Store `Callable` objects in an array. Execute them by calling `.call()`. For undo/redo, store pairs.

```gdscript
# command_processor.gd
class_name CommandProcessor extends Node

# Store do/undo pairs together to prevent history desync
class CommandEntry:
    var do_cmd: Callable
    var undo_cmd: Callable
    func _init(d: Callable, u: Callable) -> void:
        do_cmd = d
        undo_cmd = u

var _history: Array[CommandEntry] = []

func execute(command: Callable, undo_command: Callable = Callable()) -> void:
    command.call()
    _history.append(CommandEntry.new(command, undo_command))

func undo() -> void:
    if _history.is_empty():
        return
    var entry: CommandEntry = _history.pop_back()
    if entry.undo_cmd.is_valid():
        entry.undo_cmd.call()
```

```gdscript
# Usage — player input mapped to commands
func _unhandled_input(event: InputEvent) -> void:
    if event.is_action_pressed("move_right"):
        var old_pos := global_position
        command_processor.execute(
            func(): global_position.x += 32,
            func(): global_position = old_pos
        )
```

**When to use built-in:** `Callable` is the native command object. For simple cases (no undo), just call the function directly. Use this pattern when you need undo/redo, replay, or deferred execution.
**Common mistake:** Capturing mutable state in closures. Capture values, not references, for undo to work correctly.

---

### Strategy → Swappable Resource or Script

**Godot approach:** Define behavior as a `Resource` subclass with a method. Swap the resource to change behavior.

```gdscript
# ai_strategy.gd — base strategy
class_name AIStrategy extends Resource

func get_move_direction(enemy: CharacterBody2D, player: CharacterBody2D) -> Vector2:
    return Vector2.ZERO  # override in subclasses
```

```gdscript
# chase_strategy.gd
class_name ChaseStrategy extends AIStrategy

func get_move_direction(enemy: CharacterBody2D, player: CharacterBody2D) -> Vector2:
    return (player.global_position - enemy.global_position).normalized()
```

```gdscript
# patrol_strategy.gd
class_name PatrolStrategy extends AIStrategy

@export var patrol_points: Array[Vector2] = []
var _current_point: int = 0

func get_move_direction(enemy: CharacterBody2D, player: CharacterBody2D) -> Vector2:
    if patrol_points.is_empty():
        return Vector2.ZERO
    var target := patrol_points[_current_point]
    if enemy.global_position.distance_to(target) < 5.0:
        _current_point = (_current_point + 1) % patrol_points.size()
    return (target - enemy.global_position).normalized()
```

```gdscript
# enemy.gd
@export var ai_strategy: AIStrategy

func _physics_process(delta: float) -> void:
    if ai_strategy:
        velocity = ai_strategy.get_move_direction(self, player) * speed
        move_and_slide()
```

**When to use built-in:** This Resource-based approach is idiomatic Godot. For simple cases, a plain `Callable` works too.
**Common mistake:** Using inheritance instead of composition. An enemy shouldn't be `ChaseEnemy extends Enemy` — it should be `Enemy` with a `ChaseStrategy` resource.

---

### Decorator → Child Node Wrapping

**Godot approach:** Add child nodes at runtime to augment behavior. Remove them to strip the augmentation.

```gdscript
# power_up_component.gd — base class for power-up decorators
class_name PowerUpComponent extends Node

func apply(player: CharacterBody2D) -> void:
    pass  # override

func remove(player: CharacterBody2D) -> void:
    queue_free()
```

```gdscript
# speed_boost_component.gd
class_name SpeedBoostComponent extends PowerUpComponent

@export var speed_multiplier: float = 1.5
@export var duration: float = 5.0

func apply(player: CharacterBody2D) -> void:
    player.speed *= speed_multiplier
    await get_tree().create_timer(duration).timeout
    if is_instance_valid(player):
        remove(player)
    else:
        queue_free()  # player gone, just clean up the component

func remove(player: CharacterBody2D) -> void:
    player.speed /= speed_multiplier
    super.remove(player)
```

```gdscript
# pickup.gd — applies decorator on collection
func _on_body_entered(body: CharacterBody2D) -> void:
    if body.is_in_group("player"):
        var boost := SpeedBoostComponent.new()
        body.add_child(boost)
        boost.apply(body)
        queue_free()
```

**When to use built-in:** This pattern. Godot's node system makes add/remove child the natural decorator mechanism.
**Common mistake:** Modifying the player's base stats permanently. Always track the original value and restore it on removal.

---

### Service Locator → AutoLoad with Interface

**Godot approach:** An AutoLoad provides a service. Swap the implementation by reassigning the AutoLoad's internal reference.

```gdscript
# audio_service.gd (AutoLoad: AudioService)
extends Node

var _provider: AudioProvider = NullAudioProvider.new()

func set_provider(provider: AudioProvider) -> void:
    _provider = provider

func play_sfx(sound_name: String) -> void:
    _provider.play_sfx(sound_name)

func play_music(track_name: String) -> void:
    _provider.play_music(track_name)
```

```gdscript
# audio_provider.gd — interface (duck-typed in GDScript)
class_name AudioProvider extends Resource

func play_sfx(sound_name: String) -> void:
    pass

func play_music(track_name: String) -> void:
    pass
```

```gdscript
# null_audio_provider.gd — silent fallback
class_name NullAudioProvider extends AudioProvider
# inherits no-op implementations — safe to use before real audio loads
```

```gdscript
# real_audio_provider.gd
class_name RealAudioProvider extends AudioProvider

func play_sfx(sound_name: String) -> void:
    # actual AudioStreamPlayer logic
    pass
```

**When to use built-in:** AutoLoad is the service locator. The Null Object pattern (silent fallback) prevents crashes during initialization.
**Common mistake:** Skipping the null provider. Without it, code that calls `AudioService.play_sfx()` before the real provider is set will error.

---

### Event Queue → Array + _process Drain

**Godot approach:** Buffer events in an `Array`. Drain them in `_process` — either one per frame or all at once.

```gdscript
# game_event.gd — top-level class so it's accessible from any script
class_name GameEvent extends RefCounted

var type: String
var data: Dictionary

func _init(event_type: String, event_data: Dictionary = {}) -> void:
    type = event_type
    data = event_data
```

```gdscript
# event_queue.gd (AutoLoad: EventQueue)
extends Node

var _queue: Array[GameEvent] = []
var _max_per_frame: int = 10  # prevent frame spikes

signal event_processed(event: GameEvent)

func enqueue(type: String, data: Dictionary = {}) -> void:
    _queue.append(GameEvent.new(type, data))

func _process(_delta: float) -> void:
    var processed: int = 0
    while not _queue.is_empty() and processed < _max_per_frame:
        var event: GameEvent = _queue.pop_front()
        event_processed.emit(event)
        processed += 1
```

```gdscript
# Usage
EventQueue.enqueue("enemy_killed", {"type": "goblin", "position": global_position})

# Listener
func _ready() -> void:
    EventQueue.event_processed.connect(_on_event)

func _on_event(event: GameEvent) -> void:
    if event.type == "enemy_killed":
        _update_kill_counter()
```

**When to use built-in:** Godot's signal system handles most event needs. Use an event queue when you need: deferred processing, rate limiting, replay, or ordered event handling across frames.
**Common mistake:** Processing the entire queue in one frame. Cap with `_max_per_frame` to prevent hitches.

---

## Remaining Patterns

### Component → Child Nodes with Scripts

See `scene-architecture.md` for the full component pattern. The short version: each capability is a `Node` child with a focused script. Components communicate via signals, not direct references.

**Common mistake:** Components reaching into siblings via `get_parent().get_node("OtherComponent")`. Use signals or `@export` references instead.

---

### Prototype → resource.duplicate()

```gdscript
# Deep copy a resource to create an independent instance
var base_sword: WeaponData = preload("res://resources/items/sword.tres")

func create_enchanted_sword() -> WeaponData:
    var enchanted: WeaponData = base_sword.duplicate(true)  # true = deep copy
    enchanted.damage = base_sword.damage * 2
    enchanted.item_name = "Enchanted " + base_sword.item_name
    return enchanted
```

`duplicate(true)` deep-copies nested resources. `duplicate(false)` (default) shallow-copies — nested resources are shared.

**Common mistake:** Modifying a resource directly without duplicating. All nodes sharing that resource will see the change.

---

### Flyweight → Shared Resource

Multiple nodes share one `Resource` instance. Godot does this automatically when you assign the same `.tres` file to multiple nodes.

```gdscript
# All goblins share one GoblinStats resource
# goblin.gd
@export var stats: GoblinStats  # assign same .tres in editor to all goblins

func _ready() -> void:
    # stats is shared — don't modify it at runtime
    # if you need per-instance data, duplicate() in _ready
    var my_stats: GoblinStats = stats.duplicate()
```

**When to use built-in:** Godot's resource system is the flyweight. Assign the same `.tres` to multiple nodes — they share the data automatically.
**Common mistake:** Modifying a shared resource at runtime. Always `duplicate()` before modifying per-instance data.

---

### Object Pool → Node Pool

```gdscript
# bullet_pool.gd
class_name BulletPool extends Node

@export var bullet_scene: PackedScene
@export var pool_size: int = 20

var _pool: Array[Node2D] = []

func _ready() -> void:
    for i in pool_size:
        var bullet: Node2D = bullet_scene.instantiate()
        bullet.visible = false
        bullet.process_mode = Node.PROCESS_MODE_DISABLED
        add_child(bullet)
        _pool.append(bullet)

func get_bullet() -> Node2D:
    for bullet in _pool:
        if not bullet.visible:
            bullet.visible = true
            bullet.process_mode = Node.PROCESS_MODE_INHERIT
            return bullet
    # Pool exhausted — optionally grow
    push_warning("BulletPool: pool exhausted, growing")
    var bullet: Node2D = bullet_scene.instantiate()
    add_child(bullet)
    _pool.append(bullet)
    return bullet

func return_bullet(bullet: Node2D) -> void:
    bullet.visible = false
    bullet.process_mode = Node.PROCESS_MODE_DISABLED
```

**When to use:** Bullets, particles, damage numbers — anything spawned and freed at high frequency. For low-frequency spawning (enemies), `instantiate()`/`queue_free()` is fine.
**Common mistake:** Forgetting to reset bullet state (position, velocity, damage) when retrieving from pool.

---

### Double Buffer → Two Arrays, Swap Each Frame

Godot's rendering pipeline handles double-buffering for visuals. For game logic (cellular automata, fluid simulation), implement manually:

```gdscript
# grid_simulation.gd
var _front_buffer: Array[Array] = []
var _back_buffer: Array[Array] = []

func _ready() -> void:
    _front_buffer = _create_grid()
    _back_buffer = _create_grid()

func _physics_process(_delta: float) -> void:
    _simulate(_front_buffer, _back_buffer)
    # Swap buffers
    var temp := _front_buffer
    _front_buffer = _back_buffer
    _back_buffer = temp

func _simulate(read: Array[Array], write: Array[Array]) -> void:
    # Read from `read`, write results to `write`
    pass
```

**When to use:** Grid simulations, cellular automata, fluid dynamics. Rarely needed for typical game logic.

---

### Game Loop → Built-in _process / _physics_process

Godot owns the game loop. Override `_process(delta)` for per-frame logic and `_physics_process(delta)` for physics.

```gdscript
func _process(delta: float) -> void:
    # Runs every rendered frame — use for visuals, input, UI
    _update_animations(delta)

func _physics_process(delta: float) -> void:
    # Runs at fixed rate (default 60Hz) — use for physics, movement
    _move(delta)
    move_and_slide()
```

**Rule:** Movement and collision go in `_physics_process`. Animation, camera, UI go in `_process`. Never put physics in `_process` — it produces frame-rate-dependent behavior.

---

### Update Method → _process(delta) / _physics_process(delta)

Each node has its own update method. Enable/disable processing per-node:

```gdscript
# Disable processing when not needed
func _on_player_died() -> void:
    set_process(false)
    set_physics_process(false)

# Re-enable on respawn
func respawn() -> void:
    set_process(true)
    set_physics_process(true)
```

**Common mistake:** Leaving `_process` running on inactive nodes. Disable it — hundreds of idle `_process` calls add up.

---

### Spatial Partition → Area2D/3D + Physics Layers

Use Godot's built-in physics layers before writing custom spatial partitioning.

```gdscript
# Configure collision layers in Project Settings → Physics → 2D
# Layer 1: Player
# Layer 2: Enemies
# Layer 3: Bullets
# Layer 4: Environment

# Area2D for detection zones
@onready var detection_area: Area2D = $DetectionArea

func _ready() -> void:
    # Only detect player (layer 1)
    detection_area.collision_mask = 1
    detection_area.body_entered.connect(_on_player_detected)
```

For large worlds with thousands of entities, use `Quadtree` or `Octree` (custom implementation) or Godot's `NavigationRegion` for pathfinding partitioning.

---

### Dirty Flag → Setter with Flag

```gdscript
# inventory.gd
var _items: Array[ItemData] = []
var _is_dirty: bool = true  # start dirty so first call computes the cache
var _cached_total_weight: float = 0.0

func _ready() -> void:
    _is_dirty = true  # recompute if items were pre-populated via @export

func add_item(item: ItemData) -> void:
    _items.append(item)
    _is_dirty = true

func remove_item(item: ItemData) -> void:
    _items.erase(item)
    _is_dirty = true

func get_total_weight() -> float:
    if _is_dirty:
        _cached_total_weight = _items.reduce(
            func(acc: float, item: ItemData) -> float: return acc + item.weight,
            0.0
        )
        _is_dirty = false
    return _cached_total_weight
```

**When to use:** Expensive computed properties that depend on frequently-changed data. Inventory weight, pathfinding graphs, UI layout recalculation.

---

### Data Locality → TileMap / MultiMeshInstance3D

For large uniform sets of objects, use engine nodes that store data contiguously:

```gdscript
# TileMapLayer for tile-based levels (Godot 4.3+)
@onready var tile_map: TileMapLayer = $TileMapLayer

func get_tile_at(grid_pos: Vector2i) -> int:
    return tile_map.get_cell_source_id(grid_pos)

# MultiMeshInstance3D for thousands of identical objects (trees, grass)
@onready var multi_mesh: MultiMeshInstance3D = $MultiMeshInstance3D

func _ready() -> void:
    multi_mesh.multimesh.instance_count = 1000
    for i in 1000:
        var transform := Transform3D()
        transform.origin = Vector3(randf() * 100, 0, randf() * 100)
        multi_mesh.multimesh.set_instance_transform(i, transform)
```

**When to use:** Thousands of identical or tile-based objects. Don't use individual nodes for grass blades or tile cells.

---

### Bytecode → GDScript Expression Class

For runtime-evaluated expressions (mod support, scripted events, formula-based stats):

```gdscript
# formula_evaluator.gd
class_name FormulaEvaluator extends Node

func evaluate(formula: String, variables: Dictionary) -> Variant:
    var expr := Expression.new()
    var var_names: PackedStringArray = PackedStringArray()
    var var_values: Array = []

    for key in variables:
        var_names.append(key)
        var_values.append(variables[key])

    var error := expr.parse(formula, var_names)
    if error != OK:
        push_error("Formula parse error: " + expr.get_error_text())
        return null

    # Do NOT pass a base_instance here — see security note below
    var result: Variant = expr.execute(var_values)
    if expr.has_execute_failed():
        push_error("Formula execute error in: " + formula)
        return null
    return result

# Usage
var damage: float = evaluator.evaluate(
    "base_damage * (1 + strength * 0.1)",
    {"base_damage": 10.0, "strength": 5}
)
```

> **Security:** Never call `expr.execute(var_values, self)` with a `base_instance` when formula strings come from untrusted sources (save files, mods, network). Passing `self` grants the expression full method-call access to that object — a sandbox escape. The safe form above passes no base instance, limiting expressions to arithmetic and the provided variables.

**When to use:** Data-driven damage formulas, mod scripts, designer-editable game logic. For full scripting, GDScript itself is the bytecode VM.

---

### Subclass Sandbox → Base Script + class_name

Abilities extend `Node` (not `Resource`) so they can receive `_process` callbacks for cooldown ticking. Mount them as child nodes of the caster.

```gdscript
# ability.gd — sandbox base
class_name Ability extends Node

@export var ability_name: String = ""
@export var cooldown: float = 1.0

var _cooldown_remaining: float = 0.0

func can_use() -> bool:
    return _cooldown_remaining <= 0.0

func use(caster: CharacterBody2D) -> void:
    if not can_use():
        return
    _cooldown_remaining = cooldown
    _execute(caster)  # subclasses implement this

func _execute(caster: CharacterBody2D) -> void:
    pass  # override in subclasses

func _process(delta: float) -> void:
    _cooldown_remaining = max(0.0, _cooldown_remaining - delta)
```

```gdscript
# fireball_ability.gd
class_name FireballAbility extends Ability

@export var fireball_scene: PackedScene
@export var damage: int = 25

func _execute(caster: CharacterBody2D) -> void:
    if fireball_scene == null:
        push_error("FireballAbility: fireball_scene not assigned on " + name)
        return
    var fireball: Node2D = fireball_scene.instantiate()
    fireball.global_position = caster.global_position
    fireball.damage = damage
    caster.get_parent().add_child(fireball)
```

**When to use:** Ability systems, enemy behaviors, item effects — anything where many variants share a common lifecycle.

---

### Type Object → Custom Resource Subclass

Each "type" is a `.tres` file. Behavior comes from exported data, not code subclasses.

```gdscript
# enemy_type.gd
class_name EnemyType extends Resource

@export var type_name: String = ""
@export var max_health: int = 50
@export var speed: float = 100.0
@export var damage: int = 10
@export var sprite_frames: SpriteFrames
@export var loot_table: Array[ItemData] = []
@export var xp_reward: int = 10
```

```gdscript
# enemy.gd — one script, many types
class_name Enemy extends CharacterBody2D

@export var enemy_type: EnemyType  # assign goblin.tres, skeleton.tres, etc.

func _ready() -> void:
    if enemy_type == null:
        push_error("Enemy: enemy_type not assigned on " + name)
        return
    $HealthComponent.max_health = enemy_type.max_health
    $AnimatedSprite2D.sprite_frames = enemy_type.sprite_frames
    speed = enemy_type.speed
```

Create `goblin.tres`, `skeleton.tres`, `dragon.tres` in the editor — each is an `EnemyType` resource with different values. One `enemy.gd` script handles all of them.

**When to use:** Any entity with many variants that differ in data, not behavior. Items, enemies, weapons, spells.
**Common mistake:** Creating a subclass per enemy type (`GoblinEnemy extends Enemy`). Use Type Object instead — it's data-driven and doesn't require code changes to add new types.
