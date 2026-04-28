# Stage 04 — Run The Better Policy (Narration + Browser Handoff)

## Goal

Briefly tell the user the swap is done, then hand them back to
the browser to manually re-run the eval — same buttons as before,
no guided tour this time. They'll see the ACT+PPO policy succeed
where the IL baseline failed.

## Required narration

Two short beats. Don't recap the architectural details — the
"research progression from CNN+MLP to ACT+PPO" framing from Stage
02 already set the expectation, and the demo experience itself
will land it. Just tell the user the swap is done and what to do.

- **What just changed.** Agent rewrote `services.yaml` to point
  inference at the ACT+PPO checkpoint, registered a new eval
  provenance manifest, restarted the runtime, and linked the IL
  eval as an output of the IL run on the way through. Same
  wiring otherwise — only the policy changed.

- **Now go run it again, with a short second tour.** Open
  `http://127.0.0.1:8000/controls?tour=intro2`. The tour will
  auto-click Start Eval, watch the eval-state label until it
  reads SUCCESS (or until ~10s pass), then bring you to the new
  episode in Datasets. You'll see two episodes side by side, one
  fail and one success, each linked back to its source run.

## Mandatory checklist — before requesting `continue`

You MUST have said all of the following, in chat, in your own
words. Walk every bracketed item; if any is unchecked, narrate
the missing item now and only THEN ask.

- [ ] Said the swap is done — services.yaml rewritten, ACT+PPO
       checkpoint loaded, new provenance registered, IL eval
       linked as output of the IL run.
- [ ] Pointed the user at
       `http://127.0.0.1:8000/controls?tour=intro2` and told them
       the tour will auto-run the eval and bring them to the new
       episode in Datasets.
- [ ] Set expectation that ACT+PPO will succeed and the eval will
       auto-end, with two comparable episodes appearing on the
       Datasets page.
- [ ] Told the user to come back and type `continue` when done.

If any item is unchecked, you have not completed this stage. Do
NOT request the continue token.

## Allowed commands

**NONE.** This stage is conversation only. The user is doing the
manual eval in the browser.

## Continue token

The user must type, EXACTLY, in their next message:

    continue

Vague confirmations DO NOT count. The user should type `continue`
ONLY after they have completed the success eval and seen both
episodes on the Datasets page.

## Next file

Once the token is received, open
`onboarding/05-link-act-ppo-output.md`. Do NOT open it before.
