---
name: nix
description: "Comprehensive NixOS, Nix Flakes, Home Manager, and nix-darwin skill. Covers declarative system configuration, reproducible environments, package management, and cross-platform Nix workflows. Activate for any Nix/NixOS/Flakes/Home-Manager/nix-darwin tasks. Also use when the user mentions flake.nix, devShells, mkShell, nixos-rebuild, darwin-rebuild, home-manager switch, nix develop, overlays, derivations, or anything involving declarative system/package configuration on Linux or macOS -- even if they don't explicitly say 'Nix'."
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
  nixpkgs.url = "github:NixOS/nixpkgs/nixos-25.11";
  unstable.url = "github:NixOS/nixpkgs/nixos-unstable";

  # Pin dependencies to your nixpkgs to avoid downloading multiple copies
  home-manager.inputs.nixpkgs.follows = "nixpkgs";

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
```nix
{
  # lib.mkDefault (priority 1000) - for base module defaults, easily overridden
  services.nginx.enable = lib.mkDefault true;

  # Direct assignment (priority 100) - normal configuration
  services.nginx.enable = true;

  # lib.mkForce (priority 50) - last resort override
  services.nginx.enable = lib.mkForce false;
}
```

### Package Customization
```nix
{
  # Override function arguments (change what goes INTO a package build)
  pkgs.fcitx5-rime.override { rimeDataPkgs = [ ./custom-rime ]; }

  # Override derivation attributes (change the build itself)
  pkgs.hello.overrideAttrs (old: { doCheck = false; })

  # Overlays (modify packages globally across your config)
  nixpkgs.overlays = [
    (final: prev: {
      myPackage = prev.myPackage.override { /* ... */ };
    })
  ];
}
```

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

## Common Gotchas

1. **Untracked files invisible to flakes** - Run `git add` before any flake command. Nix only sees files tracked by git (even if staged but not committed).
2. **allowUnfree breaks in devShells** - `nixpkgs.config.allowUnfree` from your system config doesn't flow into standalone `nix develop`. Use `--impure` flag, an overlay, or set it in `~/.config/nixpkgs/config.nix`.
3. **Duplicate nixpkgs downloads** - Use `inputs.nixpkgs.follows = "nixpkgs"` on all inputs that depend on nixpkgs, or you'll download and evaluate it multiple times.
4. **Python pip/pip install fails** - Nix's sandboxed builds can't run pip. Use `venv` inside a `mkShell`, `poetry2nix`, or containers.
5. **Downloaded binaries crash** - Pre-built binaries expect FHS paths (`/lib`, `/usr`). Use `pkgs.buildFHSEnv` for a compatibility wrapper or `nix-ld` system-wide.
6. **String interpolation in multi-line strings** - Use `''$` to escape `${` inside `''...''` strings (e.g., `''${var}` evaluates the Nix variable, but `''\${var}` prevents interpolation).
7. **Build from source unexpectedly** - Overlays can invalidate the binary cache since they change the input hash. Consider a separate nixpkgs instance for overlayed packages.

## Development Environments

```nix
# In flake.nix outputs:
devShells.x86_64-linux.default = pkgs.mkShell {
  packages = with pkgs; [ nodejs python3 rustc ];

  shellHook = ''
    echo "Dev environment ready"
    export MY_VAR="value"
  '';

  # For C libraries that need LD_LIBRARY_PATH
  LD_LIBRARY_PATH = lib.makeLibraryPath [ pkgs.openssl ];
};
```

### direnv Integration
```bash
# .envrc
use flake
# or for unfree packages: use flake --impure
```

For higher-level dev environments with managed language versions, services (Postgres, Redis, etc.), and pre-commit hooks, see **devenv** in `references/dev-environments.md`.

## Debugging

```bash
# Verbose rebuild with full trace
sudo nixos-rebuild switch --show-trace --print-build-logs --verbose

# Interactive REPL — the fastest way to explore and debug
nix repl
:lf .                    # load current flake
:e pkgs.hello           # open package definition in $EDITOR
:b pkgs.hello           # build a derivation
inputs.<TAB>            # explore flake inputs
builtins.toString pkgs.hello  # show store path
```

## References

Consult these based on what you're working on:

| Reference | When to read it |
|-----------|----------------|
| `references/nix-language.md` | Writing or debugging Nix expressions, understanding syntax |
| `references/flakes.md` | Configuring flake inputs/outputs, understanding lock files |
| `references/home-manager.md` | Managing user dotfiles, programs, and services |
| `references/nix-darwin.md` | macOS system config, Homebrew integration, system defaults |
| `references/nixpkgs-advanced.md` | Custom packages, overlays, overrides, `callPackage` |
| `references/dev-environments.md` | Dev shells, direnv, FHS compat, devenv, language-specific setups |
| `references/best-practices.md` | Project structure, debugging, deployment, secrets, CI/CD |
| `references/templates.md` | Copy-paste flake.nix starting points for common setups |
