# Migrating to Dendritic Nix

This guide is for experienced Nix users with an existing multi-host or multi-platform config
who want to restructure it using the dendritic pattern. The migration is incremental -- you
don't need to rewrite everything at once.

## Migration Checklist

### Step 1: Add flake-parts and import-tree to your flake inputs

```nix
# flake.nix
{
  inputs = {
    flake-parts.url = "github:hercules-ci/flake-parts";
    import-tree.url = "github:vic/import-tree";
    # ... your existing inputs
  };
}
```

### Step 2: Wrap your outputs with mkFlake

Replace your `outputs` function with `mkFlake` + `import-tree`. Move your existing output
logic into `modules/` files.

Before:
```nix
outputs = { self, nixpkgs, home-manager, ... }@inputs: {
  nixosConfigurations.my-host = nixpkgs.lib.nixosSystem {
    system = "x86_64-linux";
    specialArgs = { inherit inputs; userName = "bob"; };
    modules = [
      ./hosts/my-host/configuration.nix
      ./hosts/my-host/hardware.nix
      home-manager.nixosModules.home-manager
      {
        home-manager.useGlobalPkgs = true;
        home-manager.useUserPackages = true;
        home-manager.users.bob = import ./home/bob.nix;
        home-manager.extraSpecialArgs = { inherit inputs; };
      }
    ];
  };
};
```

After:
```nix
outputs = inputs:
  inputs.flake-parts.lib.mkFlake { inherit inputs; } (inputs.import-tree ./modules);
```

All the logic that was in `flake.nix` moves into files under `modules/`.

### Step 3: Replace specialArgs with let-bindings or flake-parts options

This is usually the biggest change. Every value passed through `specialArgs` or
`extraSpecialArgs` needs a new home.

Before (`specialArgs`):
```nix
nixosConfigurations.my-host = nixpkgs.lib.nixosSystem {
  specialArgs = { inherit inputs; userName = "bob"; adminEmail = "admin@example.org"; };
  modules = [ ./configuration.nix ];
};

# In configuration.nix:
{ userName, adminEmail, ... }:
{
  users.users.${userName}.isNormalUser = true;
  services.zfs.zed.settings.ZED_EMAIL_ADDR = [ adminEmail ];
}
```

After (let-bindings in a flake-parts module):
```nix
# modules/users/bob.nix
let
  userName = "bob";
in
{
  flake.modules.nixos.${userName} = {
    users.users.${userName}.isNormalUser = true;
  };
}

# modules/system/settings/systemConstants.nix
{
  flake.modules.generic.systemConstants =
    { lib, ... }:
    {
      options.systemConstants = lib.mkOption {
        type = lib.types.attrsOf lib.types.unspecified;
        default = { };
      };
      config.systemConstants.adminEmail = "admin@example.org";
    };
}
```

The `inputs` argument is automatically available in every flake-parts module -- no need to
pass it through `specialArgs`.

### Step 4: Replace manual imports with import-tree

Remove explicit `import ./path/to/file.nix` calls from your flake.nix. With `import-tree`,
every `.nix` file under `modules/` is automatically loaded as a flake-parts module.

To temporarily disable a file during migration, prefix it or its parent directory with `_`
(e.g., rename `modules/old-stuff.nix` to `modules/_old-stuff.nix`). `import-tree` ignores
any path containing `/_`.

### Step 5: Reorganize from host-centric to feature-centric

This is the gradual part. Move config from host-specific files into feature files, one
feature at a time.

Before (host-centric):
```
hosts/
├── my-host/
│   ├── configuration.nix  # ssh + printing + bluetooth + users + ...
│   └── hardware.nix
└── my-server/
    ├── configuration.nix  # ssh + syncthing + users + ...
    └── hardware.nix
```

After (feature-centric):
```
modules/
├── services/
│   ├── ssh.nix           # ssh config for all platforms
│   ├── printing.nix      # printing config
│   └── syncthing.nix     # syncthing config
├── system/
│   └── settings/
│       └── bluetooth.nix
├── hosts/
│   ├── my-host.nix       # imports: system-desktop, ssh, printing, bob
│   └── my-server.nix     # imports: system-cli, ssh, syncthing, bob
└── users/
    └── bob.nix
```

Each host file becomes a thin composition of features rather than a monolith.

## Tips

- **Migrate one feature at a time.** Extract ssh, then printing, then users -- don't try to
  restructure everything in one commit.
- **Keep your system building.** After each extraction, run `nixos-rebuild build` (or
  `darwin-rebuild build`) to verify nothing broke.
- **Start with features used on multiple hosts.** These benefit most from the pattern and
  validate that your feature modules work across different compositions.
- **Hardware configs stay per-host.** `hardware-configuration.nix` is inherently host-specific.
  Keep it in the host's directory.

Once migrated, add new features using the aspect patterns in `references/aspect-patterns.md`
and the decision tree in SKILL.md.
