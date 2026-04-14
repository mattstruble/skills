---
name: love2d
description: Use when working on any Love2D project — writing Lua for Love2D, implementing Love2D callbacks (love.load, love.update, love.draw), handling input, writing shaders, structuring a game loop, or asking about Love2D APIs. Also trigger when implementing game patterns (Observer, State, Command, etc.) in a Love2D project — this skill takes precedence over game-patterns for Love2D-specific implementation. NOT for Fennel interactive development workflow (see love2d-fennel). NOT for engine-agnostic pattern theory (see game-patterns).
---

# Love2D 11.x Development

Love2D 11.x (baseline: 11.1–11.5) with Lua. All code examples target Lua — not Fennel. This skill is for hobbyist developers; prefer vanilla Love2D first, community libraries as alternatives.

## References

| Reference | When to read it |
|---|---|
| [`references/shaders.md`](references/shaders.md) | Full shader pipeline: uniforms, displacement, masking, reflections |
| [`references/love2d-pattern-mappings.md`](references/love2d-pattern-mappings.md) | Full Lua implementations of all 23 game patterns |
| [`references/ui-patterns.md`](references/ui-patterns.md) | Button drawing, hover detection, click handling, sound effects |

---

## Project Structure

```
my-game/
├── conf.lua        -- window config, identity (runs before love.load)
├── main.lua        -- entry point; all callbacks defined here
└── assets/
```

**`conf.lua`** — configure the window and game identity before Love2D initializes:

```lua
function love.conf(t)
    t.identity = "my-game"          -- save directory name
    t.window.title = "My Game"
    t.window.width = 800
    t.window.height = 600
    t.window.resizable = false
end
```

**`main.lua`** — define the standard callbacks:

```lua
function love.load()
    -- one-time setup: load assets, initialize state
end

function love.update(dt)
    -- game logic; dt is seconds since last frame
end

function love.draw()
    -- rendering only; no state mutation here
end
```

**Callback lifecycle order** (per frame):

1. Event processing — `love.keypressed`, `love.keyreleased`, `love.mousepressed`, `love.mousereleased`, `love.mousemoved` fire here, before update
2. `love.update(dt)` — game logic, physics, timers
3. `love.draw()` — all rendering

`love.run` owns the main loop — you can override it for custom loop behavior (fixed timestep, etc.), but rarely need to.

---

## Love2D Idioms

### Graphics Stack

Use `love.graphics.push()` / `love.graphics.pop()` to isolate transforms. Transforms applied inside a push/pop block do not bleed out.

```lua
function love.draw()
    love.graphics.push()
        love.graphics.translate(player.x, player.y)
        love.graphics.rotate(player.angle)
        love.graphics.draw(player.sprite, -16, -16)  -- centered
    love.graphics.pop()
end
```

`love.graphics.scale(sx, sy)` scales from the current origin. Chain `translate` → `rotate` → `scale` in that order for predictable results.

### Pixel Art

Set the default filter before loading any images:

```lua
function love.load()
    love.graphics.setDefaultFilter("nearest", "nearest")
    -- now load sprites; they'll use nearest-neighbor scaling
    player.sprite = love.graphics.newImage("assets/player.png")
end
```

Calling `setDefaultFilter` after images are loaded has no effect on already-loaded images.

### Canvas (Off-Screen Rendering)

```lua
local canvas

function love.load()
    canvas = love.graphics.newCanvas(800, 600)
end

function love.draw()
    love.graphics.setCanvas(canvas)
        love.graphics.clear()
        -- draw scene to canvas
        love.graphics.draw(background)
    love.graphics.setCanvas()  -- restore to screen

    -- draw canvas to screen (apply post-processing shader here)
    love.graphics.draw(canvas, 0, 0)
end
```

### Color Management

`love.graphics.setColor(r, g, b, a)` affects everything drawn after it. Values are 0–1. **Always reset to white after drawing colored elements** — forgetting this is the most common Love2D bug.

```lua
-- Draw a red health bar, then reset
love.graphics.setColor(1, 0, 0, 1)
love.graphics.rectangle("fill", 10, 10, hp_width, 20)
love.graphics.setColor(1, 1, 1, 1)  -- reset; sprites draw tinted otherwise
love.graphics.draw(sprite, x, y)
```

### Drawing Primitives

