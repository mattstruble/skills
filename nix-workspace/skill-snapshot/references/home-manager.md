# Home Manager Reference

## Overview

Home Manager manages user-specific:
- Packages in `~/.nix-profile`
- Dotfiles in `~/.config`, `~/.*`
- User services
- Shell configuration

## Installation Methods

### As NixOS Module
```nix
# flake.nix
{
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-25.11";
    home-manager = {
      url = "github:nix-community/home-manager/release-25.11";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = { nixpkgs, home-manager, ... }: {
    nixosConfigurations.hostname = nixpkgs.lib.nixosSystem {
      modules = [
        ./configuration.nix
        home-manager.nixosModules.home-manager
        {
          home-manager.useGlobalPkgs = true;
          home-manager.useUserPackages = true;
          home-manager.users.username = import ./home.nix;
          # Pass extra args to home.nix
          home-manager.extraSpecialArgs = { inherit inputs; };
          # Auto-backup files that would be overwritten (common pain point)
          home-manager.backupFileExtension = "hm-backup";
        }
      ];
    };
  };
}
```

### As Darwin Module
```nix
# Same pattern as NixOS
{
  inputs = {
    nix-darwin.url = "github:LnL7/nix-darwin/nix-darwin-25.11";
    home-manager = {
      url = "github:nix-community/home-manager/release-25.11";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = { nix-darwin, home-manager, ... }: {
    darwinConfigurations.hostname = nix-darwin.lib.darwinSystem {
      modules = [
        ./darwin.nix
        home-manager.darwinModules.home-manager
        {
          home-manager.useGlobalPkgs = true;
          home-manager.useUserPackages = true;
          home-manager.users.username = import ./home.nix;
          home-manager.backupFileExtension = "hm-backup";
        }
      ];
    };
  };
}
```

### Standalone
```nix
# flake.nix
{
  outputs = { nixpkgs, home-manager, ... }: {
    homeConfigurations."user@hostname" = home-manager.lib.homeManagerConfiguration {
      pkgs = nixpkgs.legacyPackages.x86_64-linux;
      modules = [ ./home.nix ];
      extraSpecialArgs = { inherit inputs; };
    };
  };
}

# Apply with:
# home-manager switch --flake .#user@hostname
```

## Basic home.nix

```nix
{ config, pkgs, ... }: {
  home.username = "username";
  home.homeDirectory = "/home/username";  # /Users/username on macOS

  # Packages
  home.packages = with pkgs; [
    ripgrep
    fd
    jq
    htop
  ];

  # IMPORTANT: Match your Home Manager version
  home.stateVersion = "25.11";

  # Let Home Manager manage itself (standalone only)
  programs.home-manager.enable = true;
}
```

## backupFileExtension

When home-manager finds an existing file it would overwrite, it errors out by default. This is a very common pain point. Set `backupFileExtension` to auto-backup instead:

```nix
# As a NixOS/Darwin module option:
home-manager.backupFileExtension = "hm-backup";

# Or inside home.nix (standalone):
home.backupFileExtension = "hm-backup";
```

This renames the conflicting file (e.g., `.bashrc` becomes `.bashrc.hm-backup`) so home-manager can proceed.

## File Management

```nix
{
  # Copy file
  home.file.".config/app/config.toml".source = ./config.toml;

  # Create from text
  home.file.".config/app/config.toml".text = ''
    [section]
    key = "value"
  '';

  # Mutable symlink (points OUTSIDE the Nix store)
  # Normal home.file creates immutable symlinks to the Nix store.
  # mkOutOfStoreSymlink creates symlinks to a path OUTSIDE the store,
  # so you can edit the file without rebuilding:
  home.file.".config/nvim".source =
    config.lib.file.mkOutOfStoreSymlink "/home/user/dotfiles/nvim";

  # Executable script
  home.file.".local/bin/myscript" = {
    executable = true;
    text = ''
      #!/bin/bash
      echo "Hello"
    '';
  };

  # Recursive directory
  home.file.".config/nvim" = {
    source = ./nvim;
    recursive = true;
  };

  # XDG config (equivalent to ~/.config)
  xdg.configFile."app/config.toml".source = ./config.toml;
}
```

### mkOutOfStoreSymlink

This is important for mutable dotfiles — files you want to edit in place without rebuilding:

```nix
{
  # Instead of copying into the Nix store (immutable), this creates a
  # symlink directly to the specified path on disk.
  # The path must be absolute.
  home.file.".config/nvim".source =
    config.lib.file.mkOutOfStoreSymlink "/home/user/dotfiles/nvim";

  # Common pattern: reference your dotfiles repo
  home.file.".config/kitty".source =
    config.lib.file.mkOutOfStoreSymlink "${config.home.homeDirectory}/dotfiles/kitty";
}
```

## Program Modules

