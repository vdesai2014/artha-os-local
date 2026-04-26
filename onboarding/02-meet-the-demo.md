# Stage 02 — Meet The Demo (Narration + Browser Handoff)

## Goal

Briefly orient the user on what was just pulled and how the runtime
holds it together at a high level. Then hand them to the browser to
run the IL eval — which will fail on purpose — and trace the
lineage on the Datasets page.

## Required narration

Four short beats, in plain language. Keep each tight; don't go
deep into architecture.

- **What got pulled.** A real research project from artha.bot —
  not a tutorial fixture. It contains a ladder of trained policies
  (imitation learning → action chunking → ACT → ACT+PPO), all
  organized as a parent-child run chain on disk under
  `workspace/grasp-pickup__*/`. The runtime is currently wired to
  the bottom rung — a small CNN+MLP imitation-learning baseline
  that predicts one robot command at a time.

- **How the runtime holds it together (briefly).** Underneath the
  demo, high-rate data — camera frames, joint state, robot
  commands — flows over typed shared memory between the sim, the
  AI policy, the recorder, and the bridge to the user's browser.
  NATS is the event bus: eval start/stop clicks, the recorder's
  provenance link to the source run, parameter changes. The agent
  wired all of this in the prep step. The user doesn't need to
  think about it for the demo, but it's the same pattern that
  scales to a real robot.

- **The agent already linked provenance.** Before any eval click,
  the agent used NATS to tell the recorder which policy + run +
  checkpoint is generating the actions you're about to see. So
  when the new eval episode appears in Datasets, the link back to
  its source code (the IL training run, this specific checkpoint)
  is already there — no manual tagging, no remembering which
  checkpoint was running. The agent does that bookkeeping; the
  user focuses on the experiment.

- **Now go run the bad eval.** Walk the user through the browser
  flow, bullet by bullet. Make sure they understand the IL policy
  is failing on purpose:
  1. Open `http://127.0.0.1:8000`.
  2. Go to the **Controls** page.
  3. Click **start-eval**. The robot will start moving.
  4. **The IL policy is going to fail.** It averages across grasp
     phases (approach, close, lift) and never quite closes the
     gripper at the right moment. This is by design — it's the
     bottom of the architectural ladder.
  5. When the robot is clearly stuck, click **STOP**.
  6. Go to the **Datasets** page. Find the new episode.
  7. On the right-hand side of the Datasets page, find the
     **provenance** panel. The **Run** linked there is the
     imitation-learning training run that produced this
     checkpoint — the link the agent set up via NATS during prep.
  8. Thumbs-down the eval to mark it as a failure.
  9. Come back to chat and type `continue` when done.

## Mandatory checklist — before requesting `continue`

You MUST have said all of the following, in chat, in your own
words. Walk every bracketed item; if any is unchecked, narrate the
missing item now and only THEN ask for the token.

- [ ] Said what got pulled — a real research project on artha.bot
       with a ladder of policies — and that the IL baseline is
       currently loaded.
- [ ] Said one paragraph (high level) about how the OS handles it
       under the hood: typed shared memory for high-rate data, NATS
       for events, agent did the wiring.
- [ ] Said the agent already used NATS to link the eval's recorded
       data to the IL run + checkpoint, so provenance shows up
       automatically in Datasets — no manual tagging.
- [ ] Set expectation that the IL eval will fail on purpose
       (averages across grasp phases).
- [ ] Walked the user through the full browser flow (open URL →
       Controls → start-eval → STOP when stuck → Datasets →
       right-side provenance panel → Run linked there →
       thumbs-down → come back and type `continue`).

If any item is unchecked, you have not completed this stage. Do NOT
request the continue token.

## Allowed commands

**NONE.** This stage is conversation only. The user is doing the
eval in the browser.

## Continue token

The user must type, EXACTLY, in their next message:

    continue

Vague confirmations DO NOT count. The user should type `continue`
ONLY after they have completed the browser eval flow and seen the
Datasets page lineage.

## Next file

Once the token is received, open `onboarding/03-swap-policy.md`. Do
NOT open it before.
