# -*- coding: utf-8 -*-
"""Macmillan UK supplement for the 613 CALD3-uncovered words.

- Match each uncovered word -> Macmillan headword (variant-normalized).
- When a headword has several UK audios (homograph senses), disambiguate with
  the card's POS hint against each sense's POS label.
- Extract the UK audio (MP3-in-WAV) from the .mdd, REMUX to .mp3 (bitstream
  copy, no re-encode -> no quality loss).
- Name: mald2_uk_{word}_{Nth}.mp3  (Nth = position of the selected UK audio
  among ALL sound:// links in the resolved entry, 1-based).
- Output to _work/mald2_uk/ (a SEPARATE folder from cald3).
- Writes _work/mald2_tags.json (noteId -> {word, filename, tag}).
"""
import re, os, json, sys, subprocess
sys.path.insert(0, '_work')
sys.stdout.reconfigure(encoding='utf-8')
import mdict_utils.reader as r
from ac import ac
from build_uk import clean, fold, word_candidates, card_pos, POS_MAP
from variants import normalize

FF = r'E:\Videos\yt-dlp\ffmpeg-2024-03-14-git-2129d66a66-full_build\bin\ffmpeg.exe'
MALD_MDX = 'mald2/Macmillan English Dictionary for Advanced Learners.mdx'
MALD_MDD = 'mald2/Macmillan English Dictionary for Advanced Learners.mdd'
OUT = '_work/mald2_uk'
TMP = '_work/mald2_uk/_tmp'
os.makedirs(OUT, exist_ok=True)
os.makedirs(TMP, exist_ok=True)

UK_RE = re.compile(r'href="sound://(zzz_uk_[^"]+\.wav)"')
ALL_RE = re.compile(r'href="sound://([^"]+\.wav)"')
POS_RE = re.compile(r'<font color="#6020ae">\s*([a-zA-Z ]+?)\s*</font>')


def slug(word):
    w = word.lower().replace(' ', '_').replace('-', '_').replace('/', '_')
    w = re.sub(r'[^a-z0-9_.]+', '', w)
    return w.strip('._') or 'word'


def parse_mald_senses(body):
    """Per-sense list of {uk, pos} (homograph senses are split on ▪)."""
    senses = []
    for p in re.split(r'▪', body):
        ukm = UK_RE.search(p)
        if not ukm:
            continue
        pos = None
        pm = POS_RE.search(p)
        if pm:
            pos = pm.group(1).strip().lower()
        senses.append({'uk': ukm.group(1), 'pos': pos})
    return senses


# ---- 1. parse MDX -> headword lookups ----
print('parsing Macmillan MDX...', flush=True)
norm_lookup = {}   # normalize(hw) -> {'hw','senses','all'}
fold_lookup = {}   # fold(hw) -> same (irregular-inflection fallback)
for k, v in r.MDX(MALD_MDX).items():
    hw = k.decode('utf-8', 'replace')
    body = v.decode('utf-8', 'replace')
    rec = {'hw': hw, 'senses': parse_mald_senses(body),
           'all': ALL_RE.findall(body)}
    norm_lookup.setdefault(normalize(hw), rec)
    fold_lookup.setdefault(fold(hw), rec)
print('norm headwords=%d  fold headwords=%d' % (len(norm_lookup), len(fold_lookup)), flush=True)


def match_entry(word):
    for c in [word] + word_candidates(word):
        e = norm_lookup.get(normalize(c))
        if e:
            return e
    for c in word_candidates(word):
        e = fold_lookup.get(fold(c))
        if e and e['senses']:
            return e
    return None


# ---- 2. fetch uncovered notes ----
nids = ac('findNotes', query='deck:"01_g6_260916"')
infos = ac('notesInfo', notes=nids)
print('[Anki] notes=%d' % len(infos), flush=True)

