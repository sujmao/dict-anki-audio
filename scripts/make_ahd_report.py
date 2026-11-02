# -*- coding: utf-8 -*-
"""Generate the corrected AHD5 report: exact matches kept vs non-exact removed."""
import json, sys
sys.stdout.reconfigure(encoding='utf-8')

cov = json.load(open('_work/ahd_coverage.json', encoding='utf-8'))
hits = cov['hits']
exact = [(w, v) for w, v in hits.items() if v['how'] == 'direct']
link = [(w, v) for w, v in hits.items() if v['how'] == 'link']
derived = [(w, v) for w, v in hits.items() if v['how'] == 'derived']
manual = [(w, v) for w, v in hits.items() if v['how'] == 'manual']
miss = cov['miss_words']

notes = {
    'spined': 'spine+d 非 spin+ed',
    'untamed': 'un+tame+d 非 tam',
    'archetypally': '-ally 詞形不在 AHD，取最近',
    'enflame': '拼寫變體',
    'minutia': '單數→複數',
    'idiosyncracy': '牌組拼錯改正',
    'plentitude': '牌組拼錯改正',
}

removed_total = len(link) + len(derived) + len(manual)

L = []
A = L.append
A('# AHD5 美音補缺 —— 精確對應版（去除派生/變體失真）')
A('')
A('## 摘要')
A('')
A('- 劍橋 + 麥克米倫後未覆蓋：**420**')
A('- AHD5 **精確**匹配（錄音 = 卡片單詞本身）：**%d**' % len(exact))
A('- 已去除的非精確匹配（錄音是詞根/變體，非卡片逐字）：**%d**' % removed_total)
A('  - AHD5 `@@@LINK` 派生跳轉：%d' % len(link))
A('  - 前綴/後綴派生還原：%d' % len(derived))
A('  - 手工覆寫：%d' % len(manual))
A('- 詞典內無此詞/無音頻：**%d**' % len(miss))
A('- **去除後仍未覆蓋：%d**' % (removed_total + len(miss)))
A('')
A('## 1. 精確匹配（保留，%d）' % len(exact))
A('')
A('| 單詞 | 詞頭 | 音頻 |')
A('|------|------|------|')
for w, v in sorted(exact):
    A('| %s | %s | `%s` |' % (w, v['hw'], v['audio']))
A('')
A('## 2. 已去除的非精確匹配（%d，按原因分組）' % removed_total)
A('')
A('### 2a. AHD5 @@@LINK 派生跳轉（%d）' % len(link))
A('')
A('| 單詞 | 實際錄音詞頭 |')
A('|------|--------------|')
for w, v in sorted(link):
    A('| %s | %s |' % (w, v['hw']))
A('')
A('### 2b. 前綴/後綴派生還原（%d）' % len(derived))
A('')
A('| 單詞 | 實際錄音詞頭 |')
A('|------|--------------|')
for w, v in sorted(derived):
    A('| %s | %s |' % (w, v['hw']))
A('')
A('### 2c. 手工覆寫（%d）' % len(manual))
A('')
A('| 單詞 | 實際錄音詞頭 | 說明 |')
A('|------|--------------|------|')
for w, v in sorted(manual):
    A('| %s | %s | %s |' % (w, v['hw'], notes.get(w, '')))
A('')
A('## 3. 詞典內無此詞/無音頻（%d）' % len(miss))
A('')
A('| 單詞 |')
A('|------|')
for w in sorted(miss):
    A('| %s |' % w)
A('')
A('> 原則：卡片音頻必須**完全對應**卡片單詞；派生詞若詞典只有詞根錄音，一律跳過而非張冠李戴。')
md = '\n'.join(L) + '\n'
open('_work/ahd_review.md', 'w', encoding='utf-8').write(md)
print('wrote _work/ahd_review.md')
print('exact=%d link=%d derived=%d manual=%d miss=%d removed=%d' %
      (len(exact), len(link), len(derived), len(manual), len(miss), removed_total))
