---
name: slopmonster
description: Turn AI-written copy into copy a human would ship. Lint for AI tells, rewrite, cleanse with a rival model, lint again. Trigger on /slopmonster, "humanize this", "de-slop this", "does this sound like AI", "fix this copy".
---

# SlopMonster

Take any draft and make it read like a person wrote it. A landing page, a README, an
email, a script. The target is not "passes a detector". Detectors are noise, and chasing them makes prose
worse. The target is the gut of a reader who has seen a thousand AI paragraphs this month.

The loop is always the same four steps, and the linter gets the first and last word,
because the linter is honest and the model is persuasive.

```
1. LINT      python3 tools/deslop.py --text "…"      score /5, exits red below 5
2. REWRITE   three passes, by hand or by model       (see below)
3. CLEANSE   a DIFFERENT model family strips tells   tools/cleanse.sh
4. RE-LINT   python3 tools/deslop.py again           ship only at 5/5
```

## Lenses

A lens is the viewpoint the loop works from. It does not change what counts as a tell. It
changes what the line should say once the tell is gone.

| Lens | For |
|---|---|
| `marketing` (default) | landing pages, product pages, emails, ads |
| `business-eval` (pack) | offers, pitches, investor memos, anything judged as a deal |
| `legal` (pack) | contracts, policies, notices, anything a court may read one day |
| `editorial` (pack) | essays, articles, op-eds, long-form argument |
| `hormozi`, `utl` (pack) | offer copy through the Hormozi corpus; learning systems through UTL |

You pick the lens by reading the draft, and Step 0 is how. Several at once: `--lens
legal,editorial`. The vocabularies union, the cleanse model gets both overlays in the order
you listed them, and the first listed lens wins a clash of register. The five linter checks
are identical under every lens. A lens changes the rewrite principles, the register and Pass
3 the cleanse model is sent, and an allow/extra vocabulary list for words a domain uses
literally.

**Where lenses live.** A NAME is searched for in each directory of `$DESLOP_LENS_PATH`
(colon-separated), then `lenses.local/`, then `lenses/`. First hit wins; a path ending in
`.md` is used as given. The private-pack pattern: clone or symlink a private repo of lens
files to `lenses.local/`, and each answers to its own name with none of your writing here.

**Make your own lens.** Copy `lenses/_template.md` to `lenses/<name>.md` and fill in its
three sections. The template is the contract. Then pass `--lens <name>` to both tools.

## Step 0 — pick the lenses

Read the draft first, then put your choice of lenses to the user. For a mechanical hint:
`python3 tools/deslop.py --pick-lenses draft.md`, which prints a comma-separated list.

`--pick-lenses` and `--lens auto` count trigger words. They do not read. Take the hint, then
decide by meaning. "As a lawyer" or "legal review" means `legal`. "Business evaluation", "is
this a good offer" or "investor pitch" means `business-eval`. "Editorial", "essay" or "op-ed"
means `editorial`. Anything else is `marketing`. A lens that is not installed
is a pack lens: say so, offer the pack link from the README, and fall back to `marketing`.

Propose your set with one line of reason per lens, plus any lens you weighed and dropped and
why. Where `AskUserQuestion` is available, ask there with `multiSelect` on, the recommended
set first and each of those marked `(Recommended)`. In a plain chat, ask in one short message
and wait. Skip the question only when the request already named the lenses, as "de-slop this
as a lawyer" does, or when `--lens NAME` was passed; then say which lens you have and carry on.

## Step 1 — Lint

```bash
python3 tools/deslop.py page.html              # a built page (scores visible text only)
python3 tools/deslop.py page.html --view hero  # one element by id
python3 tools/deslop.py --text "paste a draft"
python3 tools/deslop.py --lens legal contract.md   # score under another lens
python3 tools/deslop.py page.html --allow-proof  # numbers are real and evidenced
```

