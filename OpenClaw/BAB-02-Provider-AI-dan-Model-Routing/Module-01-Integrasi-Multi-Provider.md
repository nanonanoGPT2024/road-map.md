# Module 01: Integrasi Multi-Provider (OpenAI, Anthropic, Gemini, & Ollama Lokal)

## 1. Learning Objective
Setelah menyelesaikan modul ini, Anda akan mampu:
- Mengonfigurasi dan mengintegrasikan berbagai provider model AI ke dalam OpenClaw Gateway.
- Menghubungkan provider komersial berbasis cloud: **Anthropic (Claude 3.5 Sonnet)**, **OpenAI (GPT-4o)**, dan **Google (Gemini 2.0 Flash)**.
- Menghubungkan provider lokal offline gratis (**Ollama / vLLM**) untuk pemrosesan data privat dan zero-cost inference.
- Mengabstraksi perbedaan format payload API (JSON schema, tool calling signatures, streaming responses) melalui arsitektur adapter terpadu.

## 2. Prerequisite
- Memahami konsep API Key, HTTP Bearer Authentication, dan JSON payload.
- Memahami konsep dasar LLM context window dan output token generation.

## 3. Concept
Setiap penyedia model kecerdasan buatan (AI Provider) memiliki spesifikasi antarmuka API yang berbeda:
- OpenAI menggunakan format Chat Completions standard (`/v1/chat/completions`) dengan array `messages` dan struktur `tools`.
- Anthropic menggunakan Messages API (`/v1/messages`) dengan header spesifik `anthropic-version: 2023-06-01` dan skema tool definition yang berbeda.
- Google Gemini menggunakan Generative Language API (`/v1beta/models/...:generateContent`) dengan struktur `contents` dan `parts`.
- Ollama menyediakan endpoint lokal (`http://localhost:11434/api/chat`) yang kompatibel dengan OpenAI schema tetapi berjalan sepenuhnya di GPU/CPU komputer Anda tanpa internet.

**OpenClaw Provider Engine** bertindak sebagai *Universal Translator (Adapter Pattern)*: modul ini menerima format pesan terpadu dari sistem gateway OpenClaw, menerjemahkannya ke format spesifik provider target, mengeksekusi request, dan mengembalikan respon yang dinormalisasi ke agen.

## 4. Why?
- **Anti Ketergantungan (Vendor Independence)**: Jika API OpenAI sedang mengalami insiden pemadaman (*outage*) atau kuota habis, asisten Anda tidak boleh lumpuh total.
- **Keseimbangan Biaya dan Kecerdasan**: Menggunakan model terbaik untuk setiap skenario (misal: model penalaran super pintar untuk analisis kode, model gratis lokal untuk sapaan dan klasifikasi sederhana).
- **Kedaulatan Privasi Data**: Beberapa instruksi (seperti membaca dokumen kontrak kerja atau password manager) hanya boleh dikirim ke model lokal di mesin sendiri.

## 5. What?
### 4 Provider AI Utama di OpenClaw:
1. **Anthropic Claude (Claude 3.5 Sonnet / Haiku)**:
   - *Kekuatan*: Kemampuan instruksi paling presisi, penulisan kode tingkat tinggi, dan kepatuhan tool calling yang sangat konsisten.
   - *Use Case*: Tugas analitik rumit, refactoring kode, dan eksekusi instruksi multi-step.
2. **OpenAI (GPT-4o / GPT-4o-mini)**:
   - *Kekuatan*: Pengolahan multimodal (audio, gambar, teks) yang sangat matang dan throughput kecepatan stabil.
   - *Use Case*: Analisis foto dokumen dan integrasi fungsi standar.
3. **Google Gemini (Gemini 2.0 Flash / Pro)**:
   - *Kekuatan*: Kecepatan respon ultra-cepat (*sub-second time-to-first-token*), context window raksasa (hingga 1-2 Juta token), dan harga per token yang sangat murah.
   - *Use Case*: Membaca dokumen PDF ratusan halaman, web scraping summarizer, dan sapaan cepat.
4. **Ollama (Local Offline: Llama 3.2, DeepSeek-R1, Mistral, Qwen)**:
   - *Kekuatan*: **100% Gratis, Zero Internet, 100% Privat**.
   - *Use Case*: Pemrosesan data rahasia, operasi saat offline di perjalanan, dan pemantauan sistem rutin tanpa biaya API.

