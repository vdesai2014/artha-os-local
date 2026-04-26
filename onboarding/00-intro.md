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
  and half model training. Four pain points keep biting; explain
  each one as a *problem*, then say in one sentence how artha-os
  or artha.bot addresses it:
  1. **High-rate typed data, plus events.** Robots need two
     kinds of plumbing: high-rate typed transport for streams
     like cameras, joint state, and motor commands (tens-to-
     hundreds of Hz), and lightweight events for things like
     data-recorder start/stop, parameter changes, and eval
     triggers. Both surfaces need to change often as the setup
     evolves. → artha-os builds on iceoryx2 (typed shared memory)
     and NATS (events), with a quick easy install, so a coding
     agent can wire new sensors, services, or eval triggers in
     minutes.
  2. **Experiment lineage.** After weeks of iteration, tracking
     "which dataset trained which model that produced this
     eval?" gets messy and hard to keep straight. → artha-os
     records every link automatically — code, data, run, episode,
     checkpoint — and artha.bot is where lineage gets shared and
     pushed back.
  3. **Cloud round-trips.** Big training needs cloud GPUs; data
     and checkpoints have to travel both ways without flattening.
     → `artha push`/`pull`/`clone` move code, datasets, and
     checkpoints between local and artha.bot — additively,
     traceably.
  4. **Plumbing dominates.** Glue code (socket reconnects, format
     mismatches, restarts, provenance bookkeeping) eats a lot of
     robot-learning time. → artha-os is small, file-based, and
     inspectable enough that a coding agent (you) does that
     plumbing while the user focuses on the experiment.

- **What's on offer (the demo).** A grasp-pickup robot manipulation
  research project hosted on artha.bot — real research, not a
  tutorial fixture. The agent will pull it down and run it on the
  user's machine in a **MuJoCo physics simulation** (no real robot
  hardware needed; everything is simulated, locally). The user will
  compare two of the project's trained policies in a browser:
  first a deliberately-weak imitation-learning baseline (it will
  fail; that's the point), then a much-better ACT+PPO policy that
  should succeed. Both evals end up side-by-side in the user's own
  local datasets, with full lineage to the runs that produced them.
  Total ~20–30 minutes of agent work plus a few minutes of
  clicking.

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
- [ ] Named all four pain points (high-rate data + events,
       lineage, cloud round-trips, plumbing) AND said in one
       sentence how artha-os or artha.bot addresses each.
- [ ] Described what's on offer: real research project on
       artha.bot, runs locally in a MuJoCo physics simulation (no
       real robot hardware needed), two policies will be compared
       (one fails on purpose, one succeeds), in-browser eval, ~20–
       30 min total.
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
