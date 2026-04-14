# GDScript Patterns Reference

## Signal Bus Pattern

An EventBus AutoLoad decouples systems that have no natural parent-child relationship. Use it for game-wide events, not for local parent-child communication.

```gdscript
# autoloads/event_bus.gd
# Register as AutoLoad named "EventBus" in Project Settings
extends Node

# Game lifecycle
signal game_started
signal game_over(winner: String)
signal level_completed(level_index: int)

# Player events
signal player_died
signal player_respawned(position: Vector2)
signal score_changed(new_score: int)

# Item events
signal item_picked_up(item_data: ItemData)
signal item_dropped(item_data: ItemData, position: Vector2)
```

```gdscript
# Any script can emit
EventBus.score_changed.emit(new_score)

# Any script can listen
func _ready() -> void:
    EventBus.score_changed.connect(_on_score_changed)
    EventBus.game_over.connect(_on_game_over)
```

**Keep the EventBus lean.** Only events that genuinely cross scene boundaries belong here. If only two nodes need to communicate, use a direct signal connection.

---

## State Machine Implementation

The Packt book's approach: a `StateMachine` node owns `State` child nodes. Each state is a script on a `Node`.

```gdscript
# state.gd — base class for all states
class_name State extends Node

# Override these in subclasses
func enter() -> void:
    pass

func exit() -> void:
    pass

func update(delta: float) -> void:
    pass

func physics_update(delta: float) -> void:
    pass

func get_transition() -> State:
    return null  # return a State to transition, null to stay
```

```gdscript
# state_machine.gd
class_name StateMachine extends Node

@export var initial_state: State

var current_state: State

var _transitioning: bool = false

func _ready() -> void:
    if initial_state == null:
        push_error("StateMachine: initial_state not set on " + name)
        return
    current_state = initial_state
    current_state.enter()

func _process(delta: float) -> void:
    if current_state == null:
        return
    current_state.update(delta)
    var next_state: State = current_state.get_transition()
    if next_state:
        transition_to(next_state)

func _physics_process(delta: float) -> void:
    if current_state == null:
        return
    current_state.physics_update(delta)

func transition_to(new_state: State) -> void:
    if _transitioning:
        push_error("StateMachine: re-entrant transition attempted — queue transitions instead")
        return
    _transitioning = true
    current_state.exit()
    current_state = new_state
    current_state.enter()
    _transitioning = false
    # Note: GDScript has no try/finally. If exit() or enter() crashes mid-execution,
    # _transitioning stays true and the state machine locks. Keep state exit()/enter()
    # implementations free of operations that abort execution (e.g., queue_free(self)).
```

```gdscript
# player_idle_state.gd
class_name PlayerIdleState extends State

@export var player: CharacterBody2D
@export var animated_sprite: AnimatedSprite2D  # wire in editor
@export var run_state: State
@export var jump_state: State

func enter() -> void:
    player.velocity = Vector2.ZERO
    if animated_sprite:
        animated_sprite.play("idle")

func get_transition() -> State:
    if Input.get_axis("move_left", "move_right") != 0.0:
        return run_state
    if Input.is_action_just_pressed("jump"):
        return jump_state
    return null
```

Scene tree for a player with state machine:
```
Player (CharacterBody2D)
├── StateMachine (Node, script: state_machine.gd)
│   ├── IdleState (Node, script: player_idle_state.gd)
│   ├── RunState (Node, script: player_run_state.gd)
│   └── JumpState (Node, script: player_jump_state.gd)
├── AnimatedSprite2D
└── CollisionShape2D
```

Wire `initial_state` and state transitions via `@export` in the editor — no hardcoded state names.

---

## Resource-Based Configuration

Custom Resources are the cleanest way to define data-driven game content. Define once, create many `.tres` instances in the editor.

```gdscript
# resources/item_data.gd
class_name ItemData extends Resource

@export var item_name: String = ""
@export var description: String = ""
@export var icon: Texture2D
@export var max_stack: int = 1
@export var value: int = 0
@export var weight: float = 0.0
enum ItemType { WEAPON, ARMOR, CONSUMABLE, QUEST }
@export var item_type: ItemType = ItemType.CONSUMABLE
```

```gdscript
# resources/weapon_data.gd
class_name WeaponData extends ItemData

@export var damage: int = 10
@export var attack_speed: float = 1.0
@export var range: float = 50.0
@export var projectile_scene: PackedScene
```

```gdscript
# In a node that uses weapon data
@export var weapon: WeaponData

func attack() -> void:
    if weapon == null:
        return
    if weapon.projectile_scene == null:
        push_error("WeaponData '%s' has no projectile_scene assigned" % weapon.item_name)
        return
    var projectile: Node2D = weapon.projectile_scene.instantiate()
    # configure projectile with weapon.damage, etc.
```

Create `.tres` files in the editor (right-click in FileSystem → New Resource → WeaponData). Each weapon is a separate `.tres` file — no code changes needed to add new weapons.

