# Love2D UI Patterns

Practical UI patterns for Love2D 11.x — buttons, hover detection, click handling, and sound effects. All code in Lua.

**Community alternatives:** [SUIT](https://github.com/vrld/SUIT) (immediate-mode UI), [Nuklear](https://github.com/keharriso/love-nuklear) (retained-mode UI). The patterns below are vanilla Love2D — useful when you want full control or a minimal dependency footprint.

---

## 1. Drawing a Button

A button is a filled rectangle with centered text drawn on top. Color management is critical — reset to white after drawing colored elements.

```lua
-- Draw a button at (x, y) with given width/height
-- Returns nothing; use hover detection and click handling separately
local function draw_button(label, x, y, w, h, hovered)
    -- Background color: highlight on hover
    if hovered then
        love.graphics.setColor(0.4, 0.6, 1.0, 1)
    else
        love.graphics.setColor(0.2, 0.3, 0.6, 1)
    end
    love.graphics.rectangle("fill", x, y, w, h)

    -- Border
    love.graphics.setColor(0.8, 0.8, 1.0, 1)
    love.graphics.rectangle("line", x, y, w, h)

    -- Label — centered in the button
    love.graphics.setColor(1, 1, 1, 1)
    love.graphics.printf(label, x, y + h/2 - 8, w, "center")

    -- Always reset color after drawing
    love.graphics.setColor(1, 1, 1, 1)
end
```

---

## 2. Centering and Positioning

Use `love.graphics.translate` to position a group of UI elements relative to a common origin. This makes layout changes easy — move the origin, everything moves.

```lua
local BUTTON_W = 200
local BUTTON_H = 50
local BUTTON_GAP = 20

-- Center a column of buttons on screen
local function draw_menu(buttons, hovered_index)
    -- Read dimensions inside draw; don't capture at module level (window not ready yet)
    local sw = love.graphics.getWidth()
    local sh = love.graphics.getHeight()
    local total_h = #buttons * BUTTON_H + (#buttons - 1) * BUTTON_GAP
    local start_x = (sw - BUTTON_W) / 2
    local start_y = (sh - total_h) / 2

    love.graphics.push()
    love.graphics.translate(start_x, start_y)

    for i, label in ipairs(buttons) do
        local by = (i - 1) * (BUTTON_H + BUTTON_GAP)
        draw_button(label, 0, by, BUTTON_W, BUTTON_H, i == hovered_index)
    end

    love.graphics.pop()
end
```

**Font sizing:** Load a font in `love.load` and set it before drawing text:

```lua
local ui_font

function love.load()
    ui_font = love.graphics.newFont("assets/font.ttf", 18)
end

function love.draw()
    local prev_font = love.graphics.getFont()
    love.graphics.setFont(ui_font)
    -- draw UI
    love.graphics.setFont(prev_font)  -- restore previous font
end
```

---

## 3. Hover Detection

Hover detection requires converting the mouse position into the same coordinate space as the button. If you've applied transforms (translate, scale), use `love.graphics.inverseTransformPoint` to map screen coordinates back to local coordinates.

```lua
-- Check if point (px, py) is inside rectangle (rx, ry, rw, rh)
local function point_in_rect(px, py, rx, ry, rw, rh)
    return px >= rx and px <= rx + rw
       and py >= ry and py <= ry + rh
end

-- Hover check — must be called inside love.draw after applying the same
-- push/translate used for drawing, so inverseTransformPoint reads correctly
local function get_hovered_button(buttons)
    local mx, my = love.mouse.getPosition()
    -- Convert screen mouse position to local (translated) space
    local lx, ly = love.graphics.inverseTransformPoint(mx, my)

    for i, _ in ipairs(buttons) do
        local by = (i - 1) * (BUTTON_H + BUTTON_GAP)
        if point_in_rect(lx, ly, 0, by, BUTTON_W, BUTTON_H) then
            return i
        end
    end
    return nil
end
```

> **Important:** `love.graphics.inverseTransformPoint` reads the *current* graphics transform. Call it during `love.draw` (after applying the same transforms used for drawing) or store the transform matrix and invert it manually.

**Simpler approach** (no transforms): If your UI is drawn at fixed screen coordinates, skip `inverseTransformPoint` and compare directly:

```lua
local function is_hovered(x, y, w, h)
    local mx, my = love.mouse.getPosition()
    return point_in_rect(mx, my, x, y, w, h)
end
```

---

## 4. Click Handling — The `over` Variable Pattern

The challenge with click handling in Love2D: `love.mousereleased` fires as an event callback, but hover state is computed in `love.draw`. The `over` variable bridges them.

**Pattern:**
1. In `love.draw`, compute which button is hovered and store it in `over`.
2. In `love.mousereleased`, check `over` to know which button was clicked.
3. In `love.update`, clear `over` at the start of each frame so stale hover state doesn't persist.

**Why this works:** `love.mousereleased` fires during event processing at the *start* of a frame, before `love.update` runs. So when a click fires, `over` still holds the value set by the *previous* frame's `love.draw`. `love.update` then clears it, and `love.draw` recomputes it for the current frame.

```lua
local buttons = { "Play", "Options", "Quit" }
local over = nil  -- index of currently hovered button, or nil

function love.update(dt)
    over = nil  -- clear each frame; recomputed in draw
end

function love.draw()
    local SCREEN_W = love.graphics.getWidth()
    local SCREEN_H = love.graphics.getHeight()
    local total_h = #buttons * BUTTON_H + (#buttons - 1) * BUTTON_GAP
    local origin_x = (SCREEN_W - BUTTON_W) / 2
    local origin_y = (SCREEN_H - total_h) / 2

    love.graphics.push()
    love.graphics.translate(origin_x, origin_y)

    -- Compute hover in the same transform context as drawing
    local mx, my = love.mouse.getPosition()
    local lx, ly = love.graphics.inverseTransformPoint(mx, my)

    for i, label in ipairs(buttons) do
        local by = (i - 1) * (BUTTON_H + BUTTON_GAP)
        local hovered = point_in_rect(lx, ly, 0, by, BUTTON_W, BUTTON_H)
        if hovered then over = i end
        draw_button(label, 0, by, BUTTON_W, BUTTON_H, hovered)
    end

    love.graphics.pop()
end

function love.mousereleased(x, y, button)
    if button == 1 and over then
        if over == 1 then
            -- Play
            StateManager.switch(PlayState)
        elseif over == 2 then
            -- Options
            StateManager.switch(OptionsState)
        elseif over == 3 then
            love.event.quit()
        end
    end
end
```

---

## 5. Sound Effects — First-Only Trigger Pattern

Playing a hover sound every frame while the mouse is over a button produces rapid-fire audio spam. Use a `last_over` variable to detect the *transition* into hover and play the sound only once.

```lua
local hover_sound
local click_sound
local last_over = nil  -- tracks previous frame's hovered button

function love.load()
    hover_sound = love.audio.newSource("assets/hover.wav", "static")
    click_sound = love.audio.newSource("assets/click.wav", "static")
end

function love.draw()
    -- ... (same hover computation as above, sets `over`) ...

    -- Play hover sound only on the frame we first enter a button
    if over ~= last_over and over ~= nil then
        hover_sound:stop()
        hover_sound:play()
    end
    last_over = over
end

function love.mousereleased(x, y, button)
    if button == 1 and over then
        click_sound:stop()
        click_sound:play()
        -- handle click...
    end
end
```

`hover_sound:stop()` before `play()` ensures the sound restarts cleanly if the user moves quickly between buttons.

---

## 6. Composing Multiple Buttons with push/pop

When drawing several UI panels or groups, use `push()`/`pop()` to isolate each group's transform. This prevents transform state from one group affecting another.

```lua
local function draw_hud(player)
    -- HUD in top-left corner
    love.graphics.push()
    love.graphics.translate(10, 10)
    draw_health_bar(player.hp, player.max_hp)
    draw_score(player.score)
    love.graphics.pop()
end

local function draw_pause_menu(hovered_index)
    local cx = love.graphics.getWidth() / 2
    local cy = love.graphics.getHeight() / 2

    love.graphics.push()
    love.graphics.translate(cx - BUTTON_W/2, cy - 80)
    for i, label in ipairs({"Resume", "Restart", "Quit"}) do
        local by = (i-1) * (BUTTON_H + BUTTON_GAP)
        draw_button(label, 0, by, BUTTON_W, BUTTON_H, i == hovered_index)
    end
    love.graphics.pop()
end

function love.draw()
    draw_game_world()
    draw_hud(player)
    if paused then
        -- Dim overlay
        love.graphics.setColor(0, 0, 0, 0.5)
        love.graphics.rectangle("fill", 0, 0, love.graphics.getWidth(), love.graphics.getHeight())
        love.graphics.setColor(1, 1, 1, 1)
        draw_pause_menu(over)
    end
end
```

**Key rule:** Every `love.graphics.push()` must have a matching `love.graphics.pop()`. Unmatched pushes accumulate transform state across frames and produce increasingly wrong rendering.

---

## Complete Minimal Menu Example

```lua
-- main.lua — minimal menu with hover, click, and sound
local BUTTON_W, BUTTON_H, BUTTON_GAP = 200, 50, 15
local buttons = { "Play", "Quit" }
local over = nil
local last_over = nil
local hover_sfx, click_sfx

local function point_in_rect(px, py, rx, ry, rw, rh)
    return px >= rx and px <= rx + rw and py >= ry and py <= ry + rh
end

function love.load()
    hover_sfx = love.audio.newSource("assets/hover.wav", "static")
    click_sfx = love.audio.newSource("assets/click.wav", "static")
end

function love.update(dt)
    over = nil
end

function love.draw()
    local sw = love.graphics.getWidth()
    local sh = love.graphics.getHeight()
    local total_h = #buttons * BUTTON_H + (#buttons-1) * BUTTON_GAP

    love.graphics.push()
    love.graphics.translate((sw - BUTTON_W)/2, (sh - total_h)/2)

    local mx, my = love.mouse.getPosition()
    local lx, ly = love.graphics.inverseTransformPoint(mx, my)

    for i, label in ipairs(buttons) do
        local by = (i-1) * (BUTTON_H + BUTTON_GAP)
        local hovered = point_in_rect(lx, ly, 0, by, BUTTON_W, BUTTON_H)
        if hovered then over = i end

        love.graphics.setColor(hovered and {0.4,0.6,1,1} or {0.2,0.3,0.6,1})
        love.graphics.rectangle("fill", 0, by, BUTTON_W, BUTTON_H)
        love.graphics.setColor(1,1,1,1)
        love.graphics.printf(label, 0, by + BUTTON_H/2 - 8, BUTTON_W, "center")
    end

    love.graphics.pop()

    if over ~= last_over and over ~= nil then
        hover_sfx:stop(); hover_sfx:play()
    end
    last_over = over
end

function love.mousereleased(x, y, btn)
    if btn == 1 and over == 1 then
        -- start game
    elseif btn == 1 and over == 2 then
        love.event.quit()
    end
    if btn == 1 and over then
        click_sfx:stop(); click_sfx:play()
    end
end
```
