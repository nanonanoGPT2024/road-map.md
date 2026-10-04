import os
import re
import sys
import time
import json
import urllib.request
import concurrent.futures

BASE_DIR = "/mnt/d/explore/road-map.md"
CAT_NAME = "02-Programming-Languages"
CAT_DIR = os.path.join(BASE_DIR, CAT_NAME)

KEY = ""
with open("/root/.hermes/.env") as f:
    for line in f:
        if line.startswith("HERMES_CUSTOM_LOCALHOST_20128_API_KEY="):
            KEY = line.strip().split("=", 1)[1]

MODELS = [
    "ag/gemini-3.8-flash",
    "ag/gemini-3.7-flash-high",
    "ag/claude-sonnet-4-6",
    "ag/gpt-oss-120b-medium"
]

EXT_MAP = {
    "aspnet-core": "Program.cs",
    "c": "main.c",
    "c-sharp": "Program.cs",
    "cpp": "main.cpp",
    "golang": "main.go",
    "java": "Main.java",
    "javascript": "index.js",
    "kotlin": "Main.kt",
    "php": "index.php",
    "python": "main.py",
    "python-data-analysis": "analysis.py",
    "r": "script.R",
    "r-programming": "script.R",
    "ruby": "main.rb",
    "ruby-on-rails": "app.rb",
    "rust": "main.rs",
    "scala": "Main.scala",
    "swift-ui": "ContentView.swift",
    "typescript": "index.ts"
}

LANG_TAGS = {
    "aspnet-core": ["csharp", "cs"],
    "c": ["c"],
    "c-sharp": ["csharp", "cs"],
    "cpp": ["cpp", "c++"],
    "golang": ["go", "golang"],
    "java": ["java"],
    "javascript": ["javascript", "js"],
    "kotlin": ["kotlin", "kt"],
    "php": ["php"],
    "python": ["python", "py"],
    "python-data-analysis": ["python", "py"],
    "r": ["r"],
    "r-programming": ["r"],
    "ruby": ["ruby", "rb"],
    "ruby-on-rails": ["ruby", "rb"],
    "rust": ["rust", "rs"],
    "scala": ["scala"],
    "swift-ui": ["swift"],
    "typescript": ["typescript", "ts"]
}

def extract_best_code(content, track, bab_title):
    valid_tags = LANG_TAGS.get(track, [])
    blocks = re.findall(r'```([a-zA-Z0-9_\-\+]*)\n(.*?)```', content, re.DOTALL)
    
    # First look for matching language tag
    tagged_blocks = []
    for tag, code in blocks:
        t = tag.strip().lower()
        if t in valid_tags and len(code.strip()) > 50:
            tagged_blocks.append(code.strip())
            
    if tagged_blocks:
        # Return the most substantial code block (e.g. from practical example / implementation)
        return max(tagged_blocks, key=len)
        
    # Fallback to any code block not looking like ascii diagram
    for tag, code in blocks:
        c = code.strip()
        if len(c) > 50 and not c.startswith("+--") and not c.startswith("|"):
            return c
            
    return f"// Hands-on Lab for {track} - {bab_title}\n"

def query_llm(prompt, system_prompt="Anda adalah Senior Technical Curriculum Architect sesuai standar GEMINI.md."):
    for m in MODELS:
        for attempt in range(2):
            try:
                url = "http://localhost:20128/v1/chat/completions"
                payload = json.dumps({
                    "model": m,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.3,
                    "stream": False
                }).encode("utf-8")
                req = urllib.request.Request(url, data=payload, headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {KEY}"
                })
                with urllib.request.urlopen(req, timeout=120) as resp:
                    res = json.loads(resp.read().decode("utf-8"))
                    content = res.get("choices", [{}])[0].get("message", {}).get("content", "")
                    if content and len(content) > 500:
                        return content
            except Exception as e:
                time.sleep(2)
                continue
    return None

def slugify(text):
    text = re.sub(r'[\/\\:*\?"<>|&,–—\(\)\[\]]', ' ', text)
    text = re.sub(r'\s+', '-', text.strip())
    return text.strip('-')

def get_track_bab_titles(track):
    readme = os.path.join(CAT_DIR, track, 'README.md')
    if not os.path.exists(readme): return {}
    with open(readme, 'r', encoding='utf-8', errors='ignore') as f:
        text = f.read()
    
    titles = {}
    for line in text.splitlines():
        line_clean = line.strip()
        m = re.search(r'\[bab\s*(\d{1,2})\]\s*([^\]\(\r\n#\|]+)', line_clean, re.I)
        if m:
            n, t = int(m.group(1)), m.group(2).strip().strip(':—–- ')
            if 1 <= n <= 10 and n not in titles and t:
                titles[n] = t; continue
        m = re.search(r'\[bab\s*(\d{1,2})\s*[:—\-–]\s*([^\]]+)\]', line_clean, re.I)
        if m:
            n, t = int(m.group(1)), m.group(2).strip().strip(':—–- ')
            if 1 <= n <= 10 and n not in titles and t:
                titles[n] = t; continue
        m = re.search(r'###\s*(?:\[)?bab\s*(\d{1,2})\s*[:—\-–]\s*([^\]\(\r\n#\|]+)', line_clean, re.I)
        if m:
            n, t = int(m.group(1)), m.group(2).strip().strip(':—–- ')
            if 1 <= n <= 10 and n not in titles and t:
                titles[n] = t; continue
        m = re.search(r'bab\s*(\d{1,2})\s*[—\-–:]\s*([^#\]\r\n\|]+)', line_clean, re.I)
        if m:
            n, t = int(m.group(1)), m.group(2).strip().strip(':—–- ')
            if 1 <= n <= 10 and n not in titles and t:
                titles[n] = t; continue
    return titles

