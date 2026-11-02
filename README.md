# 詞典音頻 ↔ Anki 單詞匹配方法論

一套把 MDict 詞典（MDX/MDD）裡的真人發音音頻，按「單詞 → 詞典詞頭」精確匹配到 Anki 卡片上的完整工作方法論與參考實現。

> Dictionary ↔ Anki word-audio matching: a reproducible pipeline that maps each
> Anki vocabulary word to the *correct* dictionary headword, extracts its audio,
> converts it losslessly, and writes a `[sound:...]` tag into a per-dictionary field.

---

## 0. 目標與總體流程

**輸入**：一個 Anki 牌組（單詞存在 note 欄位裡）+ 一或多本 MDict 詞典。
**輸出**：每張卡片一個 `[sound:文件名]` 標籤，落在「詞典 + 口音」專屬欄位（如 `cald3_uk`），媒體文件放進 Anki 的 `collection.media`。

流程分 8 步：

1. **提取** —— 讀 MDX，得到 詞頭 → 音頻引用 的映射。
2. **匹配** —— 把卡片單詞摺疊（fold）後查詞頭索引，含連字號／空格／括號變體與 `@@@LINK` 跳轉。
3. **變體判定** —— 區分「拼寫變體」（保留）與「同義詞摺疊」（剔除）。
4. **消歧** —— 一詞多音時用詞性 + IPA + 重音位置選對。
5. **轉換** —— 用正確解碼器把音頻轉成統一格式（這是音質的正確性關鍵）。
6. **命名** —— `{詞典代號}_{口音}_{單詞}_{第N個音頻}`。
7. **寫入** —— 經 AnkiConnect 把標籤寫進欄位；媒體由用戶手動導入。
8. **覆蓋率** —— 統計每本詞典能補多少缺漏，決定去留與查漏補缺順序。

---

## 1. 數據源：MDict 詞典文件

