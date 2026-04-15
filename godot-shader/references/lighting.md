# Lighting Reference

Lighting in Godot spatial shaders uses three functions: `vertex()`, `fragment()`, and `light()`. The `light()` function is the key one — it runs once per pixel **per light** affecting that pixel. Defining it overrides Godot's default lighting, which means you must implement all lighting components manually.

**Critical behavior**: When `light()` is defined, `RIM`, `ROUGHNESS`, `RIM_TINT`, and similar `fragment()` output variables lose their visual effect. You must compute everything inside `light()`.

---

## Built-in Variables (light() context)

| Variable | Type | Role |
|---|---|---|
| `NORMAL` | `vec3` | Surface normal (view space, unit vector) |
| `LIGHT` | `vec3` | Direction toward light source (unit vector) |
| `VIEW` | `vec3` | Direction toward camera (unit vector) |
| `ATTENUATION` | `float` | Light intensity / distance falloff |
| `LIGHT_COLOR` | `vec3` | Light color |
| `DIFFUSE_LIGHT` | `vec3` | **Output**: write diffuse contribution here (+=) |
| `SPECULAR_LIGHT` | `vec3` | **Output**: write specular contribution here (+=) |
| `ALBEDO` | `vec3` | Surface base color (readable in light(); multiply into DIFFUSE_LIGHT) |
| `INV_VIEW_MATRIX` | `mat4` | World←View transform; use to convert view-space NORMAL to world space |

`TANGENT` and `BINORMAL` are **not** available in `light()` — pass them via `varying` from `fragment()`.

---

## Lambertian Diffuse

**Formula**: `D = max(0.0, dot(n, l)) * i`

**Variables**: `NORMAL`, `LIGHT`, `ATTENUATION` → `DIFFUSE_LIGHT`

Multiply `DIFFUSE_LIGHT` by `ALBEDO` to apply the surface base color. Godot exposes `ALBEDO` as a readable variable in `light()` for exactly this purpose — it does **not** apply it automatically when `light()` is defined.

```glsl
shader_type spatial;
render_mode ambient_light_disabled; // isolate custom lighting

void fragment() {
    ALBEDO = vec3(1.0); // set surface color here; readable in light()
}

void light() {
    float d = max(0.0, dot(NORMAL, LIGHT)) * ATTENUATION;
    DIFFUSE_LIGHT += vec3(d) * ALBEDO; // multiply by ALBEDO for surface color
}
```

**With toon shading** (sharpen the light/shadow boundary):

```glsl
void light() {
    float d = max(0.0, dot(NORMAL, LIGHT)) * ATTENUATION;
    d = smoothstep(0.0, 0.05, d); // narrow transition = harder edge
    DIFFUSE_LIGHT += vec3(d) * ALBEDO;
}
```

**With colored shadow** (mix between shadow color and lit color):

```glsl
void light() {
    float d = max(0.0, dot(NORMAL, LIGHT)) * ATTENUATION;
    d = smoothstep(0.0, 0.05, d);
    vec3 diffuse = mix(vec3(0.042, 0.023, 0.534), vec3(1.0), d); // shadow=blue, lit=white
    DIFFUSE_LIGHT += diffuse; // custom color replaces ALBEDO here intentionally
}
```

**Gotchas**:
- Use `+=` not `=` — multiple lights accumulate.
- `max(0.0, ...)` is required; negative dot products (back-facing light) must be discarded.
- `ambient_light_disabled` is useful during development to isolate custom lighting; remove or keep based on artistic intent.

---

## Blinn-Phong Specular

**Formula**: `S = max(0, dot(n, h))^m * (dot(n,l) > 0)`  
where `h = normalize(LIGHT + VIEW)`

**Variables**: `NORMAL`, `LIGHT`, `VIEW`, `ATTENUATION` → `SPECULAR_LIGHT`

The `(dot(n,l) > 0)` guard prevents specular highlights in shadowed regions.

