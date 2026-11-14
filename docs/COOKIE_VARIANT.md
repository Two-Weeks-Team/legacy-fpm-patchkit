# Cookie normalization variant

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
