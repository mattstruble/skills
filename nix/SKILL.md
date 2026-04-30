---
name: nix
description: Use this skill for any Nix, NixOS, Flakes, Home Manager, or nix-darwin task. Also trigger when the user mentions flake.nix, devShells, mkShell, nixos-rebuild, darwin-rebuild, home-manager switch, nix develop, overlays, derivations, or anything involving declarative system/package configuration on Linux or macOS — even if they don't explicitly say 'Nix'. NOT for writing packages from scratch with stdenv.mkDerivation or language-specific builders (see nix-packaging). NOT for the dendritic flake-parts pattern — if the query mentions import-tree, `flake.modules.<class>.<aspect>`, aspect-oriented config, generic module class, or feature-based module sharing across NixOS/darwin, see nix-dendritic instead.
---

# Nix Ecosystem Guide

## Core Philosophy

1. **Declarative over Imperative** - Describe desired state, not steps to reach it
2. **Reproducibility** - Lock files (`flake.lock`) pin exact versions
3. **Immutability** - Nix Store is read-only; same inputs = same outputs
4. **Rollback** - Every generation preserved; instant recovery via boot menu (NixOS) or `--rollback` (all platforms)

## Flake Structure

```nix
{
  description = "My Nix configuration";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-25.11";
    home-manager = {
      url = "github:nix-community/home-manager/release-25.11";
      inputs.nixpkgs.follows = "nixpkgs";  # Avoid duplicate nixpkgs evaluations
    };
    # macOS support
    nix-darwin = {
      url = "github:nix-darwin/nix-darwin/nix-darwin-25.11";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = { self, nixpkgs, home-manager, nix-darwin, ... }@inputs: {
    # NixOS configurations
    nixosConfigurations.hostname = nixpkgs.lib.nixosSystem {
      system = "x86_64-linux";
      modules = [ ./configuration.nix ];
    };

    # macOS configurations
    darwinConfigurations.hostname = nix-darwin.lib.darwinSystem {
      modules = [
        ./darwin.nix
        { nixpkgs.hostPlatform = "aarch64-darwin"; }  # or x86_64-darwin for Intel
      ];
    };

    # Development shells
    devShells.x86_64-linux.default = nixpkgs.legacyPackages.x86_64-linux.mkShell {
      packages = [ /* ... */ ];
    };
  };
}
```

## Essential Patterns

### Input Management
```nix
inputs = {
  # Add an unstable channel alongside stable (shown in Flake Structure above)
  unstable.url = "github:NixOS/nixpkgs/nixos-unstable";

  # Non-flake input (config files, plain repos, etc.)
  private-config = {
    url = "git+ssh://git@github.com/user/config.git";
    flake = false;
  };
};
```

### Module System
```nix
# Every module has three parts: imports, options, config
{ config, pkgs, lib, ... }: {
  imports = [ ./hardware.nix ./services.nix ];

  options.myOption = lib.mkOption {
    type = lib.types.bool;
    default = false;
  };

  config = lib.mkIf config.myOption {
    # Only applied when myOption is true
  };
}
```

### Priority Control

The module system merges options from multiple modules. When two modules set the same option, the **lower priority number wins** (overrides the others).

```nix
{
  # lib.mkDefault (priority 1000) - loses to almost everything
  # Use in shared/common modules so host-specific configs can override
  services.nginx.enable = lib.mkDefault true;

  # Direct assignment (priority 100) - normal, overrides mkDefault
  services.nginx.enable = true;

  # lib.mkForce (priority 50) - wins over everything
  # Use when another module sets a value you can't change any other way
  services.nginx.enable = lib.mkForce false;
}
```

### Package Customization

Three levels of customization, from least to most invasive:

```nix
{
  # override: change function arguments (what goes INTO a package build)
  # Use when a package accepts configuration parameters (e.g., enabling optional features)
  pkgs.fcitx5-rime.override { rimeDataPkgs = [ ./custom-rime ]; }

  # overrideAttrs: change derivation attributes (the build itself)
  # Use when you need to patch source, change build flags, or pin a version
  pkgs.hello.overrideAttrs (old: { doCheck = false; })

  # Overlays: modify packages globally across your entire config
  # Use when you want the change to apply everywhere (all dependents use the modified version)
  # Warning: overlays invalidate binary cache for affected packages — they'll build from source
  nixpkgs.overlays = [
    (final: prev: {
      myPackage = prev.myPackage.override { /* ... */ };
    })
  ];
}
```

**Rule of thumb:** `override` for feature flags → `overrideAttrs` for build changes → overlays for global changes. See `references/nixpkgs-advanced.md` for full details including `callPackage` and trivial builders.

