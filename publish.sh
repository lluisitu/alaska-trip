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
# build_*.py, apply_*.py or *_db.json is picked up automatically with no edit here.
for f in "$DL"/build_*.py "$DL"/apply_*.py "$DL"/*_db*.json "$DL"/test_alaska*.js; do
  [ -e "$f" ] || continue
  take "$f" "tools"
done

# Workflow files go to .github/workflows/. Matched by CONTENT, not by name: a
# bare *.yml rule would sweep any unrelated YAML sitting in Downloads straight
# into CI, which is not a mistake worth making to save a grep.
for f in "$DL"/*.yml "$DL"/*.yaml; do
  [ -e "$f" ] || continue
  grep -q '^jobs:' "$f" 2>/dev/null && grep -q 'runs-on:' "$f" 2>/dev/null || continue
  take "$f" ".github/workflows"
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
  # Bake the road changes into real dates before building, exactly as
  # rebuild.yml does. Without this a laptop publish and a phone publish did
  # different things to the same overrides.json: the workflow baked the changes
  # in and emptied the file, while publish.sh built straight over the top of
  # them and left them pending. The script empties overrides.json once it has
  # applied it, so running this twice is a no-op rather than eighteen months of
  # dates shifted twice.
  [ -f tools/apply_overrides.py ] && { say "Baking road changes into the itinerary ..."
    ( cd tools && python3 apply_overrides.py ) || fail "apply_overrides.py failed."; }
  # Two passes. Some steps read what an earlier step wrote — build_bookings
  # rebuilds its cards from the stops that build_swaps has just rewritten — so a
  # single pass leaves the published file one step behind itself. The second
  # pass is nearly free and is what makes the output converged rather than
  # merely recent.
  for pass in 1 2; do
    for s in build_strategy build_frozen build_light build_phonecraft build_drone build_passes build_legs build_costs build_petlog build_staynotes build_rigfit build_campfacts build_swaps build_bookings build_parks build_askbox; do
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
# Now that workflow files are picked up, the likeliest push failure is no longer
# an expired credential: a token needs the 'workflow' scope to push anything
# under .github/workflows/, and GitHub rejects it at the push with a message
# this used to report as expired. Say both, so the right one gets tried first.
git push || fail "Push failed.
     If the diff touches .github/workflows/, the token needs the 'workflow' scope.
     That is a rejected push, not an expired credential - re-issue the token with
     that box ticked. Otherwise the credential may genuinely have expired."
printf '\nDone. GitHub Pages is rebuilding, about a minute:\n  chooser  https://lluisitu.github.io/alaska-trip/\n  desktop  https://lluisitu.github.io/alaska-trip/desktop/\n  phone    https://lluisitu.github.io/alaska-trip/mobile/\n'
