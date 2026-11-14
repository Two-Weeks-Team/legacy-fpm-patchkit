# Legacy FPM worker-log hardening

## Completed portable file-log verification

[Paired run 43606021097](https://github.com/Two-Weeks-Team/legacy-fpm-patchkit/actions/runs/43606021097), head `896f91a007bd2a9c71e5844c342d6379ee8aca63`, built both full trees and completed **96 actual FPM requests**: 48 synthetic producers and 48 separate barriers. Across 48 repeated trials, the master log's 328 data records matched an independent callback/pipe check, including record boundaries. The candidate retained every payload byte in the documented representation; six parent case/stream combinations reproduced NUL-tail/following-line loss. All 24 FPM instances exited cleanly. Producer PHPT passed per build, as did 36 separate normal checks per build.

[Hashed results](../evidence/fpm-log-portable-20261114.json) and [539 retained raw files](../evidence/fpm-log-20261114/README.md) bind source, binaries, logs, request slices, shutdown tails and cleanup. Known non-root `user` startup notices are retained; no unexpected diagnostics were observed. Default-build Checks 43606021092 passed four jobs and 121 unit tests; it is separate from file-log proof.

The prepared PHP delta changes one file, but that candidate build also regenerated its JSON scanner while the parent did not. Both make logs are retained. Do not describe those compiled trees as differing solely by the FPM delta; use each run's binary hashes.

The subsequent [content-based build correction](BUILDING.md) was verified in run 43607944104: both builds reused the fixed JSON tuple without regeneration, with recorded before/after hashes. The new binaries repeated all 96 requests and 48 log trials with the same behavior as the first run. [Separate records](../evidence/json-generation-portable-20261115.json) preserve that build change; the first run's asymmetric make logs remain intact.

Limits: small synthetic Ubuntu 22.04 portable file-log campaigns; no syslog daemon delivery, Xenial/module/site or production acceptance. The parent's expected-loss list assumes the single-write fixture; other read splits can cause a harness failure. Random-chunk component checks are separate from actual FPM. No whole-advisory credit is added: cumulative accounting stays **7 implemented / 14 mechanism-absent / 45 planned**, default build007 **2 / 14 / 50**.

## Source and reproduction

`fpm-log-20261114` is a fixed child of the complete `cookie-20261114` source.
It addresses legacy NUL log loss in `fpm_stdio_child_said`. It is not the upstream
FLUSH-offset backport or a claim that all CVE-2024-9026 behavior is resolved.
Earlier source variants, the default build driver and their hashes stay frozen.

The single-file PHP delta replaces newline string search with bounded byte search.
The original read/fifo/EAGAIN/EOF, newline consumption and close paths remain in
place. Each line or read fragment is logged in bounded chunks: NUL and ASCII
controls/DEL become lowercase `\xHH`, literal backslash becomes `\\`, and bytes
above ASCII remain unchanged. The escape token is never split between records.
Newlines delimit records rather than being printed as message data. Empty lines
remain empty messages. An incomplete tail is still emitted when the pipe drains
to EAGAIN or closes, and the existing close suffix remains.

Short ordinary printable lines and ordinary pool names have the same wrapper and
contents. Longer lines may produce additional records; concatenating their data
recovers all bytes in the documented representation. Encoded payloads are at most
512 bytes per record and the pool label is at most 128 original bytes plus an
explicit `...` when shortened. This bounds metadata as well as escape expansion
under the unchanged final zlog 1024-byte cap, including its debug header. Pool
names longer than 128 bytes therefore have an observable shortened label.
No heap allocation, FLUSH command recognition, new buffering state or version
protocol is introduced. Input data is never a format string.

```sh
python3 -m patchkit prepare --variant cookie-20261114 --output .work/source-log-parent
python3 -m patchkit prepare --variant fpm-log-20261114 --output .work/source-log
bash scripts/build.sh .work/source-log-parent .work/build-log-parent portable cookie-20261114
bash scripts/build.sh .work/source-log .work/build-log portable fpm-log-20261114
python3 scripts/fpm-log-check.py \
  --parent-cli .work/build-log-parent/php --parent-fpm .work/build-log-parent/php-fpm \
  --parent-source .work/source-log-parent \
  --candidate-cli .work/build-log/php --candidate-fpm .work/build-log/php-fpm \
  --candidate-source .work/source-log --output .work/fpm-log-result
```

The paired Linux runner binds source/variant/build records and both binary hashes.
It creates only owned short temporary directories, Unix sockets and foreground
FPM pools with `catch_workers_output=yes`. Each case sends harmless literal bytes
through `php://stdout` or `php://stderr`. Application response acknowledgments are
separate from worker-to-master log evidence. Requests repeat in the same worker;
conditional log-drain waits and a separate barrier request bind each log slice.
There is a campaign deadline, request/process limits and owned-process cleanup.
Raw responses, input/log bytes, diagnostics and shutdown tails survive failures.
Unexpected warnings, wrong worker/stream, protocol errors, forced cleanup and
unrelated baseline failures cannot count as the expected legacy NUL loss.

The accompanying CLI PHPT checks the binary-safe **producer** contract only and
must pass on both sides. The worker-to-master preservation assertion belongs to
the paired FPM campaign. Existing benign runtime checks run separately, 36 per
side. Neither PHPT producer success nor a component shim is actual FPM acceptance.

The private component test compiles the complete source callback region and the
entire unchanged zlog.c with real nonblocking pipes and a real file sink. Type,
event deletion, quiet-write and syslog-transport adapters are declared explicitly.
A syslog adapter can check the `%s`/NUL-free formatting contract; it does not prove
daemon delivery, remote syslog behavior or transport reliability. Actual syslog
delivery is not a prerequisite for the local file-sink campaign and must remain
marked unrun unless separately observed. Source, component, build, FPM, CI and
production evidence are separate. This command never installs or deploys PHP.