- **`.mdx`** = 詞頭索引 → HTML 正文（含音頻引用、音標、詞性）。
- **`.mdd`** = 媒體歸檔（音頻、圖片），文件名被 `sound://` 引用。
- 用 [`mdict-utils`](https://pypi.org/project/mdict-utils/)（`pip install mdict-utils`）讀取：

```python
import mdict_utils.reader as r
md = r.MDX('cald3/剑桥高阶英英 CALD3_v1.4.mdx')
for key, body in md.items():
    headword = key.decode('utf-8')
    html = body.decode('utf-8')          # 裡面有 sound://xxx
```

- 詞頭跳轉：正文以 `@@@LINK=目標詞頭` 開頭時，該詞頭是別處詞條的別名，要沿連結解析到真實詞條。
- 三本常用詞典的音頻引用格式：

| 詞典 | 音頻引用 | 口音標記 |
|------|----------|----------|
| CALD3 劍橋高階 | `sound://*.spx`（Speex-in-Ogg） | `<b>UK</b>` / `<b>US</b>` |
| Macmillan 麥克米倫 | `sound://zzz_uk_*.wav` / `sound://zzz_us_*.wav` | 文件名 `zzz_uk` / `zzz_us` |
| AHD5 美國傳統 | `sound://*.wav`，重拼寫在 `class="rtseg"` | 美音為主 |

### 安全：不可信數據

下載解壓的詞典歸檔是**不可信數據**（可能夾帶惡意 `json.py`、`mdict_utils.py` 等）。規則：

- 每個歸檔放到**獨立的空目錄**。
- 你寫的腳本放在**另一個目錄**。
- 讀取它們的 Python 一律用隔離模式 **`python -I`**（忽略 `PYTHONPATH` 與當前目錄，防止 import 被劫持）。
- 路徑用參數傳入，不要在歸檔目錄裡跑直譯器／構建工具。

---

## 2. 詞頭與音頻提取

對每個詞頭，解析出**有序**的發音記錄 `{kind, audio, ipa, pos}`。關鍵是 UK/US 標籤與音頻連結的**配對**——一個標籤可能沒有自己的音頻（只是另一種音標），要跳過：

```python
labels = list(re.finditer(r'<b>(UK|US)</b>', body))
for i, m in enumerate(labels):
    seg = body[m.end() : labels[i+1].start() if i+1 < len(labels) else m.end()+600]
    am = re.search(r'href="sound://([^"]+\.(spx|wav))"', seg)
    if not am:      # 只有音標、沒有音頻的備選發音
        continue
```

---

## 3. 單詞匹配（word matching）

卡片單詞往往和詞典詞頭在**形式**上不一致。摺疊 + 生成候選鍵：

```python
def fold(s):
    s = s.lower().replace('æ','ae').replace('œ','oe').replace('ß','ss')
    s = unicodedata.normalize('NFD', s)
    return ''.join(c for c in s if unicodedata.category(c) != 'Mn')  # 去變音符

def word_candidates(word):
    # 括號變體： cosy(cozy) -> cosy, cozy
    # 連字號/空格變體： ill-will <-> ill will <-> illwill
```

匹配順序：直接命中 `fold(詞頭)` → 沿 `@@@LINK` 目標再查。

---

## 4. 拼寫變體 vs 同義詞摺疊（最易錯的一步）

這是「匹配到**對的詞**」與「匹配到**另一個詞**」的分界線。

### 4a. 拼寫變體 —— 保留

英式/美式拼寫差異，是**同一個詞**，音頻通用：

| 卡片單詞 | 詞典詞頭 | 判定 |
|----------|----------|------|
| color | colour | 變體，保留 |
| skeptical | sceptical | 變體，保留 |
| catalog | catalogue | 變體，保留 |
| realize | realise | 變體，保留 |
| glamor | glamour | 變體，保留 |

用**策展式（curated）正則化**而不是一刀切後綴規則（後者會把 `hour→hor`、`promise→promize` 搞壞）。`variants.normalize()` 把英式映射到美式規範形：

- 一次性詞對 `PAIRS`：`centre→center`、`manoeuvre→maneuver`、`sceptical→skeptical`、`skullduggery→skulduggery` ……
- `-our` 詞幹表 `OUR_STEMS`（子串替換，處理 `belabour/armoured` 這類前後綴形式）。
- `-ise→-ize` 但帶 `ISE_STOP` 停用表（`promise/exercise/advise` 等永遠不變）。
- 後綴規則：`-lling→-ling`、`-lled→-led`、`-mme→-m`。

### 4b. 同義詞摺疊 —— 剔除

卡片單詞 W 命中了某詞條，但該詞條的**主詞頭（primary headword）是另一個詞**——W 只是被摺進該詞條的「同義詞」，發音根本不同：

| 卡片單詞 | 命中詞條主詞頭 | 判定 |
|----------|----------------|------|
| acclimate | acclimatize | 同義詞，剔除 |
| recurrent | recurring | 同義詞，剔除 |
| rendition | rendering | 同義詞，剔除 |
| summation | summary | 同義詞，剔除 |
| envision | envisage | 同義詞，剔除 |

判定方法：提取主詞頭（第一個 `<b>…</b>`，剝掉嵌套標籤與羅馬數字義項標號），再比較
`normalize(主詞頭) == normalize(卡片單詞)`：

- 相等 → 拼寫變體，**保留**；
- 不等 → 同義詞摺疊，**剔除**（該卡片的音頻清空，留待查漏補缺）。

> 實測：CALD3 一輪匹配後，用此法從 5911 張卡片中剔除 **32** 張同義詞摺疊，同時保住 **48** 組拼寫變體。

---

## 5. 一詞多音消歧

同形異義（homograph）或一詞多義時，一個詞頭可能有多條 UK 音頻。選哪條？

- **詞性提示**（來自卡片中文釋義欄，如 `vi.` / `n.` / `adj.`）與詞條 POS 對齊；
- **IPA 相似度**（摺疊重音符號與音位等價後做 Levenshtein）；
- **重音位置**一致（主重音在第幾個音節）。

打分取最低者；當 POS 決定但 IPA 嚴重衝突時標記人工復核。

---

## 6. 音頻轉換（音質正確性的關鍵）

CALD3 的 `.spx` 是 **Speex-in-Ogg，32 kHz 超寬帶，雙聲道（兩聲道完全一致）**。

**坑**：ffmpeg 自帶的 `speex` 解碼器對這條流是**壞的**——它按 16 kHz 解碼，導致

- 時長變成 **2 倍**（聽起來慢半拍、悶），
- 浮點值溢出到 4.6e33（爆音／滋滋聲）。

這就是「聽感與詞典不一致」的全部根因，**跟重採樣／單聲道／AAC 無關**。

**正確命令**：把 `libspeex` 作為**輸入解碼器**放在 `-i` **之前**：

```bash
ffmpeg -y -hide_banner -loglevel error \
  -c:a libspeex -i IN.spx \
  -ac 1 -c:a aac -b:a 64k OUT.m4a
```

- 保留原生 **32 kHz**（不要加 `-ar`）。
- `-ac 1` 是無損下混（兩聲道逐位相同）。
- `libspeex`（定點參考解碼器）給出正確時長與乾淨浮點（峰值 ≤ 1.0）。

驗證：`ffprobe` 下，原生 `speex` 解碼時長 = 容器時長的 2 倍；`libspeex` = 容器時長。

> 注意：`-c:a libspeex` 放在 `-i` **之後**會變成**輸出編碼器**，是錯的。

---

## 7. 命名與欄位

- **欄位**：每本詞典 + 口音一個欄位，命名 `{詞典代號}_{口音}`：
  `cald3_uk`、`cald3_us`、`mald2_uk`、`mald2_us`、`ahd5_us` ……
- **文件**：`{詞典代號}_{口音}_{單詞}_{第N個音頻}.m4a`，其中 **N** = 選中音頻在該詞條**所有**音頻連結中的 1-based 序號（用於日後追溯/去重）。
- **卡片標籤**：欄位值 = `[sound:文件名]`。

---

## 8. 寫入 Anki（AnkiConnect）

經 HTTP `127.0.0.1:8765`：

```python
import requests
def ac(action, **params):
    r = requests.post('http://127.0.0.1:8765',
                      json={'action': action, 'version': 6, 'params': params})
    d = r.json()
    if d.get('error') is not None:
        raise RuntimeError(d['error'])
    return d.get('result')

ids  = ac('findNotes', query='deck:"你的牌組"')
info = ac('notesInfo', notes=ids)
ac('updateNoteFields', note={'id': nid, 'fields': {'cald3_uk': '[sound:cald3_uk_word_1.m4a]'}})
```

媒體文件由用戶手動放進 `collection.media`（或用 `storeMediaFile`）。
注意：AnkiConnect 不支援 `addModelField`；新增欄位要用 Anki 的 MCP 工具或手工加。

---

## 9. 覆蓋率分析與查漏補缺

逐詞典統計覆蓋率，決定「去留」與「補缺順序」：

| 詞典 | 全量匹配（音頻） | 對 CALD3 缺漏的補充 |
|------|------------------|---------------------|
| CALD3 英音 | 5879 / 6492（剔除 32 同義詞摺疊後） | — |
| Macmillan（英+美） | 5857 / 6492（90.2%） | **193 / 613**（31.5%） |

剩餘 420 個單詞兩本都缺。

**推薦策略**（分里程碑，勿一次全做）：

1. **英音版**：`cald3_uk` 先行（5879 張）。
2. **英音 + 美音查漏補缺版**：把 613 個缺漏用第二本詞典的美音補上（如 AHD5 US）。
3. 完全美音版、全部詞典合併版——**暫時擱置**。

---

## 10. 復現清單

```bash
pip install mdict-utils requests

# 1. 提取 + 匹配（隔離模式，防不可信數據）
python -I build_uk.py            # 詞頭 + 發音提取、匹配、一詞多音消歧
python -I match_mald.py          # 覆蓋率統計（可替換成任意詞典）

# 2. 同義詞摺疊檢測（輸出剔除清單 + 拼寫變體清單）
python -I detect_synonym.py

# 3. 轉換音頻（libspeex 輸入解碼器）
python -I build_full_aac_mono.py

# 4. 命名 + 寫欄位
python -I build_naming.py
python -I set_audio_tags.py
```

---

## 腳本索引（scripts/）

| 腳本 | 作用 |
|------|------|
| `variants.py` | 英/美拼寫正則化（策展式），區分變體與同義詞的核心 |
| `build_uk.py` | 詞頭 + 發音提取、摺疊匹配、一詞多音消歧（POS + IPA + 重音） |
| `detect_synonym.py` | 同義詞摺疊檢測（主詞頭判定 → 剔除清單） |
| `match_mald.py` | 覆蓋率統計（含拼寫變體歸一化），用於「去留」決策 |
| `build_naming.py` | `{詞典}_{口音}_{單詞}_{第N個音頻}` 命名 |
| `build_full_aac_mono.py` | `libspeex → AAC mono 64k`（正確解碼） |
| `set_audio_tags.py` | AnkiConnect 寫 `[sound:...]` 欄位 |
| `blank_synonyms.py` | 清空同義詞摺疊卡片的音頻欄位 |
| `ac.py` | 最小 AnkiConnect 客戶端 |

路徑都在各腳本頂部常量配置。字典 `.mdx/.mdd`、音頻與 `_work/` 產物**不進版本庫**（見 `.gitignore`）。
