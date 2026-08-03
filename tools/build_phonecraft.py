#!/usr/bin/env python3
"""
Add iPhone settings and live-conditions links to every shot in the shot list.

    cd tools && python3 build_phonecraft.py

Two things the shot list was missing.

First, the craft note is written for a camera. Most pictures on this trip will be
made on a phone, and the phone advice is genuinely different - not "same thing but
worse". Night mode with the slider dragged to Max on a tripod is a real 30-second
exposure, which no phone could do a few years ago, and it is the single technique
that turns an iPhone into an aurora camera. But 30 seconds is not always right:
a fast substorm smears at that length, and the answer is a SHORTER exposure, which
is the opposite of the advice every guide gives.

Second, several shots depend on conditions nobody can predict months ahead - the
aurora above all, but also fire closures and road status. Those need a link you
tap on the night, not a paragraph written in 2026.

Both are derived from what each shot already says, so this stays in step with the
shot list rather than being a second thing to maintain.

Standard library only; no network.
"""
import json, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / 'desktop' / 'index.html'


def ex(hh, decl, o='{', c='}'):
    i = hh.index(decl); s = hh.index(o, i); d = 0; ins = False; esc = False
    for j in range(s, len(hh)):
        ch = hh[j]
        if ins:
            if esc: esc = False
            elif ch == '\\': esc = True
            elif ch == '"': ins = False
        else:
            if ch == '"': ins = True
            elif ch == o: d += 1
            elif ch == c:
                d -= 1
                if d == 0: return hh[s:j + 1]
    raise ValueError('unterminated: ' + decl)


AURORA_LINKS = [
    {'label': 'UAF aurora forecast (Alaska & Yukon)', 'url': 'https://www.gi.alaska.edu/monitors/aurora-forecast'},
    {'label': 'NOAA 30-minute OVATION forecast', 'url': 'https://www.swpc.noaa.gov/products/aurora-30-minute-forecast'},
]

# The phone advice, by what the shot actually is.
IPHONE = {
 'aurora':
   "Night mode, slider dragged to **Max**. On a tripod that is a true 30s; handheld the phone caps you "
   "around 10s because it detects the shake. Set the 3s timer so pressing the button does not move it. "
   "Focus is the part that goes wrong: tap a bright star or a distant town light, hold until AE/AF LOCK "
   "appears, then do not touch the screen again. Shoot ProRAW if you have a 12 Pro or later — aurora "
   "colour lives in the shadows and JPEG throws that away.\n\n"
   "The exposure length is a judgement, not a setting. Max is right for a faint diffuse glow. When the "
   "aurora is moving and structured — the display worth being there for — 30s smears the curtains into "
   "a green fog. Drop to 3-8s and take the noise; the structure is the picture.",
 'night':
   "Night mode on a tripod with the slider at Max, 3s timer. Tap-and-hold on a light to lock focus at "
   "infinity before it gets fully dark, or the phone will hunt. ProRAW if you have it. Turn the flash off "
   "explicitly — auto will fire and kill the frame.",
 'blue':
   "Blue hour is the one time a phone genuinely matches a camera: enough light for a short Night mode "
   "exposure, and the sky holds colour a sensor renders well. Tripod, 1-3s, tap to expose for the sky and "
   "let the land go dark. Shoot it 20 minutes later than feels right — the best blue is after most people "
   "have packed up.",
 'tele':
   "This one is hard on a phone and worth being honest about. Use the longest real lens you have — the 5x "
   "on a 15 Pro/16 Pro or later, 3x before that — and never the digital zoom past it, which is a crop "
   "pretending to be a lens. Lock exposure on the subject, not the sky. If the subject is far and small, "
   "the phone will lose it; this is the category where a camera still wins outright.",
 'wide':
   "0.5x ultra-wide, and get much closer to the foreground than feels right — a wide lens with nothing in "
   "front of it makes everything look small and far away. Tap the sky and pull exposure down a third; "
   "phones over-brighten landscapes. ProRAW if you plan to edit.",
 'people':
   "1x, not the ultra-wide, which distorts faces. Portrait mode only in decent light — it guesses edges "
   "badly on hats, hair and gear. Lock exposure on the face by tapping it, then hold to lock so it does "
   "not jump between frames. Burst by holding the shutter for anything moving.",
 'water':
   "For silk on moving water use Live Photo, then swipe up on the image and choose **Long Exposure** — "
   "that is a free ND filter and it works well. Needs a tripod or a rock. In bright light a screw-on ND "
   "is the only way to get a true long exposure, which is rarely worth carrying.",
 'wildlife':
   "Realistically: a phone photographs wildlife badly unless it is close, and getting close is the thing "
   "you must not do. Use the longest optical lens, shoot bursts, and accept that most of these are records "
   "rather than pictures. Better to film 4K and pull a frame than to crop a still.",
 'general':
   "1x is the sharpest lens on the phone; use it unless there is a reason not to. Tap to set exposure, "
   "hold to lock it. Shoot ProRAW if you will edit, HEIC if you will not. Wipe the lens — a smeared "
   "phone lens is the most common cause of a soft picture and nobody ever checks.",
}

