#!/usr/bin/env bash
set -uo pipefail
cd "$(dirname "$0")" || exit 1
say(){ printf '\n%s\n' "$*"; }
fail(){ printf '\n!! %s\n' "$*" >&2; exit 1; }
[ -d .git ] || fail "Not a git repo."
MSG="${1:-Update Alaska dashboards}"; DL="$HOME/Downloads"
if [ -z "$(git config --global user.email)" ]; then
  git config --global user.name "Lluis B"; git config --global user.email "lluisitu@gmail.com"; fi
# Files arrive via the browser's Downloads folder, which renames duplicates to
# "build_passes-1.py" or "build_passes (1).py". Strip that back off, and match
# by RULE rather than by an explicit list — the old hardcoded list silently
# ignored four new build scripts and two data files because nobody remembered
# to add them, and the publish then ran without them.
canon(){                       # build_passes-2.py -> build_passes.py
  local b="$1"; local ext="${b##*.}"; local stem="${b%.*}"
  # Only strip a duplicate marker that has a separator in front of it, or
  # test_alaska_ext_v3.js loses its 3 and lands as a file nothing runs.
  stem="$(printf '%s' "$stem" | sed -E 's/[ _-]\(?[0-9]+\)?$//')"
  printf '%s.%s' "$stem" "$ext"
}
moved=0
take(){                        # take <src> <destdir> [destname]
  local src="$1" dir="$2" name="${3:-}"
  [ -f "$src" ] || return 0
  [ -n "$name" ] || name="$(canon "$(basename "$src")")"
  mkdir -p "$dir"
  mv "$src" "$dir/$name" && { printf '  picked up  %-28s -> %s\n' "$(basename "$src")" "$dir/$name"; moved=1; }
}
newest(){ ls -t "$DL"/$1 2>/dev/null | head -1; }

# The three page builds keep their explicit mapping, because the file they
# become is not named after the file that arrives.
take "$(newest 'root-index*.html')"    "."       "index.html"
take "$(newest 'desktop-index*.html')" "desktop" "index.html"
take "$(newest 'mobile-index*.html')"  "mobile"  "index.html"

# Everything the build runs on goes to tools/ under its own name. Any future
# build_*.py or *_db.json is picked up automatically with no edit here.
for f in "$DL"/build_*.py "$DL"/*_db*.json "$DL"/test_alaska*.js; do
  [ -e "$f" ] || continue
  take "$f" "tools"
done

# publish.sh cannot replace itself while it is running, so a new copy is staged
# and swapped in on the next run.
NEWPUB="$(newest 'publish*.sh')"
if [ -n "${NEWPUB:-}" ] && [ -f "$NEWPUB" ]; then
  mv "$NEWPUB" ./publish.sh.new && printf '  staged     %-28s -> publish.sh.new\n' "$(basename "$NEWPUB")"
fi
if [ -f publish.sh.new ] && ! cmp -s publish.sh.new publish.sh; then
  cp publish.sh.new publish.sh && chmod +x publish.sh && rm -f publish.sh.new
  say "publish.sh was updated - re-run it to use the new version."
  exit 0
fi
rm -f publish.sh.new
[ "$moved" -eq 0 ] && say "(nothing new in Downloads - publishing what's already here)"
if command -v python3 >/dev/null 2>&1; then
  # Two passes. Some steps read what an earlier step wrote — build_bookings
  # rebuilds its cards from the stops that build_swaps has just rewritten — so a
  # single pass leaves the published file one step behind itself. The second
  # pass is nearly free and is what makes the output converged rather than
  # merely recent.
  for pass in 1 2; do
    for s in build_strategy build_frozen build_light build_phonecraft build_drone build_passes build_legs build_costs build_petlog build_staynotes build_rigfit build_campfacts build_swaps build_bookings build_parks; do
      [ -f "tools/$s.py" ] || continue
      [ "$pass" = 1 ] && say "Running $s.py ..."
      ( cd tools && python3 "$s.py" >/dev/null ) || fail "$s.py failed."
    done
  done
  [ -f tools/build_routes.py ] && { say "Refreshing road geometry ..."; ( cd tools && python3 build_routes.py ) || say "(routing failed - keeping existing lines)"; }
  [ -f tools/build_mobile.py ] && { say "Regenerating phone build ..."; ( cd tools && python3 build_mobile.py >/dev/null ) || fail "Mobile rebuild failed."; }
  [ -f tools/build_vendor.py ] && { say "Inlining Leaflet so the map works offline ..."; ( cd tools && python3 build_vendor.py ) || say "(leaflet inline skipped)"; }
  # The phone build is REGENERATED from the desktop file every publish, so a
  # hand-delivered mobile/index.html is overwritten unless tools/build_mobile.py
  # is the matching version. That happened once and published a phone build
  # missing a whole tab, silently. Check that every data block the desktop
  # carries also reached the phone.
  if [ -f desktop/index.html ] && [ -f mobile/index.html ]; then
    missing=""
    check(){ grep -q "const $1 =" desktop/index.html 2>/dev/null || return 0
             grep -q "\"$2\"" mobile/index.html 2>/dev/null || missing="$missing $1"; }
    check PETLOG petlog
    check PASSES passes
    check LEGINFO legInfo
    if [ -n "$missing" ]; then
      fail "tools/build_mobile.py is out of date: the desktop carries$missing but the phone build does not.
     Save the newest build_mobile.py into Downloads and run this again, or the
     phone gets a build that is quietly missing features."
    fi
  fi
else
  say "(python3 not found - run xcode-select --install)"
fi
git add -A
git diff --cached --quiet && { say "Nothing to publish."; exit 0; }
say "Publishing:"; git diff --cached --stat | tail -8
git commit -q -m "$MSG" || fail "Commit failed."
git push || fail "Push failed - your GitHub credential may have expired."
printf '\nDone. GitHub Pages is rebuilding, about a minute:\n  chooser  https://lluisitu.github.io/alaska-trip/\n  desktop  https://lluisitu.github.io/alaska-trip/desktop/\n  phone    https://lluisitu.github.io/alaska-trip/mobile/\n'
