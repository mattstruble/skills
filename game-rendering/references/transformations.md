# Transformations and Coordinate Spaces

Covers the five coordinate spaces in a 3D rendering pipeline, the matrices that bridge them, and the math for constructing each transform. Read this when you need matrix formulas, are debugging projection or orientation issues, or want to understand why each space exists.

For a complete worked Odin implementation, see Pekar Parts II–III: https://marianpekar.com/blog/software-renderer-in-odin-from-scratch-part-ii

---

## The Five Coordinate Spaces

```
  [Model Space]
       |  Model Matrix = T × R × S
       v
  [World Space]
       |  View Matrix (inverse of camera transform)
       v
  [View Space]
       |  Projection Matrix (perspective or orthographic)
       v
  [Clip Space]
       |  Perspective Division (÷ w)
       v
  [NDC Space]   x,y,z ∈ [-1, +1]
       |  Viewport Transform
       v
  [Screen Space]  (x,y) in pixels
```

| Space | Origin | Axes | Purpose |
|---|---|---|---|
| **Model** | Object center | Defined by artist | Mesh data as authored |
| **World** | Scene origin | Shared by all objects | Positions objects relative to each other |
| **View** | Camera position | Camera looks along -Z (right-handed) | Simplifies projection math |
| **Clip** | Camera position | Homogeneous (x,y,z,w) | Enables perspective division; clipping against frustum planes |
| **NDC** | Center of screen | [-1,+1] cube | Hardware-independent normalized space |
| **Screen** | Top-left corner | Pixels (y increases downward) | Final pixel addresses |

---

## Coordinate System Handedness

**Right-handed** (OpenGL convention): X points right, Y points up, Z points *toward the viewer* (out of the screen). The camera looks along -Z.

**Left-handed** (Direct3D convention): X points right, Y points up, Z points *away from the viewer* (into the screen). The camera looks along +Z.

**Rule: pick one and stay consistent.** Mixing handedness causes mirrored geometry or inverted depth. The matrices below use right-handed convention. To convert: negate the Z column of the view matrix and flip the sign of the Z terms in the projection matrix.

---

## Homogeneous Coordinates

3D transformations including translation cannot be expressed as a 3×3 matrix multiplication — translation requires addition. Homogeneous coordinates solve this by adding a fourth component `w`:

- A **point** is represented as `(x, y, z, 1)` — w=1 means "this is a position"
- A **direction** is represented as `(x, y, z, 0)` — w=0 means "this is a vector; translation has no effect"

This lets all transforms (translation, rotation, scale, projection) be expressed as 4×4 matrix multiplications, which can be composed by multiplication.

---

## Individual Transform Matrices

All matrices below are in column-major form (standard mathematical convention). Apply as `M × v` where `v` is a column vector.

### Identity Matrix

```
I = | 1  0  0  0 |
    | 0  1  0  0 |
    | 0  0  1  0 |
    | 0  0  0  1 |
```

Multiplying by I leaves the vector unchanged. The starting point for building composite transforms.

### Translation Matrix

Moves a point by `(tx, ty, tz)`. Has no effect on direction vectors (w=0).

```
T(tx, ty, tz) = | 1  0  0  tx |
                | 0  1  0  ty |
                | 0  0  1  tz |
                | 0  0  0   1 |
```

### Scale Matrix

Scales along each axis independently.

```
S(sx, sy, sz) = | sx  0   0   0 |
                |  0  sy  0   0 |
                |  0   0  sz  0 |
                |  0   0   0  1 |
```

Uniform scale: `sx = sy = sz`. Non-uniform scale after rotation causes shearing — apply scale before rotation in the model matrix.

### Rotation Matrices

Rotation around the **X axis** by angle θ:

```
Rx(θ) = | 1    0       0    0 |
        | 0   cos θ  -sin θ  0 |
        | 0   sin θ   cos θ  0 |
        | 0    0       0    1 |
```

Rotation around the **Y axis** by angle θ:

```
Ry(θ) = |  cos θ   0   sin θ  0 |
        |    0     1     0    0 |
        | -sin θ   0   cos θ  0 |
        |    0     0     0    1 |
```

Rotation around the **Z axis** by angle θ:

```
Rz(θ) = | cos θ  -sin θ  0  0 |
        | sin θ   cos θ  0  0 |
        |   0       0    1  0 |
        |   0       0    0  1 |
```

### Combined Rotation (YXZ — Yaw, Pitch, Roll)

Applying yaw α (around Y), pitch β (around X), roll γ (around Z) in YXZ order gives the combined 3×3 rotation block:

```
R = Ry(α) × Rx(β) × Rz(γ)
```

The full 3×3 form (omitting the 4th row/column for clarity):

```
R = | cos α cos γ + sin α sin β sin γ   cos γ sin α sin β - cos α sin γ   cos β sin α |
    | cos β sin γ                        cos β cos γ                       -sin β      |
    | cos α sin β sin γ - sin α cos γ   sin α sin γ + cos α sin β cos γ   cos α cos β |
```

**Order matters.** YXZ is a common game convention (yaw first, then pitch, then roll). Different orders produce different results. Document your convention and stay consistent.

---

## Model Matrix

The model matrix places an object in world space. It is the composition of scale, rotation, and translation:

```
M_model = T × R × S
```

