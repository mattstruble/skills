---
name: nix-dendritic
description: "Dendritic Nix configuration pattern -- aspect-oriented flake-parts modules for multi-host, multi-platform NixOS/nix-darwin/Home Manager setups. Covers scaffolding new dendritic configs, writing feature modules across configuration classes, selecting aspect patterns (Simple, Multi Context, Inheritance, Conditional, Collector, Constants, DRY, Factory), and migrating existing Nix configs to the dendritic structure. Use when the user mentions dendritic, flake-parts modules, aspect-oriented Nix config, feature-centric configuration, `flake.modules.<class>.<aspect>`, import-tree, flake-file, or wants to restructure their Nix config to share features across NixOS/darwin/Home Manager. Also trigger when the user has a multi-host or cross-platform Nix setup and wants to reduce duplication or improve modularity. NOT for general Nix questions, basic flake setup, or single-machine configs -- see the `nix` skill for those."
---

# Dendritic Nix Configuration

This skill covers the Dendritic configuration pattern for Nix. It assumes familiarity with
Nix flakes, the module system, and Home Manager. For those fundamentals, see the `nix` skill.

## Core Principles

Dendritic is a *configuration pattern*, not a library or framework. It uses flake-parts to
structure Nix configs around features (cross-cutting concerns) rather than hosts.

1. **Every `.nix` file is a flake-parts module.** One semantic meaning across the entire codebase -- no guessing whether a file is a NixOS module, a Home Manager config, or a package.

2. **Features are the unit of composition, not hosts.** Name files after what they do (`ssh.nix`, `printing.nix`, `desktop-environment.nix`), not where they run (`my-laptop.nix`). A host module is a thin list of feature imports.

3. **An aspect configures a cross-cutting concern across module classes.** A single `ssh.nix` file defines `flake.modules.nixos.ssh`, `flake.modules.darwin.ssh`, and `flake.modules.homeManager.ssh` -- all the SSH config for all platforms in one place.

4. **`flake.modules.<class>.<aspect>` is the core mechanism.** Classes include `nixos`, `darwin`, `homeManager`, and any custom name. Aspects are referenced via `inputs.self.modules.<class>.<aspect>`.

5. **File organization is free.** The pattern imposes no directory structure. Paths serve as documentation -- organize files in whatever way reflects your mental model.

6. **No manual imports.** `import-tree` auto-loads every `.nix` file under `modules/`. A module becomes active only when another module imports its aspect via `imports`.

7. **Feature closures.** Everything needed for a feature to work lives in one place -- system config, user config, packages, secrets. If you need to debug SSH, look in `ssh.nix`.

8. **Incremental features.** Add capability by adding files. Remove capability by deleting or prefixing with `_`. No other files need to change.

## Example: The SSH Aspect

This single file configures SSH across NixOS, Darwin, and Home Manager:

