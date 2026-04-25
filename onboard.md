# artha-os Guided Onboarding

You are running an interactive, staged onboarding.

Start with `onboarding/00-orient.md`. Read ONLY that file first.

## Rules — non-negotiable

1. **Read ONE stage file at a time.** Do NOT open the next stage file
   until the current stage's exact continue token appears verbatim in
   the latest user message.
2. **Vague confirmations DO NOT count as continue tokens.** "yes", "go",
   "yee", "sounds good", "looks good", and similar words do not advance
   the flow. The user must type the literal token string.
3. **Each stage file has required narration.** You must explain the
   stage's content to the user, in your own words, with concrete
   examples — not paraphrase, not bullet recital. The user is the
   audience; the file is your script, not your speech.
4. **If interrupted or resuming**, identify the current stage from chat
   history before continuing. Confirm with the user which stage you are
   in, what was last narrated, and what token is pending.

## Stage file structure

Every `onboarding/NN-*.md` file contains:

- **Goal** — what the stage accomplishes
- **Required narration** — what to explain (in your own words)
- **Allowed commands** — what (if anything) you may execute
- **Success criteria** — how to know the stage is complete
- **Continue token** — exact literal string the user must type
- **Next file** — opened only after the token is received

## Why the agent does so much by hand

artha-os is intentionally not a framework that hides the runtime behind a
polished API. It is a small, file-based, inspectable system the user can
hack their own way. The friction of editing real files is the point.
Coding-agent capability is exactly what makes that under-definition
tractable — the agent handles the bespoke plumbing while the user keeps
full visibility into what is running and why.
