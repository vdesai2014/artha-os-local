# Supervisor

## Model

The supervisor is the parent process for every service in `services.yaml`.
Each service runs under `supervisor/wrapper.py` — a thin child that owns
one subprocess and reports its lifecycle state via a JSON file.

```
supervisor           (pid S,    session_id SID)
├── wrapper(sim)           → child sim process
├── wrapper(bridge)        → child bridge process
├── wrapper(data_recorder) → child data_recorder process
└── ...
```

Runtime state lives under `.artha/run/`:

```
.artha/run/
  supervisor.json                 # supervisor's own state + lease heartbeat
  services/
    sim.json                      # wrapper(sim)'s state + heartbeat
    bridge.json
    ...
```

## The session lease

On startup the supervisor mints a fresh `session_id` and writes it to
`supervisor.json` alongside a `heartbeat_at` timestamp refreshed every 1s.

Each wrapper polls `supervisor.json` every 0.5s. The wrapper stops its
child and exits with code 75 (`lease_invalid`) when any of:

- the file disappears
- the `session_id` changed (fresh supervisor started)
- `heartbeat_at` is older than `lease_timeout_s` (default 3s)

Net effect: `kill -9` on the supervisor takes every service down within
~3 seconds. No orphan processes survive a crash.

## Wrapper heartbeat

Each wrapper writes `services/<name>.json` with `heartbeat_at` refreshed
every 2s. This is the filesystem-based liveness signal the CLI's
`status` command consumes — works even when NATS is down.

Cadences:

| Writer | Cadence | Consumer |
|--------|---------|----------|
| supervisor | 1s | wrappers checking lease (stale after 3s) |
| wrapper | 2s | CLI status (stale after ~5s) |

## Restart semantics

- **Crash within 5s of start:** treated as a repeat crash; exponential
  backoff (`2^n` seconds, capped at 30s).
- **Crash after 5s of uptime:** counter resets; next start uses short
  backoff.
- **`services.yaml` re-read on each restart.** Edit between crashes and the
  new env / cmd applies on the next spawn. No supervisor restart needed for
  most config changes — only for changing the set of services.

## Liveness probes per tier

Don't force one uniform probe. Each tier has its own right-shaped check:

| Component | Probe | Fails independently? |
|-----------|-------|----------------------|
| `local_tool` backend | `GET /api/health` | yes |
| NATS | connect attempt to `nats://localhost:4222` | yes |
| supervisor | `supervisor.json` fresh + pid alive w/ matching start-ticks | yes |
| service | `services/<name>.json` fresh + child pid alive w/ matching start-ticks | yes |

Start-ticks come from `/proc/<pid>/stat` field 22 (procfs). Storing ticks
alongside pid defeats pid reuse — a new process with the same pid gets a
different start-tick value.

`core/supervision.py` exposes `probe_supervisor()` and `probe_service()`
returning a structured `{alive, reason, payload}` dict. The CLI aggregates
them for one-shot `artha status`.

## Type check at boot

Before launching services, the supervisor runs `<binary> --type-check` for
every service entry with `type_check: true` and parses the stdout layout
dump. It refuses to start if any Rust struct disagrees with the matching
Python `ctypes.Structure` in `core/types.py`. See `concepts/ipc.md` for
why this matters (segfaults on mismatch).
