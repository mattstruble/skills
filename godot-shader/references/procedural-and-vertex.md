# Procedural Shapes, Vertex Animation, and Rotations

## UV Coordinate Setup

Godot's UV origin is top-left (V increases downward). For procedural shapes that use
Cartesian math, flip V and center the coordinates:

```glsl
void fragment() {
    float u = UV.x - 0.5;
    float v = (1.0 - UV.y) - 0.5;  // flip V, then center
    vec2 uv = vec2(u, v);
    // uv is now centered at (0,0), range [-0.5, 0.5]
}
```

**Gotcha:** Skipping the V-flip causes procedural shapes to appear vertically mirrored
compared to Desmos or standard math notation.

---

## SDF Shape Primitives

All shapes use centered UV coordinates (`uv` from the setup above). Each returns `float`
(1.0 = inside, 0.0 = outside). Cast boolean comparisons with `float()`.

### Circle

```glsl
// dot(uv, uv) == uv.x*uv.x + uv.y*uv.y — use dot() for efficiency
float circle(vec2 uv, float radius) {
    return float(dot(uv, uv) < radius * radius);
}

// Usage: centered circle at origin
float shape = circle(uv, 0.35);
```

### Soft Rectangle (Rounded Capsule)

Uses `max()` to compute the outside-edge distance, raised to a power — higher exponents = sharper corners:

```glsl
// Exponent 4 = soft rounded rect; exponent 2 = more circular
float soft_rect(vec2 uv, float half_w, float half_h, float r) {
    // max(abs(x) - half, 0.0) = distance outside the box edge (0 inside, positive outside)
    // pow() requires non-negative base in GLSL — using max() ensures this
    float u = max(abs(uv.x) - half_w, 0.0);
    float v = max(abs(uv.y) - half_h, 0.0);
    return float(pow(u, 4.0) + pow(v, 4.0) < pow(r, 4.0));
}
```

### Mirrored Shape (Bilateral Symmetry)

Apply `abs()` to one axis to mirror a shape across that axis:

```glsl
// Two circles (e.g., eyes) from one equation
float u_mirrored = abs(uv.x) - 0.15;  // offset from center axis
float v_offset   = uv.y + 0.1;
float both_eyes  = float(u_mirrored * u_mirrored + v_offset * v_offset < r * r);
```

### Triangle (Linear Inequality)

```glsl
// Downward-pointing triangle: -v > slope * abs(u) + offset, bounded vertically
float nose = float(-v > 2.0 * abs(u) + 0.05)   // slope = 2.0
           * float(-v < 0.15);                   // vertical clamp
```

### SDF Segment (for specular/line effects)

```glsl
float projection(vec2 a, vec2 b, vec2 c) {
    vec2 cb = c - b;
    vec2 ab = a - b;
    float denom = dot(cb, cb);
    return denom > 0.0 ? dot(ab, cb) / denom : 0.0;  // guard: p0==p1 → NaN without this
}

// Returns distance from uv to the segment p0→p1
float segment_sd(vec2 uv, vec2 p0, vec2 p1) {
    float h = projection(uv, p0, p1);
    h = clamp(h, 0.0, 1.0);
    vec2 p2 = p0 + h * (p1 - p0);
    return distance(p2, uv);
}

// Sharpen with smoothstep (lower edge = sharper)
float line = segment_sd(uv, vec2(0.0, 0.8), vec2(1.0, 0.2));
line = smoothstep(0.2, 0.1, line);  // white at center, fades outward
```

**Note:** `segment_sd` uses UV with origin at bottom-left. In `canvas_item` shaders,
invert V before passing: `vec2 uv = vec2(UV.x, 1.0 - UV.y)`.

---

## Combining Shapes

Each shape is a float mask (0.0 or 1.0). Combining them naively with `+` can exceed 1.0
and cause color saturation artifacts.

```glsl
// Union — visible if either shape is present
float union_shape = clamp(a + b, 0.0, 1.0);
// or: max(a, b)  — no saturation, but no additive blending

// Intersection — visible only where both overlap
float intersection = a * b;

// Subtraction — cut b out of a
float subtracted = a * (1.0 - b);
// or: a *= (1.0 - b);

// Layered color composition (accumulate into render_rgb)
vec3 render_rgb = vec3(0.0);
render_rgb += color_a * mask_a;
render_rgb = mix(render_rgb, color_b, mask_b);  // overlay b on top of a
```