```glsl
shader_type spatial;
render_mode ambient_light_disabled;

float lambert(float i, vec3 l, vec3 n) {
    return max(0.0, dot(n, l)) * i;
}

float blinn_phong(vec3 v, vec3 l, vec3 n, float m) {
    vec3 h = normalize(l + v);              // halfway vector
    float s = pow(max(0.0, dot(n, h)), m);  // specular intensity
    s *= float(dot(n, l) > 0.0);           // kill specular in shadow
    return s;
}

void fragment() {}

void light() {
    float d = lambert(ATTENUATION, LIGHT, NORMAL);
    float s = blinn_phong(VIEW, LIGHT, NORMAL, 64.0); // m=64: medium highlight

    DIFFUSE_LIGHT  += vec3(d) * ALBEDO * 0.3; // 0.3: balance diffuse against specular in this example; tune to taste
    SPECULAR_LIGHT += vec3(s);
}
```

**Shininess exponent `m`**: low (8–16) = wide soft highlight; high (128–256) = tight sharp highlight.

**Gotchas**:
- Phong variant uses `reflect(-l, n)` instead of the halfway vector — more expensive, visually similar.
- Both Phong and Blinn-Phong operate in linear space; apply sRGB conversion for perceptually correct highlights (see sRGB section below).

---

## sRGB / Linear Conversion

**When to use**: Lighting calculations are in linear space. Human vision is non-linear (more sensitive to dark changes). Converting specular output to sRGB makes highlights appear sharper and more visually striking.

**Rule**: Color textures (albedo, diffuse) are sRGB → convert to linear before math. Grayscale textures (normal maps, roughness) stay linear. Convert final lighting output back to sRGB for display.

```glsl
// Accurate IEC 61966-2-1 conversion functions
vec3 to_linear(vec3 srgb) {
    srgb = clamp(srgb, vec3(0.0), vec3(1.0)); // sRGB formula only defined on [0,1]
    vec3 a = pow((srgb + 0.055) / 1.055, vec3(2.4));
    vec3 b = srgb / 12.92;
    bvec3 c = lessThan(srgb, vec3(0.04045));
    return mix(a, b, c);
}

vec3 to_sRGB(vec3 linearRGB) {
    linearRGB = max(linearRGB, vec3(0.0)); // pow(x<0, non-integer) is undefined in GLSL
    vec3 a = vec3(1.055) * pow(linearRGB.rgb, vec3(1.0/2.4)) - vec3(0.055);
    vec3 b = linearRGB.rgb * vec3(12.92);
    bvec3 c = lessThan(linearRGB, vec3(0.0031308));
    return vec3(mix(a, b, c));
}

void light() {
    vec3 s = vec3(blinn_phong(VIEW, LIGHT, NORMAL, 64.0));
    s = to_sRGB(s); // converts linear specular to perceptual space
    SPECULAR_LIGHT += s;
}
```

**Simple approximation** (less accurate but cheaper): `pow(value, vec3(1.0/2.2))` for gamma correction.

**Gotchas**:
- `to_sRGB()` returns `vec3`; `blinn_phong()` returns `float` — cast to `vec3` before converting.
- Do not apply sRGB conversion to normal maps or roughness values — they must stay linear.
- Move these functions to a `.gdshaderinc` file to reuse across shaders (see ShaderInclude section).

---

## Fresnel / Rim Effect

**Formula**: `F = s * pow(1.0 - max(0.0, dot(n, v)), m)`

**Variables**: `NORMAL`, `VIEW` → added to `DIFFUSE_LIGHT`

Maximum rim at grazing angles (VIEW ⊥ NORMAL), zero when looking straight at the surface.

**Quick approach** (without `light()`): use built-in `RIM`, `ROUGHNESS`, `RIM_TINT` in `fragment()`. This only works when `light()` is **not** defined.

```glsl
// fragment()-only approach (no light() function):
void fragment() {
    ROUGHNESS = 0.8;  // controls edge thickness (0=sharp, 1=wide)
    RIM       = 1.0;  // effect intensity
    RIM_TINT  = 0.5;  // 0=white rim, 1=tinted with material color
    ALBEDO    = texture(_MainTex, UV).rgb;
}
```

**Manual approach** (required when `light()` is defined):

