# -*- coding: utf-8 -*-
"""Match all deck words against Macmillan (mald2) and report AUDIO coverage,
especially among the words CALD3 could NOT cover (gap-fill candidates).

Read-only: parses the .mdx, reads Anki notes, prints a report + JSON.
Matches BOTH exact/folded headwords AND British<->American spelling variants
(via variants.normalize) so -ise/-ize, -our/-or, -ogue/-og etc. line up.
"""
import re, json, sys
from collections import defaultdict
sys.path.insert(0, '_work')
sys.stdout.reconfigure(encoding='utf-8')
import mdict_utils.reader as r
from ac import ac
from build_uk import clean, fold, word_candidates
from variants import normalize

MALD = 'mald2/Macmillan English Dictionary for Advanced Learners.mdx'
UK_RE = re.compile(r'href="sound://(zzz_uk_[^"]+\.wav)"')
US_RE = re.compile(r'href="sound://(zzz_us_[^"]+\.wav)"')

print('parsing Macmillan...', flush=True)
md = r.MDX(MALD)
fold_lookup = {}   # fold(hw) -> {'uk':set,'us':set}
norm_lookup = {}   # normalize(hw) -> {'uk':set,'us':set}
for k, v in md.items():
    hw = k.decode('utf-8', 'replace')
    body = v.decode('utf-8', 'replace')
    uk = UK_RE.findall(body)
    us = US_RE.findall(body)
    for lookup, key in ((fold_lookup, fold(hw)), (norm_lookup, normalize(hw))):
        e = lookup.setdefault(key, {'uk': set(), 'us': set()})
        e['uk'].update(uk)
        e['us'].update(us)

n_uk = sum(1 for e in norm_lookup.values() if e['uk'])
n_us = sum(1 for e in norm_lookup.values() if e['us'])
print('normalized headwords: UK-audio=%d  US-audio=%d' % (n_uk, n_us), flush=True)

# ---- fetch deck notes ----
nids = ac('findNotes', query='deck:"01_g6_260916"')
infos = ac('notesInfo', notes=nids)
print('[Anki] notes=%d' % len(infos), flush=True)

words = {}   # noteId -> word (cleaned)
cald_covered = set()
for ni in infos:
    f = ni['fields']
    w = clean((f.get('wb') or f.get('word') or {}).get('value', ''))
    words[ni['noteId']] = w
    if (f.get('cald3_uk') or {}).get('value', '').strip():
        cald_covered.add(ni['noteId'])

all_ids = set(words)
uncovered_ids = sorted(all_ids - cald_covered)


def mald_hit(word):
    """(uk_count, us_count) for a deck word, matching variants + exact folds."""
    uk = us = 0
    # variant-normalized candidates (also catches exact headwords)
    for c in [word] + word_candidates(word):
        e = norm_lookup.get(normalize(c))
        if e:
            uk = max(uk, len(e['uk']))
            us = max(us, len(e['us']))
    # exact/folded fallback (irregular inflections, e.g. minutes/minutia)
    if not uk and not us:
        for c in word_candidates(word):
            e = fold_lookup.get(fold(c))
            if e:
                uk = max(uk, len(e['uk']))
                us = max(us, len(e['us']))
    return uk, us


def tally(ids):
    uk = us = either = both = none = 0
    for nid in ids:
        u, s = mald_hit(words[nid])
        if u and s:
            both += 1
        elif u:
            uk += 1
        elif s:
            us += 1
        else:
            none += 1
        if u or s:
            either += 1
    return {'n': len(ids), 'uk_only': uk, 'us_only': us, 'both': both,
            'either': either, 'none': none}


all_t = tally(sorted(all_ids))
unc_t = tally(uncovered_ids)

print()
print('=== ALL %d notes ===' % all_t['n'])
print('  Macmillan any-audio: %d (%.1f%%)' % (all_t['either'], 100*all_t['either']/all_t['n']))
print('    UK-only %d | US-only %d | both %d | none %d' %
      (all_t['uk_only'], all_t['us_only'], all_t['both'], all_t['none']))

print()
print('=== CALD3-UNCOVERED %d notes (gap-fill candidates) ===' % unc_t['n'])
print('  Macmillan any-audio: %d (%.1f%%)' % (unc_t['either'], 100*unc_t['either']/unc_t['n']))
print('    UK-only %d | US-only %d | both %d | none %d' %
      (unc_t['uk_only'], unc_t['us_only'], unc_t['both'], unc_t['none']))

uniq_uncovered = {}
for nid in uncovered_ids:
    w = words[nid]
    if w not in uniq_uncovered:
        uniq_uncovered[w] = mald_hit(w)
u_any = sum(1 for (u, s) in uniq_uncovered.values() if u or s)
u_none = sum(1 for (u, s) in uniq_uncovered.values() if not u and not s)
print()
print('=== unique uncovered words: %d ===' % len(uniq_uncovered))
print('  Macmillan covers %d unique words, misses %d' % (u_any, u_none))

miss_words = sorted(w for w, (u, s) in uniq_uncovered.items() if not u and not s)
print()
print('--- %d unique uncovered words Macmillan ALSO misses ---' % len(miss_words))
for w in miss_words:
    print('   ', w)

out = {
    'all_notes': all_t,
    'uncovered_notes': unc_t,
    'unique_uncovered': {
        'total': len(uniq_uncovered),
        'macmillan_covers': u_any,
        'macmillan_misses': u_none,
    },
    'miss_words': miss_words,
    'per_note': {str(nid): {'word': words[nid],
                            'uk': mald_hit(words[nid])[0],
                            'us': mald_hit(words[nid])[1]}
                 for nid in uncovered_ids},
}
json.dump(out, open('_work/mald_coverage.json', 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
print()
print('saved _work/mald_coverage.json', flush=True)
