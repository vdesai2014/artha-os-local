# Stage 11 — Swap To ACT+PPO (Narration Only)

## Goal

Pay off the research arc the user has been building toward since
Stage 05. They just watched the bottom rung (imitation learning)
fail. Now we explain what's about to replace it and why it works,
so the upcoming success isn't just a number — it's the gap that
several architecture iterations closed.

This stage is conversation ONLY. The actual `services.yaml` swap,
new provenance registration, restart, and browser eval happen in
Stage 12. Do NOT skip ahead.

## Required narration

Walk the user through the following, in your own words. The user
just experienced failure — keep momentum, make the contrast feel
earned.

- **What's about to happen mechanically.** Stage 12 will edit
  `services.yaml` to swap `imitation_learning_inference` for an
  `act_ppo_inference` service pointing at a different run, then
  register a new eval provenance manifest, then `artha up --force`
  to restart with the new topology. Same wiring (state + cameras
  in, command predictions out), same `data_recorder`, same
  frontend. Only the policy weights and its driver script change.
  This is also how the user would A/B any future policy in their
  own project: edit one yaml entry, set new provenance, restart.

- **What ACT+PPO is, architecturally.** The top rung of the ladder.
  Three things change relative to the IL baseline:
  1. **Action chunking** — the policy predicts a chunk of 50 future
     actions at once, not one. That alone lets it commit to a
     coherent grasp trajectory instead of averaging across phases.
  2. **Transformer backbone (ACT)** — instead of a CNN+MLP, it's a
     small transformer that attends across the camera tokens and
     temporal context. Better suited to multi-modal, multi-phase
     manipulation.
  3. **Residual PPO on top** — once ACT was trained via behavior
     cloning, a PPO layer was bolted on and trained in simulation
     against task reward. PPO outputs a *correction* to ACT's chunk,
     not a replacement. So the final policy is `ACT(state) + δ(state)`,
     where δ is the RL-trained nudge toward grasping success.

- **Why it works where IL failed.** Same sim, same task, same input
  modalities, same training data ultimately. The IL baseline scored
  0/20 because it averaged across grasp phases; ACT+PPO scores ~98%
  (62/63 latest, 100% best) because chunking makes it commit, the
  transformer gives it the right inductive bias for multi-camera
  manipulation, and PPO closes the gap that pure imitation can't.
  This is the gap the architectural ladder bought — exactly the
  research arc previewed in the Stage 05 sidebar, made concrete by
  the contrast you just earned.

- **What the user will do next.** After Stage 12 runs the swap,
  they'll click `start-eval` again in the frontend. The robot will
  reach, close the gripper at the right moment, and lift the block.
  The eval auto-ends on success (or 20s timeout). The Datasets page
  will then show a SECOND episode under a new manifest
  (`eval-act-ppo-grasp-pickup`), with lineage to the
  `act-ppo-dense-affine` training run. Tell them: same project,
  two evals, two runs, queryable side by side — that's the artha-os
  data-model promise from Stage 05 paying off in their local store.

## Allowed commands

**NONE.** This stage is conversation only. The actual swap and
re-eval happen in Stage 12.

If you find yourself wanting to edit `services.yaml`, set
provenance, restart anything, or run any command: STOP. You are in
the wrong stage.

## Success criteria

- You have explained, in your own words, what changes architecturally
  in ACT+PPO vs IL — the three rungs (chunking, transformer, PPO
  residual).
- You have explicitly tied the failure-to-success contrast to the
  architectural ladder rather than to "more training" or "magic".
  Same task, same inputs, same data — just better architecture.
- The user has heard what to expect in the next browser eval (success
  this time, auto-end, second episode in Datasets, lineage to the
  ACT+PPO run).
- The user understands the mechanic generalizes: future A/B testing
  of policies in their own work is one yaml edit + new provenance +
  restart.
- The user is ready to proceed.

## Continue token

The user must type, EXACTLY, in their next message:

    continue

Vague confirmations DO NOT count.

## Next file

Once the token is received, open `onboarding/12-swap-good-run.md`.
Do NOT open it before. Note: `12-swap-good-run.md` does not yet
exist in this checkout — if the file is missing, tell the user the
next stage is not yet authored and stop. Do not improvise the next
stage.