```glsl
shader_type spatial;
render_mode ambient_light_disabled;

uniform sampler2D _MainTex : source_color;

float fresnel(vec3 n, vec3 v, float m, float s) {
    float f = 1.0 - max(0.0, dot(n, v));
    return s * pow(f, m); // m=exponent (higher=thinner), s=intensity multiplier
}

float lambert(float i, vec3 l, vec3 n) {
    return max(0.0, dot(n, l)) * i;
}

float blinn_phong(vec3 v, vec3 l, vec3 n, float m) {
    vec3 h = normalize(l + v);
    float s = pow(max(0.0, dot(n, h)), m);
    s *= float(dot(n, l) > 0.0);
    return s;
}

void fragment() {
    ALBEDO = texture(_MainTex, UV).rgb;
}

void light() {
    float f = fresnel(NORMAL, VIEW, 5.0, 2.0); // m=5: tight rim, s=2: bright
    float d = lambert(ATTENUATION, LIGHT, NORMAL);
    float s = blinn_phong(VIEW, LIGHT, NORMAL, 128.0);

    DIFFUSE_LIGHT  += (vec3(d) + vec3(f)) * ALBEDO; // rim and diffuse both modulated by surface color
    SPECULAR_LIGHT += vec3(s);
}
```

**Gotchas**:
- `RIM` in `fragment()` is silently ignored when `light()` is defined — this is a common source of confusion.
- Rim is view-dependent; it will shift as the camera moves, which is the intended behavior.
- `m=1` gives a wide, soft glow; `m>5` gives a thin, sharp edge.

---

## Anisotropic (Ashikhmin-Shirley)

**Formula**: Extends Blinn-Phong with separate exponents `au` (tangent) and `av` (bitangent) to stretch the specular lobe directionally. Includes Schlick Fresnel term.

**Variables**: `NORMAL`, `LIGHT`, `VIEW`, plus `TANGENT`/`BINORMAL` (via varying) → `SPECULAR_LIGHT`

Use for: hair, brushed metal, satin fabrics — any surface with directional microstructure.

**Setup**: `TANGENT` and `BINORMAL` are unavailable in `light()`. Pass them via `varying` from `fragment()`.

```glsl
shader_type spatial;

uniform sampler2D _MainTex : source_color;
uniform float _AU : hint_range(0.0, 256.0, 0.1); // tangent exponent
uniform float _AV : hint_range(0.0, 256.0, 0.1); // bitangent exponent
uniform float _ReflectionFactor : hint_range(0.0, 1.0, 0.1);

varying vec3 _tangent;
varying vec3 _binormal;

void vertex() {}

void fragment() {
    _tangent  = TANGENT;  // capture here; unavailable in light()
    _binormal = BINORMAL;
    ALBEDO = texture(_MainTex, UV).rgb;
}

float lambert(float i, vec3 l, vec3 n) {
    return max(0.0, dot(n, l)) * i;
}

float ashikhmin_shirley(float rs, float au, float av,
                        vec3 n, vec3 l, vec3 v, vec3 t, vec3 b) {
    const float PI = 3.14159265358979;
    vec3 h = normalize(l + v);
    float NdotL = max(dot(n, l), 0.0001);
    float NdotV = max(dot(n, v), 0.0001);
    float NdotH = max(dot(n, h), 0.0001);
    float VdotH = max(dot(v, h), 0.0001);
    float HdotT = dot(h, t);
    float HdotB = dot(h, b);

    // Anisotropic exponent: stretches lobe along tangent/bitangent
    float exponent = au * pow(HdotT, 2.0) + av * pow(HdotB, 2.0);
    // Guard denominator directly — NdotH clamp above does NOT prevent NdotH≈1
    exponent /= max(1.0 - pow(NdotH, 2.0), 1e-6);

    float specular = sqrt((au + 1.0) * (av + 1.0)) * pow(NdotH, exponent);
    specular /= (8.0 * PI) * VdotH * max(NdotL, NdotV);

    // Schlick Fresnel term (optional but improves grazing angle response)
    float f = rs + (1.0 - rs) * pow(1.0 - VdotH, 5.0);
    specular *= f;

    return specular;
}

void light() {
    float aniso = ashikhmin_shirley(
        _ReflectionFactor, _AU, _AV,
        NORMAL, LIGHT, VIEW, _tangent, _binormal
    );

    // Modulate by albedo brightness to follow texture detail
    vec3 albedo = ALBEDO;
    aniso *= albedo.r * albedo.g * albedo.b; // weight highlight by texture luminance
    aniso  = smoothstep(0.0, 0.1, aniso);    // soften highlight transition

    // Attenuate in shadow using Lambert
    aniso *= lambert(ATTENUATION, LIGHT, NORMAL);

    DIFFUSE_LIGHT  += albedo * lambert(ATTENUATION, LIGHT, NORMAL); // attenuated texture color
    SPECULAR_LIGHT += vec3(aniso); // vec3 cast required — SPECULAR_LIGHT is vec3
}
```

