# -*- coding: utf-8 -*-
"""AHD5 US audio gap-fill for the 405 CALD3+Macmillan-uncovered words.

- Reads _work/ahd_coverage.json (word -> chosen audio ref).
- Maps words back to the Anki notes whose cald3_uk AND mald2_uk are both empty.
- Extracts the AHD5 audio from the .mdd. Source is genuine PCM WAV
  (11025 Hz, 16-bit, mono), so we write the bytes as-is (no re-encode,
  lossless, no ffmpeg).
- Name: ahd5_us_{word}.wav  -> separate folder _work/ahd5_us/.
- Sets the ahd5_us field to [sound:ahd5_us_{word}.wav] on those notes.
- Writes _work/ahd5_tags.json (noteId -> {word, filename, tag}).
"""
import re, os, json, sys
sys.path.insert(0, '_work')
sys.stdout.reconfigure(encoding='utf-8')
import mdict_utils.reader as r
from ac import ac
from build_uk import clean

AHD_MDD = 'AHD5/AHD52017.mdd'
OUT = '_work/ahd5_us'
os.makedirs(OUT, exist_ok=True)


def slug(word):
    w = word.lower().replace(' ', '_').replace('-', '_').replace('/', '_')
    w = re.sub(r'[^a-z0-9_.]+', '', w)
    return w.strip('._') or 'word'


coverage = json.load(open('_work/ahd_coverage.json', encoding='utf-8'))
hits = coverage['hits']   # word -> {hw, audio, all, how}

# ---- map words back to notes (cald3_uk AND mald2_uk both empty) ----
nids = ac('findNotes', query='deck:"01_g6_260916"')
infos = ac('notesInfo', notes=nids)
print('[Anki] notes=%d' % len(infos), flush=True)

word_to_notes = {}   # word -> [noteId, ...]
for ni in infos:
    f = ni['fields']
    if (f.get('cald3_uk') or {}).get('value', '').strip():
        continue
    if (f.get('mald2_uk') or {}).get('value', '').strip():
        continue
    w = clean((f.get('wb') or f.get('word') or {}).get('value', ''))
    word_to_notes.setdefault(w, []).append(ni['noteId'])

# select the notes that have a matching AHD audio
plan = []   # {word, ref, outfile, nids}
unmatched_words = []
for word, v in sorted(hits.items()):
    nids = word_to_notes.get(word, [])
    if not nids:
        unmatched_words.append(word)
        continue
    ref = v['audio']
    outfile = 'ahd5_us_%s.wav' % slug(word)
    plan.append({'word': word, 'ref': ref, 'outfile': outfile, 'nids': nids})

print('plan entries: %d' % len(plan), flush=True)
if unmatched_words:
    print('WARNING words without a matching note: %d -> %s' %
          (len(unmatched_words), unmatched_words[:20]), flush=True)

# ---- extract the needed .wav bytes from the .mdd ----
needed = {}   # mdd_key -> entry
for p in plan:
    key = p['ref'].replace('/', '\\')   # /wavs/X.wav -> \wavs\X.wav
    needed[key] = p

extracted = {}   # mdd_key -> bytes
print('scanning AHD5 MDD for %d files...' % len(needed), flush=True)
for name, data in r.MDD(AHD_MDD).items():
    n = name.decode('utf-8', 'replace') if isinstance(name, bytes) else str(name)
    if n in needed or n.lower() in needed:
        extracted[n] = data
# case-insensitive fallback
for k, p in list(needed.items()):
    if k not in extracted:
        lk = k.lower()
        for n2, d2 in extracted.items():
            if n2.lower() == lk:
                p['_key'] = n2
                break

print('extracted %d/%d raw files' % (len(extracted), len(needed)), flush=True)

# ---- write audio files ----
ok = fail = 0
for p in plan:
    key = p['ref'].replace('/', '\\')
    data = extracted.get(key)
    if data is None and '_key' in p:
        data = extracted.get(p['_key'])
    if data is None:
        fail += 1
        print('MISS', p['word'], p['ref'], flush=True)
        continue
    # sanity: RIFF/WAVE header
    if not (data[:4] == b'RIFF' and data[8:12] == b'WAVE'):
        fail += 1
        print('BAD-HEADER', p['word'], p['ref'], data[:8], flush=True)
        continue
    with open(os.path.join(OUT, p['outfile']), 'wb') as f:
        f.write(data)
    ok += 1
print('wrote ok=%d fail=%d -> %s' % (ok, fail, OUT), flush=True)

# ---- set ahd5_us field on the notes ----
tags = {}
set_ok = set_fail = 0
for p in plan:
    if not os.path.exists(os.path.join(OUT, p['outfile'])):
        continue
    tag = '[sound:%s]' % p['outfile']
    for nid in p['nids']:
        try:
            ac('updateNoteFields', note={'id': nid, 'fields': {'ahd5_us': tag}})
            set_ok += 1
            tags[str(nid)] = {'word': p['word'], 'filename': p['outfile'], 'tag': tag}
        except Exception as e:
            set_fail += 1
            print('SET-FAIL', nid, p['word'], str(e)[:120], flush=True)

json.dump(tags, open('_work/ahd5_tags.json', 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
print('set ahd5_us on %d notes (fail %d)' % (set_ok, set_fail), flush=True)
print('ahd5_tags.json: %d notes' % len(tags), flush=True)
