# -*- coding: utf-8 -*-
"""Generate the AHD5 report: kept (direct + homophone) vs removed non-exact."""
import json, sys
sys.stdout.reconfigure(encoding='utf-8')

cov = json.load(open('_work/ahd_coverage.json', encoding='utf-8'))
hits = cov['hits']
direct = [(w, v) for w, v in hits.items() if v['how'] == 'direct']
homophone = [(w, v) for w, v in hits.items() if v['how'] == 'homophone']
link = [(w, v) for w, v in hits.items() if v['how'] == 'link']
derived = [(w, v) for w, v in hits.items() if v['how'] == 'derived']
manual = [(w, v) for w, v in hits.items() if v['how'] == 'manual']
miss = cov['miss_words']

kept = len(direct) + len(homophone)
removed_total = len(link) + len(derived) + len(manual)

homophone_notes = {
    'enflame': '變體拼寫，與 inflame 同音',
    'idiosyncracy': '變體拼寫，與 idiosyncrasy 同音',
    'plentitude': '變體拼寫，與 plenitude 同音',
}
manual_notes = {
    'spined': 'spine+d 非 spin+ed（非同音）',
    'minutia': '單數→複數，尾音不同（非同音）',
    'archetypally': '-ally 詞形不在 AHD，取最近（非同音）',
    'untamed': 'un+tame+d 非 tam（非同音）',
}

L = []
A = L.append
A('# AHD5 美音補缺 —— 精確對應版（去除派生/變體失真）')
A('')
A('## 摘要')
A('')
A('- 劍橋 + 麥克米倫後未覆蓋：**420**')
A('- AHD5 **保留**（錄音 = 卡片單詞本身，或同音異形）：**%d**' % kept)
A('  - 直接詞頭：%d' % len(direct))
A('  - 同音異形（變體拼寫，錄音念法相同）：%d' % len(homophone))
A('- 已去除的非精確匹配（錄音是**不同**的詞，非卡片逐字）：**%d**' % removed_total)
A('  - AHD5 `@@@LINK` 派生跳轉：%d' % len(link))
A('  - 前綴/後綴派生還原：%d' % len(derived))
A('  - 手工覆寫（非同音）：%d' % len(manual))
A('- 詞典內無此詞/無音頻：**%d**' % len(miss))
A('- **去除後仍未覆蓋：%d**' % (removed_total + len(miss)))
A('')
A('## 1. 直接詞頭（保留，%d）' % len(direct))
A('')
A('| 單詞 | 詞頭 | 音頻 |')
A('|------|------|------|')
for w, v in sorted(direct):
    A('| %s | %s | `%s` |' % (w, v['hw'], v['audio']))
A('')
A('## 2. 同音異形（保留，%d）' % len(homophone))
A('')
A('| 單詞 | 實際錄音詞頭 | 說明 | 音頻 |')
A('|------|--------------|------|------|')
for w, v in sorted(homophone):
    A('| %s | %s | %s | `%s` |' % (w, v['hw'], homophone_notes.get(w, ''), v['audio']))
A('')
A('## 3. 已去除的非精確匹配（%d，按原因分組）' % removed_total)
A('')
A('### 3a. AHD5 @@@LINK 派生跳轉（%d）' % len(link))
A('')
A('| 單詞 | 實際錄音詞頭 |')
A('|------|--------------|')
for w, v in sorted(link):
    A('| %s | %s |' % (w, v['hw']))
A('')
A('### 3b. 前綴/後綴派生還原（%d）' % len(derived))
A('')
A('| 單詞 | 實際錄音詞頭 |')
A('|------|--------------|')
for w, v in sorted(derived):
    A('| %s | %s |' % (w, v['hw']))
A('')
A('### 3c. 手工覆寫（%d，非同音）' % len(manual))
A('')
A('| 單詞 | 實際錄音詞頭 | 說明 |')
A('|------|--------------|------|')
for w, v in sorted(manual):
    A('| %s | %s | %s |' % (w, v['hw'], manual_notes.get(w, '')))
A('')
A('## 4. 詞典內無此詞/無音頻（%d）' % len(miss))
A('')
A('| 單詞 |')
A('|------|')
for w in sorted(miss):
    A('| %s |' % w)
A('')
A('> 原則：卡片音頻必須**完全對應**卡片單詞本身，或對應**同音異形**（變體拼寫、念法相同）。')
A('> 派生/屈折/單複數若錄音是**不同的**詞（念法不同），一律跳過而非張冠李戴。')
md = '\n'.join(L) + '\n'
open('_work/ahd_review.md', 'w', encoding='utf-8').write(md)
print('wrote _work/ahd_review.md')
print('direct=%d homophone=%d kept=%d | link=%d derived=%d manual=%d removed=%d | miss=%d'
      % (len(direct), len(homophone), kept, len(link), len(derived), len(manual), removed_total, len(miss)))
