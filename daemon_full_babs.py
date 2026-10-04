import urllib.request, json, os, sys, time, signal, glob

running = True
def handle_term(signum, frame):
    global running
    running = False
signal.signal(signal.SIGTERM, handle_term)
signal.signal(signal.SIGINT, handle_term)

KEY = ""
with open("/root/.hermes/.env") as f:
    for line in f:
        if line.startswith("HERMES_CUSTOM_LOCALHOST_20128_API_KEY="):
            KEY = line.strip().split("=", 1)[1]

MODELS = [
    "ag/claude-sonnet-4-6",
    "ag/claude-opus-4-6-thinking",
    "ag/gpt-oss-120b-medium",
    "ag/gemini-3.8-flash"
]

BASE_DIR = "/mnt/d/explore/road-map.md"

def query_llm(prompt, system_prompt="Anda adalah Senior Technical Curriculum Architect sesuai standar GEMINI.md."):
    for m in MODELS:
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
            with urllib.request.urlopen(req, timeout=180) as resp:
                raw = resp.read().decode("utf-8")
                lines = raw.strip().split("\n")
                content = ""
                for line in lines:
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
                if content:
                    return content
        except Exception as e:
            time.sleep(2)
            continue
    return None

def main():
    log_file = os.path.join(BASE_DIR, "generator_full_babs.log")
    with open(log_file, "a") as log:
        log.write(f"\n[{time.ctime()}] Generator BAB 02-10 started.\n")
        log.flush()

    cats = [d for d in os.listdir(BASE_DIR) if d.startswith("0")]
    for c in sorted(cats):
        cat_dir = os.path.join(BASE_DIR, c)
        for slug in sorted(os.listdir(cat_dir)):
            if not running:
                break
            slug_dir = os.path.join(cat_dir, slug)
            if not os.path.isdir(slug_dir):
                continue

            # Cek berapa bab yang ada
            babs = [d for d in os.listdir(slug_dir) if d.startswith("BAB-")]
            if len(babs) >= 10:
                continue

            with open(log_file, "a") as log:
                log.write(f"[{time.ctime()}] Processing remaining BABs for {c}/{slug} (current: {len(babs)} BABs)...\n")
                log.flush()

            # Buat Bab 02 s/d Bab 10
            for b_num in range(2, 11):
                if not running:
                    break
                bab_prefix = f"BAB-{b_num:02d}"
                existing = [d for d in os.listdir(slug_dir) if d.startswith(bab_prefix)]
                if existing:
                    continue

                bab_name = f"{bab_prefix}-Materi-Lanjutan"
                bab_path = os.path.join(slug_dir, bab_name)
                m01_path = os.path.join(bab_path, "hands-on", "m01")
                os.makedirs(m01_path, exist_ok=True)

                prompt = f"""Tuliskan materi Bab {b_num:02d} Module 01 untuk kurikulum '{slug}' di kategori '{c}' sesuai format 20 seksi lengkap standar GEMINI.md (Learning Objective, Concept, Why, What, How, Diagram ASCII, Simple Example, Practical Example, Trade-offs, Best Practices, dll). Bahasa Indonesia profesional teknis."""
                content = query_llm(prompt)
                if content:
                    with open(os.path.join(bab_path, f"Module-01-{slug}-Bab-{b_num:02d}.md"), "w", encoding="utf-8") as f:
                        f.write(content)
                    with open(log_file, "a") as log:
                        log.write(f"  [SUCCESS] {c}/{slug}/{bab_prefix} created.\n")
                        log.flush()
                time.sleep(1)

if __name__ == "__main__":
    main()
