#!/usr/bin/env bash
set -uo pipefail
cd "$(dirname "$0")" || exit 1
say(){ printf '\n%s\n' "$*"; }
fail(){ printf '\n!! %s\n' "$*" >&2; exit 1; }
[ -d .git ] || fail "Not a git repo."
MSG="${1:-Update Alaska dashboards}"; DL="$HOME/Downloads"
if [ -z "$(git config --global user.email)" ]; then
  git config --global user.name "Lluis B"; git config --global user.email "lluisitu@gmail.com"; fi
newest(){ ls -t "$DL"/$1 2>/dev/null | head -1; }
moved=0
while IFS='|' read -r pat dest; do
  [ -n "$pat" ] || continue
  src="$(newest "$pat")"
  if [ -n "${src:-}" ] && [ -f "$src" ]; then
    mkdir -p "$(dirname "$dest")"
    mv "$src" "$dest" && { printf '  picked up  %-26s -> %s\n' "$(basename "$src")" "$dest"; moved=1; }
  fi
done <<'PAIRS'
desktop-index*.html|desktop/index.html
mobile-index*.html|mobile/index.html
build_routes*.py|tools/build_routes.py
build_mobile*.py|tools/build_mobile.py
build_parks*.py|tools/build_parks.py
build_strategy*.py|tools/build_strategy.py
build_bookings*.py|tools/build_bookings.py
build_frozen*.py|tools/build_frozen.py
build_light*.py|tools/build_light.py
build_vendor*.py|tools/build_vendor.py
parks_db*.json|tools/parks_db.json
PAIRS
[ "$moved" -eq 0 ] && say "(nothing new in Downloads - publishing what's already here)"
if command -v python3 >/dev/null 2>&1; then
  for s in build_strategy build_frozen build_light build_bookings build_parks; do
    [ -f "tools/$s.py" ] && { say "Running $s.py ..."; ( cd tools && python3 "$s.py" >/dev/null ) || fail "$s.py failed."; }
  done
  [ -f tools/build_routes.py ] && { say "Refreshing road geometry ..."; ( cd tools && python3 build_routes.py ) || say "(routing failed - keeping existing lines)"; }
  [ -f tools/build_mobile.py ] && { say "Regenerating phone build ..."; ( cd tools && python3 build_mobile.py >/dev/null ) || fail "Mobile rebuild failed."; }
  [ -f tools/build_vendor.py ] && { say "Inlining Leaflet so the map works offline ..."; ( cd tools && python3 build_vendor.py ) || say "(leaflet inline skipped)"; }
else
  say "(python3 not found - run xcode-select --install)"
fi
git add -A
git diff --cached --quiet && { say "Nothing to publish."; exit 0; }
say "Publishing:"; git diff --cached --stat | tail -8
git commit -q -m "$MSG" || fail "Commit failed."
git push || fail "Push failed - your GitHub credential may have expired."
printf '\nDone. GitHub Pages is rebuilding, about a minute:\n  chooser  https://lluisitu.github.io/alaska-trip/\n  desktop  https://lluisitu.github.io/alaska-trip/desktop/\n  phone    https://lluisitu.github.io/alaska-trip/mobile/\n'
