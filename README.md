# artha-os-local

The local runtime for [artha.bot](https://artha.bot) — an agent-first
operating system for robot manipulation learning.

Real-time services (SHM + NATS) under a lease-based supervisor, a local
FastAPI store with push/pull/clone to the cloud, a React frontend, and
an `artha` CLI. Meant to be read, hacked, and extended by the user's
coding agent.

## Start here

- **[`AGENTS.md`](AGENTS.md)** — if you're a coding agent, read this
  first.
- **[`docs/onboarding-steps.md`](docs/onboarding-steps.md)** — one-page
  bootstrap for a fresh machine.
- **[`docs/concepts/`](docs/concepts/)** — *why* the system is shaped
  the way it is (IPC tiers, supervisor lease, cloud model, etc.)
- **[`docs/operations/`](docs/operations/)** — *how* to extend it (add
  a service, add a robot, modify the frontend).

## CLI sketch

```
artha up / down / status
artha restart <service>      artha logs <name> [-f]
artha peek <topic>           artha camera <topic>
artha push / pull / clone    artha provenance {set,get,clear}
artha nats {pub,req}
```

Install from repo root: `pip install -e .`

## License

(TBD)
