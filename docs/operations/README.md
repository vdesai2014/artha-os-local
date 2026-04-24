# Operations

Utilitarian how-to guides. Terse, executable, one page max each.

These answer **"how do I get X done"** — the *why* lives in
`docs/concepts/`.

## Available

- [`add-service.md`](add-service.md) — generic pattern for adding any
  supervisor-managed service (Python or Rust)
- [`add-robot.md`](add-robot.md) — wiring a new robot: HAL + safety +
  commander + recorder + frontend, with per-layer coupon tests
- [`modify-frontend.md`](modify-frontend.md) — React/Vite layout, hook
  surface (`useTopic`, `useNatsSubject`, `usePublish`, `natsRequest`),
  dev loop, overlay convention

## Deferred until we actually hit them

These are candidates whose shape we'll know better after real usage.
Write them when the agent accumulates recurring questions, not in
advance.

- `add-camera.md` — specialized case of add-service; one-page after
  we've done it a second time for real
- `troubleshooting.md` — write when symptom patterns emerge from use
- `replicate-experiment.md` — clone-and-run someone else's project;
  mostly covered by `onboarding-steps.md` + AGENTS.md common-flows
- `cloud-collab.md` — multi-user manifest sharing, once the workflow
  stabilizes

If you're here looking for one of the deferred pages and the answer
isn't obvious from the existing concepts + available operations docs,
that's the signal to write it.