**Pattern:** Build shapes as masks, then compose colors separately. This keeps the
mask logic and the color logic decoupled.

---

## Procedural Animation with TIME

`TIME` is a built-in `float` — seconds since engine start, repeats at 3600s.

```glsl
// Oscillation: sin/cos output [-1, 1]
float wave = sin(TIME * speed);

// Remap to [0, 1]
float wave_01 = sin(TIME * speed) * 0.5 + 0.5;

// Oscillate scale in [1.0, 1.0 + 2·_Amplitude]; minimum is always 1.0 (never shrinks below original size)
float scale = sin(TIME * _Speed * PI) * _Amplitude + (1.0 + _Amplitude);

// Scrolling UVs (e.g., moving texture)
vec2 scrolled_uv = UV + vec2(TIME * 0.1, 0.0);
vec4 color = texture(TEXTURE, scrolled_uv);
```

**Gotcha:** `TIME` is not paused when the game pauses. For pause-aware animation,
pass a custom `uniform float _Time` updated from GDScript.

---

## Procedural Patterns

### Stripes

```glsl
// Horizontal stripes — fract repeats [0,1] every 1/frequency units
float stripes = step(0.5, fract(UV.y * 10.0));

// Smooth stripes with smoothstep
float smooth_stripes = smoothstep(0.45, 0.55, fract(UV.y * 10.0));
```

### Checkerboard

```glsl
// floor() + mod() parity check
float checker = mod(floor(UV.x * 8.0) + floor(UV.y * 8.0), 2.0);
// Returns 0.0 or 1.0 alternating
```

### Grid Lines

```glsl
// Thin lines at integer UV boundaries
float line_x = step(0.95, fract(UV.x * 8.0));
float line_y = step(0.95, fract(UV.y * 8.0));
float grid = max(line_x, line_y);
```

---

## Vertex Displacement (spatial shaders)

Modify `VERTEX` in `vertex()` to displace mesh geometry. `VERTEX` is in **object space**.
After modifying `VERTEX`, also update `NORMAL` so lighting stays correct.

```glsl
shader_type spatial;
uniform float _WaveAmplitude = 0.1;
uniform float _WaveFrequency = 2.0;
uniform float _WaveSpeed     = 1.0;

void vertex() {
    // Wave displacement along Y axis, driven by X position and TIME
    float wave = sin(VERTEX.x * _WaveFrequency + TIME * _WaveSpeed) * _WaveAmplitude;
    VERTEX.y += wave;

    // Recalculate normal to match displaced geometry
    // (for simple waves, approximate with the derivative)
    float dx = cos(VERTEX.x * _WaveFrequency + TIME * _WaveSpeed)
               * _WaveAmplitude * _WaveFrequency;
    NORMAL = normalize(vec3(-dx, 1.0, 0.0));
}

void fragment() {
    ALBEDO = vec3(0.2, 0.6, 1.0);
}
```

### Heightmap Displacement

Sample a texture in `vertex()` to displace terrain:

```glsl
uniform sampler2D _HeightMap;
uniform float _HeightScale = 1.0;

void vertex() {
    // textureLod required in vertex() — implicit derivatives are unavailable there,
    // so mip selection is undefined without an explicit LOD level
    float height = textureLod(_HeightMap, UV, 0.0).r;
    VERTEX.y += height * _HeightScale;

    // Approximate normal from neighboring samples (requires texelFetch or manual offset)
    // For production, bake normals into a normal map instead
}
```

**Gotcha:** `texture()` in `vertex()` has undefined mip selection — always use `textureLod(tex, uv, 0.0)` for deterministic results.

---

## canvas_item Shader: UI Vertex Animation + Specular Effect

`shader_type canvas_item` is required for all 2D/UI elements (`TextureRect`, `Sprite2D`, etc.).
Fewer built-in variables than `spatial` — `VERTEX` is in canvas (screen-pixel) space.

### Vertex Scaling from Center

`skip_vertex_transform` disables Godot's automatic vertex transform. You must then
apply `MODEL_MATRIX` manually. Without it, images shift position in the viewport.

