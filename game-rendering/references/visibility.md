# Visibility: Z-Buffer, Backface Culling, Frustum Culling

Covers the three primary visibility techniques in a software renderer: the Z-buffer (depth buffer) for correct pixel overdraw, backface culling to skip rear-facing triangles, and frustum culling to skip geometry outside the view volume. Read this when implementing depth testing, culling logic, or debugging incorrect occlusion.

For a complete worked Odin implementation, see Pekar Parts V and VI: https://marianpekar.com/blog/software-renderer-in-odin-from-scratch-part-v

---

## Z-Buffer (Depth Buffer)

### What It Is

The Z-buffer is an array of floating-point values, one per pixel, that tracks the depth of the closest geometry drawn to each pixel so far. Before drawing a pixel, the renderer checks whether the new geometry is closer than what was previously drawn. If it is, the pixel is drawn and the buffer is updated; if not, the pixel is discarded.

Without a Z-buffer, the last triangle drawn to a pixel wins, regardless of depth — producing incorrect overdraw.

### Data Structure

```
zbuffer: array[screen_width * screen_height] of float
```

Indexed as `zbuffer[y * screen_width + x]`.

### Initialization

At the start of each frame, initialize every entry to `0` (representing "nothing drawn yet" when storing `1/w`, since no valid geometry has `1/w = 0`):

```
for i in range(screen_width * screen_height):
    zbuffer[i] = 0.0
```

### Per-Pixel Depth Test

For each pixel about to be drawn at `(x, y)` with depth value `d`:

**Perspective projection** (storing `1/w` — larger value = closer):

```
idx = y * screen_width + x
if d > zbuffer[idx]:           // larger 1/w = closer to camera
    zbuffer[idx] = d
    framebuffer[idx] = pixel_color
// else: discard — something closer was already drawn here
```

**Orthographic projection** (storing `clip.z` — smaller value = closer):

```
idx = y * screen_width + x
if d < zbuffer[idx]:           // smaller clip.z = closer to camera
    zbuffer[idx] = d
    framebuffer[idx] = pixel_color
// else: discard
```

**Depth test direction**: For `1/w` (perspective), closer objects have *larger* `1/w` (e.g., distance 1 → `1/w = 1.0`; distance 100 → `1/w = 0.01`). Keep the larger value; initialize to `0`. For `clip.z` (orthographic), the near plane is `-1` and the far plane is `+1` — closer objects have *smaller* `clip.z`. Keep the smaller value; initialize to `+1` (or `float.MAX`).

### What Depth Value to Store

Store `1/w` (the reciprocal of clip-space w) as the depth value. This is the value that is linear in screen space, enabling correct perspective-correct interpolation of depth and UV coordinates.

In practice, when the projected vertex stores `1/w` in its z component (a common convention in software renderers), the per-pixel depth is:

```
depth = alpha * p0.z + beta * p1.z + gamma * p2.z
```

where `p0.z`, `p1.z`, `p2.z` are the stored `1/w` values and `(alpha, beta, gamma)` are the barycentric weights. This interpolation is linear in screen space and gives perspective-correct depth.

**Orthographic projection**: w is always 1, so `1/w = 1` everywhere and is useless for depth discrimination. Instead, store `clip.z` directly (which equals NDC z since w=1). The near plane maps to `clip.z = -1` and the far plane maps to `clip.z = +1` — closer objects have *smaller* `clip.z`. Use `d < zbuffer` with initialization to `+1` (or `float.MAX`) so the first draw always passes and closer (smaller) values win.

**Z-fighting**: When two surfaces are at nearly the same depth, floating-point precision limits cause them to alternate which one passes the depth test — producing a flickering pattern. Mitigations: increase the near-plane distance (concentrates `1/w` precision near the camera), reduce the far-plane distance, or add a small depth bias to coplanar surfaces (e.g., decals).

---

## Backface Culling

### What It Is

Backface culling skips triangles whose surface normal points away from the camera. For closed meshes (objects with no holes), the back faces are never visible — they are always occluded by the front faces. Culling them saves rasterization work.

### When to Apply

Apply backface culling in **view space**, after the view matrix transform but before projection. In view space, the camera is at the origin.

### Algorithm

1. Compute the triangle's face normal in view space:

```
edge1 = v2 - v1
edge2 = v3 - v1
N = normalize(cross(edge1, edge2))
```

2. Compute the vector from the triangle to the camera. In view space, the camera is at the origin, so this is simply `-v1` (pointing from the first vertex toward the origin):

```
toCamera = normalize(-v1)
```

3. Test the dot product:

```
if dot(N, toCamera) <= 0:
    skip this triangle  // normal points away from camera — back-facing
```

