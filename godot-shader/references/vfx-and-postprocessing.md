# VFX and Post-Processing Reference

## Post-Processing Setup in Godot

Post-processing in Godot requires a `canvas_item` shader on a full-screen `ColorRect` inside a `CanvasLayer`. The shader reads the rendered frame via `hint_screen_texture`.

**Node structure:**
```
CanvasLayer
└── ColorRect (Anchor: Full Rect, Material: ShaderMaterial)
```

**Critical setup steps:**
1. Set shader type to `canvas_item` (not `spatial` — new shaders default to spatial)
2. Declare the screen texture sampler with `hint_screen_texture`
3. Post-processing effects **only appear at runtime** — not in the editor viewport

**Minimal post-processing scaffold:**
```glsl
shader_type canvas_item;

// hint_screen_texture: reads the rendered framebuffer
// repeat_disable: no tiling outside [0,1] UV range
// filter_nearest: pixel-exact sampling (no smoothing) — use filter_linear for smooth effects
uniform sampler2D _ScreenTexture : hint_screen_texture, repeat_disable, filter_nearest;

void fragment() {
    vec2 screen_uv = SCREEN_UV;
    vec4 screen_color = texture(_ScreenTexture, screen_uv);
    COLOR = screen_color;  // pass-through; modify screen_color before assigning
}
```

**Key built-ins for post-processing:**
- `SCREEN_UV` — normalized [0,1] UV coordinates for the current fragment
- `SCREEN_PIXEL_SIZE` — size of one pixel in UV space (`vec2(1/width, 1/height)`)
- `1.0 / SCREEN_PIXEL_SIZE` — screen resolution in pixels

---

## Color Quantization / Retro Effects (Game Boy)

**Effect:** Convert the full-color render to a limited palette with optional pixelation.

**Algorithm:**
1. Pixelate UVs by snapping to a grid (reduces effective resolution)
2. Convert each pixel to luminance (grayscale)
3. Map luminance to a palette index
4. Look up the palette color from a texture

```glsl
shader_type canvas_item;

uniform sampler2D _Palette : source_color;           // 4-color palette texture (vertical strip)
uniform int _PixelSize : hint_range(1, 10, 1);       // pixel block size; 6 = classic Game Boy look
uniform sampler2D _ScreenTexture : hint_screen_texture, repeat_disable, filter_nearest;

// BT.709 luminance — perceptual brightness of an RGB color
float luma(vec3 c) {
    return max(0.0, dot(c, vec3(0.2126, 0.7152, 0.0722)));
}

// Fetch palette color by index (0=darkest, 3=brightest)
// Palette texture: 4 colors stacked vertically top-to-bottom, brightest at top
vec3 palette_fetch(int i) {
    i = clamp(i, 0, 3);
    float v = 0.125 + 0.25 * float(i);              // center of each 0.25-height band
    return texture(_Palette, vec2(0.5, 1.0 - v)).rgb; // 1.0-v: inverts so idx=3 (brightest) maps to top
}

// Map an RGB color to the nearest palette entry via luminance
vec3 gameboy_color(vec3 color) {
    float t = luma(color);
    t = smoothstep(0.1, 0.9, t);                     // compress extremes for retro contrast
    int idx = int(floor(t * 4.0));
    if (idx == 4) idx = 3;                           // clamp edge case (t == 1.0)
    return palette_fetch(idx);
}

// Snap UVs to pixel-block grid — produces pixelation effect
// screen_uv: normalized UV, screen_pixel: resolution in pixels, pixel_size: block size
vec2 to_pixel(vec2 screen_uv, vec2 screen_pixel, float pixel_size) {
    vec2 px = screen_uv * screen_pixel;
    px = floor(px / pixel_size) * pixel_size + pixel_size; // +pixel_size: samples at block trailing edge (consistent per-block color)
    return clamp(px / screen_pixel, vec2(0.0), vec2(1.0)); // clamp: prevents edge stripe when screen size is not divisible by pixel_size
}

void fragment() {
    float size = max(1.0, float(_PixelSize)); // guard: _PixelSize=0 from GDScript causes division by zero
    vec2 screen_uv = to_pixel(SCREEN_UV, 1.0 / SCREEN_PIXEL_SIZE, size);
    vec4 screen_texture = texture(_ScreenTexture, screen_uv);
    screen_texture.rgb = gameboy_color(screen_texture.rgb);
    COLOR = screen_texture;
}
```

