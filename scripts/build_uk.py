# -*- coding: utf-8 -*-
"""Build the word -> CALD3 UK audio mapping (pure-British milestone).

Read-only against Anki (only findNotes/notesInfo) and the CALD3 .mdx.
Produces _work/uk_mapping.json and a review list; no writes to the collection.
"""
import re, json, sys, unicodedata
from collections import defaultdict
import mdict_utils.reader as r
from ac import ac

sys.stdout.reconfigure(encoding='utf-8')

CALD_MDX = 'cald3/剑桥高阶英英 CALD3_v1.4.mdx'
LINK_RE = re.compile(rb'@@@LINK=([^\r\n]+)')
TAG = re.compile(r'<[^>]+>')


def clean(s):
    s = TAG.sub('', s)
    s = s.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
    return s.strip()


def fold(s):
    s = s.lower()
    s = s.replace('æ', 'ae').replace('œ', 'oe').replace('ß', 'ss')
    s = unicodedata.normalize('NFD', s)
    return ''.join(c for c in s if unicodedata.category(c) != 'Mn')


def parse_cald3_pron(body):
    """Return ordered list of dicts {kind, audio, ipa, pos}.

    Each <b>UK</b>/<b>US</b> label pairs with the audio link that appears
    BEFORE the next label (an alternative-IPA label with no audio is skipped).
    """
    label_re = re.compile(r'<b>(UK|US)</b>')
    pos_re = re.compile(r'<font color=orange>\s*([a-zA-Z ]+?)\s*</font>')
    audio_re = re.compile(r'href="sound://([^"]+\.spx)"')
    ipa_re = re.compile(r'\[([^\]]*)\]')
    labels = list(label_re.finditer(body))
    items = []
    for i, m in enumerate(labels):
        kind = m.group(1)
        start = m.end()
        end = labels[i + 1].start() if i + 1 < len(labels) else min(len(body), start + 600)
        seg = body[start:end]
        am = audio_re.search(seg)
        if not am:
            continue  # alternative-IPA marker (no audio of its own)
        audio = am.group(1)
        ipa = None
        im = ipa_re.search(seg, am.end())
        if im:
            ipa = clean(im.group(1))
        pos = None
        pm = pos_re.search(body[max(0, m.start() - 400):m.start()])
        if pm:
            pos = pm.group(1).strip()
        items.append({'kind': kind, 'audio': audio, 'ipa': ipa, 'pos': pos})
    return items


def parse_cald3():
    md = r.MDX(CALD_MDX)
    entries = defaultdict(list)
    links = {}
    for k, v in md.items():
        hw = k.decode('utf-8')
        body = v.decode('utf-8')
        m = LINK_RE.match(v)
        if m:
            links[hw] = m.group(1).decode('utf-8').strip()
            continue
        entries[hw].extend(parse_cald3_pron(body))
    return dict(entries), links


# ---------- IPA normalization & similarity ----------
STRESS = 'ˈˌ'
SEP = '·.‐-'
EQUIV = str.maketrans({
    'ɒ': 'ɑ', 'ɔ': 'ɑ', 'ɹ': 'r', 'ɡ': 'g', 'ɜ': 'ə', 'ɝ': 'ə',
    'ʳ': 'r', 'ʰ': '', 'ː': '', 'ɪ': 'i', 'ʊ': 'u', 'ə': 'ə',
})


def segs(ipa):
    if not ipa:
        return ''
    s = TAG.sub('', ipa).lower()
    s = s.translate(EQUIV)
    s = ''.join(c for c in s if c not in STRESS and c not in SEP and not c.isspace())
    return s


def stress_vec(ipa):
    if not ipa:
        return None
    s = TAG.sub('', ipa).lower()
    s = ''.join(c for c in s if c != 'ˌ' and c not in SEP and not c.isspace())
    # primary stress index in segment stream
    if 'ˈ' in s:
        return s.index('ˈ')
    return None


