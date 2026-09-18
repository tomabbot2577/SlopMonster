#!/usr/bin/env bash
# Regression tests for the copy/notes split in cleanse.sh.
#
# The split is what keeps the model's change notes out of cleansed.md. Without it
# step 4 re-lints the notes as if they were prose and reports CLEAN, which is the
# gate lying at the one moment you are relying on it.
#
# Sources emit_copy out of cleanse.sh rather than reimplementing it, so this test
# fails if the real function drifts. No model calls, so it runs in CI.
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
eval "$(sed -n "/^NOTES_SENTINEL=/,/^}$/p" "$HERE/cleanse.sh")"

fail=0
check() {  # check <name> <condition-result>
  if [ "$2" = "0" ]; then printf '  ok    %s\n' "$1"
  else printf '  FAIL  %s\n' "$1"; fail=1; fi
}

# ── the ordinary reply ──────────────────────────────────────────────────────
out="$(printf 'Line one.\nLine two.\n\n%s\n- killed a tell\n' "$NOTES_SENTINEL" | emit_copy 2>/dev/null)"
[ "$out" = "$(printf 'Line one.\nLine two.')" ]; check 'copy is the text above the sentinel' $?
err="$(printf 'Copy.\n\n%s\n- killed a tell\n' "$NOTES_SENTINEL" | emit_copy 2>&1 >/dev/null)"
case "$err" in *'killed a tell'*) check 'notes go to stderr' 0;; *) check 'notes go to stderr' 1;; esac
case "$out" in *'killed a tell'*) check 'notes stay OUT of stdout' 1;; *) check 'notes stay OUT of stdout' 0;; esac

# ── a draft that legitimately contains --- ──────────────────────────────────
# The old separator was a bare `---`, which is both a markdown rule and a YAML
# frontmatter delimiter, so splitting on it truncated any draft containing one.
body="$(printf 'Intro.\n\n---\n\nAfter the rule.\nFinal line.\n\n%s\n- a note\n' "$NOTES_SENTINEL" | emit_copy 2>/dev/null)"
case "$body" in *'Final line.'*) check 'copy past a --- survives' 0;; *) check 'copy past a --- survives' 1;; esac
case "$body" in *'---'*) check 'the --- itself is preserved' 0;; *) check 'the --- itself is preserved' 1;; esac
case "$body" in *'a note'*) check 'notes not leaked past a ---' 1;; *) check 'notes not leaked past a ---' 0;; esac

# ── no sentinel: fail OPEN, never eat the copy ──────────────────────────────
out="$(printf 'Only copy.\nSecond line.\n' | emit_copy 2>/dev/null)"
case "$out" in *'Second line.'*) check 'missing sentinel keeps all copy' 0;; *) check 'missing sentinel keeps all copy' 1;; esac
err="$(printf 'Only copy.\n' | emit_copy 2>&1 >/dev/null)"
case "$err" in *WARNING*) check 'missing sentinel warns loudly' 0;; *) check 'missing sentinel warns loudly' 1;; esac

# ── sentinel with nothing after it ──────────────────────────────────────────
err="$(printf 'Copy only.\n\n%s\n' "$NOTES_SENTINEL" | emit_copy 2>&1 >/dev/null)"
[ -z "$err" ]; check 'empty notes print nothing to stderr' $?

# ── the blank lines before the sentinel are not published ───────────────────
# The model separates the sentinel from the copy with a blank line. Without the
# trim, every cleansed file ends in trailing whitespace.
# Asserted through a FILE, not "$(...)": command substitution strips trailing
# newlines, so a $()-based check cannot see this bug at all and passes either way.
tmp="$(mktemp)"
printf 'Copy ends here.\n\n\n%s\n- a note\n' "$NOTES_SENTINEL" | emit_copy 2>/dev/null >"$tmp"
[ "$(wc -c <"$tmp" | tr -d ' ')" = "16" ]; check 'blank lines before the sentinel are trimmed' $?
rm -f "$tmp"

# ── the sentinel must not match when quoted inside prose ────────────────────
out="$(printf 'We use the `%s` marker.\nStill copy.\n' "$NOTES_SENTINEL" | emit_copy 2>/dev/null)"
case "$out" in *'Still copy.'*) check 'sentinel inside a line is not a split point' 0;; *) check 'sentinel inside a line is not a split point' 1;; esac

