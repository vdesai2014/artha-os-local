# Stage 00 — Orient

## Goal

Get the user's informed buy-in on running the demo, and confirm the
install location, WITHOUT installing anything.

## Required narration

Explain the following in your own words, in chat, with concrete examples
(do not paraphrase, do not just recite the bullets):

- **What artha-os is.** An agent-first robot learning platform — local
  NATS + supervisor + frontend + file-based store, with cloud sync to
  artha.bot for code, datasets, and checkpoints. The runtime is
  intentionally small, file-based, and inspectable so the agent (you)
  can do the plumbing while the user focuses on the experiment.

- **Why it exists.** Robot learning is half OS-level data plumbing and
  half model training. Four pain points keep biting:

  1. **High-rate, typed data movement that's fast to iterate on.**
     Robots push dozens of streams (cameras, joints, torque, contact)
     at tens-to-hundreds of Hz; controllers publish back at 100Hz+.
     artha-os uses typed shared memory + a small supervisor so adding
     a sensor, swapping a model, or wiring a new controller is a
     struct definition plus a `services.yaml` entry — not a transport
     rewrite.
  2. **Experiment lineage.** Robot learning is a ladder of experiments.
     After weeks of iteration, "which dataset trained which model
     produced this eval?" only has an answer if every link — code,
     data, run, episode — is recorded with structured provenance.
  3. **Cloud round-trips.** Robots produce more data than fits on a
     laptop; bigger models need cloud GPUs. `push`/`pull`/`clone` move
     code, datasets, and checkpoints between local and artha.bot,
     additively and traceably.
  4. **Plumbing dominates.** Most robot-learning time goes to gluing
     services, debugging socket reconnects, and re-deriving which
     checkpoint trained on which data. Researchers want time on the
     science.

- **What's on offer.** A canonical MuJoCo grasp-pickup demo on
  artha.bot, pulled fresh and run end-to-end in the browser — the
  fastest way to see all four pain points solved together. The arc:
  - Install Python + Node + NATS + Rust deps (~10–15 min fresh).
  - Boot the base runtime; confirm frontend loads.
  - Clone the grasp-pickup project from artha.bot (~10–15 min;
    multi-gigabyte checkpoint downloads).
  - Wire its sim, inference, recorder, and UI into the runtime.
  - Click eval/start; watch the arm grasp a block.

- **Where to drop it.** Ask the user where they want artha-os installed.
  Default: the current checkout dir. Confirm — pip editable install,
  node_modules, cargo target, and the demo workspace all land here.

## Allowed commands

NONE. This stage is conversation only.

## Success criteria

- You have explained artha-os and the four pain points in your own
  words, with concrete examples.
- The user has affirmatively chosen to run the demo.
- The user has confirmed the install location.

## Continue token

The user must type, EXACTLY, in their next message:

    continue

Vague confirmations ("yes", "sounds good", "go", "yee") DO NOT count.

## Next file

Once the token is received, open `onboarding/01-install.md`. Do NOT
open it before.
