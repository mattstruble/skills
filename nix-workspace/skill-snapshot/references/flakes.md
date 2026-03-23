# Flakes Reference

## Overview

Flakes provide:
- **Hermetic evaluation** - No impure operations
- **Lock file** - Reproducible dependency versions
- **Standard structure** - Consistent `inputs`/`outputs` schema
- **Composability** - Easy to combine multiple flakes

> **Note:** Flakes are technically still an "experimental" Nix feature, but they are the de facto standard. The vast majority of modern Nix documentation, tooling, and community projects assume flakes. You should use them unless you have a specific reason not to.

## Enabling Flakes

```nix
# In configuration.nix or nix.conf
nix.settings.experimental-features = [ "nix-command" "flakes" ];
```

## Input Types

### GitHub
```nix
inputs = {
  # Default branch
  nixpkgs.url = "github:NixOS/nixpkgs";

  # Specific branch
  nixpkgs.url = "github:NixOS/nixpkgs/nixos-25.11";

  # Specific commit
  nixpkgs.url = "github:NixOS/nixpkgs/abc123def456";

  # Specific tag
  nixpkgs.url = "github:NixOS/nixpkgs/25.11";

  # Private repo (uses SSH)
  private.url = "github:owner/private-repo";
};
```

### Git
```nix
inputs = {
  # HTTPS
  repo.url = "git+https://git.example.com/repo.git";

  # SSH
  repo.url = "git+ssh://git@github.com/owner/repo.git";

  # Specific branch
  repo.url = "git+https://example.com/repo?ref=develop";

  # Specific tag
  repo.url = "git+https://example.com/repo?tag=v1.0.0";

  # Specific commit
  repo.url = "git+https://example.com/repo?rev=abc123";

  # Shallow clone
  repo.url = "git+ssh://git@github.com/owner/repo?shallow=1";
};
```

### Path (Local)
```nix
inputs = {
  # Local directory
  local.url = "path:/home/user/projects/my-flake";

  # Relative (from flake root)
  local.url = "path:./subdir";
};
```

### Tarball
```nix
inputs = {
  archive.url = "https://example.com/archive.tar.gz";
};
```

### Non-Flake Inputs
```nix
inputs = {
  # Config files, data, etc.
  dotfiles = {
    url = "github:user/dotfiles";
    flake = false;  # Don't evaluate as flake
  };
};

# Usage in outputs:
outputs = { dotfiles, ... }: {
  # Reference files directly
  home.file.".vimrc".source = "${dotfiles}/vimrc";
};
```

## Input Follows

Prevents downloading multiple versions of the same dependency:

```nix
inputs = {
  nixpkgs.url = "github:NixOS/nixpkgs/nixos-25.11";

  home-manager = {
    url = "github:nix-community/home-manager/release-25.11";
    inputs.nixpkgs.follows = "nixpkgs";  # Use OUR nixpkgs
  };

  # Nested follows
  foo = {
    url = "github:owner/foo";
    inputs.nixpkgs.follows = "nixpkgs";
    inputs.bar.follows = "bar";  # If foo has bar as input
  };
};
```

## Flake Outputs Schema

```nix
outputs = { self, nixpkgs, ... }: {
  # ===== Packages =====
  packages.<system>.<name> = derivation;
  packages.x86_64-linux.default = pkgs.hello;
  packages.x86_64-linux.myApp = pkgs.callPackage ./app.nix {};

  # ===== Applications =====
  apps.<system>.<name> = {
    type = "app";
    program = "${package}/bin/executable";
  };

  # ===== Development Shells =====
  devShells.<system>.<name> = pkgs.mkShell { ... };
  devShells.x86_64-linux.default = pkgs.mkShell {
    packages = [ pkgs.nodejs ];
  };

  # ===== NixOS Configurations =====
  nixosConfigurations.<hostname> = nixpkgs.lib.nixosSystem {
    system = "x86_64-linux";
    modules = [ ./configuration.nix ];
    specialArgs = { inherit inputs; };  # Pass to modules
  };

  # ===== Darwin Configurations =====
  darwinConfigurations.<hostname> = darwin.lib.darwinSystem {
    system = "aarch64-darwin";
    modules = [ ./darwin.nix ];
  };

  # ===== Home Manager Configurations =====
  homeConfigurations."user@host" = home-manager.lib.homeManagerConfiguration {
    pkgs = nixpkgs.legacyPackages.x86_64-linux;
    modules = [ ./home.nix ];
  };

  # ===== Overlays =====
  overlays.<name> = final: prev: { ... };
  overlays.default = final: prev: {
    myPackage = prev.myPackage.override { ... };
  };

  # ===== NixOS/Darwin Modules =====
  nixosModules.<name> = { config, ... }: { ... };
  darwinModules.<name> = { config, ... }: { ... };

  # ===== Templates =====
  templates.<name> = {
    path = ./template;
    description = "A template";
  };
  templates.default = { ... };

  # ===== Checks (CI) =====
  checks.<system>.<name> = derivation;

  # ===== Formatter =====
  formatter.<system> = pkgs.nixpkgs-fmt;  # or alejandra, nixfmt

  # ===== Library Functions =====
  lib = { ... };

  # ===== Hydra Jobs =====
  hydraJobs.<attr>.<system> = derivation;
};
```

