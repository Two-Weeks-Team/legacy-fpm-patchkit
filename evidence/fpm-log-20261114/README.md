# Retained legacy worker-log evidence

The [summary](../fpm-log-portable-20261114.json) describes [paired run 43606021097](https://github.com/Two-Weeks-Team/legacy-fpm-patchkit/actions/runs/43606021097): Ubuntu 22.04 portable worker-to-master file logging with benign synthetic input.

[`raw.tar.gz`](raw.tar.gz) retains 539 original files, 1,930,156 bytes before compression, from artifact `fpm-log-paired-native`, ID 14118024442. [`raw-files.json`](raw-files.json) pins each member's SHA-256; the summary also pins archive/index hashes and the original artifact digest and expiry (2027-02-12). Repository copies remain available after that expiry.

Included: paired results, source preparation/build records, toolchain/configure arguments, both make logs, 48 producer and 48 barrier response bodies, 48 producer FastCGI-stderr records, input/log hex records, raw logs and shutdown tails, 24 process-cleanup records, producer PHPT sources/output and both normal 36-check reports. Public PHPT copies are test data; generated standalone PHP programs, shell drivers and executable binaries are excluded. All members are regular non-executable data files with safe relative paths, byte-identical to their original artifact members.

Known non-error startup notices about the ignored FPM `user` directive are retained. Candidate-only JSON scanner regeneration is visible in its make log and recorded in the summary. These binaries are identified by their own hashes; compiled-tree equivalence is not claimed.

The secret scanner matched 12 occurrences of the two deterministic public request labels `expansion-stderr-0` and `expansion-stderr-1`. Each exact full line was classified as a fixture correlation label; no other findings were accepted and raw bytes were not altered. These labels are not credentials. Paths belong to the public GitHub runner and its owned temporary test directories. Private operational data and agent transcripts are excluded.

These are copied results, not a new execution. Syslog transport was not tested; no whole-CVE or production acceptance is granted. Default build007 and its historical deployment are unchanged.
