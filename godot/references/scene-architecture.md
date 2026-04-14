# Scene Architecture Reference

## Node Selection Guide

Choose the right base node type — the wrong base creates unnecessary overhead and missing functionality.

### 2D

| Need | Node |
|---|---|
| Player, enemy, NPC with physics | `CharacterBody2D` |
| Rigid physics object (crate, ball) | `RigidBody2D` |
| Static environment (walls, platforms) | `StaticBody2D` |
| Trigger zone, hitbox, hurtbox | `Area2D` |
| Sprite with no physics | `Sprite2D` or `AnimatedSprite2D` |
| UI anchored to world position | `Node2D` + `CanvasLayer` |
| Tile-based levels | `TileMapLayer` (Godot 4.3+) |
| Particle effects | `GPUParticles2D` |
| Raycasting | `RayCast2D` |

### 3D

| Need | Node |
|---|---|
| Player, enemy with physics | `CharacterBody3D` |
| Rigid physics object | `RigidBody3D` |
| Static environment | `StaticBody3D` |
| Trigger zone | `Area3D` |
| Mesh rendering | `MeshInstance3D` |
| Skeletal animation | `Skeleton3D` + `AnimationPlayer` |
| Particle effects | `GPUParticles3D` |
| Navigation agent | `NavigationAgent3D` |

### UI

| Need | Node |
|---|---|
| Screen-space UI root | `CanvasLayer` |
| Flexible layout | `Control` subclasses (`HBoxContainer`, `VBoxContainer`, `GridContainer`) |
| Text | `Label`, `RichTextLabel` |
| Button | `Button`, `TextureButton` |
| Progress bar | `ProgressBar` |
| Popup | `PopupPanel` |
| Inventory grid | `GridContainer` inside `ScrollContainer` |

### Utility Nodes

| Need | Node |
|---|---|
| Timed events | `Timer` |
| Audio | `AudioStreamPlayer` (global), `AudioStreamPlayer2D` (positional) |
| Animation | `AnimationPlayer`, `AnimationTree` |
| Tweening | `Tween` (created via `create_tween()`) |
| Pathfinding | `NavigationRegion2D/3D` + `NavigationAgent2D/3D` |
| Camera | `Camera2D`, `Camera3D` |

---

## Scene Splitting Decisions

### Split into a separate scene when:

1. **Reuse** — the scene appears in multiple parent scenes (enemy, bullet, pickup, UI panel)
2. **Independent lifecycle** — it gets instantiated and freed independently
3. **Size** — the scene exceeds ~20 nodes and has a clear conceptual boundary
4. **Ownership** — a different "system" logically owns it (a level owns enemies, not the player)
5. **Iteration speed** — you edit it frequently and want to open it in isolation

### Keep inline (as nodes in parent) when:

1. It's structural glue — `HBoxContainer`, `Marker2D`, `CollisionShape2D`
2. It's never reused outside this parent
3. It has no independent state

### Practical example — enemy scene:

```
Enemy.tscn
├── CharacterBody2D (root, script: enemy.gd)
├── AnimatedSprite2D
├── CollisionShape2D
├── HealthComponent.tscn (instanced — reused by player too)
├── HurtboxComponent.tscn (instanced)
├── NavigationAgent2D
└── Timer (patrol timer — inline, not reused)
```

`HealthComponent` and `HurtboxComponent` are their own scenes because they're reused. `Timer` stays inline because it's specific to this enemy's patrol logic.

---

## Large Project Organization

For projects beyond a few scenes, organize by **feature/domain**, not by file type:

```
res://
├── actors/
│   ├── player/
│   │   ├── player.tscn
│   │   ├── player.gd
│   │   └── player_states/
│   │       ├── idle_state.gd
│   │       └── run_state.gd
│   └── enemies/
│       ├── goblin/
│       └── skeleton/
├── components/
│   ├── health_component.tscn
│   ├── health_component.gd
│   ├── hurtbox_component.tscn
│   └── hitbox_component.tscn
├── ui/
│   ├── hud.tscn
│   └── menus/
├── levels/
│   ├── level_01.tscn
│   └── level_02.tscn
├── resources/
│   ├── items/
│   │   ├── sword.tres
│   │   └── shield.tres
│   └── enemies/
│       └── goblin_stats.tres
├── autoloads/
│   ├── event_bus.gd
│   ├── scene_manager.gd
│   └── audio_manager.gd
└── shared/
    ├── constants.gd
    └── utils.gd
```

**Key rules:**
- Each feature folder contains its scene, script, and related assets together
- `components/` holds reusable capability nodes
- `resources/` holds `.tres` data files
- `autoloads/` holds AutoLoad scripts (register them in Project Settings)

---

## Composition Patterns

### Component Pattern

Give entities capabilities via child nodes. Each component is a focused script on a `Node`.

```gdscript
# health_component.gd
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
    if current_health == 0:
        died.emit()

func heal(amount: int) -> void:
    current_health = min(max_health, current_health + amount)
    health_changed.emit(current_health, max_health)
```

```gdscript
# player.gd — wires up components in _ready
extends CharacterBody2D

@onready var health_component: HealthComponent = $HealthComponent
@onready var hud: HUD = $HUD

func _ready() -> void:
    health_component.health_changed.connect(_on_health_changed)
    health_component.died.connect(_on_died)

func _on_health_changed(new_health: int, max_health: int) -> void:
    hud.update_health(new_health, max_health)

func _on_died() -> void:
    # handle death
    pass
```

### Scene Instancing Pattern

```gdscript
# spawner.gd — manages enemy spawning
class_name Spawner extends Node

@export var enemy_scene: PackedScene
@export var spawn_interval: float = 3.0

var _timer: float = 0.0

func _process(delta: float) -> void:
    _timer += delta
    if _timer >= spawn_interval:
        _timer = 0.0
        _spawn_enemy()

func _spawn_enemy() -> void:
    var enemy: Node = enemy_scene.instantiate()
    enemy.global_position = global_position
    get_parent().add_child(enemy)  # add to same level as spawner
```

### Dependency Injection via @export

Instead of AutoLoads or `get_node` path strings, inject dependencies through the editor:

```gdscript
# ui_health_bar.gd
class_name UIHealthBar extends ProgressBar

@export var health_component: HealthComponent  # drag-drop in editor

func _ready() -> void:
    if health_component:
        health_component.health_changed.connect(_on_health_changed)
        max_value = health_component.max_health
        value = health_component.current_health

func _on_health_changed(new_health: int, max_health: int) -> void:
    max_value = max_health
    value = new_health
```

This makes the relationship explicit and editor-visible. No hidden globals, no fragile path strings.

---

## Scene Communication Patterns

### Parent → Child: Direct method call

A parent owns its children. Calling methods on them is fine.

```gdscript
# parent calling child
$AnimationPlayer.play("run")
$HealthComponent.heal(20)
```

### Child → Parent: Signal

Children don't know who their parent is. Emit a signal; the parent listens.

```gdscript
# child emits
signal item_collected(item: ItemData)

# parent connects in _ready
$Player.item_collected.connect(_on_item_collected)
```

### Sibling → Sibling: Route through parent or EventBus

Siblings shouldn't hold direct references to each other. Either the parent mediates, or an EventBus AutoLoad carries the event.

```gdscript
# EventBus.gd (AutoLoad)
signal enemy_killed(enemy_type: String, position: Vector2)

# enemy.gd
func _die() -> void:
    EventBus.enemy_killed.emit(enemy_type, global_position)

# score_manager.gd
func _ready() -> void:
    EventBus.enemy_killed.connect(_on_enemy_killed)
```