**Gotchas**:
- `TANGENT`/`BINORMAL` must be captured in `fragment()` and passed via `varying` — forgetting this is the most common error.
- High `_AU` with `_AV=0` stretches the highlight horizontally (along tangent); swap to stretch vertically.
- The `1.0 - pow(NdotH, 2.0)` denominator approaches zero when `NdotH→1` (direct specular hit). The `NdotH` clamp (`max(..., 0.0001)`) guards the *lower* end (NdotH→0), not the upper end. The `max(..., 1e-6)` guard on the denominator itself is what prevents division by zero here.
- Without the Lambert attenuation multiply, anisotropic highlights appear on shadowed surfaces.
- `_AU = _AV = 0` produces `exponent = 0`, which evaluates `NdotH^0 = 1` — a valid (non-directional) specular result. The `1e-6` guard is not needed for this case; it guards against `NdotH→1` with non-zero `au`/`av` values.

---

## Hemispheric Shading

**Formula**: `gradient = n_y * 0.5 + 0.5` (remap Y normal from [-1,1] to [0,1]), then `mix(ground_color, sky_color, gradient)`

**Variables**: `NORMAL` (converted to world space via `INV_VIEW_MATRIX`) → `DIFFUSE_LIGHT`

Simulates ambient light that varies by surface orientation — surfaces facing up get sky color, facing down get ground color.

```glsl
shader_type spatial;
render_mode ambient_light_disabled; // disable engine ambient; we replace it

uniform sampler2D _MainTex : source_color;
uniform vec3 _GroundColor : source_color;
uniform vec3 _SkyColor    : source_color;
uniform float _Smoothness : hint_range(0.0, 0.49, 0.01); // max 0.49: smoothstep(s, 1-s, t) requires edge0 < edge1

// Place in a .gdshaderinc for reuse:
vec3 to_sRGB(vec3 linearRGB) {
    linearRGB = max(linearRGB, vec3(0.0)); // pow(x<0, non-integer) is undefined in GLSL
    vec3 a = vec3(1.055) * pow(linearRGB.rgb, vec3(1.0/2.4)) - vec3(0.055);
    vec3 b = linearRGB.rgb * vec3(12.92);
    bvec3 c = lessThan(linearRGB, vec3(0.0031308));
    return vec3(mix(a, b, c));
}

float hemisphere(vec3 n, float s) {
    float t = n.y * 0.5 + 0.5;              // remap [-1,1] -> [0,1]
    return smoothstep(0.0 + s, 1.0 - s, t); // s controls transition sharpness
}

void fragment() {
    ALBEDO = texture(_MainTex, UV).rgb;
}

void light() {
    // NORMAL in light() is view space — convert to world space for hemisphere
    vec3 normal_ws = (INV_VIEW_MATRIX * vec4(NORMAL, 0.0)).xyz;

    float gradient      = hemisphere(normal_ws, _Smoothness);
    vec3 custom_ambient = mix(_GroundColor, _SkyColor, gradient);
    // Note: _GroundColor/_SkyColor use source_color hint, so they are already linear.
    // Do NOT apply to_sRGB here — DIFFUSE_LIGHT is a linear accumulator.

    // Optional: add Lambert for light/shadow contrast
    float NdotL = max(dot(NORMAL, LIGHT), 0.0);
    vec3 lambert = NdotL * ATTENUATION * LIGHT_COLOR;

    DIFFUSE_LIGHT += lambert + custom_ambient;
}
```