uncovered = []   # (noteId, word, ci)
for ni in infos:
    f = ni['fields']
    if (f.get('cald3_uk') or {}).get('value', '').strip():
        continue
    w = clean((f.get('wb') or f.get('word') or {}).get('value', ''))
    ci = (f.get('ci') or {}).get('value', '')
    uncovered.append((ni['noteId'], w, ci))
print('uncovered notes: %d' % len(uncovered), flush=True)


# ---- 3. match + select (POS disambiguation for multi-UK) ----
selected = []
multi = []
no_uk = []
for nid, word, ci in uncovered:
    e = match_entry(word)
    if not e or not e['senses']:
        no_uk.append((nid, word))
        continue
    senses = e['senses']
    hints = card_pos(ci)
    # pick the sense whose POS matches the card; else first sense
    pick = senses[0]
    if len(senses) > 1:
        multi.append((nid, word, [(s['uk'], s['pos']) for s in senses], sorted(hints)))
        for s in senses:
            if s['pos'] and hints and s['pos'] in hints:
                pick = s
                break
    src = pick['uk']
    idx = (e['all'].index(src) + 1) if src in e['all'] else 1
    outfile = 'mald2_uk_%s_%d.mp3' % (slug(word), idx)
    selected.append({'nid': nid, 'word': word, 'src': src, 'idx': idx,
                     'outfile': outfile, 'hw': e['hw'], 'pos': pick['pos']})

print('selected (Macmillan UK): %d' % len(selected), flush=True)
print('multi-UK disambiguated: %d' % len(multi), flush=True)
for nid, word, pairs, hints in multi:
    print('   MULTI', word, 'card_pos=', hints, '->', pairs)
print('no Macmillan UK: %d' % len(no_uk), flush=True)

# ---- 4. extract + remux from MDD ----
needed = {('\\' + s['src']): s for s in selected}
need_lc = {('\\' + s['src']).lower(): s for s in selected}

extracted = {}
print('scanning MDD for %d files...' % len(needed), flush=True)
for name, data in r.MDD(MALD_MDD).items():
    n = name.decode('utf-8', 'replace') if isinstance(name, bytes) else str(name)
    s = needed.get(n) or need_lc.get(n.lower())
    if s:
        extracted[s['src']] = data
print('extracted %d/%d raw files' % (len(extracted), len(needed)), flush=True)

missing = [s['src'] for s in selected if s['src'] not in extracted]
if missing:
    print('MISSING MDD files (%d):' % len(missing), flush=True)
    for m in missing[:20]:
        print('   ', m)

ok = fail = 0
for s in selected:
    if s['src'] not in extracted:
        continue
    tmp = os.path.join(TMP, s['src'].replace('/', '_'))
    dst = os.path.join(OUT, s['outfile'])
    with open(tmp, 'wb') as f:
        f.write(extracted[s['src']])
    r = subprocess.run([FF, '-y', '-hide_banner', '-loglevel', 'error',
                        '-i', tmp, '-c:a', 'copy', '-f', 'mp3', dst],
                       capture_output=True, text=True)
    if r.returncode == 0 and os.path.exists(dst) and os.path.getsize(dst) > 0:
        ok += 1
    else:
        fail += 1
        print('FAIL', s['word'], s['src'], r.stderr[:120])
    try:
        os.remove(tmp)
    except OSError:
        pass
print('remuxed ok=%d fail=%d -> %s' % (ok, fail, OUT), flush=True)

# ---- 5. write tags ----
tags = {}
for s in selected:
    if s['src'] not in extracted:
        continue
    tags[str(s['nid'])] = {'word': s['word'], 'filename': s['outfile'],
                           'tag': '[sound:%s]' % s['outfile']}
json.dump(tags, open('_work/mald2_tags.json', 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
print('mald2_tags.json: %d notes' % len(tags), flush=True)

still = sorted(w for nid, w in no_uk)
json.dump({'count': len(still), 'words': still},
          open('_work/still_uncovered.json', 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
print('still uncovered (CALD3+Macmillan): %d -> _work/still_uncovered.json' % len(still), flush=True)