```glsl
shader_type canvas_item;
render_mode skip_vertex_transform;

uniform bool  _VertexAnimation;
uniform float _VertexScale : hint_range(0.0, 0.5, 0.01);
uniform float _VertexSpeed : hint_range(1.0, 3.0, 0.1);

// Helper: offset needed to keep scaling centered
// a = scale factor, x = image dimension in pixels
float scale_from_center(float a, float x) {
    return x * (a - 1.0) * 0.5;
}

void vertex() {
    if (!_VertexAnimation) {
        // Identity: apply model transform unchanged
        VERTEX = (MODEL_MATRIX * vec4(VERTEX, 0.0, 1.0)).xy;
    } else {
        // Oscillate scale with sin(); base is (1 + amp) so minimum is always 1.0
        float time       = (TIME * _VertexSpeed) * PI;
        float scale_ratio = sin(time) * _VertexScale + (1.0 + _VertexScale);

        // pixel_scaler = 0.5 if images were scaled to 50% in the Inspector
        const float pixel_scaler = 0.5;
        vec2 resolution = pixel_scaler / TEXTURE_PIXEL_SIZE;  // effective pixel dims

        float px = scale_from_center(scale_ratio, resolution.x);
        float py = scale_from_center(scale_ratio, resolution.y);

        vec2 scaled_vertex = VERTEX * vec2(scale_ratio);
        scaled_vertex -= vec2(px, py);  // re-center the scale pivot

        VERTEX = (MODEL_MATRIX * vec4(scaled_vertex, 0.0, 1.0)).xy;
    }
}
```

**Key built-ins:**
- `TEXTURE_PIXEL_SIZE` — `vec2(1/width, 1/height)` of the default texture
- `MODEL_MATRIX` — canvas-to-screen transform for this element
- `COLOR` — vertex color × Modulate × SelfModulate; use as per-instance ID

### Per-Instance Animation Phase via COLOR

All instances sharing one material animate in sync. Use `COLOR` (driven by the node's
Modulate property) to offset the phase per image:

```glsl
void vertex() {
    // ...
    // dot(COLOR.rgb, COLOR.rgb) = squared RGB magnitude — not luminance, but a
    // cheap per-instance differentiator. Requires intentionally varied Modulate
    // colors per instance. Default white Modulate gives color_id = 3.0 for all
    // instances (no differentiation). Black Modulate gives 0.0 (all sync).
    float color_id = dot(COLOR.rgb, COLOR.rgb);
    float time = (color_id + TIME * _VertexSpeed) * PI;
    // ...
}
```

Then restore the correct texture color in `fragment()` (otherwise the modulate tint persists):

```glsl
void fragment() {
    vec4 color = texture(TEXTURE, UV);
    COLOR = color;  // overwrite vertex color with actual texture
}
```

### Animated Specular Highlight (SDF Segment)

A diagonal segment sweeps across the image, shaped by the texture's blue channel:

```glsl
uniform float _SpecularSpeed : hint_range(0.5, 2.0, 0.1);
uniform vec3  _SpecularColor : source_color;

// (projection and segment_sd functions defined above)

void fragment() {
    vec4 color = texture(TEXTURE, UV);

    // Invert V for Cartesian-space segment math
    vec2 uv = vec2(UV.x, 1.0 - UV.y);
    uv += color.b;  // distort UVs with blue channel — highlight adopts image shape

    float time = TIME / max(_SpecularSpeed, 0.001);  // guard: _SpecularSpeed=0 → Inf
    float offset = fract(time) * 3.0 - 1.5;  // cycles [-1.5, 1.5]

    // Throttle: ceil(sin(t*PI)) alternates 1/0 each cycle — highlight skips every other pass
    // +0.00001 epsilon prevents exact 0 when sin hits zero at cycle boundaries (ceil(0.0)=0)
    float offset_mask = ceil(sin(time * PI)) + 0.00001;
    offset *= offset_mask;

    // Vertical segment sweeping horizontally
    vec2 p0 = vec2(0.5 + offset, 0.8);
    vec2 p1 = vec2(0.5 + offset, 0.2);

    float specular = segment_sd(uv, p0, p1);
    specular = smoothstep(0.2, 0.1, specular);  // sharpen
    specular *= offset_mask;                     // hide when not sweeping

    vec3 specular_color = vec3(specular) * _SpecularColor;
    color.rgb += specular_color;
    color.rgb = clamp(color.rgb, 0.0, 1.0);

    COLOR = color;
}
```

---

## 2D Rotation Matrix

