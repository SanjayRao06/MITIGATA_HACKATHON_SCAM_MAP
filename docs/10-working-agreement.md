# 10 — Working agreement (how Claude reports to the team)

These are the team's standing instructions. They apply to every session.

## After each feature/functionality is implemented
Report in **short, simple terms**, in this order:
1. **What I built**: 2–4 plain bullets.
2. **Run it yourself**: copy-paste commands (PowerShell on Windows) to start the server and test
   the feature, with the expected output. The user must be able to run the code after every feature.
3. **Code walkthrough**: a **very concise**, high-level brief. Name each file/function and say in
   one line how it works. Not line by line; the user doesn't want to spend long on this.
4. **How the judges will test it**: what the test tool or judge sends, and what must come back
   (cite `[PRD §…]` from `docs/00-prd.md`).
5. **Where we are**: the exact status in `docs/08-implementation-plan.md` (done / in progress / next).

Also update `PROGRESS.md` (see CLAUDE.md "How to work").

## Code style
- Readable **comments everywhere**, so the user can explain the code to judges: a docstring per file
  and per function, plus a short comment above each logical block (see CLAUDE.md).

## Bug fixes only
Skip the 5-part report. Just say **what was wrong, what changed**, and give a **one-line code overview**. Keep it concise.

## Source of truth
- `docs/00-prd.md` (the organisers' brief) outranks `docs/01–09`, which Claude generated. If they
  disagree, follow the PRD and fix the other doc.
- Always focus heavily on **how the judges' test tool will test the project** ([PRD §8], [PRD §A]).
