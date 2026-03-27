---
name: nix-dendritic
description: "Dendritic Nix configuration pattern -- aspect-oriented flake-parts modules for multi-host, multi-platform NixOS/nix-darwin/Home Manager setups. Use when the user mentions dendritic, flake-parts modules, aspect-oriented Nix config, feature-centric configuration, `flake.modules.<class>.<aspect>`, import-tree, flake-file, or wants to restructure their Nix config to share features across NixOS/darwin/Home Manager. Also trigger when the user has a multi-host or cross-platform Nix setup and wants to reduce duplication or improve modularity. NOT for general Nix questions, basic flake setup, or single-machine configs -- see the `nix` skill for those."
---

# Dendritic Nix Configuration

This skill covers the Dendritic configuration pattern for Nix. It assumes familiarity with
Nix flakes, the module system, and Home Manager. For those fundamentals, see the `nix` skill.

## Core Principles

Dendritic is a *configuration pattern*, not a library or framework. It uses flake-parts to
structure Nix configs around features (cross-cutting concerns) rather than hosts.

1. **Every `.nix` file is a flake-parts module.** One semantic meaning across the entire codebase -- no guessing whether a file is a NixOS module, a Home Manager config, or a package.

2. **Features are the unit of composition, not hosts.** Name files after *how you use your environment* -- the usability concern, not the tool or host. Ask "what experience am I configuring?" rather than "what package am I installing?" For example, `scrolling-desktop.nix` (enables `niri` on Linux and `paneru` on macOS) is better than `niri.nix`, and `tui.nix` or `ai.nix` are better than lists of specific packages. Simpler features can still be named after what they configure (`ssh.nix`, `printing.nix`), but the key insight is: features describe *capabilities*, hosts consume them. A host module is a thin list of feature imports.

3. **Terminology: features vs aspects.** A *feature* is the flake-parts module file (e.g., `ssh.nix`). An *aspect* is a `flake.modules.<class>.<name>` definition within that file. A single feature can contain multiple aspects (one per module class) plus flake-parts boilerplate. When the design guide says "aspect," it means the named module definition; when it says "feature," it means the enclosing file/directory.

4. **`flake.modules.<class>.<aspect>` is the core mechanism.** This requires importing `inputs.flake-parts.flakeModules.modules` in your flake-parts setup (see scaffolding template). Classes include `nixos`, `darwin`, `homeManager`, `generic` (for modules importable across any class -- it works because flake-parts omits the class constraint, so the module system accepts the options in any context), and any custom name you define. Aspects are referenced via `inputs.self.modules.<class>.<aspect>`. All features are auto-loaded by `import-tree`, so all aspect definitions are registered with flake-parts. However, an aspect only takes effect when something imports it -- either a host module's `imports` list or flake-parts boilerplate like `flake.nixosConfigurations`.

5. **The dendritic pattern imposes no file organization restrictions.** You are free to organize and name files however suits your mental model -- subdirectory structure is purely organizational and has no effect on module loading. That said, organizing by feature category helps navigation. A common convention from the design guide:

   ```
   modules/
   ├── factory/          -- parameterized feature generation
   ├── hosts/            -- host definitions (thin compositions)
   ├── nix/              -- framework boilerplate (flake-parts.nix)
   │   └── tools/        -- tool integrations (home-manager, secrets)
   ├── programs/         -- user-facing applications (browser, shell, office)
   ├── services/         -- system services (ssh, printing, syncthing)
   ├── system/
   │   ├── settings/     -- system-level config (bluetooth, network, constants)
   │   └── system-types/ -- inheritance hierarchy (default -> cli -> desktop)
   └── users/            -- per-user modules
   ```

   The critical rule is: organize by what features *do*, not which module class they configure. Directories named `nixos/`, `darwin/`, `home-manager/` force you to split a single feature across multiple places.

6. **No manual imports.** `import-tree` auto-loads every `.nix` file under `modules/`. Files or directories with `/_` in their path are ignored -- prefix with `_` to temporarily disable features during development.

