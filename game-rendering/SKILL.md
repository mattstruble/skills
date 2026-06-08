---
name: game-rendering
description: You MUST consult this skill when reasoning about 3D rendering pipelines — coordinate spaces (model/world/view/clip/screen), perspective vs orthographic projection, affine transformations, triangle rasterization, barycentric coordinates, z-buffering, backface and frustum culling, UV mapping with perspective-correct interpolation, and lighting models (flat, Phong, multi-light blending). Also trigger when implementing a software renderer, debugging projection issues, or reasoning about what a GPU does internally. NOT for shader implementation in a specific engine (see godot-shader). NOT for art direction or visual legibility (see game-visuals). NOT for engine-specific renderer configuration.
---

# 3D Rendering Pipeline

Engine-agnostic reference for 3D rendering concepts: coordinate spaces, transformations, rasterization, visibility, texturing, and lighting. Synthesized from Marian Pekar's *3D Software Renderer in Odin from Scratch* tutorial series (marianpekar.com).

**Relationship to other skills**: This skill covers the *what* and *why* of rendering math. For Odin/raylib implementation specifics, see `odin-gamedev/references/raylib-rendering.md`. For shader implementation in Godot, see `godot-shader`. For art direction and visual communication, see `game-visuals`. For diagnosing frame-rate and GPU bottlenecks, see `game-performance`.

---

## Pipeline Overview

A 3D renderer transforms geometry through a series of coordinate spaces before producing pixels. Each space has a distinct purpose; each transition is a matrix multiplication.

```
  [Model Space]
       |
       | Model Matrix (T × R × S)
       v
  [World Space]
       |
       | View Matrix (camera transform)
       v
  [View Space]
       |
       | Projection Matrix (perspective or orthographic)
       v
  [Clip Space]
       |
       | Perspective Division (÷ w)
       v
  [NDC Space]   (-1 to +1 on each axis)
       |
       | Viewport Transform
       v
  [Screen Space]  (pixel coordinates)
```

| Space | What it represents | Key operation |
|---|---|---|
| **Model** | Geometry relative to the object's own origin | Artist-authored mesh data |
| **World** | All objects in a shared coordinate system | Model matrix positions/orients the object |
| **View** | World seen from the camera's perspective; camera at origin | View matrix inverts the camera transform |
| **Clip** | Homogeneous coordinates ready for clipping | Projection matrix encodes FOV, aspect, near/far |
| **NDC** | Normalized Device Coordinates; cube [-1,1]³ | Divide x,y,z by w |
| **Screen** | Integer pixel coordinates | Viewport scale and Y-flip |

See `references/transformations.md` for the full matrix forms and derivations.

---

## Mesh Data

A mesh is the input to the rendering pipeline. At minimum it contains:

| Field | Type | Description |
|---|---|---|
| `vertices` | `[]Vector3` | Positions in model space |
| `normals` | `[]Vector3` | Surface normals per vertex (unit vectors) |
| `uvs` | `[]Vector2` | Texture coordinates per vertex, range [0,1] |
| `triangles` | `[]Triangle` | Index triples into the vertex/normal/UV arrays |

A `Triangle` stores three indices: one for each vertex, normal, and UV. This allows vertices to be shared between triangles (reducing memory) while allowing different normals or UVs at the same position (required at hard edges and UV seams).

**OBJ file format** (Pekar Part IX) stores exactly this structure: `v` lines for vertices, `vn` for normals, `vt` for UVs, `f` lines for faces with `vertex/uv/normal` index triples. Loading an OBJ means parsing these lines and building the arrays above.

---

## Per-Frame Rendering Loop

The full pipeline, from scene data to pixels, runs once per frame:

```
// Per frame:
clear(framebuffer, background_color)
clear(zbuffer, 0)          // 0 = "nothing drawn"; 1/w convention (larger = closer)

for each model in scene:
    M = model.transform.matrix()         // T × R × S

    for each triangle in model.mesh:
        // 1. Transform vertices to view space
        v0_view = V × M × triangle.v0
        v1_view = V × M × triangle.v1
        v2_view = V × M × triangle.v2

        // 2. Backface cull (in view space)
        if is_backfacing(v0_view, v1_view, v2_view): continue

        // 3. Project to clip space, then NDC
        v0_clip = P × v0_view
        v1_clip = P × v1_view
        v2_clip = P × v2_view

        // 4. Frustum cull
        if outside_frustum(v0_clip, v1_clip, v2_clip): continue

        // 5. Perspective divide → NDC
        v0_ndc = v0_clip.xyz / v0_clip.w
        ...

        // 6. NDC → screen space
        v0_screen = viewport_transform(v0_ndc)
        ...

        // 7. Rasterize: fill pixels, Z-test, interpolate UVs/normals, shade
        rasterize_triangle(v0_screen, v1_screen, v2_screen, ...)
```

Each step is covered in the reference files. The key insight is that culling happens as early as possible — backface culling in view space, frustum culling in clip space — to avoid rasterizing geometry that produces no pixels.

---

## Decision Tables

### Perspective vs. Orthographic Projection

