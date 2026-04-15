---
name: godot-shader
description: You MUST consult this skill when writing or reviewing `.gdshader` files, GDSL shader code, visual effects, lighting models, or post-processing in Godot. Also trigger on Shadertoy porting, vertex displacement, procedural shapes in shaders, screen-space effects, normal maps, transparency sorting, ray marching, or particle shader logic. NOT for GDScript game logic, scene architecture, or node patterns (see godot). NOT for C# or visual shaders.
---

# Godot 4.x Shader Development

Godot 4.x (baseline: 4.6) GDSL shaders. Three shader types: `spatial` (3D), `canvas_item` (2D/UI), `particles` (GPU particles). This skill is for a hobbyist developer; prefer built-in variables and render modes over custom implementations where they exist.

## References

| Reference | When to read it |
|---|---|
| [`references/gdsl-reference.md`](references/gdsl-reference.md) | Full built-in variable tables, all render modes, uniform hints, varyings, ShaderInclude, particle lifecycle |
| [`references/lighting.md`](references/lighting.md) | Lambertian, Blinn-Phong, Fresnel, anisotropic, hemispheric, normal maps — complete implementations |
| [`references/procedural-and-vertex.md`](references/procedural-and-vertex.md) | SDF shapes, procedural animation, vertex displacement, 2D/3D rotations, quaternions |
| [`references/vfx-and-postprocessing.md`](references/vfx-and-postprocessing.md) | Post-processing setup, Shadertoy porting, transparency/depth, ray marching, stencil buffer |

---

## Shader Types

| Type | Processor Functions | Use For |
|---|---|---|
| `spatial` | `vertex()`, `fragment()`, `light()` | 3D meshes — `MeshInstance3D`, terrain, particles mesh |
| `canvas_item` | `vertex()`, `fragment()`, `light()` | 2D sprites, UI, `TextureRect`, `Sprite2D`, post-processing |
| `particles` | `start()`, `process()` | GPU particle simulation — `GPUParticles2D` / `GPUParticles3D` only |

**`light()` note:** Defining `light()` overrides Godot's entire lighting pipeline. You must compute diffuse, specular, and any rim/fresnel manually. Built-in `fragment()` outputs like `RIM` and `RIM_TINT` are silently ignored when `light()` is defined.

**Particles note:** `start()` runs once on spawn; `process()` runs every frame. `TRANSFORM`, `COLOR`, `CUSTOM`, and `USERDATA1–6` persist across frames — particle state accumulates naturally.

---

## GDSL Essentials

Most-used built-ins across all shader types. For the full tables, see `gdsl-reference.md`.

### Spatial — `fragment()` outputs (write to these)

| Variable | Type | Description |
|---|---|---|
| `ALBEDO` | `vec3` | Base color (linear space). Never assign gamma-encoded values. |
| `ALPHA` | `float` | Transparency [0,1]. Writing this triggers the transparent pipeline. |
| `EMISSION` | `vec3` | Emissive color (additive, unaffected by lighting) |
| `METALLIC` | `float` | Metallic [0,1] |
| `ROUGHNESS` | `float` | Roughness [0,1] |
| `NORMAL_MAP` | `vec3` | Assign raw `[0,1]` texture sample — Godot remaps to `[-1,1]` internally. Do NOT remap first. |
| `NORMAL` | `vec3` | Override surface normal directly (view space) |

### Spatial — inputs available in `fragment()`

| Variable | Type | Description |
|---|---|---|
| `UV` | `vec2` | Primary texture coordinates |
| `UV2` | `vec2` | Secondary texture coordinates |
| `COLOR` | `vec4` | Vertex color (from `vertex()` or mesh data) |
| `NORMAL` | `vec3` | Surface normal (view space) |
| `VERTEX` | `vec3` | Fragment position (view space) |
| `VIEW` | `vec3` | Normalized fragment→camera direction (view space) |
| `FRAGCOORD` | `vec4` | Pixel position; `.xy` = screen coords, `.z` = depth [0,1] |
| `SCREEN_UV` | `vec2` | Normalized screen UV for this pixel |
| `TIME` | `float` | Seconds since engine start (resets at 3600s) |

### Spatial — `vertex()` key built-ins

| Variable | Type | Description |
|---|---|---|
| `VERTEX` | `vec3` | Position in model space (write to displace geometry) |
| `NORMAL` | `vec3` | Normal in model space (update after displacing VERTEX) |
| `UV` | `vec2` | Primary UV (writable — modify to scroll/transform) |

### Canvas Item — `fragment()` key built-ins

| Variable | Type | Description |
|---|---|---|
| `COLOR` | `vec4` | Output color (read vertex color, write final pixel color) |
| `TEXTURE` | `sampler2D` | Main sprite/rect texture |
| `TEXTURE_PIXEL_SIZE` | `vec2` | `1.0 / texture_size` |
| `SCREEN_UV` | `vec2` | Normalized screen UV |
| `SCREEN_PIXEL_SIZE` | `vec2` | `vec2(1/width, 1/height)` of screen |

