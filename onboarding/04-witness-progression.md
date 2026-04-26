# Stage 04 — Witness The Progression (Narration + Browser Handoff)

## Goal

Tell the user what just got swapped and why ACT+PPO works where IL
didn't. Then hand them back to the browser to run the same eval
and see the contrast — two episodes side-by-side, one failure, one
success, distinct lineage.

## Required narration

Three short beats. The user just lived through failure; pay off
the contrast.

- **What just changed.** The agent rewrote `services.yaml` to
  point inference at the ACT+PPO checkpoint, registered new eval
  provenance, and restarted the runtime. Same wiring, same task,
  same input modalities — only the policy changed. This is the
  same A/B mechanic the user would use to compare any two policies
  in their own work: edit one yaml entry, set new provenance,
  restart.

- **Why this one works.** Three architectural changes vs the IL
  baseline, each in one sentence:
  1. **Action chunking** — predicts a chunk of 50 future actions at
     once, so it commits to a coherent grasp trajectory instead of
     averaging across phases.
  2. **Transformer backbone (ACT)** — better fit for multi-camera
     manipulation than the small CNN+MLP.
  3. **Residual PPO on top** — RL-trained nudge that fine-tuned the
     chunk policy in simulation against task reward.
  Same data, same task — only the architecture changed. ~98%
  success vs 0%. That gap is what the architectural ladder bought,
  and the user is about to see it run.

- **Now go run the better eval.** Walk the user through:
  1. Switch back to the browser tab at `http://127.0.0.1:8000`
     (still open from the bad eval; refresh if the websocket
     dropped during the restart).
  2. Go to the **Controls** page.
  3. Click **start-eval**. The robot will reach for the block.
  4. Watch it close the gripper at the right moment and lift. The
     eval auto-ends on success.
  5. Go to the **Datasets** page. There are now TWO episodes —
     the IL failure from before and this new ACT+PPO success.
  6. Click `Run` on the new episode to confirm lineage links to
     the `act-ppo-dense-affine` training run (different from the
     IL episode's lineage).
  7. Thumbs-up the eval (contrast with the thumbs-down on the IL
     one).
  8. Come back to chat and type `continue` when done.

## Mandatory checklist — before requesting `continue`

You MUST have said all of the following, in chat, in your own
words. Walk every bracketed item; if any is unchecked, narrate the
missing item now and only THEN ask for the token.

- [ ] Said what just changed mechanically (services.yaml swap +
       new provenance + restart) and that this is the canonical
       A/B mechanic for any future policy comparison.
- [ ] Named the three architectural changes in ACT+PPO vs IL
       (chunking, transformer, residual PPO), each in one
       sentence.
- [ ] Tied the contrast to the architectural ladder — same data,
       same task, only architecture changed; 0% → ~98%.
- [ ] Walked the user through the full browser flow (refresh tab
       → start-eval → watch success → Datasets → see two episodes
       with distinct lineage → thumbs-up → continue).

If any item is unchecked, you have not completed this stage. Do NOT
request the continue token.

## Allowed commands

**NONE.** This stage is conversation only. The user is doing the
eval in the browser.

## Continue token

The user must type, EXACTLY, in their next message:

    continue

Vague confirmations DO NOT count. The user should type `continue`
ONLY after they have completed the success eval and seen both
episodes on the Datasets page.

## Next file

Once the token is received, open
`onboarding/05-link-act-ppo-output.md`. Do NOT open it before.