```lua
love.graphics.draw(image, x, y)                    -- image at position
love.graphics.draw(image, x, y, r, sx, sy, ox, oy) -- with rotation, scale, origin
love.graphics.rectangle("fill", x, y, w, h)        -- filled rect
love.graphics.rectangle("line", x, y, w, h)        -- outline rect
love.graphics.print("text", x, y)                  -- text at position
love.graphics.printf("text", x, y, limit, "center") -- wrapped/aligned text
```

---

## Shader Basics

For the full shader pipeline (uniforms, displacement, masking, reflections), see `references/shaders.md`.

**Loading** (inside `love.load` — shaders require an active graphics context):

```lua
local shader

function love.load()
    shader = love.graphics.newShader("shaders/effect.glsl")
    -- or inline:
    shader = love.graphics.newShader([[
        vec4 effect(vec4 color, Image tex, vec2 uv, vec2 screen) {
            return Texel(tex, uv) * color;
        }
    ]])
end
```

**Applying:**

```lua
love.graphics.setShader(shader)   -- enable
love.graphics.draw(image, 0, 0)
love.graphics.setShader()         -- reset to default
```

**Sending uniforms:**

```lua
-- Check before sending to avoid errors on unused/optimized-out uniforms
if shader:hasUniform("time") then
    shader:send("time", love.timer.getTime())
end
```

**Love2D GLSL flavor** — two differences from standard GLSL:
- Use `Image` instead of `sampler2D` for texture uniforms
- Use `Texel(tex, uv)` instead of `texture2D(tex, uv)` for sampling

---

## Pattern Mapping (Quick Reference)

**This skill takes precedence over game-patterns for Love2D implementation.** For full Lua implementations, see `references/love2d-pattern-mappings.md`.

| Pattern | Love2D Approach | Community Alternative |
|---|---|---|
| **Observer** | Callback tables; custom event system | — |
| **Singleton** | Module return value (`require` caches modules) | — |
| **State** | Module-per-state with a state manager table | hump.gamestate |
| **Command** | Tables with `execute`/`undo` functions | — |
| **Factory** | Constructor functions returning configured tables | — |
| **Strategy** | Swappable function or table on entity field | — |
| **Decorator** | Wrapper table delegating to inner via `__index` | — |
| **Service Locator** | Module-level table with `get`/`set` for swappable services | — |
| **Event Queue** | Array buffer, drain in `love.update` | — |
| **Component** | Tables with domain-specific data, updated by system functions | — |
| **Prototype** | Deep copy via recursive table clone, or metatables | — |
| **Flyweight** | Shared data tables referenced by multiple entity instances | — |
| **Object Pool** | Pre-allocated array, active/inactive flags | — |
| **Double Buffer** | `love.graphics.Canvas` (draw to canvas, present) | — |
| **Game Loop** | Built-in (`love.update`, `love.draw`) | — |
| **Update Method** | Each entity table has an `update(dt)` method | — |
| **Spatial Partition** | Manual grid or quadtree | bump.lua (AABB) |
| **Dirty Flag** | Boolean flag on table, recompute on access when dirty | — |
| **Data Locality** | Array-of-tables with homogeneous structure, iterate sequentially | — |
| **Bytecode** | Lua itself (`load`/`loadstring` for runtime code) | — |
| **Subclass Sandbox** | Base table with methods; "subclass" tables set it as `__index` | — |
| **Type Object** | Shared "type" table referenced by instances via metatable `__index` | — |
| **Input** | `love.keypressed`/`love.keyreleased`/`love.mouse*` callbacks | — |

---

## Common Pitfalls

**Forgetting to reset color.** After `love.graphics.setColor(r, g, b, a)`, everything drawn afterward is tinted. Always call `love.graphics.setColor(1, 1, 1, 1)` after drawing colored elements.

**Drawing outside push/pop.** Transforms applied without a matching `pop()` bleed into subsequent draw calls. Wrap every entity's draw in `push()`/`pop()`.

**Loading resources in `love.draw`.** `love.graphics.newImage`, `love.graphics.newFont`, etc. create new GPU objects every frame if called in `love.draw`. Load once in `love.load`, store in variables.

**Calling `setDefaultFilter` after loading images.** The filter must be set before any `love.graphics.newImage` calls. Put it as the first line of `love.load`.

**Not using `dt` in `love.update`.** Movement like `x = x + speed` is frame-rate-dependent. Always multiply by `dt`: `x = x + speed * dt`.