Rotate a UV point by angle `a` (radians) around the origin:

```glsl
vec2 rotate2D(float x, float y, float a) {
    return vec2(
        cos(a) * x + sin(a) * y,
       -sin(a) * x + cos(a) * y
    );
}

// Usage: rotate a point, then evaluate a shape at the rotated position
float angle_rad = _AngleDeg * (PI / 180.0);
vec2 rotated = rotate2D(uv.x - pivot.x, uv.y - pivot.y, angle_rad);
float shape  = some_shape(rotated);
```

**Pattern:** Translate to the rotation pivot first (subtract pivot), rotate, then evaluate
the shape at the rotated coordinates. This is how the book rotates eyebrows and bones
around their local origins.

**Mirror trick:** To reflect a shape across the Y axis, negate the X input before rotating:
```glsl
vec2 p_right = rotate2D( u - 0.1, v - 0.15, angle);  // right side
vec2 p_left  = rotate2D(-u - 0.1, v - 0.15, angle);  // mirror: negate u
```

---

## 3D Rotation Matrices

Define as macros for reuse. GLSL `mat3` is column-major, so these macros produce **clockwise**
rotation for positive angles (equivalently: the coordinate frame rotates CCW).
Apply to `VERTEX` and `NORMAL` in `vertex()`.

```glsl
// x-axis rotation (modifies YZ)
#define RX(a) mat3( \
    vec3(1,      0,       0), \
    vec3(0,  cos(a), -sin(a)), \
    vec3(0,  sin(a),  cos(a)))

// y-axis rotation (modifies XZ)
#define RY(a) mat3( \
    vec3( cos(a), 0, sin(a)), \
    vec3(      0, 1,      0), \
    vec3(-sin(a), 0, cos(a)))

// z-axis rotation (modifies XY)
#define RZ(a) mat3( \
    vec3(cos(a), -sin(a), 0), \
    vec3(sin(a),  cos(a), 0), \
    vec3(     0,       0, 1))

void vertex() {
    vec3 angles = _Angles * (PI / 180.0);  // degrees → radians

    // Compose: order matters — ZXY is a common convention
    mat3 EULER_ZXY = RY(angles.y) * RX(angles.x) * RZ(angles.z);

    VERTEX = EULER_ZXY * VERTEX;
    NORMAL = normalize(EULER_ZXY * NORMAL);  // must rotate normals too
}
```

**Gimbal Lock:** Euler matrix composition loses a degree of freedom when two axes
align (e.g., 90° on X makes Y and Z equivalent). Use quaternions to avoid this.

**Tip:** Put these macros in a `.gdshaderinc` file and `#include` them across shaders:
```glsl
#include "res://shaders/functions.gdshaderinc"
```

### Procedural Per-Instance Rotation (wind sway example)

```glsl
void vertex() {
    vec3 vertex_os = VERTEX;
    vec3 vertex_ws = (MODEL_MATRIX * vec4(vertex_os, 1.0)).xyz;

    // Vertical gradient: 0 at base, 1 at top — keeps roots stable
    float gradient = clamp(vertex_ws.y - NODE_POSITION_WORLD.y, 0.0, 1.0);

    // Pseudo-random angle from world position (hash33 from a .gdshaderinc)
    float angle_map = hash33(floor(NODE_POSITION_WORLD)).y;
    angle_map *= gradient;

    float st = sin(TIME + angle_map * 2.0) * 0.05 + 0.05;  // sine sway
    float ct = cos(TIME + angle_map * 2.0) * 0.05 + 0.05;  // cosine sway

    mat3 EULER_ZXY = RY(angle_map * TAU)
                   * RX((angle_map * 0.1345) - st)
                   * RZ((angle_map * 0.1567) - ct);

    VERTEX = EULER_ZXY * vertex_os * clamp(angle_map, 0.4, 1.0);
    NORMAL = normalize(EULER_ZXY * NORMAL);  // must rotate normals to match displaced geometry
}
```

---

## Quaternion Rotation

Quaternions avoid gimbal lock. Use when composing rotations from multiple axes or
when orientation must be stable across all angles.

### Struct and Helper Functions

