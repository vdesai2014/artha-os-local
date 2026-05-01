# Stage 00 — Intro (Narration Only)

## Goal

Tell the user what artha-os is, why it exists, and what's about to
happen. Get explicit permission to do the demo and confirm where
artha-os should live on their machine.

## Required narration

Explain in plain language, in chat, with concrete examples. Keep it
high-level — the user does not need every architectural detail yet.

- **What artha-os is, and why.** Robot learning is dominated by data
  movement and the glue code that holds it together: high-rate
  streams between sim, sensors, and policies (local); large datasets
  and checkpoints round-tripping to cloud GPUs (cloud); and event
  handling, provenance tracking, and restart logic between them
  (glue). That muck is where a lot of the time goes. artha-os
  simplifies all three: typed shared memory (iceoryx2) for the
  local data plane, `push`/`pull`/`clone` via artha.bot for the
  cloud round-trip, and NATS + a small supervisor + a file-based
  local store for the glue. Tight vertical integration means adding
  a sensor, swapping a policy, or pushing eval data is a one-file
  or one-command change.

- **Why it's agent-first.** A coding agent handles the muck for
  the user: wires the data plumbing, registers provenance,
  replicates code and data to and from the cloud. This allows for
  users to focus on the experiment instead of ancillary logic.

- **What's on offer.** A sample project on artha.bot — a simulated
  robot doing block grasping in MuJoCo, with pre-trained policies.
  The agent will install the runtime, pull the project, and walk
  you through running two policies: a deliberately-weak one that
  fails on purpose, then a strong one that succeeds. The point is
  to see the data-movement and glue automation in action, end to
  end. ~20–30 min total.

- **If anything breaks or feels stuck along the way.** Tell me.
  With your okay, I'll file the issue as feedback to the team
  via the cloud feedback endpoint so they can see what tripped
  us up. No silent failures, no need for you to dig up a GitHub
  link.

- **Permission to proceed?** Confirm, and confirm the default
  install location (current artha-os checkout dir).

## Mandatory checklist — before requesting `continue`

You MUST have said all of the following, in chat, in your own
words. Before asking the user for the token, mentally walk through
every bracketed item; if any is unchecked, narrate the missing item
now and only THEN ask.

- [ ] Said what artha-os IS, framed around the three muck areas it
       simplifies (local data movement, cloud round-trip, glue
       between them), naming the underlying primitives (iceoryx2
       SHM, NATS events, supervisor, file-based local store,
       `push`/`pull`/`clone`).
- [ ] Said why it's agent-first — a coding agent wires plumbing,
       registers provenance, and replicates code/data between local
       and cloud, so the user can focus on the experiment.
- [ ] Described what's on offer: a sample project on artha.bot, a
       simulated robot in MuJoCo, two policies (one fails on
       purpose, one succeeds), in-browser eval, ~20–30 min total.
- [ ] Mentioned that if anything breaks or the user gets stuck
       along the way, the agent will offer to file feedback for
       them (with their okay) — see "Filing feedback (any stage)"
       in `onboard.md` for the curl shape.
- [ ] Asked permission to proceed AND confirmed install location.

If any item is unchecked, you have not completed this stage. Do NOT
request the continue token.

## Allowed commands

**NONE within this stage's flow.** The single exception across
all narration stages: the `curl POST /api/feedback` documented
under "Filing feedback (any stage)" in `onboard.md`. Use it only
with explicit user permission.

## Continue token

The user must type, EXACTLY, in their next message:

    continue

Vague confirmations DO NOT count.

## Next file

Once the token is received, open `onboarding/01-prepare.md`. Do NOT
open it before.
