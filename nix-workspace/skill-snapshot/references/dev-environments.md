# Development Environments

## Overview

Four approaches for dev environments:
1. **nix shell** - Quick, temporary access to packages
2. **nix develop** - Full dev shell with build inputs
3. **direnv** - Automatic environment on directory entry
4. **devenv** - High-level dev shells with services, language management, and less boilerplate

## nix shell

Temporary shell with packages available:

```bash
# Single package
nix shell nixpkgs#nodejs

# Multiple packages
nix shell nixpkgs#nodejs nixpkgs#yarn nixpkgs#python3

# Run command directly
nix shell nixpkgs#cowsay --command cowsay "Hello"

# From specific nixpkgs version
nix shell github:NixOS/nixpkgs/nixos-25.11#nodejs
```

## nix run

Run package without installing:

```bash
# Run default program
nix run nixpkgs#hello

# Run specific program from package
nix run nixpkgs#python3 -- script.py

# Run from flake
nix run .#myApp
```

## nix develop

Enter development shell defined in flake:

```bash
# Default devShell
nix develop

# Named devShell
nix develop .#python

# From remote flake
nix develop github:owner/repo

# Run command without entering shell
nix develop --command bash -c "npm install && npm test"
```

### Impure mode
If your devShell needs access to system state (unfree config, environment variables at eval time):
```bash
nix develop --impure
```
This is sometimes needed for `allowUnfree` in devShells or when environment variables affect evaluation.

## pkgs.mkShell

Define development environment in `flake.nix`:

```nix
{
  outputs = { nixpkgs, ... }: let
    pkgs = nixpkgs.legacyPackages.x86_64-linux;
  in {
    devShells.x86_64-linux.default = pkgs.mkShell {
      # Packages available in shell
      packages = with pkgs; [
        nodejs_20
        yarn
        python3
        go
        rustc
        cargo
      ];

      # Build inputs (for compiling native extensions)
      buildInputs = with pkgs; [
        openssl
        zlib
      ];

      # Native build inputs (build tools)
      nativeBuildInputs = with pkgs; [
        pkg-config
        cmake
      ];

      # Environment variables
      MY_VAR = "value";
      RUST_SRC_PATH = "${pkgs.rust.packages.stable.rustPlatform.rustLibSrc}";

      # Shell hook (runs on entry)
      shellHook = ''
        echo "Welcome to dev environment!"
        export PATH="$PWD/node_modules/.bin:$PATH"
      '';

      # For C library headers
      LD_LIBRARY_PATH = pkgs.lib.makeLibraryPath [
        pkgs.openssl
        pkgs.zlib
      ];
    };
  };
}
```

## Multi-Platform Support

```nix
{
  outputs = { nixpkgs, flake-utils, ... }:
    flake-utils.lib.eachDefaultSystem (system: let
      pkgs = nixpkgs.legacyPackages.${system};
    in {
      devShells.default = pkgs.mkShell {
        packages = with pkgs; [ nodejs ];
      };
    });
}
```

Or manually:

```nix
{
  outputs = { nixpkgs, ... }: let
    systems = [ "x86_64-linux" "aarch64-linux" "x86_64-darwin" "aarch64-darwin" ];
    forAllSystems = f: nixpkgs.lib.genAttrs systems (system: f {
      pkgs = nixpkgs.legacyPackages.${system};
    });
  in {
    devShells = forAllSystems ({ pkgs }: {
      default = pkgs.mkShell { packages = [ pkgs.nodejs ]; };
    });
  };
}
```

## Multiple Dev Shells

```nix
{
  devShells.x86_64-linux = {
    default = pkgs.mkShell {
      packages = [ pkgs.nodejs ];
    };

    python = pkgs.mkShell {
      packages = [ pkgs.python3 pkgs.poetry ];
    };

    rust = pkgs.mkShell {
      packages = [ pkgs.rustc pkgs.cargo pkgs.rust-analyzer ];
    };
  };
}

# Usage:
# nix develop        # default
# nix develop .#python
# nix develop .#rust
```

## direnv Integration

Automatic environment activation:

### Setup

```nix
# In home.nix or configuration.nix
programs.direnv = {
  enable = true;
  nix-direnv.enable = true;  # Better caching
};
```

### Usage

```bash
# In project root, create .envrc
echo "use flake" > .envrc

# Allow direnv
direnv allow

# Now environment activates automatically on cd
```

### Advanced .envrc

```bash
# Basic
use flake

# With impure (for unfree packages)
use flake --impure

# Specific devShell
use flake .#python

# From remote
use flake github:owner/repo

# Watch additional files (rebuild on change)
watch_file flake.nix
watch_file flake.lock

# Additional env vars
export MY_VAR="value"

# Load .env file
dotenv_if_exists
```

## devenv (High-Level Dev Environments)

devenv provides a higher-level abstraction over Nix dev shells with less boilerplate:

