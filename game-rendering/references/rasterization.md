# Rasterization

Covers converting vector geometry (triangles) into a pixel grid: the FTFB triangle rasterization algorithm, line drawing, and barycentric coordinates for attribute interpolation. Read this when implementing a rasterizer, debugging triangle rendering artifacts, or needing to interpolate per-vertex data (color, UV, normals) across a triangle's interior.

For a complete worked Odin implementation, see Pekar Parts V–VI: https://marianpekar.com/blog/software-renderer-in-odin-from-scratch-part-v

---

## What Rasterization Is

Rasterization converts continuous vector geometry — triangles defined by floating-point vertex positions — into a discrete pixel grid (a raster). For each triangle, the rasterizer determines which pixels fall inside it and computes per-pixel values (color, depth, UV coordinates) by interpolating from the triangle's vertices.

The two core operations are:
1. **Coverage determination**: which pixels are inside the triangle?
2. **Attribute interpolation**: what value does each covered pixel have?

---

## Triangle Rasterization: FTFB Algorithm

The **Flat-Top Flat-Bottom (FTFB)** algorithm rasterizes a triangle by splitting it into at most two simpler triangles — one with a flat top edge and one with a flat bottom edge — then filling each with horizontal scanlines.

### Why FTFB?

A general triangle has three vertices at arbitrary Y positions. Filling it with horizontal scanlines requires computing the left and right X boundaries for each scanline. A flat-top or flat-bottom triangle has exactly two edges contributing to each scanline, making the boundary computation straightforward. Splitting a general triangle at its middle vertex's Y coordinate reduces it to these two simple cases.

### Step 1: Sort Vertices by Y

Sort the three vertices so that `p0.y ≤ p1.y ≤ p2.y` (p0 at top, p2 at bottom in screen space where Y increases downward).

```
// Sort vertices by Y (ascending)
if p1.y < p0.y: swap(p0, p1)
if p2.y < p0.y: swap(p0, p2)
if p2.y < p1.y: swap(p1, p2)
// Now: p0.y ≤ p1.y ≤ p2.y
```

### Step 2: Identify or Create the Split

```
  p0 ─────────────── (top)
   \                /
    \              /
     p1 ──────── pM    ← split point at p1.y
    /              \
   /                \
  p2 ─────────────── (bottom)
```

- If `p0.y == p1.y`: already a flat-top triangle (p0 and p1 share the top edge)
- If `p1.y == p2.y`: already a flat-bottom triangle (p1 and p2 share the bottom edge)
- If `p0.y == p2.y`: degenerate triangle (all three vertices at the same Y — a horizontal line). **Skip it — no pixels to fill.**
- Otherwise: compute the split point `pM` — the point on edge `p0→p2` at the same Y as `p1`:

```
// Interpolate X along the long edge p0→p2 at y = p1.y
// Safe: p2.y != p0.y is guaranteed by the checks above
t  = (p1.y - p0.y) / (p2.y - p0.y)
pM = (p0.x + t * (p2.x - p0.x), p1.y)
```

This creates two triangles: `{p0, p1, pM}` (flat-bottom) and `{p1, pM, p2}` (flat-top).

**Attribute interpolation at pM**: When the rasterizer interpolates per-vertex attributes (depth `1/w`, UVs, normals), `pM` must also carry interpolated values using the same `t` parameter. `1/w` is linear in screen space and can be affinely lerped; UVs must be perspective-correct:

```
pM.inv_w  = lerp(p0.inv_w, p2.inv_w, t)   // 1/w is linear — affine lerp is correct

// Guard: pM.inv_w == 0 means the split point is at the camera origin.
// Near-plane culling should prevent this. If not culled, skip the triangle.
if pM.inv_w == 0: skip this triangle

// Perspective-correct UV interpolation at pM:
pM.uv.x   = lerp(p0.uv.x * p0.inv_w, p2.uv.x * p2.inv_w, t) / pM.inv_w
pM.uv.y   = lerp(p0.uv.y * p0.inv_w, p2.uv.y * p2.inv_w, t) / pM.inv_w

// Normal: affine lerp is acceptable (re-normalization corrects the magnitude error)
pM.normal = normalize(lerp(p0.normal, p2.normal, t))
```

