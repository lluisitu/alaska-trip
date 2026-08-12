#!/usr/bin/env python3
"""
Merge a research patch into links_db.json. Merge, never replace.

    cd tools && python3 merge_patch.py ../path/to/patch.json          # dry run
    cd tools && python3 merge_patch.py ../path/to/patch.json --write

Why this exists
---------------
Research arrives as patch files — one per agent, one per region — and every
one of them has to land in links_db.json without destroying what is already
there. The first time this was done by hand, a wholesale list assignment
deleted Santa Fe's five researched trails and Estes Park's six, because the
patch only carried the stop's *new* entries and the merge treated the list as
the whole truth. Lists here are keyed by `name` and merged item by item.

What it will not do
-------------------
* Overwrite a field that already has a value with a different value. That is
  reported as a CONFLICT and skipped, because two sources disagreeing is a
  research question, not something a script should silently resolve. Pass
  --force-field NAME to let a specific field be overwritten.
* Add a list item whose `name` matches nothing when the patch is flagged
  --strict-names. Name matching is exact, and a one-character drift means the
  work silently does nothing — that failure has cost three commits on this
  repo already, so it is reported loudly either way.

Nothing here touches desktop/index.html. Run the build loop afterwards.
"""
import json, pathlib, sys

HERE = pathlib.Path(__file__).resolve().parent
DB = HERE / 'links_db.json'
SRC = HERE.parent / 'desktop' / 'index.html'


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


def itinerary_ids():
    h = SRC.read_text()
    main = json.loads(ex(h, 'const STOPS ='))
    east = json.loads(ex(h, 'const EXT_DATA =', '{', '}'))['STOPS']
    return {s['id'] for s in main} | {s['id'] for s in east}


ITINERARY = itinerary_ids()

# Lists inside a stop entry that are keyed by 'name'.
NAMED_LISTS = ('trails', 'offroad', 'scenicDrives_patch', 'not_a_trail', 'not_a_route')
# Dicts inside a stop entry that merge key by key.
MERGE_DICTS = ('activities', 'trail_dogs')


def negative_finding(field, old, new):
    """True when `old` records a failed search and `new` actually found the thing.

    `{"match": "none", "tier": "unlisted"}` does not mean "there is no listing".
    It means "this pass did not find one" — and a domain-restricted search
    returns FEWER AllTrails results than an open search does, which is how
    Warner Point, Horse Gulch and Piedra River were all filed as unlisted while
    having perfectly good listings. A later pass that produces a url supersedes
    the negative, the same way a null trail_dogs is superseded by a real rule.

    The reverse is NOT symmetric: a url replaced by "none" is a real conflict
    and stops, because that is either a dead link or a worse search.
    """
    if field != 'alltrails' or not isinstance(old, dict) or not isinstance(new, dict):
        return False
    return not old.get('url') and bool(new.get('url'))


def merge_stop(cur, new, sid, log, force):
    for key, val in new.items():
        if key in MERGE_DICTS and isinstance(val, dict):
            dst = cur.setdefault(key, {})
            for k, v in val.items():
                # null is not "already set". In trail_dogs it means the exact
                # opposite: researched, and the authority said nothing. A later
                # pass that DOES find the rule supersedes it. Only a real value
                # disagreeing with a real value is a conflict worth stopping on.
                if k in dst and dst[k] is not None and dst[k] != v and key not in force:
                    log.append(f'  CONFLICT {sid}.{key}[{k[:40]!r}] = {dst[k]!r}, patch says {v!r} — skipped')
                    continue
                if k not in dst:
                    log.append(f'  + {sid}.{key}[{k[:40]!r}]')
                elif dst[k] is None and v is not None:
                    log.append(f'  RESOLVED {sid}.{key}[{k[:40]!r}] was silent, now {v!r}')
                dst[k] = v
        elif key in NAMED_LISTS and isinstance(val, list):
            dst = cur.setdefault(key, [])
            index = {i.get('name'): i for i in dst if isinstance(i, dict)}
            for item in val:
                name = item.get('name')
                if name in index:
                    tgt = index[name]
                    for f, v in item.items():
                        if f == 'name':
                            continue
                        if f in tgt and tgt[f] != v and f not in force:
                            if negative_finding(f, tgt[f], v):
                                log.append(f'  SUPERSEDED {sid}.{key}[{name[:36]!r}].{f} '
                                           f'was "no listing", now found')
                            else:
                                log.append(f'  CONFLICT {sid}.{key}[{name[:36]!r}].{f} already set, skipped')
                                continue
                        tgt[f] = v
                    log.append(f'  ~ {sid}.{key}[{name[:36]!r}] merged')
                else:
                    dst.append(item)
                    log.append(f'  NEW-NAME {sid}.{key}[{name[:36]!r}] matched nothing — appended')
        else:
            if key in cur and cur[key] != val and key not in force:
                log.append(f'  CONFLICT {sid}.{key} already set, skipped')
                continue
            if key not in cur:
                log.append(f'  + {sid}.{key}')
            cur[key] = val


def main():
    write = '--write' in sys.argv
    force, args, skip = set(), [], False
    for i, a in enumerate(sys.argv[1:]):
        if skip:                       # the value of --force-field is not a path
            force.add(a); skip = False
        elif a == '--force-field':
            skip = True
        elif not a.startswith('--'):
            args.append(a)
    if not args:
        sys.exit('usage: merge_patch.py PATCH.json [more.json ...] [--write] [--force-field F]')

    db = json.loads(DB.read_text())
    log = []
    for path in args:
        patch = json.loads(pathlib.Path(path).read_text())
        stops = patch.get('stops', patch)
        log.append(f'== {pathlib.Path(path).name}: {len(stops)} stops')
        for sid, entry in stops.items():
            if not isinstance(entry, dict):
                continue
            # The guard is "is this a real stop on the itinerary", NOT "does
            # links_db already carry it". Most east-extension stops have only
            # an `activities` key so far and several have no entry at all;
            # checking against links_db threw away a whole stop's research.
            if sid not in ITINERARY:
                log.append(f'  UNKNOWN STOP {sid!r} — skipped, matches no stop in STOPS or EXT_DATA')
                continue
            if sid not in db['stops']:
                log.append(f'  NEW STOP {sid!r} — first research for this stop')
                db['stops'][sid] = {}
            merge_stop(db['stops'][sid], entry, sid, log, force)

    for line in log:
        print(line)
    conflicts = sum(1 for l in log if 'CONFLICT' in l)
    newnames = sum(1 for l in log if 'NEW-NAME' in l)
    unknown = sum(1 for l in log if 'UNKNOWN STOP' in l)
    print(f'\n{len(log)} operations | {conflicts} conflicts skipped | '
          f'{newnames} names matched nothing | {unknown} unknown stops')
    if write:
        DB.write_text(json.dumps(db, ensure_ascii=False, indent=2) + '\n')
        print('written to links_db.json')
    else:
        print('(dry run — pass --write to save)')


if __name__ == '__main__':
    main()
