# Stage 05 — Close The Loop (Narration Only — Terminal)

## Goal

Close out the onboarding. Briefly recap. Offer three concrete
next-step paths. Stay in the conversation to drive whichever the
user picks.

This is the **terminal stage** — no continue token, no next file.

## Required narration

Two beats then offer three choices.

- **One-breath recap.** The user just cloned a real research
  project from artha.bot, ran two policies (one designed to fail,
  one designed to succeed), and now has two comparable eval
  episodes in their local store with full lineage to the runs that
  produced them. The artha-os data model isn't aspirational — it's
  living on their disk, by their hand.

- **What they can do next — three on-ramps.** Offer all three with
  one sentence each, then ask the user to pick one:
  1. **Technical deep-dive.** Walk them through any layer they want
     — `services.yaml` topology, the SHM/NATS split, how the
     recorder picks up provenance, the supervisor model, the bridge
     internals, etc. The agent (you) drives.
  2. **Cloud round-trip — push back to artha.bot.** Help them
     create an artha.bot account, get a token, then `artha push`
     the eval episodes (and/or the forked project) back up. They
     see their own work appear on their own cloud project page —
     closes the cloud loop.
  3. **Continue research.** Start a new experiment — generate
     fresh synthetic data, branch a new run from one of the rungs,
     train, push, pull, eval. The same dual-checkpoint A/B pattern
     they just lived through, but with the user choosing the
     rungs.

After narrating, ask the user which path they want. Stay in the
conversation. Once they pick, you are no longer following this
onboarding flow — you are operating as their general-purpose agent
in the artha-os checkout, governed by `AGENTS.md` and the project's
own rules.

## Mandatory checklist — before closing the stage

You MUST have said all of the following, in chat, in your own
words.

- [ ] Recapped what just happened (clone → bad eval → good eval →
       two comparable episodes with lineage).
- [ ] Offered all three next-step paths (deep-dive, cloud
       round-trip via account creation + push, new experiment),
       each in one sentence.
- [ ] Asked the user which path they want to take.

If any item is unchecked, narrate the missing item now.

## Allowed commands

**NONE within this stage.** Once the user picks a next-step path,
you may run commands relevant to that path — but at that point you
are no longer following this onboarding flow.

## Terminal stage

This is the end of the staged onboarding. No continue token. No
next file. The user is now driving.
