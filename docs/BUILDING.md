# Building in isolation

## Input contract

Only `.work/source` (or another new output from `prepare`) with the exact normalized candidate digest is accepted. The build script checks the complete input and copies it to `NEW_OUTPUT/source` before running re2c/buildconf. It never relies on a private cache or modifies the prepared original. Fresh output paths are mandatory.

Reserve at least 4 GB free disk and 2 GB available RAM; 4 GB RAM and 2 build jobs are a reasonable starting point. Build time varies substantially under CPU emulation. `JOBS` controls make parallelism. Keep full `buildconf.log`, `configure.log`, `make.log`, toolchain and dependency records when investigating a failure.

## Profiles

| Profile | Purpose | Dependencies and limits |
|---|---|---|
| `portable` | Benign native regression on modern Linux | C compiler, make, autoconf compatible with PHP 7.0, automake/libtool, bison, re2c, pkg-config, Python, binutils; minimal built-in session/hash/filter/JSON; no OpenSSL/systemd/libxml promise |
| `xenial-amd64` | Isolated Ubuntu 16.04 x86-64 source build | Same build tools plus libxml2-dev, libssl-dev (legacy OpenSSL), zlib1g-dev, libpcre3-dev, libmhash-dev, libedit-dev, libsystemd-dev, systemtap-sdt-dev, libevent-dev |

Typical build-tool packages on an isolated Debian/Ubuntu machine are `build-essential autoconf automake bison re2c pkg-config dpkg-dev libtool binutils`. Install development packages using your environment's trusted package manager; this repository does not provision or mutate your operating system automatically. Legacy package availability and support are outside this kit.

The Xenial profile preserves the relevant original feature choices but uses a deliberate public prefix and clean configure invocation. It removes the old private configure cache. Different compilers/libraries/generator versions can produce different binaries; the project claims **source/procedure reproducibility**, not bit-for-bit agreement with the historical deployed build007.

## Commands

```sh
# On the control host:
python3 -m patchkit fetch
python3 -m patchkit prepare

# In isolated Linux, with the repository and prepared source:
bash scripts/build.sh .work/source .work/build portable
# Or, only on the documented Xenial host:
# bash scripts/build.sh .work/source .work/build-xenial xenial-amd64

python3 scripts/native-check.py \
  --fpm .work/build/php-fpm --cli .work/build/php \
  --output .work/native-result.json
```

## Output

`php`, `php-fpm`, `build.json`, `SHA256SUMS`, configure arguments, compiler/generator versions, ELF headers/dynamic entries and linked-library names are recorded. `BUILT_NOT_RUNTIME_VERIFIED` remains the build result even if the separate native test later passes; consult both records.

Hardening includes PIE, stack protector, format-security, FORTIFY_SOURCE and RELRO/NOW. Implicit function declaration and integer conversion errors remain fatal. Read compiler warnings rather than interpreting compilation alone as correctness.

`ldd` is used only on the binary just built from the verified source. Do not apply `ldd` to an untrusted downloaded executable; use `patchkit inspect` for nonexecuting basic inspection.

## Module/application acceptance

API number `20151012`, NTS/non-debug and architecture are necessary context, not sufficient ABI proof. Inventory exact extension files/digests and library packages from your target; test them in an equivalent isolated environment using a copied configuration with private paths and services removed. Run your actual site flows before activation. The bundled native test deliberately loads no external modules, so it cannot certify them.