**Gotchas**:
- `NORMAL` inside `light()` is in **view space**, not world space. Always transform with `INV_VIEW_MATRIX` before using the Y component for hemisphere.
- For optimization, compute `normal_ws` in `fragment()` and pass via `varying` — avoids repeating the matrix multiply per light.
- `_Smoothness` max is 0.49 — at 0.5, `smoothstep(0.5, 0.5, t)` has equal edges, which is undefined behavior in GLSL.
- Do **not** apply `to_sRGB()` to `_GroundColor`/`_SkyColor` — the `source_color` hint causes Godot to convert them to linear on import. `DIFFUSE_LIGHT` is a linear accumulator; writing sRGB values into it produces incorrect (too dark) results.

---

## Normal Maps

**Two approaches**: use the built-in `NORMAL_MAP` variable (simple), or manually construct the TBN matrix (full control).

### Built-in approach (recommended)

```glsl
shader_type spatial;

uniform sampler2D _MainTex   : source_color;
uniform sampler2D _NormalMap : hint_normal; // hint_normal triggers correct reimport
uniform float _Scale         : hint_range(-16.0, 16.0, 0.1);

void fragment() {
    ALBEDO          = texture(_MainTex, UV).rgb;
    NORMAL_MAP      = texture(_NormalMap, UV).rgb; // Godot handles TBN transform
    NORMAL_MAP_DEPTH = _Scale;                     // intensity multiplier
}
```

`hint_normal` on the sampler is required — it tells Godot to reimport the texture as a normal map. Without it, the texture is treated as color data and the normals will be wrong.

### Manual TBN approach (for custom control)

```glsl
shader_type spatial;
render_mode diffuse_toon, specular_toon; // stylized modes make relief more visible

uniform sampler2D _MainTex   : source_color;
uniform sampler2D _NormalMap : hint_normal;
uniform float _Scale         : hint_range(-16.0, 16.0, 0.1);

void fragment() {
    vec3 albedo = texture(_MainTex, UV).rgb;

    // 1. Sample and remap [0,1] -> [-1,1]
    vec3 normal_map = texture(_NormalMap, UV).rgb;
    normal_map = normal_map * 2.0 - 1.0;

    // If Y appears inverted (DirectX vs OpenGL convention): normal_map.y *= -1.0;

    // 2. Reconstruct Z BEFORE scaling (Pythagorean theorem: x²+y²+z²=1)
    //    Scaling XY first would break the unit-vector invariant
    float xy_sq = clamp(dot(normal_map.xy, normal_map.xy), 0.0, 1.0); // |xy|²
    normal_map.z = sqrt(1.0 - xy_sq);

    // 3. Scale XY intensity (Z stays as reconstructed)
    normal_map.xy *= _Scale;

    // 4. Build TBN matrix and transform to view space
    mat3 TBN = mat3(TANGENT.xyz, BINORMAL.xyz, NORMAL.xyz);
    vec3 normal_vs = normalize(TBN * normal_map);

    ALBEDO = albedo;
    NORMAL = normal_vs; // overwrite NORMAL with transformed result
}
```

**Gotchas**:
- Always use `hint_normal` on the sampler uniform — omitting it is the most common normal map bug.
- `NORMAL_MAP` and manual `NORMAL` assignment are mutually exclusive; pick one approach per shader.
- Grayscale textures (normal maps, roughness) must **not** use `source_color` hint — that applies gamma correction and corrupts the data.
- Y-axis inversion between OpenGL and DirectX normal maps: fix with `normal_map.y *= -1.0` in code, or enable "Normal Map Invert Y" in the Import panel.
- When `light()` is defined, the `NORMAL` you set in `fragment()` is what `light()` receives — the TBN transform in `fragment()` correctly feeds into lighting.
- `render_mode diffuse_toon, specular_toon` in the manual TBN example is for visualization only — remove it for standard PBR or custom lighting.

---

## ShaderInclude

