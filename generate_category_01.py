import urllib.request, json, os, sys, time, re, concurrent.futures

BASE_DIR = "/mnt/d/explore/road-map.md"
CAT_NAME = "01-Core-Foundations"
CAT_DIR = os.path.join(BASE_DIR, CAT_NAME)

TRACKS = [
    "backend-beginner",
    "computer-science",
    "datastructures-and-algorithms",
    "devops-beginner",
    "frontend-beginner",
    "git-github",
    "git-github-beginner",
    "leetcode",
    "linux",
    "shell-bash"
]

KEY = ""
with open("/root/.hermes/.env") as f:
    for line in f:
        if line.startswith("HERMES_CUSTOM_LOCALHOST_20128_API_KEY="):
            KEY = line.strip().split("=", 1)[1]

MODELS = [
    "ag/gemini-3.8-flash",
    "ag/gemini-3.7-flash-high",
    "ag/claude-sonnet-4-6"
]

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
                    "temperature": 0.3
                }).encode("utf-8")
                req = urllib.request.Request(url, data=payload, headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {KEY}"
                })
                with urllib.request.urlopen(req, timeout=150) as resp:
                    raw = resp.read().decode("utf-8")
                    content = ""
                    for line in raw.strip().split("\n"):
                        line = line.strip()
                        if line.startswith("data: ") and not line.endswith("[DONE]"):
                            try:
                                chunk = json.loads(line[6:])
                                content += chunk.get("choices", [{}])[0].get("delta", {}).get("content", "")
                            except:
                                pass
                        elif line.startswith("{"):
                            try:
                                res = json.loads(line)
                                content = res.get("choices", [{}])[0].get("message", {}).get("content", "")
                            except:
                                pass
                    if content and len(content) > 5000:
                        return content
            except Exception as e:
                # print(f"Error querying {m}: {e}")
                time.sleep(2)
    return None

def get_track_titles(slug):
    readme_path = os.path.join(CAT_DIR, slug, "README.md")
    titles = {}
    if os.path.exists(readme_path):
        with open(readme_path, encoding="utf-8", errors="ignore") as f:
            content = f.read()
        matches = re.findall(r'(?:Bab|BAB)\s*(\d{1,2})[\s:—–-]+([^\n\r]+)', content)
        for num, title in matches:
            n = int(num)
            if 1 <= n <= 10 and n not in titles:
                t = title.strip().split('|')[0].split('(')[0].split('[')[0].strip()
                t = re.sub(r'—+.*$', '', t).strip()
                if t:
                    titles[n] = t
    return titles

def process_bab(slug, b_num, title):
    slug_dir = os.path.join(CAT_DIR, slug)
    bab_prefix = f"BAB-{b_num:02d}"
    existing = [d for d in os.listdir(slug_dir) if d.startswith(bab_prefix)]
    
    if existing:
        bab_name = existing[0]
    else:
        bab_name = f"{bab_prefix}-Materi-Lanjutan"
        
    bab_path = os.path.join(slug_dir, bab_name)
    m01_path = os.path.join(bab_path, "hands-on", "m01")
    os.makedirs(m01_path, exist_ok=True)
    
    target_file = os.path.join(bab_path, f"Module-01-{slug}-Bab-{b_num:02d}.md")
    if os.path.exists(target_file) and os.path.getsize(target_file) > 5000:
        return f"[SKIP] {slug}/{bab_prefix} already exists ({os.path.getsize(target_file)} bytes)"

    prompt = f"""Tuliskan materi Bab {b_num:02d} Module 01 untuk kurikulum '{slug}' di kategori '{CAT_NAME}'.
Topik Bab: {title}
Format wajib 20 seksi lengkap standar GEMINI.md:
## SEKSI 01 — IDENTITAS MODUL
## SEKSI 02 — LEARNING OBJECTIVES
## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)
## SEKSI 04 — MENGAPA INI PENTING (WHY)
## SEKSI 05 — APA ITU (WHAT)
## SEKSI 06 — BAGAIMANA CARA KERJA (HOW)
## SEKSI 07 — DIAGRAM ASCII DETAIL
## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)
## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)
## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN
## SEKSI 11 — BEST PRACTICES
## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)
## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)
## SEKSI 14 — QUIZ & SELF-ASSESSMENT
## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN
## SEKSI 16 — RINGKASAN MODUL (SUMMARY)
## SEKSI 17 — GLOSARIUM
## SEKSI 18 — CATATAN INSTRUKTUR
## SEKSI 19 — CHANGELOG & VERSI
## SEKSI 20 — NAVIGASI KURIKULUM
Gunakan Bahasa Indonesia profesional teknis yang sangat mendalam, detail, dan aplikatif."""

    t0 = time.time()
    content = query_llm(prompt)
    if content:
        with open(target_file, "w", encoding="utf-8") as f:
            f.write(content)
        elapsed = time.time() - t0
        return f"[SUCCESS] {slug}/{bab_prefix} created ({len(content)} chars, {elapsed:.1f}s)"
    else:
        return f"[FAILED] {slug}/{bab_prefix} generation failed"

def main():
    print(f"Starting Generation for {CAT_NAME}...")
    tasks = []
    for slug in TRACKS:
        titles = get_track_titles(slug)
        slug_dir = os.path.join(CAT_DIR, slug)
        for b in range(2, 11):
            title = titles.get(b, f"Materi Lanjutan Bab {b:02d}")
            tasks.append((slug, b, title))

    print(f"Total potential tasks: {len(tasks)}")
    
    completed = 0
    # Use 5 concurrent workers
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        future_to_task = {
            executor.submit(process_bab, slug, b, title): (slug, b)
            for slug, b, title in tasks
        }
        
        for future in concurrent.futures.as_completed(future_to_task):
            task_info = future_to_task[future]
            try:
                res = future.result()
                print(res, flush=True)
                completed += 1
                if completed % 5 == 0:
                    os.system(f"python3 {os.path.join(BASE_DIR, 'update_checklist.py')} > /dev/null 2>&1")
            except Exception as e:
                print(f"[ERROR] Task {task_info}: {e}", flush=True)

    os.system(f"python3 {os.path.join(BASE_DIR, 'update_checklist.py')}")
    print("Done! Checklist updated.")

if __name__ == "__main__":
    main()
