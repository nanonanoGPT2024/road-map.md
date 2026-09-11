# Module 02: Model Routing, Fallback Provider, & Token Budget Optimization

## 1. Learning Objective
Setelah menyelesaikan modul ini, Anda akan mampu:
- Merancang aturan **Model Routing** dinamis berdasarkan intent instruksi, ukuran payload, atau perintah eksplisit pengguna.
- Mengimplementasikan mekanisme **Automated Failover & Fallback** saat provider utama mengalami gangguan (*Outage 500/503*) atau kehabisan kuota (*Rate Limit 429*).
- Mengendalikan pengeluaran biaya API melalui teknik **Token Budget Optimization**, **Context Compaction**, dan **Prompt Caching**.
- Memasang sistem *Hard Budget Ceiling* untuk mencegah pembengkakan tagihan tak terkendali.

## 2. Prerequisite
- Memahami konsep integrasi multi-provider dari Module 01.
- Memahami konsep Circuit Breaker dan HTTP status codes (429, 500, 503).

## 3. Concept
Dalam operasional agen AI otonom 24/7, mengirimkan seluruh pesan tanpa pandang bulu ke satu model tercanggih (seperti Claude 3.5 Sonnet atau GPT-4o) adalah pemborosan biaya besar dan risiko keandalan (*Single Point of Failure*).

Dua pilar optimasi operasional OpenClaw adalah:
1. **Intelligent Model Routing & Failover**:
   - Pesan sederhana dirutekan ke model cepat dan hemat (**Gemini Flash**).
   - Analisis logika mendalam dirutekan ke model penalaran (**Claude Sonnet**).
   - Jika Claude mengembalikan error `429 Too Many Requests` atau `503 Service Unavailable`, gateway secara instan mengalihkan instruksi ke **GPT-4o** atau model cadangan lokal tanpa disadari oleh pengguna.
2. **Token Economy & Context Compaction**:
   - Sesi percakapan yang panjang tidak boleh memuat 100 riwayat chat masa lalu ke dalam setiap prompt. Konteks lama wajib diringkas (*compacted*) menjadi memori padat untuk menghemat 70-80% konsumsi token.

## 4. Why?
- **Keberlanjutan Finansial (Cost Control)**: Pengguna aktif yang mengobrol dan menjalankan puluhan task proaktif harian dapat menghabiskan \$50 - \$100 per bulan jika tidak dioptimasi. Dengan routing cerdas, biaya dapat ditekan menjadi < \$5 per bulan tanpa menurunkan kualitas jawaban!
- **Ketersediaan Layanan 99.9% (Zero Downtime)**: Provider AI sering mengalami fluktuasi latensi atau pemadaman API sesaat. Fallback otomatis menjamin bot asisten di ponsel Anda selalu membalas dalam hitungan detik.

## 5. What?
### 1. Pola Routing OpenClaw:
- **Rule-Based Routing**: Mengarahkan model berdasarkan kata kunci atau tag topik (misal: ada kata `refactor`, `bug`, `class` $\rightarrow$ Claude).
- **Explicit Command Override**: Pengguna dapat memaksa model tertentu langsung dari chat Telegram:
  - `/model claude` $\rightarrow$ beralih ke Claude Sonnet.
  - `/model gemini` $\rightarrow$ beralih ke Gemini Flash.
  - `/local` $\rightarrow$ beralih ke Ollama offline.
- **Privacy Gate Routing**: Mendeteksi entitas sensitif (seperti NIK, nomor kartu kredit, password) dan otomatis mengalihkan proses ke Ollama lokal.

### 2. Rantai Failover (Fallback Chain):
$$\text{Primary: Claude Sonnet} \xrightarrow{\text{Error 429/5xx}} \text{Secondary: GPT-4o} \xrightarrow{\text{Offline}} \text{Emergency: Local Ollama}$$

### 3. Teknik Penghematan Token:
- **Prompt Caching**: Memanfaatkan fitur caching sistem prompt (Anthropic Prompt Caching) yang memotong biaya input hingga 90% pada prompt sistem yang statis.
- **Sliding Window History**: Hanya menyertakan 10 chat terakhir, sedangkan chat sebelumnya dirangkum menjadi 1 paragraf ringkas di memori agen.