Failing to interpolate attributes at `pM` causes incorrect depth and texture coordinates in the bottom half of every split triangle. Using affine lerp for UVs (instead of the perspective-correct form above) produces the same sliding distortion as affine UV interpolation in the rasterizer.

### Step 3: Compute Inverse Slopes

For each triangle half, compute the inverse slope (dx/dy) for each **non-horizontal** edge. This tells you how much X changes per unit of Y — exactly what you need to advance the scanline boundaries.

```
// For the flat-bottom half {p0, p1, pM}:
// Both edges p0→p1 and p0→pM are non-horizontal (p1.y != p0.y, pM.y != p0.y)
invSlope_left  = (p1.x - p0.x) / (p1.y - p0.y)
invSlope_right = (pM.x - p0.x) / (pM.y - p0.y)
```

**Never compute an inverse slope for a horizontal edge** (where `dy == 0`). The flat-bottom half has a horizontal bottom edge `p1→pM`; the flat-top half has a horizontal top edge. These edges are not used in the scanline loop and must not be divided by.

### Step 4: Fill Scanlines

For each integer Y from `ceil(p0.y)` to `floor(p1.y)` (flat-bottom half):

```
xStart = p0.x + (y - p0.y) * invSlope_left
xEnd   = p0.x + (y - p0.y) * invSlope_right

if xStart > xEnd: swap(xStart, xEnd)

for x in range(floor(xStart), floor(xEnd) + 1):
    draw_pixel(x, y)
```

Repeat for the flat-top half `{p1, pM, p2}` from `ceil(p1.y)` to `floor(p2.y)`.

**Always floor X and Y** at the start of each scanline to avoid sub-pixel artifacts and ensure consistent coverage. The right edge uses `floor(xEnd) + 1` (inclusive) to avoid missing the rightmost pixel when `xEnd` is exactly an integer.

### ASCII Diagram: FTFB Split

```
        p0
       /  \
      /    \
     /      \
    p1──────pM   ← split at p1.y; pM interpolated on p0→p2
     \      /
      \    /
       \  /
        p2
```

Top half (p0 to p1/pM): flat-bottom triangle
Bottom half (p1/pM to p2): flat-top triangle

---

## Line Drawing (DDA Algorithm)

The **Digital Differential Analyzer (DDA)** draws a line between two integer pixel positions by stepping along the longer axis.

```
dx = b.x - a.x
dy = b.y - a.y

longerDelta = max(abs(dx), abs(dy))

if longerDelta == 0: return  // degenerate line (same point)

incX = dx / longerDelta
incY = dy / longerDelta

x = a.x
y = a.y

for i in range(0, longerDelta + 1):
    draw_pixel(int(x), int(y))
    x += incX
    y += incY
```

Stepping along the longer axis ensures no gaps: if `|dx| > |dy|`, stepping by 1 in X advances less than 1 in Y, so every pixel column gets exactly one drawn pixel.

**Bresenham's algorithm** is an alternative that uses only integer arithmetic (no floating-point division), making it faster on hardware without FPUs. DDA is simpler to implement and understand; Bresenham is preferred in performance-critical software renderers.

---

## Barycentric Coordinates

Barycentric coordinates express any point P as a weighted combination of a triangle's three vertices A, B, C:

```
P = α·A + β·B + γ·C
```

with the constraint `α + β + γ = 1`.

### Geometric Meaning

- `α`, `β`, `γ` are the "weights" of each vertex
- At vertex A: `(α, β, γ) = (1, 0, 0)`
- At vertex B: `(α, β, γ) = (0, 1, 0)`
- At vertex C: `(α, β, γ) = (0, 0, 1)`
- At the centroid: `(α, β, γ) = (1/3, 1/3, 1/3)`
- **Negative weight** means P is outside the triangle (on the opposite side of the corresponding edge)

