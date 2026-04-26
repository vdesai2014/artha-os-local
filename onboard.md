# artha-os Guided Onboarding

You are running an interactive, staged onboarding.

Start with `onboarding/00-intro.md`. Read ONLY that file first.

## Rules — non-negotiable

1. **Stage transitions.** Narration stages wait for the literal
   `continue` token from the user before opening the next stage
   file. Execution stages auto-flow: as soon as their success
   criteria are met, immediately open the next narration file and
   start narrating from there. Execution stages DO NOT wait for a
   token.
2. **The continue token is the literal word `continue`.** Only
   that exact word advances narration stages. "yes", "go", "yee",
   "sounds good", and similar DO NOT count.
3. **Narration and execution live in separate stage files.** A file
   is EITHER a narration stage (zero executable commands; you
   explain) OR an execution stage (commands you run; no narration
   of the WHY — that was done in the previous narration stage). If
   you find commands in a narration stage or vice versa, that is a
   bug in the file — flag it and stop.
4. **Each narration stage has a mandatory checklist.** Before
   requesting the `continue` token, walk through every bracketed
   item in the checklist and verify you have actually said it in
   chat. If any item is unchecked, narrate the missing item now —
   only THEN ask for the token. Skipping items is failing the stage.
5. **If interrupted or resuming**, identify the current stage from
   chat history before continuing. Confirm with the user which
   stage you are in, what was last narrated, and what is pending.

## Stage file structure

Every `onboarding/NN-*.md` file contains:

- **Goal** — what the stage accomplishes
- **Required narration** OR **Allowed commands** — never both
- **Mandatory checklist** (narration stages) or **Success criteria**
  (execution stages)
- **Continue token** (narration) or **auto-flow note** (execution)
- **Next file** — opened after token (narration) or after success
  criteria are met (execution)

## Why the agent does so much by hand

artha-os is intentionally not a framework that hides the runtime
behind a polished API. It is a small, file-based, inspectable system
the user can hack their own way. The friction of editing real files
is the point. Coding-agent capability is exactly what makes that
under-definition tractable — the agent handles the bespoke plumbing
while the user keeps full visibility into what is running and why.