## 6. How?
### Konfigurasi Model Routing di `config.json`:
```json
{
  "routing": {
    "default": "gemini-flash",
    "intents": {
      "code_engineering": "claude-sonnet",
      "deep_reasoning": "claude-sonnet",
      "summarization": "gemini-flash",
      "offline_private": "ollama-local"
    },
    "fallbacks": {
      "claude-sonnet": ["gpt-4o", "gemini-flash", "ollama-local"],
      "gemini-flash": ["gpt-4o-mini", "ollama-local"]
    },
    "budget": {
      "maxDailySpendUSD": 2.0,
      "alertThresholdUSD": 1.5
    }
  }
}
```

## 7. Analogy
- **Model Router = Manajer Restoran Bintang Lima**:
  - Jika ada pesanan minuman es teh manis (tugas sepele), manajer menyuruh barista junior (Gemini Flash).
  - Jika ada pesanan hidangan steak Wagyu spesial (tugas analitik rumit), manajer menugaskannya ke Head Chef (Claude 3.5 Sonnet).
  - Jika Head Chef tiba-tiba sakit flu di tengah jam makan malam (API Error 503), manajer langsung meminta Sous Chef (GPT-4o) untuk menggantikannya memasak hidangan tersebut tanpa mengecewakan pelanggan.

## 8. Diagram

```text
================ ALUR KERJA MODEL ROUTER & FAILOVER ================

[Instruksi Masuk dari Chat]
             │
             ▼
[Intent Classifier & Privacy Check]
             │
             ├── Ada Data Rahasia? ──(Ya)──> [Eksekusi di Ollama Lokal (Zero Cloud)]
             │
             └── (Tidak) ──> Tentukan Primary Model (misal: Claude Sonnet)
                                      │
                                      ▼
                        [Panggil Provider: Claude]
                                      │
                         ┌────────────┴────────────┐
                         │                         │
                     (Sukses)                 (Gagal 429/503/Timeout)
                         │                         │
                         ▼                         ▼
                 [Kembalikan Hasil]    [Memicu Fallback ke: GPT-4o]
                                                   │
                                      ┌────────────┴────────────┐
                                      │                         │
                                  (Sukses)                 (Gagal Lagi)
                                      │                         │
                                      ▼                         ▼
                              [Kembalikan Hasil]    [Emergency: Ollama Local]
```

## 9. Simple Example: Algoritma Context Window Compaction
Jika panjang riwayat obrolan mencapai 15 pesan:
1. Ambil pesan index 1 sampai 10.
2. Minta model kecil membuat ringkasan: *"Pengguna bernama Budi sedang mendiskusikan migrasi database Postgres ke cloud"*.
3. Ganti 10 pesan tersebut dengan 1 ringkasan tunggal.
4. Pertahankan 5 pesan terakhir apa adanya.
Hasil: Ukuran token riwayat menyusut dari **4.500 token** menjadi hanya **350 token**!

## 10. Practical Example: Penanganan Error 429 Rate Limit
Ketika akun Anthropic Anda mencapai batas *Rate Limit per Minute (RPM)*:
```javascript
try {
  return await callAnthropic(prompt);
} catch (err) {
  if (err.status === 429) {
    console.warn("⚠️ Rate limit Anthropic terlampaui! Mengalihkan ke backup GPT-4o...");
    return await callOpenAI(prompt);
  }
  throw err;
}
```
Pengguna yang sedang chat di Telegram tidak pernah melihat pesan error merah; mereka tetap mendapatkan jawaban berkualitas tinggi tepat waktu!

## 11. Real World Example
- **FinTech Personal Assistant**: Menggunakan model routing berbasis aturan ketat: Setiap kali prompt pengguna mengandung kata kunci seperti *"saldo rekening"*, *"mutasi kartu"*, atau *"nomor rekening"*, sistem otomatis mengunci model ke Ollama lokal di server private intranet bank dan mematikan pengiriman ke provider cloud manapun (*Air-gapped compliance*).

## 12. Trade-offs

