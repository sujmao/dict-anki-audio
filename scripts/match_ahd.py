# -*- coding: utf-8 -*-
"""Match the 420 CALD3+Macmillan-uncovered words against AHD5 (US audio).

Read-only. Uses pre-parsed ahd5_entries.json / ahd5_links.json. Writes
_work/ahd_coverage.json (word -> chosen audio ref + how it was resolved) and
_work/ahd_review.md (human-auditable report).

Resolution strategy (most -> least trusted):
  0. MANUAL overrides (hand-checked spellings / lemmas).
  1. direct / variant-normalized headword (exact fold match preferred over
     suffix entries like "-cephalic").
  2. @@@LINK redirects (British spelling -> American headword).
  3. fold fallback (irregular inflections).
  4. derived-form recovery: strip a closed set of stress-neutral affixes
     (un-/non-/over-/semi-/self-/under-/well-/ill-/sun-  and  -s/-es/-ies/-ed/
     -d/-ied/-ing/-er/-est/-ness/-ly/-less/-ful/-able/-ible/-ish/-like), with
     silent-e restore + consonant-doubling undo, up to 2 strips. Only accepted
     when the stem is an EXACT AHD headword with audio.

Multi-audio entries: AHD5 orders the primary sense first, so we take the FIRST
distinct audio (verified correct for the two such words: "minutes" -> noun
"min-it", "finable" -> "fine"=fīn, not the musical "fee-nay").
"""
import re, json, sys
from collections import defaultdict
sys.path.insert(0, '_work')
sys.stdout.reconfigure(encoding='utf-8')
from build_uk import fold, word_candidates
from variants import normalize

entries = json.load(open('_work/ahd5_entries.json', encoding='utf-8'))
links = json.load(open('_work/ahd5_links.json', encoding='utf-8'))
uncovered = json.load(open('_work/still_uncovered.json', encoding='utf-8'))['words']

norm_lookup = defaultdict(list)   # normalize(hw) -> [hw, ...]
fold_lookup = defaultdict(list)   # fold(hw) -> [hw, ...]
for hw in entries:
    norm_lookup[normalize(hw)].append(hw)
    fold_lookup[fold(hw)].append(hw)

link_norm = defaultdict(list)     # normalize(hw) -> [target, ...]
for hw, tgt in links.items():
    link_norm[normalize(hw)].append(tgt)

# hand-checked: misspelled deck words -> correct headword; ambiguous lemmas.
MANUAL = {
    'spined': 'spine',          # spine+d, NOT spin+ed
    'enflame': 'inflame',       # variant spelling
    'minutia': 'minutiae',      # singular -> plural lemma
    'idiosyncracy': 'idiosyncrasy',   # deck misspelling
    'plentitude': 'plenitude',        # deck misspelling
    'archetypally': 'archetype',      # -ally stress-form not in AHD; closest
    'untamed': 'tame',                # un+tame+d; "tam" (Scottish cap) would shadow
}

PREFIXES = ('un', 'non', 'over', 'semi', 'self', 'under', 'well', 'ill', 'sun')
# stress-neutral suffixes only (no -al/-ally/-ment/-tion/-ic/-ity: stress-shift)
SUFFIXES = ('ies', 'ied', 'able', 'ible', 'ness', 'less', 'ful', 'ish',
            'like', 'ing', 'ed', 'er', 'est', 'ly', 'es', 'd', 's')
# suffixes that imply a silent-e restore and/or consonant doubling on the stem
E_RESTORE = ('ed', 'd', 'ing', 'er', 'est')


def audios_of(hw):
    return [a for r in entries[hw] for a in r['audio']]


def pick(hws, exact):
    """Prefer exact fold match with audio, else the first hw with audio."""
    best = None
    for hw in hws:
        a = audios_of(hw)
        if not a:
            continue
        if exact is not None and fold(hw) == fold(exact):
            return hw, a
        if best is None:
            best = (hw, a)
    return best if best else (None, [])


def headword_for(stem):
    """Exact-headword lookup of a stem; returns (hw, audios) or (None, [])."""
    for c in [stem] + word_candidates(stem):
        hws = norm_lookup.get(normalize(c))
        if hws:
            hw, a = pick(hws, c)
            if a:
                return hw, a
    return None, []


def restore_variants(base, suf):
    """Yield candidate spellings of the stem for a given suffix."""
    yield base
    if suf in E_RESTORE:
        if base and base[-1].isalpha() and base[-1] in 'bcdfghjklmnpqrstvwxz':
            yield base + 'e'          # blight -> blight (no-op), bristl->bristle
    if suf in ('ied', 'ies'):
        yield base + 'y'              # purified -> purify, studied -> study
    if base.endswith('y') and suf in ('ing', 'er', 'est'):
        yield base[:-1] + 'ie'        # (y-keeping -ing forms)
    if len(base) >= 2 and base[-1] == base[-2] and base[-1].isalpha():
        yield base[:-1]               # sparr -> spar (consonant doubling)


