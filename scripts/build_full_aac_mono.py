# -*- coding: utf-8 -*-
"""Full rebuild: decode every selected CALD3 UK .spx with libspeex -> AAC mono 64k
(native 32 kHz, no resample), named cald3_uk_{word}_{index}.m4a.

Outputs to _work/audio_final/ and writes _work/audio_tags.json (noteId -> filename+tag).
Dedupes by output filename (5910 unique; one 'ocular' duplicate card shares a file).
"""
import os, sys, json, time, subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
sys.stdout.reconfigure(encoding='utf-8')

FF = r'E:\Videos\yt-dlp\ffmpeg-2024-03-14-git-2129d66a66-full_build\bin\ffmpeg.exe'
SPX = '_work/cald3_spx'
OUT = '_work/audio_final'
os.makedirs(OUT, exist_ok=True)

WORKERS = 6
TIMEOUT = 30
MIN_SIZE = 200

naming = json.load(open('_work/uk_naming.json', encoding='utf-8'))

# build tasks deduped by output filename
tasks = {}   # out_name -> spx
for v in naming.values():
    out_name = v['newfile'].replace('.wav', '.m4a')
    tasks[out_name] = v['spx']

print('tasks (unique output files): %d  (notes: %d)' % (len(tasks), len(naming)), flush=True)


def convert(item):
    out_name, spx = item
    src = os.path.join(SPX, spx)
    dst = os.path.join(OUT, out_name)
    if os.path.exists(dst) and os.path.getsize(dst) >= MIN_SIZE:
        return (out_name, True, 'cached')
    cmd = [FF, '-y', '-hide_banner', '-loglevel', 'error',
           '-c:a', 'libspeex', '-i', src, '-ac', '1', '-c:a', 'aac', '-b:a', '64k', dst]
    for attempt in (1, 2):
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT)
            if r.returncode == 0 and os.path.exists(dst) and os.path.getsize(dst) >= MIN_SIZE:
                return (out_name, True, 'ok')
        except subprocess.TimeoutExpired:
            pass
        # cleanup partial
        if os.path.exists(dst):
            try: os.remove(dst)
            except OSError: pass
    return (out_name, False, 'fail')


items = sorted(tasks.items())
ok = fail = cached = 0
fails = []
t0 = time.time()
with ThreadPoolExecutor(max_workers=WORKERS) as ex:
    futs = {ex.submit(convert, it): it for it in items}
    for i, fut in enumerate(as_completed(futs), 1):
        out_name, good, status = fut.result()
        if status == 'cached':
            cached += 1
        elif good:
            ok += 1
        else:
            fail += 1
            fails.append(out_name)
        if i % 250 == 0 or i == len(items):
            el = time.time() - t0
            rate = i / el if el > 0 else 0
            eta = (len(items) - i) / rate if rate > 0 else 0
            print('  %d/%d ok=%d cached=%d fail=%d rate=%.1f/s ETA=%.0fs' %
                  (i, len(items), ok, cached, fail, rate, eta), flush=True)

print('DONE ok=%d cached=%d fail=%d  (%.1fs)' % (ok, cached, fail, time.time() - t0), flush=True)
if fails:
    json.dump(fails, open('_work/full_fail.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('FAILED files written to _work/full_fail.json:', len(fails), flush=True)

# write tag mapping (noteId -> tag)
tags = {}
for nid, v in naming.items():
    out_name = v['newfile'].replace('.wav', '.m4a')
    tags[nid] = {'word': v['word'], 'filename': out_name, 'tag': '[sound:%s]' % out_name}
json.dump(tags, open('_work/audio_tags.json', 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
print('tag map written: _work/audio_tags.json (%d notes)' % len(tags), flush=True)
