# Stage 07 — Wire Demo Services (Narration Only)

## Goal

Tell the system-level story of what we're about to add to the running
program: the demo project's inference service, the data recorder
hooked to sim sources, agentic provenance set over NATS, and the
frontend ↔ NATS event surface that makes the eval clickable in the
browser. This is the user's first time seeing inference, the
recorder, agentic provenance, and NATS used together in the live
runtime.

This stage is conversation ONLY. The actual yaml + python edits
happen in Stage 08. Do NOT skip ahead.

## Required narration

Three beats, in your own words. Don't dive into file-edit mechanics
— those belong to the execute stage. Focus on what each addition
does in the running system, and why the pattern generalizes:

1. **Inference is attached as a service.** The grasp-pickup project
   came down with the clone, including multiple trained policies
   along the architectural ladder previewed in Stage 05 (imitation
   learning → action chunking → ACT → ACT+PPO). We're starting at
   the bottom rung — an **imitation learning baseline** — and
   registering its inference script as a service in `services.yaml`,
   with declared IPC pubs and subs. When the supervisor comes back
   up, that inference process will subscribe to sim state and camera
   frames over typed shared memory and publish action predictions on
   its own topic. The same mechanic — declare a service, declare
   its pubs/subs — is how the user wires any future policy or
   sensor into the runtime, and is also how we will swap to a
   stronger policy a few stages from now. (We are deliberately
   starting with the weak one; you will see why in Stage 09.)

2. **Provenance is registered agentically over NATS.** Among the
   services we're adding is `data_recorder` — it subscribes to sim
   state, commands, and policy cameras, and writes every eval
   episode as typed dataset rows plus videos. Once the services
   are running, the agent (you) uses NATS to register provenance
   for those episodes, tying them to the specific run and
   checkpoint that produced them. Make the user feel why this
   matters: in most robot-learning workflows, manual lineage upkeep
   is the hidden tax that kills iteration speed. In artha-os the
   agent does it via NATS, so swapping a checkpoint and re-running
   eval is fast and traceable instead of slow and forgotten.

3. **NATS is the universal I/O fabric — including frontend ↔ runtime.**
   Once everything is wired and the runtime is back up, the user
   clicks `start eval` in the frontend; that click fires a NATS
   event the `eval_runner` picks up. NATS isn't only for backend
   service coordination — it's the same fabric the frontend uses to
   send commands into the running system. Future I/O (motor
   commands from a teleop pad, intervention buttons, footpedal
   events, reward labels) all flow through the same surface. The
   frontend is just another participant on the bus.

Keep each beat tight. The mechanistic flow of clicking start-eval
and watching the dataset populate is for a later narration stage,
not this one.

## Allowed commands

**NONE.** This stage is conversation only. The actual wiring happens
in Stage 08.

If you find yourself wanting to edit `services.yaml`, run a python
heredoc to add SHM types or recorder sources, copy a frontend file,
or restart anything: STOP. You are in the wrong stage. The
execution stage opens only after the user supplies the continue
token.

## Success criteria

- You have walked through the three system-level beats above
  (inference-as-service, agentic-provenance-over-NATS, NATS-as-I/O-
  fabric) in your own words, with concrete examples.
- The user has heard, conceptually, why each addition matters for
  the broader artha-os pattern — not just for this demo.
- You have NOT dived into the specifics of which files get edited
  or which heredocs get run. That's Stage 08's job.
- The user is ready to proceed.

## Continue token

The user must type, EXACTLY, in their next message:

    continue

Vague confirmations DO NOT count.

## Next file

Once the token is received, open `onboarding/08-wire-services-run.md`.
Do NOT open it before.
