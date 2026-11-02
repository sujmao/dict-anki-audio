# -*- coding: utf-8 -*-
"""Set mald2_uk = [sound:...] on the 193 Macmillan-supplemented notes."""
import sys, json, time
sys.path.insert(0, '_work')
sys.stdout.reconfigure(encoding='utf-8')
from ac import ac

tags = json.load(open('_work/mald2_tags.json', encoding='utf-8'))
targets = [(int(nid), v['tag']) for nid, v in tags.items()]
print('PHASE set-mald2-tags: notes=%d' % len(targets), flush=True)

ok = fail = 0
fails = []
t0 = time.time()
for i, (nid, tag) in enumerate(targets, 1):
    try:
        ac('updateNoteFields', note={'id': nid, 'fields': {'mald2_uk': tag}})
        ok += 1
    except Exception as e:
        fail += 1
        fails.append((nid, str(e)[:120]))
    if i % 100 == 0 or i == len(targets):
        print('  %d/%d ok=%d fail=%d' % (i, len(targets), ok, fail), flush=True)

print('DONE ok=%d fail=%d (%.1fs)' % (ok, fail, time.time() - t0), flush=True)
if fails:
    json.dump(fails, open('_work/set_mald2_fail.json', 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print('failures -> _work/set_mald2_fail.json', flush=True)
