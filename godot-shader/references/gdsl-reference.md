# GDSL Language Reference

Godot's shading language is a simplified GLSL ES 3.0 variant. Files use `.gdshader` extension; include files use `.gdshaderinc`.

## Table of Contents
1. [Type System](#type-system)
2. [Shader Structure](#shader-structure)
3. [Coordinate Spaces](#coordinate-spaces)
4. [Built-in Matrices](#built-in-matrices)
5. [Spatial Shader Built-ins](#spatial-shader-built-ins)
6. [Canvas Item Shader Built-ins](#canvas-item-shader-built-ins)
7. [Uniforms and Varyings](#uniforms-and-varyings)
8. [ShaderInclude](#shaderinclude)
9. [Particle Shaders](#particle-shaders)
   - [Structure](#structure)
   - [Lifecycle and State Persistence](#lifecycle-and-state-persistence)
   - [Render Modes](#render-modes-particles)
   - [Built-ins Reference](#built-ins-startprocess)
   - [emit_subparticle()](#emit_subparticle)
   - [Common Particle Patterns](#common-particle-patterns)

---

## Type System

### Scalar and Vector Types

| Type | Description |
|------|-------------|
| `bool` | Boolean |
| `int` | 32-bit signed integer |
| `uint` | Unsigned integer (requires `u` suffix: `1u`) |
| `float` | 32-bit float (requires `.` or `f` suffix: `1.0`, `1.0f`) |
| `vec2/3/4` | Float vectors |
| `ivec2/3/4` | Signed integer vectors |
| `uvec2/3/4` | Unsigned integer vectors |
| `bvec2/3/4` | Boolean vectors |
| `mat2/3/4` | Column-major matrices (2×2, 3×3, 4×4) |
| `sampler2D` | 2D texture sampler (float) |
| `sampler2DArray` | 2D texture array sampler |
| `sampler3D` | 3D texture sampler |
| `samplerCube` | Cubemap sampler |

### Swizzling

```glsl
vec4 a = vec4(0.0, 1.0, 2.0, 3.0);
vec3 b = a.rgb;    // same as a.xyz
vec3 c = a.bgr;    // reorder components
float d = a.w;     // single component → scalar
// Sets: xyzw, rgba, stpq — cannot mix styles in one swizzle
b.bgr = a.rgb;     // valid: assignment with reorder
// b.rrr = a.rgb;  // invalid: assignment with duplication
```

### Type Casting

No implicit casting. Use constructors:
```glsl
float a = float(2);       // int → float
uint b = uint(2);         // int → uint
vec3 c = vec3(some_mat3_col);  // extract column
mat3 basis = mat3(MODEL_MATRIX);  // mat4 → mat3 (top-left 3×3)
```

### Matrix Construction

```glsl
mat4 identity = mat4(1.0);  // diagonal = 1.0, rest = 0.0
// Each vec3 argument is a COLUMN (column-major order)
mat3 m3 = mat3(vec3(1,0,0), vec3(0,1,0), vec3(0,0,1));  // identity
mat4 m4 = mat4(basis);      // mat3 → mat4 (identity padding)
```

Matrix access: `m[column][row]` or `m[column].y`

**GLSL uses column-vector convention: `M * v`, not `v * M`.** These are transposes of each other and produce different results for non-symmetric matrices.

### Precision Qualifiers

```glsl
lowp vec4 a;    // ~8 bits per component, [0,1] — do NOT use for normals or HDR values
mediump vec4 b; // ~16 bits / half float
highp vec4 c;   // 32 bits (default)
```

> **Warning:** `lowp` clamps to [0,1] on mobile hardware. Using it for normals ([-1,1]) or HDR values produces incorrect results.

---

## Shader Structure

### Shader Type Declarations

```glsl
shader_type spatial;      // 3D objects (MeshInstance3D, etc.)
shader_type canvas_item;  // 2D sprites, UI, CanvasItem nodes
shader_type particles;    // GPUParticles2D / GPUParticles3D
shader_type sky;          // Sky backgrounds
shader_type fog;          // FogVolume nodes
```

### Processor Functions

```glsl
shader_type spatial;

// Optional: runs per-vertex before rasterization
void vertex() { }

// Optional: runs per-fragment (pixel) after rasterization
void fragment() { }

// Optional: runs per-fragment per-light (after fragment)
void light() { }
```

For `canvas_item`, same three functions apply. For `particles`, use `start()` and `process()` (see [Particle Shaders](#particle-shaders)).

### Render Mode

Multiple modes can be combined with commas:

```glsl
shader_type spatial;
render_mode unshaded, cull_disabled;
```

**Spatial render modes:**

| Mode | Effect |
|------|--------|
| `unshaded` | No lighting/shading; only ALBEDO output |
| `cull_back` | Cull back faces **(default)** |
| `cull_front` | Cull front faces |
| `cull_disabled` | Double-sided rendering |
| `blend_mix` | Alpha transparency **(default)** |
| `blend_add` | Additive blending |
| `blend_sub` | Subtractive blending |
| `blend_mul` | Multiplicative blending |
| `blend_premul_alpha` | Premultiplied alpha blend |
| `depth_draw_opaque` | Depth only for opaque **(default)** |
| `depth_draw_always` | Always write depth |
| `depth_draw_never` | Never write depth |
| `depth_prepass_alpha` | Opaque depth pre-pass for transparent geometry |
| `depth_test_disabled` | Disable depth test |
| `skip_vertex_transform` | Disable auto transform; VERTEX/NORMAL/TANGENT/BINORMAL must be transformed manually |
| `world_vertex_coords` | VERTEX/NORMAL/TANGENT/BINORMAL in world space instead of model space |
| `shadows_disabled` | No shadow receiving |
| `ambient_light_disabled` | No ambient/radiance contribution |
| `diffuse_burley` | Burley (Disney PBS) diffuse **(default)** |
| `diffuse_lambert` | Lambert diffuse |
| `diffuse_lambert_wrap` | Lambert-wrap diffuse |
| `diffuse_toon` | Toon diffuse |
| `specular_schlick_ggx` | Schlick-GGX specular **(default)** |
| `specular_toon` | Toon specular |
| `specular_disabled` | No direct specular |
| `shadow_to_opacity` | Shadows modulate alpha (useful for AR camera overlay) |
| `fog_disabled` | No fog (useful for additive particles) |
| `particle_trails` | Enable particle trail geometry |
| `vertex_lighting` | Per-vertex lighting instead of per-pixel |
| `alpha_to_coverage` | Alpha antialiasing mode |
| `alpha_to_coverage_and_one` | Alpha antialiasing mode |
| `sss_mode_skin` | Subsurface scattering optimized for skin |
| `wireframe` | Draw geometry as lines (debug) |

**Canvas item render modes:**

| Mode | Effect |
|------|--------|
| `blend_mix` | Normal alpha blend **(default)** |
| `blend_add` | Additive |
| `blend_sub` | Subtractive |
| `blend_mul` | Multiplicative |
| `blend_premul_alpha` | Premultiplied alpha |
| `blend_disabled` | Disable all blending (useful for render targets) |
| `unshaded` | No lighting |
| `light_only` | Only render where lit |
| `skip_vertex_transform` | Manual vertex transform |
| `world_vertex_coords` | VERTEX in world space |

---

## Coordinate Spaces

| Space | Description | How to reach it |
|-------|-------------|-----------------|
| **Object/Model/Local** | Relative to mesh pivot | VERTEX, NORMAL, TANGENT, BINORMAL in `vertex()` (default) |
| **World** | Relative to scene origin (Viewport grid) | `MODEL_MATRIX * vec4(VERTEX, 1.0)` |
| **View** | Relative to camera | `VIEW_MATRIX * world_pos`; VERTEX/NORMAL/TANGENT/BINORMAL in `fragment()` (after auto-transform) |
| **Clip** | Homogeneous projection space | `PROJECTION_MATRIX * view_pos`; write to `POSITION` |
| **NDC** | Clip ÷ W, range [-1,1] | After perspective divide |
| **Screen** | Pixel coordinates | `FRAGCOORD.xy`; `SCREEN_UV` |
| **UV/Texture** | [0,1]² per-vertex texture coords | `UV`, `UV2` |
| **Tangent** | Per-vertex local surface frame (T, B, N) | Dot product with TANGENT/BINORMAL/NORMAL |

**Space naming convention for variables:**
- `_os` = object space
- `_ws` = world space
- `_vs` = view space
- `_ss` = screen space

**Key space facts:**
- `vertex()`: VERTEX/NORMAL/TANGENT/BINORMAL are in **model space** (or world space with `world_vertex_coords`)
- `fragment()`: VERTEX/NORMAL/TANGENT/BINORMAL are in **view space** (after auto-transform)
- `light()`: NORMAL is in **view space**; use `INV_VIEW_MATRIX * vec4(NORMAL, 0.0)` to get world space
- VIEW vector (fragment→camera) is always in **view space**
- TANGENT and VIEW are both in view space → valid to dot-product them directly

**Tangent space TBN construction (right-handed, Godot):**
```glsl
// In fragment() — all vectors are in view space
vec3 view_in_tangent = normalize(vec3(
    dot(-TANGENT, VIEW),   // negate TANGENT for Godot's right-handed system
    dot(BINORMAL, VIEW),
    dot(NORMAL, VIEW)
));
// Use view_in_tangent.xy to offset UV for parallax/depth effects
```

---

## Built-in Matrices

| Matrix | Type | Transform |
|--------|------|-----------|
| `MODEL_MATRIX` | `mat4` | Model/local space → world space |
| `VIEW_MATRIX` | `mat4` | World space → view space |
| `PROJECTION_MATRIX` | `mat4` | View space → clip space |
| `INV_VIEW_MATRIX` | `mat4` | View space → world space |
| `INV_PROJECTION_MATRIX` | `mat4` | Clip space → view space |
| `MODELVIEW_MATRIX` | `mat4` | Model/local space → view space (combined; prefer for float precision) |
| `MODELVIEW_NORMAL_MATRIX` | `mat3` | Normals: model → view space |
| `MODEL_NORMAL_MATRIX` | `mat3` | Normals: model → world space (handles non-uniform scale) |
| `MAIN_CAM_INV_VIEW_MATRIX` | `mat4` | View → world for the main scene camera (differs from `INV_VIEW_MATRIX` in shadow/XR passes) |

**W component convention:**
- `W = 1.0` → position vector (affected by translation, rotation, scale)
- `W = 0.0` → direction vector (affected by rotation and scale only)

**Full manual transform chain:**
```glsl
void vertex() {
    vec4 pos_ws = MODEL_MATRIX * vec4(VERTEX, 1.0);   // object → world
    vec4 pos_vs = VIEW_MATRIX * pos_ws;                // world → view
    POSITION = PROJECTION_MATRIX * pos_vs;             // view → clip (overrides auto)
}
```

**Billboard effect (always face camera):**
```glsl
void vertex() {
    // Replace rotation with camera orientation, keep world position
    mat4 BILLBOARD_MATRIX = mat4(
        INV_VIEW_MATRIX[0],   // camera right (world)
        INV_VIEW_MATRIX[1],   // camera up (world)
        INV_VIEW_MATRIX[2],   // camera forward (world)
        MODEL_MATRIX[3]       // object world position
    );
    vec4 pos_ws = BILLBOARD_MATRIX * vec4(VERTEX, 1.0);
    vec4 pos_vs = VIEW_MATRIX * pos_ws;
    POSITION = PROJECTION_MATRIX * pos_vs;
}
```

**Custom transformation matrix — column-vector convention (`M * v`):**
```glsl
// Scale macro — apply in object space before MODEL_MATRIX
#define SCALE_MATRIX(s) mat3(vec3(s,0,0), vec3(0,s,0), vec3(0,0,s))
void vertex() {
    VERTEX = SCALE_MATRIX(2.0) * VERTEX;  // M * v, not v * M
}

// Shear: each vec3 is a COLUMN. col0=(1,0,0), col1=(1,1,0) → x' = x + y
#define SHEAR_XY mat3(vec3(1,0,0), vec3(1,1,0), vec3(0,0,1))
void vertex() {
    VERTEX = SHEAR_XY * VERTEX;  // shears x-axis by y-axis
}
```

---

## Spatial Shader Built-ins

### Global Built-ins (available everywhere)

| Name | Type | Access | Description |
|------|------|--------|-------------|
| `TIME` | float | in | Seconds since engine start; resets at 3600s |
| `PI` | float | in | 3.141592 |
| `TAU` | float | in | 6.283185 (2×PI) |
| `E` | float | in | 2.718281 |
| `OUTPUT_IS_SRGB` | bool | in | true in Compatibility renderer — in Compatibility, ALBEDO/EMISSION are written to an sRGB framebuffer without auto conversion; apply `pow(color, vec3(1.0/2.2))` manually if targeting both renderers |
| `CLIP_SPACE_FAR` | float | in | 0.0 (Forward+/Mobile), -1.0 (Compatibility) — affects depth reconstruction |

### vertex() Built-ins

| Name | Type | Access | Description |
|------|------|--------|-------------|
| `VERTEX` | vec3 | inout | Position in model space (world space with `world_vertex_coords`) |
| `NORMAL` | vec3 | inout | Normal in model space |
| `TANGENT` | vec3 | inout | Tangent in model space |
| `BINORMAL` | vec3 | inout | Binormal in model space |
| `POSITION` | vec4 | out | Override final clip-space position; disables auto projection. **Also used in shadow/depth passes** — writing POSITION for a visual-only effect causes shadows to be cast from the modified position. |
| `UV` | vec2 | inout | Primary UV channel |
| `UV2` | vec2 | inout | Secondary UV channel |
| `COLOR` | vec4 | inout | Vertex color (8-bit per channel, [0,1]) |
| `POINT_SIZE` | float | inout | Point size for point rendering |
| `ROUGHNESS` | float | out | Roughness for vertex lighting |
| `VIEWPORT_SIZE` | vec2 | in | Viewport size in pixels |
| `NODE_POSITION_WORLD` | vec3 | in | Node world position |
| `NODE_POSITION_VIEW` | vec3 | in | Node view-space position |
| `CAMERA_POSITION_WORLD` | vec3 | in | Camera world position |
| `CAMERA_DIRECTION_WORLD` | vec3 | in | Camera world direction |
| `CAMERA_VISIBLE_LAYERS` | uint | in | Cull layers of the rendering camera |
| `INSTANCE_ID` | int | in | Instance ID |
| `INSTANCE_CUSTOM` | vec4 | in | Per-instance data (particles: x=rotation angle, y=lifetime phase, z=anim frame) |
| `VERTEX_ID` | int | in | Index in vertex buffer |
| `BONE_INDICES` | uvec4 | in | Bone indices for skinning |
| `BONE_WEIGHTS` | vec4 | in | Bone weights for skinning |
| `CUSTOM0` | vec4 | in | Custom vertex data (xy=UV3, zw=UV4 when using extra UVs) |
| `CUSTOM1` | vec4 | in | Custom vertex data (xy=UV5, zw=UV6 when using extra UVs) |
| `CUSTOM2` | vec4 | in | Custom vertex data (xy=UV7, zw=UV8 when using extra UVs) |
| `CUSTOM3` | vec4 | in | Custom vertex data |
| `Z_CLIP_SCALE` | float | out | Scale vertex toward camera to avoid clipping |
| `MODEL_MATRIX` | mat4 | in | Model → world |
| `MODEL_NORMAL_MATRIX` | mat3 | in | Normals: model → world |
| `VIEW_MATRIX` | mat4 | in | World → view |
| `INV_VIEW_MATRIX` | mat4 | in | View → world |
| `MAIN_CAM_INV_VIEW_MATRIX` | mat4 | in | View → world for main camera (differs in shadow/XR passes) |
| `PROJECTION_MATRIX` | mat4 | inout | View → clip |
| `MODELVIEW_MATRIX` | mat4 | inout | Model → view (combined) |
| `MODELVIEW_NORMAL_MATRIX` | mat3 | inout | Normals: model → view |
| `INV_PROJECTION_MATRIX` | mat4 | in | Clip → view |

### fragment() Built-ins

| Name | Type | Access | Description |
|------|------|--------|-------------|
| `FRAGCOORD` | vec4 | in | Pixel center in screen space; xy=window pos (upper-left origin), z=depth [0,1] (see CLIP_SPACE_FAR for Compatibility) |
| `FRONT_FACING` | bool | in | true if front face |
| `VIEW` | vec3 | in | Normalized fragment→camera vector (view space) |
| `VERTEX` | vec3 | in | Fragment position in view space |
| `LIGHT_VERTEX` | vec3 | inout | Writable VERTEX for altering light/shadows without moving fragment |
| `NORMAL` | vec3 | inout | Normal in view space |
| `TANGENT` | vec3 | inout | Tangent in view space |
| `BINORMAL` | vec3 | inout | Binormal in view space |
| `NORMAL_MAP` | vec3 | out | Assign raw [0,1] texture sample — Godot remaps to [-1,1] internally. Do NOT remap before assigning. |
| `NORMAL_MAP_DEPTH` | float | out | Normal map depth multiplier (default 1.0) |
| `UV` | vec2 | in | Primary UV |
| `UV2` | vec2 | in | Secondary UV |
| `COLOR` | vec4 | in | Vertex color from vertex() |
| `SCREEN_UV` | vec2 | in | Screen UV for current pixel |
| `DEPTH` | float | out | Custom depth [0,1]; **if written in any branch, must be written in ALL branches** |
| `ALBEDO` | vec3 | out | Base color in linear space (default white). **Do NOT assign gamma-encoded values.** |
| `ALPHA` | float | out | Transparency [0,1]; writing triggers transparent pipeline. **Depth is not written by default** — add `render_mode depth_draw_always` if depth-based effects (soft particles, refraction) are needed. |
| `ALPHA_SCISSOR_THRESHOLD` | float | out | Discard pixels below this alpha (prefer over `discard` for performance) |
| `ALPHA_HASH_SCALE` | float | out | Alpha hash scale for dithered transparency (default 1.0) |
| `PREMUL_ALPHA_FACTOR` | float | out | Premultiplied alpha factor (only with `blend_premul_alpha`) |
| `METALLIC` | float | out | Metallic [0,1] |
| `ROUGHNESS` | float | out | Roughness [0,1] |
| `SPECULAR` | float | out | Specular (default 0.5; 0.0 disables reflections) |
| `RIM` | float | out | Rim lighting amount [0,1] |
| `RIM_TINT` | float | out | Rim tint (0=white, 1=albedo color) |
| `CLEARCOAT` | float | out | Clearcoat layer amount |
| `CLEARCOAT_GLOSS` | float | out | Clearcoat gloss (not roughness; higher = smoother) |
| `ANISOTROPY` | float | out | Anisotropy amount |
| `ANISOTROPY_FLOW` | vec2 | out | Anisotropy flow direction |
| `SSS_STRENGTH` | float | out | Subsurface scattering strength |
| `BACKLIGHT` | vec3 | inout | Backlight color |
| `AO` | float | out | Ambient occlusion [0,1] |
| `AO_LIGHT_AFFECT` | float | out | How much AO affects lighting [0,1] |
| `EMISSION` | vec3 | out | Emission color |
| `FOG` | vec4 | out | Override fog color (rgb) and amount (a) |
| `RADIANCE` | vec4 | out | Override radiance (environment reflection) |
| `IRRADIANCE` | vec4 | out | Override irradiance (environment diffuse) |
| `POINT_COORD` | vec2 | in | Point coordinate for POINT_SIZE rendering |
| `VIEWPORT_SIZE` | vec2 | in | Viewport size in pixels |
| `NODE_POSITION_WORLD` | vec3 | in | Node world position |
| `NODE_POSITION_VIEW` | vec3 | in | Node view-space position |
| `CAMERA_POSITION_WORLD` | vec3 | in | Camera world position |
| `CAMERA_DIRECTION_WORLD` | vec3 | in | Camera world direction |
| `MODEL_MATRIX` | mat4 | in | Model → world |
| `MODEL_NORMAL_MATRIX` | mat3 | in | Normals: model → world (handles non-uniform scale) |
| `VIEW_MATRIX` | mat4 | in | World → view |
| `INV_VIEW_MATRIX` | mat4 | in | View → world |
| `PROJECTION_MATRIX` | mat4 | in | View → clip |
| `INV_PROJECTION_MATRIX` | mat4 | in | Clip → view |

> **DEPTH pitfall:** If you write `DEPTH` in any branch of `fragment()`, you must write it in every branch (including all `if/else` paths and early returns). Unwritten branches leave depth undefined, causing z-fighting artifacts. Pattern: initialize `float out_depth = FRAGCOORD.z;` and write `DEPTH = out_depth;` unconditionally at the end.

### light() Built-ins

| Name | Type | Access | Description |
|------|------|--------|-------------|
| `FRAGCOORD` | vec4 | in | Pixel center in screen space; xy=window pos (upper-left origin) |
| `NORMAL` | vec3 | in | Normal in view space |
| `UV` | vec2 | in | Primary UV |
| `UV2` | vec2 | in | Secondary UV |
| `VIEW` | vec3 | in | Fragment→camera (view space) |
| `LIGHT` | vec3 | in | Light direction (fragment→light, view space) |
| `LIGHT_COLOR` | vec3 | in | Light color × energy |
| `LIGHT_IS_DIRECTIONAL` | bool | in | true for DirectionalLight3D |
| `ATTENUATION` | float | in | Light attenuation |
| `ALBEDO` | vec3 | in | Albedo from fragment() |
| `METALLIC` | float | in | Metallic from fragment() |
| `ROUGHNESS` | float | in | Roughness from fragment() |
| `BACKLIGHT` | vec3 | in | Backlight from fragment() |
| `SPECULAR_AMOUNT` | float | in | Specular amount (use to scale SPECULAR_LIGHT output) |
| `DIFFUSE_LIGHT` | vec3 | inout | Accumulated diffuse light output |
| `SPECULAR_LIGHT` | vec3 | inout | Accumulated specular light output |
| `ALPHA` | float | inout | Alpha |
| `SCREEN_UV` | vec2 | in | Screen UV |
| `INV_VIEW_MATRIX` | mat4 | in | View → world (use to convert NORMAL to world space) |

**light() note:** Runs once per light per fragment, after `fragment()`. Not a replacement for `fragment()`. To convert NORMAL to world space: `(INV_VIEW_MATRIX * vec4(NORMAL, 0.0)).xyz`.

---

## Canvas Item Shader Built-ins

### vertex() Built-ins (canvas_item)

| Name | Type | Access | Description |
|------|------|--------|-------------|
| `VERTEX` | vec2 | inout | Vertex position in local space |
| `UV` | vec2 | inout | UV coordinates |
| `COLOR` | vec4 | inout | Vertex color |
| `POINT_SIZE` | float | inout | Point size |
| `VERTEX_ID` | int | in | Index in vertex buffer |
| `INSTANCE_ID` | int | in | Instance ID |
| `INSTANCE_CUSTOM` | vec4 | in | Per-instance custom data |
| `AT_LIGHT_PASS` | bool | in | true during light pass |
| `TEXTURE_PIXEL_SIZE` | vec2 | in | 1.0 / texture_size |
| `CUSTOM0` | vec4 | in | Custom vertex data |
| `CUSTOM1` | vec4 | in | Custom vertex data |
| `MODEL_MATRIX` | mat4 | in | Local → world (2D) |
| `CANVAS_MATRIX` | mat4 | in | Canvas → screen |
| `SCREEN_MATRIX` | mat4 | in | Screen transform |

### fragment() Built-ins (canvas_item)

| Name | Type | Access | Description |
|------|------|--------|-------------|
| `FRAGCOORD` | vec4 | in | Pixel position |
| `UV` | vec2 | in | UV coordinates |
| `COLOR` | vec4 | inout | Vertex color in (read); write to set output pixel color |
| `TEXTURE` | sampler2D | — | Main texture |
| `TEXTURE_PIXEL_SIZE` | vec2 | in | 1.0 / texture_size |
| `NORMAL_TEXTURE` | sampler2D | — | Normal texture |
| `SPECULAR_SHININESS_TEXTURE` | sampler2D | — | Specular shininess texture |
| `SPECULAR_SHININESS` | vec4 | in | Specular shininess value |
| `SCREEN_UV` | vec2 | in | Screen UV |
| `SCREEN_PIXEL_SIZE` | vec2 | in | 1.0 / screen_size |
| `REGION_RECT` | vec4 | in | Region rect for AtlasTexture |
| `TIME` | float | in | Global time |
| `AT_LIGHT_PASS` | bool | in | true during light pass |
| `NORMAL` | vec3 | inout | Normal for 2D lighting |
| `NORMAL_MAP` | vec3 | out | Normal from texture (assign raw [0,1] sample) |
| `NORMAL_MAP_DEPTH` | float | out | Normal map depth |
| `POINT_COORD` | vec2 | in | Point coordinate for point rendering |

### light() Built-ins (canvas_item)

| Name | Type | Access | Description |
|------|------|--------|-------------|
| `FRAGCOORD` | vec4 | in | Pixel position |
| `NORMAL` | vec3 | in | Normal |
| `COLOR` | vec4 | in | Color from fragment() |
| `UV` | vec2 | in | UV coordinates |
| `TEXTURE` | sampler2D | — | Main texture |
| `TEXTURE_PIXEL_SIZE` | vec2 | in | 1.0 / texture_size |
| `SCREEN_UV` | vec2 | in | Screen UV |
| `LIGHT_COLOR` | vec4 | in | Light color × energy |
| `LIGHT_ENERGY` | float | in | Light energy |
| `LIGHT_POSITION` | vec3 | in | Light position |
| `LIGHT_DIRECTION` | vec3 | in | Light direction |
| `LIGHT_IS_DIRECTIONAL` | bool | in | true for DirectionalLight2D |
| `LIGHT_VERTEX` | vec3 | inout | Vertex position for light calculations |
| `SPECULAR_SHININESS` | vec4 | in | Specular shininess |
| `SHADOW_MODULATE` | vec4 | inout | Shadow color modulation |
| `LIGHT` | vec4 | inout | Output light color (write to accumulate light) |

---

## Uniforms and Varyings

### Uniforms

```glsl
// Basic uniform — appears in material Inspector
uniform float _Offset;
uniform vec4 _Color : source_color;
uniform sampler2D _MainTex : source_color;

// With default value (after hint)
uniform float _Roughness : hint_range(0.0, 1.0) = 0.5;
uniform vec4 _Tint : source_color = vec4(1.0);

// Set from GDScript:
material.set_shader_parameter("_Offset", 0.5)
```

### Uniform Hints

**Semantic hints** (affect Inspector widget or color space conversion):

| Type | Hint | Effect |
|------|------|--------|
| `vec3, vec4` | `source_color` | Color picker; applies sRGB→linear conversion |
| `sampler2D` | `source_color` | Albedo/color texture; sRGB→linear |
| `sampler2D` | `hint_normal` | Normal map texture |
| `sampler2D` | `hint_default_white` | Defaults to opaque white |
| `sampler2D` | `hint_default_black` | Defaults to opaque black |
| `sampler2D` | `hint_default_transparent` | Defaults to transparent black |
| `sampler2D` | `hint_anisotropy` | Anisotropy flow map; defaults to right |
| `sampler2D` | `hint_roughness_r/g/b/a/normal/gray` | Roughness limiter channel |
| `sampler2D` | `hint_screen_texture` | Samples the screen (see caveat below) |
| `sampler2D` | `hint_depth_texture` | Samples the depth buffer |
| `sampler2D` | `hint_normal_roughness_texture` | Combined normal+roughness (Forward+ only) |
| `int, float` | `hint_range(min, max[, step])` | Slider in Inspector |
| `int` | `hint_enum("A", "B")` | Dropdown widget |

**Sampler state hints** (affect GPU texture sampling; combinable with semantic hints):

| Hint | Effect |
|------|--------|
| `repeat_disable` | Clamp wrap mode (no repeat) |
| `repeat_enable` | Repeat wrap mode |
| `filter_nearest` | Nearest filtering |
| `filter_linear` | Linear filtering |
| `filter_nearest_mipmap` | Nearest + mipmap |
| `filter_linear_mipmap` | Linear + mipmap |
| `filter_nearest_mipmap_anisotropic` | Nearest + mipmap + anisotropic |
| `filter_linear_mipmap_anisotropic` | Linear + mipmap + anisotropic |

Multiple hints: comma-separated after the colon:
```glsl
uniform sampler2D _MainTex : source_color, repeat_disable;
```

> **hint_screen_texture caveat:** Only captures objects rendered *before* this draw call. Sampling the screen texture while rendering to the same viewport creates a feedback loop (undefined behavior). Sample with `SCREEN_UV + offset`. For transparent objects, add `render_mode blend_mix, depth_draw_always` to ensure correct ordering.

### Uniform Groups

```glsl
group_uniforms Surface;
uniform float _Roughness : hint_range(0.0, 1.0) = 0.5;
uniform float _Metallic  : hint_range(0.0, 1.0) = 0.0;

group_uniforms Surface.Detail;
uniform sampler2D _DetailTex : source_color;

group_uniforms;  // close group
```

### Global Uniforms

Defined in Project Settings → Shader Globals. Available across all shaders:
```glsl
global uniform vec4 wind_direction;  // must exist in Project Settings
```

Set at runtime: `RenderingServer.global_shader_parameter_set("wind_direction", ...)`

### Per-instance Uniforms

```glsl
// Set per GeometryInstance3D, not per material
instance uniform vec4 my_color : source_color = vec4(1.0);
// Max 16 per shader; no textures or arrays
```

### Varyings

Pass data from `vertex()` to `fragment()` (or `fragment()` to `light()`):

```glsl
varying vec3 vertex_os;   // _os suffix = object space
varying vec2 custom_uv;

void vertex() {
    vertex_os = VERTEX;   // capture before transform
    custom_uv = UV * 2.0;
}

void fragment() {
    // vertex_os and custom_uv available here
    vec3 world_pos = (MODEL_MATRIX * vec4(vertex_os, 1.0)).xyz;
}
```

Interpolation qualifiers:
```glsl
varying flat vec3 flat_color;   // no interpolation
varying smooth vec3 color;      // perspective-correct (default)
```

**Restrictions:** Varyings cannot be assigned in custom functions or in `light()`.

---

## ShaderInclude

Reusable shader code in `.gdshaderinc` files. Only `res://` absolute paths are valid — relative paths and `user://` paths are not supported and cause a compile error.

```glsl
// res://shaders/utils.gdshaderinc
// Returns out_min when in_max == in_min (avoids division by zero / NaN propagation)
float remap(float v, float in_min, float in_max, float out_min, float out_max) {
    float range = in_max - in_min;
    if (abs(range) < 1e-6) return out_min;
    return out_min + (v - in_min) / range * (out_max - out_min);
}
```

```glsl
// In any .gdshader file — #include before processor functions
shader_type spatial;
#include "res://shaders/utils.gdshaderinc"

void fragment() {
    float remapped = remap(UV.x, 0.0, 1.0, -1.0, 1.0);
    ALBEDO = vec3(remapped * 0.5 + 0.5);
}
```

Functions must be declared before use (GPU reads top-to-bottom). Place `#include` directives before processor functions.

---

## Particle Shaders

Only available with `GPUParticles2D` / `GPUParticles3D`. CPU-based particles cannot use particle shaders.

### Structure

```glsl
shader_type particles;

void start() {
    // Runs once when particle spawns (RESTART_* flags are true)
    // Initialize TRANSFORM, VELOCITY, COLOR, CUSTOM here
}

void process() {
    // Runs every frame while particle is ACTIVE
    // RESTART (process-only flag) is true on the particle's first process() frame
    // — distinct from RESTART_* flags in start()
    // Update TRANSFORM, VELOCITY, COLOR, CUSTOM here
}
```

### Lifecycle and State Persistence

Unlike other shader types, **particle state persists across frames**. `TRANSFORM`, `COLOR`, `CUSTOM`, and `USERDATA1–6` written in one frame are available in the next. This enables multi-frame simulation (trails, physics, etc.).

- `start()` runs when a particle is first emitted or restarted
- `process()` runs every simulation frame for active particles
- `ACTIVE = false` deactivates the particle (it stops rendering and processing)
- `RESTART` (in `process()`) is `true` only on the particle's first process frame

### Render Modes (particles)

| Mode | Description |
|------|-------------|
| `keep_data` | Don't clear state on system restart |
| `disable_force` | Ignore attractor forces |
| `disable_velocity` | Ignore VELOCITY value |
| `collision_use_scale` | Scale particle size for collision detection |

### Built-ins: start() and process()

| Name | Type | Access | Description |
|------|------|--------|-------------|
| `TRANSFORM` | mat4 | inout | Particle transform (position in `[3].xyz`); persists across frames |
| `VELOCITY` | vec3 | inout | Particle velocity |
| `COLOR` | vec4 | inout | Particle color; accessible in mesh shader as `COLOR`; persists across frames |
| `CUSTOM` | vec4 | inout | Custom data; accessible in mesh shader as `INSTANCE_CUSTOM`; persists across frames |
| `ACTIVE` | bool | inout | true = particle alive; set false to deactivate |
| `MASS` | float | inout | Particle mass for attractors (default 1.0) |
| `LIFETIME` | float | in | Total particle lifetime in seconds |
| `DELTA` | float | in | Frame delta time |
| `INDEX` | uint | in | Particle index within the pool |
| `NUMBER` | uint | in | Unique emission counter (increments each spawn) |
| `EMISSION_TRANSFORM` | mat4 | in | Emitter node transform (for non-local systems) |
| `RANDOM_SEED` | uint | in | Per-particle random seed base |
| `EMITTER_VELOCITY` | vec3 | in | Velocity of the GPUParticles node |
| `INTERPOLATE_TO_END` | float | in | `interp_to_end` property value |
| `AMOUNT_RATIO` | float | in | `amount_ratio` property value [0.0, 1.0] |
| `USERDATA1` | vec4 | inout | User-defined persistent data (persists across frames like CUSTOM) |
| `USERDATA2` | vec4 | inout | User-defined persistent data |
| `USERDATA3` | vec4 | inout | User-defined persistent data |
| `USERDATA4` | vec4 | inout | User-defined persistent data |
| `USERDATA5` | vec4 | inout | User-defined persistent data |
| `USERDATA6` | vec4 | inout | User-defined persistent data |
| `TIME` | float | in | Global time |

### Built-ins: start() only

| Name | Type | Access | Description |
|------|------|--------|-------------|
| `RESTART_POSITION` | bool | in | true if restarted or emitted without position flag |
| `RESTART_ROT_SCALE` | bool | in | true if restarted or emitted without rot/scale flag |
| `RESTART_VELOCITY` | bool | in | true if restarted or emitted without velocity flag |
| `RESTART_COLOR` | bool | in | true if restarted or emitted without color flag |
| `RESTART_CUSTOM` | bool | in | true if restarted or emitted without custom flag |

### Built-ins: process() only

| Name | Type | Access | Description |
|------|------|--------|-------------|
| `RESTART` | bool | in | true on first process frame for this particle |
| `COLLIDED` | bool | in | true if collided with a particle collider |
| `COLLISION_NORMAL` | vec3 | in | Normal of last collision (zero if none) |
| `COLLISION_DEPTH` | float | in | Depth of last collision (0.0 if none) |
| `ATTRACTOR_FORCE` | vec3 | in | Combined attractor force at particle position |

### emit_subparticle()

Emits a child particle from a sub-emitter. Only the properties matching `flags` are applied.

```glsl
bool emit_subparticle(mat4 xform, vec3 velocity, vec4 color, vec4 custom, uint flags)
```

**Flags:**
- `FLAG_EMIT_POSITION` — use `xform[3].xyz` as position
- `FLAG_EMIT_ROT_SCALE` — use `xform` rotation/scale
- `FLAG_EMIT_VELOCITY` — use `velocity`
- `FLAG_EMIT_COLOR` — use `color`
- `FLAG_EMIT_CUSTOM` — use `custom`

```glsl
void process() {
    if (RESTART) {
        // Emit a child at offset position with red color
        mat4 child_xform = mat4(1.0);
        child_xform[3].xyz = TRANSFORM[3].xyz + vec3(1.0, 0.0, 0.0);
        emit_subparticle(
            child_xform,
            vec3(0.0, 2.0, 0.0),          // velocity
            vec4(1.0, 0.0, 0.0, 1.0),     // red
            vec4(0.0),                     // custom
            FLAG_EMIT_POSITION | FLAG_EMIT_VELOCITY | FLAG_EMIT_COLOR
        );
    }
}
```

### Common Particle Patterns

**Initialization in start():**
```glsl
shader_type particles;

void start() {
    if (RESTART_POSITION) {
        TRANSFORM[3].xyz = EMISSION_TRANSFORM[3].xyz;
    }
    if (RESTART_VELOCITY) {
        float angle = float(NUMBER) * 2.399963;  // golden angle spread
        VELOCITY = vec3(cos(angle), 2.0, sin(angle));
    }
    if (RESTART_COLOR) {
        COLOR = vec4(1.0);
    }
    if (RESTART_CUSTOM) {
        CUSTOM.y = 0.0;  // initialize lifetime phase manually (pure particle shader)
    }
}
```

**Per-frame simulation in process():**
```glsl
void process() {
    // Manually track lifetime phase (only needed in pure particle shaders;
    // ParticleProcessMaterial populates CUSTOM.y automatically)
    // Guard against LIFETIME == 0 to avoid NaN/Inf
    CUSTOM.y = clamp(CUSTOM.y + DELTA / max(LIFETIME, 1e-6), 0.0, 1.0);
    float age = CUSTOM.y;

    COLOR.a = 1.0 - age;             // fade out
    VELOCITY.y -= 9.8 * DELTA;       // gravity
    TRANSFORM[3].xyz += VELOCITY * DELTA;  // integrate position (TRANSFORM persists)
    if (age >= 1.0) {
        ACTIVE = false;
    }
}
```

**State persistence** — TRANSFORM persists, so position integrates naturally:
```glsl
void process() {
    TRANSFORM[3].xyz += VELOCITY * DELTA;  // no need to re-read initial pos
}
```

**Accessing particle data in the mesh shader:**
- `COLOR` from particle shader → `COLOR` in mesh vertex shader (requires `vertex_color_use_as_albedo` on StandardMaterial3D, or read `COLOR` directly in a ShaderMaterial)
- `CUSTOM` from particle shader → `INSTANCE_CUSTOM` in mesh vertex shader (x=rotation angle, y=lifetime phase, z=anim frame by default with ParticleProcessMaterial)