7. **Feature closures.** Everything needed for a feature to work lives in one place -- system config, user config, packages, secrets. If you need to debug SSH, look in `ssh.nix`. If a feature's code grows large, split it into multiple files within a feature directory -- all files contribute to the same feature through module merging.

8. **Incremental features.** Add capability by adding files. Remove capability by deleting or prefixing with `_`. No other files need to change.

9. **`perSystem` for per-system outputs.** Use `perSystem` in any feature module to define packages, devShells, checks, and other per-system flake outputs alongside the feature they belong to:

   ```nix
   # modules/services/ssh.nix (alongside the flake.modules definitions)
   perSystem = { pkgs, ... }: {
     packages.deploy-ssh = pkgs.writeShellScriptBin "deploy-ssh" ''
       # deployment script taking advantage of ssh facilities
     '';
   };
   ```

## Example: The SSH Feature

This single file is a *feature* containing *aspects* for three module classes:

```nix
# modules/services/ssh.nix -- one feature, multiple aspects
{ inputs, config, ... }:
let
  scpPort = 2277;  # shared across classes via let-binding -- no specialArgs needed
in
{
  flake.modules.nixos.ssh = {          # <- NixOS aspect
    services.openssh = {
      enable = true;
      ports = [ scpPort ];
    };
    networking.firewall.allowedTCPPorts = [ scpPort ];
  };

  flake.modules.darwin.ssh = {         # <- Darwin aspect
    system.defaults.ssh = {
      # macOS SSH server config
    };
  };

  flake.modules.homeManager.ssh = {    # <- Home Manager aspect
    programs.ssh = {
      enable = true;
      matchBlocks = {
        # ~/.ssh/config entries
      };
    };
  };
}
```

Key things to notice:
- The file name (`ssh.nix`) describes the capability, not a host or package
- `scpPort` is shared across classes via a let-binding -- no `specialArgs` needed
- Each class gets only the config relevant to it
- A host activates SSH by adding `ssh` to its imports list

## Scaffolding a New Dendritic Config

Read `references/scaffolding.md` for the full scaffold templates (`flake.nix`,
`modules/nix/flake-parts.nix`, `modules/system/system-types/system-default.nix`). Ask the
user which platforms they need (NixOS, Darwin, Home Manager standalone), then generate from
those templates.

After scaffolding, create feature modules as the user describes what they need. The directory
structure is flexible, but here's a common convention for where things go:

| Directory | What goes here | Create when |
|-----------|---------------|-------------|
| `programs/` | User-facing applications (browser, shell, office) | First user app feature |
| `services/` | System services and daemons (ssh, printing, syncthing) | First service feature |
| `system/settings/` | System-level config (bluetooth, network, constants) | First system setting |
| `system/system-types/` | Inheritance hierarchy (default -> cli -> desktop) | Already scaffolded (uncomment Darwin/HM blocks if needed) |
| `users/` | Per-user modules | First user module |
| `hosts/` | Host definitions (thin compositions of feature imports) | First host definition |
| `factory/` | Factory functions for parameterized features | First factory pattern |
| `nix/` | Framework boilerplate (flake-parts.nix) | Already scaffolded |
| `nix/tools/` | Nix tool integrations (home-manager, secrets, impermanence) | First tool integration |

## Pattern Selection Decision Tree

When the user wants to add a feature, walk through these questions to select aspect pattern(s).
Most features combine 2-3 patterns. Read `references/aspect-patterns.md` for implementation
details and code examples once you've identified the pattern(s).

1. **Single module class only?** (e.g., just NixOS or just Home Manager)
   -> Simple Aspect

2. **Multiple module classes?** (e.g., NixOS + Darwin + Home Manager aspects in one feature file)
   -> Simple Aspect with one block per class

3. **System-level feature that requires mandatory Home Manager config?** (e.g., GNOME needs both system services and user extensions)
   -> Multi Context Aspect (system module pulls in HM module via `home-manager.sharedModules`)

4. **Feature that extends or composes other features?** (e.g., `system-desktop` builds on `system-cli`)
   -> Inheritance Aspect (use `imports` to pull in parent aspects)