VOWELS = set('aeiouyæɑɒɔəɛɪʊʌɜɝɨʉœøɐɞ')


def stress_syll(ipa):
    """0-based syllable index of primary stress, or None if no primary."""
    if not ipa:
        return None
    s = TAG.sub('', ipa).lower()
    idx = s.find('ˈ')
    if idx < 0:
        return None
    clusters = 0
    prev = False
    for c in s[:idx]:
        v = c in VOWELS
        if v and not prev:
            clusters += 1
        prev = v
    return clusters


def lev(a, b):
    if a == b:
        return 0
    la, lb = len(a), len(b)
    prev = list(range(lb + 1))
    for i in range(1, la + 1):
        cur = [i] + [0] * lb
        for j in range(1, lb + 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1,
                         prev[j - 1] + (0 if a[i - 1] == b[j - 1] else 1))
        prev = cur
    return prev[lb]


# ---------- POS from ci ----------
POS_MAP = {
    'v': 'verb', 'vt': 'verb', 'vi': 'verb', 'verb': 'verb',
    'n': 'noun', 'noun': 'noun',
    'adj': 'adjective', 'a': 'adjective', 'adjective': 'adjective',
    'adv': 'adverb', 'adverb': 'adverb',
    'prep': 'preposition', 'preposition': 'preposition',
    'conj': 'conjunction', 'conjunction': 'conjunction',
    'int': 'exclamation', 'interj': 'exclamation',
    'pron': 'pronoun', 'pronoun': 'pronoun',
}


def card_pos(ci):
    """Extract POS hint(s) from the Chinese-definition field."""
    if not ci:
        return set()
    t = TAG.sub('', ci).strip().lower()
    out = set()
    for tok in re.split(r'[;；,，/\s]+', t)[:6]:
        tok = tok.strip('.。')
        if tok in POS_MAP:
            out.add(POS_MAP[tok])
    return out


def word_candidates(word):
    w = clean(word)
    cands = []

    def add(s):
        f = fold(s)
        if f and f not in cands:
            cands.append(f)
    add(w)
    if '(' in w or '（' in w:
        base = re.sub(r'[（(].*?[)）]', '', w).strip()
        if base:
            add(base)
        m = re.search(r'[（(](.*?)[)）]', w)
        if m:
            add(re.sub(r'[（(].*?[)）]', '', w).strip() + m.group(1).strip())
    for v in (w.replace('-', ' '), w.replace('-', ''), w.replace(' ', '-'), w.replace(' ', '')):
        add(v)
    return cands


