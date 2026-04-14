# Persistence Macros for Fennel + Love2D

Two macros for preserving module-local state across hot-reloads. Both are controlled by a `params.fnl` module — in release builds they compile to plain `local` with no runtime overhead.

---

## `persist` — Survive Module Reload

**Problem:** Module-level locals reset to their initial values every time you `,reload` a module. A counter, a timer, or any accumulated state is lost.

**How it works:** On first load, stores the value in `_G._persist[module][handle]`. On subsequent loads (reloads), finds the existing value and returns it instead of re-initializing.

### Macro Code

Save as `persist.fnlm` (a Fennel macro file):

```fennel
;; persist.fnlm
(fn persist [handle literal]
  (local (ok params?) (pcall (fn [] (require :params))))
  (local params (if ok params? {:persist true}))
  (if params.persist
    `(local ,handle
          (let [module# (or ... :entry-module)]
            (print (string.format "Persiting %s %s" module# ,(tostring handle)))
            (when (not _G._persist) (tset _G :_persist {}))
            (when (not (. _G._persist module#)) (tset _G :_persist module# {}))
            (when (not (. _G._persist module# ,(tostring handle)))
              (tset _G :_persist module# ,(tostring handle) ,literal))
            (. _G :_persist module# ,(tostring handle))))
    `(local ,handle ,literal)))
```

Note: `"Persiting"` is the original spelling from the source — preserve it to match the macro output exactly.

**Constraint:** The `literal` argument is emitted verbatim into the generated code. It should be a cheap, side-effect-free expression — a literal value, `{}`, or a simple constructor. For expensive resources (images, sounds), load them in `love.load` or `activate` and store in the state module instead. The `literal` expression is evaluated on every load (including reloads), but the guard prevents it from being stored more than once.

### Usage

```fennel
;; mode-game.fnl
(import-macros {: persist} :persist)

;; This counter survives ,reload — it won't reset to 0
(persist enemy-count 0)

;; This local WILL reset on reload (intentional for config values)
(local speed 150)

(fn update [dt set-mode]
  (set enemy-count (+ enemy-count 1)))

(fn draw []
  (love.graphics.print (.. "Enemies: " enemy-count) 10 10))

{: draw : update}
```

After `,reload mode-game`, `enemy-count` retains its current value. `speed` resets to `150` (which is fine — it's a constant).

---

## `hot-table` — Keep Metatable References Valid

**Problem:** When a module is reloaded, its metatable is a brand-new table. Any objects created before the reload still hold a reference to the *old* metatable — their methods won't reflect your changes.

**How it works:** Persists the table reference itself (so existing objects keep pointing to the same table), but merges the new values into it on each reload. The reference stays stable; the contents update.

**Important:** `hot-table` performs a merge, not a replacement. Keys that existed in the old table but are absent from the new one are not removed — they persist until the game restarts. If you rename or delete a method, the old name remains callable on existing objects until restart. This is intentional: removing keys would break existing references. The second argument must be a literal table `{...}` — the macro splices it directly into the generated code.

### Macro Code

Add to `persist.fnlm` alongside the `persist` macro:

```fennel
(fn hot-table [handle literal]
  (local (ok params?) (pcall (fn [] (require :params))))
  (local params (if ok params? {:persist true}))
  (if params.persist
    `(local ,handle
          (let [module# (or ... :entry-module)]
            (print (string.format "Replacing %s %s" module# ,(tostring handle)))
            (when (not _G._persist) (tset _G :_persist {}))
            (when (not (. _G._persist module#)) (tset _G :_persist module# {}))
            (when (not (. _G._persist module# ,(tostring handle)))
              (tset _G :_persist module# ,(tostring handle) {}))
            (each [key# value# (pairs ,literal)]
              (tset _G :_persist module# ,(tostring handle)  key# value#))
            (. _G :_persist module# ,(tostring handle))))
    `(local ,handle ,literal)))
```

Export both macros at the bottom of `persist.fnlm`:

```fennel
{: persist : hot-table}
```

### Usage

```fennel
;; enemy.fnl
(import-macros {: persist : hot-table} :persist)

;; The Enemy table reference stays stable across reloads.
;; Existing enemy objects keep their metatable — methods update in place.
(hot-table Enemy
  {:new (fn [x y]
          (setmetatable {:x x :y y :hp 3} Enemy))
   :draw (fn [self]
           (love.graphics.circle :fill self.x self.y 8))
   :update (fn [self dt]
             (set self.x (+ self.x (* 50 dt))))})

;; Set __index after hot-table, not inside it.
;; Inside the literal, Enemy refers to the transient local — not the persisted table.
(set Enemy.__index Enemy)

;; Persist the enemy list so it survives reload
(persist enemies [])

(fn activate []
  ;; Reset enemies when this mode becomes active
  (set enemies [(Enemy.new 100 100) (Enemy.new 200 150)]))

{: activate}
```

After `,reload enemy`, all existing `Enemy` instances immediately use the updated `draw`, `update`, and other methods — no need to recreate them.

**Note:** Do not include `__index = Self` inside the `hot-table` literal. After reload, `hot-table` would set `__index` to the transient local table (not the persisted one), breaking method dispatch for objects created after the reload. Always set `__index` after the `hot-table` call.

---

## `params.fnl` — Dev vs Release Control

Both macros use `pcall` to load `params`. If `params` can't be loaded (module missing or errors), they default to `{:persist true}` — safe for development.

```fennel
;; params.fnl — development build
{:persist true}
```

```fennel
;; params.fnl — release build
{:persist false}
```

In release mode, both macros expand to plain `local`:

```fennel
;; (persist enemy-count 0) expands to:
(local enemy-count 0)

;; (hot-table Enemy {...}) expands to:
(local Enemy {...})
```

No `_G._persist` table, no print statements, no overhead. The macros are purely a development tool.

**Tip:** Keep `params.fnl` in `.gitignore` or use a build step to swap it. Without `params.fnl`, the `pcall` fallback defaults to `{:persist true}` (dev mode) — your release build will include `_G._persist` writes and debug `print` statements. Ensure your release build step either includes `params.fnl` with `{:persist false}` or verifies the file is present before packaging.
