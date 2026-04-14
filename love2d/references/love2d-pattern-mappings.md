# Love2D Pattern Mappings

Full Lua implementations of all 23 game patterns for Love2D 11.x. Love2D is a thin framework — most patterns are manual implementations using Lua tables and metatables.

## Table of Contents

- [Observer](#observer--callback-tables)
- [Singleton](#singleton--module-return-value)
- [State](#state--state-manager-table)
- [Command](#command--tables-with-executeundo)
- [Factory](#factory--constructor-functions)
- [Strategy](#strategy--swappable-function-field)
- [Decorator](#decorator--wrapper-table-with-__index)
- [Service Locator](#service-locator--module-level-registry)
- [Event Queue](#event-queue--array-buffer)
- [Component](#component--domain-tables-with-system-functions)
- [Prototype](#prototype--deep-copy)
- [Flyweight](#flyweight--shared-data-tables)
- [Object Pool](#object-pool--pre-allocated-array)
- [Double Buffer](#double-buffer--canvas-swap)
- [Game Loop](#game-loop--built-in)
- [Update Method](#update-method--entity-update-function)
- [Spatial Partition](#spatial-partition--grid)
- [Dirty Flag](#dirty-flag--boolean-on-table)
- [Data Locality](#data-locality--array-of-tables)
- [Bytecode](#bytecode--lua-load)
- [Subclass Sandbox](#subclass-sandbox--base-table-with-__index)
- [Type Object](#type-object--shared-type-table)
- [Input](#input--love-callbacks)

---

## Observer → Callback Tables

**Love2D approach:** Maintain a list of listener functions per event. Call each listener when the event fires.

```lua
-- event_bus.lua
local EventBus = {}
local listeners = {}

function EventBus.on(event, fn)
    if not listeners[event] then
        listeners[event] = {}
    end
    table.insert(listeners[event], fn)
end

function EventBus.emit(event, ...)
    if listeners[event] then
        for _, fn in ipairs(listeners[event]) do
            fn(...)
        end
    end
end

return EventBus
```

```lua
-- Usage
local EventBus = require("event_bus")

EventBus.on("player_died", function()
    -- show game over screen
end)

-- Elsewhere:
EventBus.emit("player_died")
```

**Community alternative:** None needed — this pattern is simple enough to implement directly.

---

## Singleton → Module Return Value

**Love2D approach:** Lua's `require` caches module return values. A module that returns a table is a singleton — every `require` of the same file returns the same table.

```lua
-- game_state.lua
local GameState = {
    score = 0,
    lives = 3,
    level = 1,
}

function GameState.add_score(points)
    GameState.score = GameState.score + points
end

function GameState.reset()
    GameState.score = 0
    GameState.lives = 3
    GameState.level = 1
end

return GameState
```

```lua
-- Usage from any file
local GameState = require("game_state")
GameState.add_score(100)
```

**Note:** Lua module caching is per-`package.loaded` entry. Don't `dofile` or manually reload modules if you want singleton behavior.

---

## State → State Manager Table

**Love2D approach:** Each state is a module (table) with `enter`, `exit`, `update(dt)`, and `draw` functions. A manager table holds the current state and delegates callbacks to it.

```lua
-- states/play.lua
local Play = {}

function Play.enter()
    -- initialize play state
end

function Play.exit()
    -- clean up
end

function Play.update(dt)
    -- update game logic
end

function Play.draw()
    -- render game
end

return Play
```

```lua
-- state_manager.lua
local StateManager = { current = nil }

function StateManager.switch(new_state)
    if StateManager.current and StateManager.current.exit then
        StateManager.current.exit()
    end
    StateManager.current = new_state
    if new_state.enter then
        new_state.enter()
    end
end

function StateManager.update(dt)
    if StateManager.current and StateManager.current.update then
        StateManager.current.update(dt)
    end
end

function StateManager.draw()
    if StateManager.current and StateManager.current.draw then
        StateManager.current.draw()
    end
end

return StateManager
```

```lua
-- main.lua
local StateManager = require("state_manager")
local Play = require("states/play")
local Menu = require("states/menu")

function love.load()
    StateManager.switch(Menu)
end

function love.update(dt)
    StateManager.update(dt)
end

function love.draw()
    StateManager.draw()
end
```

**Community alternative:** [hump.gamestate](https://github.com/vrld/hump) — provides push/pop state stack in addition to simple switching.

---

## Command → Tables with execute/undo

**Love2D approach:** Each command is a table with `execute` and `undo` functions. Store a history array for undo support.

```lua
-- command_processor.lua
local CommandProcessor = { history = {} }

function CommandProcessor.execute(cmd)
    cmd.execute()
    table.insert(CommandProcessor.history, cmd)
end

function CommandProcessor.undo()
    local cmd = table.remove(CommandProcessor.history)
    if cmd and cmd.undo then
        cmd.undo()
    end
end

return CommandProcessor
```

```lua
-- Usage — move command with undo
local function make_move_command(entity, dx, dy)
    return {
        execute = function()
            entity.x = entity.x + dx
            entity.y = entity.y + dy
        end,
        undo = function()
            entity.x = entity.x - dx
            entity.y = entity.y - dy
        end,
    }
end

local cmd = make_move_command(player, 32, 0)
CommandProcessor.execute(cmd)
-- later:
CommandProcessor.undo()
```

---

## Factory → Constructor Functions

**Love2D approach:** A constructor function creates and returns a configured table. Centralizes construction logic.

```lua
-- entities/enemy.lua
local Enemy = {}

-- Load sprites once, not per-instance
local sprites = {}
local function get_sprite(path)
    if not sprites[path] then
        sprites[path] = love.graphics.newImage(path)
    end
    return sprites[path]
end

function Enemy.new(x, y, enemy_type)
    local config = {
        goblin = { hp = 30, speed = 80, sprite = "assets/goblin.png" },
        orc    = { hp = 80, speed = 50, sprite = "assets/orc.png" },
    }
    local cfg = config[enemy_type] or config.goblin

    return {
        x = x,
        y = y,
        hp = cfg.hp,
        speed = cfg.speed,
        sprite = get_sprite(cfg.sprite),  -- shared; not created per-instance
        active = true,
    }
end

return Enemy
```

```lua
-- Usage
local Enemy = require("entities/enemy")
local e = Enemy.new(200, 300, "goblin")
```

---

## Strategy → Swappable Function Field

**Love2D approach:** Store the algorithm as a function field on the entity. Swap the field to change behavior.

```lua
-- AI strategies as plain functions
local function chase_strategy(enemy, player, dt)
    local dx = player.x - enemy.x
    local dy = player.y - enemy.y
    local len = math.sqrt(dx*dx + dy*dy)
    if len > 0 then
        enemy.x = enemy.x + (dx/len) * enemy.speed * dt
        enemy.y = enemy.y + (dy/len) * enemy.speed * dt
    end
end

local function patrol_strategy(enemy, player, dt)
    enemy.x = enemy.x + enemy.speed * enemy.dir * dt
    if enemy.x > enemy.patrol_max or enemy.x < enemy.patrol_min then
        enemy.dir = -enemy.dir
    end
end

-- Entity with swappable strategy
local enemy = {
    x = 100, y = 100,
    speed = 60,
    dir = 1, patrol_min = 50, patrol_max = 250,
    move = patrol_strategy,  -- start patrolling
}

-- Switch to chase when player is near
function enemy:update(player, dt)
    local dx = player.x - self.x
    local dy = player.y - self.y
    if math.sqrt(dx*dx + dy*dy) < 150 then
        self.move = chase_strategy
    else
        self.move = patrol_strategy
    end
    self.move(self, player, dt)
end
```

---

## Decorator → Wrapper Table with __index

**Love2D approach:** Create a wrapper table that delegates unknown fields to the inner object via `__index`. Override specific methods to add behavior.

```lua
-- Wrap an entity with a speed boost
local function with_speed_boost(entity, multiplier, duration)
    local original_speed = entity.speed
    local timer = duration

    local wrapper = setmetatable({}, {
        __index = entity,  -- delegate all reads to inner entity
    })

    -- Override update to tick the timer and restore speed
    function wrapper:update(dt)
        timer = timer - dt
        if timer <= 0 then
            entity.speed = original_speed
            wrapper.expired = true  -- caller should remove wrapper from entity list
            -- still update entity on expiry frame
            if entity.update then entity:update(dt) end
            return
        end
        if entity.update then entity:update(dt) end
    end

    entity.speed = entity.speed * multiplier
    return wrapper
end

-- Usage: replace entity in your list with wrapper; remove when expired
-- for i = #entities, 1, -1 do
--     if entities[i].expired then table.remove(entities, i) end
-- end
```

**Note:** Deep wrapper chains become hard to debug. For flat, composable effects, prefer a list of active modifiers on the entity instead.

---

## Service Locator → Module-Level Registry

**Love2D approach:** A module holds a table of named services. Swap implementations by reassigning entries.

```lua
-- services.lua
local Services = {}
local registry = {}

function Services.register(name, impl)
    registry[name] = impl
end

function Services.get(name)
    return registry[name]
end

-- Null implementations for safe defaults
Services.register("audio", {
    play = function(sound) end,  -- no-op
    stop = function(sound) end,
})

return Services
```

```lua
-- Register real audio on load
local Services = require("services")
local RealAudio = require("audio/real_audio")

function love.load()
    Services.register("audio", RealAudio)
end

-- Use from anywhere
local Services = require("services")
Services.get("audio").play("explosion")
```

---

## Event Queue → Array Buffer

**Love2D approach:** Append events to an array. Drain the array in `love.update`.

```lua
-- event_queue.lua
local EventQueue = { _queue = {}, _handlers = {} }

function EventQueue.push(event_type, data)
    table.insert(EventQueue._queue, { type = event_type, data = data or {} })
end

function EventQueue.on(event_type, fn)
    if not EventQueue._handlers[event_type] then
        EventQueue._handlers[event_type] = {}
    end
    table.insert(EventQueue._handlers[event_type], fn)
end

function EventQueue.drain()
    local queue = EventQueue._queue
    EventQueue._queue = {}  -- swap to new table; handlers may push new events
    for _, event in ipairs(queue) do
        local handlers = EventQueue._handlers[event.type]
        if handlers then
            for _, fn in ipairs(handlers) do
                fn(event.data)
            end
        end
    end
end

return EventQueue
```

```lua
-- In love.update:
EventQueue.drain()

-- Anywhere:
EventQueue.push("enemy_killed", { x = 200, y = 300 })
```

---

## Component → Domain Tables with System Functions

**Love2D approach:** An entity is a table of component sub-tables. System functions iterate all entities and operate on a specific component.

```lua
-- Entity with components — initialized in love.load, not at module level
local player  -- declared here, constructed in love.load

function love.load()
    player = {
        transform = { x = 100, y = 200 },
        health    = { current = 100, max = 100 },
        sprite    = { image = love.graphics.newImage("assets/player.png") },
        velocity  = { vx = 0, vy = 0 },
    }
end

-- System functions
local function physics_system(entities, dt)
    for _, e in ipairs(entities) do
        if e.transform and e.velocity then
            e.transform.x = e.transform.x + e.velocity.vx * dt
            e.transform.y = e.transform.y + e.velocity.vy * dt
        end
    end
end

local function render_system(entities)
    for _, e in ipairs(entities) do
        if e.transform and e.sprite then
            love.graphics.draw(e.sprite.image, e.transform.x, e.transform.y)
        end
    end
end
```

---

## Prototype → Deep Copy

**Love2D approach:** Recursively copy a template table to create independent instances.

```lua
-- util.lua
local function deep_copy(orig)
    local copy
    if type(orig) == "table" then
        copy = {}
        for k, v in pairs(orig) do
            copy[deep_copy(k)] = deep_copy(v)
        end
        setmetatable(copy, getmetatable(orig))
    else
        copy = orig
    end
    return copy
end

-- Template
local sword_template = {
    name = "Iron Sword",
    damage = 10,
    weight = 3.5,
}

-- Create instances from template
local enchanted_sword = deep_copy(sword_template)
enchanted_sword.name = "Enchanted Sword"
enchanted_sword.damage = 20
```

**Metatable alternative:** Set the template as `__index` on instances for shared-but-overridable data without copying.

---

## Flyweight → Shared Data Tables

**Love2D approach:** Multiple entity instances reference the same "type" table for shared immutable data. Only per-instance data is stored on each entity.

```lua
-- Shared type data — sprites loaded in love.load, not at module level
local enemy_types = {
    goblin = { sprite = nil, max_hp = 30, speed = 80, xp = 10 },
    orc    = { sprite = nil, max_hp = 80, speed = 50, xp = 25 },
}

-- Call this from love.load before spawning any enemies
local function load_enemy_types()
    enemy_types.goblin.sprite = love.graphics.newImage("assets/goblin.png")
    enemy_types.orc.sprite    = love.graphics.newImage("assets/orc.png")
end

-- Per-instance data only
local function new_enemy(type_name, x, y)
    local t = enemy_types[type_name]
    assert(t, "unknown enemy type: " .. tostring(type_name))
    return {
        type = t,       -- shared reference
        x = x,
        y = y,
        hp = t.max_hp,  -- per-instance copy
    }
end

-- Drawing uses shared sprite
local function draw_enemy(e)
    love.graphics.draw(e.type.sprite, e.x, e.y)
end
```

---

## Object Pool → Pre-Allocated Array

**Love2D approach:** Pre-allocate a fixed array of entities. Mark them active/inactive instead of creating/destroying.

```lua
-- bullet_pool.lua
local BulletPool = {}
local pool = {}
local POOL_SIZE = 50

function BulletPool.init()
    for i = 1, POOL_SIZE do
        pool[i] = { active = false, x = 0, y = 0, vx = 0, vy = 0 }
    end
end

function BulletPool.get()
    for _, b in ipairs(pool) do
        if not b.active then
            b.active = true
            return b
        end
    end
    return nil  -- pool exhausted
end

function BulletPool.release(bullet)
    bullet.active = false
end

function BulletPool.update(dt)
    for _, b in ipairs(pool) do
        if b.active then
            b.x = b.x + b.vx * dt
            b.y = b.y + b.vy * dt
            -- deactivate if off-screen
            if b.x < 0 or b.x > 800 or b.y < 0 or b.y > 600 then
                b.active = false
            end
        end
    end
end

function BulletPool.draw()
    for _, b in ipairs(pool) do
        if b.active then
            love.graphics.circle("fill", b.x, b.y, 4)
        end
    end
end

return BulletPool
```

**Usage — always check for nil when the pool may be exhausted:**

```lua
BulletPool.init()

-- Firing a bullet:
local b = BulletPool.get()
if b then
    b.x = player.x
    b.y = player.y
    b.vx = 0
    b.vy = -300
end
```

---

## Double Buffer → Canvas Swap

**Love2D approach:** Render to a `Canvas` each frame; draw the canvas to the screen. For logic double-buffering (cellular automata), swap two arrays.

```lua
-- Post-processing with canvas
local scene_canvas
local post_shader  -- define your shader; nil = no post-processing

local function draw_scene()
    -- your game world rendering here
end

function love.load()
    scene_canvas = love.graphics.newCanvas(800, 600)
    -- post_shader = love.graphics.newShader("shaders/post.glsl")
end

function love.draw()
    -- Render scene to canvas
    love.graphics.setCanvas(scene_canvas)
    love.graphics.clear()
    draw_scene()
    love.graphics.setCanvas()

    -- Draw canvas to screen (apply post-processing shader here)
    if post_shader then love.graphics.setShader(post_shader) end
    love.graphics.draw(scene_canvas, 0, 0)
    love.graphics.setShader()
end
```

For logic double-buffering (e.g., Game of Life):

```lua
local front = {}  -- read buffer
local back  = {}  -- write buffer

function love.update(dt)
    simulate(front, back)
    front, back = back, front  -- swap
end
```

---

## Game Loop → Built-in

**Love2D approach:** Love2D owns the loop. Override `love.update(dt)` and `love.draw()`.

```lua
function love.update(dt)
    -- dt is seconds since last frame; always multiply movement by dt
    player.x = player.x + player.vx * dt
    player.y = player.y + player.vy * dt
end

function love.draw()
    love.graphics.draw(player.sprite, player.x, player.y)
end
```

For a fixed-timestep loop, override `love.run`:

```lua
function love.run()
    if love.load then love.load() end
    local accumulator = 0
    local fixed_dt = 1/60
    local last_time = love.timer.getTime()

    return function()
        love.event.pump()
        for name, a, b, c, d, e, f in love.event.poll() do
            if name == "quit" then
                if not love.quit or not love.quit() then return a or 0 end
            end
            if love.handlers[name] then
                love.handlers[name](a, b, c, d, e, f)
            end
        end

        local now = love.timer.getTime()
        local dt = now - last_time
        last_time = now
        accumulator = accumulator + dt
        -- Cap accumulator to prevent spiral-of-death after pauses
        if accumulator > 0.25 then accumulator = 0.25 end

        while accumulator >= fixed_dt do
            if love.update then love.update(fixed_dt) end
            accumulator = accumulator - fixed_dt
        end

        if love.graphics and love.graphics.isActive() then
            love.graphics.origin()
            love.graphics.clear()
            if love.draw then love.draw() end
            love.graphics.present()
        end
    end
end
```

---

## Update Method → Entity update Function

**Love2D approach:** Each entity table has an `update(dt)` function. The game loop calls it each frame.

```lua
local function new_enemy(x, y)
    local self = { x = x, y = y, speed = 60, active = true }

    function self:update(dt)
        self.x = self.x + self.speed * dt
        if self.x > 900 then
            self.active = false
        end
    end

    function self:draw()
        love.graphics.rectangle("fill", self.x, self.y, 32, 32)
    end

    return self
end

-- In love.update:
for i = #enemies, 1, -1 do
    enemies[i]:update(dt)
    if not enemies[i].active then
        table.remove(enemies, i)
    end
end
```

---

## Spatial Partition → Grid

**Love2D approach:** Divide the world into a grid. Each cell holds a list of entities whose position falls within it. Query only nearby cells.

```lua
-- spatial_grid.lua
local Grid = {}
Grid.__index = Grid

function Grid.new(cell_size)
    return setmetatable({ cell_size = cell_size, cells = {} }, Grid)
end

function Grid:_key(x, y)
    local cx = math.floor(x / self.cell_size)
    local cy = math.floor(y / self.cell_size)
    return cx .. "," .. cy
end

function Grid:insert(entity)
    local key = self:_key(entity.x, entity.y)
    if not self.cells[key] then self.cells[key] = {} end
    table.insert(self.cells[key], entity)
end

function Grid:query(x, y, radius)
    local results = {}
    local r = math.ceil(radius / self.cell_size)
    local cx = math.floor(x / self.cell_size)
    local cy = math.floor(y / self.cell_size)
    for dx = -r, r do
        for dy = -r, r do
            local key = (cx+dx) .. "," .. (cy+dy)
            if self.cells[key] then
                for _, e in ipairs(self.cells[key]) do
                    table.insert(results, e)
                end
            end
        end
    end
    return results
end

function Grid:clear()
    self.cells = {}
end

return Grid
```

**Community alternative:** [bump.lua](https://github.com/kikito/bump.lua) — AABB collision detection with spatial hashing. Handles insertion, removal, and movement queries.

---

## Dirty Flag → Boolean on Table

**Love2D approach:** Set a `dirty` flag when source data changes. Recompute the cached value only when the flag is set and the value is needed.

```lua
local inventory = {
    items = {},
    _dirty = true,
    _cached_weight = 0,
}

function inventory:add_item(item)
    table.insert(self.items, item)
    self._dirty = true
end

function inventory:remove_item(item)
    for i, v in ipairs(self.items) do
        if v == item then
            table.remove(self.items, i)
            self._dirty = true
            return
        end
    end
end

function inventory:total_weight()
    if self._dirty then
        local w = 0
        for _, item in ipairs(self.items) do
            w = w + item.weight
        end
        self._cached_weight = w
        self._dirty = false
    end
    return self._cached_weight
end
```

---

## Data Locality → Array-of-Tables

**Love2D approach:** Store entities in a flat array with homogeneous structure. Iterate sequentially to benefit from CPU cache prefetching.

```lua
-- Homogeneous particle array — all particles have the same fields
local particles = {}
local MAX_PARTICLES = 1000

function init_particles()
    for i = 1, MAX_PARTICLES do
        particles[i] = { x=0, y=0, vx=0, vy=0, life=0, active=false }
    end
end

-- Tight update loop — sequential access, no table creation
function update_particles(dt)
    for i = 1, MAX_PARTICLES do
        local p = particles[i]
        if p.active then
            p.x = p.x + p.vx * dt
            p.y = p.y + p.vy * dt
            p.life = p.life - dt
            if p.life <= 0 then p.active = false end
        end
    end
end
```

**Note:** Lua tables are hash maps, not contiguous arrays. For true cache-locality in hot loops, consider LuaJIT's FFI with C structs, or keep the array dense (no holes) and avoid mixed types.

---

## Bytecode → Lua load

**Love2D approach:** Use `load()` (Lua 5.1: `loadstring`) to compile and execute Lua code at runtime. Useful for data-driven formulas, mod scripts, or scripted events.

```lua
-- Evaluate a formula string with variables
-- vars is a table of {name = value} pairs accessible in the formula
local function eval_formula(formula_str, vars)
    -- Pass vars as the chunk's environment so names resolve directly
    -- This avoids fragile positional vararg ordering
    local fn, err = load("return " .. formula_str, "formula", "t", vars)
    if not fn then return nil, err end
    return fn()
end

-- Usage
local damage, err = eval_formula(
    "base_damage * (1 + strength * 0.1)",
    { base_damage = 10, strength = 5 }
)
-- damage == 15.0
```

> **Security:** Never `load` strings from untrusted sources (network, user input) — Lua has no sandbox by default. For mod support, use a restricted environment or a dedicated scripting library.

---

## Subclass Sandbox → Base Table with __index

**Love2D approach:** Define a base table with shared methods. "Subclass" tables set the base as their `__index` metatable, inheriting all base methods while overriding specific ones.

```lua
-- ability.lua — base "class"
local Ability = {}
Ability.__index = Ability

function Ability.new(name, cooldown)
    return setmetatable({
        name = name,
        cooldown = cooldown,
        _timer = 0,
    }, Ability)
end

function Ability:can_use()
    return self._timer <= 0
end

function Ability:use(caster)
    if not self:can_use() then return end
    self._timer = self.cooldown
    self:_execute(caster)  -- subclasses override this
end

function Ability:_execute(caster)
    -- no-op in base
end

function Ability:update(dt)
    self._timer = math.max(0, self._timer - dt)
end
```

```lua
-- fireball.lua — "subclass"
local Ability = require("ability")
local Fireball = setmetatable({}, { __index = Ability })
Fireball.__index = Fireball

function Fireball.new()
    local self = Ability.new("Fireball", 1.5)
    return setmetatable(self, Fireball)
end

function Fireball:_execute(caster)
    -- spawn fireball projectile at caster position
    spawn_projectile(caster.x, caster.y, 10)
end

return Fireball
```

---

## Type Object → Shared Type Table

**Love2D approach:** A "type" table holds shared data and behavior. Instances set the type table as their `__index` metatable, inheriting all type-level data.

```lua
-- Define types
local enemy_types = {
    goblin = {
        max_hp = 30,
        speed  = 80,
        xp     = 10,
        sprite = nil,  -- loaded in love.load
    },
    orc = {
        max_hp = 80,
        speed  = 50,
        xp     = 25,
        sprite = nil,
    },
}

-- Load sprites once — call from love.load before any new_enemy() calls
function load_enemy_types()
    enemy_types.goblin.sprite = love.graphics.newImage("assets/goblin.png")
    enemy_types.orc.sprite    = love.graphics.newImage("assets/orc.png")
    -- Set __index on each type so instances inherit from it
    for _, t in pairs(enemy_types) do
        t.__index = t
    end
end

-- Create instance — inherits type data via __index
local function new_enemy(type_name, x, y)
    local t = enemy_types[type_name]
    assert(t, "unknown enemy type: " .. tostring(type_name))
    return setmetatable({
        x  = x,
        y  = y,
        hp = t.max_hp,  -- per-instance copy of max_hp
    }, t)
end

-- Usage: e.speed reads from type table; e.hp reads from instance
local e = new_enemy("goblin", 100, 200)
-- e.speed == 80 (from type), e.hp == 30 (per-instance)
```

---

## Input → Love Callbacks

**Love2D approach:** Define `love.keypressed`, `love.keyreleased`, `love.mousepressed`, `love.mousereleased`, and `love.mousemoved` in `main.lua`. For rebindable input, map action names to keys.

```lua
-- Simple direct input
function love.keypressed(key)
    if key == "space" then
        player:jump()
    elseif key == "escape" then
        love.event.quit()
    end
end

-- Rebindable input map
local bindings = {
    jump  = "space",
    left  = "left",
    right = "right",
    shoot = "z",
}

local function is_action_pressed(action)
    return love.keyboard.isDown(bindings[action])
end

function love.update(dt)
    if is_action_pressed("left") then
        player.x = player.x - player.speed * dt
    end
    if is_action_pressed("right") then
        player.x = player.x + player.speed * dt
    end
end

function love.keypressed(key)
    if key == bindings.jump then
        player:jump()
    end
end
```

**Note:** `love.keyboard.isDown` polls current state (good for held keys). `love.keypressed` fires once per press (good for discrete actions like jumping or shooting).
