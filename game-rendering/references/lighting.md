# Lighting Models

Covers light types, the diffuse (Lambertian) term, ambient light, flat shading, Phong shading, and multi-light blending with RGB colors. Read this when implementing a lighting model, choosing between flat and smooth shading, or debugging incorrect light behavior.

For a complete worked Odin implementation, see Pekar Parts VII, X, and XIII: https://marianpekar.com/blog/software-renderer-in-odin-from-scratch-part-vii

---

## Light Types

| Type | Parameters | Direction at pixel | Typical use |
|---|---|---|---|
| **Directional** | Direction vector, color, strength | Constant — same for every pixel | Sun, moon; infinite distance |
| **Point** | Position, color, strength | Varies — computed per pixel from light position | Torches, lamps, explosions |
| **Spot** | Position, direction, cone angle, color, strength | Varies, masked by cone | Flashlights, stage lights |

**Spot lights** are not covered in the tutorial; they extend point lights with a cone mask and are out of scope here.

**Light color** is an RGB vector. **Light strength** (intensity) is a scalar multiplier. These are often packed as a `Vector4(r, g, b, strength)` for convenience.

### Point Light Direction

For a point light, the direction from the surface to the light varies per pixel:

```
lightVec = normalize(light.position - pixel.world_position)
```

For a directional light, the direction is constant and pre-normalized:

```
lightVec = normalize(-light.direction)  // direction toward the light source
```

---

## Diffuse Term (Lambertian Reflectance)

The diffuse term models how much light a surface receives based on its orientation relative to the light source. A surface facing directly toward the light receives maximum illumination; a surface tilted away receives less; a surface facing away receives none.

```
diffuse = max(0.0, dot(surface_normal, light_direction))
```

`dot(N, L)` is the cosine of the angle between the surface normal `N` and the light direction `L` (both unit vectors). The cosine is 1 when they are parallel (surface faces the light directly), 0 when perpendicular (grazing angle), and negative when the light is behind the surface.

`max(0, ...)` clamps negative values to zero — surfaces facing away from the light receive no direct illumination.

This is **Lambertian reflectance**, the physically-motivated model for diffuse (matte) surfaces. It assumes light scatters equally in all directions from the surface.

---

## Ambient Term

Ambient light is a constant base illumination added to every surface, regardless of orientation. It prevents surfaces in shadow from being completely black, approximating the indirect light that bounces around a real scene.

**Scalar ambient** (white ambient light):

```
intensity = clamp(diffuse + ambient, 0.0, 1.0)
```

where `ambient` is a small scalar (e.g., 0.1).

**RGB ambient** (tinted ambient — e.g., blue skylight):

```
ambient = Vector3(0.05, 0.05, 0.15)  // slight blue tint
```

RGB ambient is more expressive: a slight blue ambient simulates open-sky indirect light; a warm orange ambient simulates firelight fill. See the multi-light section below for how RGB ambient integrates with the accumulation loop.

---

## Flat Shading

Flat shading computes one lighting intensity per triangle and applies it uniformly to every pixel in that triangle.

### Algorithm

1. Compute the triangle's face normal (once, in view space or world space):

```
N = normalize(cross(v2 - v1, v3 - v1))
```

2. Compute the light direction (for a directional light, this is constant):

```
L = normalize(-light.direction)
```

3. Compute intensity:

```
intensity = clamp(dot(N, L), ambient, 1.0)
```

4. Apply to every pixel in the triangle:

```
pixel_color = base_color * intensity
```

### Visual Signature

Flat shading produces a **faceted** appearance: each triangle has a uniform color, and adjacent triangles with different normals have visibly different shades. This creates hard edges between triangles. It is the characteristic look of low-poly 3D art.

---

## Phong Shading

Phong shading computes lighting per pixel by interpolating vertex normals across the triangle. The result is smooth gradients across surfaces, hiding the underlying triangle structure.

> **Terminology note**: "Phong shading" refers to the *interpolation method* (smooth normal interpolation). The "Phong reflection model" refers to a *lighting equation* that includes a specular term. This reference implements Phong shading with diffuse + ambient only; the specular term is out of scope.

### Algorithm

1. **Interpolate vertex normals** using perspective-correct weights (same method as UV interpolation — see `texturing.md § Perspective-Correct Interpolation`):

```
// Perspective-correct normal interpolation
// p0.z, p1.z, p2.z are stored 1/w values; (alpha, beta, gamma) are screen-space barycentric weights
inv_w = alpha * p0.z + beta * p1.z + gamma * p2.z

interpN.x = (n0.x * p0.z * alpha + n1.x * p1.z * beta + n2.x * p2.z * gamma) / inv_w
interpN.y = (n0.y * p0.z * alpha + n1.y * p1.z * beta + n2.y * p2.z * gamma) / inv_w
interpN.z = (n0.z * p0.z * alpha + n1.z * p1.z * beta + n2.z * p2.z * gamma) / inv_w
N = normalize(interpN)  // always re-normalize after interpolation
```

