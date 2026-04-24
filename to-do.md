# artha-os to-do

Clean lean rev of the OS. Working list of decisions, refactors, and carryover
issues from `local-artha-rev5`.

## Carryover bugs / coordination needed

### Manifest `source_run_id` ↔ `associated_runs` drift

**Context:** `local-artha-rev5` migrated manifests from a single
`source_run_id` to `associated_runs: list[AssociatedRun]` (see
`tools/migrate_workspace_schema.py`). The cloud API was not migrated in
lockstep — it still expects `source_run_id`.

**Symptom in rev5:** `LocalManifest.source_run_id` was referenced in three
places that would have raised `AttributeError` at runtime
(`cloud_portal.ensure_manifest`, `plan._append_pull_linked_manifest_actions`,
`exec._execute_pull_plan` manifest branches). Rev5 now translates at the
boundary (`associated_runs[0].run_id` on push; wraps `source_run_id` into a
single `associated_runs` entry on pull), but this loses the multi-run
information on every cloud round trip.

**Decision needed for artha-os:**
- Option A: cloud adopts `associated_runs` (multi-run parity with local).
  Coordinated schema + migration on the cloud side.
- Option B: local reverts to single `source_run_id`; we accept that a
  manifest can only be associated with one source run.
- Option C: keep both, but make the translation explicit and bidirectional,
  with a clear ownership rule (which side is source of truth when they
  diverge).

**Action:** pick one before any sync code lands in artha-os. Don't ship the
boundary-translation shim — it's a band-aid, not a design.

### `data_recorder` doesn't couple to the slowest writer

**Context:** The recorder ticks at `LOOP_RATE_HZ` and, on each tick, appends
the latest-cached value of every source to its buffer. If a source is slower
than the loop (e.g. camera at 30 Hz while the loop runs at 30 Hz but drifts
a hair faster, or obs at 50 Hz with camera at 30 Hz), the same frame gets
duplicated into the buffer — parquet columns and video silently
desynchronize step-by-step.

**Symptom in rev5 and the ported version:** episodes that look fine in
length/shape but have doubled observations or skipped ones depending on the
relative rates. No error, no warning.

**Fix (owed):**
- Tick at the rate of the slowest source (or run a pull loop per source and
  gate on all-advanced).
- Only append to buffers when every source's `frame_id` has changed since
  the last append.
- Bonus: warn at boot if the advertised `LOOP_RATE_HZ` exceeds what any
  source is publishing.

**Location:** `services/data_recorder/main.py` — the main loop's "Append if
recording" block. See the `KNOWN ISSUE` note in the module docstring.

### Clone mints IDs in both `/plan` and `/execute`, giving different remaps

**Context:** `_build_project_clone_plan` calls `generate_id("proj")` and
`generate_id("run")` while building the plan. `POST /api/sync/plan` and
`POST /api/sync/execute` each re-run `plan_sync` internally, so every call
produces a fresh UUID set. An agent that plans, inspects `id_remaps`, then
executes, gets *different* final IDs than the ones it previewed.

**Symptom:** dogfood run on 2026-04-21 — plan returned
`proj_a8a097ef…`; execute returned `proj_882ddfae…`. Only /execute's
remap is usable for downstream file rewrites.

**Fix direction (preferred):** move target-ID minting out of
`_build_project_clone_plan` and into `_execute_clone_plan`. Clone's plan
becomes a true preview (source scope + "N IDs will be remapped at exec"
structure), and the execute result is the single authoritative source of
`id_remaps`. No server-side plan caching, no round-tripping of large
plan bodies. Push/pull are unaffected — their IDs are source IDs,
stable across re-plans.

**Location:** `local_tool/sync/plan.py::_build_project_clone_plan` and
`local_tool/sync/exec.py::_execute_clone_plan`.

### Sync operations (push/pull/clone) have no progress tracking

**Context:** `/api/sync/execute` is a single long-lived HTTP request. A
743 MB clone took 12m19s with zero intermediate feedback — clients,
frontends, and agents all block with no visible progress. Same for big
pushes.

**Symptom:** frontend spinner turns infinitely; agents have no way to
distinguish "still downloading" from "hung"; no way to cancel partway
through.

**Fix direction options:**
- Server-sent events / chunked HTTP on `/api/sync/execute` streaming
  per-file progress.
- Split into `/api/sync/jobs` (POST starts job, returns `job_id`) +
  `/api/sync/jobs/{id}` (GET polls status/progress) + optional
  WebSocket stream for live updates.
- CLI-side progress bar (tqdm or similar) that wraps the Python sync
  entrypoints directly — skips HTTP altogether for local use.

**Location:** `local_tool/sync/exec.py` + `local_tool/server/routes/sync.py`.

### macOS: `process_start_ticks` returns None — lose PID-reuse defense

**Context:** `supervisor/platform/posix.py::process_start_ticks` reads
`/proc/<pid>/stat` field 22. macOS has no `/proc`, so the function
returns None. `_probe_process` in `core/supervision.py` already
degrades gracefully (treats None as "trust pid_is_alive"), so liveness
checks still work — but we lose the defense against a dead process's
PID getting reassigned to an unrelated process between state-file
writes and reads.

**Symptom:** low-probability false positives in `artha status` when a
supervisor crashed days ago and the OS has recycled its PID to
something else. `pid_is_alive` says "yes" for the new unrelated
process.

**Fix direction options:**
- Add `psutil` as a dependency; use `Process(pid).create_time()` which
  is cross-platform and returns epoch seconds. Cleanest, ~500KB dep.
- Write a `DarwinPlatformAdapter` that shells out to `ps -o lstart -p
  <pid>` and parses the timestamp. No new deps, uglier parsing.
- Leave it. Practical impact is limited to stale state files across
  reboots on macOS.

**Feedback needed:** requires a macOS machine to reproduce and
validate any fix end-to-end. Without the loop we can't confirm the
adapter actually works.

**Location:** `supervisor/platform/posix.py::process_start_ticks`.

## Open (unscheduled)

- (add items here)