if __name__ == '__main__':
    only_parse = '--parse-only' in sys.argv

    cald_entries, cald_links = parse_cald3()
    with open('_work/cald3_pron.json', 'w', encoding='utf-8') as f:
        json.dump(cald_entries, f, ensure_ascii=False)
    with open('_work/cald3_links_pron.json', 'w', encoding='utf-8') as f:
        json.dump(cald_links, f, ensure_ascii=False)
    n_uk = sum(1 for v in cald_entries.values() if any(x['kind'] == 'UK' for x in v))
    print('[CALD3] unique=%d, links=%d, hw_with_UK_audio=%d' % (len(cald_entries), len(cald_links), n_uk))
    if only_parse:
        sys.exit(0)

    lookup = defaultdict(list)
    for hw, recs in cald_entries.items():
        lookup[fold(hw)].append((hw, recs))
    link_map = {fold(k): fold(v) for k, v in cald_links.items()}

    def find_uk(cands):
        """Return list of UK records (audio+ipa+pos), merging direct + link targets."""
        recs = []
        for c in cands:
            if c in lookup:
                for (_h, rs) in lookup[c]:
                    recs.extend(x for x in rs if x['kind'] == 'UK')
        for c in cands:
            if c in link_map:
                tgt = link_map[c]
                if tgt in lookup:
                    for (_h, rs) in lookup[tgt]:
                        recs.extend(x for x in rs if x['kind'] == 'UK')
        # dedupe by audio, keep order
        seen = set()
        out = []
        for x in recs:
            if x['audio'] not in seen:
                seen.add(x['audio'])
                out.append(x)
        return out

    # fetch live notes
    nids = ac('findNotes', query='deck:"01_g6_260916"')
    infos = ac('notesInfo', notes=nids)
    print('[Anki] notes=%d' % len(infos))

    mapping = {}
    multi = []
    missing = []
    for ni in infos:
        fld = ni['fields']
        word = (fld.get('wb') or fld.get('word') or {}).get('value', '')
        ipa = (fld.get('ipa') or {}).get('value', '')
        ci = (fld.get('ci') or {}).get('value', '')
        gyid = (fld.get('gyid') or {}).get('value', '')
        word_clean = clean(word)
        cands = word_candidates(word_clean)
        uk = find_uk(cands)
        # dedupe by audio, keep order
        seen = set()
        uk_unq = []
        for x in uk:
            if x['audio'] not in seen:
                seen.add(x['audio'])
                uk_unq.append(x)
        rec = {
            'gyid': gyid, 'noteId': ni['noteId'], 'word': word_clean, 'ipa': ipa, 'ci': ci,
            'uk': uk_unq, 'selected': None, 'confidence': None, 'needs_review': False,
        }
        if not uk_unq:
            rec['confidence'] = 'missing'
            missing.append(rec)
        elif len(uk_unq) == 1:
            rec['selected'] = uk_unq[0]
            rec['confidence'] = 'only-one'
        else:
            # disambiguate
            pos_hints = card_pos(ci)
            card_seg = segs(ipa)
            card_syll = stress_syll(ipa)
            best = None
            best_score = 1e9
            scored = []
            for x in uk_unq:
                xpos = (x.get('pos') or '').strip().lower()
                score = 0
                if pos_hints:
                    if xpos and any(p in xpos for p in pos_hints):
                        score -= 40  # POS match bonus
                    elif xpos:
                        score += 60  # POS mismatch penalty
                if card_seg and x['ipa']:
                    score += 3 * lev(card_seg, segs(x['ipa']))
                if card_syll is not None:
                    xs = stress_syll(x['ipa'])
                    if xs is not None and xs != card_syll:
                        score += 30  # stress-position mismatch
                scored.append((score, x))
                if score < best_score:
                    best_score, best = score, x
            rec['selected'] = best
            rec['confidence'] = 'pos+ipa'
            rec['scores'] = [(s, x['ipa'], x['pos'], x['audio']) for s, x in scored]
            multi.append(rec)
            # flag for review when POS was decisive but IPA disagrees, or ties
        mapping[str(ni['noteId'])] = rec

    with open('_work/uk_mapping.json', 'w', encoding='utf-8') as f:
        json.dump(mapping, f, ensure_ascii=False, indent=1)

    n = len(mapping)
    n_miss = sum(1 for m in mapping.values() if m['confidence'] == 'missing')
    n_one = sum(1 for m in mapping.values() if m['confidence'] == 'only-one')
    n_multi = sum(1 for m in mapping.values() if m['confidence'] == 'pos+ipa')
    print('\n=== SUMMARY ===')
    print('total notes:', n)
    print('single UK audio (auto):', n_one)
    print('multi UK audio (disambiguated):', n_multi)
    print('no UK audio (missing):', n_miss)

    print('\n=== MULTI-UK (disambiguated) sample (%d) ===' % len(multi))
    for m in multi[:80]:
        print('%-20s card=%s ci=%.24s' % (m['word'], m['ipa'], clean(m['ci'])))
        for s, ipa, pos, au in m.get('scores', []):
            mark = ' *' if au == m['selected']['audio'] else ''
            print('      %-6s %-16s %-12s %s%s' % (pos or '-', ipa or '-', au, s, mark))

    print('\n=== MISSING UK (%d) ===' % len(missing))
    for m in missing[:120]:
        print('   %-22s %s' % (m['word'], m['ipa']))