## Platform-Specific

### NixOS
```bash
sudo nixos-rebuild switch --flake .#hostname
sudo nixos-rebuild boot --flake .#hostname    # apply on next boot only
sudo nixos-rebuild test --flake .#hostname    # test without creating boot entry
```

### nix-darwin (macOS)

nix-darwin now requires `sudo` and `system.primaryUser` in your config:
```nix
# In darwin.nix — this is required:
system.primaryUser = "username";
```
```bash
sudo darwin-rebuild switch --flake .#hostname
```

### Home Manager
```nix
# As NixOS/Darwin module (recommended):
home-manager.useGlobalPkgs = true;
home-manager.useUserPackages = true;
home-manager.users.username = import ./home.nix;
```
```bash
# Standalone:
home-manager switch --flake .#username@hostname
```

## Commands Reference

| Task | Command |
|------|---------|
| Rebuild NixOS | `sudo nixos-rebuild switch --flake .#hostname` |
| Rebuild Darwin | `sudo darwin-rebuild switch --flake .#hostname` |
| Dev shell | `nix develop` |
| Temp package | `nix shell nixpkgs#package` |
| Run without install | `nix run nixpkgs#package` |
| Update all inputs | `nix flake update` |
| Update single input | `nix flake update nixpkgs` |
| GC old generations | `sudo nix-collect-garbage -d` |
| List generations | `nix profile history --profile /nix/var/nix/profiles/system` |
| Debug build | `sudo nixos-rebuild switch --show-trace -L -v` |
| REPL | `nix repl` then `:lf .` to load flake |
| Search packages | `nix search nixpkgs#<term>` |
| Explore flake outputs | `nix flake show` or `nix flake show github:owner/repo` |

## Common Gotchas

1. **Untracked files invisible to flakes** - Run `git add` before any flake command. Nix only copies git-tracked files into the store for evaluation (staged but uncommitted is fine).
2. **allowUnfree breaks in devShells** - `nixpkgs.config.allowUnfree` doesn't flow into standalone `nix develop` because devShells bypass the module system. Use `nixpkgs-unfree` (recommended), `--impure`, or `~/.config/nixpkgs/config.nix`. See `references/nixpkgs-advanced.md` for details.
3. **Duplicate nixpkgs downloads** - Use `inputs.nixpkgs.follows = "nixpkgs"` on all inputs that depend on nixpkgs, or each input downloads its own copy.
4. **Python pip install fails** - Nix's sandbox blocks network and filesystem writes. Use `venv` inside `mkShell`, `poetry2nix`, or containers. See `references/dev-environments.md`.
5. **Downloaded binaries crash** - Pre-built binaries expect FHS paths (`/lib`, `/usr`) that don't exist on NixOS. Use `pkgs.buildFHSEnv` or `nix-ld`. See `references/dev-environments.md`.
6. **String interpolation in multi-line strings** - Use `''$` to escape `${` inside `''...''` strings. See `references/nix-language.md` for the full escaping table.
7. **Build from source unexpectedly** - Overlays change derivation hashes, invalidating binary cache. Consider a separate nixpkgs instance for overlayed packages. See `references/nixpkgs-advanced.md`.
8. **`legacyPackages` is not legacy** - When using `nix search` or consuming Nixpkgs outputs directly, packages appear under `legacyPackages` not `packages`. The name is misleading — it's how Nixpkgs exposes its deep nested package set through the flake interface. Use `nixpkgs.legacyPackages.${system}` to access them programmatically.

## References

Consult these based on what you're working on:

| Reference | When to read it |
|-----------|----------------|
| `references/nix-language.md` | Writing or debugging Nix expressions, syntax, builtins, `lib` functions, string escaping |
| `references/flakes.md` | Flake input types, outputs schema, lock files, flake-parts, flake-compat |
| `references/home-manager.md` | User dotfiles, program modules, file management, `mkOutOfStoreSymlink`, activation scripts |
| `references/nix-darwin.md` | macOS system config, Homebrew integration, system defaults (Dock/Finder/Keyboard), launchd, TouchID |
| `references/nixpkgs-advanced.md` | Custom packages, `callPackage`, overlays, overrides, unfree packages, trivial builders, fetchers |
| `references/dev-environments.md` | Dev shells, `mkShell`, direnv, devenv, FHS compat, nix-ld, language-specific setups (Python, Rust, Node, etc.) |
| `references/best-practices.md` | Project structure, debugging (`nix repl`, `--show-trace`), deployment (Colmena, deploy-rs), secrets, CI/CD |
| `references/templates.md` | Copy-paste `flake.nix` starting points for NixOS, Darwin, Home Manager, dev shells, Docker images |