| Criterion | Perspective | Orthographic |
|---|---|---|
| Objects shrink with distance | Yes — natural depth cue | No — parallel lines stay parallel |
| Typical use | 3D games, first/third-person views | CAD, 2D-style 3D, isometric games |
| Depth stored as | Non-linear (1/z distribution) | Linear (clip.z; range [-1, +1]) |
| UV interpolation | Must be perspective-correct | Affine interpolation is exact |
| Switch at runtime | Yes — swap projection matrix | Yes — swap projection matrix |

**Rule**: Use perspective for any scene where depth perception matters. Use orthographic when you want to preserve scale across distance (e.g., strategy games, blueprint views).

### Flat vs. Phong Shading

| Criterion | Flat Shading | Phong Shading |
|---|---|---|
| Normal computed | Once per triangle | Per pixel (interpolated from vertices) |
| Visual result | Faceted, hard edges between triangles | Smooth gradients across surfaces |
| Performance cost | Low — one dot product per triangle | Higher — dot product per pixel |
| Best for | Low-poly stylized art, early prototyping | Smooth organic surfaces |
| Requires | Triangle normal | Per-vertex normals in mesh data |

### Culling Strategy

| Technique | What it eliminates | Cost | When to apply |
|---|---|---|---|
| **Backface culling** | Triangles facing away from camera | Very low (one dot product) | Always in closed meshes |
| **Frustum culling** | Triangles outside the view volume | Low (bounding box test) | Always |
| **Occlusion culling** | Geometry hidden behind other geometry | Medium–high | Complex scenes with many overlapping objects |

**Note**: Backface and frustum culling are nearly free and should always be enabled. Occlusion culling requires spatial data structures and is out of scope here.

---

## Key Invariants

**Handedness consistency.** Pick right-handed or left-handed coordinates and stay consistent throughout the pipeline. Mixing conventions causes mirrored geometry or inverted depth. Right-handed is the mathematical convention (OpenGL, Vulkan default); left-handed is common in Direct3D. The view matrix construction and projection matrix signs depend on this choice.

**Perspective division.** After the projection matrix, clip-space coordinates are in homogeneous form `(x, y, z, w)`. Dividing by `w` gives NDC. This division is what makes distant objects appear smaller — the projection matrix encodes distance into `w`.

**Store 1/w for perspective-correct interpolation.** Linear interpolation in screen space is only correct for attributes that are linear in screen space. Depth and UV coordinates are *not* linear in screen space after perspective projection — they are linear in *view space* (before projection). What *is* linear in screen space is `1/w`, `U/w`, and `V/w`. Storing `1/w` (the reciprocal of clip-space w) and interpolating it linearly in screen space, then dividing back, gives perspective-correct results. This is why the Z-buffer stores `1/w` rather than the raw view-space depth.

**Winding order determines front faces.** Counter-clockwise (CCW) winding is front-facing in right-handed systems. Backface culling depends on this convention being consistent across all meshes.

**Model matrix order: T × R × S.** Translation, then rotation, then scale. Applied right-to-left to a vertex: scale first, then rotate, then translate. Changing this order produces different results — scale after rotation causes shearing.

---

## Common Bugs — Symptoms → Cause

| Symptom | Likely Cause | Reference |
|---|---|---|
| Texture looks like it slides or distorts as the triangle rotates | Affine UV interpolation — not dividing by w | `references/texturing.md` |
| Pixels overdraw incorrectly; wrong geometry appears in front | No Z-buffer, or depth test direction reversed | `references/visibility.md` |
| Back faces of mesh are visible | Backface culling disabled or winding order inconsistent | `references/visibility.md` |
| Model disappears when camera gets close | Near-plane clipping not handled; geometry behind near plane projects incorrectly | `references/visibility.md` |
| Model looks inside-out or mirrored | Coordinate system handedness mismatch | `references/transformations.md` |
| Projection looks wrong (too wide, too narrow, stretched) | Incorrect aspect ratio in projection matrix, or FOV in wrong units (degrees vs radians) | `references/transformations.md` |
| Lighting is always maximum or always zero | Normal not normalized after interpolation, or dot product not clamped to [0,1] | `references/lighting.md` |
| Flat-shaded triangles show seams at edges | Expected — flat shading is per-triangle; switch to Phong for smooth surfaces | `references/lighting.md` |
| Z-fighting (flickering between two surfaces) | Two surfaces at nearly identical depth; Z-buffer precision insufficient | `references/visibility.md` |
| Triangle rasterization has gaps or double-drawn edges | Incorrect scanline bounds; off-by-one in FTFB split | `references/rasterization.md` |

---

## What's Not Covered Here

These topics are out of scope for this skill. They are mentioned only to orient you toward the right resource.

| Topic | Where to look |
|---|---|
| Specular highlights (Blinn-Phong, Phong reflection model) | `godot-shader/references/lighting.md`; external: learnopengl.com |
| Normal/bump mapping | `godot-shader/references/lighting.md` |
| Shadow mapping | External: learnopengl.com/Advanced-Lighting/Shadows |
| Anti-aliasing (MSAA, FXAA, TAA) | External: GPU vendor documentation |
| Physically-based rendering (PBR) | External: learnopengl.com/PBR |
| GPU pipeline stages (vertex shaders, fragment shaders, rasterizer hardware) | `godot-shader`; external: Khronos OpenGL specification |
| Post-processing effects | `godot-shader/references/vfx-and-postprocessing.md` |
| Texture filtering (bilinear, trilinear, anisotropic) | External: GPU documentation |
| Spatial data structures for occlusion | External: game-engine-specific documentation |