**Why perspective-correct?** Affine normal interpolation (using `alpha * n0 + beta * n1 + gamma * n2` directly) produces subtle shading errors on oblique triangles — the same sliding artifact as affine UV interpolation. The perspective-correct form divides by `1/w` to recover the correct interpolated value.

2. **Interpolate vertex positions** (perspective-correct, same pattern as normals above):

```
// inv_w already computed in step 1
// p0.pos, p1.pos, p2.pos must be in the same space as light.position
// (both world-space or both view-space — do not mix)
interpPos.x = (p0.pos.x * p0.z * alpha + p1.pos.x * p1.z * beta + p2.pos.x * p2.z * gamma) / inv_w
interpPos.y = (p0.pos.y * p0.z * alpha + p1.pos.y * p1.z * beta + p2.pos.y * p2.z * gamma) / inv_w
interpPos.z = (p0.pos.z * p0.z * alpha + p1.pos.z * p1.z * beta + p2.pos.z * p2.z * gamma) / inv_w
```

3. **Compute per-pixel light direction** (for a point light):

```
L = normalize(light.position - interpPos)
```

4. **Compute per-pixel intensity**:

```
intensity = clamp(dot(N, L) * light.strength, ambient, 1.0)
```

5. **Apply to pixel color**:

```
pixel_color = base_color * intensity
```

### Visual Signature

Phong shading produces **smooth gradients** across surfaces. Specular highlights (if implemented) move smoothly across rotating objects. The underlying triangle mesh is invisible unless the polygon count is very low.

### Re-normalizing After Interpolation

Linearly interpolating unit vectors does not produce unit vectors — the interpolated result has length < 1 (it is pulled toward the interior of the unit sphere). Always re-normalize after interpolation:

```
N = normalize(interpN)
```

Skipping this causes the dot product to return values less than the true cosine, making the surface appear darker than it should.

---

## Multiple Lights with RGB Colors

When the scene has multiple lights, accumulate each light's contribution per channel, then clamp and apply.

### Accumulation Loop

```
// Initialize with ambient (RGB)
lightAccum = ambient  // e.g., Vector3(0.1, 0.1, 0.1)

for each light in lights:
    // Compute light direction (directional or point)
    if light.type == DIRECTIONAL:
        L = normalize(-light.direction)
    else:  // POINT
        L = normalize(light.position - interpPos)

    // Diffuse contribution
    diffuse = max(0.0, dot(N, L))

    // Accumulate per channel
    lightAccum.r += diffuse * light.color.r * light.strength
    lightAccum.g += diffuse * light.color.g * light.strength
    lightAccum.b += diffuse * light.color.b * light.strength

// Clamp accumulated light before applying to surface color
lightAccum.r = min(lightAccum.r, 1.0)
lightAccum.g = min(lightAccum.g, 1.0)
lightAccum.b = min(lightAccum.b, 1.0)

// Multiply per channel: surface color × light color
final.r = base_color.r * lightAccum.r
final.g = base_color.g * lightAccum.g
final.b = base_color.b * lightAccum.b
```

### Why Per-Channel Multiplication

Multiplying surface color by light color per channel is physically motivated: a surface reflects only the wavelengths it doesn't absorb. A red surface (`base_color = (1, 0, 0)`) under blue light (`light.color = (0, 0, 1)`) reflects no light — the product is `(0, 0, 0)` (black). A white surface under colored light takes on the light's color. This is the correct model for surface reflectance.

### Clamping Before Applying

Clamp `lightAccum` to `[0, 1]` before multiplying by the surface color. Multiple lights can sum to values greater than 1; clamping prevents oversaturation and ensures the final color stays in the valid range.

---

## Flat vs. Phong: Decision Guide

| Situation | Recommendation |
|---|---|
| Low-poly stylized art (intentional faceted look) | Flat shading |
| Smooth organic surfaces (characters, vehicles) | Phong shading |
| Early prototyping | Flat shading (simpler, faster) |
| Mesh has no per-vertex normals | Flat shading (compute face normal) |
| Performance-critical path | Flat shading (one dot product per triangle vs. per pixel) |

---

## What's Not Covered Here

These lighting topics are out of scope for this reference:

| Topic | Where to look |
|---|---|
| **Specular highlights** (Blinn-Phong, Phong reflection model) | `godot-shader/references/lighting.md` |
| **Normal mapping** (perturbing normals from a texture) | `godot-shader/references/lighting.md` |
| **Shadow mapping** | External: learnopengl.com/Advanced-Lighting/Shadows |
| **Image-based lighting (IBL)** | External: learnopengl.com/PBR/IBL |
| **Physically-based rendering (PBR)** | External: learnopengl.com/PBR |
| **Attenuation** (light falloff with distance) | Extend the point light formula: multiply by `1 / (distance^2)` |