# ── the lens overlay is substituted before the prompt is sent ───────────────
# Driven through the real script, not a reimplementation. PATH is cut back to
# /usr/bin:/bin and HOME moved, so neither codex nor claude is found and the
# script takes its exit-127 branch and PRINTS the prompt. That is the whole
# prompt the model would have received, so it is the honest place to assert that
# {{LENS_OVERLAY}} was replaced. A placeholder reaching a model is not a crash;
# it is a cleanse run with no register, silently, at full price.
tmphome="$(mktemp -d)"
noclis() { PATH=/usr/bin:/bin HOME="$tmphome" bash "$HERE/cleanse.sh" "$@"; }

prompt="$(printf 'Draft line.\n' | noclis - 2>/dev/null)"; rc=$?
[ "$rc" = "127" ]; check 'no rival CLI still prints the prompt (exit 127)' $?
case "$prompt" in *'{{LENS_OVERLAY}}'*) check 'the placeholder never reaches the model' 1;;
                  *) check 'the placeholder never reaches the model' 0;; esac
case "$prompt" in *'REGISTER:'*) check 'the default lens overlay is spliced in' 0;;
                  *) check 'the default lens overlay is spliced in' 1;; esac
case "$prompt" in *'PASS 3 — put a person back in.'*) check 'the base passes survive' 0;;
                  *) check 'the base passes survive' 1;; esac
case "$prompt" in *'Draft line.'*) check 'the draft is appended' 0;;
                  *) check 'the draft is appended' 1;; esac

prompt="$(printf 'Draft line.\n' | DESLOP_LENS=marketing noclis - 2>/dev/null)"
case "$prompt" in *'{{LENS_OVERLAY}}'*) check 'DESLOP_LENS also substitutes' 1;;
                  *) check 'DESLOP_LENS also substitutes' 0;; esac

# An unknown lens stops. Falling back to the default would cleanse a contract in
# sales register and exit 0 while doing it.
err="$(printf 'Draft line.\n' | bash "$HERE/cleanse.sh" --lens no-such-lens - 2>&1 >/dev/null)"; rc=$?
[ "$rc" = "66" ]; check 'unknown lens exits 66' $?
case "$err" in *'available lenses'*) check 'unknown lens lists what there is' 0;;
               *) check 'unknown lens lists what there is' 1;; esac
case "$err" in *marketing*) check 'unknown lens names the default lens' 0;;
               *) check 'unknown lens names the default lens' 1;; esac

err="$(bash "$HERE/cleanse.sh" --lens 2>&1 >/dev/null)"; rc=$?
[ "$rc" = "66" ]; check '--lens with no name exits 66' $?

# ── several lenses are all spliced in, in the order given ───────────────────
# Same exit-127 print path: the prompt that reaches stdout is the prompt the model
# would have received, so it is the honest place to assert the splice order.
prompt="$(printf 'Draft line.\n' | noclis --lens marketing,legal - 2>/dev/null)"
case "$prompt" in *'LENS: marketing'*) check 'the first lens is labelled' 0;;
                  *) check 'the first lens is labelled' 1;; esac
case "$prompt" in *'LENS: legal'*) check 'the second lens is labelled' 0;;
                  *) check 'the second lens is labelled' 1;; esac
case "$prompt" in *'LENS: marketing'*'LENS: legal'*) check 'the lenses keep the order given' 0;;
                  *) check 'the lenses keep the order given' 1;; esac
case "$prompt" in *'Where they disagree on register, the first listed wins.'*)
                    check 'two lenses get the tie-break line' 0;;
                  *) check 'two lenses get the tie-break line' 1;; esac
# The tie-break line sits before the first overlay, not after it. A model reading
# it after both registers has already picked one.
case "$prompt" in *'first listed wins.'*'LENS: marketing'*)
                    check 'the tie-break line comes first' 0;;
                  *) check 'the tie-break line comes first' 1;; esac

# Reversing the order reverses the splice, because the first listed lens wins.
prompt="$(printf 'Draft line.\n' | noclis --lens legal,marketing - 2>/dev/null)"
case "$prompt" in *'LENS: legal'*'LENS: marketing'*) check 'reversing --lens reverses the splice' 0;;
                  *) check 'reversing --lens reverses the splice' 1;; esac

