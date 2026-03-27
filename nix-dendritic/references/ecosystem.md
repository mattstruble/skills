# Dendritic Ecosystem

Tools, libraries, and community resources for working with the Dendritic pattern.

## flake-parts

The framework that makes dendritic configs possible. It provides the `flake.modules.<class>.<aspect>`
option that is the core mechanism of the pattern.

Setup in your `flake.nix`:
```nix
{
  inputs = {
    flake-parts.url = "github:hercules-ci/flake-parts";
  };
  outputs = inputs:
    inputs.flake-parts.lib.mkFlake { inherit inputs; } {
      # Your flake-parts modules here, or use import-tree
      imports = [ /* ... */ ];
    };
}
```

Enable the modules option (required for `flake.modules` to work). See `references/scaffolding.md`
for the full `flake-parts.nix` template including `mkNixos`/`mkDarwin`/`mkHome` helper functions.
The minimal setup is:

```nix
# modules/nix/flake-parts.nix
{ inputs, ... }:
{
  imports = [ inputs.flake-parts.flakeModules.modules ];
  systems = [ "x86_64-linux" ]; # adjust to your target architectures
}
```

Key concepts:
- `flake.modules.<class>.<aspect>` defines a named module for a given class
- Module classes include `nixos`, `darwin`, `homeManager`, and any custom name you define
- `inputs.self.modules.<class>.<aspect>` references a defined module for use in `imports`
- `perSystem` provides per-system outputs (packages, devShells, checks)

Docs: https://flake.parts

## import-tree

Automatically imports all `.nix` files under a directory as flake-parts modules. Eliminates
manual import management.

```nix
# flake.nix -- the only place you call import-tree
outputs = inputs:
  inputs.flake-parts.lib.mkFlake { inherit inputs; } (inputs.import-tree ./modules);
```

Add to your inputs:
```nix
inputs.import-tree.url = "github:vic/import-tree";
```

Conventions:
- Every `.nix` file under the target directory is loaded as a flake-parts module
- Files or directories with `/_` in their path are ignored (e.g., `modules/_disabled/foo.nix`)
- This ignore convention is useful for temporarily disabling features during development or migration
- Subdirectory structure is purely organizational -- it has no effect on module loading or namespacing

Repo: https://github.com/vic/import-tree

## flake-file (optional)

Lets each flake-parts module declare the flake inputs it needs. Inputs are collected and
managed automatically, so `flake.nix` stays minimal.

```nix
# modules/programs/nixvim.nix
{ inputs, ... }:
{
  flake-file.inputs.nixvim.url = "github:nix-community/nixvim";

  flake.modules.homeManager.vim = {
    imports = [ inputs.nixvim.homeManagerModules.nixvim ];
    programs.nixvim.enable = true;
  };
}
```

Setup:
```nix
inputs.flake-file.url = "github:vic/flake-file";

# In your flake-parts setup module:
imports = [ inputs.flake-file.flakeModules.default ];
```

### Quick setup with `flakeModules.dendritic`

`flake-file` also provides a `flakeModules.dendritic` convenience module that sets up
flake-file, import-tree, flake-parts, and configures `outputs` to import all `./modules`
in one step. This replaces manual wiring of these three tools:

```nix
# In your flake-parts setup module:
imports = [ inputs.flake-file.flakeModules.dendritic ];
```

This is a convenience, not a requirement. It makes inputs co-located with the features that
use them, but adds another dependency to understand. Consider adopting it after you're
comfortable with the base dendritic pattern.

Repo: https://github.com/vic/flake-file

## Alternatives

These implement the dendritic pattern differently or offer alternative approaches:

- **den** (https://github.com/vic/den) -- aspect-oriented configuration approach. A different
  take on the same underlying ideas.
- **dendritic-unflake** (https://github.com/vic/dendritic-unflake) -- dendritic configuration
  without flakes or flake-parts. For users who prefer the pattern but want to avoid the flakes
  ecosystem.
- **Unify** (https://codeberg.org/quasigod/unify/) -- framework for unifying multiple Nix
  configuration types under a single interface.

## Community and References

- **Dendritic Pattern** (https://github.com/mightyiam/dendritic) -- the pattern definition
- **Dendrix** (https://dendrix.oeiuwq.com) -- community-driven dendritic configurations
- **Doc-Steve's Design Guide** (https://github.com/Doc-Steve/dendritic-design-with-flake-parts) --
  comprehensive guide with aspect patterns and a worked example
- **Pol Dellaiera: Flipping the Configuration Matrix** (https://not-a-number.io/2025/refactoring-my-infrastructure-as-code-configurations/#flipping-the-configuration-matrix) --
  essay on the feature-centric vs host-centric shift
- **NixOS Discourse: Every File is a Flake-Parts Module** (https://discourse.nixos.org/t/pattern-every-file-is-a-flake-parts-module/61271) --
  community discussion of the pattern
