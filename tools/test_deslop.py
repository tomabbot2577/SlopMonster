#!/usr/bin/env python3
"""Regression tests for the linter. Run: python3 tools/test_deslop.py

Two directions, and the second is the one that matters. It is easy to widen a
regex until it catches everything, so every widening here is paired with a
must-stay-clean case that would break if the rule got greedy.
"""
import re
import subprocess
import sys
import tempfile
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from deslop import (VOCAB, VOCAB_EXACT, audit, visible_text, _root_pattern,
                    markdown_prose, PROOF, read_lens, lens_vocab, merge_lenses)

fails = []


def check(name, cond, detail=''):
    if not cond:
        fails.append(f'{name}: {detail}')


def groups(text):
    return {k for k, v in audit(text).items() if v}


# ── every catalogue word still fires in its own base form ───────────────────
# The obvious stemming fix (strip a trailing "e") silently kills `elevate`,
# `leverage`, `delve` and ten others. This test is what catches that.
for w in VOCAB:
    check(f'base form "{w}"', re.search(_root_pattern(w), w.lower()),
          'root pattern no longer matches its own base word')
for w in VOCAB_EXACT:
    check(f'exact form "{w}"', 'vocab' in groups(f'We {w} things.'), 'not detected')

# ── inflections fire too: the gap that made the tool half-blind ─────────────
for w in ('elevates', 'unlocks', 'empowers', 'streamlines', 'leverages',
          'harnessing', 'revolutionizes', 'innovation', 'transformational'):
    check(f'inflection "{w}"', 'vocab' in groups(f'Acme {w} your workflow.'), 'missed')

# ── literal senses must NOT fire ────────────────────────────────────────────
# Stemming `crafted` to `craft` would flag a furniture maker. These are the
# words that earn their place on the exact-match list.
for ok in ('We craft furniture by hand in Leeds.',
           'Harness the horse before you load the cart.',
           'They walked the length of the valley.'):
    check('literal sense clean', 'vocab' not in groups(ok), ok)

# ── constructions, contracted and not ───────────────────────────────────────
for bad in ("It's not just a tool, it's a platform.",
            'It is not just a tool, it is a platform.',
            'Whether you are a beginner or a pro, start here.',
            'This is where Acme comes in.',
            "Here's the thing. You need a plan.",
            'The result? Teams ship faster.',
            'Ready to get started?'):
    check('construction caught', 'phrases' in groups(bad), bad)

check('plain "whether you are" is clean',
      'phrases' not in groups('Check whether you are on the latest version.'))

# ── rhythm: the repo's own canonical bad example must fail ──────────────────
check('no-Oxford tricolon', 'rhythm' in groups('Trusted, reliable and built to last.'),
      'the tell quoted in examples/ridgeline-roofing.md scored clean')
check('Oxford tricolon', 'rhythm' in groups('It is faster, smarter, and better.'))
check('short items are not a tricolon', 'rhythm' not in groups('We shipped red, white, and blue.'))
check('fronted adverbial is not a tricolon',
      'rhythm' not in groups('On Tuesday, we shipped the release and went home.'))
# The discriminator that earns the no-Oxford rule its place: a rhetorical
# flourish ends in a phrase, a plain list of services does not. This is the
# repo's own shipped hero line — flagging it would be crying wolf.
check('service list is not a tricolon',
      'rhythm' not in groups('Inspection, repair and replacement for homes and commercial buildings.'))
check('or-list is not a tricolon',
      'rhythm' not in groups('We do not do gutters, siding, windows or conservatories.'))

# ── proof: the canonical fabricated line must fail ──────────────────────────
check('canonical invented proof', 'proof' in groups('Loved by 10,000+ happy homeowners.'),
      'the line quoted in references/principles.md scored clean')
check('small counts too', 'proof' in groups('Trusted by 25 businesses.'))

# ── entities: decoded, not leaked ───────────────────────────────────────────
t = visible_text("<p>It&#x27;s not just a tool, it&#x27;s a platform.</p>")
check('entity apostrophes decoded', "it's not just" in t.lower(), repr(t))
check('entities do not donate semicolons', t.count(';') == 0, repr(t))
check('phrase seen through entities', 'phrases' in groups(t))
check('nbsp becomes a space', visible_text('<p>a&nbsp;b</p>') == 'a b')

# ── the gate: empty input must fail, not pass ───────────────────────────────
here = os.path.dirname(os.path.abspath(__file__))
r = subprocess.run([sys.executable, f'{here}/deslop.py', '--text', ''],
                   capture_output=True, text=True)
