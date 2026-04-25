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

### Frontend sync UI still uses blocking push/pull calls

**Context:** The backend now supports sync jobs:
`POST /api/sync/jobs`, `GET /api/sync/jobs`, and
`GET /api/sync/jobs/{id}`. The CLI uses this path and prints job/file/byte
progress. The old `/api/sync/execute` path remains for direct/blocking
clients.

**Remaining symptom:** frontend project sync still calls the older blocking
project sync route and shows a spinner without file-level status.

**Fix direction:**
- Route frontend push/pull/clone actions through `/api/sync/jobs`.
- Add a small sync jobs panel that lists recent jobs from
  `.artha/run/sync/<job_id>.json`.
- Optional later: add cooperative cancellation via an explicit
  `/api/sync/jobs/{id}/cancel` endpoint. Ctrl-C in the CLI currently stops
  polling only; it does not stop the background job.

**Location:** `frontend/src/features/projects/` +
`local_tool/server/routes/sync.py`.

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