Reusable functions across shaders. File extension: `.gdshaderinc`.

```glsl
// res://shaders/functions.gdshaderinc
// Contains shared lighting helpers

vec3 to_sRGB(vec3 linearRGB) {
    linearRGB = max(linearRGB, vec3(0.0)); // pow(x<0, non-integer) is undefined in GLSL
    vec3 a = vec3(1.055) * pow(linearRGB.rgb, vec3(1.0/2.4)) - vec3(0.055);
    vec3 b = linearRGB.rgb * vec3(12.92);
    bvec3 c = lessThan(linearRGB, vec3(0.0031308));
    return vec3(mix(a, b, c));
}

float lambert(float i, vec3 l, vec3 n) {
    return max(0.0, dot(n, l)) * i;
}
```

```glsl
// res://shaders/my_material.gdshader
shader_type spatial;
render_mode ambient_light_disabled;

#include "res://shaders/functions.gdshaderinc" // path must be res:// absolute

uniform sampler2D _MainTex : source_color;

void fragment() {
    ALBEDO = texture(_MainTex, UV).rgb;
}

void light() {
    float d = lambert(ATTENUATION, LIGHT, NORMAL);
    vec3 specular = to_sRGB(vec3(d)); // apply sRGB only to specular-like output
    DIFFUSE_LIGHT  += vec3(d) * ALBEDO;
    SPECULAR_LIGHT += specular;
}
```

**Gotchas**:
- Path in `#include` must be a `res://` absolute path — relative paths do not work.
- Create the file via: right-click folder → Create New > Resource > ShaderInclude. The `.gdshaderinc` extension is required.
- No `shader_type` declaration in `.gdshaderinc` files — they are raw GLSL fragments.
- Include order matters: functions must be declared before use. Place `#include` before `void fragment()`.

---

## Complete Combined Shader (Lambert + Blinn-Phong + Fresnel + sRGB)

A production-ready spatial shader combining the most common techniques:

```glsl
shader_type spatial;
render_mode ambient_light_disabled;

uniform sampler2D _MainTex : source_color;
uniform float _Shininess   : hint_range(1.0, 256.0, 1.0) = 64.0;
uniform float _RimPower    : hint_range(1.0, 10.0, 0.1)  = 5.0;
uniform float _RimIntensity: hint_range(0.0, 5.0, 0.1)   = 1.5;

vec3 to_sRGB(vec3 linearRGB) {
    linearRGB = max(linearRGB, vec3(0.0)); // pow(x<0, non-integer) is undefined in GLSL
    vec3 a = vec3(1.055) * pow(linearRGB.rgb, vec3(1.0/2.4)) - vec3(0.055);
    vec3 b = linearRGB.rgb * vec3(12.92);
    bvec3 c = lessThan(linearRGB, vec3(0.0031308));
    return vec3(mix(a, b, c));
}

float lambert_diffuse(vec3 n, vec3 l, float attenuation) {
    return max(0.0, dot(n, l)) * attenuation;
}

float blinn_phong_specular(vec3 n, vec3 l, vec3 v, float shininess) {
    vec3 h = normalize(l + v);
    float s = pow(max(0.0, dot(n, h)), shininess);
    s *= float(dot(n, l) > 0.0); // no specular in shadow
    return s;
}

float fresnel_rim(vec3 n, vec3 v, float power, float intensity) {
    return intensity * pow(1.0 - max(0.0, dot(n, v)), power);
}

void fragment() {
    ALBEDO = texture(_MainTex, UV).rgb;
}

void light() {
    float d = lambert_diffuse(NORMAL, LIGHT, ATTENUATION);
    float s = blinn_phong_specular(NORMAL, LIGHT, VIEW, _Shininess);
    float r = fresnel_rim(NORMAL, VIEW, _RimPower, _RimIntensity);

    vec3 diffuse  = (vec3(d) + vec3(r)) * ALBEDO;  // surface color applied here
    vec3 specular = to_sRGB(vec3(s));               // sRGB for perceptual highlights

    DIFFUSE_LIGHT  += diffuse;
    SPECULAR_LIGHT += specular;
}
```