check('empty input exits non-zero', r.returncode != 0, f'exit {r.returncode}')
r = subprocess.run([sys.executable, f'{here}/deslop.py', '/nope/missing.html'],
                   capture_output=True, text=True)
check('missing file exits non-zero', r.returncode != 0, f'exit {r.returncode}')
check('missing file has no traceback', 'Traceback' not in r.stderr, r.stderr[:80])

# ── files are read as UTF-8, whatever the locale ───────────────────────────
# open() with no encoding= uses the locale's, cp1252 on a stock Windows box. A
# UTF-8 page then decodes to mojibake and the em-dash and construction rules
# never fire, so a page full of tells scores CLEAN. Driven through the CLI on
# purpose: --text was always fine, the file paths were the blind spot. Both of
# them: .html goes through visible_text, .md through markdown_prose.
_dir = tempfile.mkdtemp()
_tells = ('It\u2019s not just a tool, it\u2019s a platform. Whether you\u2019re a startup '
          'or an agency, we ship fast \u2014 really fast \u2014 every week.')

for name, body in (('utf8.html', f'<html><body><p>{_tells}</p></body></html>'),
                   ('utf8.md', _tells)):
    path = os.path.join(_dir, name)
    with open(path, 'w', encoding='utf-8') as fh:
        fh.write(body)
    r = subprocess.run([sys.executable, f'{here}/deslop.py', path],
                       capture_output=True, text=True, encoding='utf-8', errors='replace')
    check(f'{name} is not decoded as cp1252', r.returncode != 0,
          'a UTF-8 page full of tells scored CLEAN - locale decoding is back')
    check(f'{name}: construction rule fires', 'construction' in r.stdout, r.stdout[:140])
    check(f'{name}: em-dash rule fires', 'em-dash' in r.stdout, r.stdout[:140])

# A flagged snippet outside the console codepage must score, not traceback.
_cjk = os.path.join(_dir, 'cjk.html')
with open(_cjk, 'w', encoding='utf-8') as fh:
    fh.write('<html><body><p>Our seamless platform \u4f60\u597d \u2014 \u4e16\u754c '
             '\u2014 delivers robust value today.</p></body></html>')
r = subprocess.run([sys.executable, f'{here}/deslop.py', _cjk],
                   capture_output=True, text=True, encoding='utf-8', errors='replace')
check('non-cp1252 snippet does not traceback', 'Traceback' not in r.stderr, r.stderr[-160:])
check('non-cp1252 snippet still scores', 'score' in r.stdout, r.stdout[:140])

# ── clean human copy still scores 5/5 ───────────────────────────────────────
for ok in ('Six nails per shingle, every shingle.',
           'You get a written scope and a fixed number before anyone climbs a ladder.',
           'We do not do overlays. If the roof needs replacing, it gets stripped.'):
    check('clean copy stays clean', not groups(ok), f'{ok} -> {groups(ok)}')

# ── markdown: a literal is not copy ─────────────────────────────────────────
# Every strip below is paired with a case that must survive it, because the
# fastest way to make a catalogue score 5/5 is to stop reading the catalogue.
md = markdown_prose('Use `delve` here. See [the guide](u.md) for more.')
check('inline code is not scored', 'delve' not in md, repr(md))
check('link text survives', 'the guide' in md, repr(md))
check('surrounding prose survives', 'for more' in md, repr(md))

md = markdown_prose('> ~~Trusted, reliable and built to last.~~\n> **Six nails per shingle.**')
check('struck specimen is not scored', 'rhythm' not in groups(md), repr(md))
check('the shipped line survives', 'Six nails per shingle' in md, repr(md))

md = markdown_prose('Intro.\n```\nleverage seamless unlock\n```\nOutro.')
check('fenced block is not scored', not groups(md), repr(md))
check('prose around the fence survives', 'Intro' in md and 'Outro' in md, repr(md))

# Deleting a code span outright welds the clause into a false rule-of-three.
md = markdown_prose('If a claim needs a number you do not have, write `[needs number]` and move on.')
check('stripping code invents no tricolon', 'rhythm' not in groups(md), repr(md))

# Two table rows are two lines of copy, not one sentence with a dash pile-up.
md = markdown_prose('| a | **3/5** — one thing |\n| b | **5/5** — another thing |')
check('table rows do not merge into one cadence', 'punctuation' not in groups(md), repr(md))

