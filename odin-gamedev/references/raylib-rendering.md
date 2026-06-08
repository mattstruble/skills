# Raylib Rendering

Read this when implementing custom rendering on top of raylib in Odin — software framebuffers, per-pixel image drawing, multi-pointer interop with raylib's color arrays, and runtime FPS overlays. **For the underlying rendering theory** (rasterization, projection, barycentric coordinates, depth testing, lighting models) **see the `game-rendering` skill.** This file is purely the Odin/raylib glue patterns.

---

## Software Framebuffer Pattern (`rl.Image` as a Backing Buffer)

The "draw to a buffer, blit at frame end" pattern is the central performance technique for any CPU-side renderer on raylib. Per-pixel `rl.DrawPixel` calls go through the GPU pipeline individually — at 480,000 calls per frame (800×600 screen, full coverage) they become the bottleneck. The buffer pattern reduces frame-end work to a single `UpdateTexture` + `DrawTexture`.

```odin
import rl "vendor:raylib"

SCREEN_W :: 800
SCREEN_H :: 600

main :: proc() {
    rl.InitWindow(SCREEN_W, SCREEN_H, "renderer")
    defer rl.CloseWindow()

    // Setup once: backing image and the GPU texture that mirrors it
    framebuffer := rl.GenImageColor(SCREEN_W, SCREEN_H, rl.BLACK)
    defer rl.UnloadImage(framebuffer)

    framebuffer_tex := rl.LoadTextureFromImage(framebuffer)
    defer rl.UnloadTexture(framebuffer_tex)

    for !rl.WindowShouldClose() {
        rl.BeginDrawing()

        // Per-pixel writes go to the IMAGE (CPU memory), not the screen
        for y in 0..<SCREEN_H {
            for x in 0..<SCREEN_W {
                rl.ImageDrawPixel(&framebuffer, i32(x), i32(y), some_color(x, y))
            }
        }

        // Single upload + blit at frame end
        rl.UpdateTexture(framebuffer_tex, framebuffer.data)
        rl.DrawTexture(framebuffer_tex, 0, 0, rl.WHITE)

        // Clear the IMAGE backing buffer for next frame
        rl.ImageClearBackground(&framebuffer, rl.BLACK)

        rl.EndDrawing()
        free_all(context.temp_allocator)
    }
}
```

Key points:
- `rl.ImageDrawPixel` writes to CPU memory; `rl.DrawPixel` issues a GPU draw call per call. The former is much cheaper when called millions of times per frame.
- `rl.UpdateTexture` uploads the entire image to GPU once per frame — a single PCIe transfer regardless of how many pixels changed.
- `rl.ImageClearBackground` wipes the buffer for the next frame; skip it only if your rendering code writes every pixel unconditionally.
- `rl.DrawTexture` takes a tint color as the fourth argument (after texture, posX, posY); pass `rl.WHITE` to draw the texture unmodified.
- This pattern applies to any CPU-side renderer: software rasterizer, raymarcher, fractal viewer, retro-style demo.
- Pekar Part XI measures roughly 2× FPS improvement just from this change: https://marianpekar.com/blog/software-renderer-in-odin-from-scratch-part-xi

### Framebuffer vs. Direct Draw: Decision Table

| Approach | When to use | Cost per pixel |
|---|---|---|
| `rl.DrawPixel` | Occasional debug overlays, a handful of pixels | GPU draw call per pixel |
| `rl.ImageDrawPixel` + `rl.UpdateTexture` | Any CPU-side renderer covering many pixels | CPU write; one GPU upload per frame |
| `rl.DrawTexture` (GPU texture) | Sprites, UI, pre-rendered assets | GPU draw call per texture |

The framebuffer pattern is not the right choice for drawing a few debug points — `rl.DrawPixel` is fine there. It becomes necessary once you're covering a significant fraction of the screen with CPU-computed pixels.

---

## Multi-Pointers from Raylib Pixel APIs (`[^]rl.Color`)

