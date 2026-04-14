# Love2D Shaders

Full shader pipeline for Love2D 11.x. All code in Lua (game side) and GLSL (shader side).

## Love2D GLSL Flavor

Two differences from standard GLSL:
- **`Image`** instead of `sampler2D` for texture uniforms
- **`Texel(tex, uv)`** instead of `texture2D(tex, uv)` for sampling

The entry point is `effect()` (not `main()`):

```glsl
vec4 effect(vec4 color, Image tex, vec2 texture_coords, vec2 screen_coords) {
    return Texel(tex, texture_coords) * color;
}
```

Arguments:
- `color` — the current draw color set by `love.graphics.setColor`
- `tex` — the texture being drawn
- `texture_coords` — UV coordinates (0–1)
- `screen_coords` — pixel position on screen

---

## Step 1: Rendering a Tile Without a Shader

Baseline — draw a tile image at a position:

```lua
-- main.lua
local tile

function love.load()
    love.graphics.setDefaultFilter("nearest", "nearest")
    tile = love.graphics.newImage("assets/tile.png")
end

function love.draw()
    love.graphics.draw(tile, 100, 100)
end
```

---

## Step 2: Applying the Default Effect Shader

The default shader passes pixels through unchanged. Applying it explicitly confirms the pipeline works:

```lua
local tile
local shader

function love.load()
    love.graphics.setDefaultFilter("nearest", "nearest")
    tile = love.graphics.newImage("assets/tile.png")

    shader = love.graphics.newShader([[
        vec4 effect(vec4 color, Image tex, vec2 uv, vec2 screen) {
            return Texel(tex, uv) * color;
        }
    ]])
end

function love.draw()
    love.graphics.setShader(shader)
    love.graphics.draw(tile, 100, 100)
    love.graphics.setShader()
end
```

---

## Step 3: Passing Uniforms — Time-Based Animation

Track elapsed time in `love.update`, send it to the shader each frame.

```lua
local tile
local shader
local time = 0

function love.load()
    love.graphics.setDefaultFilter("nearest", "nearest")
    tile = love.graphics.newImage("assets/tile.png")

    shader = love.graphics.newShader([[
        uniform float time;

        vec4 effect(vec4 color, Image tex, vec2 uv, vec2 screen) {
            // Pulse brightness using a sine wave
            float pulse = 0.8 + 0.2 * sin(time * 3.0);
            return Texel(tex, uv) * color * pulse;
        }
    ]])
end

function love.update(dt)
    time = time + dt
    if shader:hasUniform("time") then
        shader:send("time", time)
    end
end

function love.draw()
    love.graphics.setShader(shader)
    love.graphics.draw(tile, 100, 100)
    love.graphics.setShader()
end
```

Always guard `shader:send` with `shader:hasUniform` — GLSL optimizes out unused uniforms, and sending to a non-existent uniform throws an error.

---

## Step 4: Displacement Effects

Displacement warps UV coordinates using a noise texture. The noise texture scrolls over time to create a flowing, animated distortion.

**Lua side:**

```lua
local tile
local noise_tex
local shader
local time = 0

function love.load()
    love.graphics.setDefaultFilter("nearest", "nearest")
    tile = love.graphics.newImage("assets/tile.png")
    noise_tex = love.graphics.newImage("assets/simplex_noise.png")
    -- noise texture must wrap (tile seamlessly)
    noise_tex:setWrap("repeat", "repeat")

    shader = love.graphics.newShader("shaders/displacement.glsl")
end

function love.update(dt)
    time = time + dt
    if shader:hasUniform("time") then
        shader:send("time", time)
    end
    if shader:hasUniform("noise_tex") then
        shader:send("noise_tex", noise_tex)
    end
end

function love.draw()
    love.graphics.setShader(shader)
    love.graphics.draw(tile, 100, 100)
    love.graphics.setShader()
end
```

**`shaders/displacement.glsl`:**

```glsl
uniform float time;
uniform Image noise_tex;

// How far the displacement can push UVs (in UV space, 0–1)
const float AMPLITUDE = 0.02;
// How fast the noise scrolls
const float SCROLL_SPEED = 0.1;

vec4 effect(vec4 color, Image tex, vec2 uv, vec2 screen) {
    // Scroll the noise texture over time
    vec2 noise_uv = uv + vec2(time * SCROLL_SPEED, time * SCROLL_SPEED * 0.7);
    vec2 noise_sample = Texel(noise_tex, noise_uv).rg;

    // Remap noise from [0,1] to [-1,1], then scale by amplitude
    vec2 offset = (noise_sample * 2.0 - 1.0) * AMPLITUDE;

    // Sample the tile at the displaced UV
    return Texel(tex, uv + offset) * color;
}
```

