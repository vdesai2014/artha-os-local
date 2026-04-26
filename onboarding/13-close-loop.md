# Stage 13 — Close The Loop (Narration Only)

## Goal

Close out the onboarding: summarize what just happened, give the
user the cloud round-trip story (push back to artha.bot, GPU
training, pull checkpoints), and offer a small set of concrete
next-step on-ramps. Then make yourself (the agent) available for
whichever path they pick.

This is the **terminal stage** — no continue token, no next file.
The staged onboarding ends here; the agent stays in the conversation
to drive whatever the user chooses next.

## Required narration

Walk the user through the following, in your own words. Keep
momentum — they just succeeded at the demo, this is where they
graduate from "watching the agent" to "driving it on their own".

- **What just happened, in one breath.** They cloned a real research
  project from artha.bot, wired its imitation-learning baseline into
  the runtime, watched it fail with full provenance traceability,
  swapped to the ACT+PPO checkpoint, watched it succeed, and now
  have two comparable eval episodes in their local `local_tool`
  store with lineage back to the runs that produced them. The data
  model previewed at clone time is now materialized in their local
  store, by their hand.

- **The cloud round-trip — push back to artha.bot.** The data the
  user just generated isn't trapped locally. With an artha.bot
  token, `artha push <episode-or-run>` sends episodes, manifests,
  and checkpoints back up to artha.bot. From there a collaborator
  can `artha clone` what they pushed, or the user themselves can
  pull it onto a GPU machine to train, then `artha pull` brings
  new checkpoints back to local for eval. That round-trip is the
  second half of the cloud pain point named at the very start of
  the onboarding, and it is what makes artha.bot a collaboration /
  training-fleet surface, not just a download mirror.

- **Concrete next-step paths — offer all four, ask the user to
  pick one.**
  - **Push the eval data back to artha.bot.** Quick, gives them
    something visible on their cloud project page; introduces the
    push-side of the round-trip mechanically.
  - **Wire your own robot or sim.** Same SHM types + `services.yaml`
    pattern they just watched. The agent can scaffold a new typed
    struct, a new sim or hardware service, a new recorder source,
    and a new frontend overlay — same workflow at smaller scale.
  - **Start a new experiment.** Branch from the ACT+PPO run with a
    different architecture or hyperparameter, train, push, pull,
    eval. The same dual-checkpoint A/B pattern they just lived
    through, but with the user choosing the rungs.
  - **Read the concept docs.** `docs/concepts/` covers IPC tiers
    (SHM vs NATS), supervisor lease semantics, the bridge model,
    cameras, the local-tool API, the sync model, and the cloud
    architecture — the *why* behind everything they saw.

- **The closing thought.** The agent (you) handled the plumbing
  while the user focused on the science. That is the artha-os
  promise — not a framework that hides the runtime, but a small,
  file-based, inspectable system that a coding agent can drive.
  Anything they want to do next, they can drive through this same
  loop.

After narrating, ask the user which path they want to take, and
stay in the conversation.

## Allowed commands

**NONE within this stage.** The narration is the entire stage.

Once the user picks a next-step path, you may run commands relevant
to that path — but at that point you are no longer following this
onboarding flow. You are operating as the user's general-purpose
agent inside their artha-os checkout, governed by `AGENTS.md` and
the project's own rules.

## Success criteria

- You have summarized what just happened (clone → IL fail → ACT+PPO
  success → two evals with lineage) in your own words.
- You have explained the cloud push/pull round-trip and tied it back
  to the cloud pain point from the very first stage.
- You have offered the four concrete next-step paths (push, wire
  own robot, new experiment, concept docs) and asked the user to
  pick one.
- You have stayed in the conversation, ready to drive whichever
  path they choose.

## Terminal stage

This is the end of the staged onboarding. No continue token. No
next file. The user is now driving.