# A heading must not run into the sentence beneath it.
md = markdown_prose('## Receipts, not claims\nA real run on seven sentences.')
check('heading does not weld to body', 'Receipts, not claims A real' not in md, repr(md))

# Markdown handling strips markup only. Real slop in real prose still fails.
md = markdown_prose('We leverage seamless, robust and cutting-edge tooling to empower teams.')
check('markdown does not soften vocabulary', 'vocab' in groups(md), repr(md))
md = markdown_prose('It is not just a tool, it is a journey.')
check('markdown does not soften constructions', 'phrases' in groups(md), repr(md))

md = markdown_prose('- Tier 1 — delete on sight\n- Tier 2 — usually cut')
check('bullets do not merge into one cadence', 'punctuation' not in groups(md), repr(md))
# but a genuine pile-up inside one bullet must still fire
md = markdown_prose('- Our team — trained, certified and local — is ready to help.')
check('dash pile-up inside a bullet still fires', 'punctuation' in groups(md), repr(md))

# ── hyphens: stacking, not the hyphen itself ────────────────────────────────
stack = 'Our industry-leading, context-aware, best-in-class, AI-powered platform ships.'
check('four stacked compounds fire', 'punctuation' in groups(stack), stack)
for ok in ('We fitted a 25-year warranty and a 4.2-hour call-out on a two-storey roof.',
           'The built-up roof needs a full-width strip before the tear-off.',
           'A well-known, long-standing trade name.'):
    check('ordinary hyphenated copy stays clean',
          'punctuation' not in groups(ok), f'{ok} -> {groups(ok)}')

md = markdown_prose('> ~~Em-dash pile-up~~\n> **Thirty-eight on the crew, factory-trained today.**')
check('blockquote lines do not merge', 'punctuation' not in groups(md), repr(md))

# ── proof: a number and its noun live in one sentence ───────────────────────
for hit in ('10,000+ happy users', '500 teams', '2,000 verified customers',
            '3.5 million customers'):
    check('real proof claim still caught', PROOF.search(hit), hit)
for clean in ('"Don\'t Make Me Think", 2000. The reader decides in seconds.',
              'Roofing, and only roofing, since 2001. Customers come back.',
              'Version 2.0. Readers can skip it.'):
    check('proof does not reach across a full stop', not PROOF.search(clean), clean)

# ── negated "just": the contracted register counts too ──────────────────────
# `\bnot\b` has no standalone token to match inside `isn't`, so an uncontracted-only
# pattern scored every contracted form clean — in the register a model reaches for
# when it is trying hardest to sound human. The full stop cases matter as much: the
# window could not previously cross one.
for hit in ("This isn't just a map, it's a plan.",
            'It is not just a map. It is a plan.',
            "SlopMonster isn't just a linter, it's a gate.",
            "These aren't just words, they're tells.",
            'This is not just a map, but a plan.',
            "It doesn't just score you, it fails the build."):
    check('negated-just construction caught', 'phrases' in groups(hit), hit)

# Paired must-stay-clean cases, per this file's rule. The Y clause needs a comma or a
# full stop before its pronoun, which is what stops a bare negation tripping the rule.
for clean in ("It's not just about money.",
              'Do not just take my word for it.',
              'We could not just sit there. The rain kept falling.',
              'The lot is not paved, it is grass.',
              'He said the price was not right, and we walked away.'):
    check('negated-just stays clean', 'phrases' not in groups(clean), clean)

# ── proof nouns need a closing boundary ─────────────────────────────────────
# `sites?` matched inside "sitemaps", `teams?` inside "teamsters". Real proof
# claims must still fire; ordinary nouns that merely start with one must not.
for clean in ('We generated 12 sitemaps last quarter.',
              'The hall seats 20 projectors.',
              'We shipped 40 userscripts.',
              'The union sent 300 teamsters.'):
    check('proof noun does not match inside a longer word', 'proof' not in groups(clean), clean)
for hit in ('Trusted by 10,000 teams.', 'We host 12 sites.', 'Over 300 clients served.'):
    check('proof claim still caught', 'proof' in groups(hit), hit)

# ── the README's own must-not-fire tricolon example ─────────────────────────
# The wolf-crying case the narrowness exists to prevent. If this fires, the
# README is lying about the rule.
check('README safe tricolon example stays clean',
      'rhythm' not in groups('Inspection, repair and replacement for homes and commercial buildings.'))
check('README tricolon example still fires',
      'rhythm' in groups('Trusted, reliable and built to last.'))

