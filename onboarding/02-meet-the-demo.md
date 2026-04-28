# Stage 02 — Meet The Demo (Narration + Browser Handoff)

## Goal

Briefly tell the user what the agent just did, what the demo is,
and hand them to the in-browser tour for the IL eval. The tour
walks them through Controls → start-eval → Cancel Eval →
Datasets → run lineage automatically.

## Required narration

Three short beats, in plain language. Each beat ties what just
happened back to the data-movement / glue automation framing from
Stage 00. Don't repeat the 4-pain-points enumeration.

- **What the agent just did.** Installed all dependencies, pulled
  the grasp-pickup project from artha.bot (the cloud → local
  hop), wired the imitation-learning inference into
  `services.yaml`, booted the demo runtime, and registered eval
  provenance over NATS.

- **What the demo actually is.** A simulated robot in MuJoCo
  trying to pick up a block. The cloud project is meant to
  simulate a real research project, iterating from an older less
  performant approach (CNN+MLP) to something modern that achieves
  high success rate (ACT+PPO). The runtime is currently wired to
  the bottom rung — a small CNN+MLP imitation-learning baseline
  (~0% success). In stage 03, we'll swap this out for the
  ACT+PPO policy.

- **Underneath, while you watch:** typed shared memory carrying
  camera frames + joint state between sim and policy at 50Hz, a
  recorder writing every episode with the IL run already linked
  via NATS provenance. All wired by the agent without you typing
  anything!

## Browser handoff

Tell the user to open this URL in their browser:

    http://127.0.0.1:8000/controls?tour=intro

The in-browser tour will walk them through clicking Start Eval,
auto-cancelling after a few seconds (the IL policy will
struggle), and tracing the new episode + lineage on the Datasets
page. Tell them to come back and type `continue` when the tour
ends.

## Mandatory checklist — before requesting `continue`

You MUST have said all of the following, in chat, in your own
words. Walk every bracketed item; if any is unchecked, narrate
the missing item now and only THEN ask.

- [ ] Said what the agent just did (install + clone + wire + boot
       + provenance).
- [ ] Said what the demo is — a simulated robot in MuJoCo doing
       block grasping, the cloud project simulating a real research
       progression from CNN+MLP to ACT+PPO, the runtime currently
       wired to the IL baseline, and a swap to ACT+PPO coming in
       Stage 03.
- [ ] Said one or two sentences about what's flowing underneath
       (typed SHM for camera frames + joint state at 50Hz, NATS
       for provenance/events, all agent-wired) so the user sees
       the data-movement and glue layers in motion.
- [ ] Pointed the user at `http://127.0.0.1:8000/controls?tour=intro`
       and told them to come back + type `continue` when the
       in-browser tour ends.

If any item is unchecked, you have not completed this stage. Do
NOT request the continue token.

## Allowed commands

**NONE.** This stage is conversation only. The user is doing the
guided eval in the browser.

## Continue token

The user must type, EXACTLY, in their next message:

    continue

Vague confirmations DO NOT count. The user should type `continue`
ONLY after they have completed the in-browser tour.

## Next file

Once the token is received, open `onboarding/03-swap-policy.md`.
Do NOT open it before.
