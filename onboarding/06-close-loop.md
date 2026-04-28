# Stage 06 — Close The Loop (Narration Only — Terminal)

## Goal

Close out the onboarding. Recap what just happened. Reframe the
demo as just one slice — the real product is the underlying
primitives + agent. Offer three concrete on-ramps. Stay in the
conversation to drive whichever the user picks.

This is the **terminal stage** — no continue token, no next file.

## Required narration

Two beats then offer three choices. Lean into the reframe — the
UI/sim/policies are pieces of one demo project, the primitives
underneath are the product.

- **If you made it this far…** A coding agent installed, pulled,
  wired, and ran a real robot-learning project on your machine —
  two policies compared side by side with full lineage from each
  eval back to its source run. ~25 min of agent work, a few
  minutes of clicking from you. The data-movement, cloud
  round-trip, and glue layers from Stage 00 — all did their job!

- **What's actually the product.** The UI you used, the Controls
  page, the camera streams, the sim, the IL and ACT+PPO inference
  services — those are pieces of one demo project. The product
  is what's underneath: typed shared memory (iceoryx2) for
  high-rate data, NATS for events, a small supervisor wiring
  them, a file-based local store, and `push`/`pull`/`clone` for
  cloud sync. Those primitives plus a coding agent are what make
  robot-learning research fast for any robot — real or simulated.

- **If you want to keep building, here's what the tool offers
  from here.** No pressure — the demo is done and you're free to
  poke around or close the tab. But if anything below sounds fun:
  1. **Push to artha.bot.** Create an account, grab a token,
     `artha push` — your eval data and lineage go up to your
     cloud project, ready for collaborators or GPU training.
  2. **Wire your own robot.** Same primitives. Define typed
     structs for your robot's data, write a service for your sim
     or hardware, declare them in `services.yaml` — the agent
     helps with all of it.
  3. **Branch a new experiment.** Take any rung of the
     architectural ladder and iterate from there.

After narrating, let the user know the staged onboarding is done
and you (the agent) are around if they want to dig into any of
the directions above or ask questions. DO NOT pressure them to
pick a path. If they say they're done, that's a fine outcome —
acknowledge and stop. Once they engage on a specific direction,
you are no longer following this onboarding flow — you are
operating as their general-purpose agent in the artha-os
checkout, governed by `AGENTS.md` and the project's own rules.

## Mandatory checklist — before closing the stage

You MUST have said all of the following, in chat, in your own
words.

- [ ] Recapped what just happened (clone → bad eval → good eval
       → two comparable episodes with lineage), tying it back to
       the data-movement / cloud / glue layers from Stage 00.
- [ ] Reframed: the UI/sim/policies are pieces of one demo; the
       product is the underlying primitives (iceoryx2, NATS,
       supervisor, local file store, push/pull/clone) + the
       coding agent.
- [ ] Offered all three directions (push, wire own robot, branch
       new experiment), one sentence each, framed as optional —
       not a forced choice.
- [ ] Made clear the staged onboarding is complete and the agent
       is available if the user wants to dig in further. Did NOT
       pressure them to pick a path.

If any item is unchecked, narrate the missing item now.

## Allowed commands

**NONE within this stage.** Once the user picks a next-step path,
you may run commands relevant to that path — but at that point
you are no longer following this onboarding flow.

## Terminal stage

This is the end of the staged onboarding. No continue token. No
next file. The user is now driving.
