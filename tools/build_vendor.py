#!/usr/bin/env python3
"""
Inline Leaflet into the dashboards so the map works without a CDN.

    cd tools && python3 build_vendor.py

Both builds loaded Leaflet from cdnjs.cloudflare.com. When that request fails the
page does not error in any way a normal person would notice — the map container
renders at its full height and stays empty. "No map", with nothing to click on
and nothing in the interface saying why.

Plenty of ordinary things block it: an ad blocker or privacy extension, a DNS
filter like Pi-hole or NextDNS, a captive portal, a hotel network. And the one
that actually matters for this trip: no signal. This dashboard exists to be used
on the Dempster and the Cassiar, where there is no cell service for hours at a
stretch, and a map engine fetched over the network is guaranteed to fail exactly
where it is most needed.

Inlining costs about 150 KB against a 2.7 MB file. Map tiles still need a
connection — nothing can be done about that — but with Leaflet inlined the route
lines, every stop marker, the park layers and all the popups draw offline. A
route with no basemap under it is far more use than an empty grey box.

The vendored copy lives in tools/vendor/ so this needs no network either. If it
is genuinely absent — a fresh clone on a machine that never had it — this will
fetch it once from the CDN and cache it there, but only if the bytes match the
copy that was vetted and is already inlined into the published dashboard. An
unrecognised leaflet.js is refused rather than inlined, because this publishes
to a public website and a swapped script would be served to anyone who opens it.
"""
import base64, hashlib, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
VENDOR = pathlib.Path(__file__).resolve().parent / 'vendor'
TARGETS = [ROOT / 'desktop' / 'index.html', ROOT / 'mobile' / 'index.html']

CSS_URL = 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css'
JS_URL = 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js'

MARK = '/* leaflet inlined by build_vendor.py */'

# sha256 of the vetted Leaflet 1.9.4 copies — the exact bytes already inlined
# into the published dashboard. The fetch below refuses anything else.
PINS = {
    'leaflet.css': 'a7837102824184820dfa198d1ebcd109ff6d0ff9a2672a074b9a1b4d147d04c6',
    'leaflet.js': 'db49d009c841f5ca34a888c96511ae936fd9f5533e90d8b2c4d57596f4e5641a',
}


def ensure(path, url):
    """Return the vendored file's text, fetching it once if it is missing."""
    if path.exists():
        return path.read_text()
    import urllib.request
    print(f"   {path.name} not vendored — fetching once from the CDN")
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            body = r.read()
    except Exception as e:
        sys.exit(f"!! {path.name} is missing and could not be fetched ({e}).\n"
                 f"   Put a copy in {path.parent} and commit it — then this never needs network.")
    got = hashlib.sha256(body).hexdigest()
    if got != PINS[path.name]:
        sys.exit(f"!! {path.name} downloaded from {url} does not match the vetted copy.\n"
                 f"   expected {PINS[path.name]}\n   got      {got}\n"
                 f"   Refusing to inline unrecognised code into a public site.")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    print(f"   cached {path} ({len(body) // 1024} KB) — commit it so this never needs network again")
    return body.decode()


def main():
    css_f, js_f = VENDOR / 'leaflet.css', VENDOR / 'leaflet.js'
    css = ensure(css_f, CSS_URL)
    js = ensure(js_f, JS_URL)

    # Leaflet's CSS points at marker-icon.png and layers.png relative to itself.
    # Once inlined those paths resolve against the HTML and 404. The dashboard
    # draws its markers with divIcon and circleMarker so the pins are unused, but
    # the layers control would show a broken image — so strip the url() rules
    # rather than ship something visibly broken offline.
    css = re.sub(r'url\((["\']?)[^)]*\.png\1\)', lambda _m: 'none', css)

    for path in TARGETS:
        if not path.exists():
            print(f"   skip {path.name} (not present)"); continue
        h = path.read_text(); before = len(h)
        if MARK in h:
            print(f"   {path.parent.name}/{path.name}: already inlined")
            continue
        n_css = len(re.findall(re.escape(CSS_URL), h))
        n_js = len(re.findall(re.escape(JS_URL), h))
        if not (n_css or n_js):
            print(f"   !! {path.parent.name}: no cdnjs Leaflet reference found — not touching it")
            continue
        css_block = f'<style>{MARK}\n{css}</style>'
        js_block = f'<script>{MARK}\n{js}</script>'
        h = re.sub(r'<link[^>]*href="%s"[^>]*>' % re.escape(CSS_URL),
                   lambda _m: css_block, h, count=1)
        h = re.sub(r'<script[^>]*src="%s"[^>]*></script>' % re.escape(JS_URL),
                   lambda _m: js_block, h, count=1)
        if CSS_URL in h or JS_URL in h:
            sys.exit(f"!! {path} still references the CDN after inlining — the tag shape must have changed")
        path.write_text(h)
        print(f"   {path.parent.name}/{path.name}: inlined "
              f"({before/1048576:.2f} -> {len(h)/1048576:.2f} MB, +{(len(h)-before)/1024:.0f} KB)")


if __name__ == '__main__':
    main()
