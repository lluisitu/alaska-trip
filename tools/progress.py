#!/usr/bin/env python3
"""
Where the research actually stands, per leg and per section.

    cd tools && python3 progress.py

Why two numbers
---------------
A single percentage was hiding two different things and making both of them
unreadable. "Leg 1 trails 97%" meant FINISHED — the one gap is a trail with no
listing anywhere. "Leg 1 shots 5/13" meant barely started. Same column, same
kind of number, opposite meanings.

So every cell shows:

    have   what is actually filled in, out of everything there is
    prog   what is done out of what CAN be done

`prog` reaches 100% when there is nothing left to research — including the items
that will never be fillable. Those are counted as BLOCKED, not as failures:

  * a trail the managing authority confirms exists and no database has indexed
    (Mesa Trail at Caprock — TPWD lists it, AllTrails never has)
  * a highlight with no entity in it at all ("Dawn and dusk wildlife watching
    from established roads and overlooks" — there is nothing to link to)
  * a dog rule the authority states for some trails and is silent on for others
    (Great Sand Dunes names Mosca Pass and the dunefield, says nothing about
    Montville — so that one stays blank rather than inheriting a guess)
  * a shot finding needing a coordinate nobody has published

The distinction matters because `have` will never reach 100% and pretending
otherwise means either inventing data or treating finished work as unfinished.
Blocked items are the honest floor.

Standard library only; no network. Reads the built page and the two dbs.
"""
import json, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / 'desktop' / 'index.html'
HERE = pathlib.Path(__file__).resolve().parent

# A headline with no proper noun has no entity to link to. This is the same
# test the resolver uses, run offline so no API call is needed to count it.
PROPER = re.compile(r'\b[A-Z][a-z\'’-]{2,}')
STOPWORD = {'Day', 'Drive', 'Visit', 'Walk', 'Hike', 'Wildlife', 'Dawn', 'Explore',
            'Stroll', 'Soak', 'Build', 'Final', 'Ride', 'See', 'Tour', 'Add', 'Spend'}


def has_entity(name):
    return any(w not in STOPWORD for w in PROPER.findall(name or ''))


def ex(hh, decl, o='[', c=']'):
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


def cell(have, blocked, total):
    """have/total, and have out of what is reachable."""
    reachable = total - blocked
    a = f"{100 * have // total:d}%" if total else "-"
    b = f"{100 * (have + blocked) // total:d}%" if total else "-"
    return a, b, blocked


HTML_HEAD = """<style>
:root{
  /* Grounded in the dashboard's own palette so this reads as part of it:
     the amber the trip cards use for accents, and the same green/amber/red
     it already uses for on-track / check-season / blocked. */
  --ink:#0f1319; --panel:#161b23; --panel2:#1c222b; --line:#28303b;
  --text:#e7ecf3; --muted:#8d99a9; --accent:#e8b04b;
  --done:#6fbf7f; --part:#e6a34a; --thin:#d9605f; --blocked:#5b6675;
}
@media (prefers-color-scheme: light){
  :root{ --ink:#f6f7f9; --panel:#fff; --panel2:#f0f2f5; --line:#dfe4ea;
         --text:#161b22; --muted:#5e6a78; --blocked:#9aa5b2; }
}
:root[data-theme="dark"]{ --ink:#0f1319; --panel:#161b23; --panel2:#1c222b; --line:#28303b;
  --text:#e7ecf3; --muted:#8d99a9; --blocked:#5b6675; }
:root[data-theme="light"]{ --ink:#f6f7f9; --panel:#fff; --panel2:#f0f2f5; --line:#dfe4ea;
  --text:#161b22; --muted:#5e6a78; --blocked:#9aa5b2; }
*{box-sizing:border-box}
body{margin:0;background:var(--ink);color:var(--text);
     font:15px/1.5 ui-sans-serif,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
     font-variant-numeric:tabular-nums;padding:28px 20px 48px}
.wrap{max-width:1080px;margin:0 auto;display:flex;flex-direction:column;gap:22px}
h1{margin:0;font-size:1.35rem;letter-spacing:-.01em}
.sub{margin:0;color:var(--muted);font-size:.86rem;max-width:70ch}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:10px}
.tile{background:var(--panel);border:1px solid var(--line);border-radius:11px;padding:12px 14px}
.tile b{display:block;font-size:1.5rem;font-weight:650;letter-spacing:-.02em}
.tile span{display:block;font-size:.7rem;color:var(--muted);text-transform:uppercase;letter-spacing:.06em;margin-top:2px}
.scroll{overflow-x:auto;background:var(--panel);border:1px solid var(--line);border-radius:12px}
table{border-collapse:collapse;width:100%;min-width:820px}
th,td{padding:9px 12px;text-align:left;border-bottom:1px solid var(--line)}
thead th{position:sticky;top:0;background:var(--panel2);font-size:.68rem;text-transform:uppercase;
         letter-spacing:.07em;color:var(--muted);font-weight:650;white-space:nowrap}
tbody tr:last-child td{border-bottom:none}
tr.total td{background:var(--panel2);font-weight:650}
td.leg{font-weight:600;white-space:nowrap}
.cellnum{display:flex;align-items:baseline;gap:6px;font-size:.82rem}
.cellnum i{font-style:normal;color:var(--muted);font-size:.72rem}
.bar{margin-top:5px;height:5px;border-radius:3px;background:var(--panel2);overflow:hidden;display:flex;min-width:86px}
.bar u{display:block;height:100%;text-decoration:none}
.b-done{background:var(--done)} .b-part{background:var(--part)} .b-thin{background:var(--thin)}
.b-blocked{background:var(--blocked)}
.key{display:flex;gap:16px;flex-wrap:wrap;color:var(--muted);font-size:.76rem;align-items:center}
.key i{display:inline-block;width:20px;height:5px;border-radius:3px;margin-right:6px;vertical-align:middle;font-style:normal}
footer{color:var(--muted);font-size:.76rem;line-height:1.6;max-width:76ch}
code{background:var(--panel2);padding:1px 5px;border-radius:4px;font-size:.85em}
</style>"""