def process_bab(track, b_num, bab_title):
    slug_dir = os.path.join(CAT_DIR, track)
    bab_prefix = f"BAB-{b_num:02d}"
    existing = [d for d in os.listdir(slug_dir) if d.startswith(bab_prefix)]
    
    if existing:
        bab_name = existing[0]
        bab_path = os.path.join(slug_dir, bab_name)
        # Check if already has module file
        mod_files = [f for f in os.listdir(bab_path) if f.endswith(".md") and os.path.isfile(os.path.join(bab_path, f))]
        if mod_files:
            return f"[SKIP] {track}/{bab_name} already exists with {mod_files[0]}"
    else:
        clean_title = slugify(bab_title)
        if clean_title:
            bab_name = f"{bab_prefix}-{clean_title}"
        else:
            bab_name = f"{bab_prefix}-Materi-Lanjutan"
        bab_path = os.path.join(slug_dir, bab_name)

    m01_path = os.path.join(bab_path, "hands-on", "m01")
    os.makedirs(m01_path, exist_ok=True)

    prompt = f"""Tuliskan materi pembelajaran komprehensif Bab {b_num:02d} Module 01 untuk kurikulum '{track}' pada kategori '02-Programming-Languages' dengan judul/topik: '{bab_title}'.
WAJIB ikuti format 20 seksi lengkap standar GEMINI.md:
SEKSI 01 — IDENTITAS MODUL
SEKSI 02 — LEARNING OBJECTIVES
SEKSI 03 — MINDSET & MENTAL MODEL
SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR (Diagram ASCII art)
SEKSI 05 — ANATOMI & MEKANISME INTERNAL
SEKSI 06 — DEEP DIVE KONSEP & TEORI
SEKSI 07 — CONTOH KODE FUNDAMENTAL (Step-by-step)
SEKSI 08 — ANALISIS BARIS DEMI BARIS
SEKSI 09 — STUDI KASUS NYATA (Real-World Production Scenario)
SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE
SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN
SEKSI 12 — EDGE CASES & PITFALLS
SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA
SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI
SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA
SEKSI 16 — KEAMANAN & HARDENING
SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING
SEKSI 18 — RINGKASAN & CHEAT SHEET
SEKSI 19 — KUIS EVALUASI PEMAHAMAN (5 Soal Basic, 5 Soal Intermediate)
SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

Tuliskan dalam Bahasa Indonesia profesional teknis, mendalam, lengkap dengan blok kode fungsional dan penjelasan detail."""

    content = query_llm(prompt)
    if not content:
        return f"[FAIL] Could not generate content for {track}/{bab_prefix}"

    mod_file_path = os.path.join(bab_path, f"Module-01-{track}-Bab-{b_num:02d}.md")
    with open(mod_file_path, "w", encoding="utf-8") as f:
        f.write(content)

    # Hands-on code file
    code_filename = EXT_MAP.get(track, "main.txt")
    code_file_path = os.path.join(m01_path, code_filename)
    if not os.path.exists(code_file_path):
        extracted_code = extract_best_code(content, track, bab_title)
        with open(code_file_path, "w", encoding="utf-8") as f:
            f.write(extracted_code + "\n")

    return f"[SUCCESS] {track}/{bab_name} ({len(content)} chars)"

def main():
    tracks = sorted([d for d in os.listdir(CAT_DIR) if os.path.isdir(os.path.join(CAT_DIR, d))])
    tasks = []
    for t in tracks:
        titles = get_track_bab_titles(t)
        for b in range(2, 11):
            title = titles.get(b, f"Materi Lanjutan Bab {b}")
            tasks.append((t, b, title))

    print(f"Total BAB to process: {len(tasks)} across {len(tracks)} tracks")
    
    completed = 0
    t0 = time.time()
    # 8 concurrent workers
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
        futures = {ex.submit(process_bab, t, b, title): (t, b) for t, b, title in tasks}
        for fut in concurrent.futures.as_completed(futures):
            t, b = futures[fut]
            try:
                res = fut.result()
                completed += 1
                elapsed = time.time() - t0
                print(f"[{completed}/{len(tasks)}] [{elapsed:.1f}s] {res}", flush=True)
            except Exception as e:
                print(f"[ERROR] {t} Bab {b}: {e}", flush=True)

    print(f"All done in {time.time()-t0:.1f}s! Running update_checklist.py...")
    os.system(f"python3 {os.path.join(BASE_DIR, 'update_checklist.py')}")

if __name__ == "__main__":
    main()
