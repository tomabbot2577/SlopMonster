---
name: my-lens
description: One line. What kind of writing this lens is for, and whose judgement it borrows.
voices: Named Person (Work, Year), Named Person (Work, Year)
# triggers: words and phrases that mean a draft belongs to this lens. Matched
# case-insensitively, as whole words or whole phrases, against the draft text.
# `--lens auto` counts the hits and selects every lens on three or more. Delete
# the line if you never want this lens picked automatically.
triggers: word, phrase, another phrase
---

# My lens

<!--
HOW A LENS WORKS

A lens does not change what counts as an AI tell. The five linter checks (vocabulary,
constructions, punctuation, rule-of-three, invented proof) run the same under every lens.
A lens changes three other things:

  1. PRINCIPLES      what the line should say instead, once the tell is gone
  2. CLEANSE OVERLAY the register and Pass 3 instructions sent to the rival model
  3. LINT            a few words this domain legitimately uses, or extra tells it has

The frontmatter `triggers:` line is separate from all three. It never changes how a
draft is scored. It only lets `--lens auto` find this lens by counting how often the
draft says the things this lens is for. A lens with no `triggers:` line is still a
perfectly good lens. It just has to be asked for by name.

To make your own: copy this file to lenses/<name>.md (or to a directory on
DESLOP_LENS_PATH, or to lenses.local/ for a private pack), fill in the three
sections, and run

    python3 tools/deslop.py --lens <name> --text "…"
    tools/cleanse.sh --lens <name> draft.md > cleansed.md

Every source in `voices` must be a real, checkable work. Every before/after pair must be
your own writing, not a quotation. Never invent proof, in the lens or in the copy.
-->

## Principles

Three to six. Each one: a title, the source it comes from in italics, two or three
sentences on why, then one before/after pair in this exact shape.

### 1 · Title of the principle
*Who said it, and where.*
Why this matters for this kind of writing. What the reader is doing when they meet
the line, and what they skip.

> **Before:** A line that is technically fine and says nothing.
> **After:** The same line, rewritten under this principle.

### 2 · Title of the principle
*Who said it, and where.*
Why.

> **Before:** …
> **After:** …

## Cleanse overlay

Everything in this section is sent verbatim to the rival model, spliced into
`prompts/cleanse.txt` after PASS 3 and before the ABSOLUTE RULES. Write it as
instructions. Say what register the text is in, who the reader is, and what "put a
person back in" means here (PASS 3 in the base prompt assumes marketing copy. Override
it). Keep it under 25 lines. Do not restate the base passes.

REGISTER: describe the register in one or two sentences.
READER: who they are and what they need from the text.
PASS 3 FOR THIS LENS:
- instruction
- instruction
- instruction

## Lint

Plain `key: value` lines, comma-separated words. Leave a key out if it is empty.
`allow_vocab` stops a catalogue word from firing because this domain uses it literally.
`extra_vocab` adds tells specific to this domain, matched as whole words or phrases.
`allow_proof` defaults to false. Set true only if numbers in this domain are always
evidenced elsewhere (they almost never are, so leave it).

allow_vocab: word, another word
extra_vocab: phrase one, phrase two, phrase three
allow_proof: false
