import urllib.request, json, os, sys, time

# Baca API Key untuk 9router lokal
key = ""
with open("/root/.hermes/.env") as f:
    for line in f:
        if line.startswith("HERMES_CUSTOM_LOCALHOST_20128_API_KEY="):
            key = line.strip().split("=", 1)[1]

MODELS = [
    "ag/claude-sonnet-4-6",
    "ag/claude-opus-4-6-thinking",
    "ag/gpt-oss-120b-medium",
    "ag/gemini-3.8-flash"
]

def query_llm(prompt, system_prompt="Anda adalah Senior Technical Curriculum Architect sesuai panduan GEMINI.md."):
    for m in MODELS:
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
            "Authorization": f"Bearer {key}"
        })
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                raw = resp.read().decode("utf-8")
                # Parse stream/SSE or JSON
                lines = raw.strip().split("\n")
                content = ""
                for line in lines:
                    line = line.strip()
                    if line.startswith("data: ") and not line.endswith("[DONE]"):
                        try:
                            chunk = json.loads(line[6:])
                            delta = chunk.get("choices", [{}])[0].get("delta", {}).get("content", "")
                            content += delta
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
            print(f"[Model {m} failed]: {e}, trying next...")
            time.sleep(2)
    return None

if __name__ == "__main__":
    print("Worker engine ready.")
