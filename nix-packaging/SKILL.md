---
name: nix-packaging
description: "Use when writing Nix packages from scratch, authoring derivations with stdenv.mkDerivation or language-specific builders (buildPythonPackage, buildRustPackage, buildGoModule), debugging build phase failures, patching package sources, or managing build/runtime dependencies. Also trigger on closure size analysis, wrapProgram, substituteInPlace, or fetchpatch. NOT for system configuration, dev shells, or customizing existing packages with override/overrideAttrs (see nix)."
---

# Nix Packaging Guide

## 1. Packaging Mental Model

A Nix package goes through two distinct stages:

1. **Instantiation**: The Nix expression evaluates to a `.drv` file in the store. This is pure evaluation — no I/O, no network, no side effects.
2. **Realisation**: The `.drv` is built, producing a store path like `/nix/store/abc123-mypkg-1.0/`. This is where compilation happens.

Every package installs to its own unique store path (`$out`). Nothing is shared via FHS paths like `/usr/lib` — every dependency is referenced by its full store path.

**Why everything must be explicit:**
- The sandbox blocks all network access during realisation (except for Fixed-Output Derivations)
- There is no implicit `PATH` — tools must be in `nativeBuildInputs` or explicitly referenced
- No `/usr/bin`, `/lib`, or other FHS paths exist — hardcoded paths in source must be patched

**Derivation types:**
- **Fixed-Output Derivations (FODs)**: Fetchers like `fetchFromGitHub`. They have a known output hash, so Nix permits network access. These are the leaves of the build closure.
- **Input-Addressed Derivations**: Normal packages. The output hash is derived from all inputs — same inputs always produce the same output.
- **Content-Addressed Derivations**: Experimental. The hash is of the actual output content, enabling deduplication across rebuilds.

## 2. stdenv.mkDerivation Scaffold

```nix
{ lib, stdenv, fetchFromGitHub, cmake, pkg-config, openssl, zlib }:

stdenv.mkDerivation rec {
  pname = "mypkg";
  version = "1.2.3";

  src = fetchFromGitHub {
    owner = "example";
    repo = "mypkg";
    rev = "v${version}";
    hash = "sha256-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=";
  };

  # Tools that run on the BUILD machine (compilers, code generators, pkg-config)
  nativeBuildInputs = [ cmake pkg-config ];

  # Libraries linked into the final binary (for the HOST machine)
  buildInputs = [ openssl zlib ];

  # Flags passed to cmake/configure
  cmakeFlags = [
    "-DENABLE_TESTS=OFF"
  ];

  # Override a phase completely — ALWAYS include runHook calls or pre/postPhase hooks break
  buildPhase = ''
    runHook preBuild
    make -j$NIX_BUILD_CORES
    runHook postBuild
  '';

  # Extend a phase without replacing it (preferred over overriding)
  postInstall = ''
    install -Dm644 LICENSE $out/share/licenses/mypkg/LICENSE
  '';

  # Skip phases you don't need
  # dontConfigure = true;
  # dontBuild = true;
  # dontFixup = true;

  meta = with lib; {
    description = "A short description";
    homepage = "https://github.com/example/mypkg";
    license = licenses.mit;
    maintainers = [ ];
    platforms = platforms.unix;
  };
}
```

**Phase execution order**: `unpackPhase` → `patchPhase` → `configurePhase` → `buildPhase` → `checkPhase` → `installPhase` → `fixupPhase`

**The `runHook` rule**: Whenever you override a phase entirely (e.g., `buildPhase = ''...''`), you MUST include `runHook preBuild` at the start and `runHook postBuild` at the end. Without these, any `preBuild`/`postBuild` hooks set elsewhere (including by setup hooks from dependencies) will silently not run. This is the most common cause of mysterious build failures after adding a dependency.

**Prefer hooks over overrides**: Use `preConfigure`, `postBuild`, `postInstall`, etc. to extend phases rather than replacing them. This composes better with setup hooks from dependencies.

