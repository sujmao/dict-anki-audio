# -*- coding: utf-8 -*-
"""Blank cald3_uk for the 32 synonym-fold notes (wrong audio from a different
headword). Idempotent. These words become candidates for the US gap-fill pass."""
import sys, json, time
sys.path.insert(0, '_work')
sys.stdout.reconfigure(encoding='utf-8')
from ac import ac

sf = json.load(open('_work/synonym_filter.json', encoding='utf-8'))
nids = sorted(int(x) for x in sf)
print('blanking cald3_uk on %d synonym-fold notes' % len(nids), flush=True)

ok = fail = 0
fails = []
t0 = time.time()
for i, nid in enumerate(nids, 1):
    try:
        ac('updateNoteFields', note={'id': nid, 'fields': {'cald3_uk': ''}})
        ok += 1
    except Exception as e:
        fail += 1
        fails.append((nid, str(e)[:120]))
print('DONE ok=%d fail=%d (%.1fs)' % (ok, fail, time.time() - t0), flush=True)
if fails:
    json.dump(fails, open('_work/blank_synonym_fail.json', 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print('failures -> _work/blank_synonym_fail.json', flush=True)
