# -*- coding: utf-8 -*-
"""Compute the naming index (第幾個音頻) for each selected UK audio.

Outputs _work/uk_naming.json: noteId -> {word, spx, index, newfile}
where newfile = cald3_uk_{word}_{index}.wav  (index = 1-based position of the
selected .spx among ALL audio links in the resolved dictionary entry, doc order).
"""
import re, json, sys, unicodedata
from collections import defaultdict
sys.path.insert(0, '_work')
import mdict_utils.reader as r
from build_uk import clean, fold, word_candidates

sys.stdout.reconfigure(encoding='utf-8')

CALD_MDX = 'cald3/剑桥高阶英英 CALD3_v1.4.mdx'
LINK_RE = re.compile(rb'@@@LINK=([^\r\n]+)')
AUDIO_RE = re.compile(r'href="sound://([^"]+\.spx)"')


def slug(word):
    """Sanitize a word for a filename component."""
    w = word.lower().replace(' ', '_').replace('-', '_').replace('/', '_')
    w = re.sub(r'[^a-z0-9_.]+', '', w)
    return w.strip('._') or 'word'


print('parsing CALD3 .mdx (full audio order)...', flush=True)
md = r.MDX(CALD_MDX)
full_order = {}   # headword -> [spx, ...] in document order
links = {}
for k, v in md.items():
    hw = k.decode('utf-8')
    body = v.decode('utf-8')
    m = LINK_RE.match(v)
    if m:
        links[hw] = m.group(1).decode('utf-8').strip()
        full_order[hw] = []
        continue
    full_order[hw] = AUDIO_RE.findall(body)

print('headwords=%d links=%d' % (len(full_order), len(links)), flush=True)

lookup = defaultdict(list)
for hw in full_order:
    lookup[fold(hw)].append(hw)
link_map = {fold(k): fold(v) for k, v in links.items()}


def resolved_headwords(word):
    cands = word_candidates(clean(word))
    heads = []
    for c in cands:
        heads.extend(lookup.get(c, []))
    for c in cands:
        t = link_map.get(c)
        if t:
            heads.extend(lookup.get(t, []))
    seen = set()
    out = []
    for h in heads:
        if h not in seen:
            seen.add(h)
            out.append(h)
    return out


def index_for(word, spx):
    for h in resolved_headwords(word):
        lst = full_order.get(h, [])
        if spx in lst:
            return lst.index(spx) + 1   # 1-based
    return None


mapping = json.load(open('_work/final_uk_mapping.json', encoding='utf-8'))
out = {}
no_index = []
for nid, v in mapping.items():
    if not v.get('audio'):
        continue
    spx = v['audio']
    idx = index_for(v['word'], spx)
    if idx is None:
        no_index.append((nid, v['word'], spx))
        idx = 1
    word = v['word']
    newfile = 'cald3_uk_%s_%d.wav' % (slug(word), idx)
    out[nid] = {'word': word, 'spx': spx, 'index': idx, 'newfile': newfile}

json.dump(out, open('_work/uk_naming.json', 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
print('naming entries=%d, no_index(fallback=1)=%d' % (len(out), len(no_index)), flush=True)
for row in no_index[:40]:
    print('  NOINDEX', row, flush=True)