**Resource arrays for databases:**

```gdscript
# item_database.gd (AutoLoad or Resource)
class_name ItemDatabase extends Resource

@export var items: Array[ItemData] = []

func get_item_by_name(item_name: String) -> ItemData:
    for item in items:
        if item.item_name == item_name:
            return item
    return null
```

---

## Coroutine Patterns

### Sequential animation sequence

```gdscript
func play_death_sequence() -> void:
    $AnimationPlayer.play("hurt")
    await $AnimationPlayer.animation_finished
    if not is_instance_valid(self):
        return

    $AnimationPlayer.play("death")
    await $AnimationPlayer.animation_finished
    if not is_instance_valid(self):
        return

    await get_tree().create_timer(0.5).timeout
    if is_instance_valid(self):
        queue_free()
```

> **Coroutine safety rule:** After every `await`, check `is_instance_valid(self)` before accessing nodes or calling methods. Nodes can be freed externally (scene change, level reset) while a coroutine is suspended.

### Async scene transition

```gdscript
# scene_manager.gd (AutoLoad)
func transition_to(scene_path: String) -> void:
    $AnimationPlayer.play("fade_out")
    await $AnimationPlayer.animation_finished

    get_tree().change_scene_to_file(scene_path)

    await get_tree().process_frame  # wait one frame for new scene to load
    $AnimationPlayer.play("fade_in")
```

### Waiting for a condition

```gdscript
# Wait for player to be ready before spawning enemies
func _ready() -> void:
    await get_tree().process_frame  # let all nodes finish _ready
    _start_wave()
```

### Coroutine with timeout (don't hang forever)

Godot has no `Promise.race`. Use a flag set by both the signal and the timer:

```gdscript
# Waits for input or timeout. Returns true if input was received before timeout.
# Note: ensure the owning node outlives the timeout duration, or add
# is_instance_valid(self) guards after each await.
func _prompt_player(timeout: float = 5.0) -> bool:
    var responded := false

    var timer := get_tree().create_timer(timeout)
    timer.timeout.connect(func(): responded = true, CONNECT_ONE_SHOT)
    $InputDetector.input_received.connect(func(): responded = true, CONNECT_ONE_SHOT)

    while not responded:
        await get_tree().process_frame
        if not is_instance_valid(self):
            return false  # node freed while waiting

    return $InputDetector.last_input != ""
```

---

## Typed Arrays and Dictionaries

### Typed arrays (Godot 4.x)

```gdscript
var enemies: Array[Enemy] = []
var item_names: Array[String] = []
var damage_values: Array[int] = [10, 20, 30]

# Typed array operations
enemies.append(new_enemy)
enemies.filter(func(e: Enemy) -> bool: return e.is_alive())
enemies.map(func(e: Enemy) -> int: return e.health)
```

### Dictionaries as lightweight data objects

```gdscript
# Use typed custom Resources for persistent data
# Use Dictionary for transient/computed data

func get_player_stats() -> Dictionary:
    return {
        "health": health_component.current_health,
        "position": global_position,
        "score": score,
    }

# Type-annotate dictionary values where possible
var save_data: Dictionary = {
    "level": 1,
    "score": 0,
    "player_position": Vector2.ZERO,
}
```

For data that persists or gets passed around, prefer a custom `Resource` or a `class_name` script with typed variables. Dictionaries are fine for transient, local data.

---

## Input Handling Patterns

### Action-based input (preferred)

```gdscript
func _process(delta: float) -> void:
    var direction: Vector2 = Input.get_vector("move_left", "move_right", "move_up", "move_down")
    velocity = direction * speed

func _unhandled_input(event: InputEvent) -> void:
    if event.is_action_pressed("jump"):
        _jump()
    elif event.is_action_pressed("attack"):
        _attack()
```

Use `_unhandled_input` for game actions — it only fires if no UI element consumed the event first. Use `_input` only when you need to intercept before UI.

### Remappable controls

Define actions in Project Settings → Input Map. Scripts reference action names, never key codes. This makes remapping trivial.

---

## Tween Patterns

```gdscript
# Smooth movement
func move_to(target: Vector2) -> void:
    var tween := create_tween()
    tween.tween_property(self, "global_position", target, 0.3)\
        .set_ease(Tween.EASE_OUT)\
        .set_trans(Tween.TRANS_CUBIC)

# Sequence of tweens
func bounce_and_fade() -> void:
    var tween := create_tween()
    tween.tween_property(self, "scale", Vector2(1.3, 1.3), 0.1)
    tween.tween_property(self, "scale", Vector2.ONE, 0.1)
    tween.tween_property(self, "modulate:a", 0.0, 0.5)
    await tween.finished
    queue_free()
```

Prefer `Tween` over `AnimationPlayer` for code-driven, parameterized animations. Use `AnimationPlayer` for authored, asset-driven animations.