## 6. How?
### Konfigurasi Provider di `~/.openclaw/config.json`:
```json
{
  "providers": {
    "anthropic": {
      "apiKey": "${env:ANTHROPIC_API_KEY}",
      "defaultModel": "claude-3-5-sonnet-20241022"
    },
    "openai": {
      "apiKey": "${env:OPENAI_API_KEY}",
      "defaultModel": "gpt-4o"
    },
    "google": {
      "apiKey": "${env:GEMINI_API_KEY}",
      "defaultModel": "gemini-2.0-flash"
    },
    "ollama": {
      "baseUrl": "http://127.0.0.1:11434",
      "defaultModel": "llama3.2:3b"
    }
  }
}
```

### Konfigurasi Kunci Rahasia di `~/.openclaw/.env`:
```env
ANTHROPIC_API_KEY=sk-ant-api03-...
OPENAI_API_KEY=sk-proj-...
GEMINI_API_KEY=AIzaSy...
```

## 7. Analogy
- **AI Provider = Tim Konsultan Ahli**:
  - Claude Sonnet adalah insinyur senior lulusan MIT yang Anda bayar per jam untuk memeriksa cetak biru arsitektur.
  - Gemini Flash adalah asisten magang yang membaca ribuan berkas arsip dengan sangat cepat dan murah.
  - Ollama Llama 3 adalah buku ensiklopedia offline di lemari rumah Anda yang bisa Anda baca kapan saja tanpa bayar dan tanpa perlu internet.
- **OpenClaw Provider Adapter = Penerjemah Multibahasa**: Memastikan bahwa apapun bahasa ibu konsultan Anda, Anda hanya perlu berbicara dalam satu bahasa perintah yang sama.

## 8. Diagram

```text
================ OPENCLAW UNIVERSAL PROVIDER ADAPTER ================

               [OpenClaw Unified Agent Context]
               (Role, Messages, Normalized Tools)
                               │
                               ▼
                   [Provider Adapter Layer]
                               │
         ┌─────────────────────┼─────────────────────┬─────────────────────┐
         ▼                     ▼                     ▼                     ▼
[Anthropic Adapter]   [OpenAI Adapter]      [Google Adapter]      [Ollama Adapter]
 ├── URL: /v1/messages ├── URL: /v1/chat/... ├── URL: :generate... ├── URL: localhost:11434
 ├── Header: x-api-key ├── Header: Bearer    ├── Header: x-goog... ├── No Auth Required
 └── Tool: tools array └── Tool: tool_calls  └── Tool: funcDecl    └── Tool: json format
         │                     │                     │                     │
         ▼                     ▼                     ▼                     ▼
[Claude 3.5 Sonnet]       [GPT-4o]          [Gemini 2.0 Flash]    [Llama 3.2 (Local)]
```

## 9. Simple Example: Menjalankan Model Lokal via Ollama
1. Unduh dan jalankan Ollama di mesin lokal:
   ```bash
   ollama run llama3.2:3b
   ```
2. Uji endpoint chat lokal via `curl`:
   ```bash
   curl http://localhost:11434/api/chat -d '{
     "model": "llama3.2:3b",
     "messages": [{ "role": "user", "content": "Halo OpenClaw!" }],
     "stream": false
   }'
   ```
3. Di OpenClaw, set model aktif ke Ollama:
   `openclaw config set model ollama/llama3.2:3b`

## 10. Practical Example: Normalisasi Tool Calling
Ketika agen ingin memanggil skill cuaca `get_weather(city: "Jakarta")`:
- **OpenAI**: Menghasilkan object `tool_calls: [{ id: "call_123", function: { name: "get_weather", arguments: "{\"city\":\"Jakarta\"}" } }]`.
- **Anthropic**: Menghasilkan content block `type: "tool_use", id: "toolu_01", name: "get_weather", input: { city: "Jakarta" }`.
- **OpenClaw Adapter**: Mengubah format respon di atas menjadi format internal agen standar:
  `{ action: "call_tool", toolName: "get_weather", parameters: { city: "Jakarta" } }`.
Developer custom skill tidak perlu menulis penanganan format vendor terpisah!

## 11. Real World Example
- **Edge Deployment di Pabrik / Tambang Terpencil**: Agen OpenClaw dipasang di server mini (Raspberry Pi / Intel NUC) di area tambang tanpa koneksi internet stabil. Agen menggunakan Ollama Llama 3 untuk memantau sensor mesin pabrik dan mencatat anomali secara lokal. Saat koneksi satelit Starlink menyala setiap jam 18:00, agen merutekan ringkasan harian ke Claude via cloud API.