### Setup
```bash
# Install (if not already via nix profile)
nix profile install github:cachix/devenv/latest

# Initialize in a project
devenv init
```

### Configuration (devenv.nix)
```nix
{ pkgs, ... }: {
  # Languages with automatic version management
  languages.python = {
    enable = true;
    version = "3.12";
  };
  languages.rust.enable = true;

  # Packages
  packages = [ pkgs.git pkgs.curl ];

  # Services (databases, queues, etc.)
  services.postgres.enable = true;

  # Environment variables
  env.DATABASE_URL = "postgres://localhost/mydb";

  # Shell hooks
  enterShell = ''
    echo "Dev environment ready"
  '';

  # Pre-commit hooks
  pre-commit.hooks.rustfmt.enable = true;
}
```

### Key Features
- **50+ language integrations** with version management
- **Services** (Postgres, Redis, MySQL, etc.) managed per-project
- **Pre-commit hooks** built in
- **Container generation**: `devenv container build`
- **Task runner**: dependency-based parallel task execution
- **Profiles**: `devenv --profile backend` for selective environments
- **Instant caching**: sub-100ms shell activation after first build

### When to use devenv vs mkShell
- **devenv**: When you want managed language versions, services, or pre-commit hooks without writing raw Nix
- **mkShell**: When you need fine-grained control, custom derivations, or minimal dependencies

## FHS Environment (Downloaded Binaries)

NixOS doesn't follow standard Linux paths. For prebuilt binaries:

> **Note:** `buildFHSUserEnv` is the legacy name; use `buildFHSEnv` (current).

```nix
{ pkgs, ... }: {
  # Add to environment
  environment.systemPackages = [
    (pkgs.buildFHSEnv {
      name = "fhs";
      targetPkgs = pkgs: with pkgs; [
        # Common requirements
        zlib
        glib
        # Add what your binary needs
        openssl
        curl
        libGL
        xorg.libX11
      ];
      runScript = "bash";
    })
  ];
}

# Usage: enter with `fhs`, then run binaries normally
```

### For Specific Binary

```nix
{
  myBinary = pkgs.buildFHSEnv {
    name = "my-binary";
    targetPkgs = pkgs: [ pkgs.zlib ];
    runScript = "${./my-binary}";
  };
}
```

## nix-ld (Alternative for Binaries)

System-wide dynamic linker for unpatched binaries:

```nix
# In NixOS configuration
{
  programs.nix-ld = {
    enable = true;
    libraries = with pkgs; [
      stdenv.cc.cc
      zlib
      openssl
      curl
    ];
  };
}
```

## Python Development

Python packages installed via pip fail on NixOS. Solutions:

### Virtual Environment

```nix
devShells.default = pkgs.mkShell {
  packages = [ pkgs.python3 ];
  shellHook = ''
    python -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
  '';
};
```

### poetry2nix

```nix
{
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-25.11";
    poetry2nix.url = "github:nix-community/poetry2nix";
  };

  outputs = { nixpkgs, poetry2nix, ... }: let
    pkgs = nixpkgs.legacyPackages.x86_64-linux;
    p2n = poetry2nix.lib.mkPoetry2Nix { inherit pkgs; };
  in {
    devShells.x86_64-linux.default = p2n.mkPoetryEnv {
      projectDir = ./.;
    };
  };
}
```

## Language-Specific Shells

### Node.js
```nix
pkgs.mkShell {
  packages = with pkgs; [ nodejs_20 yarn nodePackages.pnpm ];
  shellHook = ''
    export PATH="$PWD/node_modules/.bin:$PATH"
  '';
}
```

### Rust
```nix
pkgs.mkShell {
  packages = with pkgs; [
    rustc cargo rust-analyzer rustfmt clippy
  ];
  RUST_SRC_PATH = "${pkgs.rust.packages.stable.rustPlatform.rustLibSrc}";
}
```

### Go
```nix
pkgs.mkShell {
  packages = with pkgs; [ go gopls gotools go-tools ];
  shellHook = ''
    export GOPATH="$PWD/.go"
    export PATH="$GOPATH/bin:$PATH"
  '';
}
```

### Java
```nix
devShells.default = pkgs.mkShell {
  packages = with pkgs; [
    jdk21
    maven
    gradle
  ];
  JAVA_HOME = "${pkgs.jdk21}";
};
```

### C/C++
```nix
pkgs.mkShell {
  packages = with pkgs; [ gcc cmake gnumake gdb ];
  buildInputs = with pkgs; [ openssl zlib ];
  nativeBuildInputs = [ pkgs.pkg-config ];
}
```

## Community Templates

Use existing templates instead of writing from scratch. The `the-nix-way/dev-templates` repo has been growing steadily and is a good starting point for most languages:

```bash
# List available templates
nix flake show templates

# Initialize from template
nix flake init -t github:the-nix-way/dev-templates#rust
nix flake init -t github:the-nix-way/dev-templates#node
nix flake init -t github:the-nix-way/dev-templates#python
```
