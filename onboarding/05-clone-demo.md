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

- **Sync is additive — and not git.** Clone never prunes; if a cloud
  file is removed, the local copy is unaffected unless the user
  explicitly invokes a cloud file-delete endpoint. Even though
  `clone`/`push`/`pull` sound like git, the model is different: code
  is represented as files, not line-level diffs. Each experiment is
  meant to be a fully self-contained unit — input datasets in, output
  evals out — joined by structured provenance rather than commit
  graphs.

- **Time and bandwidth.** This stage is heavy: 10–15 minutes typical,
  longer on a slow connection. Checkpoints are ~350MB; episodes and
  manifests add more on top. The command will print a sync-job id and
  periodic file/byte progress while `local_tool` does the work in the
  background — surface that progress to the user so they don't think
  it stalled.

## Allowed commands

**NONE.** This stage is conversation only. The actual clone happens
in Stage 06.

If you find yourself wanting to run `artha clone`, `artha pull`, or
any other command: STOP. You are in the wrong stage. The execution
stage opens only after the user supplies the continue token.

## Success criteria

- You have explained what `artha clone` pulls (code + runs +
  manifests + episodes + checkpoints), in your own words.
- You have walked through the artha.bot data model (projects → runs
  → manifests/episodes) so the user knows what they're about to see
  in `local_tool`.
- You have set expectations on time (10–15 min) and size (~350MB
  checkpoints plus episodes and manifests).
- You have flagged the additive-sync, not-git property, and what
  that implies for how experiments are structured (self-contained
  units joined by provenance, not commits).
- The user is ready to proceed.

## Continue token

The user must type, EXACTLY, in their next message:

    continue

Vague confirmations DO NOT count.

## Next file

Once the token is received, open `onboarding/06-clone-demo-run.md`. Do
NOT open it before.
