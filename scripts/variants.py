# -*- coding: utf-8 -*-
"""British <-> American spelling-variant canonicalization.

Purpose: decide whether two dictionary headwords are the SAME word (spelling
variant, e.g. colour/color, sceptical/skeptical) versus DIFFERENT words
(synonyms, e.g. acclimate/acclimatize, recurrent/recurring). `normalize()`
maps both spellings to one canonical (US-leaning) form; equal output => same
word (keep), different => candidate synonym (filter).

This is deliberately CURATED, not rule-blanket, because blanket suffix rules
corrupt common words ("hour"->"hor", "there"->"therer", "promise"->"promize").
"""
import re, unicodedata


def fold(s):
    """Lowercase, ligature/diacritic fold (base step shared with matching)."""
    s = s.lower()
    s = s.replace('æ', 'ae').replace('œ', 'oe').replace('ß', 'ss')
    s = unicodedata.normalize('NFD', s)
    return ''.join(c for c in s if unicodedata.category(c) != 'Mn')


# One-off variant pairs (canonicalize British -> US form).
PAIRS = {
    # double-l vs single-l (verbs / adjectives)
    'appal': 'appall', 'enthral': 'enthrall', 'instil': 'instill',
    'fulfil': 'fulfill', 'enrol': 'enroll', 'distil': 'distill',
    'extol': 'extoll', 'skilful': 'skillful', 'wilful': 'willful',
    'instalment': 'installment', 'instal': 'install',
    'enrolment': 'enrollment', 'fulfilment': 'fulfillment',
    # -ogue / -og
    'catalogue': 'catalog', 'analogue': 'analog', 'dialogue': 'dialog',
    'monologue': 'monolog', 'epilogue': 'epilog', 'prologue': 'prolog',
    'demagogue': 'demagog', 'synagogue': 'synagog', 'pedagogue': 'pedagog',
    # -ette / -et
    'omelette': 'omelet', 'toilette': 'toilet', 'cigarette': 'cigaret',
    'brunette': 'brunet', 'silhouette': 'silhouette',
    # -e / -0
    'largesse': 'largess', 'lissome': 'lissom', 'matte': 'matt',
    'phoney': 'phony', 'storey': 'story', 'annexe': 'annex',
    'glycerine': 'glycerin',
    # -ould / -old
    'mould': 'mold', 'mouldy': 'moldy', 'smoulder': 'smolder',
    # -yse / -yze
    'paralyse': 'paralyze', 'analyse': 'analyze', 'catalyse': 'catalyze',
    'hydrolyse': 'hydrolyze',
    # -ey / -y
    'chantey': 'chanty',
    # misc single words
    'manoeuvre': 'maneuver', 'behove': 'behoove', 'furore': 'furor',
    'naivety': 'naivete', 'libellous': 'libelous',
    'skullduggery': 'skulduggery', 'cheque': 'check', 'disc': 'disk',
    'kerb': 'curb', 'tyre': 'tire', 'draught': 'draft', 'plough': 'plow',
    'grey': 'gray', 'moustache': 'mustache', 'sulphur': 'sulfur',
    'aluminium': 'aluminum', 'pyjamas': 'pajamas', 'aeroplane': 'airplane',
    # -re / -er nouns
    'centre': 'center', 'theatre': 'theater', 'metre': 'meter',
    'litre': 'liter', 'fibre': 'fiber', 'calibre': 'caliber',
    'lustre': 'luster', 'meagre': 'meager', 'sceptre': 'scepter',
    'spectre': 'specter', 'sombre': 'somber', 'reconnoitre': 'reconnoiter',
    'accoutrement': 'accouterment',
    # -ce / -se
    'defence': 'defense', 'offence': 'offense', 'pretence': 'pretense',
    'licence': 'license',
    # -sc- / -sk-
    'sceptical': 'skeptical', 'scepticism': 'skepticism', 'sceptic': 'skeptic',
    # compound/derived forms whose base is in PAIRS
    'outmanoeuvre': 'outmaneuver', 'lacklustre': 'lackluster',
}

# British -our stems (colour/coloured/colourful/behaviour/behavioural ...).
# Blanket "our"->"or" would corrupt hour/four/your/tour/sour/court; use stems.
OUR_STEMS = [
    'colour', 'favour', 'honour', 'humour', 'labour', 'neighbour', 'rumour',
    'valour', 'vigour', 'armour', 'behaviour', 'candour', 'clamour',
    'demeanour', 'endeavour', 'fervour', 'flavour', 'odour', 'parlour',
    'rancour', 'rigour', 'saviour', 'splendour', 'succour', 'tumour',
    'vapour', 'ardour', 'harbour', 'enamour', 'misdemeanour', 'glamour',
]

# -ise / -ize: only verbs that genuinely take -ize; exclude words that only
# ever spell -ise (promise, exercise, surprise, advise, ...).
ISE_STOP = {
    'promise', 'premise', 'premises', 'exercise', 'surprise', 'compromise',
    'advertise', 'advise', 'devise', 'revise', 'disguise', 'franchise',
    'excise', 'incise', 'despise', 'arise', 'rise', 'wise', 'otherwise',
    'paradise', 'concise', 'precise', 'improvise', 'supervise', 'enterprise',
    'expertise', 'chastise', 'merchandise', 'demise', 'surmise', 'reprise',
}


def _norm_our(s):
    for st in OUR_STEMS:
        if st in s:                            # handles prefixed/suffixed forms
            return s.replace(st, st[:-3] + 'or')
    return s


def normalize(s):
    s = fold(s)
    s = s.replace('-', '').replace(' ', '')
    s = s.rstrip('.')                       # con. -> con (abbreviation headwords)
    s = re.sub(r'[ˈˌˏˑ]', '', s)            # strip IPA stress marks (ˌill ˈwill)
    s = re.sub(r'\([^)]*\)', '', s)         # drop parenthetical variant (cosy(cozy))
    if s in PAIRS:
        return PAIRS[s]
    s = _norm_our(s)
    if s.endswith('ise') and s not in ISE_STOP:
        s = s[:-3] + 'ize'                 # realise -> realize
    if s.endswith('lling'):
        s = s[:-5] + 'ling'                # travelling -> traveling
    if s.endswith('lled'):
        s = s[:-4] + 'led'
    if s.endswith('ller'):
        s = s[:-4] + 'ler'
    if s.endswith('llity'):
        s = s[:-5] + 'lity'                # tranquillity -> tranquility
    if s.endswith('mme'):
        s = s[:-2] + 'm'                   # programme -> program
    return s