def lemma_candidates(word):
    """(stem, ops) candidates from a closed affix set (<=2 strips)."""
    w = fold(word).replace('-', '')
    out = []
    # single prefix
    for p in PREFIXES:
        if w.startswith(p) and len(w) - len(p) >= 3:
            out.append((w[len(p):], 'pre:%s' % p))
    # single suffix
    for suf in SUFFIXES:
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            base = w[:-len(suf)]
            for cand in restore_variants(base, suf):
                out.append((cand, 'suf:%s' % suf))
    # prefix + suffix
    for p in PREFIXES:
        if not w.startswith(p):
            continue
        rest = w[len(p):]
        if len(rest) < 3:
            continue
        for suf in SUFFIXES:
            if rest.endswith(suf) and len(rest) - len(suf) >= 3:
                base = rest[:-len(suf)]
                for cand in restore_variants(base, suf):
                    out.append((cand, 'pre:%s+suf:%s' % (p, suf)))
    return out


def resolve_derived(word):
    for stem, ops in lemma_candidates(word):
        hw, a = headword_for(stem)
        if a:
            return hw, a, stem, ops
    return None, [], '', ''


def resolve(word):
    # 0. manual override
    if word in MANUAL:
        hw = MANUAL[word]
        a = audios_of(hw)
        if a:
            return hw, a, 'manual'
    # 1. direct / variant-normalized headword
    for c in [word] + word_candidates(word):
        hws = norm_lookup.get(normalize(c))
        if hws:
            hw, a = pick(hws, c)
            if a:
                return hw, a, 'direct'
    # 2. link redirects
    seen = set()
    queue = [word]
    while queue:
        cur = queue.pop(0)
        n = normalize(cur)
        if n in seen:
            continue
        seen.add(n)
        for tgt in link_norm.get(n, []):
            if tgt in entries:
                a = audios_of(tgt)
                if a:
                    return tgt, a, 'link'
            queue.append(tgt)
    # 3. fold fallback
    for c in word_candidates(word):
        hws = fold_lookup.get(fold(c))
        if hws:
            hw, a = pick(hws, c)
            if a:
                return hw, a, 'fold'
    # 4. derived
    hw, a, stem, ops = resolve_derived(word)
    if a:
        return hw, a, 'derived'
    return None, [], 'none'


hits = {}   # word -> {hw, audio, how}
miss = []
for w in uncovered:
    hw, audios, how = resolve(w)
    if hw and audios:
        # first DISTINCT audio (primary sense is first in AHD5)
        uniq = list(dict.fromkeys(audios))
        hits[w] = {'hw': hw, 'audio': uniq[0], 'all': uniq, 'how': how}
    else:
        miss.append(w)

miss.sort()
covered = sorted(hits)
n_multi = sum(1 for v in hits.values() if len(v['all']) > 1)

print('uncovered words: %d' % len(uncovered))
print('AHD5 covers (>=1 audio): %d (%.1f%%)' % (len(hits), 100*len(hits)/len(uncovered)))
print('AHD5 misses: %d' % len(miss))
print('multi-distinct-audio entries: %d' % n_multi)
for w in sorted(k for k, v in hits.items() if len(v['all']) > 1):
    print('   MULTI', w, '->', hits[w]['hw'], hits[w]['all'], 'pick=', hits[w]['audio'])

print()
print('--- AHD5 misses (%d) ---' % len(miss))
for w in miss:
    print('   ', w)

# ---- review report (human-auditable) ----
L = []
A = L.append
A('# AHD5 美音補缺覆蓋報告（對 420 個未覆蓋詞）')
A('')
A('## 摘要')
A('')
A('- 未覆蓋詞（劍橋 + 麥克米倫後）：**420**')
A('- AHD5 補上美音：**%d**（%.1f%%）' % (len(hits), 100*len(hits)/len(uncovered)))
A('- AHD5 仍未覆蓋：**%d**' % len(miss))
A('- 多音頻（取第一個義項）：**%d**' % n_multi)
A('')
A('## 1. 直接匹配（direct / manual / link / fold）')
A('')
A('| 單詞 | 詞頭 | 方式 | 音頻 |')
A('|------|------|------|------|')
for w in covered:
    v = hits[w]
    if v['how'] != 'derived':
        A('| %s | %s | %s | `%s` |' % (w, v['hw'], v['how'], v['audio']))
A('')
A('## 2. 派生詞還原（derived）')
A('')
A('| 單詞 | 詞頭 | 音頻 |')
A('|------|------|------|')
for w in covered:
    v = hits[w]
    if v['how'] == 'derived':
        A('| %s | %s | `%s` |' % (w, v['hw'], v['audio']))
A('')
A('## 3. 仍未覆蓋（%d）' % len(miss))
A('')
A('| 單詞 |')
A('|------|')
for w in miss:
    A('| %s |' % w)
A('')
A('> 這些多為罕見/已廢詞、拼寫錯誤（如 idiosyncracy→idiosyncrasy 已手工改正）、或 AHD5 無音頻條目。')
md = '\n'.join(L) + '\n'
open('_work/ahd_review.md', 'w', encoding='utf-8').write(md)

out = {
    'total': len(uncovered),
    'covered': len(hits),
    'missed': len(miss),
    'miss_words': miss,
    'hits': {w: v for w, v in hits.items()},
}
json.dump(out, open('_work/ahd_coverage.json', 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
print()
print('saved _work/ahd_coverage.json and _work/ahd_review.md')
