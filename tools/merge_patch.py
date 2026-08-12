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

# Lists inside a stop entry that are keyed by 'name'.
NAMED_LISTS = ('trails', 'offroad', 'scenicDrives_patch', 'not_a_trail', 'not_a_route')
# Dicts inside a stop entry that merge key by key.
MERGE_DICTS = ('activities', 'trail_dogs')


def merge_stop(cur, new, sid, log, force):
    for key, val in new.items():
        if key in MERGE_DICTS and isinstance(val, dict):
            dst = cur.setdefault(key, {})
            for k, v in val.items():
                if k in dst and dst[k] != v and key not in force:
                    log.append(f'  CONFLICT {sid}.{key}[{k[:40]!r}] already set, skipped')
                    continue
                if k not in dst:
                    log.append(f'  + {sid}.{key}[{k[:40]!r}]')
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
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    write = '--write' in sys.argv
    force = set()
    for i, a in enumerate(sys.argv):
        if a == '--force-field' and i + 1 < len(sys.argv):
            force.add(sys.argv[i + 1])
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
            if sid not in db['stops']:
                log.append(f'  UNKNOWN STOP {sid!r} — skipped, id matches nothing')
                continue
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