Regex, no opinions. Five groups, one point each: AI vocabulary, AI constructions,
punctuation cadence, rule-of-three rhythm, invented proof. Below 5/5 it exits non-zero, so
it works as a build gate. "Mostly clean" is how a page ends up sounding like every other
AI page on the internet.

Empty input fails rather than passing. A cleanse that times out leaves a zero-byte file,
and a gate that stamps that CLEAN reports slop as clean exactly when the pipeline broke.

Touching a regex means running `python3 tools/test_deslop.py`. The catalogue is matched by
word root, and the obvious stemming shortcut silently kills a dozen base words.

## Step 2 — Rewrite (three passes)

Full catalogue in `references/signs-of-ai-writing.md`. The short version:

1. **Kill the vocabulary.** `delve`, `seamless`, `robust`, `unlock`, `elevate`,
   `leverage`, `game-changing`, `journey`, `realm`… Replace with a plainer word, not a
   synonym of the same word.
2. **Kill the shapes.** `not just X, but Y` is the single loudest tell in English right
   now. Also the `rule-of-three` reflex, `em-dash` pile-ups, hedge stacks, symmetrical
   paragraphs, the closing summary nobody asked for, and a bold lead on every bullet.
3. **Put a person back in.** Removing tells leaves clean, dead copy. One specific number
   per claim. Sentence lengths that vary hard. One thing a cautious writer would have cut.
   One rough edge — a contraction, a fragment, a sentence starting with "And".

## Step 3 — Cleanse with a rival model

A model is bad at hearing its own accent. A rival model hears it instantly. So the cleanse
runs on a **different model family** than the one that wrote the draft:

| You are working in | The draft's accent | Cleanse with |
|---|---|---|
| Claude Code / Claude | Anthropic | GPT-5.6 via the codex CLI — `tools/cleanse.sh` does this |
| Codex / ChatGPT | OpenAI | Claude via `claude -p`, or set `DESLOP_WRITER=gpt` for `cleanse.sh` |
| Gemini CLI | Google | Either CLI; `cleanse.sh` picks whichever is installed |
| No CLI at all | — | `cleanse.sh` prints the prompt; paste it into the other family's chat |

```bash
tools/cleanse.sh draft.md > cleansed.md                 # copy out, notes on stderr
tools/cleanse.sh --lens legal draft.md > cleansed.md    # the lens sets the register
tools/cleanse.sh draft.md > cleansed.md 2> notes.txt    # keep the notes as well
```

The instruction it carries (`prompts/cleanse.txt`): strip the tells, keep every fact,
keep the length within 10%, invent nothing.

It returns **two things**. The rewritten copy, then a `<<<SLOPMONSTER-NOTES>>>` line, then up
to five bullets naming each tell and its fix. The script splits them, so **stdout is copy and
stderr is notes**, and the redirect above writes prose only.

Read the notes. PASS 2 tells the model to stop at the last real point, so it will sometimes
delete your closing line, and the notes are the only place it says so.

`WARNING no <<<SLOPMONSTER-NOTES>>> line` means the model ignored the format and the whole
reply came through as copy. Check the tail before you ship.

## Step 4 — Re-lint

Always. A frontier model is very good at removing tells and quite capable of adding new
ones while it does. An unlinted cleanse is a coin flip.

## The one hard rule

**Never invent proof.** No user counts, no testimonials, no ratings, no `trusted by
10,000 teams` unless every one is true and you can show it. If a claim needs a number you
do not have, write `[needs number]` and move on. The linter flags number-plus-noun
patterns on purpose: a false positive costs ten seconds, a false negative is a claim you
cannot back. Specificity beats borrowed credibility anyway.

## Output format

Return the rewritten copy first, in full. Then a short `▎ what changed` list — at most
five lines, each naming the tell and the fix. Never return analysis alone. Keep the
author's meaning exactly: de-slopping is not rewriting the argument. Match the register
you were given.