```glsl
struct quaternion { float x; float y; float z; float w; };

// Build quaternion from axis-angle (axis need not be normalized — normalize() is called)
// Gotcha: passing a zero-length axis (vec3(0,0,0)) causes normalize() to return NaN.
// Ensure the axis is non-zero, or guard: length(axis) > 0.0 ? normalize(axis) : vec3(0,0,1)
quaternion quat_create(float angle, vec3 axis) {
    float s = sin(angle / 2.0);
    float c = cos(angle / 2.0);
    vec3 v  = normalize(axis) * s;
    return quaternion(v.x, v.y, v.z, c);
}

// Conjugate: inverts the rotation direction
quaternion quat_conjugate(quaternion q) {
    return quaternion(-q.x, -q.y, -q.z, q.w);
}

// Hamilton product: q1 * q2
quaternion quat_mult(quaternion q1, quaternion q2) {
    float s1 = q1.w;  float s2 = q2.w;
    vec3  v1 = vec3(q1.x, q1.y, q1.z);
    vec3  v2 = vec3(q2.x, q2.y, q2.z);
    float s  = s1 * s2 - dot(v1, v2);
    vec3  v  = s1 * v2 + s2 * v1 + cross(v1, v2);
    return quaternion(v.x, v.y, v.z, s);
}
```

### Applying Quaternion Rotation to a vec3

The sandwich product `p' = q * p * q⁻¹` rotates point `p` by quaternion `q`:

```glsl
// Rotate a world-space position using per-axis quaternions (YXZ order)
void fragment() {
    vec3 vertex_ws   = (INV_VIEW_MATRIX * vec4(VERTEX, 1.0)).xyz;
    vec3 position_ws = vertex_ws - _LightPosition;

    // Build per-axis quaternions (negate angles to match Godot's light gizmo convention)
    quaternion qx = quat_create(-_LightRotation.x, vec3(1, 0, 0));
    quaternion qy = quat_create(-_LightRotation.y, vec3(0, 1, 0));
    quaternion qz = quat_create(-_LightRotation.z, vec3(0, 0, 1));

    // Compose in YXZ order (matches Godot's DirectionalLight3D gizmo)
    quaternion q_YXZ = quat_mult(qz, quat_mult(qx, qy));
    quaternion q_inv = quat_conjugate(q_YXZ);

    // Sandwich product: q * p * q⁻¹
    quaternion p  = quaternion(position_ws.x, position_ws.y, position_ws.z, 0.0);
    quaternion pr = quat_mult(q_YXZ, p);
    pr            = quat_mult(pr, q_inv);

    // Extract rotated position
    vec3 pos_rot = vec3(pr.x, pr.y, pr.z);

    // Center projection in [0,1] UV space
    vec2 uv_ws = pos_rot.xy + vec2(0.5);

    float spot = texture(_SpotMap, uv_ws).r;
    vec3  color = mix(texture(_FrontMap, UV).rgb,
                      texture(_BackMap,  UV).rgb,
                      spot);
    ALBEDO = color;
}
```

**Key variables:**
- `INV_VIEW_MATRIX` — transforms from view space to world space (available in `fragment()`)
- `NODE_POSITION_WORLD` — world-space position of the mesh node
- `_LightRotation` — pass from GDScript via `set_shader_parameter()`

**Multiplication order matters.** The order `quat_mult(qz, quat_mult(qx, qy))` (YXZ)
matches Godot's DirectionalLight3D rotation gizmo. Change order if your reference
frame differs.

**Conjugate placement:** Conjugate the *composed* quaternion, not individual axis
quaternions. Apply it as the right-hand factor in the sandwich product.

---

## Common Gotchas

| Issue | Cause | Fix |
|---|---|---|
| Shape appears flipped vertically | Godot UV V-axis is top-down | `v = (1.0 - UV.y) - 0.5` |
| Shape union exceeds 1.0 | Direct addition of masks | `clamp(a + b, 0.0, 1.0)` or `max(a, b)` |
| Lighting wrong after vertex displacement | NORMAL not updated | `NORMAL = normalize(rotation_mat * NORMAL)` |
| UI images shift when adding `skip_vertex_transform` | Manual transform required | Apply `MODEL_MATRIX * vec4(VERTEX, 0.0, 1.0)` |
| Scaling from wrong corner | Default pivot is top-left | Subtract `scale_from_center()` offset after scaling |
| Gimbal lock at 90° | Euler matrix composition | Switch to quaternions |
| `texture()` in `vertex()` gives wrong results | Implicit LOD undefined | Use `textureLod(tex, uv, 0.0)` |
