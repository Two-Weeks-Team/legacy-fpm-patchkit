# Explicit ACL/filter source variant

`acl-filter-20261114` layers two one-line changes onto the frozen build007 source.
It compares the full IPv6 address for `listen.allowed_clients` and initializes
all 256 URL sanitizer lookup entries. Mapped IPv4's offset 12 / length 4 stays
unchanged. IPv6 allowlist entries are individual addresses, not /96 ranges.

## Completed portable runtime verification

[Run 43592653493](https://github.com/Two-Weeks-Team/legacy-fpm-patchkit/actions/runs/43592653493) built both variants from pinned full source on Ubuntu 22.04 x86-64 with gcc 11.4/glibc 2.35. Baseline/candidate A1–A5 behaved as specified below. Valgrind found the baseline's exact uninitialized table branch at `sanitizing_filters.c:108` (37 occurrences) and no candidate errors. The 270 byte/normal/flag cases, five existing PHPTs plus the new PHPT, and 36 benign checks passed on both builds. Twelve owned FPM instances exited cleanly.

[Public evidence](../evidence/acl-filter-portable-20261114.json) binds source/patch/binary hashes, raw-file hashes and the GitHub artifact digest. The baseline's ordinary output also passed; its Valgrind observation supplies the distinguishing RED. The new variant therefore adds two implemented advisories to build007's two: 4 implemented, 14 mechanism-absent, 48 planned. No Xenial binary, external-module or production validation is claimed for this variant.

The default remains `build007`. Its patch, inputs and preparation are preserved.
The new variant has a fixed repository manifest and patch, with a manifest digest
pinned in `patchkit/variants.py`. No arbitrary manifest path or expected-hash
override is accepted. Preparation verifies and publishes a new **whole tree**.

The [behavior changes](BEHAVIOR_CHANGES.md#optional-aclfilter-variant) explain the narrower IPv6 admission rule, mapped-address distinction and byte-filter semantics. The verified portable configuration uses `--disable-all` and explicitly enables `filter`, `hash`, `session` and `json`, alongside core functionality. It does not represent every PHP extension configuration.

Binary hashes identify the exact artifacts from each recorded build. The paired baseline's hashes differ from the standalone default build record; source identity does not promise bit-identical recompilation. Build paths embedded in debug information can affect bytes, but the cause of this particular difference was not established by a binary comparison. Use the hashes belonging to the run being checked.

## Permanent raw evidence

The [retained raw files](../evidence/acl-filter-20261114/README.md) include the complete paired result JSON, both original Valgrind XML files, both build records and all 12 process cleanup records. The five previously published raw-file hashes still match these byte-for-byte copies. They remain available in repository history after the original GitHub artifact's recorded expiry of 2027-02-12. Executables and private operational or agent logs are not included.

## Reproduce on isolated Linux

```sh
python3 -m patchkit fetch
python3 -m patchkit prepare --output .work/source-baseline
python3 -m patchkit prepare --variant acl-filter-20261114 --output .work/source-candidate
bash scripts/build.sh .work/source-baseline .work/build-baseline portable
bash scripts/build.sh .work/source-candidate .work/build-candidate portable acl-filter-20261114
python3 scripts/advisory-check.py \
  --baseline-cli .work/build-baseline/php --baseline-fpm .work/build-baseline/php-fpm \
  --baseline-source .work/source-baseline \
  --candidate-cli .work/build-candidate/php --candidate-fpm .work/build-candidate/php-fpm \
  --candidate-source .work/source-candidate --output .work/advisory-result
```

Builds and the runtime runner require Linux. The runtime runner also requires
IPv6 loopback, dual-stack sockets (`bindv6only=0`), trusted freshly built binaries,
their matching build records/configuration and Valgrind. It starts only its own
foreground FPM processes and makes only literal loopback requests. A3/A4 use an
ephemeral `[::]` listener with a loopback IPv4 allowlist to exercise mapped peers.
It never changes sysctls, installs a service or controls a container.

The runner records actual A1–A5 responses/drop logs, complete filter byte outputs,
normal/flag cases, existing and new PHPT runs, and both sets of 36 existing benign
checks. It copies PHPT files into its new result directory so generated PHPT
diagnostics cannot alter prepared input trees. Timeouts and cleanup are bounded;
forced cleanup is a failure. Raw logs/configuration and identities survive failure.

The baseline A2 must allow while the candidate refuses. Ordinary controls must
hold on both. A Valgrind error counts as filter RED only when an uninitialized
read trace reaches the sanitizer. If that baseline observation is absent, the
result is `PARTIAL_BASELINE_MEMCHECK_RED_NOT_OBSERVED` (nonzero exit), even if
candidate output is correct. A baseline 0xff output discrepancy is preserved;
other output corruption fails. ASan, UBSan and compiler stack initialization do
not replace this observation.

The completed paired workflow uses the existing `portable` profile on a hosted
Ubuntu runner. This does not establish Xenial ABI, external-module compatibility,
application exposure or production deployment. Source, build, runtime and CI
results must each be reported from actual evidence before claiming resolution.
