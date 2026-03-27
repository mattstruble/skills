# Scaffolding a New Dendritic Config

When setting up a new dendritic config, ask the user which platforms they need (NixOS, Darwin,
Home Manager standalone), then generate this minimal scaffold.

## flake.nix

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

## modules/nix/flake-parts.nix

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

## modules/system/system-types/system-default.nix

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

## Iterating After the Scaffold

After generating the scaffold, iterate: the user describes a feature they need, you select
the appropriate aspect pattern(s) from the decision tree in SKILL.md, then create the module
in the appropriate category directory.
