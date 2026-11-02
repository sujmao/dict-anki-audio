# -*- coding: utf-8 -*-
"""Remove AHD5 non-exact matches: keep ONLY 'direct' (recording == card word).

The user requires the card's audio to correspond EXACTLY to the card word.
Non-exact tiers (recording = a related base/variant word) must be removed:
  - link     (AHD5 @@@LINK derived-form redirects, e.g. anticipatory->anticipate)
  - derived  (my affix-stripping, e.g. blighted->blight)
  - manual   (hardcoded overrides, e.g. spined->spine)
Actions: blank the ahd5_us field on those notes + delete their .wav files.
"""
import os, json, sys
sys.path.insert(0, '_work')
sys.stdout.reconfigure(encoding='utf-8')
from ac import ac

cov = json.load(open('_work/ahd_coverage.json', encoding='utf-8'))
tags = json.load(open('_work/ahd5_tags.json', encoding='utf-8'))

how_of = {w: v['how'] for w, v in cov['hits'].items()}

keep = 0
blanked = 0
deleted = 0
not_found = []

for nid, t in tags.items():
    word = t['word']
    how = how_of.get(word)
    if how == 'direct':
        keep += 1
        continue
    # non-exact -> blank the field
    try:
        ac('updateNoteFields', note={'id': int(nid), 'fields': {'ahd5_us': ''}})
        blanked += 1
    except Exception as e:
        print('BLANK-FAIL', nid, word, str(e)[:120], flush=True)
        continue
    # delete the audio file
    fn = t['filename']
    p = os.path.join('_work/ahd5_us', fn)
    if os.path.exists(p):
        os.remove(p)
        deleted += 1
    else:
        not_found.append(fn)

print('exact kept   : %d' % keep)
print('blanked notes: %d' % blanked)
print('deleted files: %d' % deleted)
if not_found:
    print('files not found (%d):' % len(not_found), not_found[:20])

# remaining files in the folder
remaining = sorted(os.listdir('_work/ahd5_us'))
print('files remaining in _work/ahd5_us/: %d' % len(remaining))

# corrected coverage
exact_words = [w for w, v in cov['hits'].items() if v['how'] == 'direct']
non_exact_words = sorted(w for w, v in cov['hits'].items() if v['how'] != 'direct')
uncovered = sorted(set(cov['miss_words']) | set(non_exact_words))
print('exact words: %d | non-exact removed: %d | total uncovered now: %d'
      % (len(exact_words), len(non_exact_words), len(uncovered)))

json.dump({'exact_covered': len(exact_words),
           'exact_words': sorted(exact_words),
           'removed_non_exact': non_exact_words,
           'uncovered': uncovered,
           'uncovered_count': len(uncovered)},
          open('_work/ahd_exact_only.json', 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
print('wrote _work/ahd_exact_only.json')