# ── lenses: the catalogue moves, the five checks do not ─────────────────────
# The lens files are written here rather than read out of lenses/, so this suite
# does not break when somebody adds, renames or edits a shipped lens.
_lens_dir = tempfile.mkdtemp()


def write_lens(name, body):
    path = os.path.join(_lens_dir, name)
    with open(path, 'w', encoding='utf-8') as fh:
        fh.write(body)
    return path


def deslop_cli(*argv, **env):
    return subprocess.run([sys.executable, f'{here}/deslop.py', *argv],
                          capture_output=True, text=True, encoding='utf-8',
                          errors='replace', env={**os.environ, **env})


LENS_FULL = write_lens('full.md', '''---
name: full
---

## Cleanse overlay

REGISTER: a lens written by the test suite.

## Lint

allow_vocab: seamless, journey
extra_vocab: fully baked, widget wrangler
allow_proof: false
''')

LENS_BARE = write_lens('bare.md', '''---
name: bare
---

## Cleanse overlay

REGISTER: a lens with no Lint section at all.
''')

LENS_LOOSE = write_lens('loose.md', '''---
name: loose
---

## Lint

allow_proof: true
''')

rules = read_lens(LENS_FULL)
check('allow_vocab parsed', rules['allow_vocab'] == ['seamless', 'journey'], rules)
check('extra_vocab parsed', rules['extra_vocab'] == ['fully baked', 'widget wrangler'], rules)
check('allow_proof parsed as false', rules['allow_proof'] is False, rules)

lv, lve = lens_vocab(rules)
check('allow_vocab drops a root-list entry', 'seamless' not in lv)
check('allow_vocab drops an exact-list entry', 'journey' not in lve)
check('allow_vocab leaves the rest of the catalogue', 'robust' in lv and 'crafted' in lve)
check('extra_vocab lands on the exact list', 'widget wrangler' in lve)
# Exact, like VOCAB_EXACT. A lens author naming one phrase has not signed up for
# every word that starts with it.
check('extra_vocab does not stem',
      not audit('The widget wranglers of Leeds.', vocab=lv, vocab_exact=lve)['vocab'])

slop = 'Our seamless platform ships on Friday.'
r = deslop_cli('--lens', LENS_FULL, '--text', slop)
check('allow_vocab suppresses a catalogue hit', r.returncode == 0, r.stdout[:200])
r = deslop_cli('--text', slop)
check('the same line without the lens still fails', r.returncode != 0, r.stdout[:200])

extra = 'The widget wrangler arrives on Friday.'
r = deslop_cli('--lens', LENS_FULL, '--text', extra)
check('extra_vocab fires', r.returncode != 0 and 'widget wrangler' in r.stdout, r.stdout[:200])
r = deslop_cli('--text', extra)
check('extra_vocab does not leak into the default lens', r.returncode == 0, r.stdout[:200])

# A lens with no Lint section is legal, and must change nothing at all.
check('a lens with no Lint section parses empty',
      read_lens(LENS_BARE) == {'allow_vocab': [], 'extra_vocab': [],
                               'allow_proof': False, 'triggers': []},
      read_lens(LENS_BARE))
r = deslop_cli('--lens', LENS_BARE, '--text', slop)
check('no Lint section changes nothing', r.returncode != 0 and 'seamless' in r.stdout, r.stdout[:200])
check('the report names the lens', 'lens: bare' in r.stdout, r.stdout[:200])

r = deslop_cli('--lens', LENS_LOOSE, '--text', 'Trusted by 10,000 teams.')
check('lens allow_proof drops the proof rule', r.returncode == 0, r.stdout[:200])
check('lens allow_proof still prints the hit', '10,000 teams' in r.stdout, r.stdout[:200])

r = deslop_cli('--text', slop, DESLOP_LENS=LENS_FULL)
check('DESLOP_LENS selects the lens', r.returncode == 0, r.stdout[:200])

# An unknown lens is an error. Falling back to the default would score a document
# against the wrong catalogue and print CLEAN while doing it.
r = deslop_cli('--lens', 'no-such-lens', '--text', 'Six nails per shingle.')
check('unknown lens exits non-zero', r.returncode != 0, f'exit {r.returncode}')
check('unknown lens does not traceback', 'Traceback' not in r.stderr, r.stderr[:120])
check('unknown lens lists what is available', 'available lenses' in r.stderr, r.stderr[:160])
check('unknown lens lists the default lens', 'marketing' in r.stderr, r.stderr[:160])
r = deslop_cli('--lens')
check('--lens with no name exits non-zero', r.returncode != 0, f'exit {r.returncode}')