5. **Platform-specific behavior within a single module class?** (e.g., different packages on Linux vs Darwin in a Home Manager module)
   -> Conditional Aspect (`lib.mkMerge` + `lib.mkIf pkgs.stdenv.isLinux/isDarwin`)

6. **Multiple features contribute to the same service?** (e.g., each host adds its device to syncthing)
   -> Collector Aspect (multiple files define the same `flake.modules.<class>.<aspect>`)

7. **Shared constants needed across module classes?** (e.g., admin email, domain name, timezone)
   -> Constants Aspect (generic module with custom options)

8. **Repeated config structure applied to different targets?** (e.g., network subnet definitions reused across interfaces)
   -> DRY Aspect (custom module class as reusable data)

9. **Parameterized feature generation?** (e.g., user modules that follow the same structure but differ in name/permissions)
   -> Factory Aspect (function that returns module attrsets)

## Anti-patterns

### Hard errors — these will break your config

**Do not put `lib.mkIf` in `imports`.** Nix evaluates the `imports` list unconditionally —
conditions are silently ignored, so the module is always imported regardless of the condition.
Use the Conditional Aspect instead: put `lib.mkMerge` + `lib.mkIf` on config *values*, not on
imports.

**Do not import across module classes.** A `nixos` module cannot import a `darwin` module
because they are different module systems with different option sets -- Nix will error on unknown
options. If you need a module accessible from multiple classes, define it under the `generic`
class (`flake.modules.generic.<name>`) and import it from each class's base module. The Constants
Aspect is the canonical example of this pattern.

**Do not create import cycles.** If module A imports B which imports A, Nix will fail with an
infinite recursion error. Diamond imports are fine -- A and C can both import B, and Nix will
deduplicate the same module reference. However, design your hierarchy so each module is imported
once per path to avoid unexpected option merging from duplicate imports.

### Guidance — not errors, but against the pattern's spirit

**Avoid `specialArgs` and `extraSpecialArgs`.** Every flake-parts module file receives `inputs`
as a module argument at the outer level — no need to pass it through `specialArgs`. For values
shared within a file, use a `let` binding at the top of the file (visible to all inner module
blocks). For values shared across files, use the Constants Aspect. `specialArgs` is a workaround
for a problem that doesn't exist in dendritic configs — using it means you're fighting the
framework rather than working with it.

**Keep `flake.nix` to inputs and the `mkFlake` call.** If configuration logic lives in
`flake.nix`, it bypasses `import-tree` and breaks the "every file is a flake-parts module"
invariant. It also makes the config harder to navigate — readers expect `flake.nix` to be
minimal. Move all logic into `modules/`.

**Organize directories by feature, not module class.** Directories named `nixos/`, `darwin/`,
`home-manager/`, or `home/` force you to split a feature across multiple files. SSH config for
NixOS ends up in `nixos/ssh.nix` and SSH config for Home Manager ends up in `home/ssh.nix` --
now you have to look in two places to understand SSH. In dendritic, `services/ssh.nix` holds
all SSH config for all platforms in one place.

**Name files after capabilities, not tools or hosts.** Think about *how you use your environment*.
`scrolling-desktop.nix` (which enables `niri` on Linux and `paneru` on macOS) is better than
`niri.nix` because the capability is the same across platforms even though the tools differ.
Similarly, `tui.nix`, `ai.nix`, or `macos-like-bindings.nix` describe the experience, not the
implementation. Simple features like `ssh.nix` or `printing.nix` are fine when the capability
and tool are effectively synonymous.

**Use imports as the enable toggle, not `enable = true` flags.** In dendritic, you activate a
feature by adding its aspect to a host's `imports` list. Custom `enable` options add indirection
without benefit — the presence or absence of the import is already the toggle.

## References

| Reference | When to read it |
|-----------|----------------|
| `references/aspect-patterns.md` | Writing feature modules or selecting aspect patterns |
| `references/scaffolding.md` | Setting up a new dendritic config from scratch |
| `references/migration.md` | Converting an existing Nix config to dendritic |
| `references/ecosystem.md` | Setting up flake-parts/import-tree, using flake-file for co-located inputs, exploring alternatives |