Applied right-to-left to a vertex: scale first, then rotate, then translate. This is the correct order because:
1. Scale the mesh to the right size
2. Rotate it to the right orientation
3. Move it to the right position in the world

Reversing the order (e.g., translate then rotate) would rotate around the world origin instead of the object's center.

---

## View Matrix

The view matrix transforms world-space coordinates into view space, where the camera sits at the origin looking along -Z.

**Construction from eye, target, and up:**

```
forward = normalize(eye - target)        // camera looks along -forward
right   = normalize(up_global × forward) // right vector (cross product)
up      = forward × right                // recomputed up (orthogonalized)
```

The view matrix is then:

```
V = | right.x    right.y    right.z    -(right · eye)   |
    | up.x       up.y       up.z       -(up · eye)      |
    | forward.x  forward.y  forward.z  -(forward · eye) |
    | 0          0          0           1               |
```

The `-(vec · eye)` terms in the right column encode the translation component: they move the world so the camera is at the origin.

**Why `eye - target` for forward?** In right-handed coordinates, the camera looks along -Z. `eye - target` points *away* from the target, which is the +Z direction in view space. The camera's view direction is then `-forward` = `normalize(target - eye)`.

**Gimbal lock warning**: When `forward` is parallel to `up_global` (camera looking straight up or straight down), `up_global × forward` is the zero vector and `normalize` is undefined. Mitigations: (1) clamp pitch to slightly less than ±90°; (2) detect the degenerate case and substitute a different `up_global` (e.g., switch to `(0, 0, 1)` when looking nearly along Y); (3) use quaternions for camera orientation to avoid this singularity entirely.

---

## Perspective Projection Matrix

Maps view-space geometry into clip space, encoding depth into the `w` component so that perspective division produces the correct foreshortening.

Let:
- `f = 1 / tan(fov_y / 2)` — the focal length (fov_y in radians)
- `a` — aspect ratio (width / height)
- `n` — near plane distance (positive value)
- `far` — far plane distance (positive value)

```
P_persp = | f/a    0         0                    0          |
          |  0     f         0                    0          |
          |  0     0   -(far+n)/(far-n)   -(2*far*n)/(far-n) |
          |  0     0        -1                    0          |
```

The `-1` in the bottom row copies `-z` into `w`. After perspective division (`÷ w`), distant points (large `|z|`) are divided by a larger value, making them appear smaller.

**Common mistake**: passing FOV in degrees instead of radians. `tan()` expects radians. Convert: `fov_radians = fov_degrees * π / 180`.

---

## Orthographic Projection Matrix

Maps a rectangular box (left/right/top/bottom/near/far) to the NDC cube. No perspective division effect — `w` stays 1.

For a symmetric frustum with half-width `r` (= aspect ratio), half-height `1`, near `n`, far `far`:

```
P_ortho = | 1/r    0       0              0          |
          |  0     1       0              0          |
          |  0     0   -2/(far-n)   -(far+n)/(far-n) |
          |  0     0       0              1          |
```

General form (asymmetric, for left `l`, right `r`, bottom `b`, top `t`):

```
P_ortho = | 2/(r-l)    0        0          -(r+l)/(r-l) |
          |    0     2/(t-b)    0          -(t+b)/(t-b) |
          |    0       0    -2/(far-n)    -(far+n)/(far-n) |
          |    0       0        0               1        |
```

**Depth in orthographic**: because `w = 1` always, `1/w` is useless for depth discrimination. Instead, store `clip.z` directly (which equals NDC z since w=1). The near plane maps to `clip.z = -1` and the far plane maps to `clip.z = +1` — closer objects have *smaller* `clip.z`. Use `d < zbuffer` with initialization to `+1` (or `float.MAX`) so the first draw always passes and closer (smaller) values win — see `visibility.md` for the full depth test.

---

## Perspective Division (Clip → NDC)

After the projection matrix, a vertex is in clip space: `(cx, cy, cz, cw)`.

Divide all components by `w`:

```
ndcX = cx / cw
ndcY = cy / cw
ndcZ = cz / cw
```

Result: NDC coordinates in `[-1, +1]` on each axis (for points inside the frustum).

**Why store 1/w**: The reciprocal `1/cw` is linear in screen space (it varies linearly as you move across a triangle's projected image). This linearity is what makes perspective-correct interpolation possible — see `texturing.md`.

---

## NDC to Screen Space

Convert NDC coordinates to pixel coordinates. Screen origin is top-left; Y increases downward.

```
screenX = (ndcX * 0.5 + 0.5) * screenWidth
screenY = (-ndcY * 0.5 + 0.5) * screenHeight
```

The negation of `ndcY` flips the Y axis: NDC has Y=+1 at the top, but screen space has Y=0 at the top.

**Depth for Z-buffer**: store `ndcZ` (or `1/cw` depending on your Z-buffer convention) per pixel. See `visibility.md`.

---

## Summary: Matrix Composition

To transform a model-space vertex all the way to screen space:

```
clip_pos = P × V × M × vertex_model

// Then:
ndc = clip_pos.xyz / clip_pos.w
screen = viewport_transform(ndc)
```

Where:
- `M` = model matrix (T × R × S)
- `V` = view matrix
- `P` = projection matrix (perspective or orthographic)

The combined `P × V × M` is often called the **MVP matrix** and can be precomputed once per object per frame.
