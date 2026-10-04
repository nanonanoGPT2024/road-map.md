import urllib.request, json, os, sys, time, signal

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
            with urllib.request.urlopen(req, timeout=120) as resp:
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
    log_file = os.path.join(BASE_DIR, "generator_daemon.log")
    with open(log_file, "a") as log:
        log.write(f"\n[{time.ctime()}] Resilient generator daemon started.\n")
        log.flush()

    queue = [
        ("01-Core-Foundations", "datastructures-and-algorithms", "Data Structures & Algorithms (DSA)"),
        ("01-Core-Foundations", "computer-science", "Computer Science Foundations"),
        ("02-Programming-Languages", "cpp", "C++ Modern Engineering"),
        ("02-Programming-Languages", "python", "Python Professional Mastery"),
        ("04-Backend-and-Database", "spring-boot", "Java Spring Boot Microservices"),
        ("08-AI-Data-and-Autonomous-Agents", "power-bi", "Power BI & Business Intelligence Analytics"),
        ("08-AI-Data-and-Autonomous-Agents", "ai-product-builder", "AI Product Builder Mastery")
    ]

    for cat, slug, title in queue:
        if not running:
            break
        target_dir = os.path.join(BASE_DIR, cat, slug)
        readme_path = os.path.join(target_dir, "README.md")
        if os.path.exists(readme_path) and os.path.getsize(readme_path) > 100:
            continue

        os.makedirs(target_dir, exist_ok=True)
        with open(log_file, "a") as log:
            log.write(f"[{time.ctime()}] Generating syllabus for: {cat}/{slug} ({title})...\n")
            log.flush()

        prompt = f"""Buatkan file README.md silabus lengkap 10 BAB sesuai standar GEMINI.md untuk topik resmi roadmap.sh: '{title}' ({slug}).
Format wajib: Course Overview, Learning Roadmap (Pohon ASCII 10 BAB), Navigasi Detail Bab 01 s/d Bab 10, Spesifikasi Capstone Project Enterprise. Bahasa Indonesia profesional teknis."""

        content = query_llm(prompt)
        if content:
            with open(readme_path, "w", encoding="utf-8") as f:
                f.write(content)
            with open(log_file, "a") as log:
                log.write(f"[{time.ctime()}] SUCCESS: {cat}/{slug}/README.md created.\n")
                log.flush()

            bab1_dir = os.path.join(target_dir, "BAB-01-Fondasi-dan-Arsitektur")
            m01_dir = os.path.join(bab1_dir, "hands-on", "m01")
            os.makedirs(m01_dir, exist_ok=True)

            mod_prompt = f"""Buatkan materi Bab 01 Module 01 untuk '{title}' ({slug}) format 20 seksi GEMINI.md. Bahasa Indonesia teknis."""
            mod_content = query_llm(mod_prompt)
            if mod_content:
                with open(os.path.join(bab1_dir, "Module-01-Fondasi-Konsep-Inti.md"), "w", encoding="utf-8") as f:
                    f.write(mod_content)

            time.sleep(2)

if __name__ == "__main__":
    main()
