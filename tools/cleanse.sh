#!/usr/bin/env bash
# The model cleanse — a second model strips the tells the first one wrote.
#
# The rule: the cleanse runs on a DIFFERENT model family than the one that wrote
# the draft. A model is bad at hearing its own accent. A rival hears it instantly.
#
#   ./cleanse.sh draft.md                       # cleanse a file
#   cat draft.md | ./cleanse.sh -               # cleanse stdin
#   ./cleanse.sh --lens legal draft.md          # a different viewpoint
#   ./cleanse.sh --lens legal,editorial d.md    # several, first listed wins
#   ./cleanse.sh --lens auto draft.md           # pick by the draft's triggers
#   DESLOP_LENS=legal ./cleanse.sh draft.md     # same, from the environment
#   TIMEOUT=240 ./cleanse.sh draft.md           # longer bound for a long document
#
# --lens comes first, before the file. A NAME is searched for in every directory
# of DESLOP_LENS_PATH (colon-separated), then lenses.local/, then lenses/; first
# hit wins, so a private pack of lenses can live outside this repo. A path ending
# in .md is used as given. Default `marketing`. Each lens supplies the register
# and its own Pass 3, spliced into the prompt where {{LENS_OVERLAY}} sits. An
# unknown lens exits 66 rather than quietly cleansing under the wrong viewpoint.
#
# `--lens auto` asks deslop.py which lenses the draft's own words call for. That
# is the mechanical fallback. If you can read the draft, name the lens yourself.
#
# Routing, in order:
#   1. codex CLI found  -> GPT-5.6 pass via `codex exec` (you are in Claude Code / Gemini)
#   2. no codex, claude CLI found AND DESLOP_WRITER=gpt -> Claude pass (you are in Codex)
#   3. neither          -> prints the prompt so you can paste it into ChatGPT yourself
#
# If you are ALREADY inside Codex/ChatGPT: you do not need this script. The GPT
# family is the one you are talking to. Paste prompts/cleanse.txt plus your draft.
#
# Always exits 124 on timeout. ALWAYS re-lint the output:
#   python3 tools/deslop.py --text "$(cat cleansed.md)"
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
PROMPT_FILE="$HERE/../prompts/cleanse.txt"
LENS_DIR="$HERE/../lenses"
LENS_LOCAL_DIR="$HERE/../lenses.local"
TIMEOUT="${TIMEOUT:-180}"
MULTI_LENS_NOTE='Several lenses apply. Where they disagree on register, the first listed wins.'

