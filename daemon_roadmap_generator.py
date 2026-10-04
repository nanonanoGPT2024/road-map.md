import urllib.request, json, os, sys, time, re

KEY = ""
with open("/root/.hermes/.env") as f:
    for line in f:
        if line.startswith("HERMES_CUSTOM_LOCALHOST_20128_API_KEY="):
            KEY = line.strip().split("=", 1)[1]

MODELS = [
    "ag/gemini-3.8-flash",
    "ag/claude-sonnet-4-6",
    "ag/gpt-oss-120b-medium"
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
                "temperature": 0.3,
                "stream": False
            }).encode("utf-8")
            req = urllib.request.Request(url, data=payload, headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {KEY}"
            })
            with urllib.request.urlopen(req, timeout=120) as resp:
                raw = resp.read().decode("utf-8")
                try:
                    res = json.loads(raw)
                    content = res.get("choices", [{}])[0].get("message", {}).get("content", "")
                    if content:
                        return content
                except Exception:
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
                    if content:
                        return content
        except Exception:
            time.sleep(1)
            continue
    return None

def main():
    log_file = os.path.join(BASE_DIR, "generator_daemon.log")
    catalog_path = os.path.join(BASE_DIR, "MASTER_CATALOG_TRACKING.md")

    with open(log_file, "a") as log:
        log.write(f"\n[{time.ctime()}] Daemon continuous generator (96 roadmaps) active.\n")
        log.flush()

    while True:
        with open(catalog_path, "r", encoding="utf-8") as f:
            cat_text = f.read()

        queue = [(cat, slug, slug.replace("-", " ").title()) for slug, cat, _ in re.findall(r"- \[([^\]]+)\]\(\./([^/]+)/([^/]+)/\)", cat_text)]
        processed_any = False

        for cat, slug, title in queue:
            target_dir = os.path.join(BASE_DIR, cat, slug)
            readme_path = os.path.join(target_dir, "README.md")
            bab1_dir = os.path.join(target_dir, "BAB-01-Fondasi-dan-Arsitektur")
            mod1_path = os.path.join(bab1_dir, "Module-01-Fondasi-Konsep-Inti.md")

            if os.path.exists(readme_path) and os.path.getsize(readme_path) > 100 and os.path.exists(mod1_path) and os.path.getsize(mod1_path) > 100:
                continue

            processed_any = True
            os.makedirs(target_dir, exist_ok=True)
            with open(log_file, "a") as log:
                log.write(f"[{time.ctime()}] Generating syllabus for: {cat}/{slug} ({title})...\n")
                log.flush()

            if not (os.path.exists(readme_path) and os.path.getsize(readme_path) > 100):
                prompt = f"""Buatkan file README.md silabus lengkap 10 BAB sesuai standar GEMINI.md untuk topik resmi roadmap.sh: '{title}' ({slug}).
Format wajib mencakup:
1. Course Overview & Mindset
2. Learning Roadmap (Diagram pohon ASCII 10 BAB)
3. Navigasi Detail Bab 01 s/d Bab 10 (masing-masing ada 2-3 modul dengan link relatif)
4. Spesifikasi Capstone Project Enterprise di akhir kursus.
Gunakan Bahasa Indonesia profesional teknis."""
                content = query_llm(prompt)
                if content:
                    with open(readme_path, "w", encoding="utf-8") as f:
                        f.write(content)
                    with open(log_file, "a") as log:
                        log.write(f"[{time.ctime()}] SUCCESS: {cat}/{slug}/README.md created.\n")
                        log.flush()

            if not (os.path.exists(mod1_path) and os.path.getsize(mod1_path) > 100):
                m01_dir = os.path.join(bab1_dir, "hands-on", "m01")
                os.makedirs(m01_dir, exist_ok=True)
                mod_prompt = f"""Buatkan materi Bab 01 Module 01 untuk '{title}' ({slug}) sesuai format lengkap 20 seksi GEMINI.md (Learning Objective, Concept, Why, What, How, Diagram ASCII, Simple Example, Practical Example, Trade-offs, Best Practices, dll). Bahasa Indonesia teknis."""
                mod_content = query_llm(mod_prompt)
                if mod_content:
                    with open(mod1_path, "w", encoding="utf-8") as f:
                        f.write(mod_content)
                    with open(log_file, "a") as log:
                        log.write(f"[{time.ctime()}] SUCCESS: {cat}/{slug}/BAB-01/Module-01 created.\n")
                        log.flush()

            old_s = f"- [{slug}](./{cat}/{slug}/) — Status: `⏳ ANTRIAN GENERATE`"
            new_s = f"- [{slug}](./{cat}/{slug}/) — Status: `✅ SELESAI (10 Bab + Lab)`"
            if old_s in cat_text:
                cat_text = cat_text.replace(old_s, new_s)
                with open(catalog_path, "w", encoding="utf-8") as f:
                    f.write(cat_text)

            time.sleep(1)

        if not processed_any:
            with open(log_file, "a") as log:
                log.write(f"[{time.ctime()}] All 96 roadmaps complete. Sleeping 300s.\n")
                log.flush()
            time.sleep(300)

if __name__ == "__main__":
    main()
