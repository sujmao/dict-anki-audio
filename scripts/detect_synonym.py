# -*- coding: utf-8 -*-
"""Detect 'synonym-fold' matches: deck word W matched a CALD3 entry whose
PRIMARY headword is a *different word* than W (e.g. acclimate -> acclimatize).
Spelling variants (rancor/rancour, skeptical/sceptical) are normalized so they
are KEPT; only true synonyms are FILTERED."""
import re, json, sys
from collections import defaultdict
sys.path.insert(0, '_work')
sys.stdout.reconfigure(encoding='utf-8')
import mdict_utils.reader as r
from build_uk import clean, fold, word_candidates
from variants import normalize

CALD = 'cald3/剑桥高阶英英 CALD3_v1.4.mdx'
LINK_RE = re.compile(rb'@@@LINK=([^\r\n]+)')
B = re.compile(r'<b>(.*?)</b>', re.S)


def primary_of(body):
    m = B.search(body)
    if not m:
        return None
    t = re.sub(r'<[^>]+>', '', m.group(1))   # strip nested tags
    t = t.replace('▪', ' ').strip()
    t = re.sub(r'^[IVX]+\s*\.?\s*', '', t)   # strip roman-numeral sense label
    t = t.split(',')[0].split('/')[0].strip()
    return fold(t)


# --- British/American variant normalization (curated) ---
RE_ER = {'centre': 'center', 'theatre': 'theater', 'metre': 'meter', 'litre': 'liter',
         'fibre': 'fiber', 'calibre': 'caliber', 'lustre': 'luster', 'meagre': 'meager',
         'sceptre': 'scepter', 'spectre': 'specter', 'sombre': 'somber',
         'reconnoitre': 'reconnoiter', 'accoutrement': 'accouterment'}
CE_SE = {'defence': 'defense', 'offence': 'offense', 'pretence': 'pretense',
         'licence': 'license', 'practice': 'practise'}
SC_SK = {'sceptical': 'skeptical', 'scepticism': 'skepticism', 'sceptic': 'skeptic'}
ISE_STOP = {'promise', 'premise', 'premises', 'exercise', 'surprise', 'compromise',
            'advertise', 'advise', 'devise', 'revise', 'disguise', 'franchise',
            'excise', 'incise', 'despise', 'arise', 'rise', 'wise', 'otherwise',
            'paradise', 'concise', 'precise', 'improvise', 'supervise', 'enterprise',
            'expertise', 'chastise', 'merchandise'}


def vfold(s):
    s = fold(s)
    s = s.replace('-', '').replace(' ', '')
    if s.endswith('our'):
        s = s[:-3] + 'or'                    # colour -> color
    if s in RE_ER:
        s = RE_ER[s]
    if s in CE_SE:
        s = CE_SE[s]
    if s in SC_SK:
        s = SC_SK[s]
    if s.endswith('ise') and s not in ISE_STOP:
        s = s[:-3] + 'ize'                   # realise -> realize
    if s.endswith('lling'):
        s = s[:-5] + 'ling'
    if s.endswith('lled'):
        s = s[:-4] + 'led'
    if s.endswith('ller'):
        s = s[:-4] + 'ler'
    if s.endswith('llity'):
        s = s[:-5] + 'lity'                  # tranquillity -> tranquility
    if s.endswith('ggery'):
        s = s[:-5] + 'gery'                  # skullduggery -> skulduggery
    if s.endswith('mme'):
        s = s[:-2] + 'm'                     # programme -> program
    if s.endswith('yl'):
        s = s[:-2] + 'il'                    # (rare)
    return s


print('parsing CALD3...', flush=True)
md = r.MDX(CALD)
lookup = defaultdict(list)
primary = {}
links = {}
for k, v in md.items():
    hw = k.decode('utf-8')
    fk = fold(hw)
    m = LINK_RE.match(v)
    if m:
        links[fk] = fold(m.group(1).decode('utf-8'))
        continue
    lookup[fk].append(hw)
    ph = primary_of(v.decode('utf-8'))
    primary[fk] = ph if ph else fk


def resolve_keys(word):
    cands = word_candidates(clean(word))
    keys = []
    for c in cands:
        keys.extend(lookup.get(c, []))
    for c in cands:
        t = links.get(c)
        if t:
            keys.extend(lookup.get(t, []))
    seen, out = set(), []
    for k in keys:
        if k not in seen:
            seen.add(k); out.append(k)
    return out


def resolved_primary(word):
    keys = resolve_keys(word)
    if not keys:
        return None, None
    k = keys[0]
    return k, primary.get(fold(k), fold(k))


mapping = json.load(open('_work/final_uk_mapping.json', encoding='utf-8'))
filtered, kept_variant = [], []
for nid, v in mapping.items():
    if not v.get('audio'):
        continue
    w = v['word']
    k, ph = resolved_primary(w)
    if ph is None:
        continue
    if ph == fold(w):
        continue
    if normalize(ph) == normalize(w):
        kept_variant.append((w, k, ph))
    else:
        filtered.append((nid, w, k, ph, v['audio']))

print('deck words with audio:', sum(1 for v in mapping.values() if v.get('audio')))
print('TRUE SYNONYM-FOLD (to filter): %d' % len(filtered))
for nid, w, k, ph, spx in sorted(filtered):
    print('  FILTER  %-16s -> primary %-16s  spx=%s' % (w, ph, spx))
print()
print('spelling-variant (kept, normalized): %d' % len(kept_variant))
for w, k, ph in sorted(kept_variant)[:40]:
    print('  KEEP    %-16s == %-16s' % (w, ph))
if len(kept_variant) > 40:
    print('  ... +%d more' % (len(kept_variant) - 40))

# write the filter list (noteId -> {word, primary, spx}) for the gap-fill/blank step
out = {str(nid): {'word': w, 'primary': ph, 'spx': spx}
       for nid, w, k, ph, spx in filtered}
json.dump(out, open('_work/synonym_filter.json', 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
print()
print('synonym filter written: _work/synonym_filter.json (%d notes)' % len(out), flush=True)