LENS="${DESLOP_LENS:-marketing}"
if [ "${1:-}" = "--lens" ]; then
  [ $# -ge 2 ] || { echo "cleanse: --lens needs a lens name" >&2; exit 66; }
  LENS="$2"; shift 2
fi

lens_dirs() {  # the search path, in order, one directory per line
  set -f; old_ifs="$IFS"; IFS=':'
  for d in ${DESLOP_LENS_PATH:-}; do
    [ -n "$d" ] && printf '%s\n' "$d"
  done
  IFS="$old_ifs"; set +f
  printf '%s\n' "$LENS_LOCAL_DIR"
  printf '%s\n' "$LENS_DIR"
}

resolve_lens() {  # resolve_lens NAME -> the file, on stdout. 1 if there is none.
  case "$1" in
    */*|*.md) [ -f "$1" ] && [ -r "$1" ] && { printf '%s' "$1"; return 0; }; return 1 ;;
  esac
  while IFS= read -r d; do
    [ -n "$d" ] || continue
    if [ -f "$d/$1.md" ] && [ -r "$d/$1.md" ]; then printf '%s' "$d/$1.md"; return 0; fi
  done <<EOF
$(lens_dirs)
EOF
  return 1
}

lens_names() {  # every lens on the path and where it came from, first hit wins
  seen=' '
  while IFS= read -r d; do
    [ -d "$d" ] || continue
    for f in "$d"/*.md; do
      [ -f "$f" ] || continue
      b="$(basename "$f" .md)"
      case "$b" in _*) continue ;; esac
      [ "$(head -n 1 "$f")" = "---" ] || continue   # a lens opens with frontmatter
      case "$seen" in *" $b "*) continue ;; esac
      seen="$seen$b "
      printf '%s (%s) ' "$b" "$d"
    done
  done <<EOF
$(lens_dirs)
EOF
}

overlay_of() {  # the body of `## Cleanse overlay`, up to the next `## ` heading,
  # blank lines at both ends trimmed. The only part of a lens file this reads.
  awk '
    /^##[[:space:]]+Cleanse overlay[[:space:]]*$/ { on = 1; next }
    on && /^## / { on = 0 }
    on { buf = buf $0 "\n" }
    END { sub(/^\n+/, "", buf); sub(/\n+$/, "", buf); printf "%s", buf }
  ' "$1"
}

# The draft is read BEFORE the lens is resolved, because `--lens auto` picks the
# lens by reading the draft. Everything after this point can see both.
if [ "${1:-}" = "-" ] || [ $# -eq 0 ]; then
  DRAFT="$(cat)"
else
  # Without this, a typo'd filename sent an EMPTY draft to a paid model call and
  # wrote the reply into your output file at exit 0.
  [ -f "$1" ] && [ -r "$1" ] || { echo "cleanse: cannot read $1" >&2; exit 66; }
  DRAFT="$(cat "$1")"
fi
[ -n "$(printf '%s' "$DRAFT" | tr -d '[:space:]')" ] || {
  echo "cleanse: draft is empty, nothing to cleanse" >&2; exit 66; }

# `auto` is the one case that needs python: counting trigger hits is deslop.py's
# job and duplicating it in awk would give two answers to the same question.
if [ "$LENS" = "auto" ]; then
  AUTO_TMP="$(mktemp)"
  printf '%s\n' "$DRAFT" >"$AUTO_TMP"
  PICKED="$(python3 "$HERE/deslop.py" --pick-lenses --markdown "$AUTO_TMP" 2>/dev/null)"
  rm -f "$AUTO_TMP"
  [ -n "$PICKED" ] || {
    echo "cleanse: --lens auto could not pick a lens (needs python3 and deslop.py)" >&2
    exit 66; }
  LENS="$PICKED"
  echo "cleanse: auto lens -> $LENS" >&2
fi

# `--lens a,b,c`: every overlay is spliced in, in the order given, each under its
# own LENS: line so the model can tell them apart.
LENS_NAMES=()
old_ifs="$IFS"; IFS=','
for n in $LENS; do
  n="$(printf '%s' "$n" | tr -d '[:space:]')"
  [ -n "$n" ] && LENS_NAMES+=("$n")
done
IFS="$old_ifs"
[ ${#LENS_NAMES[@]} -gt 0 ] || { echo "cleanse: --lens needs a lens name" >&2; exit 66; }

LENS_OVERLAY=''
for n in "${LENS_NAMES[@]}"; do
  # A missing lens is a hard stop, not a fallback. Falling back to marketing would
  # cleanse a contract in sales register and report success while doing it.
  LENS_FILE="$(resolve_lens "$n")" || {
    echo "cleanse: no lens '$n' (searched: $(lens_dirs | tr '\n' ' '))" >&2
    echo "cleanse: available lenses: $(lens_names)" >&2
    echo "cleanse: more lenses (legal, business-eval, editorial, hormozi, utl): [needs link]" >&2
    exit 66; }
  CHUNK="LENS: $(basename "$n" .md)
$(overlay_of "$LENS_FILE")"
  if [ -z "$LENS_OVERLAY" ]; then
    LENS_OVERLAY="$CHUNK"
  else
    LENS_OVERLAY="$LENS_OVERLAY

$CHUNK"
  fi
done

if [ ${#LENS_NAMES[@]} -gt 1 ]; then
  LENS_OVERLAY="$MULTI_LENS_NOTE

$LENS_OVERLAY"
fi

# Passed through the environment, not awk -v: -v expands backslash escapes, and a
# lens is prose that may contain them.
PROMPT="$(LENS_OVERLAY="$LENS_OVERLAY" awk '
  BEGIN { ov = ENVIRON["LENS_OVERLAY"] }
  index($0, "{{LENS_OVERLAY}}") { if (ov != "") print ov; next }
  { print }
' "$PROMPT_FILE")"

FULL="$PROMPT

$DRAFT"

find_bin() { command -v "$1" 2>/dev/null || { [ -x "$HOME/.local/bin/$1" ] && echo "$HOME/.local/bin/$1"; }; }

# The reply is the copy, then a sentinel line, then the change notes. Copy goes to
# STDOUT so the documented `cleanse.sh draft.md > cleansed.md` writes prose ONLY;
# the notes go to STDERR so you still read them.
#
# Splitting on the old bare `---` was not possible: `---` is a legal markdown
# horizontal rule and a YAML frontmatter delimiter, so any draft that contained one
# got cut at the wrong place. Without a split the notes landed inside cleansed.md,
# and step 4 then scored the model's own commentary as prose and stamped it CLEAN —
# the gate reporting a clean page at exactly the moment it was measuring the wrong
# bytes. Redirecting to a file and reading only that file is the documented flow, so
# the leak was invisible until you opened the output.
#
# Fails OPEN on content: no sentinel means print the whole reply as copy and warn.
# A stray note you can see and delete; a silently swallowed last paragraph you cannot.
NOTES_SENTINEL='<<<SLOPMONSTER-NOTES>>>'

emit_copy() {
  awk -v s="$NOTES_SENTINEL" '
    $0 == s { seen = 1; next }
    seen    { notes = notes $0 "\n"; next }
            { body = body $0 "\n" }
    END {
      if (!seen) {
        printf "%s", body
        print "cleanse: WARNING no " s " line in the reply." > "/dev/stderr"
        print "cleanse: emitting everything as copy. Check the tail before you ship," > "/dev/stderr"
        print "cleanse: because change notes may be scored as prose by the re-lint." > "/dev/stderr"
        exit 0
      }
      sub(/\n+$/, "", body)          # drop the blank lines that preceded the sentinel
      printf "%s\n", body
      if (notes != "") {
        print ""                       > "/dev/stderr"
        print "cleanse: what changed -" > "/dev/stderr"
        printf "%s", notes             > "/dev/stderr"
      }
    }
  '
}

CODEX="$(find_bin codex || true)"
CLAUDE="$(find_bin claude || true)"

run_bounded() {  # run_bounded <cmd...>  — macOS has no `timeout`, so we roll one
  OUT="$(mktemp)"; trap 'rm -f "$OUT"' RETURN
  "$@" >"$OUT" 2>&1 </dev/null &
  PID=$!; WAITED=0
  while kill -0 "$PID" 2>/dev/null; do
    if [ "$WAITED" -ge "$TIMEOUT" ]; then
      kill -9 "$PID" 2>/dev/null; wait "$PID" 2>/dev/null
      echo "deslop: cleanse timed out after ${TIMEOUT}s" >&2; return 124
    fi
    sleep 2; WAITED=$((WAITED + 2))
  done
  wait "$PID"; RC=$?; cat "$OUT"; return $RC
}

if [ -n "$CODEX" ] && [ "${DESLOP_WRITER:-claude}" != "gpt" ]; then
  # Claude (or Gemini) wrote the draft -> GPT-5.6 cleanses it.
  # --skip-git-repo-check: copy lives in plain folders. Sandbox read-only: this
  # is a text transform, it has no business writing files.
  RAW="$(run_bounded "$CODEX" exec --skip-git-repo-check --sandbox read-only "$FULL")" || exit $?
  # codex wraps the answer in banners; the answer sits between the last bare
  # `codex` line and `tokens used`.
  #
  # Test the EXTRACTION, not the first line. Branching on `read -r first` meant an
  # answer that opened with a blank line fell through to the raw transcript —
  # banner, session id, the whole prompt file — written straight into your output.
  # `read` also strips leading whitespace, which breaks the "preserve markdown
  # structure exactly" instruction the prompt file gives.
  BODY="$(printf '%s\n' "$RAW" | awk '$0=="codex"{buf="";on=1;next} $0=="tokens used"{on=0;next} on{buf=buf $0 "\n"} END{printf "%s", buf}')"
  if [ -n "$(printf '%s' "$BODY" | tr -d '[:space:]')" ]; then
    printf '%s\n' "$BODY" | emit_copy
  else
    printf '%s\n' "$RAW" | emit_copy
  fi
elif [ -n "$CLAUDE" ] && [ "${DESLOP_WRITER:-claude}" = "gpt" ]; then
  # GPT wrote the draft -> Claude cleanses it.
  # Captured before the split, not piped straight into it: a pipeline reports the
  # LAST command's status, so a timeout would have returned emit_copy's 0 and the
  # 124 contract would have been lost.
  CLAUDE_OUT="$(run_bounded "$CLAUDE" -p "$FULL")" || exit $?
  printf '%s\n' "$CLAUDE_OUT" | emit_copy
else
  # Reached when the only CLI available is the same family that wrote the draft.
  # Running that would be a model marking its own homework, which is the one
  # thing this script exists to prevent. Print the prompt instead.
  echo "cleanse: no rival-family CLI found (a Claude draft needs codex, a GPT" >&2
  echo "draft needs claude). Paste the block below into the other family's chat:" >&2
  echo >&2
  printf '%s\n' "$FULL"
  exit 127
fi