### Computation in 2D

Using signed parallelogram areas (cross products of 2D vectors):

```
ac = c - a
ab = b - a
ap = p - a
pc = c - p
pb = b - p

// Total triangle area (signed — sign encodes winding order)
area  = ac.x * ab.y - ac.y * ab.x

// Guard: degenerate triangle (collinear vertices or duplicate positions)
if abs(area) < 1e-6: skip this triangle  // no pixels to fill

// Barycentric weights
alpha = (pc.x * pb.y - pc.y * pb.x) / area
beta  = (ac.x * ap.y - ac.y * ap.x) / area
gamma = 1.0 - alpha - beta
```

`alpha` is the weight for vertex A, `beta` for vertex B, `gamma` for vertex C.

**Degenerate triangles**: When `area == 0`, the triangle has no area (all three vertices are collinear or two are identical). Division by zero produces NaN/Inf weights that corrupt the Z-buffer and framebuffer. Use `abs(area) < epsilon` rather than exact equality to also reject near-degenerate triangles that would produce extreme weight values.

**Optimization**: `gamma = 1 - alpha - beta` avoids a third area computation.

### Point-in-Triangle Test

A point is inside the triangle if and only if all three weights are non-negative:

```
inside = (alpha >= 0) and (beta >= 0) and (gamma >= 0)
```

### Attribute Interpolation

The primary use of barycentric coordinates in rasterization is interpolating per-vertex attributes across the triangle's interior. Given values `vA`, `vB`, `vC` at the three vertices:

```
interpolated = alpha * vA + beta * vB + gamma * vC
```

This works for any scalar or vector attribute: color, UV coordinates, surface normals, depth. However, for perspective-correct interpolation of UV and depth, the weights must be adjusted — see `texturing.md` and `visibility.md`.

### Example: Interpolating Vertex Colors

```
// Vertices with colors
A = {pos: (10, 50), color: (1, 0, 0)}  // red
B = {pos: (90, 50), color: (0, 1, 0)}  // green
C = {pos: (50, 10), color: (0, 0, 1)}  // blue

// For a pixel at position P:
(alpha, beta, gamma) = barycentric(P, A.pos, B.pos, C.pos)

pixelColor.r = alpha * A.color.r + beta * B.color.r + gamma * C.color.r
pixelColor.g = alpha * A.color.g + beta * B.color.g + gamma * C.color.g
pixelColor.b = alpha * A.color.b + beta * B.color.b + gamma * C.color.b
```

The result is a smooth gradient across the triangle — red at A, green at B, blue at C, blended in between.

---

## Putting It Together: Rasterizing a Shaded Triangle

The full per-triangle rasterization loop:

```
// 1. Project vertices to screen space (see transformations.md)
// 2. Sort by Y, compute FTFB split
// 3. For each scanline:
for y in scanline_range:
    xStart, xEnd = compute_scanline_bounds(y)
    for x in range(floor(xStart), floor(xEnd) + 1):  // inclusive right edge
        // 4. Compute barycentric weights for (x, y)
        (alpha, beta, gamma) = barycentric((x, y), p0, p1, p2)

        // 5. Depth test — storing 1/w; larger value = closer (see visibility.md)
        depth = interpolate_depth(alpha, beta, gamma)  // interpolates 1/w
        if depth <= zbuffer[y * width + x]: continue   // skip if not closer
        zbuffer[y * width + x] = depth

        // 6. Interpolate attributes
        uv    = interpolate_uv_perspective_correct(alpha, beta, gamma)
        normal = normalize(interpolate_normal(alpha, beta, gamma))

        // 7. Sample texture and compute lighting (see texturing.md, lighting.md)
        color = sample_texture(uv) * compute_lighting(normal)
        framebuffer[y * width + x] = color
```

Each step is covered in detail in its respective reference file.