---

## Coordinate Spaces

```
Object space → [MODEL_MATRIX] → World space → [VIEW_MATRIX] → View space → [PROJECTION_MATRIX] → Clip space → [÷W] → NDC → Screen
```

| Space | Where you see it | Notes |
|---|---|---|
| **Object/Model** | `vertex()`: VERTEX, NORMAL, TANGENT | Default in `vertex()` unless `world_vertex_coords` render mode |
| **World** | `MODEL_MATRIX * vec4(VERTEX, 1.0)` | Use W=1 for positions, W=0 for directions |
| **View** | `fragment()`: VERTEX, NORMAL, TANGENT, VIEW | After auto-transform; camera is at origin |
| **Clip** | Write to `POSITION` in `vertex()` | Overrides auto-projection |
| **Screen** | `FRAGCOORD.xy`, `SCREEN_UV` | Pixel coords or normalized [0,1] |

**Key rule:** `light()` receives NORMAL in **view space**. To get world-space normal: `(INV_VIEW_MATRIX * vec4(NORMAL, 0.0)).xyz`

**Matrix multiplication order:** Always `MATRIX * vector`, never `vector * MATRIX`. These produce different results for non-symmetric matrices.

---

## Example Shaders

### 1. Spatial — Lambert Diffuse + Blinn-Phong Specular

Custom lighting in `light()`. Reads albedo texture, computes diffuse and specular manually.

```glsl
shader_type spatial;
render_mode ambient_light_disabled;  // isolate custom lighting

uniform sampler2D _MainTex : source_color;
uniform float _Shininess : hint_range(1.0, 256.0, 1.0) = 64.0;

// Helper functions — place in a .gdshaderinc for reuse
float lambert(vec3 n, vec3 l, float attenuation) {
    return max(0.0, dot(n, l)) * attenuation;
}

float blinn_phong(vec3 n, vec3 l, vec3 v, float shininess) {
    vec3 h = normalize(l + v);                       // halfway vector
    float s = pow(max(0.0, dot(n, h)), shininess);
    s *= float(dot(n, l) > 0.0);                    // no specular in shadow
    return s;
}

void fragment() {
    ALBEDO = texture(_MainTex, UV).rgb;
    ROUGHNESS = 0.5;
}

void light() {
    // light() runs once per light per fragment, after fragment()
    // DIFFUSE_LIGHT and SPECULAR_LIGHT accumulate across lights — use +=
    float d = lambert(NORMAL, LIGHT, ATTENUATION);
    float s = blinn_phong(NORMAL, LIGHT, VIEW, _Shininess);

    DIFFUSE_LIGHT  += vec3(d) * ALBEDO;  // ALBEDO is readable in light()
    SPECULAR_LIGHT += vec3(s);
}
```

### 2. Canvas Item — Scrolling UV Distortion

2D post-processing effect: reads the screen texture and applies a time-based UV distortion.

```glsl
shader_type canvas_item;

// hint_screen_texture: reads the rendered framebuffer
// repeat_disable: clamp to [0,1] — no tiling artifacts at screen edges
// filter_linear: smooth sampling for distortion effects
uniform sampler2D _ScreenTexture : hint_screen_texture, repeat_disable, filter_linear;
uniform float _DistortStrength : hint_range(0.0, 0.05, 0.001) = 0.01;
uniform float _ScrollSpeed : hint_range(0.0, 2.0, 0.1) = 0.5;

void fragment() {
    // Animate distortion offset with TIME
    vec2 offset = vec2(
        sin(SCREEN_UV.y * 20.0 + TIME * _ScrollSpeed) * _DistortStrength,
        cos(SCREEN_UV.x * 20.0 + TIME * _ScrollSpeed) * _DistortStrength
    );

    // Sample screen at distorted UV
    vec4 screen_color = texture(_ScreenTexture, SCREEN_UV + offset);
    COLOR = screen_color;
}
```

**Setup:** Attach to a `ColorRect` (Anchor: Full Rect) inside a `CanvasLayer`. Effect only appears at runtime, not in the editor viewport.

### 3. Particles — Gravity + Fade Out

Minimal particle shader: spawns particles at emitter position, applies gravity, fades alpha over lifetime.

