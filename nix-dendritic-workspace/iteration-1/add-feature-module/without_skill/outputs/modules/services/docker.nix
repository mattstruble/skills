# modules/services/docker.nix
#
# Docker feature aspect.
#
# Patterns used:
#   - Multi Context Aspect: the NixOS and Darwin modules each pull in the
#     Home Manager module via home-manager.sharedModules so Docker CLI tools
#     follow every HM-managed user automatically.
#   - Simple Aspect: the homeManager block is also usable standalone (e.g.,
#     imported directly into a standalone Home Manager configuration).
#
# Usage:
#   NixOS host  — import inputs.self.modules.nixos.docker
#     Enables the Docker daemon, adds the configured user to the docker group,
#     and installs Docker CLI tools via Home Manager.
#
#   Darwin host — import inputs.self.modules.darwin.docker
#     Installs Docker CLI tools via Home Manager (daemon managed separately,
#     e.g., Docker Desktop or colima).

{ inputs, ... }:
let
  # The local user that should be added to the docker group on NixOS.
  # Edit this value directly, or set users.users.<name>.extraGroups = [ "docker" ]
  # in your host module instead.
  dockerUser = "user";
in
{
  # ── NixOS ──────────────────────────────────────────────────────────────────
  # Enables the Docker daemon and wires in the Home Manager module so that
  # every HM-managed user on this host gets the CLI tools.
  flake.modules.nixos.docker = {
    # Pull the Home Manager docker module into every HM-managed user on
    # this host (Multi Context Aspect).
    home-manager.sharedModules = [
      inputs.self.modules.homeManager.docker
    ];

    virtualisation.docker = {
      enable = true;
      # Start the daemon at boot rather than on first use (socket activation).
      enableOnBoot = true;
    };

    # Add the configured user to the docker group so they can reach the
    # socket without sudo.  The module system merges this list with any
    # extraGroups set by other modules for the same user.
    users.users.${dockerUser}.extraGroups = [ "docker" ];
  };

  # ── Darwin ─────────────────────────────────────────────────────────────────
  # Wires in the Home Manager docker module for Darwin hosts.  The Docker
  # daemon itself is managed externally (Docker Desktop, colima, etc.).
  flake.modules.darwin.docker = {
    home-manager.sharedModules = [
      inputs.self.modules.homeManager.docker
    ];
  };

  # ── Home Manager ───────────────────────────────────────────────────────────
  # Installs Docker CLI tooling for the user.  Pulled in automatically by the
  # nixos.docker and darwin.docker modules above; also usable standalone.
  flake.modules.homeManager.docker =
    { pkgs, ... }:
    {
      home.packages = with pkgs; [
        docker # Docker CLI (bundles Compose v2 and BuildKit as plugins)
        docker-compose # Standalone docker-compose v2 binary (for legacy scripts)
      ];
    };
}