**For orthographic projection**, the camera direction is constant: `(0, 0, -1)` in right-handed view space. Replace `toCamera` with `(0, 0, -1)`:

```
if dot(N, vec3(0, 0, -1)) <= 0:   // equivalent to: if N.z <= 0
    skip this triangle
```

### Winding Order Convention

The cross product `cross(v2-v1, v3-v1)` produces a normal that points in a direction determined by the winding order of the vertices:

- **Counter-clockwise (CCW)** winding → normal points toward the viewer (front-facing) in right-handed systems
- **Clockwise (CW)** winding → normal points away (back-facing)

This convention must be consistent across all meshes. Most 3D modeling tools and file formats (OBJ, glTF) use CCW as the front-face convention. Verify when loading mesh data.

### Why It Works

In view space, the camera is at the origin. `toCamera = normalize(-v1)` points from the first vertex toward the camera. A positive dot product `dot(N, toCamera) > 0` means the surface normal and the camera-pointing vector are aligned — the surface faces *toward* the camera (front-facing). A negative or zero dot product means the normal points away from the camera — the surface faces away (back-facing). Skipping when `dot(N, toCamera) <= 0` therefore skips back-facing triangles and keeps front-facing ones.

---

## Frustum Culling

### What It Is

The view frustum is the truncated pyramid of space visible to the camera, bounded by six planes: near, far, left, right, top, and bottom. Geometry entirely outside the frustum produces no pixels and can be skipped before rasterization.

```
         /|
        / |
       /  |  ← far plane
      /   |
     / frustum \
    /     |     \
   /      |      \
  ←───────+───────→
  left   camera  right
         |
         near plane
```

### Conservative Triangle Culling

A simple and fast approach: cull a triangle if it is clearly outside the frustum. Two strategies, from simplest to most correct:

**Strategy 1 — Cull if any vertex is outside (simplest, most conservative)**

Cull the triangle if any vertex is outside the near or far plane. This misses some valid pixels for triangles that straddle the near/far planes, but avoids projection artifacts from vertices behind the camera:

```
for each vertex v in triangle:
    if v.z < -1 or v.z > 1:   // v.z is NDC z after perspective division
        skip this triangle
        break
```

**Strategy 2 — Cull only if all three vertices are outside the same plane (less conservative)**

Cull the triangle only when all three vertices are on the same outside side of a plane. This preserves more geometry but still misses triangles that straddle a plane:

```
// All three vertices beyond the far plane
if p0.z > 1 and p1.z > 1 and p2.z > 1: skip
// All three vertices behind the near plane
if p0.z < -1 and p1.z < -1 and p2.z < -1: skip
```

For a software renderer without full clipping, Strategy 1 is the safer choice: it prevents the projection artifacts that occur when a vertex is behind the camera (w ≤ 0 after projection). Strategy 2 preserves more geometry but requires that straddling triangles are handled correctly downstream.

**Viewport bounding box cull** (in screen space):

```
minX = min(p0.x, p1.x, p2.x)
maxX = max(p0.x, p1.x, p2.x)
minY = min(p0.y, p1.y, p2.y)
maxY = max(p0.y, p1.y, p2.y)

if maxX < 0 or minX >= screen_width:  skip
if maxY < 0 or minY >= screen_height: skip
```

This catches triangles that are entirely to the left, right, above, or below the viewport.

### Limitations of Conservative Culling

Conservative culling skips triangles that are entirely outside the frustum but does not handle triangles that *straddle* a frustum plane. A triangle with one vertex behind the near plane will project incorrectly (the vertex behind the camera projects to a position on the wrong side of the screen). The simple fix is to cull any triangle with a vertex behind the near plane — this misses some valid pixels at the screen edges but avoids projection artifacts.

### Proper Clipping (Out of Scope)

Full frustum clipping creates new triangles where geometry intersects frustum planes, preserving all visible pixels. Algorithms:

- **Sutherland-Hodgman** — clips a polygon against each frustum plane in sequence; produces correct output for all cases
- **Cohen-Sutherland** — line clipping algorithm; can be extended to triangles

These are more complex to implement and are out of scope for this reference. For a software renderer, conservative culling is usually sufficient.

---

## Culling Order in the Pipeline

Apply culling in this order for maximum efficiency:

```
1. Frustum cull (bounding box, in screen space or clip space)
   → Skip entire triangles outside the view volume

2. Backface cull (in view space)
   → Skip triangles facing away from camera

3. Rasterize remaining triangles
   → Z-buffer test per pixel during rasterization
```

Culling earlier in the pipeline is cheaper — a triangle rejected by frustum culling never reaches the rasterizer. A pixel rejected by the Z-buffer test still paid the cost of rasterization setup.
