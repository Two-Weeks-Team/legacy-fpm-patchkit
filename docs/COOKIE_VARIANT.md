# Cookie normalization variant

## Completed portable verification

[Paired run 43603792774](https://github.com/Two-Weeks-Team/legacy-fpm-patchkit/actions/runs/43603792774), head `0f0013bfdc74405b5cbc4379df8c6353b3f00f5b`, built the multipart parent and cookie candidate with the same Ubuntu 22.04 x86-64 portable toolchain. Actual CLI `parse_str` outputs matched 19 cases per build. All **76 FPM requests** (19 cases, twice in the same worker, on each build) matched the expected Cookie/GET/POST key types and byte values. An independent registration model also matched these responses and PHPT output. The parent reproduced manufactured protected names; the candidate rejected them. Authentic prefixes, ordinary arrays, duplicate semantics and binary values were preserved.

All 38 owned FPM instances exited cleanly. FastCGI stderr, unexpected request diagnostics and unexpected shutdown diagnostics were empty; request slices plus shutdown tails matched all 114 complete log channels. The single PHPT failed on the parent for the expected missing protection and passed on the candidate. Both builds passed 36 separate normal checks. [Hashed results](../evidence/cookie-portable-20261114.json) and [493 retained raw files](../evidence/cookie-20261114/README.md) bind source, delta, manifest, binaries and artifact identity.

First run 43603142926 failed while recording the tenth parent fixture: JSON key sorting could not compare integer `0` and string `'01'`. Candidate execution and later checks did not run. The correction records expected maps using explicit typed paths, while preserving the original input strings and in-memory comparisons. The failed run remains recorded; the completed run proves the recording correction, rather than relabeling that failure.

This cumulative variant accounts for **7 implemented / 14 mechanism-absent / 45 planned** catalog entries. CVE-2024-2756 is one additional item; implementing prerequisite checks does not grant separate credit for a 2022 advisory. Default build007 remains **2 / 14 / 50**.

This is one successful Ubuntu 22.04 portable CLI/FPM execution, using synthetic names and values. It establishes the named registration behaviors, not cookie authentication, TLS, browser Secure/Domain enforcement, Xenial ABI, external-module or actual-site compatibility, deployment, load capacity or memory safety. GET/POST share the changed registration function, so applications using rejected names need compatibility review.

## Source and reproduction

`cookie-20261114` layers GHSA-wpj3-hf5j-x4v4 / CVE-2024-2756 onto the complete
`multipart-20261114` source. The older PHP7 tree lacks the prerequisite 2022
prefix checks. This backport implements the full original-name predicate and
the 2024 checks at actual indexed/plain assignment points, including unmatched
bracket fallback. It does not copy unrelated upstream environment-loader changes.

The original registration name remains separate from its mutable normalization
buffer. Existing cookie delimiter whitespace handling and name non-decoding stay
unchanged. The helper compares the pre-mangling registration name after existing
leading-space handling, rather than decoding or rewriting cookie names again.

Normal authentic `__Host-` / `__Secure-` names, ordinary arrays, numeric keys,
suffix normalization and binary values remain supported. Top-level duplicate
cookies keep their first value; GET/POST and nested array updates retain their
existing behavior. A name that only gains a protected prefix through normalization
is rejected. The shared registration function applies this rule to GET/POST too.
As upstream does, each actual string index is checked: a forbidden nested key can
leave an already-created ordinary parent array empty. Automatic numeric append
indices cannot manufacture a protected string prefix.

```sh
python3 -m patchkit prepare --variant multipart-20261114 --output .work/source-parent
python3 -m patchkit prepare --variant cookie-20261114 --output .work/source-cookie
bash scripts/build.sh .work/source-parent .work/build-parent portable multipart-20261114
bash scripts/build.sh .work/source-cookie .work/build-cookie portable cookie-20261114
python3 scripts/cookie-check.py \
  --parent-cli .work/build-parent/php --parent-fpm .work/build-parent/php-fpm \
  --parent-source .work/source-parent \
  --candidate-cli .work/build-cookie/php --candidate-fpm .work/build-cookie/php-fpm \
  --candidate-source .work/source-cookie --output .work/cookie-result
```

The fixed manifest and full parent source are verified before applying the delta.
No arbitrary manifest/expected-hash override is accepted. Earlier variants and
their records remain unchanged, and the existing build driver is reused.

The paired Linux runner compares 19 literal cases through actual CLI parse_str,
real FPM Cookie/GET/POST parsing and a CLI PHPT. Each FPM case is repeated in one
worker. It supplies only synthetic local strings, opens no session in the cookie
fixture and contacts no external service. It uses a private owned Unix socket and
stops only its own process group. The existing 36 benign checks run separately.

Raw responses, exact typed array keys/byte values and per-request diagnostic slices
are preserved. Each request must be quiet; a 2+0 warning distribution cannot pass.
Log truncation, FastCGI stderr and post-cleanup/shutdown diagnostics fail. Evidence
survives failure through the existing short owned-workspace helper. New-source,
mock-backed component, full build, PHP/FPM and CI results must be reported as
separate layers; source/component success is not Linux or deployment acceptance.