| Pendekatan | Biaya Bulanan | Ketahanan (Uptime) | Kompleksitas |
|---|---|---|---|
| **Single Model (Claude Only)** | Tinggi (\$30 - \$60) | Rentan jika API outage | Sangat Rendah |
| **Static Router (Pilihan Manual)**| Sedang (\$15 - \$25) | Sedang | Rendah |
| **Dynamic Router + Fallback Chain**| **Sangat Hemat (\$3 - \$8)**| **Maksimal (> 99.9%)** | **Menengah** |

## 13. When To Use
- Wajib diaktifkan jika OpenClaw digunakan untuk automasi harian, pemantauan sistem, dan integrasi dengan pengguna lain.

## 14. When NOT To Use Dynamic Routing
- Saat melakukan benchmarking murni untuk mengevaluasi konsistensi respon dari satu model spesifik.

## 15. Common Mistakes
1. **Fallback Loop Tanpa Sirkuit Pemutus**: Melakukan retry fallback tanpa batas sehingga saat koneksi internet server mati, agen me-looping seluruh provider cloud secara membabi buta.
2. **Mengabaikan Token Ceiling**: Tidak menyetel batas harian (`maxDailySpendUSD`), sehingga ketika script loop bug terjadi di background task, saldo kredit kartu Anda terkuras habis dalam 1 malam.
3. **Mengabaikan Perbedaan Formatting Tool Calling**: Saat beralih ke fallback provider di tengah pemanggilan fungsi, format parameter harus dinormalisasi agar tool execution tidak melempar syntax error.

## 16. Best Practices
- **Daily Budget Hard-Stop**: Pasang batas maksimal pengeluaran harian (misal \$1.50 per hari). Jika batas tercapai, otomatis turunkan seluruh model ke Ollama gratis lokal dan kirim pesan peringatan ke Telegram pemilik.
- **Aktifkan Prompt Caching**: Pastikan instruksi identitas sistem agen Anda berada di awal prompt dan gunakan cache control agar provider hanya menagih 10% dari biaya token input.
- **Log Biaya per Permintaan**: Cetak estimasi biaya token pada setiap baris log respon agar Anda selalu sadar terhadap konsumsi finansial agen Anda.

## 17. Troubleshooting
- **Masalah: Biaya API melonjak drastis padahal chat harian sedikit**.
  - *Sebab*: Context window tidak di-reset atau di-compact; agen mengirim ulang seluruh riwayat obrolan dari 2 minggu yang lalu di setiap pesan baru.
  - *Solusi*: Aktifkan auto-compaction di `sessions.db` atau gunakan perintah `/reset` di chat untuk membersihkan riwayat lama.

## 18. Hands-on Practice
Mari kita buktikan kecanggihan arsitektur Model Routing dinamis, deteksi intent, auto-fallback saat terjadi error 503/429, dan pelacak budget token di `hands-on/m02/model_router_fallback.js`.

## 19. Exercises & Challenge
- **Exercise**: Hitung penghematan biaya jika sebuah sistem memproses 10.000 prompt per hari (rata-rata 1.000 input token):
  - Skenario A (100% Claude 3.5 Sonnet @ \$3/1M): \$30 per hari.
  - Skenario B (80% dialihkan ke Gemini Flash @ \$0.10/1M, 20% ke Claude): Hitung total biaya per hari!
  *(Jawaban: $(8.000 \times 0.0001) + (2.000 \times 0.003) = \$0.80 + \$6.00 = \$6.80 \text{ per hari}$ $\rightarrow$ Menghemat 77% biaya!).*
- **Challenge**: Rancang implementasi *Budget Ceiling Guard* yang otomatis memblokir panggilan API berbayar dan beralih ke Ollama jika akumulasi biaya harian melampaui \$2.00.

## 20. Summary
Model Routing dan Fallback Management adalah pilar efisiensi dan keandalan OpenClaw. Dengan mengombinasikan klasifikasi intent berbasis tugas, failover otomatis multi-provider, dan kontrol ketat atas konsumsi token, Anda memiliki asisten AI kelas dunia yang tangguh, hemat biaya, dan tidak pernah tumbang.
