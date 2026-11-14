# Getting started

You should be comfortable building Linux software and administering your existing FPM service. If you only need a currently supported PHP runtime, use your supported distribution packages instead.

## 1. Verify the kit on your control machine

Use Python 3.10+ and `patch`; Git is needed to obtain the repository. No virtual environment or PyPI install is required.

```sh
git clone https://github.com/Two-Weeks-Team/legacy-fpm-patchkit.git
cd legacy-fpm-patchkit
python3 -m patchkit --help
python3 -m patchkit verify
python3 -m unittest discover -v
```

Expected: `INPUTS_VERIFIED` and a green unit suite. This checks kit behavior and patch identity; it does not run PHP.

## 2. Prepare exact public source

```sh
python3 -m patchkit fetch
python3 -m patchkit prepare
```

Expected: `ARCHIVES_VERIFIED`, then `SOURCE_VERIFIED`, 84 vendor patches and 46 changed files. Files are in `.work/source`, with an adjacent preparation JSON and log. Download size is approximately 12 MB. Source extraction and compilation need substantially more disk space.

The source is pinned to Ubuntu `.16`, not a newer ESM package. Pinned HTTPS downloads are verified against checked-in SHA-256 values. A hash match is not a claim that the tool checked an uploader's PGP signature. [Provenance and source normalization](PATCH_SCOPE.md) explains the boundaries.

An existing output is never overwritten. For an independent repeat, use `--output .work/source-second`. Keep failed outputs/logs until you have diagnosed their cause; do not replace expected hashes to make a mismatch pass.

## 3. Build in disposable Linux

Create an isolated Linux VM or use an appropriate dedicated CI runner. Keep credentials and production network access out of it. Transfer the repository and prepared source if your control host is macOS. Source input is checked again before compilation; build generators use a separate copy.

Install the dependencies for the selected [build profile](BUILDING.md), then:

```sh
bash scripts/build.sh .work/source .work/build portable
```

Use `xenial-amd64` only in Ubuntu 16.04 x86-64 with its documented development packages. Do not select it on a modern distribution merely because the CPU matches. The build creates CLI/FPM binaries and `build.json`/`SHA256SUMS`; it performs no system installation.

## 4. Run the actual benign regression

```sh
python3 scripts/native-check.py \
  --fpm .work/build/php-fpm --cli .work/build/php \
  --output .work/native-result.json
```

The small native harness supports Python 3.5+ for the legacy guest. It launches its own temporary FPM with a private config/socket and no external modules or production INI. It tests all three built-in session codecs with upload progress On and Off. A different-codec runtime switch must be rejected; ordinary sessions/uploads and the same worker must continue working. The command fails if a request, assertion, startup or cleanup fails. Run it normally, never with Python's `-O` mode.

Expected: `BENIGN_RUNTIME_PASS`. That establishes the named benign behaviors for **this binary**; it does not certify application or exploit resistance.

## 5. Inspect and practice recovery

```sh
python3 -m patchkit inspect \
  --binary .work/build/php-fpm --build-record .work/build/build.json
python3 -m patchkit rehearse \
  --candidate .work/build/php-fpm --output .work/recovery-drill
```

Inspection does not execute the binary. Recovery practice uses a synthetic original in a NEW directory. Both commands explicitly withhold deployment approval. Finish [target-specific acceptance and installation](INSTALLATION.md) before any live transition.
