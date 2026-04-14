---
name: love2d-fennel
description: Use when working with Fennel and Love2D together — writing `.fnl` files in a Love2D project, setting up REPL-driven development, hot-reloading modules during live gameplay, using the min-love2d-fennel template, writing Fennel macros for state persistence across reloads, or structuring a Love2D project with the mode-based architecture. NOT for Love2D engine API patterns. NOT for engine-agnostic pattern theory (see game-patterns).
---

# Love2D + Fennel Interactive Development

Fennel is a Lisp that compiles to Lua, giving Love2D projects a REPL-driven workflow where you can evaluate expressions and reload modules without restarting the game. This skill covers that interactive development workflow.

## References

| Reference | When to read it |
|---|---|
| [`references/macros.md`](references/macros.md) | Full `persist` and `hot-table` macro code, usage examples, and the `params.fnl` module for controlling dev vs release behavior |
| [`references/template-guide.md`](references/template-guide.md) | Getting started with min-love2d-fennel, project structure, mode anatomy, building and deploying |

---

## Architecture

The recommended structure uses a **mode system** to organize Love2D callbacks:

- **`main.lua`** — initializes Fennel, then calls `wrap.fnl`
- **`wrap.fnl`** — handles Love2D callbacks and mode switching; the entry point for Fennel code
- **Each mode** is a Fennel module returning a table of callbacks (`draw`, `update`, `activate`, etc.)

```fennel
;; mode-game.fnl — minimal mode
(fn draw []
  (love.graphics.print "Hello from game mode!"))

(fn update [dt set-mode]
  (when (love.keyboard.isDown "escape")
    (set-mode :mode-menu)))

{: draw : update}
```

`update` receives `dt` and a `set-mode` function. Call `(set-mode :mode-name)` to switch modes — `wrap.fnl` handles the transition.

**This is the recommended approach, not the only one.** If your project doesn't need modes, you can write callbacks directly in `wrap.fnl`. The mode system pays off as soon as you have more than one distinct game state (menu, gameplay, pause, game over).

The [min-love2d-fennel template](https://codeberg.org/alexjgriffith/min-love2d-fennel) is the easiest way to get this setup. See `references/template-guide.md`.

---

## Interactive Development Workflow

Run with `love .` from the project directory. A REPL (`>>` prompt) appears in the shell alongside the game window.

**The REPL evaluates Fennel expressions in the live Love2D environment.** You can inspect state, call functions, and test ideas without restarting.

**`,reload module-name`** is the key command — reloads a module file and updates `package.loaded`. After reloading, the mode system picks up the new callbacks on the next frame.

```
>> ,reload mode-game
>> (print (fennel.view (require :state)))   ; inspect state
```

**The core principle: develop in module files, not in the REPL directly.** The REPL is for testing and inspection. Module files are versioned, persist between restarts, and are what actually runs your game.

### Editor Integration

- **Emacs `fennel-mode`**: `C-c k` reloads the current module, `C-c z` opens the REPL
- **Other editors**: pipe `,reload module-name` to the REPL process via stdin, or use a file watcher that sends the reload command on save

### What Not to Do

**Do not overwrite Love2D callbacks directly** (`love.draw`, `love.update`, etc.) from the REPL or from modules. The mode system intercepts these callbacks — bypassing it leads to state inconsistencies and unrecoverable crashes. Always use mode callbacks instead.

---

## State Management

The central challenge of hot-reload development: module-level locals reset when a module is reloaded. Three approaches, in order of preference:

### 1. State Module (Primary)

Store state that must survive reloads in a dedicated `state.fnl` module. Never reload this module during development — if you do, modules that already captured its reference will continue using the old table while new `require` calls return a fresh one, causing split-brain state bugs. The only safe recovery is a full game restart.

```fennel
;; state.fnl — never reload this module
{:player {:x 100 :y 200 :hp 3}
 :score 0
 :level 1}
```

Access it close to where it's used:

```fennel
;; mode-game.fnl
(local state (require :state))

(fn draw []
  (love.graphics.print (.. "Score: " state.score) 10 10))
```

Benefits: single point of visibility into all game state, easy to add reset/save/load functions, survives any number of module reloads.

### 2. `persist` Macro (Module-Local State)

For state that belongs to a module and shouldn't be externally accessible, use the `persist` macro. It checks `_G._persist[module][handle]` — if the value already exists from a previous load, it returns the existing value instead of re-initializing.

```fennel
;; mode-game.fnl — counter survives reload
(import-macros {: persist} :persist)

(persist enemy-count 0)  ; won't reset to 0 on ,reload

(fn update [dt set-mode]
  (set enemy-count (+ enemy-count 1)))
```

In release builds (`params.persist = false`), `persist` compiles to a plain `local` — no runtime overhead. See `references/macros.md` for the full macro code.

### 3. `hot-table` Macro (Metatables)

Metatables are a specific problem: after reload, the module has a new table reference. Existing objects still point to the old metatable, so method calls break.

`hot-table` persists the table reference but overwrites its members with the new values — all existing references stay valid.

```fennel
;; enemy.fnl — metatable stays connected to existing enemy objects
(import-macros {: hot-table} :persist)

(hot-table Enemy
  {:new (fn [x y] (setmetatable {:x x :y y} Enemy))
   :draw (fn [self] (love.graphics.print "E" self.x self.y))})
```

After `,reload enemy`, existing enemy objects still have valid metatables pointing to the updated methods. See `references/macros.md` for the full macro code.

### Rules of Thumb

1. Load large resources (images, music) in `love.load` or a mode's `activate` callback. Store them in a module that won't be reloaded.
2. Shared/persistent state goes in the state module.
3. Module-local parameters defined at load time or that are transient stay as top-level locals (they'll reset on reload, which is usually fine for configuration).

---

## Error Recovery

The min-love2d-fennel template includes an error mode that catches crashes in `draw` and `update` callbacks. Instead of falling through to Love2D's default error handler (which halts the game), it switches to a recovery mode that displays the error.

**Recovery workflow:**
1. A crash occurs (syntax error, nil index, etc.)
2. The error mode activates, showing the error message
3. Fix the offending module in your editor
4. Reload it: `,reload module-name`
5. Press space to recover — the game resumes

Sometimes multiple modules need reloading to fully recover (e.g., if a module that depends on the broken one was also loaded in a bad state).

This makes it safe to set up file watchers that auto-reload on save. A crash mid-thought won't kill the game session.

---

## Common Pitfalls

**Module-level locals reset on reload.** Any `(local x 0)` at the top of a module goes back to `0` when you `,reload` it. Use the state module or `persist` macro for values that should survive.

**Metatables become disconnected after reload.** When a module is reloaded, its metatable is a new table. Objects created before the reload still hold a reference to the old metatable — their methods won't reflect your changes. Use `hot-table` to keep the reference stable.

**Overwriting Love2D callbacks directly.** Setting `love.draw` or `love.update` from a module or the REPL bypasses the mode system and leads to unrecoverable crashes. Always use mode callbacks.

**LuaJIT vs Lua 5.1 compatibility.** If you're targeting web builds (lovejs uses Lua 5.1, not LuaJIT), test on both. Some LuaJIT-specific features (bitwise operators, FFI) won't work in web builds.
