# Multipart source variant

## Completed portable verification

[Final paired run 43599570950](https://github.com/Two-Weeks-Team/legacy-fpm-patchkit/actions/runs/43599570950) built the full ACL/filter parent and multipart candidate with the same Ubuntu 22.04 x86-64 portable toolchain. All 60 actual FPM requests matched: 15 cases per build, repeated in the same worker. The candidate alone enforced the 3/4-part, zero/derived-limit and boundary-5117 controls; normal boundary 5115/5116, existing variable/file limits and buffer splitting were preserved. Each request's warning count was checked separately, as were all 30 shutdown tails. Thirty owned FPM instances exited cleanly. Two INI PHPTs failed on the parent for the expected absence of the setting and passed on the candidate; both builds passed 36 separate normal checks.

[Hashed results](../evidence/multipart-portable-20261114.json) and [457 retained small raw files](../evidence/multipart-20261114/README.md) bind source, delta, manifest, binaries and artifact identity. The first run, 43597987318, failed in the fixture before candidate execution; its failure is preserved. Complete runs 43598955155 and 43599570950 agree, including byte-identical binaries and responses after excluding PIDs. The latter also checks shutdown tails. A successful default-build Checks run is recorded separately and is not this multipart evidence.

The observed scope is **Ubuntu 22.04 portable CLI/FPM**, with the minimal configuration explicitly enabling filter/hash/session/json plus core functionality. This does not establish Xenial ABI, arbitrary external-module or site compatibility, production deployment, large-request load capacity or memory-safety properties. Callback END calls were not directly traced: progress=0, empty session files and upload cleanup are measured outcomes. The source reuses the existing callback/cleanup path; source analysis and runtime observations remain distinct.

This cumulative variant accounts for **6 implemented / 14 mechanism-absent / 46 planned** catalog items. Default build007 remains **2 / 14 / 50**. No default archive or historical deployed artifact is replaced.

## Source and reproduction

`multipart-20261114` requires the complete `acl-filter-20261114` parent. It adds
the multipart boundary cap (CVE-2024-8925) and total Content-Disposition part
budget (CVE-2023-0662). Earlier source variants and their evidence remain separate.

The boundary maximum is `FILLUNIT - strlen("\r\n--")`, 5116 bytes for this PHP7
reader. Larger boundaries are rejected before multipart buffers/upload state and
callbacks are initialized. The validated size is then narrowed for the old reader.

`max_multipart_body_parts` is registered at SYSTEM/PERDIR scope, default `-1`.
Negative values derive the limit from `max_input_vars + max_file_uploads`. The
sum saturates at `ZEND_LONG_MAX`; negative sums from negative upload settings
become zero. Explicit zero accepts no parts. The request-local budget counts
Content-Disposition parts even when existing variable/upload rules skip them.
Exceeding it emits one warning and uses the existing END/cleanup path.

```sh
python3 -m patchkit prepare --variant acl-filter-20261114 --output .work/source-parent
python3 -m patchkit prepare --variant multipart-20261114 --output .work/source-multipart
bash scripts/build.sh .work/source-parent .work/build-parent portable acl-filter-20261114
bash scripts/build.sh .work/source-multipart .work/build-multipart portable multipart-20261114
python3 scripts/multipart-check.py \
  --parent-cli .work/build-parent/php --parent-fpm .work/build-parent/php-fpm \
  --parent-source .work/source-parent \
  --candidate-cli .work/build-multipart/php --candidate-fpm .work/build-multipart/php-fpm \
  --candidate-source .work/source-multipart --output .work/multipart-result
```

Preparation uses the existing pinned cache and fixed parent/child manifests; it
does not accept an arbitrary expected hash or manifest. The existing build driver
already delegates its fourth argument to the named source checker and is reused.

The paired runner requires freshly built 64-bit Linux PHP7 binaries and matching
build records. Fifteen small request cases cover 3/4 parts, zero/derived/overflow
budgets, existing upload/variable limits, progress On/Off, boundary cap ±1, mixed
field/file data and a buffer split. Each is repeated in the same worker to check
request-local reset. It preserves raw request/response bytes, warnings, process
cleanup and upload/progress observations. Parent binaries omit only the new,
unregistered INI directive, and the separate PHPT controls prove its absence.

Only owned temporary Unix sockets/processes are used. Short `/tmp/pkmp-*` paths
avoid Unix socket path limits; evidence is copied to the new result directory even
on failure. Prepared source inputs are not written by the PHPT or request tests.
Two CLI PHPT checks cover INI registration/default/permissions; multipart requests
use real FPM rather than requiring a CGI SAPI absent from the normal build profile.
The existing 36 benign checks are run on each binary as separate regression data.

Source, extracted components, complete builds, actual FPM and CI each need their
own results. Successful earlier ACL/filter checks do not demonstrate these two
multipart fixes. Core globals layout changes require a fresh build; external
module ABI/application/deployment compatibility is not established by this work.
