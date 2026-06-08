# Texturing: UV Mapping and Perspective-Correct Interpolation

Covers UV coordinates, texture sampling, and the critical difference between affine and perspective-correct UV interpolation. Read this when applying textures to 3D geometry, debugging texture distortion, or implementing UV interpolation in a rasterizer.

For a complete worked Odin implementation, see Pekar Part VIII: https://marianpekar.com/blog/software-renderer-in-odin-from-scratch-part-viii

---

## UV Coordinates

UV coordinates are 2D values stored per-vertex that specify which point on a texture maps to that vertex. The name "UV" distinguishes the texture axes from the spatial axes X, Y, Z.

- **U** is the horizontal axis of the texture
- **V** is the vertical axis of the texture
- Coordinates typically range from `[0, 1]`, where `(0, 0)` is one corner and `(1, 1)` is the opposite corner

**Origin convention**: In most 3D tools and file formats (including OBJ), UV origin `(0, 0)` is at the **bottom-left** of the texture. Some rendering systems (Direct3D, some game engines) use **top-left** as the origin. Be consistent — mixing conventions causes textures to appear vertically flipped.

UV coordinates outside `[0, 1]` are handled by the wrap mode (see below).

---

## Texture Sampling

To sample a texture at UV coordinates `(U, V)`, convert to integer texel indices. Use the two-modulo form to handle negative UV values safely (valid with repeat wrap):

```
// Always-positive modulo: handles negative UV inputs in all languages
texX = ((int(U * texWidth)  % texWidth)  + texWidth)  % texWidth
texY = ((int(V * texHeight) % texHeight) + texHeight) % texHeight
texel = pixels[texY * texWidth + texX]
```

The outer `+ texWidth) % texWidth` ensures the result is non-negative even when `int(U * texWidth)` is negative (e.g., `U = -0.1`). In languages where `%` on a negative dividend returns a negative result (C, C++, Odin, Rust, Java), a single modulo is not sufficient.

### Power-of-2 Optimization

When texture dimensions are powers of 2 (e.g., 256, 512, 1024), replace modulo with a bitmask:

```
texX = int(U * texWidth)  & (texWidth  - 1)
texY = int(V * texHeight) & (texHeight - 1)
```

`x & (size - 1)` is exactly equivalent to `x % size` for any non-negative integer `x` when `size = 2^k`. The bitmask avoids integer division, which is significantly slower on most hardware.

**Why it works**: `2^k - 1` in binary is all 1s in the lower k bits. ANDing with it keeps only the lower k bits of `x`, which is the same as `x mod 2^k`.

> **Implementation warning**: `int(U * texWidth)` can overflow for very large texture dimensions. Use a wider integer type (e.g., int64) before truncating if texWidth is large.
>
> The bitmask optimization requires a **non-negative** operand. If UV coordinates can be negative (e.g., `U = -0.1` with repeat wrap), `int(U * texWidth)` is negative and `negative_int & (size - 1)` does not wrap correctly — it produces a negative index, causing an out-of-bounds read. Either clamp UVs to `[0, 1]` before sampling, or use the always-positive modulo form:
> ```
> texX = ((int(U * texWidth) % texWidth) + texWidth) % texWidth
> ```
> This two-modulo pattern handles negative inputs correctly in all languages.

### Wrap Modes

| Mode | Behavior | UV range |
|---|---|---|
| **Repeat** | Tile the texture; `U=1.1` samples the same as `U=0.1` | Unbounded |
| **Clamp** | Saturate to the edge texel; `U=1.5` samples the same as `U=1.0` | Clamped to [0, texSize-1] |
| **Mirror** | Flip direction at each integer boundary; `U=1.1` samples the same as `U=0.9` | Unbounded |

The tutorial uses repeat. Clamp is common for sprites and decals where tiling would be visible.

---

## Affine vs. Perspective-Correct Interpolation

### The Problem: Affine Distortion

Naively interpolating UV coordinates using barycentric weights produces **affine interpolation** — the UV coordinates vary linearly in screen space. This is incorrect for perspective-projected triangles.

The reason: after perspective projection, the relationship between screen-space position and 3D position is non-linear. A point that is halfway across the screen image of a triangle is *not* halfway along the 3D triangle's surface. Affine UV interpolation ignores this and produces a characteristic sliding or warping distortion, especially visible when the triangle is viewed at an oblique angle.

This distortion was famously visible in PlayStation 1 games, which used affine UV interpolation for performance.

### The Solution: Perspective-Correct Interpolation

The fix is to interpolate `U/w` and `V/w` (UV divided by clip-space w) linearly in screen space, then divide back by `1/w` at each pixel.

This works because `1/w` *is* linear in screen space — it varies linearly across the projected triangle image. Multiplying UV by `1/w` makes the combined quantity linear, enabling correct linear interpolation.

### Practical Formulation

