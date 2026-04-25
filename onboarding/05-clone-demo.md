# Stage 05 — Clone The Demo (Narration Only)

## Goal

Walk the user through what `artha clone` is about to do — the cloud →
local hop that pulls the grasp-pickup demo into their local store.

This stage is conversation ONLY. The actual `artha clone` happens in
Stage 06. Do NOT skip ahead.

## Required narration

Explain the following in your own words, in chat, with concrete
examples (do not paraphrase, do not just recite):

- **What `artha clone` actually pulls.** Not just code — the entire
  grasp-pickup project: code, runs, manifests, episodes, and
  checkpoints. The demo is a real research project hosted on
  artha.bot, not a fixture, and we are materializing it on the user's
  machine with full lineage intact. This is the "pull" half of the
  cloud round-trip pain point from Stage 00.

- **The artha.bot data model.** The clone reveals how artha-os
  organizes work — surface it to the user so they can find their way
  around `local_tool` afterward:
  - **Projects** contain runs.
  - **Runs** contain manifests, episodes, and checkpoints.
  - **Manifests** are typed dataset descriptors (column schemas, video
    schemas, fps, source provenance).
  - **Episodes** are individual recorded runs of the policy or human
    teleop.
  - **Checkpoints** are the model weights produced by training runs.
  Everything comes down with full lineage — no flattening.

- **What `artha clone` outputs.** A JSON file at
  `/tmp/artha-grasp-clone.json` containing `id_remaps` — a mapping
  from cloud project/run/manifest/episode/checkpoint IDs to fresh
  local IDs. This file is the **source of truth** for the rest of the
  walkthrough. Stage 06 saves it; later stages read it to wire the
  right run and checkpoint into `services.yaml`.

- **Sync is additive.** Clone never prunes. If a cloud file is
  removed, the local copy is unaffected unless the user explicitly
  invokes a cloud file-delete endpoint. This is a deliberate safety
  property — `clone`/`push`/`pull` are designed so accidents don't
  cascade.

- **Time and bandwidth.** This stage is heavy: 10–15 minutes typical,
  longer on a slow connection. Checkpoints are multi-gigabyte. The
  command will print a sync-job id and periodic file/byte progress
  while `local_tool` does the work in the background — surface that
  progress to the user so they don't think it stalled.

- **Why we'll bring the runtime down immediately after.** Once clone
  finishes, Stage 06 will also run `artha down`. We need the
  supervisor and bridge stopped before later stages edit
  `services.yaml`, so the running services don't compete with the
  edits.

## Allowed commands

**NONE.** This stage is conversation only. The actual clone happens
in Stage 06.

If you find yourself wanting to run `artha clone`, `artha pull`, or
any other command: STOP. You are in the wrong stage. The execution
stage opens only after the user supplies the continue token.

## Success criteria

- You have explained what `artha clone` pulls (code + runs +
  manifests + episodes + checkpoints with full lineage), in your
  own words.
- You have walked through the artha.bot data model (projects → runs
  → manifests/episodes/checkpoints) so the user knows what they're
  about to see in `local_tool`.
- You have set expectations on time (10–15 min, multi-gig checkpoints)
  and on the JSON output file as session source-of-truth.
- You have flagged the additive-sync safety property and the
  immediate-after `artha down` so the user isn't surprised.
- The user is ready to proceed.

## Continue token

The user must type, EXACTLY, in their next message:

    continue

Vague confirmations DO NOT count.

## Next file

Once the token is received, open `onboarding/06-clone-demo-run.md`. Do
NOT open it before. Note: `06-clone-demo-run.md` does not yet exist in
this checkout — if the file is missing, tell the user the next stage
is not yet authored and stop. Do not improvise the next stage.