Home Manager has built-in modules for many programs:

### Git
```nix
{
  programs.git = {
    enable = true;
    userName = "Your Name";
    userEmail = "you@example.com";

    extraConfig = {
      init.defaultBranch = "main";
      pull.rebase = true;
      push.autoSetupRemote = true;
    };

    aliases = {
      co = "checkout";
      st = "status";
    };

    ignores = [ ".DS_Store" "*.swp" ];

    signing = {
      key = "KEYID";
      signByDefault = true;
    };

    delta.enable = true;  # Better diffs
  };
}
```

### Shell (Bash)
```nix
{
  programs.bash = {
    enable = true;
    shellAliases = {
      ll = "ls -la";
      update = "sudo nixos-rebuild switch --flake .#hostname";
    };
    initExtra = ''
      # Custom bashrc content
      export PATH="$HOME/.local/bin:$PATH"
    '';
    bashrcExtra = ''
      # Additional bashrc content (sourced before initExtra)
    '';
    profileExtra = ''
      # Additional profile content
    '';
  };
}
```

### Shell (Zsh)
```nix
{
  programs.zsh = {
    enable = true;
    autosuggestion.enable = true;
    syntaxHighlighting.enable = true;

    shellAliases = {
      ll = "ls -la";
      update = "sudo nixos-rebuild switch --flake .#hostname";
    };

    initExtra = ''
      # Custom init
      export PATH="$HOME/.local/bin:$PATH"
    '';

    oh-my-zsh = {
      enable = true;
      plugins = [ "git" "docker" ];
      theme = "robbyrussell";
    };
  };
}
```

### Shell (Fish)
```nix
{
  programs.fish = {
    enable = true;
    shellAliases = { ll = "ls -la"; };
    shellInit = ''
      set -gx PATH $HOME/.local/bin $PATH
    '';
    plugins = [
      { name = "z"; src = pkgs.fishPlugins.z.src; }
    ];
  };
}
```

### Neovim
```nix
{
  programs.neovim = {
    enable = true;
    defaultEditor = true;
    viAlias = true;
    vimAlias = true;

    plugins = with pkgs.vimPlugins; [
      nvim-treesitter.withAllGrammars
      telescope-nvim
      nvim-lspconfig
    ];

    extraLuaConfig = ''
      -- Lua config here
      vim.opt.number = true
    '';

    extraPackages = with pkgs; [
      lua-language-server
      nil  # Nix LSP
    ];
  };
}
```

### Starship Prompt
```nix
{
  programs.starship = {
    enable = true;
    settings = {
      add_newline = false;
      character.success_symbol = "[➜](bold green)";
    };
  };
}
```

### Direnv
```nix
{
  programs.direnv = {
    enable = true;
    nix-direnv.enable = true;  # Better Nix integration
  };
}
```

### Tmux
```nix
{
  programs.tmux = {
    enable = true;
    clock24 = true;
    baseIndex = 1;
    terminal = "screen-256color";
    plugins = with pkgs.tmuxPlugins; [
      sensible
      yank
    ];
    extraConfig = ''
      set -g mouse on
    '';
  };
}
```

## Environment Variables

```nix
{
  home.sessionVariables = {
    EDITOR = "nvim";
    BROWSER = "firefox";
    MY_VAR = "value";
  };

  # Path additions
  home.sessionPath = [
    "$HOME/.local/bin"
    "$HOME/go/bin"
  ];
}
```

## User Services (systemd)

```nix
{
  # Linux only
  systemd.user.services.myservice = {
    Unit.Description = "My Service";
    Install.WantedBy = [ "default.target" ];
    Service = {
      ExecStart = "${pkgs.myapp}/bin/myapp";
      Restart = "always";
    };
  };
}
```

## macOS (launchd)

```nix
{
  # macOS only
  launchd.agents.myservice = {
    enable = true;
    config = {
      Program = "${pkgs.myapp}/bin/myapp";
      RunAtLoad = true;
      KeepAlive = true;
    };
  };
}
```

## Activation Scripts

```nix
{
  home.activation = {
    myScript = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
      # Run after home-manager writes files
      $DRY_RUN_CMD mkdir -p $HOME/.cache/myapp
    '';
  };
}
```

## NixOS vs Home Manager

| Aspect | NixOS | Home Manager |
|--------|-------|--------------|
| Scope | System-wide | Per-user |
| Requires | Root | No root needed |
| Services | systemd system | systemd user |
| Location | /etc, /run | ~/.config, ~/ |
| Packages | Available to all | User-specific |

**Use NixOS for:**
- System services (nginx, postgres)
- Hardware configuration
- Boot, kernel, networking
- System-wide packages

**Use Home Manager for:**
- User dotfiles
- User packages
- Shell configuration
- Desktop apps
- Portable configs (use across systems)