**Palette texture format:** A small image (e.g., 1×4 px) with colors ordered top-to-bottom from brightest to darkest. Import with `filter_nearest` to avoid interpolation between palette entries.

**Gotchas:**
- `_Palette` texture must use **Lossless** import compression and `filter_nearest`. With Godot's default `filter_linear`, palette lookups near band boundaries blend two adjacent colors, producing intermediate hues that destroy the discrete retro look. Set `filter_nearest` in the Import panel before reimporting.
- `_PixelSize` must be ≥ 1 when set from GDScript. Setting it to 0 causes division by zero in `to_pixel()` and the checkerboard calculation, producing a black screen. The `hint_range(1, 10, 1)` prevents this in the inspector but not via `set_shader_parameter`.

**Adding a checkerboard overlay (Shadertoy port):**
```glsl
void fragment() {
    float size = max(1.0, float(_PixelSize)); // guard against 0 from GDScript
    vec2 screen_uv = to_pixel(SCREEN_UV, 1.0 / SCREEN_PIXEL_SIZE, size);
    vec4 screen_texture = texture(_ScreenTexture, screen_uv);
    screen_texture.rgb = gameboy_color(screen_texture.rgb);

    // Checkerboard: alternates 0/1 per pixel-block cell
    vec2 pos = floor((SCREEN_UV / SCREEN_PIXEL_SIZE) / size);
    float pattern_mask = mod(pos.x + mod(pos.y, 2.0), 2.0);
    screen_texture.rgb *= pattern_mask;

    COLOR = screen_texture;
}
```

---

## Shadertoy Porting Guide

### Translation Table

| Shadertoy | Godot GDSL | Notes |
|---|---|---|
| `mainImage(out vec4 fragColor, in vec2 fragCoord)` | `void fragment()` | Entry point |
| `fragColor` | `COLOR` (canvas_item) / `ALBEDO` + `ALPHA` (spatial) | Output color |
| `fragCoord` | `FRAGCOORD.xy` | Pixel-space coordinates (not normalized) |
| `fragCoord / iResolution.xy` | `SCREEN_UV` | Normalized [0,1] UV |
| `iResolution.xy` | `1.0 / SCREEN_PIXEL_SIZE` | Screen size in pixels |
| `iResolution.z` | Not available | Pixel aspect ratio — hardcode 1.0 |
| `iTime` | `TIME` | Seconds since start (float) |
| `iTimeDelta` | Not built-in | Use `TIME` and compute delta manually |
| `iFrame` | Not built-in | No frame counter built-in |
| `iMouse` | Custom `uniform vec2 _Mouse` | No built-in; pass from GDScript |
| `iChannel0..3` | `uniform sampler2D _ChannelN` | Declare as regular uniforms |
| `texture(sampler, uv)` | `texture(sampler, uv)` | Same function, same syntax |
| `texelFetch(s, ivec2, 0)` | `texelFetch(s, ivec2, 0)` | Same |
| `gl_FragCoord` | `FRAGCOORD` | Built-in vec4; `.xy` = pixel coords |

### Coordinate System Differences

**Y-axis:** Shadertoy uses Y-up (origin at bottom-left). Godot uses Y-down (origin at top-left).

```glsl
// Shadertoy: fragCoord.y = 0 at bottom
// Godot: FRAGCOORD.y = 0 at top

// To flip Y when porting:
vec2 uv = SCREEN_UV;
uv.y = 1.0 - uv.y;  // flip to match Shadertoy Y-up convention
```

**Pixel coordinates:**
```glsl
// Shadertoy
vec2 uv = fragCoord / iResolution.xy;

// Godot equivalent
vec2 uv = SCREEN_UV;
// OR: FRAGCOORD.xy * SCREEN_PIXEL_SIZE  (same result)
```

