# min-love2d-fennel Template Guide

The [min-love2d-fennel](https://codeberg.org/alexjgriffith/min-love2d-fennel) template is the recommended starting point for Love2D + Fennel projects. It bundles Fennel, sets up the mode system, includes an error recovery mode, and provides a build pipeline for all platforms.

---

## Getting Started

```bash
git clone https://codeberg.org/alexjgriffith/min-love2d-fennel my-game
cd my-game
rm -rf .git
git init
```

Fennel is bundled — no separate install needed. You need **Love2D 11.x** installed and on your PATH.

Run the game:

```bash
love .
```

A game window opens and a REPL (`>>` prompt) appears in the terminal.

---

## Customization

**`conf.lua`** — window title, identity, and Love2D feature flags:

```lua
function love.conf(t)
    t.identity = "my-game"
    t.window.title = "My Game"
    t.window.width = 800
    t.window.height = 600
end
```

**`makefile`** — build metadata for releases:

```makefile
NAME        = my-game
AUTHOR      = yourname
DESCRIPTION = A short description
ITCH_ACCOUNT = your-itch-username
```

---

## Template Structure

```
my-game/
├── main.lua          -- Fennel bootstrap; calls wrap.fnl
├── wrap.fnl          -- Love2D callback handling, mode switching
├── mode-intro.fnl    -- Example starting mode
├── conf.lua          -- Love2D configuration
├── fennel.lua        -- Bundled Fennel compiler
├── makefile          -- Build and deploy targets
└── .flsproject       -- fennel-ls language server config
```

### `main.lua`

Initializes Fennel and hands control to `wrap.fnl`. You generally don't need to modify this.

### `wrap.fnl`

The heart of the template. It:
- Registers Love2D callbacks (`love.draw`, `love.update`, `love.keypressed`, etc.)
- Maintains the current mode and delegates callbacks to it
- Provides the `set-mode` function passed to each mode's `update`
- Catches errors in callbacks and switches to the error recovery mode

You can add global callbacks here (e.g., `love.resize`) that all modes share.

### `mode-intro.fnl`

The example starting mode. Read this to understand the mode pattern — it shows local state, external state references, and the returned callback table.

---

## Mode Anatomy

A mode is a Fennel module that returns a table of callbacks. Only include the callbacks your mode needs.

```fennel
;; mode-game.fnl
(local state (require :state))

;; Module-local state (resets on reload — use persist macro if needed)
(local particles [])

(fn activate []
  ;; Called when this mode becomes active
  ;; Good place to reset transient state
  (set particles []))

(fn draw []
  (love.graphics.setColor 1 1 1)
  (love.graphics.print (.. "Score: " state.score) 10 10))

(fn update [dt set-mode]
  ;; dt is delta time in seconds
  ;; set-mode switches to another mode
  (when (love.keyboard.isDown "escape")
    (set-mode :mode-menu)))

(fn keypressed [key]
  (when (= key "space")
    (table.insert particles {:x (love.math.random 800)
                             :y (love.math.random 600)})))

{: activate : draw : update : keypressed}
```

**Available callbacks:** `activate`, `draw`, `update`, `keypressed`, `keyreleased`, `mousepressed`, `mousereleased`, `mousemoved`, `wheelmoved`, `resize`, `quit`. Check `wrap.fnl` for the full list — it only delegates callbacks that are defined in the mode table.

**Switching modes:**

```fennel
;; In update:
(fn update [dt set-mode]
  (when game-over?
    (set-mode :mode-gameover)))
```

`set-mode` takes the module name as a string. `wrap.fnl` calls `require` on it and runs `activate` if defined. If the module name is wrong or the module fails to load, `wrap.fnl`'s error handler catches the exception and activates the error recovery mode — check the error message for the module path.

---

## Building and Deploying

```bash
make release    # builds Linux, Mac, Windows, and web
make linux      # Linux only
make mac        # macOS only
make windows    # Windows only
make web        # Web (lovejs) only
make upload     # pushes to itch.io via butler
```

Built files land in `releases/`. The `.love` file (platform-independent archive) is also produced.

**Web builds use Lua 5.1, not LuaJIT.** Test web compatibility before shipping:
- No bitwise operators (`bit.band`, etc.) — use `bit` library explicitly
- No LuaJIT FFI
- Some number precision differences

`make upload` requires [butler](https://itch.io/docs/butler/) installed and authenticated. Set `ITCH_ACCOUNT` and `NAME` in the makefile.

---

## fennel-ls Integration

The template includes a `.flsproject` file for the [fennel-ls](https://git.sr.ht/~xerool/fennel-ls) language server. This enables autocompletion and inline errors in editors that support LSP.

Check the template README for the exact `.flsproject` configuration — it specifies the Fennel version and any macro paths that fennel-ls needs to resolve `import-macros` correctly.