## Lock File (flake.lock)

Auto-generated, contains exact versions:

```json
{
  "nodes": {
    "nixpkgs": {
      "locked": {
        "lastModified": 1234567890,
        "narHash": "sha256-...",
        "owner": "NixOS",
        "repo": "nixpkgs",
        "rev": "abc123...",
        "type": "github"
      }
    }
  }
}
```

## Flake Commands

```bash
# Initialize new flake
nix flake init
nix flake init -t templates#rust  # From template

# Show flake info
nix flake show
nix flake show github:NixOS/nixpkgs

# Show flake metadata
nix flake metadata

# Update all inputs
nix flake update

# Update specific input
nix flake update nixpkgs

# Lock to specific version
nix flake lock --override-input nixpkgs github:NixOS/nixpkgs/abc123

# Override input for a single build (without modifying flake.lock)
nix build --override-input nixpkgs github:NixOS/nixpkgs/nixos-unstable

# Check flake
nix flake check

# Build output
nix build .#packageName
nix build .#packages.x86_64-linux.default

# Run output
nix run .#appName

# Enter dev shell
nix develop
nix develop .#shellName

# Archive flake
nix flake archive

# Clone flake
nix flake clone github:owner/repo --dest ./local
```

## Self Reference

The `self` input refers to the current flake:

```nix
outputs = { self, nixpkgs, ... }: {
  packages.x86_64-linux.default = let
    # Access other outputs
    myLib = self.lib;

    # Access flake source
    src = self;
    version = self.rev or self.dirtyRev or "unknown";
  in
    # ...
};
```

## Flake Registry

Named shortcuts for common flakes:

```bash
# List registry
nix registry list

# Add to registry
nix registry add myflake github:owner/repo

# Pin version
nix registry pin nixpkgs

# Remove
nix registry remove myflake

# Use in commands
nix shell nixpkgs#hello  # Uses registry entry
nix shell github:NixOS/nixpkgs#hello  # Explicit
```

## flake-parts (Modular Flakes)

For complex flakes, [flake-parts](https://github.com/hercules-ci/flake-parts) provides module-based composition that eliminates boilerplate (especially the per-system repetition):

```nix
# flake.nix
{
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-25.11";
    flake-parts.url = "github:hercules-ci/flake-parts";
  };

  outputs = inputs@{ flake-parts, ... }:
    flake-parts.lib.mkFlake { inherit inputs; } {
      systems = [ "x86_64-linux" "aarch64-linux" "aarch64-darwin" "x86_64-darwin" ];

      perSystem = { pkgs, ... }: {
        packages.default = pkgs.hello;
        devShells.default = pkgs.mkShell { packages = [ pkgs.nil ]; };
      };

      flake = {
        # Non-per-system outputs go here
        nixosModules.default = { ... }: { };
      };
    };
}
```

## flake-compat (Using Flakes with Non-Flake Nix)

If you need your flake to work for users who haven't enabled the flakes experimental feature:

```nix
# default.nix — allows `nix-build` and `nix-shell` without flakes
(import (
  let
    lock = builtins.fromJSON (builtins.readFile ./flake.lock);
    nodeName = lock.nodes.root.inputs.flake-compat;
    compat = lock.nodes.${nodeName}.locked;
  in
    fetchTarball {
      url = "https://github.com/edolstra/flake-compat/archive/${compat.rev}.tar.gz";
      sha256 = compat.narHash;
    }
) { src = ./.; }).defaultNix

# Add flake-compat as a flake input:
# inputs.flake-compat.url = "github:edolstra/flake-compat";
```
