# -*- coding: utf-8 -*-
"""Set audio_uk = [sound:cald3_uk_...m4a] on each note (5911), via AnkiConnect.
Idempotent. Progress with rate + ETA."""
import os, sys, json, time
sys.path.insert(0, '_work')
sys.stdout.reconfigure(encoding='utf-8')
from ac import ac

tags = json.load(open('_work/audio_tags.json', encoding='utf-8'))
targets = [(int(nid), v['tag']) for nid, v in tags.items()]
print('PHASE set-tags: notes=%d' % len(targets), flush=True)

ok = fail = 0
fails = []
t0 = time.time()
for i, (nid, tag) in enumerate(targets, 1):
    try:
        ac('updateNoteFields', note={'id': nid, 'fields': {'audio_uk': tag}})
        ok += 1
    except Exception as e:
        fail += 1
        fails.append((nid, str(e)[:120]))
    if i % 500 == 0 or i == len(targets):
        el = time.time() - t0
        rate = i / el if el > 0 else 0
        eta = (len(targets) - i) / rate if rate > 0 else 0
        print('  %d/%d ok=%d fail=%d rate=%.1f/s ETA=%.0fs' %
              (i, len(targets), ok, fail, rate, eta), flush=True)

print('DONE ok=%d fail=%d (%.1fs)' % (ok, fail, time.time() - t0), flush=True)
if fails:
    json.dump(fails, open('_work/set_tag_fail.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('failures -> _work/set_tag_fail.json', flush=True)