### Minimal Shadertoy Port Template

```glsl
shader_type canvas_item;

uniform sampler2D _ScreenTexture : hint_screen_texture, repeat_disable, filter_linear;

// Shadertoy's mainImage becomes fragment()
// fragColor → COLOR
// fragCoord → FRAGCOORD.xy
// iResolution.xy → 1.0 / SCREEN_PIXEL_SIZE
// iTime → TIME

void fragment() {
    vec2 fragCoord = FRAGCOORD.xy;
    vec2 iResolution = 1.0 / SCREEN_PIXEL_SIZE;

    // --- paste Shadertoy logic below ---
    vec2 uv = fragCoord / iResolution;
    // uv.y = 1.0 - uv.y;  // uncomment if effect appears upside-down

    vec4 fragColor = vec4(uv, 0.0, 1.0); // replace with ported logic
    // --- end Shadertoy logic ---

    COLOR = fragColor;
}
```

### Passing Mouse Position from GDScript

```gdscript
# In a script attached to the ColorRect or a parent node
@export var shader_material: ShaderMaterial

func _process(_delta: float) -> void:
    var mouse_pos: Vector2 = get_viewport().get_mouse_position()
    shader_material.set_shader_parameter("_Mouse", mouse_pos)
```

```glsl
uniform vec2 _Mouse;  // set from GDScript each frame
```

---

## Transparency and Depth

### Alpha Blending Setup

For transparent `spatial` shaders, render modes control blending and depth behavior:

```glsl
shader_type spatial;
render_mode cull_disabled;        // render both faces (vegetation, cards)
render_mode depth_prepass_alpha;  // write depth before blending — fixes depth sorting on transparent meshes
```

**`depth_prepass_alpha` is critical for vegetation and foliage.** Without it, transparent meshes sort incorrectly when overlapping.

### Reading the Depth Buffer

```glsl
shader_type spatial;

uniform sampler2D _DepthTexture : hint_depth_texture, repeat_disable, filter_nearest;

void fragment() {
    float depth = texture(_DepthTexture, SCREEN_UV).r;
    // depth is in [0,1] NDC space — linearize for world-space distance
}
```

### Distance-Based Fade (Camera Proximity Transparency)

Useful for third-person games: objects near the camera become transparent.

```glsl
shader_type spatial;
render_mode diffuse_toon, cull_disabled, depth_prepass_alpha, alpha_to_coverage;

uniform sampler2D _MainTexRGB : source_color;
uniform sampler2D _MainTexA : hint_default_white;  // alpha mask — no sRGB conversion; source_color would darken the mask
uniform float _Distance : hint_range(0.1, 10.0, 0.1);  // fade radius; minimum 0.1 avoids division by zero
uniform vec3 _EdgeColor : source_color;

varying vec3 vertex_ws;  // world-space vertex position, interpolated to fragment

void vertex() {
    // Transform local vertex to world space
    vertex_ws = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

// Pseudo-random noise from UV — breaks hard transparency edges
float hash21(vec2 uv) {
    return fract(sin(dot(uv, vec2(12.9898, 78.233))) * 43758.5453);
}

void fragment() {
    vec3 albedo = texture(_MainTexRGB, UV).rgb;
    float alpha = texture(_MainTexA, UV).r;

    // Normalized distance from vertex to camera [0,1]
    float distance_color = clamp(distance(vertex_ws, CAMERA_POSITION_WORLD) / _Distance, 0.0, 1.0);

    // Square for smooth near-camera falloff; linear feels too abrupt
    float focus = pow(distance_color, 2.0);

    // Dithered noise softens the transparency boundary
    float noise = hash21(SCREEN_UV);
    noise = mix(noise, 1.0, focus) * focus;

    // Blend edge color into albedo near camera
    albedo = mix(_EdgeColor, albedo, focus);

    ALBEDO = albedo;
    ALPHA = alpha * noise;
    ALPHA_ANTIALIASING_EDGE = 0.5;  // soften cutout edges (reduces jagged alpha borders)
}
```