See the [nixpkgs manual phases reference](https://nixos.org/manual/nixpkgs/stable/#sec-stdenv-phases) for the full phase API.

## 3. Dependency Taxonomy

Getting this right matters for cross-compilation. Even for native builds, correct placement is good practice.

| Attribute | What goes here | Rule of thumb |
|-----------|---------------|---------------|
| `nativeBuildInputs` | Tools that run during the build: `cmake`, `pkg-config`, `makeWrapper`, `protobuf`, code generators, `python3` (if used to generate code) | "Does this tool execute on my machine during compilation?" |
| `buildInputs` | Libraries linked into the final binary: `openssl`, `zlib`, `gtk3`, `boost` | "Does this get linked into the output binary?" |
| `propagatedBuildInputs` | Libraries whose headers/modules consumers also need | "Will packages that depend on mine also need to find these headers?" |
| `propagatedNativeBuildInputs` | Build tools that consumers also need | Rare — mostly for language ecosystems |

**The cross-compilation reason**: On a native build, both lists end up on `PATH` and `PKG_CONFIG_PATH` similarly. But in cross-compilation, `nativeBuildInputs` runs on the build machine (x86_64) while `buildInputs` targets the host machine (aarch64). Mixing them breaks cross builds.

**`propagatedBuildInputs` warning**: Every entry increases the closure size of every package that depends on yours. Use it only when consumers genuinely need the headers or modules at build time (common for C libraries with public headers, Python libraries, pkg-config `.pc` files that reference other `.pc` files).

**Common mistakes:**
- `cmake` in `buildInputs` instead of `nativeBuildInputs` — cmake runs during build, not at runtime
- `pkg-config` in `buildInputs` — same issue
- A Python library in `nativeBuildInputs` when it's a runtime import — it won't be in the closure

## 4. Runtime Dependencies & wrapProgram

Nix determines runtime dependencies automatically: after the build, it scans every file in `$out` for store path hashes. If `/nix/store/abc123-openssl-3.0` appears anywhere in your output (binary, script, config file), openssl becomes a runtime dependency.

This means:
- You don't declare runtime deps explicitly — they're detected from the output
- A script that `exec`s another program won't pull that program into the closure unless the path is hardcoded
- Scripts that shell out to tools like `curl` or `jq` need those tools injected via `wrapProgram`

**`wrapProgram` pattern** for scripts that shell out:

```nix
{ lib, stdenv, makeWrapper, curl, jq }:

stdenv.mkDerivation {
  # ...
  nativeBuildInputs = [ makeWrapper ];  # makeWrapper is a build tool

  postInstall = ''
    wrapProgram $out/bin/myscript \
      --prefix PATH : ${lib.makeBinPath [ curl jq ]}
  '';
}
```

`wrapProgram` replaces the binary with a wrapper script that sets environment variables before exec-ing the original. `--prefix PATH :` prepends to PATH rather than replacing it.

**`wrapProgram` creates wrapper scripts that embed store paths.** When diagnosing an unexpectedly large closure, check whether your binary is actually a wrapper script:
```bash
file /nix/store/xxx-mypkg/bin/mybinary
# "POSIX shell script" means wrapProgram was used — the script embeds store paths
# for every tool in --prefix PATH, pulling them into the runtime closure
strings /nix/store/xxx-mypkg/bin/mybinary | grep /nix/store/
```
This is the most common source of unexpected closure entries in packages that use `wrapProgram`.

**Closure analysis commands:**
```bash
nix-store -q --references /nix/store/xxx-mypkg   # immediate deps
nix-store -q --requisites /nix/store/xxx-mypkg   # full transitive closure
nix why-depends /nix/store/xxx-mypkg /nix/store/yyy-dep  # trace why dep is included
nix path-info -Sh /nix/store/xxx-mypkg           # closure size (human-readable)
```

## 5. Patching

**`substituteInPlace`** for fixing hardcoded paths:

```nix
# Inside a postPatch = ''...'' Nix string — ${curl} is Nix interpolation, $out is a shell variable:
substituteInPlace src/config.c \
  --replace-fail '/usr/bin/curl' '${curl}/bin/curl'

# Multiple replacements:
substituteInPlace Makefile \
  --replace-fail '/usr/local' "$out" \
  --replace-fail 'gcc' "$CC"
```

Always use `--replace-fail` (not `--replace`). The `--replace` flag emits a deprecation warning but does not fail the build when the pattern is absent — you'll get a binary that still has the hardcoded path and crashes at runtime. `--replace-fail` errors if the pattern is absent, catching the problem at build time.

**Quoting note**: Inside Nix `''...''` strings (multiline phase attributes), `${curl}` is Nix interpolation (expands to the store path at instantiation time) and `$out`, `$CC`, `$NIX_BUILD_CORES` are shell variables (available at build time). Never confuse the two: `${CC}` in a `''...''` string would try to interpolate a Nix variable named `CC`, not the shell variable.

**`replaceVars`** for template substitution with `@variable@` patterns — a Nix-level function that returns a store path:

```nix
# replaceVars is a Nix function, not a shell command — use it as an attribute value:
someScript = replaceVars ./myscript.sh.in {
  inherit curl;
  bash = "${bash}/bin/bash";
};

# substituteAll is a shell function for use inside phase strings:
postPatch = ''
  substituteAll ${./config.h.in} config.h
'';
```

`replaceVars` is type-safe — it fails if any `@variable@` in the template doesn't have a corresponding Nix variable. `substituteAll` substitutes all in-scope Nix variables; `replaceVars` takes an explicit attrset and is preferred when you want to be explicit.

**`fetchpatch`** for upstream patches:

```nix
patches = [
  ./fix-local.patch  # local patch file
  (fetchpatch {
    # Upstream PR #1234 fixing the crash on arm64
    # Remove when upgrading past v2.1.0
    url = "https://github.com/example/pkg/commit/abc123.patch";
    hash = "sha256-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=";
  })
];
```

Always document patches with: what they fix, a link to the upstream PR/issue, and when they can be removed.

**Creating a local patch:**
```bash
# Non-flake:
nix-shell -A mypkg       # enter build env
# Flake:
nix develop .#mypkg      # enter dev shell with build tools
unpackPhase               # extract source
cd $sourceRoot
git init && git add -A && git commit -m "pristine"
# make your changes
git diff > $OLDPWD/fix.patch
```

## 6. Language Builders

### Python (`buildPythonPackage` / `buildPythonApplication`)

```nix
{ lib, buildPythonApplication, fetchFromGitHub,
  setuptools, requests, click }:

buildPythonApplication {
  pname = "mytool";
  version = "1.0.0";

  src = fetchFromGitHub {
    owner = "example";
    repo = "mytool";
    rev = "v1.0.0";
    hash = "sha256-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=";
  };

  build-system = [ setuptools ];  # PEP 517 build backend

  dependencies = [ requests click ];  # runtime Python deps

  # Avoid doCheck = false unless tests are structurally incompatible with the
  # sandbox (e.g., require a running database). Disabling tests removes the
  # only build-time behavioral verification for third-party code.
  # doCheck = false;
}
```

**Key gotchas:**
- `buildPythonApplication` vs `buildPythonPackage`: Use `buildPythonApplication` for executables (installs to `$out/bin`, not importable as a library). Use `buildPythonPackage` for libraries (importable by other packages).
- Use `dependencies` for Python runtime deps (not `propagatedBuildInputs`). The Python infrastructure handles propagation automatically.
- `build-system` is for the PEP 517 build backend (setuptools, flit-core, hatchling, etc.) — not for runtime deps.
- To use a specific Python version: `python311.pkgs.buildPythonApplication { ... }` or `pkgs.python311Packages.callPackage ./pkg.nix { }`.

See the [nixpkgs Python packaging guide](https://nixos.org/manual/nixpkgs/stable/#python) for the full API including test frameworks and wheel support.

### Rust (`buildRustPackage`)

```nix
{ lib, rustPlatform, fetchFromGitHub, openssl, pkg-config }:

rustPlatform.buildRustPackage {
  pname = "mytool";
  version = "1.0.0";

  src = fetchFromGitHub {
    owner = "example";
    repo = "mytool";
    rev = "v1.0.0";
    hash = "sha256-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=";
  };

  # Option 1: lock file (preferred — reproducible)
  cargoLock.lockFile = ./Cargo.lock;

  # Option 2: vendor hash (set to lib.fakeHash first, use error output)
  # cargoHash = "sha256-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=";

  nativeBuildInputs = [ pkg-config ];
  buildInputs = [ openssl ];
}
```

**Key gotchas:**
- `cargoHash` must be updated whenever `Cargo.lock` changes. Set it to `lib.fakeHash` first, build to get the error with the correct hash, then update.
- `cargoLock.lockFile` is more reproducible — it vendors dependencies from the lock file directly.
- For complex builds (workspaces, custom build scripts, C FFI), consider [crane](https://github.com/ipetkov/crane) or [naersk](https://github.com/nix-community/naersk) as alternatives.

### Go (`buildGoModule`)

```nix
{ lib, buildGoModule, fetchFromGitHub }:

buildGoModule {
  pname = "mytool";
  version = "1.0.0";

  src = fetchFromGitHub {
    owner = "example";
    repo = "mytool";
    rev = "v1.0.0";
    hash = "sha256-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=";
  };

  vendorHash = "sha256-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=";

  # Build only specific packages (omit to build all)
  subPackages = [ "cmd/mytool" ];
}
```

**Key gotchas:**
- Set `vendorHash = lib.fakeHash;` first — this is a bootstrap sentinel that intentionally fails the build with a hash mismatch error that prints the correct hash. Replace it with that hash before committing. **Never commit `vendorHash = lib.fakeHash` or `vendorHash = ""` as final values** — they will always fail the build. (`vendorHash = null` is valid only for modules with no external dependencies.)
- `subPackages` limits which `cmd/` packages are built — useful for repos with multiple binaries where you only want one.
- If the module has no external dependencies, use `vendorHash = null;`.

### C/C++ with CMake or Meson

```nix
{ lib, stdenv, fetchFromGitHub, cmake, pkg-config, glib }:

stdenv.mkDerivation {
  # ...
  nativeBuildInputs = [ cmake pkg-config ];  # cmake/meson are build tools
  buildInputs = [ glib ];

  cmakeFlags = [
    "-DBUILD_TESTS=OFF"
    "-DCMAKE_BUILD_TYPE=Release"
  ];

  # For meson, use: nativeBuildInputs = [ meson ninja pkg-config ];
  # and mesonFlags = [ "-Dtests=disabled" ];
}
```

cmake and meson go in `nativeBuildInputs` — they're build tools, not linked libraries. See the [nixpkgs cmake setup hook docs](https://nixos.org/manual/nixpkgs/stable/#cmake) for how cmake integration works automatically.

## 7. Multiple Outputs

Split a package into separate outputs to reduce closure size for consumers:

```nix
stdenv.mkDerivation {
  # ...
  outputs = [ "out" "dev" "lib" "man" ];
  # out: binaries and data files
  # dev: headers and pkg-config files
  # lib: shared libraries
  # man: man pages
}
```

When another package lists yours in `buildInputs`, it gets the `.dev` output by default (if it exists), which contains headers. The runtime closure only needs `.lib` or `.out`.

```nix
# Explicitly select an output:
buildInputs = [ mylib.dev ];  # headers
buildInputs = [ mylib.lib ];  # shared library only
```

Helper functions: `lib.getDev pkg`, `lib.getLib pkg`, `lib.getBin pkg`.

**When to use multiple outputs**: C/C++ libraries where headers and shared libs are separate concerns. A package with 50MB of headers and 2MB of runtime library — consumers only need the 2MB at runtime. Reduces runtime closure by 30-50% in typical cases.

## 8. Common Mistakes

**List/function application ambiguity:**
```nix
# WRONG: two list elements — the function and the attrset
buildInputs = [ somePackage.override { enableFeature = true; } ];

# CORRECT: parentheses make it one element
buildInputs = [ (somePackage.override { enableFeature = true; }) ];
```
Nix's function application is whitespace-sensitive. `f { }` applies `f` to `{ }`, but `[ f { } ]` is a list with two elements.

**Excessive `with`:**
```nix
# AVOID: introduces 15,000+ names into scope, makes code hard to read
with pkgs; [ cmake openssl zlib ]

# PREFER: scope `with` tightly to the list
nativeBuildInputs = with pkgs; [ cmake pkg-config ];
buildInputs = with pkgs; [ openssl zlib ];
```

**URL-like strings:**
```nix
# WRONG: parsed as a URL string, not a function
f = x:x;

# CORRECT: space after colon required
f = x: x;
```

**Forgetting `runHook` in phase overrides:**
```nix
# WRONG: breaks preBuild/postBuild hooks from dependencies
buildPhase = ''
  make -j$NIX_BUILD_CORES
'';

# CORRECT
buildPhase = ''
  runHook preBuild
  make -j$NIX_BUILD_CORES
  runHook postBuild
'';
```

**Hardcoding the compiler:**
```nix
# WRONG: breaks cross-compilation and clang stdenvs
buildPhase = "gcc -o mybin src.c";

# CORRECT: stdenv sets $CC to the right compiler
buildPhase = "$CC -o mybin src.c";
```

**Silent `substituteInPlace` failures:**
```nix
# WRONG: emits a warning but does not fail the build when pattern is absent
substituteInPlace src/config.c --replace '/usr/bin/curl' '${curl}/bin/curl'

# CORRECT: fails the build if pattern is absent
substituteInPlace src/config.c --replace-fail '/usr/bin/curl' '${curl}/bin/curl'
```

## 9. Debugging Toolkit

**Interactive build environment (legacy/non-flake):**
```bash
nix-shell -A mypkg          # enter the build sandbox environment (non-flake only)
unpackPhase                  # extract source to $sourceRoot
cd $sourceRoot
configurePhase               # run configure/cmake
buildPhase                   # attempt the build
```

**Interactive build environment (flakes):**
```bash
# Enter the package's build environment (not a devShell).
# nix develop resolves .#mypkg to packages.<system>.mypkg automatically:
nix develop .#mypkg
unpackPhase && cd $sourceRoot
configurePhase
buildPhase
```

This lets you run phases manually, inspect errors, and test fixes without a full rebuild cycle.

**Build logs:**
```bash
nix build .#mypkg -L                          # verbose build output
nix build .#mypkg --print-build-logs          # same, explicit flag
nix log /nix/store/xxx-mypkg.drv              # read logs after failure
```

**Closure analysis:**
```bash
nix why-depends /nix/store/xxx-mypkg /nix/store/yyy-dep   # trace why dep is included
nix path-info -Sh /nix/store/xxx-mypkg                    # closure size
nix-tree /nix/store/xxx-mypkg                             # TUI closure browser (install nix-tree)
```

**Evaluating expressions:**
```bash
nix repl
nix-repl> :lf .                    # load current flake
nix-repl> pkgs.mypkg.drvPath       # inspect the .drv path
nix-repl> pkgs.mypkg.buildInputs   # inspect resolved deps
```

## References

| Reference | When to read it |
|-----------|----------------|
| [nixpkgs manual — stdenv phases](https://nixos.org/manual/nixpkgs/stable/#sec-stdenv-phases) | Full phase lifecycle, all hooks, `genericBuild` internals |
| [nixpkgs manual — Python](https://nixos.org/manual/nixpkgs/stable/#python) | `buildPythonPackage` full API, test frameworks, wheel support |
| [nixpkgs manual — Rust](https://nixos.org/manual/nixpkgs/stable/#rust) | `buildRustPackage` full API, cross-compilation, workspace builds |
| [nixpkgs manual — Go](https://nixos.org/manual/nixpkgs/stable/#sec-language-go) | `buildGoModule` full API, CGO, vendoring |
| [nixpkgs manual — cmake setup hook](https://nixos.org/manual/nixpkgs/stable/#cmake) | How cmake integration works automatically |
| [nix-book](https://ekala-project.github.io/nix-book/) | Deep packaging reference, derivation internals |
| `../nix/references/nixpkgs-advanced.md` | `callPackage`, overlays, overrides, fetchers, trivial builders |