`rl.LoadImageColors` returns `[^]rl.Color` — a multi-pointer (Odin's typed C-style pointer-as-array). The `Texture` struct in Pekar's renderer uses this directly:

```odin
import rl "vendor:raylib"

Texture :: struct {
    width:  i32,
    height: i32,
    pixels: [^]rl.Color,   // multi-pointer; behaves like a flat array
}

load_texture :: proc(path: cstring) -> Texture {
    img := rl.LoadImage(path)
    defer rl.UnloadImage(img)   // LoadImageColors allocates a separate buffer — pixels and img.data are independent
    return Texture{
        width  = img.width,
        height = img.height,
        pixels = rl.LoadImageColors(img),
    }
}

texture_unload :: proc(t: ^Texture) {
    rl.UnloadImageColors(t.pixels)   // free with the matching raylib free
    t.pixels = nil
}

// Sampling: index as a flat row-major array
sample :: proc(t: Texture, x, y: i32) -> rl.Color {
    return t.pixels[y * t.width + x]
}
```

Key points:
- `[^]T` is Odin's multi-pointer: a foreign-style "pointer to many" with no length tag. See `odin-design` → `references/data-oriented.md` (Multi-Pointers section) for full details.
- `rl.Color` is an alias for `[4]u8`. Access channels as `.r`, `.g`, `.b`, `.a` — or `.x`, `.y`, `.z`, `.w` via Odin's array-programming swizzle. No struct needed.
- Always pair `rl.LoadImageColors` with `rl.UnloadImageColors` — both are raylib-side allocations outside Odin's allocator system.
- For converting an Odin `string` path to the `cstring` raylib expects, use `strings.clone_to_cstring(path, context.temp_allocator)` — see the asset-caching pattern in `references/game-architecture.md`.

### Applying shading to a sampled texel

A common pattern: sample the texel, multiply each channel by a light intensity, draw the result.

```odin
shade_texel :: proc(t: Texture, x, y: i32, intensity: f32) -> rl.Color {
    tex := t.pixels[y * t.width + x]
    i := clamp(intensity, 0, 1)   // must be in [0,1]; u8 cast is undefined for values > 255
    return rl.Color{
        r = u8(f32(tex.r) * i),
        g = u8(f32(tex.g) * i),
        b = u8(f32(tex.b) * i),
        a = tex.a,
    }
}
```

The rendering theory behind computing `intensity` from normals and light direction lives in the `game-rendering` skill.

---

## Power-of-2 Texture Sizing for Fast Modulo

When texture dimensions are powers of 2, the texel-index modulo wraps with a bitmask, which is faster than a `%` op. This matters when sampling textures inside the per-pixel loop — every frame, every triangle, every covered pixel.

```odin
// Generic case (works for any size, but slower):
texX := i32(interpU * f32(tex.width))  % tex.width
texY := i32(interpV * f32(tex.height)) % tex.height

// Power-of-2 fast path (only correct if width/height are powers of 2):
texX := i32(interpU * f32(tex.width))  & (tex.width  - 1)
texY := i32(interpV * f32(tex.height)) & (tex.height - 1)
```

Key points:
- `n & (size - 1)` is equivalent to `n % size` for any non-negative integer when `size = 2^k`. Used in Pekar's renderer: https://marianpekar.com/blog/software-renderer-in-odin-from-scratch-part-x
- Negative inputs break this — UV values can go negative if interpolated barycentric weights drift. Either clamp UVs at sampling time or use `%` if your pipeline can produce negatives. Pekar's renderer assumes non-negative UVs by construction.
- Trade-off: forcing power-of-2 sizes is a content constraint. Modern art pipelines often output non-power-of-2 textures. Decide upfront and document the requirement.

| Approach | Correct for any size? | Handles negative UVs? | Speed |
|---|---|---|---|
| `% tex.width` | Yes | Yes (with care) | Slower |
| `& (tex.width - 1)` | Only for `2^k` sizes | No | Faster |

Common power-of-2 texture sizes: 64, 128, 256, 512, 1024, 2048. If you control the asset pipeline, standardize on one of these.

---

## In-Frame FPS Overlay

```odin
// After your scene render, before EndDrawing:
rl.DrawFPS(10, 10)   // top-left corner, 10px from each edge
```

Key points:
- Bare-minimum profiling — put it in every dev build to spot frame rate regressions visually.
- For real performance work, use `core:prof/spall`; see the `odin-design` skill for the Spall workflow. Pekar's Part XI walks through Spall profiling of the renderer's hot path.
- `rl.DrawFPS` renders after your framebuffer blit, so it overlays on top of the rendered scene correctly — call it between `rl.DrawTexture` and `rl.EndDrawing`.
- For a custom overlay with more detail (entity count, draw call count, memory usage), use `rl.DrawText` with `fmt.tprintf` and `strings.clone_to_cstring(text, context.temp_allocator)`. See the debug overlay pattern in `references/game-architecture.md`.

---

## Asset Cleanup Expectations

Raylib allocations from `rl.LoadImage`, `rl.LoadTexture`, `rl.LoadImageColors`, `rl.LoadSound`, `rl.LoadModel`, etc. are **not** in Odin's allocator system. They must be paired with the matching `rl.Unload*` call before window close.

| Raylib allocator | Matching free |
|---|---|
| `rl.LoadImage` | `rl.UnloadImage` |
| `rl.LoadTexture` / `rl.LoadTextureFromImage` | `rl.UnloadTexture` |
| `rl.LoadImageColors` | `rl.UnloadImageColors` |
| `rl.GenImageColor` | `rl.UnloadImage` |
| `rl.LoadSound` | `rl.UnloadSound` |
| `rl.LoadModel` | `rl.UnloadModel` |

The OS reclaims all process memory at exit — for short-running CLIs or simple demos, skipping explicit unloads is fine (Pekar's renderer does exactly this). Long-running apps and hot-reload scenarios should free what they load to avoid accumulating memory across reloads.

`defer` is the idiomatic pattern for cleanup:

```odin
framebuffer := rl.GenImageColor(SCREEN_W, SCREEN_H, rl.BLACK)
defer rl.UnloadImage(framebuffer)

framebuffer_tex := rl.LoadTextureFromImage(framebuffer)
defer rl.UnloadTexture(framebuffer_tex)
```

See `references/game-architecture.md` for the full asset-caching pattern with `unload_all_assets`.