## 12. Trade-offs

| Provider | Latensi (TTFT) | Kualitas Penalaran | Biaya per 1M Token | Kebutuhan Internet |
|---|---|---|---|---|
| **Claude 3.5 Sonnet** | Sedang (~800ms) | **Sangat Tinggi (SOTA)**| ~$3 Input / $15 Output | Wajib |
| **GPT-4o** | Cepat (~500ms) | Sangat Tinggi | ~$2.5 Input / $10 Output | Wajib |
| **Gemini 2.0 Flash** | **Ultra Cepat (~250ms)**| Tinggi | **~$0.10 Input / $0.40 Output**| Wajib |
| **Ollama (Llama 3.2 3B)**| Bergantung Hardware PC| Cukup (Basic Reasoning)| **$0 (100% GRATIS)** | **Tidak Butuh (Offline)**|

## 13. When To Use
- Integrasikan minimal **2 provider**: satu model cloud berkemampuan tinggi (Claude / GPT-4o) untuk tugas kritis, dan satu model cepat/murah (Gemini Flash atau Ollama lokal) untuk tugas harian dan heartbeat.

## 14. When NOT To Use
- Jangan gunakan model cloud untuk data yang terikat NDA ketat atau regulasi kerahasiaan perbankan; wajib gunakan Ollama lokal yang berjalan di private on-premise hardware.

## 15. Common Mistakes
1. **Hardcoding API Key di Skrip Konfigurasi**: Menyalin API key langsung ke `config.json` alih-alih merujuk ke environment variable `${env:KEY_NAME}`.
2. **Menghabiskan Kuota pada Ollama yang Belum Di-pull**: Mengonfigurasi `ollama/deepseek-r1:70b` di OpenClaw padahal model seberat 40 GB tersebut belum diunduh di Ollama lokal, menyebabkan timeout request 60 detik.
3. **Menggunakan Model Terlalu Berat untuk Chat Sederhana**: Memanggil Claude Opus atau GPT-4o hanya untuk menjawab chat *"Selamat pagi!"* dari pengguna (menghabiskan biaya token yang sia-sia).

## 16. Best Practices
- **Verifikasi Kunci dengan `openclaw doctor`**: Selalu uji validitas kunci API setelah memasukkan token baru ke `.env`.
- **Environment Variable Fallback**: Pasang default fallback key jika akun utama kehabisan saldo prepaid.
- **Batasi Output Token**: Tentukan `max_tokens: 1024` pada query percakapan biasa agar model tidak menghasilkan respon novel yang memboroskan biaya.

## 17. Troubleshooting
- **Masalah: Error `401 Unauthorized: Invalid API Key` pada Provider Anthropic**.
  - *Sebab*: API key belum diaktifkan atau memiliki format spasi/enter tersembunyi di akhir string file `.env`.
  - *Solusi*: Bersihkan spasi di file `.env`, lalu uji manual dengan:
    `curl https://api.anthropic.com/v1/messages -H "x-api-key: $ANTHROPIC_API_KEY" -H "anthropic-version: 2023-06-01"`

## 18. Hands-on Practice
Mari kita buktikan implementasi arsitektur adapter multi-provider melalui simulasi eksekusi normalisasi payload OpenAI, Anthropic, Gemini, dan Ollama di `hands-on/m01/provider_adapters_sim.js`.

## 19. Exercises & Challenge
- **Exercise**: Tuliskan perbedaan struktur header otentikasi antara OpenAI (`Authorization: Bearer <KEY>`) dan Anthropic (`x-api-key: <KEY>`).
- **Challenge**: Rancang skema *Payload Normalizer* yang secara otomatis mengubah skema JSON Schema parameter tool calling OpenAI menjadi deklarasi function call Google Gemini.

## 20. Summary
OpenClaw Provider Adapter membebaskan asisten AI Anda dari kungkungan satu ekosistem vendor. Dengan mendukung integrasi mulus ke Anthropic Claude, OpenAI, Google Gemini, dan Ollama lokal, sistem memberikan fleksibilitas penuh untuk menyeimbangkan performa penalaran, kecepatan eksekusi, privasi data, dan efisiensi biaya.