**Gotchas:**
- `ALPHA_ANTIALIASING_EDGE` requires both `alpha_to_coverage` in `render_mode` AND **Lossless** texture compression (not VRAM Compressed). Without `alpha_to_coverage`, the assignment is silently ignored.
- `depth_prepass_alpha` renders the object twice: once for depth, once for color — slight performance cost
- `CAMERA_POSITION_WORLD` is available in `fragment()` for spatial shaders
- `_Distance = 0` causes division by zero (`Inf`/`NaN`) — the `hint_range` minimum of `0.1` prevents this in the inspector, but guard the division if setting the value from code

---

## Ray Marching with 3D Textures (Volumetric Cloud)

**Setup:** A `BoxMesh` with a `spatial` + `unshaded` shader. The box defines the volume boundary. A `Texture3D` stores density data.

**Importing a 3D texture:** In the Import panel, set "Import As" → `Texture3D`, configure slice counts (e.g., 8×8 for a 64-slice volume), then Reimport.

```glsl
shader_type spatial;
render_mode unshaded;  // manual lighting — Godot's light pipeline is bypassed

uniform sampler3D _BaseTex : source_color, repeat_disable;  // volumetric density texture
uniform vec3 _ColorLight : source_color;    // color for low-density / lit regions
uniform vec3 _ColorShadow : source_color;   // color for high-density / shadowed regions

// Quality/cost tradeoffs: reduce NUM_STEPS for performance, increase for quality
#define NUM_STEPS 128        // view ray samples — higher = smoother volume
#define STEP_SIZE 0.01       // world-space distance per step
#define NUM_LIGHT_STEPS 6    // secondary light ray samples per view step
#define LIGHT_STEP_SIZE 0.05 // world-space distance per light step

// Returns vec3(final_light, transmission, transmittance)
// ray_origin: world-space start of ray (on box surface)
// ray_direction: normalized view direction
// offset: aligns volume sampling to box center
// light_direction: normalized direction toward light source
// darkness: minimum shadow brightness (0=fully dark, 1=no shadows)
// transmittance: initial light survival factor (start at 1.0)
// light_absorb: absorption coefficient (higher = denser medium)
vec3 ray_marching(
    vec3 ray_origin,
    vec3 ray_direction,
    vec3 offset,
    vec3 light_direction,
    float darkness,
    float transmittance,
    float light_absorb
) {
    float density = 0.0;
    float transmission = 0.0;
    float final_light = 0.0;

    for (int i = 0; i < NUM_STEPS; i++) {
        ray_origin += ray_direction * STEP_SIZE;
        vec3 sampled_position = ray_origin + offset;
        // Production: add bounds check here — see UVW bounds gotcha below

        float sample_density = texture(_BaseTex, sampled_position).r;
        density += sample_density;

        // Secondary ray toward light — estimates self-shadowing
        float light_accumulation = 0.0;
        vec3 light_ray_origin = sampled_position;
        for (int j = 0; j < NUM_LIGHT_STEPS; j++) {
            light_ray_origin += light_direction * LIGHT_STEP_SIZE;
            // Production: add bounds check here — see UVW bounds gotcha below
            light_accumulation += texture(_BaseTex, light_ray_origin).r;
        }

        // Exponential falloff: more density along light ray = less light reaches this point
        float light_transmission = exp(-light_accumulation);
        float shadow = darkness + light_transmission * (1.0 - darkness);

        // Accumulate lighting contribution weighted by current transmittance
        final_light += sample_density * transmittance * shadow;

        // Reduce transmittance as ray passes through denser regions
        transmittance *= exp(-sample_density * light_absorb);
    }

    // Overall opacity from total accumulated density
    transmission = exp(-density);

    return vec3(final_light, transmission, transmittance);
}

void fragment() {
    // World-space ray origin: transform view-space vertex to world space
    vec3 ray_origin_ws = (INV_VIEW_MATRIX * vec4(VERTEX.xyz, 1.0)).xyz;

    // Ray direction: from camera toward this fragment
    vec3 ray_direction = normalize(ray_origin_ws - CAMERA_POSITION_WORLD);

    // World-space position of the box pivot — anchors volume to the mesh
    vec4 transform = MODEL_MATRIX * vec4(0.0, 0.0, 0.0, 1.0);

    // Offset centers the volume sampling within the [0,1] UVW space of the 3D texture
    vec3 offset = (vec4(0.5, 0.5, 0.5, 0.0) - transform).xyz;

    const vec3 light_direction = vec3(0.0, 1.0, 0.0); // light from above
    const float darkness = 0.19;      // minimum shadow brightness
    const float transmittance = 1.0;  // full light at ray start
    const float light_absorb = 1.5;   // absorption rate

    vec3 render = ray_marching(
        ray_origin_ws, ray_direction, offset,
        light_direction, darkness, transmittance, light_absorb
    );

    // render.x = accumulated lighting (drives color gradient)
    // render.y = transmission (inverted = opacity)
    float gradient = clamp(render.x, 0.0, 1.0);
    vec3 albedo = mix(_ColorShadow, _ColorLight, gradient);
    float alpha = 1.0 - render.y;

    ALBEDO = albedo;
    ALPHA = alpha;
}
```

