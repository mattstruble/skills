# Flake Templates

Ready-to-use `flake.nix` templates for common scenarios.

## Contents

- [Minimal NixOS](#minimal-nixos)
- [NixOS + Home Manager](#nixos--home-manager)
- [nix-darwin (macOS)](#nix-darwin-macos)
- [nix-darwin + Home Manager](#nix-darwin--home-manager)
- [Standalone Home Manager](#standalone-home-manager)
- [Development Shell](#development-shell)
- [Multi-Language Dev Shell](#multi-language-dev-shell)
- [Cross-Platform (NixOS + Darwin)](#cross-platform-nixos--darwin)
- [Package + DevShell](#package--devshell)
- [Docker / OCI Image Build](#docker--oci-image-build)
- [flake-parts](#flake-parts)
- [With Overlays](#with-overlays)
- [Starter configuration.nix](#starter-configurationnix)
- [Starter home.nix](#starter-homenix)
- [Starter darwin.nix](#starter-darwinnix)

## Minimal NixOS

```nix
{
  description = "NixOS configuration";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-25.11";
  };

  outputs = { self, nixpkgs }: {
    nixosConfigurations.hostname = nixpkgs.lib.nixosSystem {
      system = "x86_64-linux";
      modules = [ ./configuration.nix ];
    };
  };
}
```

## NixOS + Home Manager

```nix
{
  description = "NixOS with Home Manager";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-25.11";
    home-manager = {
      url = "github:nix-community/home-manager/release-25.11";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = { self, nixpkgs, home-manager, ... }: {
    nixosConfigurations.hostname = nixpkgs.lib.nixosSystem {
      system = "x86_64-linux";
      modules = [
        ./configuration.nix

        home-manager.nixosModules.home-manager
        {
          home-manager.useGlobalPkgs = true;
          home-manager.useUserPackages = true;
          home-manager.users.username = import ./home.nix;
        }
      ];
    };
  };
}
```

## nix-darwin (macOS)

```nix
{
  description = "macOS configuration";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-25.11-darwin";
    nix-darwin = {
      url = "github:nix-darwin/nix-darwin/nix-darwin-25.11";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = { self, nixpkgs, nix-darwin }: {
    darwinConfigurations.hostname = nix-darwin.lib.darwinSystem {
      modules = [
        ./darwin.nix
        { nixpkgs.hostPlatform = "aarch64-darwin"; }  # or x86_64-darwin for Intel
      ];
    };
  };
}

# Apply with: sudo darwin-rebuild switch --flake .#hostname
```

## nix-darwin + Home Manager

```nix
{
  description = "macOS with Home Manager";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-25.11-darwin";
    nix-darwin = {
      url = "github:nix-darwin/nix-darwin/nix-darwin-25.11";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    home-manager = {
      url = "github:nix-community/home-manager/release-25.11";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = { self, nixpkgs, nix-darwin, home-manager }: {
    darwinConfigurations.hostname = nix-darwin.lib.darwinSystem {
      modules = [
        ./darwin.nix
        { nixpkgs.hostPlatform = "aarch64-darwin"; }

        home-manager.darwinModules.home-manager
        {
          home-manager.useGlobalPkgs = true;
          home-manager.useUserPackages = true;
          home-manager.users.username = import ./home.nix;
        }
      ];
    };
  };
}

# Apply with: sudo darwin-rebuild switch --flake .#hostname
```

## Standalone Home Manager

```nix
{
  description = "Home Manager standalone";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-25.11";
    home-manager = {
      url = "github:nix-community/home-manager/release-25.11";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = { self, nixpkgs, home-manager }: {
    homeConfigurations."username@hostname" = home-manager.lib.homeManagerConfiguration {
      pkgs = nixpkgs.legacyPackages.x86_64-linux;
      modules = [ ./home.nix ];
    };
  };
}

# Apply with: home-manager switch --flake .#username@hostname
```

## Development Shell

```nix
{
  description = "Development environment";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-25.11";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system: let
      pkgs = nixpkgs.legacyPackages.${system};
    in {
      devShells.default = pkgs.mkShell {
        packages = with pkgs; [
          # Add your dev tools here
          nodejs_20
          yarn
          python3
        ];

        shellHook = ''
          echo "Dev environment ready!"
        '';
      };
    });
}
```

## Multi-Language Dev Shell

```nix
{
  description = "Multi-language development";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-25.11";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system: let
      pkgs = nixpkgs.legacyPackages.${system};
    in {
      devShells = {
        default = pkgs.mkShell {
          packages = with pkgs; [ git vim ];
        };

        node = pkgs.mkShell {
          packages = with pkgs; [ nodejs_20 yarn pnpm ];
          shellHook = ''export PATH="$PWD/node_modules/.bin:$PATH"'';
        };

        python = pkgs.mkShell {
          packages = with pkgs; [ python3 poetry ];
        };

        rust = pkgs.mkShell {
          packages = with pkgs; [ rustc cargo rust-analyzer clippy rustfmt ];
          RUST_SRC_PATH = "${pkgs.rust.packages.stable.rustPlatform.rustLibSrc}";
        };

        go = pkgs.mkShell {
          packages = with pkgs; [ go gopls gotools ];
        };
      };
    });
}

# Usage:
# nix develop .#node
# nix develop .#python
# nix develop .#rust
```

## Cross-Platform (NixOS + Darwin)

```nix
{
  description = "Cross-platform configuration";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-25.11";
    nixpkgs-darwin.url = "github:NixOS/nixpkgs/nixpkgs-25.11-darwin";

    home-manager = {
      url = "github:nix-community/home-manager/release-25.11";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    nix-darwin = {
      url = "github:nix-darwin/nix-darwin/nix-darwin-25.11";
      inputs.nixpkgs.follows = "nixpkgs-darwin";
    };
  };

  outputs = { self, nixpkgs, nixpkgs-darwin, home-manager, nix-darwin, ... }@inputs: {
    # NixOS configurations
    nixosConfigurations = {
      desktop = nixpkgs.lib.nixosSystem {
        system = "x86_64-linux";
        modules = [
          ./hosts/desktop/configuration.nix
          home-manager.nixosModules.home-manager
          {
            home-manager.useGlobalPkgs = true;
            home-manager.useUserPackages = true;
            home-manager.users.username = import ./home/linux.nix;
          }
        ];
        specialArgs = { inherit inputs; };
      };
    };

    # macOS configurations
    darwinConfigurations = {
      macbook = nix-darwin.lib.darwinSystem {
        modules = [
          ./hosts/macbook/darwin.nix
          { nixpkgs.hostPlatform = "aarch64-darwin"; }
          home-manager.darwinModules.home-manager
          {
            home-manager.useGlobalPkgs = true;
            home-manager.useUserPackages = true;
            home-manager.users.username = import ./home/darwin.nix;
          }
        ];
        specialArgs = { inherit inputs; };
      };
    };
  };
}

# Apply NixOS:  sudo nixos-rebuild switch --flake .#desktop
# Apply macOS:  sudo darwin-rebuild switch --flake .#macbook
```

## Package + DevShell

```nix
{
  description = "Package with development shell";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-25.11";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system: let
      pkgs = nixpkgs.legacyPackages.${system};
    in {
      packages = {
        default = pkgs.callPackage ./package.nix { };
      };

      devShells.default = pkgs.mkShell {
        inputsFrom = [ self.packages.${system}.default ];
        packages = with pkgs; [
          # Additional dev tools
          nixpkgs-fmt
        ];
      };
    });
}
```

## Docker / OCI Image Build

```nix
{
  description = "Docker image build with nixpkgs";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-25.11";
  };

  outputs = { nixpkgs, ... }:
    let pkgs = nixpkgs.legacyPackages.x86_64-linux;
    in {
      packages.x86_64-linux.docker-image = pkgs.dockerTools.buildLayeredImage {
        name = "my-app";
        tag = "latest";
        contents = [ pkgs.hello ];
        config.Cmd = [ "${pkgs.hello}/bin/hello" ];
      };
    };
}

# Build with: nix build .#docker-image
# Load with:  docker load < result
```

## flake-parts

```nix
{
  description = "Flake using flake-parts";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-25.11";
    flake-parts.url = "github:hercules-ci/flake-parts";
  };

  outputs = inputs: inputs.flake-parts.lib.mkFlake { inherit inputs; } {
    systems = [ "x86_64-linux" "aarch64-darwin" ];
    perSystem = { pkgs, ... }: {
      devShells.default = pkgs.mkShell {
        packages = [ pkgs.hello ];
      };
    };
  };
}
```

## With Overlays

```nix
{
  description = "Configuration with overlays";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-25.11";
  };

  outputs = { self, nixpkgs }: let
    myOverlay = final: prev: {
      myPackage = prev.callPackage ./pkgs/mypackage.nix { };

      # Modify existing package
      vim = prev.vim.override { python3 = final.python311; };
    };
  in {
    # Export overlay for others
    overlays.default = myOverlay;

    nixosConfigurations.hostname = nixpkgs.lib.nixosSystem {
      system = "x86_64-linux";
      modules = [
        ./configuration.nix
        {
          nixpkgs.overlays = [ myOverlay ];
        }
      ];
    };
  };
}
```

## Starter configuration.nix

```nix
# configuration.nix
{ config, pkgs, ... }: {
  imports = [ ./hardware-configuration.nix ];

  # Bootloader
  boot.loader.systemd-boot.enable = true;
  boot.loader.efi.canTouchEfiVariables = true;

  # Networking
  networking.hostName = "hostname";
  networking.networkmanager.enable = true;

  # Time zone
  time.timeZone = "America/New_York";

  # Locale
  i18n.defaultLocale = "en_US.UTF-8";

  # Users
  users.users.username = {
    isNormalUser = true;
    extraGroups = [ "wheel" "networkmanager" ];
    shell = pkgs.zsh;
  };

  # Packages
  environment.systemPackages = with pkgs; [
    vim git curl wget
  ];

  # Enable flakes
  nix.settings.experimental-features = [ "nix-command" "flakes" ];

  # Allow unfree
  nixpkgs.config.allowUnfree = true;

  # System version (don't change after install)
  system.stateVersion = "25.11";
}
```

## Starter home.nix

```nix
# home.nix
{ config, pkgs, ... }: {
  home.username = "username";
  home.homeDirectory = "/home/username";  # /Users/username on macOS

  home.packages = with pkgs; [
    ripgrep fd jq htop
  ];

  programs.git = {
    enable = true;
    userName = "Your Name";
    userEmail = "you@example.com";
  };

  programs.zsh = {
    enable = true;
    autosuggestion.enable = true;
    syntaxHighlighting.enable = true;
  };

  programs.starship.enable = true;

  programs.direnv = {
    enable = true;
    nix-direnv.enable = true;
  };

  home.stateVersion = "25.11";
}
```

## Starter darwin.nix

```nix
# darwin.nix
{ config, pkgs, ... }: {
  environment.systemPackages = with pkgs; [
    vim git curl
  ];

  # Fonts (nerd-fonts use per-font packages)
  fonts.packages = [
    pkgs.nerd-fonts.jetbrains-mono
    pkgs.nerd-fonts.fira-code
  ];

  # Primary user (required)
  system.primaryUser = "username";

  # Nix configuration
  nix.enable = true;

  # Flakes
  nix.settings.experimental-features = [ "nix-command" "flakes" ];

  # Zsh (default on macOS)
  programs.zsh.enable = true;

  # System preferences
  system.defaults = {
    dock.autohide = true;
    finder.AppleShowAllExtensions = true;
    NSGlobalDomain.AppleInterfaceStyle = "Dark";
  };

  # TouchID for sudo
  security.pam.services.sudo_local.touchIdAuth = true;

  # Homebrew (optional)
  homebrew = {
    enable = true;
    onActivation.cleanup = "zap";
    casks = [ "firefox" "visual-studio-code" ];
  };

  system.stateVersion = 6;
}

# Apply with: sudo darwin-rebuild switch --flake .#hostname
```