# ── the search path: DESLOP_LENS_PATH, then lenses.local/, then lenses/ ──────
# A lens NAME is resolved by searching directories in order, so a private pack of
# lenses can live outside this repo and still be selected by name. These dirs are
# built here, not in the repo, so the suite proves the search and not the checkout.
_path_a = tempfile.mkdtemp()
_path_b = tempfile.mkdtemp()


def write_at(directory, name, body):
    path = os.path.join(directory, name)
    with open(path, 'w', encoding='utf-8') as fh:
        fh.write(body)
    return path


write_at(_path_a, 'private.md', '''---
name: private
---

## Lint

allow_vocab: seamless
''')
# Same NAME in both directories, different rules. The first directory must win.
write_at(_path_a, 'clash.md', '''---
name: clash
---

## Lint

allow_vocab: seamless
''')
write_at(_path_b, 'clash.md', '''---
name: clash
---

## Lint

extra_vocab: widget wrangler
''')

r = deslop_cli('--lens', 'private', '--text', slop, DESLOP_LENS_PATH=_path_a)
check('a lens on DESLOP_LENS_PATH resolves by name', r.returncode == 0, r.stdout[:200])
r = deslop_cli('--lens', 'private', '--text', slop)
check('a lens off the path is not found', r.returncode != 0, r.stdout[:200])
check('a lens off the path says where it searched', 'searched' in r.stderr, r.stderr[:200])

r = deslop_cli('--lens', 'clash', '--text', slop,
               DESLOP_LENS_PATH=f'{_path_a}:{_path_b}')
check('first directory on the path wins', r.returncode == 0, r.stdout[:200])
r = deslop_cli('--lens', 'clash', '--text', slop,
               DESLOP_LENS_PATH=f'{_path_b}:{_path_a}')
check('reversing the path reverses which lens wins', r.returncode != 0, r.stdout[:200])

# The listing merges every directory and says which one each lens came from, so a
# name clash is visible rather than mysterious.
r = deslop_cli('--lens', 'no-such-lens', '--text', slop, DESLOP_LENS_PATH=_path_a)
check('the listing includes a path lens', 'private' in r.stderr, r.stderr[:400])
check('the listing includes a shipped lens', 'marketing' in r.stderr, r.stderr[:400])
check('the listing names the directory each lens came from',
      f'private ({_path_a})' in r.stderr, r.stderr[:400])

# ── several lenses at once ──────────────────────────────────────────────────
LENS_A = write_lens('multi-a.md', '''---
name: multi-a
---

## Lint

allow_vocab: seamless
extra_vocab: widget wrangler
allow_proof: true
''')
LENS_B = write_lens('multi-b.md', '''---
name: multi-b
---

## Lint

allow_vocab: robust
extra_vocab: fully baked
allow_proof: true
''')
LENS_C = write_lens('multi-c.md', '''---
name: multi-c
---

## Lint

allow_proof: false
''')

merged = merge_lenses([LENS_A, LENS_B])
check('allow_vocab unions across lenses',
      merged['allow_vocab'] == ['seamless', 'robust'], merged)
check('extra_vocab unions across lenses',
      merged['extra_vocab'] == ['widget wrangler', 'fully baked'], merged)
check('the union is deduplicated',
      merge_lenses([LENS_A, LENS_A])['extra_vocab'] == ['widget wrangler'],
      merge_lenses([LENS_A, LENS_A]))
check('allow_proof holds when every lens says true',
      merge_lenses([LENS_A, LENS_B])['allow_proof'] is True)
check('one strict lens is enough to keep the proof rule',
      merge_lenses([LENS_A, LENS_C])['allow_proof'] is False)

r = deslop_cli('--lens', f'{LENS_A},{LENS_B}', '--text',
               'Our seamless and robust platform ships on Friday.')
check('both allow_vocab lists apply at once', r.returncode == 0, r.stdout[:200])
check('the header names both lenses in order',
      'lens: multi-a + multi-b' in r.stdout, r.stdout[:200])
r = deslop_cli('--lens', f'{LENS_B},{LENS_A}', '--text', slop)
check('the header keeps the order given',
      'lens: multi-b + multi-a' in r.stdout, r.stdout[:200])