**Gotchas:**
- `sampler3D` requires the texture to be imported as `Texture3D` — it will not work with a `Texture2D` or `Texture2DArray`
- `render_mode unshaded` is required — the volume computes its own lighting; Godot's light pipeline would interfere
- **Coverage constraint:** `NUM_STEPS × STEP_SIZE` must exceed the **space diagonal** of the BoxMesh in world space (not just its side length). A unit cube's space diagonal is √3 ≈ 1.73 units, which already exceeds the default 128 × 0.01 = 1.28 units — so even a unit cube will show a hard cutoff at oblique viewing angles. A safe minimum for a unit cube: `NUM_STEPS = 200` with `STEP_SIZE = 0.01`, or `NUM_STEPS = 128` with `STEP_SIZE = 0.014`. Scale proportionally for larger boxes.
- **Camera inside volume:** Default front-face culling stops generating fragments when the camera enters the box, making the cloud disappear. Add `render_mode cull_front;` to render back faces instead (or `cull_disabled` for both). Note: with `cull_front`, `VERTEX` in `fragment()` is the back-face position and the ray direction points away from the camera — this is correct for marching into the volume, but a more robust approach is `cull_disabled` with a ray-box intersection to find the true entry point.
- **UVW bounds:** Both the view ray and light ray sample `_BaseTex` without bounds checking. With `repeat_disable`, samples outside `[0,1]` UVW return zero, causing incorrect shadowing at volume edges. Add early-exit checks to both loops:
  - Outer loop (view ray): `if (any(lessThan(sampled_position, vec3(0.0))) || any(greaterThan(sampled_position, vec3(1.0)))) break;`
  - Inner loop (light ray): `if (any(lessThan(light_ray_origin, vec3(0.0))) || any(greaterThan(light_ray_origin, vec3(1.0)))) break;`
- **Non-uniform scale:** The offset calculation assumes a unit-scale BoxMesh. Non-uniform scaling (e.g., 2×1×0.5) misaligns the volume. Keep the BoxMesh at uniform scale, or incorporate scale into the offset and step size.
- High `NUM_STEPS` values are expensive. Start at 32 for iteration, raise to 128+ for final quality
- The box mesh must have its material applied to the `MeshInstance3D` node, not a surface override

---

## Stencil Buffer / Masking Effects

> **Note:** Stencil buffer support in Godot 4.x is experimental. The syntax shown here (`stencil_mode write, 1;`) is sourced from the Godot Shaders Bible and community usage, but the official documentation marks this feature as "use at your own risk." Verify against your Godot version's release notes.

Godot exposes the stencil buffer via `stencil_mode` in `spatial` shaders. The workflow is always two-pass: a **write** shader marks pixels, a **read** shader renders only where marked.

### Stencil Write Shader (mask geometry)

```glsl
shader_type spatial;
render_mode unshaded;
stencil_mode write, 1;  // write value 1 to stencil buffer for every fragment

// No fragment() needed — the stencil write happens automatically.
// Optionally add texture-based discard to shape the mask:
uniform sampler2D _MaskTex : source_color;

void fragment() {
    vec4 mask = texture(_MaskTex, UV);
    if (mask.r < 1.0) discard;  // only fully white texels write to stencil
}
```

