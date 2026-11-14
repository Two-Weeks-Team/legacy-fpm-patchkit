# Behavior changes

## Session serializer selection

Initial configuration can select `php`, `php_binary` or `php_serialize`. Reassigning the current handler remains allowed. Changing to a different handler during a request is deliberately rejected, including when upload progress is Off. Merely turning progress Off does not establish that it was Off while input was parsed.

If an application calls `ini_set('session.serialize_handler', ...)` or passes a different codec through session-start options, check the effective handler and adapt its configuration. Do not rely only on a function's return value or suppress a warning and assume the codec changed. The bundled benign test checks effective state and ordinary session persistence.

## Out-of-memory handling

The engine backport changes failure propagation and request-state cleanup. Controlled memory-limit failures and final unrecoverable allocation failures have different contracts; not every failure can safely run arbitrary shutdown code or preserve a session. This kit does not promise cleanup after OS termination, process kill or every hard allocation failure.

## Unchanged deployment boundary

The kit does not replace CLI system packages, third-party modules, opcache, application code, a database or an entire container. Compiled output contains both CLI and FPM for isolated testing, but the historical operational scope was a single FPM executable. Use an explicit scope for your own rollout.