```nix
# modules/services/ssh.nix
{ inputs, config, ... }:
let
  scpPort = 2277;
in
{
  flake.modules.nixos.ssh = {
    services.openssh = {
      enable = true;
      ports = [ scpPort ];
    };
    networking.firewall.allowedTCPPorts = [ scpPort ];
  };

  flake.modules.darwin.ssh = {
    system.defaults.ssh = {
      # macOS SSH server config
    };
  };

  flake.modules.homeManager.ssh = {
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
- `scpPort` is shared across classes via a let-binding -- no `specialArgs` needed
- Each class gets only the config relevant to it
- The file name (`ssh.nix`) documents what this feature does

## Scaffolding a New Dendritic Config

When setting up a new dendritic config, ask the user which platforms they need (NixOS, Darwin,
Home Manager standalone), then generate this minimal scaffold:

### flake.nix

```nix
{
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-parts.url = "github:hercules-ci/flake-parts";
    import-tree.url = "github:vic/import-tree";

    home-manager = {
      url = "github:nix-community/home-manager";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    # Include for Darwin support:
    # nix-darwin = {
    #   url = "github:nix-darwin/nix-darwin";
    #   inputs.nixpkgs.follows = "nixpkgs";
    # };
  };

  outputs = inputs:
    inputs.flake-parts.lib.mkFlake { inherit inputs; } (inputs.import-tree ./modules);
}
```

Uncomment `nix-darwin` if the user needs macOS support. Add other inputs as needed.

### modules/nix/flake-parts.nix

```nix
{ inputs, lib, ... }:
{
  imports = [
    inputs.flake-parts.flakeModules.modules
  ];

  systems = [
    "aarch64-darwin"
    "aarch64-linux"
    "x86_64-darwin"
    "x86_64-linux"
  ];

  # Helper: create a NixOS configuration from a module name
  config.flake.lib.mkNixos = system: name: {
    ${name} = inputs.nixpkgs.lib.nixosSystem {
      modules = [
        inputs.self.modules.nixos.${name}
        { nixpkgs.hostPlatform = lib.mkDefault system; }
      ];
    };
  };

  # Helper: create a Darwin configuration from a module name
  # config.flake.lib.mkDarwin = system: name: {
  #   ${name} = inputs.nix-darwin.lib.darwinSystem {
  #     modules = [
  #       inputs.self.modules.darwin.${name}
  #       { nixpkgs.hostPlatform = lib.mkDefault system; }
  #     ];
  #   };
  # };

  # Helper: create a standalone Home Manager configuration
  # config.flake.lib.mkHome = system: name: {
  #   ${name} = inputs.home-manager.lib.homeManagerConfiguration {
  #     pkgs = inputs.nixpkgs.legacyPackages.${system};
  #     modules = [ inputs.self.modules.homeManager.${name} ];
  #   };
  # };
}
```

Uncomment helpers as needed based on the user's target platforms. Trim `systems` to only
include architectures the user actually targets.

### modules/system/system-default.nix

```nix
{ inputs, ... }:
{
  flake.modules.nixos.system-default = {
    # Base NixOS config shared across all hosts
    nix.settings.experimental-features = [ "nix-command" "flakes" ];
  };

  # flake.modules.darwin.system-default = {
  #   # Base Darwin config shared across all hosts
  #   nix.settings.experimental-features = [ "nix-command" "flakes" ];
  # };

  # flake.modules.homeManager.system-default = {
  #   # Base Home Manager config
  # };
}
```

After generating the scaffold, iterate: the user describes a feature they need, you select
the appropriate aspect pattern(s) from the decision tree below, then generate the module.

## Pattern Selection Decision Tree

When the user wants to add a feature, walk through these questions to select aspect pattern(s).
Most features combine 2-3 patterns. Load `references/aspect-patterns.md` for implementation
details and code examples.

1. **Single module class only?** (e.g., just NixOS or just Home Manager)
   -> Simple Aspect

2. **Multiple module classes?** (e.g., NixOS + Darwin + Home Manager in one file)
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

These will cause errors or break the dendritic pattern:

**Do not use `specialArgs` or `extraSpecialArgs`.** The `inputs` argument is available in every
flake-parts module automatically. For other shared values, use let-bindings (for values within
a file) or the Constants Aspect (for values across files). `specialArgs` is a workaround for
a problem that doesn't exist in dendritic configs.

**Do not put `lib.mkIf` in `imports`.** Nix evaluates the `imports` list unconditionally --
conditions are ignored. Use the Conditional Aspect pattern (`lib.mkMerge` + `lib.mkIf` on
config values) instead.

**Do not import across module classes.** A `nixos` module cannot import a `darwin` module --
they are different module systems. Use the `generic` class for modules that need to be shared
across classes.

**Do not put logic in `flake.nix`.** Keep `flake.nix` to inputs and the `mkFlake` call.
All configuration logic belongs in `modules/`.

**Do not import the same module multiple times in one hierarchy path.** If module A imports B,
and module C also imports B, that's fine (B is deduplicated). But if A imports B which imports
A, you have a cycle.

Guidance (not hard errors, but against the pattern's spirit):

**Prefer feature-centric file names over host-centric.** Name files after what they configure
(`ssh.nix`, `desktop-environment.nix`), not where they run (`my-laptop.nix`). Host files should
be thin compositions of feature imports.

**Prefer importing a module over `enable = true` flags.** In dendritic, you "enable" a feature
by including its aspect in a host's `imports` list. You don't need custom `enable` options for
feature toggling -- the presence or absence of the import is the toggle.

## References

| Reference | When to read it |
|-----------|----------------|
| `references/aspect-patterns.md` | Writing feature modules or selecting aspect patterns |
| `references/migration.md` | Converting an existing Nix config to dendritic |
| `references/ecosystem.md` | Setting up flake-parts/import-tree, exploring alternatives |