In a software renderer where the projected vertex stores `1/w` in its z component (after perspective division), the per-pixel interpolation is:

```
// p0.z, p1.z, p2.z are the stored 1/w values for each vertex
// (alpha, beta, gamma) are the barycentric weights for the current pixel

// Step 1: interpolate 1/w linearly
inv_w = alpha * p0.z + beta * p1.z + gamma * p2.z

// Guard: inv_w == 0 means a vertex is at the camera origin (w = 0 in clip space).
// Near-plane culling should prevent this — any vertex with w <= 0 must be culled
// before reaching this step. If culling is in place, inv_w > 0 is guaranteed.
if inv_w == 0: skip  // degenerate; should not occur with proper near-plane culling

// Step 2: interpolate U/w and V/w linearly
u_over_w = (uv0.x * p0.z) * alpha + (uv1.x * p1.z) * beta + (uv2.x * p2.z) * gamma
v_over_w = (uv0.y * p0.z) * alpha + (uv1.y * p1.z) * beta + (uv2.y * p2.z) * gamma

// Step 3: recover U and V by dividing back
interpU = u_over_w / inv_w
interpV = v_over_w / inv_w
```

The division in step 3 is the perspective correction. Without it (using `u_over_w` directly as U), you get affine distortion.

### Comparison

| Method | Formula | Result |
|---|---|---|
| **Affine** | `U = alpha*u0 + beta*u1 + gamma*u2` | Fast; distorts at oblique angles |
| **Perspective-correct** | `U = (alpha*u0/w0 + beta*u1/w1 + gamma*u2/w2) / (alpha/w0 + beta/w1 + gamma/w2)` | Correct; one extra division per pixel |

The performance cost of perspective-correct interpolation is one floating-point division per pixel — negligible on modern hardware, but historically significant (hence the PS1 compromise).

---

## Applying the Texture

Once `interpU` and `interpV` are computed for the current pixel:

```
// Use the always-positive modulo form to handle negative UV values safely
// (see Power-of-2 Optimization warning above for why the bitmask is unsafe here)
texX = ((int(interpU * texWidth)  % texWidth)  + texWidth)  % texWidth
texY = ((int(interpV * texHeight) % texHeight) + texHeight) % texHeight

// Sample the texel
texel_color = texture.pixels[texY * texWidth + texX]

// Apply to the pixel (multiply by lighting intensity if applicable)
pixel_color = texel_color * lighting_intensity
```

---

## UV Seams and Hard Edges

A UV seam occurs where the texture wraps around a 3D surface and the UV coordinates must "jump" discontinuously. For example, on a cylinder, the left edge and right edge of the texture meet at the same 3D edge, but one side has `U=0` and the other has `U=1`.

The mesh data structure handles this by allowing the same vertex position to appear multiple times with different UV coordinates. In an OBJ file, a face index triple `vertex/uv/normal` can reference the same vertex position index but different UV indices — creating separate entries in the rasterizer's vertex buffer for each UV assignment.

**Practical consequence**: when loading mesh data, do not assume a 1:1 mapping between position indices and UV indices. Build the vertex buffer from the face index triples, duplicating positions as needed. The number of unique `(position, uv, normal)` triples is the vertex count for the rasterizer.

---

## Common Texturing Bugs

| Symptom | Cause | Fix |
|---|---|---|
| Texture appears vertically flipped | UV origin mismatch (bottom-left vs top-left) | Flip V: `interpV = 1.0 - interpV` before sampling |
| Texture slides/warps as triangle rotates | Affine interpolation — not dividing by w | Use perspective-correct interpolation |
| Seam visible as a bright or dark line | UV coordinates at seam not duplicated correctly | Verify face indices create separate UV entries at seam edges |
| Texture tiles unexpectedly | UV coordinates outside [0,1] with repeat wrap | Check UV export settings in modeling tool; use clamp if tiling is undesired |
| Texture looks pixelated up close | Nearest-neighbor sampling (expected) | Use bilinear filtering if available |
| Black pixels at texture edges | Integer truncation pushing UV slightly out of range | Use the two-modulo wrap: `((int(U * w) % w) + w) % w` (see Power-of-2 Optimization warning — the bitmask is unsafe for negative inputs) |

---

## Texture Filtering (Out of Scope)

This reference covers **nearest-neighbor sampling** — the texel whose center is closest to the sample point is used. This is the simplest approach and produces a pixelated look at close range (magnification) and aliasing at distance (minification).

More sophisticated filtering modes exist but are out of scope:

- **Bilinear filtering**: interpolates between the four nearest texels; smoother at magnification
- **Trilinear filtering**: bilinear across two mipmap levels; smooth at all distances
- **Anisotropic filtering**: correct sampling for oblique viewing angles

These are standard features in GPU texture samplers and are configured through the rendering API rather than implemented manually.
