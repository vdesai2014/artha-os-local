# Stage 00 — Intro (Narration Only)

## Goal

Tell the user what artha-os is, why it exists, and what's about to
happen. Get explicit permission to do the demo and confirm where
artha-os should live on their machine.

## Required narration

Explain in plain language, in chat, with concrete examples. Keep it
high-level — the user does not need every architectural detail yet.

- **What artha-os is.** An agent-first robot learning platform —
  local runtime plus cloud sync to artha.bot. The agent (you) does
  the plumbing while the user focuses on the experiment.

- **Why it exists.** Robot learning is half OS-level data plumbing
  and half model training. Four pain points keep biting:
  1. **High-rate, typed data movement.** Cameras, joints, robot
     commands at tens-to-hundreds of Hz, with primitives that make
     adding a new sensor or policy a one-file change.
  2. **Experiment lineage.** Every run, episode, and checkpoint
     traceable back to its source — no orphan checkpoints, no
     "which dataset trained this?" mysteries.
  3. **Cloud round-trips.** Push to artha.bot, train on cloud GPUs,
     pull checkpoints back — additively and traceably.
  4. **Plumbing dominates.** Most robot-learning time goes to glue
     code; artha-os makes the agent do that part so the user can
     focus on the science.

- **What's on offer (the demo).** A real grasp-pickup research
  project hosted on artha.bot — not a fixture. It contains a ladder
  of trained policies; we'll run two of them. First, a deliberately-
  weak imitation-learning baseline (it will fail; that's the point).
  Then, swap to a much-better ACT+PPO policy that should succeed.
  The user will see both evals side-by-side in their own datasets,
  with full lineage to the runs that produced them. Total ~20–30
  minutes of agent work plus a few minutes of clicking.

- **Where to drop it.** Default is the current artha-os checkout
  directory — pip editable install, node_modules, cargo target, and
  the demo workspace all land here. Confirm with the user.

## Mandatory checklist — before requesting `continue`

You MUST have said all of the following, in chat, in your own
words. Before asking the user for the token, mentally walk through
every bracketed item; if any is unchecked, narrate the missing item
now and only THEN ask.

- [ ] Said what artha-os IS in plain language (1–2 sentences,
       agent-first robot learning platform, local runtime + cloud
       sync).
- [ ] Named all four pain points (high-rate data, lineage, cloud
       round-trips, plumbing).
- [ ] Described what's on offer: real research project on artha.bot,
       ladder of policies, two will be run (one fails on purpose,
       one succeeds), in-browser eval, ~20–30 min total.
- [ ] Asked the user for permission to proceed AND confirmed the
       install location.

If any item is unchecked, you have not completed this stage. Do NOT
request the continue token.

## Allowed commands

**NONE.** This stage is conversation only.

## Continue token

The user must type, EXACTLY, in their next message:

    continue

Vague confirmations DO NOT count.

## Next file

Once the token is received, open `onboarding/01-prepare.md`. Do NOT
open it before.