---

## Worked Example: Tracing One Vertex Through the Pipeline

To make the coordinate space transitions concrete, here is a single vertex traced through each stage.

**Setup**: A cube vertex at model-space position `(1, 1, 1)`. The cube is scaled by 0.5, rotated 45° around Y, and placed at world position `(0, 0, -5)`. The camera is at the origin looking along -Z. FOV = 90°, aspect = 1.0, near = 0.1, far = 100.

```
// Model space
v_model = (1, 1, 1, 1)

// World space (after model matrix: scale 0.5, rotate 45° Y, translate (0,0,-5))
// Scale: (0.5, 0.5, 0.5)
// Rotate 45° Y: x' = 0.5*cos45 + 0.5*sin45 = 0.707, y' = 0.5, z' = -0.5*sin45 + 0.5*cos45 = 0
// Translate (0,0,-5): (0.707, 0.5, -5.0)
v_world = (0.707, 0.5, -5.0, 1)

// View space (camera at origin looking along -Z; view matrix is identity here)
v_view = (0.707, 0.5, -5.0, 1)

// Clip space (after perspective projection, FOV=90°, f=1/tan(45°)=1.0, aspect=1.0)
// clip.x = f/a * x = 0.707, clip.y = f * y = 0.5
// clip.z = -(far+n)/(far-n)*z - 2*far*n/(far-n) ≈ 4.805
// clip.w = -view.z = 5.0
v_clip = (0.707, 0.5, 4.805, 5.0)

// NDC (divide by w=5.0)
v_ndc = (0.141, 0.1, 0.961, 1)

// 1/w stored for depth and perspective-correct interpolation
inv_w = 1 / 5.0 = 0.2

// Screen space (800×600 viewport)
screenX = (0.141 * 0.5 + 0.5) * 800  ≈ 457   // right of center
screenY = (-0.1  * 0.5 + 0.5) * 600  = 270   // Y flipped; slightly above center
```

The vertex lands at approximately `(457, 270)` — right of center and slightly above the horizontal midline, which is correct for a vertex that is offset to the right and slightly above the camera's line of sight.

**Key observations from this trace**:
- The `w` component after projection equals the negated view-space z (`-(-5.0) = 5.0`)
- `1/w = 0.2` is stored for depth testing and perspective-correct UV interpolation
- The Y-flip in the viewport transform accounts for the screen's top-left origin
- The x-offset from rotation (0.707 world units) is visible in the final screen position (457 vs center 400)

---

## References

| File | Contents | Read when... |
|---|---|---|
| `references/transformations.md` | Coordinate spaces, all transformation matrices, view matrix construction, projection matrices, NDC→screen | You need matrix math, projection formulas, or are debugging coordinate space issues |
| `references/rasterization.md` | FTFB triangle rasterization, line drawing, barycentric coordinates | You're implementing a rasterizer or need to interpolate per-vertex attributes |
| `references/visibility.md` | Z-buffer, backface culling, frustum culling | You need depth testing or culling logic |
| `references/texturing.md` | UV mapping, texture sampling, perspective-correct interpolation | You're applying textures to triangles |
| `references/lighting.md` | Flat shading, Phong shading, multi-light blending, ambient/diffuse | You're implementing a lighting model |

---

## Relationship to Other Skills

**godot-shader** — Implements rendering concepts as GDSL shaders in Godot 4.x. When this skill explains the math (e.g., Lambertian diffuse), godot-shader provides the concrete `.gdshader` implementation. Use this skill to understand the concept; use godot-shader to write the code.

**game-visuals** — Art direction and visual communication: contrast, palette, legibility, simulation readability. This skill handles the rendering *pipeline*; game-visuals handles what the rendered image should *communicate* to the player.

**game-performance** — Diagnosing and fixing frame-rate problems: GPU bottlenecks, fill-rate, bandwidth, CPU submission overhead. This skill explains how the pipeline works; game-performance explains how to measure and fix it when it's too slow.

**odin-gamedev** — Odin/raylib implementation specifics. `odin-gamedev/references/raylib-rendering.md` will contain a complete worked implementation of this pipeline in Odin using raylib, based on Pekar's tutorial series (in progress).

---

## Further Reading

- Marian Pekar, *3D Software Renderer in Odin from Scratch* (14-part series): https://marianpekar.com/blog/software-renderer-in-odin-from-scratch-part-i — a complete ground-up implementation covering every topic in this skill
- [learnopengl.com](https://learnopengl.com) — Comprehensive OpenGL tutorial covering the same pipeline concepts with GLSL shader implementations
- [scratchapixel.com](https://www.scratchapixel.com) — Deep mathematical derivations of rasterization, projection, and shading from first principles
