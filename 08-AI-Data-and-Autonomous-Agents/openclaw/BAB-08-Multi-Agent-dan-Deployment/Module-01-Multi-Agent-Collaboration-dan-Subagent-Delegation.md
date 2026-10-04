# Module 01: Multi-Agent Collaboration & Subagent Delegation

## 1. Learning Objective
Setelah menyelesaikan modul ini, pembelajar akan mampu:
1. Memahami konsep arsitektur hierarki multi-agent: *Primary Orchestrator Agent* vs *Specialized Subagents*.
2. Mengonfigurasi peran (*personas*), batasan *system prompt*, dan toolset unik untuk setiap subagent.
3. Mengimplementasikan mekanisme delegasi tugas asinkron (*Agent Spawning & Task Delegation*) beserta konsolidasi hasil.
4. Mencegah *context bloat* dan pemborosan token dengan mengisolasi eksekusi tugas spesifik ke dalam subagent independen.

---

## 2. Prerequisite
- Memahami konsep tool calling dan modular skills dari [BAB 05](file:///d:/explore/roadmap.sh%20materi/OpenClaw/BAB-05-Skills-ClawHub-dan-MCP/Module-01-Menggunakan-ClawHub-dan-Membuat-Custom-Skills.md).
- Memahami konsep routing model dan token economics dari [BAB 02](file:///d:/explore/roadmap.sh%20materi/OpenClaw/BAB-02-Provider-AI-dan-Model-Routing/Module-02-Model-Routing-Fallback-dan-Token-Optimization.md).

---

## 3. Concept
Ketika sebuah tugas menjadi terlalu kompleks—misalnya: *"Riset 5 kompetitor, buat ringkasan finansial, tulis draft postingan LinkedIn, dan kirimkan ringkasannya ke WhatsApp"*—menggunakan satu agen tunggal dengan satu context window besar memiliki kelemahan fatal:
- **Context Bloat**: Context window dipenuhi ratusan baris data mentah riset, membuat reasoning model menjadi lambat dan rentan halusinasi.
- **Tool Interference**: Agen memiliki terlalu banyak tools sekaligus (30+ tools), meningkatkan risiko model salah memilih tool.
- **Model Inefficiency**: Menggunakan model cerdas mahal (seperti Claude 3.5 Sonnet) untuk pekerjaan pembersihan teks sederhana yang sebenarnya cukup ditangani oleh model ringan (seperti Claude 3.5 Haiku atau GPT-4o-mini).

**Multi-Agent Orchestration** memecah masalah ini dengan pola delegasi:
- **Orchestrator Agent (The Manager)**: Berinteraksi dengan pengguna di chat, memecah instruksi besar menjadi sub-tasks, menugaskan ke subagent yang tepat, dan menyusun laporan akhir.
- **Specialized Subagents (The Workers)**: Agen spesialis dengan system prompt tajam, tool terbatas, dan context window mandiri yang hidup sementara (*ephemeral*) hingga tugasnya selesai.

---

## 4. Why?
Mengapa arsitektur multi-agent dibutuhkan?
1. **Pemisahan Peran (Separation of Concerns)**: Subagent riset hanya memiliki tool scraping/search, subagent devops hanya memiliki tool docker/ssh. Tidak ada risiko subagent riset menyentuh server database.
2. **Efisiensi Biaya & Kecepatan**: Subagent dapat dijalankan secara paralel (*concurrent execution*). Riset 5 topik dapat didelegasikan ke 5 subagent sekaligus, memangkas waktu pengerjaan hingga 80%.
3. **Konteks Bersih (Clean Context Windows)**: Orchestrator hanya menerima rangkuman intisari dari subagent, bukan seluruh ratusan KB HTML mentah hasil browsing.

---

## 5. What?
Komponen arsitektur Multi-Agent pada OpenClaw:
- **Agent Coordinator / Dispatcher**: Modul runtime yang bertugas mem-fork instance LLM baru dengan persona dan session ID unik.
- **Subagent Manifest**: Definisi profil agent (model AI yang dipakai, system prompt, daftar tool yang diizinkan, batas iterasi).
- **Inter-Agent Message Bus**: Protokol komunikasi antar agent untuk passing argumen tugas dan mengembalikan status kemajuan (*progress / completion result*).

---

## 6. How?
Alur kerja delegasi tugas hierarkis:

```text
[ User di Telegram: "Riset tren AI 2026 & buatkan draft PR release" ]
                               │
                               ▼
               [ Primary Orchestrator Agent ]
         (Menganalisis tugas & memecah sub-task)
                               │
              ┌────────────────┴────────────────┐
              │                                 │
     (Delegasi Task 1)                 (Delegasi Task 2)
              │                                 │
              ▼                                 ▼
   [ Subagent: Researcher ]             [ Subagent: Copywriter ]
   - Model: Claude 3.5 Haiku            - Model: GPT-4o
   - Tools: web_search, fetch_page      - Tools: none (pure text synthesis)
   - Mandiri & Paralel                  - Menunggu data Task 1
              │                                 │
              └────────────────┬────────────────┘
                               │
                               ▼
               [ Primary Orchestrator Agent ]
          (Mengkonsolidasi hasil dari semua pekerja)
                               │
                               ▼
        [ Pesan Komprehensif Terkirim ke Telegram User ]
```

---

## 7. Analogy
Bayangkan **Multi-Agent Orchestration** seperti **Firma Hukum / Konsultan Eksekutif**:
- **Partner / Manajer Senior (Orchestrator)**: Menerima klien, mendengarkan kasus, dan merancang strategi besar. Manajer tidak menghabiskan waktu 8 jam memfotokopi dokumen atau membaca 500 halaman undang-undang baris demi baris.
- **Junior Associates / Peneliti (Subagents)**: Diberi instruksi spesifik: *"Tolong baca berkas putusan tahun 2024 dan berikan saya ringkasan 1 halaman dalam 30 menit."*
- Setelah menerima ringkasan 1 halaman dari para junior, Manajer mempresentasikan solusi paripurna kepada klien secara elegan.

---

## 8. Diagram
```text
+-------------------------------------------------------------+
|               PRIMARY ORCHESTRATOR AGENT                    |
|  - Role: Project Manager & Chat Communicator                |
|  - Model: Claude 3.5 Sonnet / GPT-4o                        |
+-------------------------------------------------------------+
           |                                  |
   spawn_subagent(Task A)             spawn_subagent(Task B)
           |                                  |
           v                                  v
+-----------------------+          +-----------------------+
|  SUBAGENT: RESEARCHER |          |    SUBAGENT: DEVOPS   |
|  - Tools: Tavily, Serp|          |  - Tools: Shell, Docker
|  - Model: Haiku / Mini|          |  - Model: Qwen 2.5 / DeepSeek
|  - Ephemeral Memory   |          |  - Sandboxed Runner   |
+-----------------------+          +-----------------------+
           |                                  |
           +------------------+---------------+
                              | Return Summary
                              v
             [ Orchestrator synthesizes & replies ]
```

---

## 9. Simple Example
Definisi konfigurasi subagents pada `openclaw.json`:

```json
{
  "orchestrator": {
    "defaultModel": "anthropic/claude-3-5-sonnet-20241022",
    "subagents": {
      "researcher": {
        "model": "anthropic/claude-3-5-haiku-20241022",
        "systemPrompt": "Kamu adalah peneliti data tajam. Carilah data objektif, fakta angka, dan rangkum dalam format poin padat.",
        "allowedTools": ["web_search", "fetch_url"]
      },
      "code_reviewer": {
        "model": "openai/gpt-4o",
        "systemPrompt": "Kamu adalah Senior Software Engineer. Lakukan code review terhadap diff kode berikut, fokus pada bug dan celah keamanan.",
        "allowedTools": ["read_file", "git_diff"]
      }
    }
  }
}
```

---

## 10. Practical Example
Implementasi pemanggilan subagent dari Orchestrator (Node.js):

```javascript
async function delegateTask(subagentName, taskPrompt) {
  const subagentConfig = config.subagents[subagentName];
  if (!subagentConfig) throw new Error(`Subagent ${subagentName} tidak terdaftar`);

  console.log(`[ORCHESTRATOR] Mendelegasikan tugas ke [${subagentName}]...`);
  
  // Buat context terisolasi untuk subagent
  const workerInstance = new OpenClawAgentWorker({
    model: subagentConfig.model,
    systemPrompt: subagentConfig.systemPrompt,
    tools: subagentConfig.allowedTools
  });

  const workerResult = await workerInstance.run(taskPrompt);
  return workerResult.summary;
}
```

---

## 11. Real World Example
### Kasus: Automated Weekly Competitor Intelligence Report
1. Setiap hari Senin jam 07:00, cron job memicu Primary Orchestrator.
2. Orchestrator men-spawn 3 subagent riset secara paralel:
   - *Subagent 1*: Riset rilis fitur terbaru Perusahaan A.
   - *Subagent 2*: Riset perubahan harga paket Perusahaan B.
   - *Subagent 3*: Riset sentimen pengguna di media sosial.
3. Ketiga subagent bekerja serentak di background selama 15 detik.
4. Masing-masing subagent mengembalikan ringkasan 2 paragraf ke Orchestrator.
5. Orchestrator menggabungkan ketiga laporan ke dalam format *Executive Dashboard* dan mengirimkannya ke channel Slack eksekutif.

---

## 12. Trade-offs
| Aspek | Single Monolithic Agent | Multi-Agent Hierarchy |
|---|---|---|
| **Kerapian Konteks** | Rentan kotor (*bloated context*) | Sangat bersih dan terisolasi |
| **Kecepatan** | Sekuensial (satu per satu) | Dapat dieksekusi paralel (*concurrent*) |
| **Kompleksitas Kode** | Sederhana | Lebih tinggi (memerlukan orchestrator & state aggregator) |
| **Penggunaan Token** | Boros (seluruh riwayat percakapan terbawa terus) | Hemat (subagent hanya menerima prompt spesifik tugasnya) |

---

## 13. When To Use
- Tugas kompleks yang melibatkan banyak domain keahlian berbeda (misal: analisis finansial + coding backend + penulisan copy marketing).
- Tugas riset berskala besar yang membutuhkan penelusuran puluhan sumber secara paralel.
- Menjaga batasan keamanan tool (prinsip *least privilege* antar agen).

---

## 14. When NOT To Use
- Pertanyaan sederhana sehari-hari (misal: *"Jam berapa sekarang di Tokyo?"* atau *"Apa ibukota Peru?"*).
- Menambah subagent untuk tugas sepele hanya akan menambah latency pemanggilan LLM dan pemborosan overhead.

---

## 15. Common Mistakes
1. **Overengineering Subagent Hierarchy**: Membuat 10 lapis hierarki agen untuk tugas sederhana, sehingga latency respon chat membengkak menjadi 2 menit.
2. **Infinite Delegation Loop**: Subagent A mendelegasikan tugas ke Subagent B, dan Subagent B mendelegasikannya kembali ke Subagent A. Selalu pasang *Max Recursion Depth* (misal max depth = 2).
3. **Mengirim Seluruh Konteks Obrolan ke Subagent**: Mengirimkan riwayat 50 pesan chat user ke subagent yang hanya butuh mencari 1 informasi spesifik. Cukup kirimkan *Task Objective* ringkas.

---

## 16. Best Practices
### Must Have
- Tetapkan batasan kedalaman delegasi (*max depth limit*, default: 2 tingkat).
- Batasi toolset subagent seketat mungkin sesuai kebutuhan tugasnya (*principle of least privilege*).
- Terapkan timeout per subagent (misal 30 detik) agar agen utama tidak menunggu selamanya jika ada worker yang hang.

### Recommended
- Gunakan model AI berbiaya murah dan cepat (*flash/haiku/mini*) untuk subagent pekerja tugas teknis rutin.
- Gunakan model penalaran tingkat tinggi (*sonnet/pro/o1*) hanya untuk Orchestrator pembuat keputusan.

### Avoid / Overengineering
- Jangan membuat subagent berkomunikasi bebas tanpa pengawasan Orchestrator (hindari mesh network tak terarah yang sulit di-debug).

---

## 17. Troubleshooting
| Gejala | Kemungkinan Penyebab | Solusi |
|---|---|---|
| Latensi respon ke user sangat lama (> 45 detik) | Subagent dijalankan secara sekuensial (serial) | Gunakan `Promise.all()` untuk mengeksekusi subagent secara paralel |
| Subagent gagal merespons / loop | System prompt subagent ambigu | Sediakan output schema terstruktur (JSON/Markdown template) |
| Memori RAM server melonjak tinggi | Terlalu banyak subagent di-spawn bersamaan | Batasi *concurrency pool* (maksimal 3-5 subagent aktif serentak) |

---

## 18. Exercise
1. Buat arsitektur 1 Orchestrator dan 2 Subagent:
   - `ScraperAgent`: Menghasilkan data mentah JSON.
   - `AnalystAgent`: Menganalisis data mentah dan memberikan skor insight.
2. Hubungkan alurnya agar Orchestrator menerima prompt dari user, meneruskannya ke kedua agen, dan mencetak laporan akhir.

---

## 19. Challenge
Implementasikan **Parallel Map-Reduce Agent Pattern**:
- Diberikan daftar 3 URL artikel teknologi.
- Orchestrator men-spawn 3 subagent perangkum secara serentak (`Promise.all`).
- Setiap subagent menghasilkan intisari artikel dalam waktu < 2 detik.
- Orchestrator menggabungkan (*reduce*) intisari tersebut menjadi satu laporan perbandingan tren.

---

## 20. Summary
- Multi-Agent Orchestration adalah standar industri untuk menyelesaikan alur kerja autonomous yang rumit tanpa mengalami context pollution.
- Pola *Orchestrator-Worker* memungkinkan eksekusi paralel, efisiensi biaya model routing, dan keamanan berbasis *least privilege*.
- Modul praktikum lab dapat dijalankan langsung di [hands-on/m01/multi_agent_delegator.js](file:///d:/explore/roadmap.sh%20materi/OpenClaw/BAB-08-Multi-Agent-dan-Deployment/hands-on/m01/multi_agent_delegator.js).
