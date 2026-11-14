# Retained paired Linux evidence

These are unmodified selected raw files from [workflow run 43592653493](https://github.com/Two-Weeks-Team/legacy-fpm-patchkit/actions/runs/43592653493), artifact `acl-filter-paired-native` (ID 14112629466). The complete artifact digest is `sha256:6bd878d0dc3e961cc0ffb4128524310828737eba29ec3ac81c77ecee9900a84f`; its recorded expiry is 2027-02-12. These repository copies do not depend on the artifact remaining downloadable.

- `advisory-result/result.json`: complete paired result, including individual checks and outputs.
- `advisory-result/{baseline,candidate}/memcheck.xml`: original Valgrind records, preserving the baseline's uninitialized-read finding.
- `build-{baseline,candidate}/build.json`: exact source, configuration, toolchain and executable identities for each side.
- `advisory-result/{baseline,candidate}/{A1,A2,A3,A4,A5,filter-fpm}/process.json`: all 12 owned FPM process termination and cleanup records.

Paths within the files refer to the public GitHub runner. No executables, private operational logs, credentials or agent transcripts are included. SHA-256 values for every retained file are in the parent [public result summary](../acl-filter-portable-20261114.json). The original five published raw-file hashes are preserved there unchanged.

This is Ubuntu 22.04 portable CLI/FPM evidence for the explicitly named ACL/filter variant. It establishes neither Xenial ABI or external-module compatibility nor real-site acceptance or production deployment. Default build007 remains unchanged. See [verification scope and behavior](../../docs/ACL_FILTER_VARIANT.md).