# One lens must NOT get the tie-break line. There is nothing to break.
prompt="$(printf 'Draft line.\n' | noclis --lens marketing - 2>/dev/null)"
case "$prompt" in *'first listed wins.'*) check 'one lens gets no tie-break line' 1;;
                  *) check 'one lens gets no tie-break line' 0;; esac
case "$prompt" in *'LENS: marketing'*) check 'one lens is still labelled' 0;;
                  *) check 'one lens is still labelled' 1;; esac

# ── the search path: DESLOP_LENS_PATH, then lenses.local/, then lenses/ ─────
# Built here rather than in the repo, so this proves the search and not the checkout.
lensdir="$(mktemp -d)"
cat >"$lensdir/private.md" <<'LENSEOF'
---
name: private
---

## Cleanse overlay

REGISTER: a private lens that lives outside the repo.
LENSEOF

prompt="$(printf 'Draft line.\n' | DESLOP_LENS_PATH="$lensdir" noclis --lens private - 2>/dev/null)"
case "$prompt" in *'a private lens that lives outside the repo'*)
                    check 'DESLOP_LENS_PATH resolves a lens by name' 0;;
                  *) check 'DESLOP_LENS_PATH resolves a lens by name' 1;; esac

err="$(printf 'Draft line.\n' | noclis --lens private - 2>&1 >/dev/null)"; rc=$?
[ "$rc" = "66" ]; check 'a lens off the path is not found' $?
case "$err" in *searched*) check 'a missing lens says where it searched' 0;;
               *) check 'a missing lens says where it searched' 1;; esac
case "$err" in *"private ($lensdir)"*) check 'the listing names the directory' 1;;
               *) check 'the listing omits a directory not on the path' 0;; esac

err="$(printf 'Draft line.\n' | DESLOP_LENS_PATH="$lensdir" noclis --lens nope - 2>&1 >/dev/null)"
case "$err" in *"private ($lensdir)"*) check 'the listing says which directory each lens came from' 0;;
               *) check 'the listing says which directory each lens came from' 1;; esac
case "$err" in *marketing*) check 'the listing still merges the shipped lenses' 0;;
               *) check 'the listing still merges the shipped lenses' 1;; esac

# ── lenses.local/ beats lenses/ for the same name ───────────────────────────
# This is the private-pack pattern: clone or symlink a private repo to
# lenses.local/ and a lens NAME there shadows the shipped one of the same name.
localdir="$HERE/../lenses.local"
if [ -e "$localdir" ]; then
  # Somebody's real private pack is mounted here. Never touch it: skip instead.
  printf '  skip  lenses.local/ precedence (a real lenses.local is installed)\n'
else
  mkdir -p "$localdir"
  cat >"$localdir/marketing.md" <<'LENSEOF'
---
name: marketing
---

## Cleanse overlay

REGISTER: the SHADOWED marketing lens from lenses.local.
LENSEOF
  prompt="$(printf 'Draft line.\n' | noclis --lens marketing - 2>/dev/null)"
  case "$prompt" in *'the SHADOWED marketing lens from lenses.local'*)
                      check 'lenses.local/ shadows lenses/ for the same name' 0;;
                    *) check 'lenses.local/ shadows lenses/ for the same name' 1;; esac
  # And DESLOP_LENS_PATH still beats lenses.local/, because it is searched first.
  cat >"$lensdir/marketing.md" <<'LENSEOF'
---
name: marketing
---

## Cleanse overlay

REGISTER: the marketing lens from the environment path.
LENSEOF
  prompt="$(printf 'Draft line.\n' | DESLOP_LENS_PATH="$lensdir" noclis --lens marketing - 2>/dev/null)"
  case "$prompt" in *'the marketing lens from the environment path'*)
                      check 'DESLOP_LENS_PATH beats lenses.local/' 0;;
                    *) check 'DESLOP_LENS_PATH beats lenses.local/' 1;; esac
  rm -rf "$localdir"
fi

rm -rf "$lensdir"
rm -rf "$tmphome"

[ "$fail" = "0" ] && echo "all cleanse tests passed" || { echo "cleanse tests FAILED"; exit 1; }
