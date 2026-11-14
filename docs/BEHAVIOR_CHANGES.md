# Behavior changes

## Session serializer selection

Initial configuration can select `php`, `php_binary` or `php_serialize`. Reassigning the current handler remains allowed. Changing to a different handler during a request is deliberately rejected, including when upload progress is Off. Merely turning progress Off does not establish that it was Off while input was parsed.

If an application calls `ini_set('session.serialize_handler', ...)` or passes a different codec through session-start options, check the effective handler and adapt its configuration. Do not rely only on a function's return value or suppress a warning and assume the codec changed. The bundled benign test checks effective state and ordinary session persistence.

## Out-of-memory handling

The engine backport changes failure propagation and request-state cleanup. Controlled memory-limit failures and final unrecoverable allocation failures have different contracts; not every failure can safely run arbitrary shutdown code or preserve a session. This kit does not promise cleanup after OS termination, process kill or every hard allocation failure.

## Optional ACL/filter variant

These changes apply only to `acl-filter-20261114`; default build007 preparation is unchanged.

- An IPv6 `listen.allowed_clients` entry now matches all 16 address bytes. A neighboring address sharing the first 12 bytes is refused, as demonstrated by the paired FPM A2 test. These entries name individual addresses, not /96 ranges.
- An IPv4-mapped address written as an IPv6 allowlist string, such as `::ffff:127.0.0.1`, also gets a full-address comparison. A different mapped peer no longer passes just because its prefix matches. This detail is supported by source analysis and extracted C checks; the live FPM A3/A4 controls instead use ordinary IPv4 allowlist entries, whose offset 12 / length 4 comparison is unchanged.
- `FILTER_SANITIZE_ENCODED` initializes the entire byte lookup table. When byte `0xFF` reaches the encoder it becomes `%FF`; flags such as `FILTER_FLAG_STRIP_HIGH` can remove it before encoding. Ordinary outputs passed in both real builds. Valgrind, rather than an ordinary-output mismatch, demonstrated the baseline defect.

See the [variant verification and retained evidence](ACL_FILTER_VARIANT.md).

## Optional multipart variant

`multipart-20261114` includes the ACL/filter variant and changes multipart input acceptance. Boundaries above 5116 bytes are rejected before buffer initialization. `max_multipart_body_parts` defaults to `-1`, deriving its budget from `max_input_vars + max_file_uploads` with checked arithmetic; other negative values also derive it. An explicit zero permits no Content-Disposition parts. The setting is SYSTEM/PERDIR and cannot be raised with application `ini_set`.

Every Content-Disposition part consumes the request-local budget, including fields/files that existing limits or disabled uploads would skip. An extra part triggers one warning and parsing stops; already accepted fields/files remain. Review applications that depend on processing more parts than this budget. The limit resets for every request; it does not decrement the configured INI value. Core-globals layout changes require a fresh build, and compatibility with existing external extensions is not inherited. See [actual verification and limits](MULTIPART_VARIANT.md).

## Optional cookie variant

`cookie-20261114` includes the multipart variant and rejects names that gain a `__Host-` or `__Secure-` prefix through normalization. The original registration name is preserved separately, and each actual string assignment key is checked, including indexed names and unmatched-bracket fallback. A forbidden nested key can leave an already-created ordinary parent array empty. The shared function applies the rule to Cookie, GET and POST.

Authentic protected names, ordinary arrays and integer/string key distinctions remain supported. Cookie names are not newly URL-decoded. Cookie values retain existing decoding; NUL-containing values remain values rather than name delimiters. Top-level Cookie duplicates remain first-win and GET/POST duplicates last-win. This validates name provenance, not authentication or cookie Secure/Domain attributes. See [paired runtime evidence and limits](COOKIE_VARIANT.md).

## Unchanged deployment boundary

The kit does not replace CLI system packages, third-party modules, opcache, application code, a database or an entire container. Compiled output contains both CLI and FPM for isolated testing, but the historical operational scope was a single FPM executable. Use an explicit scope for your own rollout.
