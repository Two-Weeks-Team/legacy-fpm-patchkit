# Stream-filter boundary variant

`stream-filters-20261115` is a repository-pinned child of the complete
`fpm-log-20261114` source. It tracks two advisories separately:

- GHSA-88hq-2827-7pg6 / CVE-2026-92842: preserve every byte and the original length
  of `line-break-chars` in all three affected constructors. PHP7's `pestrndup`
  already provides the required binary-safe duplication for both persistence
  modes. Embedded NUL is supported, rather than rejected or shortened.
- GHSA-r977-prxv-hc43 / CVE-2024-11233: check zero remaining input before state 5
  dereferences the decoder input. An empty chunk keeps the pending CR state so
  the next LF can complete the soft break.

Both changes are in `ext/standard/filters.c`. The PHP7 parent has fallible
allocation and an older final-flush contract. The backport therefore also checks
duplication failures, propagates option-copy/default/instance allocation failure,
and releases the already-owned option/string reference on those paths. This is
limited to the three affected option/constructor paths, not a complete Zend OOM
audit. Borrowed strings and persistent/nonpersistent ownership remain supported.

Blindly moving the state-5 guard leaves valid completed custom soft breaks and
auto-detected CR pending at EOF. In this parent their final flush dereferences
NULL. Final flush now resolves complete breaks without input, reports an incomplete
custom break as unexpected EOS, and drains buffered state-6 bytes using a bounded
empty input. The recursive drain is at most one level; its recursive call has
non-NULL input arguments. No modern PHP API or external codec is introduced.

```sh
python3 -m patchkit prepare --variant fpm-log-20261114 --output .work/source-stream-parent
python3 -m patchkit prepare --variant stream-filters-20261115 --output .work/source-stream
bash scripts/build.sh .work/source-stream-parent .work/build-stream-parent portable fpm-log-20261114
bash scripts/build.sh .work/source-stream .work/build-stream portable stream-filters-20261115
python3 scripts/stream-filters-check.py \
  --parent-cli .work/build-stream-parent/php --parent-fpm .work/build-stream-parent/php-fpm \
  --parent-source .work/source-stream-parent \
  --candidate-cli .work/build-stream/php --candidate-fpm .work/build-stream/php-fpm \
  --candidate-source .work/source-stream --valgrind /usr/bin/valgrind \
  --output .work/stream-filter-result
```

Use the existing Linux validation environment with Valgrind available. The runner
verifies full source identity, the named build record and both binary hashes.
It does not accept arbitrary manifest/hash overrides or change the default build
driver, earlier source pins or artifact JSON contracts.

The actual-runtime gates are deliberately distinct:

1. A tiny write-filter probe runs under Valgrind with `USE_ZEND_ALLOC=0`. It closes
   the stream without reading/displaying its converted contents. Parent RED must
   consist only of target `InvalidRead` contexts in the base64 converter from the
   one-byte allocation, with exit 97 and an independent completion marker.
   Candidate must complete with no memory-checker errors. This real-runtime memory
   differential covers the base64 constructor; source/component and candidate
   functional tests cover the two quoted-printable constructors too.
2. A split-CR/LF PHPT must produce the exact parent failure output `410a42` and
   candidate output `4142`. A clean same-output result on both sides cannot supply
   the required RED; crashes, warnings, skips and setup failures cannot either.
3. Normal codec PHPT passes on both sides. Candidate-only binary-option PHPT checks
   all three constructors, empty options and EOF handling. Parent binary outputs
   are not dumped or used as a functional leak demonstration.
4. A small ordinary codec matrix runs twice in one owned FPM worker per side and
   must match the literal map with PID/completion markers. No session is opened.
   Per-request, whole-log and post-cleanup diagnostics must stay quiet. This is
   normal FPM compatibility evidence, not a second memory-safety differential.
5. Existing benign runtime checks run separately, 36 per side.

The owned Unix socket/pool and process group are temporary. The runner has a
600-second work budget, phase limits and bounded owned-process cleanup. Forced or
unexpected exit fails and raw evidence survives failure. No remote service,
installation, deployment, credentials, large allocation or syslog daemon is used.

The private component tests compile the contiguous original codec/open region and
the exact Zend string-duplication function bodies with explicit allocation/type/
property adapters. ASan/UBSan and small controlled input prove those boundaries;
they are not full PHP/FPM/ABI evidence or actual Zend memory-pressure tests.
Source preparation, component, normal codec compatibility, memory differential,
actual Linux/FPM, CI and production status must be reported separately.
