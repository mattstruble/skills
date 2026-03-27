# Dendritic Aspect Patterns

Each pattern below solves a specific structural problem. Most real features combine 2-3 patterns.
The SKILL.md decision tree identifies which pattern(s) to use. This file provides the
implementation details for each.

**Terminology reminder:** A *feature* is the flake-parts module file (e.g., `ssh.nix`). An
*aspect* is a `flake.modules.<class>.<name>` definition within that file. A single feature can
define aspects for multiple classes plus flake-parts boilerplate.

## Contents

- [Simple Aspect](#simple-aspect) — one or more module classes, no dependencies
- [Multi Context Aspect](#multi-context-aspect) — system module that pulls in Home Manager config
- [Inheritance Aspect](#inheritance-aspect) — feature that composes other features
- [Conditional Aspect](#conditional-aspect) — platform-specific behavior within a module class
- [Collector Aspect](#collector-aspect) — multiple files contribute to the same service
- [Constants Aspect](#constants-aspect) — shared values across module classes
- [DRY Aspect](#dry-aspect) — reusable config fragments applied to multiple targets
- [Factory Aspect](#factory-aspect) — parameterized feature generation
- [Applying and Selecting Patterns](#applying-and-selecting-patterns) — worked example: combining multiple patterns
- [Putting It All Together](#putting-it-all-together) — full config layout with all patterns in context

## Simple Aspect

**Use case:** A feature that provides config in one or more module classes without depending on other features.

Each class gets its own block in the same file. The feature name should describe the *capability*, not the host or package.

```nix
{
  flake.modules.nixos.basicPackages =
    { pkgs, ... }:
    {
      environment.systemPackages = with pkgs; [
        # NixOS system packages
      ];
    };

  flake.modules.darwin.basicPackages =
    { pkgs, ... }:
    {
      environment.systemPackages = with pkgs; [
        # Darwin system packages
      ];
    };

  flake.modules.homeManager.basicPackages =
    { pkgs, ... }:
    {
      programs = {
        # Home Manager program configs
      };
    };
}
```

You don't need all three classes -- use only the ones relevant to your feature.

## Multi Context Aspect

**Use case:** A system-level feature (NixOS or Darwin) that requires mandatory Home Manager config as part of its setup.

The system module pulls in the Home Manager module via `home-manager.sharedModules`, creating a
parent-child relationship. The Home Manager module is "private" to this feature -- it exists to
support the system-level config.

```nix
{ inputs, ... }:
{
  flake.modules.nixos.gnome = {
    home-manager.sharedModules = [
      inputs.self.modules.homeManager.gnome
    ];
    # System-level GNOME config (GDM, dconf, etc.)
  };

  flake.modules.homeManager.gnome = {
    # User-level GNOME config (extensions, keybindings, etc.)
  };
}
```

The Home Manager module can also be used standalone (e.g., for Home Manager-only users) --
there's nothing to prevent it. This is the "public auxiliary module" pattern from the design guide.

## Inheritance Aspect

**Use case:** A feature that extends or composes other features into a higher-level capability.

Use `imports` to pull in parent aspects. This creates a hierarchy where higher-level features
build on lower-level ones.

```nix
{ inputs, ... }:
{
  flake.modules.nixos.system-desktop = {
    imports = with inputs.self.modules.nixos; [
      system-cli     # parent: everything a CLI system needs
      mail
      browser
      kde
      printing
    ];
    # Additional desktop-specific config
  };

  flake.modules.darwin.system-desktop = {
    imports = with inputs.self.modules.darwin; [
      system-cli     # same parent, different platform
      mail
      browser
    ];
    # Additional desktop-specific config for macOS
  };
}
```

This naturally produces a system type hierarchy: `system-default` -> `system-essential` ->
`system-basic` -> `system-cli` -> `system-desktop`. Each level adds capabilities.

## Conditional Aspect

**Use case:** A single module that behaves differently based on platform or other runtime conditions.

Use `lib.mkMerge` with `lib.mkIf` to conditionally include config blocks. This is useful inside
Home Manager modules that are shared across NixOS and Darwin.

```nix
flake.modules.homeManager.office =
  { pkgs, lib, ... }:
  lib.mkMerge [
    {
      home.packages = with pkgs; [
        notesnook
      ];
      # Settings for all platforms
    }
    (lib.mkIf pkgs.stdenv.isLinux {
      home.packages = with pkgs; [
        libreoffice-qt6
      ];
    })
    (lib.mkIf pkgs.stdenv.isDarwin {
      home.packages = with pkgs; [
        libreoffice-bin
      ];
    })
  ];
```

**Important:** This is for conditional *config*, not conditional *imports*. Never put `lib.mkIf`
in `imports` -- Nix evaluates imports unconditionally regardless of conditions.

## Collector Aspect

**Use case:** Multiple features contribute config to the same service or resource.

In the Nix module system, multiple definitions of the same option are merged (for list and attrset
types). The Collector pattern exploits this: define the same `flake.modules.<class>.<aspect>` in
multiple files and they merge together.

Main feature definition:
```nix
{ # modules/services/syncthing.nix
  flake.modules.nixos.syncthing = {
    services.syncthing = {
      enable = true;
      # base syncthing config
    };
  };
}
```

A host contributes its device identity:
```nix
{ # modules/hosts/homeserver.nix (among other config)
  flake.modules.nixos.syncthing = {
    services.syncthing.settings.devices = {
      homeserver = {
        id = "VNV2XTI-6VY6KR2-OCASMST-Z35JUEG-VNV2XTI-KJWBOKQ-6VYUKR2-Z35JUEG";
      };
    };
  };
}
```

Another host contributes its own:
```nix
{ # modules/hosts/linux-desktop.nix (among other config)
  flake.modules.nixos.syncthing = {
    services.syncthing.settings.devices = {
      linux-desktop = {
        id = "ABC1234-DEF5678-...";
      };
    };
  };
}
```

All three definitions merge into a single `syncthing` module with all devices configured.

## Constants Aspect

**Use case:** Shared values that need to be accessible across multiple module classes.

Define a `generic` module class with custom options, then import it into each class that needs
the values.

Define the constants module:
```nix
{
  flake.modules.generic.systemConstants =
    { lib, ... }:
    {
      options.systemConstants = lib.mkOption {
        type = lib.types.attrsOf lib.types.unspecified;
        default = { };
      };

      config.systemConstants = {
        adminEmail = "admin@example.org";
        domain = "example.org";
        timeZone = "America/New_York";
      };
    };
}
```

Include it in each class's base module:
```nix
{
  flake.modules.nixos.system-default = {
    imports = [ inputs.self.modules.generic.systemConstants ];
  };

  flake.modules.darwin.system-default = {
    imports = [ inputs.self.modules.generic.systemConstants ];
  };

  flake.modules.homeManager.system-default = {
    imports = [ inputs.self.modules.generic.systemConstants ];
  };
}
```

Use the constants anywhere:
```nix
flake.modules.nixos.homeserver =
  { config, ... }:
  {
    services.zfs.zed.settings = {
      ZED_EMAIL_ADDR = [ config.systemConstants.adminEmail ];
    };
    time.timeZone = config.systemConstants.timeZone;
  };
```

This replaces the `specialArgs` anti-pattern with proper module options.

## DRY Aspect

**Use case:** Reusable config fragments that get applied to multiple attribute assignments.

Define a custom module class for the reusable data, then reference it directly where needed.

Define the reusable fragment:
```nix
{
  flake.modules.networkInterface.subnet-A = {
    ipv6.routes = [
      {
        address = "2001:1470:fffd:2098::";
        prefixLength = 64;
        via = "fdfd:b3f0::1";
      }
    ];
    ipv4.routes = [
      {
        address = "192.168.2.0";
        prefixLength = 24;
        via = "192.168.1.1";
      }
    ];
  };
}
```

Apply it to specific interfaces:
```nix
{ inputs, lib, ... }:
{
  networking.interfaces."enp86s0" =
    with inputs.self.modules.networkInterface;
    lib.mkMerge [
      subnet-A
      subnet-B
      {
        ipv4.addresses = [
          { address = "10.0.0.1"; prefixLength = 16; }
        ];
      }
    ];
}
```

The key insight: `flake.modules` isn't limited to `nixos`/`darwin`/`homeManager`. You can define
any module class name for reusable data structures.

## Factory Aspect

**Use case:** Generating similar features from parameters -- like creating user modules that
follow the same structure but differ in name, permissions, etc.

Define a factory option at the flake level:
```nix
{ lib, ... }:
{
  options.flake.factory = lib.mkOption {
    type = lib.types.attrsOf lib.types.unspecified;
    default = { };
  };
}
```

Create a factory function:
```nix
{ lib, ... }:
{
  config.flake.factory.user = username: isAdmin: {
    darwin."${username}" = {
      users.users."${username}" = {
        name = "${username}";
      };
      system.primaryUser = lib.mkIf isAdmin "${username}";
    };

    nixos."${username}" = {
      users.users."${username}" = {
        name = "${username}";
        isNormalUser = true;
        extraGroups = lib.optionals isAdmin [ "wheel" ];
      };
    };
  };
}
```

Use the factory:
```nix
{ inputs, lib, ... }:
{
  flake.modules = lib.mkMerge [
    (inputs.self.factory.user "bob" true)
    {
      nixos.bob = {
        # Additional bob-specific NixOS config
      };
      darwin.bob = {
        # Additional bob-specific Darwin config
      };
    }
  ];
}
```

### Anonymous Module Factory Variant

Factories can also produce modules for use in `imports`. This is useful for parameterized
infrastructure like mount points:

```nix
{ lib, ... }:
{
  config.flake.factory.mount-cifs-nixos =
    { host, resource, destination, credentialspath, UID, GID }:
    { config, lib, ... }:
    {
      fileSystems."${destination}" = {
        device = "//${host}/${resource}";
        fsType = "cifs";
        options = [
          "credentials=${credentialspath}"
          "uid=${UID}" "gid=${GID}"
        ];
      };
    };
}
```

Use in imports:
```nix
flake.modules.nixos.linux-desktop =
  { lib, config, ... }:
  {
    imports =
      with inputs.self.modules.nixos;
      with inputs.self.factory;
      [
        (mount-cifs-nixos {
          host = "home-server.lan";
          resource = "home";
          destination = "/home/users/bob/homeserver";
          credentialspath = "${config.age.secrets."homeserver-cred".path}";
          UID = "bob";
          GID = "users";
        })
      ];
  };
```

## Applying and Selecting Patterns

Real features typically combine multiple patterns. Follow this process:

1. **Define requirements** -- what does this feature need to configure, and across which classes?
2. **Identify patterns** -- match each requirement to a pattern from the decision tree
3. **Implement** -- compose the patterns in a single file (or directory for complex features)

### Worked Example: User "bob"

Requirements:
- Desktop environment settings for Linux and macOS
- Home Manager as a module inside system configurations
- Imports features: `adminTools` and `videoEditing`
- Home Manager module also usable standalone

Identified patterns:
- (A) Linux + macOS -> **Simple Aspect** (one block per class)
- (B) HM inside system config -> **Multi Context Aspect**
- (C) Composes other features -> **Inheritance Aspect**
- (D) Standalone HM use -> public auxiliary module from Multi Context

```nix
{ inputs, ... }:
{
  # (A) NixOS config for bob
  flake.modules.nixos.bob = {
    # (B) Pull in bob's Home Manager config
    home-manager.users.bob = {
      imports = [ inputs.self.modules.homeManager.bob ];
    };
    # (A) System-level features
    imports = with inputs.self.modules.nixos; [
      desktopEnvironment
    ];
    # NixOS-specific user settings
  };

  # (A) Darwin config for bob
  flake.modules.darwin.bob = {
    # (B) Same Home Manager config, different system
    home-manager.users.bob = {
      imports = [ inputs.self.modules.homeManager.bob ];
    };
    imports = with inputs.self.modules.darwin; [
      desktopEnvironment
    ];
    # Darwin-specific user settings
  };

  # (B) + (D) Home Manager module -- used by both system configs and standalone
  flake.modules.homeManager.bob = {
    # (C) Compose feature modules
    imports = with inputs.self.modules.homeManager; [
      adminTools
      videoEditing
    ];
    # Home Manager user settings
  };
}
```

## Putting It All Together

Here's what a mature dendritic config looks like in practice. Letters in brackets indicate
module classes: (N)ixOS, (D)arwin, lowercase (n)/(d) for Home Manager on that platform.

```
project/
├── flake.nix
└── modules/
    ├── factory/
    │   ├── user.nix              [ND]   -- Factory Aspect
    │   └── mount-cifs-nixos.nix  [N]    -- Anonymous Module Factory
    ├── hosts/
    │   ├── homeserver/           [N]    -- host definition + per-host overrides
    │   │   ├── services/
    │   │   │   └── syncthing.nix        -- Collector contributions
    │   │   └── users/
    │   ├── linux-desktop/        [N]
    │   │   └── users/
    │   └── macbook/              [D]
    │       └── users/
    ├── nix/
    │   ├── flake-parts.nix       []     -- boilerplate, helpers (mkNixos, mkDarwin)
    │   └── tools/
    │       ├── home-manager.nix  [ND]   -- HM integration setup
    │       ├── homebrew.nix      [D]    -- Homebrew cask integration
    │       ├── impermanence.nix  [N]    -- opt-in persistence
    │       └── secrets.nix       [NDnd] -- agenix/sops setup
    ├── programs/
    │   ├── browser.nix           [nd]   -- Conditional Aspect (Linux/Darwin)
    │   ├── cli-tools.nix         [ND]   -- Simple Aspect
    │   ├── gnome.nix             [N]    -- Multi Context Aspect
    │   ├── office.nix            [nd]   -- Conditional Aspect
    │   └── shell.nix             [nd]   -- Simple Aspect
    ├── services/
    │   ├── printing.nix          [N]    -- Simple Aspect
    │   ├── ssh.nix               [ND]   -- Simple Aspect
    │   └── syncthing.nix         [N]    -- Collector base
    ├── system/
    │   ├── settings/
    │   │   ├── bluetooth.nix     [N]
    │   │   ├── network/
    │   │   │   ├── subnet-A.nix  [networkInterface]  -- DRY Aspect
    │   │   │   └── subnet-B.nix  [networkInterface]
    │   │   ├── systemConstants.nix [NDnd] -- Constants Aspect
    │   │   └── systemd-boot.nix  [N]
    │   └── system-types/
    │       ├── system-default.nix   [NDnd] -- base (imports constants)
    │       ├── system-essential.nix [NDnd] -- + core services
    │       ├── system-basic.nix     [NDnd] -- + basic programs
    │       ├── system-cli.nix       [NDnd] -- + CLI tools, shell
    │       └── system-desktop.nix   [NDnd] -- + GUI, desktop env
    └── users/
        ├── alice.nix             [D]
        ├── bob.nix               [NDn]  -- Factory + Multi Context + Inheritance
        ├── eve.nix               [N]
        └── mallory.nix           [N]
```

Key observations:
- **Feature-centric naming:** files are named for what they do, not where they run
- **System type hierarchy:** each level inherits from the previous via Inheritance Aspect
- **Hosts select features:** a host module imports the system type + user modules it needs
- **No import spaghetti:** `import-tree` loads everything; `imports` within modules defines composition
- **Directories as documentation:** the path tells you what a file does

A host definition ties it together:
```nix
{ inputs, ... }:
{
  flake.modules.nixos."linux-desktop" = {
    imports = with inputs.self.modules.nixos; [
      system-cli
      syncthing
      bob
      alice
    ];
  };

  # One-liner to create the NixOS configuration
  flake.nixosConfigurations = inputs.self.lib.mkNixos "x86_64-linux" "linux-desktop";
}
```
