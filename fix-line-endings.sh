#!/usr/bin/env bash
# Undo line-ending-only changes committed by mistake, and stop them coming back.
#
#   bash fix-line-endings.sh [GOOD_COMMIT] [BAD_COMMIT]      (default: 9f74a60 10c9587)
#
# Commit BAD (10c9587, "NHL 19 launcher, icon and settings") was made with `git add -u` while
# Visual Studio's git had checked the work tree out with converted line endings: hundreds of files
# went in with every line "changed". For each file BAD touched, this compares GOOD with the
# current HEAD ignoring line endings: when the only difference is line endings, the file is put
# back exactly as in GOOD. Files with real changes since GOOD (the launcher, README, scripts...)
# are left alone. Then .gitattributes `* -text` tells every git (MSYS2's, Visual Studio's) to
# never convert line endings in this repo, and the result is committed.
set -euo pipefail
good=${1:-9f74a60}
bad=${2:-10c9587}
git rev-parse -q --verify "$good^{commit}" >/dev/null || { echo "fix-line-endings: no commit $good here" >&2; exit 1; }
git rev-parse -q --verify "$bad^{commit}" >/dev/null || { echo "fix-line-endings: no commit $bad here" >&2; exit 1; }
if ! git diff --quiet --ignore-submodules=dirty || ! git diff --cached --quiet --ignore-submodules=dirty; then
    echo "fix-line-endings: commit or stash your changes first (git status)" >&2; exit 1
fi
restored=0 kept=0
while IFS= read -r f; do
    git cat-file -e "$good:$f" 2>/dev/null && git cat-file -e "HEAD:$f" 2>/dev/null || continue
    if git diff --quiet --ignore-cr-at-eol "$good" HEAD -- "$f"; then
        git diff --quiet "$good" HEAD -- "$f" || { git checkout -q "$good" -- "$f"; restored=$((restored + 1)); }
    else
        kept=$((kept + 1)); echo "  real changes, kept: $f"
    fi
done < <(git diff --name-only "$good" "$bad")
grep -qx '\* -text' .gitattributes 2>/dev/null || printf '%s\n' '# Never convert line endings (patch files and scripts must stay byte-exact).' '* -text' >> .gitattributes
git add .gitattributes
git commit -q -m "Undo line-ending-only changes from $bad; never convert line endings (.gitattributes)"
echo "fix-line-endings: $restored files put back as in $good, $kept with real changes kept; committed"
git status --short | head
