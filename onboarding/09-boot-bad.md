# Stage 09 — Run The IL Baseline (Narration Only)

## Goal

Prepare the user for the bad-policy run. They need to know: (a) what
the imitation learning baseline is and why it fails, so they
recognize it's intentional and not a bug; (b) how to stop the eval
manually when the robot gets stuck; (c) how to trace the eval back
to its source training run on the Datasets page.

This stage is conversation ONLY. The actual `artha up --force`,
provenance registration, and browser eval happen in Stage 10. Do
NOT skip ahead.

## Required narration

Walk the user through the following, in your own words. Set
expectations clearly — this is the eval where the robot will appear
broken, and the user needs to know that's the point.

- **Booting the demo runtime.** Stage 10 will run `artha up --force`
  to bring up the topology you just wired in Stage 08 — sim,
  recorder, video_bridge, eval_runner, commander, and the IL
  inference service. The agent will then register provenance over
  NATS so eval episodes get tagged back to the IL training run.
  The user has already seen base runtime boot in Stage 04, so this
  is a quick mention — the interesting story is the eval itself.

- **What's about to fail, and why.** The imitation learning
  baseline is the bottom rung of the architectural ladder we
  previewed in Stage 05. It's a small CNN+MLP that takes the
  gripper camera, overhead camera, and current joint positions, and
  predicts ONE 7-DOF action for the next instant — no memory of
  past frames, no lookahead, no chunking. The grasp task has phases
  (approach, close, lift), and a single-step policy averages across
  them without committing to any. The user will see the robot start
  moving, hesitate, drift, and fail to close the gripper at the
  right moment. This is the project's published 0/20 imitation-
  learning success rate; it is not a bug.

- **What the user needs to do.** When the robot is clearly stuck
  (drifting, oscillating, never closing the gripper), tell them to
  hit the **STOP** button in the frontend. Don't let the eval run
  forever waiting for a non-existent success. After they stop, walk
  them to the **Datasets** page — the eval just ran is there as a
  new episode. Tell them to click `Run` in the bottom-right of the
  episode card; that link points back to the imitation-learning
  training run that produced this checkpoint, materialized locally
  by the clone in Stage 06. That's the agentic NATS provenance
  paying off — every eval is traceable to the run that produced it.
  They can thumbs-down the eval to mark it as a failure for future
  analysis.

- **Why we're showing this first.** Contrast. Without seeing this
  policy fail, the next policy's success is just a number. With it,
  the user will see the gap that several architecture iterations
  closed. The next stage swaps in a much stronger policy and re-runs
  the same eval — same task, same inputs, different architecture.

## Allowed commands

**NONE.** This stage is conversation only. The actual boot,
provenance registration, and browser eval happen in Stage 10.

If you find yourself wanting to run `artha up`, set provenance, or
touch the runtime in any way: STOP. You are in the wrong stage.

## Success criteria

- You have explained, in your own words, what the IL policy is
  architecturally (CNN+MLP, single-step, no memory) and why it
  fails on the grasp task (averages across phases instead of
  committing).
- The user knows they need to manually hit STOP when the robot is
  stuck — they will not wait for an auto-end.
- The user knows the post-eval flow: Datasets page → click `Run`
  in the episode card → see the lineage back to the IL training
  run → thumbs-down to mark as failure.
- The user understands this is the bottom rung of the ladder and
  that we are deliberately running a weak policy first to make the
  contrast with the good policy visible.
- The user is ready to proceed.

## Continue token

The user must type, EXACTLY, in their next message:

    continue

Vague confirmations DO NOT count.

## Next file

Once the token is received, open `onboarding/10-boot-bad-run.md`.
Do NOT open it before.