def bar(have, blocked, total):
    if not total:
        return ''
    hp = 100 * have / total
    bp = 100 * blocked / total
    cls = 'b-done' if hp >= 80 else 'b-part' if hp >= 40 else 'b-thin'
    return (f'<div class="bar"><u class="{cls}" style="width:{hp:.1f}%"></u>'
            f'<u class="b-blocked" style="width:{bp:.1f}%"></u></div>')


def html_cell(have, blocked, total):
    if not total:
        return '<td><span class="cellnum">—</span></td>'
    a = 100 * have // total
    b = 100 * (have + blocked) // total
    extra = f'<i>{b}% w/ blocked</i>' if blocked else ''
    return (f'<td><span class="cellnum"><b>{a}%</b>{extra}</span>'
            f'{bar(have, blocked, total)}</td>')


def main():
    h = SRC.read_text()
    STOPS = json.loads(ex(h, 'const STOPS ='))
    EXT = json.loads(ex(h, 'const EXT_DATA =', '{', '}'))['STOPS']
    PHOTO = json.loads(ex(h, 'const PHOTO =', '{', '}'))
    db = json.loads((HERE / 'links_db.json').read_text())['stops']
    sdb = json.loads((HERE / 'shots_db.json').read_text())['shots']

    groups = [(lg, [x for x in STOPS if x['leg'] == lg]) for lg in
              ('leg1', 'leg2', 'leg3', 'leg4', 'leg5', 'leg6')] + [('EAST', EXT)]

    print(f"{'':9s}" + ''.join(f"{c:>17s}" for c in
                               ('trails', 'dogs', 'highlights', 'scenic', 'offroad', 'shot fixes')))
    print(f"{'':9s}" + ''.join(f"{'have  prog':>17s}" for _ in range(6)))
    print('-' * 111)
    tot = {k: [0, 0, 0] for k in ('tr', 'dg', 'hl', 'sc', 'of', 'sh')}
    html_rows = []

    def acc(k, have, blocked, total):
        tot[k][0] += have; tot[k][1] += blocked; tot[k][2] += total

    for name, L in groups:
        row, raw_cells, ids = [], [], {x['id'] for x in L}
        # trails: blocked when the db records that no listing exists
        t_h = t_b = t_t = 0
        for s in L:
            entry = db.get(s['id'], {})
            noted = {t['name'] for t in (entry.get('trails') or [])
                     if (t.get('alltrails') or {}).get('match') == 'none'
                     or (t.get('alltrails') or {}).get('tier') == 'unlisted'}
            for y in (s.get('alltrails') or []):
                t_t += 1
                if y.get('url'): t_h += 1
                elif y['name'] in noted: t_b += 1
        row.append(cell(t_h, t_b, t_t)); raw_cells.append((t_h, t_b, t_t)); acc('tr', t_h, t_b, t_t)

        # dogs: blocked where the authority is verdict-partial and silent on this trail
        d_h = d_b = d_t = 0
        for s in L:
            e = db.get(s['id'], {})
            partial = e.get('dogs_verdict') == 'partial'
            named = e.get('trail_dogs') or {}
            for y in (s.get('alltrails') or []):
                d_t += 1
                if 'dogs' in y: d_h += 1
                elif partial and named.get(y['name'], 'x') is None: d_b += 1
                elif partial: d_b += 1
        row.append(cell(d_h, d_b, d_t)); raw_cells.append((d_h, d_b, d_t)); acc('dg', d_h, d_b, d_t)

        # highlights: blocked when the headline contains no entity at all
        h_h = h_b = h_t = 0
        for s in L:
            for a in (s.get('activities') or []):
                h_t += 1
                if a.get('links'): h_h += 1
                elif not has_entity(a.get('name')): h_b += 1
        row.append(cell(h_h, h_b, h_t)); raw_cells.append((h_h, h_b, h_t)); acc('hl', h_h, h_b, h_t)

        for key, field in (('sc', 'scenicDrives'), ('of', 'offroad')):
            a_h = a_t = 0
            for s in L:
                for y in (s.get(field) or []):
                    a_t += 1
                    if y.get('url'): a_h += 1
            row.append(cell(a_h, 0, a_t)); raw_cells.append((a_h, 0, a_t)); acc(key, a_h, 0, a_t)

        # shot findings: blocked where marked so in shots_db
        f_h = f_b = f_t = 0
        for sid in ids:
            for sh in PHOTO.get(sid, []):
                spec = (sdb.get(sid) or {}).get(sh['title'], {})
                for f in (sh.get('flags') or []):
                    f_t += 1
                    if f.get('src') == 'fixed': f_h += 1
                    elif spec.get('blocked'): f_b += 1
        row.append(cell(f_h, f_b, f_t)); raw_cells.append((f_h, f_b, f_t)); acc('sh', f_h, f_b, f_t)

        print(f"{name:9s}" + ''.join(f"{a:>8s}{b:>9s}" for a, b, _ in row))
        html_rows.append((name, raw_cells))

    print('-' * 111)
    print(f"{'TRIP':9s}" + ''.join(
        f"{cell(*[tot[k][0], tot[k][1], tot[k][2]])[0]:>8s}{cell(*[tot[k][0], tot[k][1], tot[k][2]])[1]:>9s}"
        for k in ('tr', 'dg', 'hl', 'sc', 'of', 'sh')))
    blocked = sum(tot[k][1] for k in tot)
    print(f"\n{blocked} items counted as blocked — researched, and confirmed unfillable.")
    print("have = what is filled in.  prog = filled in, plus what never can be.")

    if '--html' in sys.argv:
        out = pathlib.Path(sys.argv[sys.argv.index('--html') + 1])
        cols = ('trails', 'dogs', 'highlights', 'scenic drives', 'offroad', 'shot fixes')
        keys = ('tr', 'dg', 'hl', 'sc', 'of', 'sh')
        rows = []
        for name, cells in html_rows:
            rows.append(f'<tr><td class="leg">{name}</td>'
                        + ''.join(html_cell(*c) for c in cells) + '</tr>')
        rows.append('<tr class="total"><td class="leg">Whole trip</td>'
                    + ''.join(html_cell(tot[k][0], tot[k][1], tot[k][2]) for k in keys) + '</tr>')
        unlinked = tot['tr'][2] - tot['tr'][0]
        openf = tot['sh'][2] - tot['sh'][0] - tot['sh'][1]
        nolink = tot['hl'][2] - tot['hl'][0] - tot['hl'][1]
        out.write_text(f"""<title>Alaska trip — research progress</title>{HTML_HEAD}
<div class="wrap">
<header style="display:flex;flex-direction:column;gap:6px">
  <h1>Research progress</h1>
  <p class="sub">Every stop card is built from six kinds of research. This is how much of each is
  actually done, per leg. The second figure in a cell adds the items that have been researched and
  found <em>unfillable</em> — a trail no database has indexed, a highlight with no entity in it, a
  correction needing a coordinate nobody has published. Those can never move.</p>
</header>
<div class="tiles">
  <div class="tile"><b>{unlinked}</b><span>trails still unlinked</span></div>
  <div class="tile"><b>{openf}</b><span>shot findings open</span></div>
  <div class="tile"><b>{nolink}</b><span>highlights without a link</span></div>
  <div class="tile"><b>{blocked}</b><span>confirmed unfillable</span></div>
</div>
<div class="scroll"><table>
<thead><tr><th>Leg</th>{''.join(f'<th>{c}</th>' for c in cols)}</tr></thead>
<tbody>{''.join(rows)}</tbody>
</table></div>
<div class="key">
  <span><i class="b-done"></i>80%+</span><span><i class="b-part"></i>40–79%</span>
  <span><i class="b-thin"></i>under 40%</span><span><i class="b-blocked"></i>researched, unfillable</span>
</div>
<footer>Generated by <code>tools/progress.py --html</code> from the built dashboard and the two research
databases — it reads the same data the site does, so it cannot drift from what is actually published.
Blocked items are the honest floor: the first figure will never reach 100%, and pretending otherwise
would mean either inventing data or treating finished work as unfinished.</footer>
</div>""", encoding='utf-8')
        print(f"wrote {out}")


if __name__ == '__main__':
    main()