**Noise texture:** Use any tileable grayscale or RG noise image (simplex, Perlin). The R and G channels drive X and Y displacement independently.

---

## Step 5: Masking

A mask image restricts the shader effect to specific pixels. Where the mask is white, the effect applies; where it's black, the original pixel shows through.

**Lua side:**

```lua
local tile
local noise_tex
local mask_tex
local shader
local time = 0

function love.load()
    love.graphics.setDefaultFilter("nearest", "nearest")
    tile = love.graphics.newImage("assets/tile.png")
    noise_tex = love.graphics.newImage("assets/simplex_noise.png")
    noise_tex:setWrap("repeat", "repeat")
    mask_tex = love.graphics.newImage("assets/mask.png")  -- white = effect, black = no effect

    shader = love.graphics.newShader("shaders/masked_displacement.glsl")
end

function love.update(dt)
    time = time + dt
    if shader:hasUniform("time") then shader:send("time", time) end
    if shader:hasUniform("noise_tex") then shader:send("noise_tex", noise_tex) end
    if shader:hasUniform("mask_tex") then shader:send("mask_tex", mask_tex) end
end

function love.draw()
    love.graphics.setShader(shader)
    love.graphics.draw(tile, 100, 100)
    love.graphics.setShader()
end
```

**`shaders/masked_displacement.glsl`:**

```glsl
uniform float time;
uniform Image noise_tex;
uniform Image mask_tex;

const float AMPLITUDE = 0.02;
const float SCROLL_SPEED = 0.1;

vec4 effect(vec4 color, Image tex, vec2 uv, vec2 screen) {
    // Sample mask — use red channel as blend weight
    float mask = Texel(mask_tex, uv).r;

    // Compute displaced UV
    vec2 noise_uv = uv + vec2(time * SCROLL_SPEED, time * SCROLL_SPEED * 0.7);
    vec2 noise_sample = Texel(noise_tex, noise_uv).rg;
    vec2 offset = (noise_sample * 2.0 - 1.0) * AMPLITUDE * mask;

    return Texel(tex, uv + offset) * color;
}
```

The mask multiplies the displacement amplitude — fully white pixels get full displacement, black pixels get none, grey pixels get partial.

---

## Step 6: Reflections

Reflections flip the UV vertically (or horizontally) and blend with the original. Combine with displacement for a water-surface effect.

**`shaders/reflection.glsl`:**

```glsl
uniform float time;
uniform Image noise_tex;
uniform float reflection_alpha;  // how opaque the reflection is (0–1)

const float AMPLITUDE = 0.015;
const float SCROLL_SPEED = 0.08;

vec4 effect(vec4 color, Image tex, vec2 uv, vec2 screen) {
    // Original pixel
    vec4 original = Texel(tex, uv) * color;

    // Reflected UV: flip vertically, add displacement
    vec2 noise_uv = uv + vec2(time * SCROLL_SPEED, 0.0);
    vec2 noise_sample = Texel(noise_tex, noise_uv).rg;
    vec2 offset = (noise_sample * 2.0 - 1.0) * AMPLITUDE;

    vec2 reflected_uv = vec2(uv.x + offset.x, 1.0 - uv.y + offset.y);
    vec4 reflection = Texel(tex, reflected_uv) * color;

    // Blend: show reflection only in the lower half of the image
    float blend = step(0.5, uv.y);  // 0 in top half, 1 in bottom half
    return mix(original, reflection, blend * reflection_alpha);
}
```

**Lua side — send the extra uniform:**

```lua
if shader:hasUniform("reflection_alpha") then
    shader:send("reflection_alpha", 0.6)
end
```

---

## Tips

- **Shader compile errors** appear in the Love2D console. Call `love.graphics.newShader` inside a `pcall` during development to catch them gracefully.
- **Multiple textures:** Love2D supports up to 8 texture units. Send additional textures as `uniform Image` and use `Texel()` to sample them.
- **Canvas + shader:** Apply post-processing to a full scene by rendering to a `Canvas`, then drawing the canvas with a shader applied.
- **Performance:** Shaders run on the GPU. Sending uniforms every frame via `shader:send` is cheap; creating new shaders every frame is not.