```glsl
shader_type particles;

void start() {
    // RESTART_* flags are true when particle first spawns
    if (RESTART_POSITION) {
        // Place particle at emitter world position
        TRANSFORM[3].xyz = EMISSION_TRANSFORM[3].xyz;
    }
    if (RESTART_VELOCITY) {
        // Spread particles in a cone using golden angle
        float angle = float(NUMBER) * 2.399963;
        VELOCITY = vec3(cos(angle) * 0.5, 2.0, sin(angle) * 0.5);
    }
    if (RESTART_CUSTOM) {
        CUSTOM.y = 0.0;  // initialize lifetime phase (0=just spawned, 1=dead)
    }
}

void process() {
    // Manually track lifetime phase
    // Guard against LIFETIME == 0 to avoid NaN
    CUSTOM.y = clamp(CUSTOM.y + DELTA / max(LIFETIME, 1e-6), 0.0, 1.0);
    float age = CUSTOM.y;  // CUSTOM persists across frames

    // Apply gravity and integrate position
    VELOCITY.y -= 9.8 * DELTA;
    TRANSFORM[3].xyz += VELOCITY * DELTA;  // TRANSFORM persists — position accumulates

    // Fade alpha over lifetime
    COLOR.a = 1.0 - age;

    // Deactivate when lifetime expires
    if (age >= 1.0) {
        ACTIVE = false;
    }
}
```

---

## Common Patterns

### Read the screen texture (post-processing / refraction)

```glsl
// Declare at top of shader
uniform sampler2D _ScreenTexture : hint_screen_texture, repeat_disable, filter_linear;

void fragment() {
    vec4 screen = texture(_ScreenTexture, SCREEN_UV);
    // For refraction: offset SCREEN_UV by NORMAL.xy before sampling
    // Caveat: only captures objects rendered before this draw call
}
```

### Pass data from `vertex()` to `fragment()`

```glsl
// Declare outside all functions
varying vec3 vertex_world;  // suffix _ws = world space convention
varying vec2 custom_uv;

void vertex() {
    vertex_world = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
    custom_uv = UV * 2.0 - 1.0;  // remap to [-1,1]
}

void fragment() {
    // vertex_world and custom_uv are available here, interpolated across the triangle
    // Restriction: varyings cannot be assigned in custom functions or in light()
}
```

### Make a property editable in the Inspector

```glsl
// Scalar with slider
uniform float _Speed : hint_range(0.0, 10.0, 0.1) = 1.0;

// Color picker (applies sRGB→linear conversion automatically)
uniform vec4 _Tint : source_color = vec4(1.0);

// Texture with normal map hint (triggers correct reimport in editor)
uniform sampler2D _NormalMap : hint_normal;

// Set from GDScript at runtime:
// material.set_shader_parameter("_Speed", 2.5)
```

### Sample a texture in `vertex()` (heightmap displacement)

```glsl
uniform sampler2D _HeightMap;
uniform float _HeightScale = 1.0;

void vertex() {
    // Must use textureLod — implicit derivatives are unavailable in vertex()
    float height = textureLod(_HeightMap, UV, 0.0).r;
    VERTEX.y += height * _HeightScale;
    // Update NORMAL after displacing VERTEX or lighting will be wrong
}
```

---

## Common Pitfalls

**Forgetting `render_mode ambient_light_disabled` when isolating custom lighting.** If you implement all lighting in `light()` but omit `render_mode ambient_light_disabled`, Godot's ambient and environment lighting still accumulates on top of your result. Add `render_mode ambient_light_disabled` to isolate custom lighting, or accept the engine ambient as a base layer. Note: `render_mode unshaded` is different — it disables the entire lighting pipeline (no `light()` runs at all), which is for fully self-lit materials like particles or UI overlays.

**Writing to `ALBEDO` inside `light()`.** `ALBEDO` is read-only in `light()` — it reflects the value set in `fragment()`. Write diffuse contributions to `DIFFUSE_LIGHT` and specular to `SPECULAR_LIGHT`. Using `=` instead of `+=` on these also breaks multi-light scenes — always accumulate.

**Wrong matrix multiplication order.** GLSL uses column-vector convention: `MATRIX * vector`, not `vector * MATRIX`. These are transposes of each other and produce incorrect results for non-symmetric matrices. Applies to all transforms: `MODEL_MATRIX * vec4(VERTEX, 1.0)`, `EULER_ZXY * VERTEX`, etc.

**Assigning remapped values to `NORMAL_MAP`.** `NORMAL_MAP` expects a raw `[0,1]` texture sample — Godot remaps to `[-1,1]` internally. If you remap first (`* 2.0 - 1.0`) and then assign, the normal will be double-remapped and incorrect. Assign the raw `texture(...).rgb` directly.

**Using `texture()` in `vertex()`.** Implicit mip-level derivatives are unavailable in `vertex()`, so `texture()` produces undefined results. Always use `textureLod(tex, uv, 0.0)` for deterministic sampling in `vertex()`.

**`pow(negative, float)` is undefined in GLSL.** This surfaces in SDF shapes and lighting. For SDF: use `abs()` before `pow()` — `pow(abs(u), 4.0)`. For lighting: guard with `max(value, 0.0)` before any `pow()` call.

**`hint_screen_texture` feedback loops.** The screen texture only captures objects rendered before this draw call. Sampling it while rendering to the same viewport creates undefined behavior. For transparent objects that need screen sampling, add `render_mode depth_draw_always` to ensure correct draw ordering.