ADDONS = ("**Worth carrying.** A small tripod with a MagSafe or clamp mount — this is the one that "
          "changes what the phone can do, because Max Night mode needs it. Spare battery or a power bank: "
          "cold kills phone batteries fast, and every aurora night on this trip is below freezing. A "
          "microfibre cloth.\n\n"
          "**Not worth it.** Clip-on lenses degrade a modern iPhone more than they add. Screw-on ND "
          "filters, when Live Photo's Long Exposure does the same job for free. A Bluetooth shutter "
          "remote, when the built-in 3s timer solves the same shake problem.")


def classify(shot):
    t = ' '.join(str(shot.get(k) or '') for k in ('title', 'subject', 'light', 'craft')).lower()
    if 'aurora' in t or 'northern lights' in t: return 'aurora'
    if 'milky way' in t or 'star' in t and 'iso' in t: return 'night'
    if 'blue hour' in t: return 'blue'
    if any(w in t for w in ('bear', 'moose', 'bighorn', 'elk', 'pronghorn', 'eagle', 'whale',
                            'bison', 'wolf', 'caribou', 'bird')): return 'wildlife'
    if re.search(r'\b(2\d{2}|[3-9]\d{2})\s*[–\-]?\s*\d*\s*mm', t): return 'tele'
    if any(w in t for w in ('waterfall', 'long exposure', 'silky', 'cascade', 'surf')): return 'water'
    if any(w in t for w in ('portrait', 'parade', 'people', 'faces', 'reportage', 'street',
                            'climbers', 'crowd')): return 'people'
    if re.search(r'\b(14|16|20|24)\s*[–\-]?\s*\d*\s*mm', t) or 'ultra-wide' in t: return 'wide'
    return 'general'


def main():
    h = SRC.read_text()
    raw = ex(h, 'const PHOTO =')
    PHOTO = json.loads(raw)
    counts, n = {}, 0
    for sid, shots in PHOTO.items():
        for sh in shots:
            kind = classify(sh)
            counts[kind] = counts.get(kind, 0) + 1
            sh['iphone'] = IPHONE[kind]
            sh['iphoneKind'] = kind
            links = []
            if kind == 'aurora':
                links += AURORA_LINKS
            if sh.get('lat') and sh.get('lng'):
                links.append({'label': 'Open this vantage in Maps',
                              'url': f"https://www.google.com/maps/search/?api=1&query={sh['lat']},{sh['lng']}"})
            if links: sh['links'] = links
            n += 1
    h = h.replace(raw, json.dumps(PHOTO, ensure_ascii=False), 1)

    # ex() brace-matches, and it treats a double quote as a string delimiter rather
    # than as a bracket — so it can never extract a quoted string. That worked on the
    # first run, which takes the insert branch, and blew up on every run after, which
    # is the branch publish.sh actually uses. Match the JSON string properly instead.
    payload = json.dumps(ADDONS, ensure_ascii=False)
    decl_re = re.compile(r'const PHONE_ADDONS = "(?:[^"\\]|\\.)*";')
    if decl_re.search(h):
        h = decl_re.sub(lambda _m: f'const PHONE_ADDONS = {payload};', h, count=1)
    else:
        anchor = 'const PHOTO ='
        assert anchor in h, 'PHOTO declaration missing — run the shot-list build first'
        h = h.replace(anchor, f'const PHONE_ADDONS = {payload};\n\n' + anchor, 1)

    SRC.write_text(h)
    print(f"  {n} shots given iPhone settings")
    for k, v in sorted(counts.items(), key=lambda kv: -kv[1]):
        print(f"     {k:<10}{v:>4}")
    aur = sum(1 for s in PHOTO.values() for x in s if x.get('iphoneKind') == 'aurora')
    print(f"  {aur} aurora shots carry live forecast links")
    print("wrote", SRC)


if __name__ == '__main__':
    main()