### Stencil Read Shader (render inside mask)

```glsl
shader_type spatial;
render_mode unshaded, depth_draw_never, depth_test_disabled;
// depth_draw_never: this object doesn't write to depth buffer
// depth_test_disabled: renders regardless of depth (always on top of depth geometry)
stencil_mode read, compare_equal, 1;  // only render where stencil == 1

uniform sampler2D _BaseColor : source_color, repeat_disable;

void fragment() {
    vec3 albedo = texture(_BaseColor, UV).rgb;
    ALBEDO = albedo;
}
```

### Stencil Comparison Modes

| Mode | Fragment passes when |
|---|---|
| `compare_equal` | stencil == reference |
| `compare_not_equal` | stencil != reference |
| `compare_always` | always (ignores stencil) |
| `compare_greater` | stencil > reference |
| `compare_greater_or_equal` | stencil >= reference |
| `compare_less` | stencil < reference |
| `compare_less_or_equal` | stencil <= reference |

### Portal Effect (complete setup)

**Scene structure:**
```
MeshInstance3D "portal_door"   → stencil_write material (mask shape)
MeshInstance3D "portal_sky"    → stencil_read material (content inside portal)
```

**Render order matters:** `portal_door` must render before `portal_sky`. Control with `Sorting > Offset` in the MeshInstance3D inspector (lower offset = renders earlier).

**Gotchas:**
- `depth_test_disabled` on the read shader means the portal content ignores scene depth — objects in front of the portal won't occlude it. This is usually correct for portals but wrong for other use cases.
- Transparent materials (those writing to `ALPHA`) render in a separate back-to-front pass *after* all opaque objects. If the write shader is transparent, the stencil is written after the read shader has already executed, so the read shader sees stencil = 0 and renders nothing. Use `discard` in the write shader to keep it in the opaque pass.
- Stencil values are 8-bit unsigned integers (0–255). Default is 0; write any non-zero value to mark.
- The stencil test runs after the fragment shader but before depth write. Modern GPUs may run early stencil tests as an optimization — avoid `discard` in the write shader if you need predictable early-test behavior.

### Applying Stencil to a Ray Marching Shader

To restrict a volumetric effect to a portal region, add the same stencil read to the volume shader:

```glsl
shader_type spatial;
render_mode unshaded, depth_draw_never, depth_test_disabled;
stencil_mode read, compare_equal, 1;
// ... rest of ray marching shader unchanged
```

---

## Quick Reference: Key Built-ins by Shader Type

| Built-in | `canvas_item` | `spatial` | Notes |
|---|---|---|---|
| `SCREEN_UV` | ✓ | ✓ | Normalized screen coords |
| `SCREEN_PIXEL_SIZE` | ✓ | — | `vec2(1/w, 1/h)`; spatial uses `VIEWPORT_SIZE` instead |
| `VIEWPORT_SIZE` | — | ✓ | Screen size in pixels (spatial equivalent of `1.0/SCREEN_PIXEL_SIZE`) |
| `FRAGCOORD` | ✓ | ✓ | `vec4`; `.xy` = pixel coords |
| `TIME` | ✓ | ✓ | Seconds since start |
| `COLOR` | ✓ (output) | — | Final fragment color |
| `ALBEDO` | — | ✓ (output) | RGB surface color |
| `ALPHA` | — | ✓ (output) | Transparency |
| `CAMERA_POSITION_WORLD` | — | ✓ | Camera world position |
| `MODEL_MATRIX` | — | ✓ | Object-to-world transform |
| `INV_VIEW_MATRIX` | — | ✓ | View-to-world transform |
| `UV` | ✓ | ✓ | Mesh UV coordinates |
| `VERTEX` | — | ✓ (vertex) | Local vertex position |
| `ALPHA_ANTIALIASING_EDGE` | — | ✓ | Softens alpha cutout edges; requires `alpha_to_coverage` render mode |