r = deslop_cli('--lens', f'{LENS_A},{LENS_B}', '--text',
               'The widget wrangler arrived fully baked on Friday.')
check('extra_vocab from either lens fires',
      'widget wrangler' in r.stdout and 'fully baked' in r.stdout, r.stdout[:300])

r = deslop_cli('--lens', f'{LENS_A},{LENS_B}', '--text', 'Trusted by 10,000 teams.')
check('two waiving lenses waive the proof rule', r.returncode == 0, r.stdout[:200])
r = deslop_cli('--lens', f'{LENS_A},{LENS_C}', '--text', 'Trusted by 10,000 teams.')
check('one strict lens keeps the proof rule at the CLI',
      r.returncode != 0, r.stdout[:200])

# ── auto selection by trigger words ─────────────────────────────────────────
_auto_dir = tempfile.mkdtemp()
write_at(_auto_dir, 'loud.md', '''---
name: loud
triggers: quarterly filing, escrow, indemnity clause
---

## Lint

allow_proof: true
''')
write_at(_auto_dir, 'quiet.md', '''---
name: quiet
triggers: cadence review, sprint burndown
---

## Lint
''')
write_at(_auto_dir, 'silent.md', '''---
name: silent
---

## Lint
''')

# Three hits for `loud`, two for `quiet`, none for `silent`. Only `loud` clears.
AUTO_TEXT = ('The quarterly filing lists the escrow account and the indemnity clause. '
             'A cadence review follows the second cadence review.')
r = deslop_cli('--pick-lenses', '--text', AUTO_TEXT, DESLOP_LENS_PATH=_auto_dir)
check('--pick-lenses prints only the selection',
      r.stdout.strip() == 'loud', repr(r.stdout))
check('--pick-lenses exits 0', r.returncode == 0, f'exit {r.returncode}')
check('a lens two hits short is not selected', 'quiet' not in r.stdout, r.stdout)
check('a lens with no triggers never auto-selects', 'silent' not in r.stdout, r.stdout)

r = deslop_cli('--lens', 'auto', '--text', AUTO_TEXT, DESLOP_LENS_PATH=_auto_dir)
check('--lens auto lints under the lens it chose',
      'lens: loud' in r.stdout, r.stdout[:200])
check('--lens auto reports the choice and the count on stderr',
      'deslop: auto lens -> loud (3)' in r.stderr, r.stderr[:200])

# Two lenses over the floor come back in hit order, loudest first.
write_at(_auto_dir, 'louder.md', '''---
name: louder
triggers: escrow
---

## Lint
''')
BOTH = ('escrow escrow escrow escrow. The quarterly filing names the indemnity clause '
        'for the escrow account.')
r = deslop_cli('--pick-lenses', '--text', BOTH, DESLOP_LENS_PATH=_auto_dir)
check('several lenses over the floor come back comma-separated, loudest first',
      r.stdout.strip() == 'loud,louder', repr(r.stdout))

r = deslop_cli('--pick-lenses', '--text', 'A quiet note about the weather in Leeds.',
               DESLOP_LENS_PATH=_auto_dir)
check('nothing triggered falls back to marketing',
      r.stdout.strip() == 'marketing', repr(r.stdout))

# Triggers are whole words or whole phrases, never substrings. Substring matching
# would score this line at four hits and select `exactly`; whole-word matching
# scores it at one, which is under the floor, so the fallback answers instead.
write_at(_auto_dir, 'exactly.md', '''---
name: exactly
triggers: gasket, flywheel
---

## Lint
''')
r = deslop_cli('--pick-lenses', '--text',
               'Gasketing gaskets aside, the gasket and the flywheels.',
               DESLOP_LENS_PATH=_auto_dir)
check('a trigger does not match inside a longer word',
      r.stdout.strip() == 'marketing', repr(r.stdout))
r = deslop_cli('--pick-lenses', '--text',
               'The gasket, a gasket, another gasket.', DESLOP_LENS_PATH=_auto_dir)
check('the same trigger fires as a whole word',
      r.stdout.strip() == 'exactly', repr(r.stdout))

# The shipped marketing lens declares triggers, and they work.
r = deslop_cli('--pick-lenses', '--text',
               'The landing page hero needs a pricing block and a call to action.')
check('the shipped marketing lens auto-selects on its own triggers',
      r.stdout.strip() == 'marketing', repr(r.stdout))

if fails:
    print(f'{len(fails)} FAILED\n')
    for f in fails:
        print(f'  · {f}')
    sys.exit(1)
print('all tests passed')
