# Module 01: Permission Model, Shell Sandboxing, & Human-in-the-Loop

## 1. Learning Objective
Setelah menyelesaikan modul ini, pembelajar akan mampu:
1. Memahami ancaman eksekusi kode tak terkendali pada autonomous AI agent.
2. Mengonfigurasi arsitektur perizinan berjenjang (*Least Privilege & Tiered Permissions*) pada OpenClaw.
3. Mengisolasi eksekusi command line menggunakan mekanisme sandboxing (Docker container / non-root unprivileged process).
4. Mengimplementasikan mekanisme persetujuan interaktif **Human-in-the-Loop (HITL)** sebelum perintah destruktif dieksekusi.

---

## 2. Prerequisite
- Memahami konsep dasar sistem operasi UNIX/Linux: process permissions, UID/GID, dan shell execution (`bash`, `sh`, `powershell`).
- Memahami konsep containerisasi dasar menggunakan Docker.
- Telah memahami arsitektur OpenClaw gateway dan integrasi kanal pesan dari [BAB 01](file:///d:/explore/roadmap.sh%20materi/OpenClaw/BAB-01-Fondasi-dan-Arsitektur/Module-01-Pengenalan-OpenClaw-dan-Arsitektur-Agent.md) dan [BAB 03](file:///d:/explore/roadmap.sh%20materi/OpenClaw/BAB-03-Integrasi-Kanal-Pesan/Module-01-Menghubungkan-Telegram-dan-Discord.md).

---

## 3. Concept
Memberikan kemampuan kepada LLM untuk mengeksekusi shell command adalah pedang bermata dua:
- **Kekuatan**: Agent dapat membantu mem-build aplikasi, menjalankan test, memeriksa log server, atau merestart database secara instan.
- **Bahaya**: LLM dapat mengalami halusinasi atau dimanipulasi oleh *adversarial input* untuk menjalankan perintah fatal seperti `rm -rf /`, menghapus tabel production, atau membocorkan private key SSH.

Oleh karena itu, OpenClaw menerapkan prinsip **Zero Trust Agent Execution**:
1. **Tiered Permission Model**: Perintah dibedakan menjadi:
   - *Read-Only / Safe*: Diizinkan otomatis (misal: `ls`, `git status`, `uptime`).
   - *Mutating / Moderate*: Membutuhkan konfirmasi jika di luar working directory.
   - *Destructive / Critical*: Wajib mendapatkan persetujuan eksplisit dari manusia via chat (*Human-in-the-Loop*).
2. **Process Sandboxing**: Perintah shell tidak dijalankan langsung di mesin host utama (terutama bukan sebagai user `root`), melainkan di dalam container atau lingkungan terbatas dengan *restricted filesystem* dan *network policy*.

---

## 4. Why?
Mengapa sistem sandboxing dan HITL mutlak diperlukan?
1. **Pencegahan Bencana Operasional**: Kesalahan kecil penulisan argumen oleh model (misal `rm -rf / app/data` karena salah spasi) dapat menghancurkan seluruh sistem operasi VPS.
2. **Kepatuhan & Audit**: Semua perintah shell yang dieksekusi oleh agent harus tercatat dalam immutable audit log bersama identitas pengesah (human approver).
3. **Kepercayaan Pengguna**: Pengguna merasa tenang mendelegasikan tugas kepada agent 24/7 karena tahu tindakan berbahaya tidak dapat terjadi tanpa persetujuannya di WhatsApp atau Telegram.

---

## 5. What?
Komponen sistem keamanan eksekusi OpenClaw:
- **Command Policy Engine**: Parser regex dan AST shell yang mengevaluasi apakah perintah masuk dalam *Allowlist*, *Denylist*, atau *Approval-Required List*.
- **HITL Approver Session**: State manager yang menjeda eksekusi agent, mengirim tombol interaktif (*[Setujui] / [Tolak]*) ke Telegram/Discord user, dan menunggu respons dalam batas timeout (misal 5 menit).
- **Execution Sandbox Container**: Worker container Docker sekali pakai (*ephemeral container*) dengan hak akses non-root, memori/CPU dibatasi, dan volume terisolasi.

---

## 6. How?
Alur verifikasi dan eksekusi perintah:

```text
[ Model LLM Memanggil Tool: execute_shell("drop database prod;") ]
                             │
                             ▼
             [ Command Policy Engine Evaluation ]
                             │
            ┌────────────────┴────────────────┐
     [Safe / Read-Only]              [Destructive / Critical]
            │                                 │
            │ Otomatis                        ▼
            │ Diizinkan              [ Kirim Prompt HITL ke User ]
            │                        Kanal: Telegram Bot
            │                        "Setujui drop database prod? (Y/N)"
            │                                 │
            │                         ┌───────┴───────┐
            │                     [Tolak/Timeout]  [Setujui]
            │                         │               │
            │                         ▼               ▼
            │               Batalkan & Laporkan   Lanjutkan
            │                                         │
            └─────────────────┬───────────────────────┘
                              ▼
                 [ Docker Sandbox Container ]
                 - User: non-root (UID 1000)
                 - Readonly Rootfs
                 - Cap-drop ALL
                              │
                              ▼
                   [ Hasil Output Command ]
```

---

## 7. Analogy
Bayangkan **Human-in-the-Loop** seperti **Kunci Ganda Peluncuran Rudal di Kapal Selam**:
- Kapten (LLM) dapat merekomendasikan target dan menghitung koordinat.
- Namun, tombol peluncur fisik tidak akan terhubung dengan sirkuit mesin kecuali Perwira Eksekutif (Manusia) memasukkan kunci otorisasi fisik dan memutar kunci tersebut bersamaan. Tanpa kunci manusia, perintah peluncuran otomatis dibatalkan.

---

## 8. Diagram
```text
+---------------------+
| LLM Reasoning Core  |
+---------------------+
           |
           | execute_command("git pull && pnpm build")
           v
+-------------------------------------------------------------+
|               Command Policy Interceptor                    |
|  - Denylist: rm -rf, mkfs, dd, :(){ :|:& };:               |
|  - HITL Required: sudo, docker run, kubectl delete, drop    |
|  - Auto-Allow: ls, cat, git, npm test                       |
+-------------------------------------------------------------+
           |
   [Needs Approval?] 
       |       \
     [No]      [Yes] ---> Kirim pesan ke Telegram:
       |                  "Agent ingin menjalankan: `docker restart api`"
       |                  [ APPROVE (Y) ]  [ REJECT (N) ]
       |                         |
       +-------<-- [Approved] <--+
       |
       v
+-------------------------------------------------------------+
|               Isolated Docker Container                     |
|  - Memory Limit: 512MB                                      |
|  - CPU Quota: 0.5 core                                      |
|  - Dropped Capabilities: CAP_SYS_ADMIN, CAP_NET_ADMIN       |
+-------------------------------------------------------------+
```

---

## 9. Simple Example
Konfigurasi `permissions` pada `openclaw.json`:

```json
{
  "sandbox": {
    "enabled": true,
    "provider": "docker",
    "image": "openclaw/sandbox-runner:alpine-node",
    "resourceLimits": {
      "memoryMb": 512,
      "cpuQuota": 0.5,
      "timeoutSeconds": 60
    }
  },
  "executionPolicy": {
    "autoApprove": [
      "^ls(\\s+.*)?$",
      "^cat(\\s+.*)?$",
      "^git\\s+(status|diff|log|branch)$",
      "^npm\\s+(test|run\\s+lint)$"
    ],
    "alwaysAsk": [
      "^git\\s+(push|reset|clean)",
      "^docker\\s+.*",
      "^npm\\s+(install|publish)"
    ],
    "hardBlock": [
      "rm\\s+-rf\\s+/",
      ":\\(\\)\\s*\\{.*\\};:",
      "dd\\s+if=.*",
      "shutdown",
      "reboot"
    ]
  }
}
```

---

## 10. Practical Example
Implementasi interceptor kebijakan perintah di Node.js:

```javascript
function evaluateCommandRisk(command) {
  const HARD_BLOCK = [/rm\s+-rf\s+\//i, />\s*\/dev\/sd[a-z]/i, /mkfs/i];
  const HITL_REQUIRED = [/git\s+push/i, /npm\s+publish/i, /drop\s+database/i, /systemctl\s+restart/i];

  for (const pattern of HARD_BLOCK) {
    if (pattern.test(command)) {
      return { status: 'DENIED', reason: 'Perintah terdeteksi dalam daftar blokir destruktif' };
    }
  }

  for (const pattern of HITL_REQUIRED) {
    if (pattern.test(command)) {
      return { status: 'REQUIRES_APPROVAL', reason: 'Perintah berpotensi mengubah state sistem' };
    }
  }

  return { status: 'ALLOWED', reason: 'Perintah aman (read-only/terdaftar)' };
}
```

---

## 11. Real World Example
### Kasus: Incident Response & Deployment di Telegram
1. Developer meminta bot OpenClaw di Telegram: *"Tolong deploy commit terbaru ke staging dan restart service api."*
2. OpenClaw menyusun perintah: `git pull origin main && pm2 restart payment-api`.
3. Interceptor mendeteksi `pm2 restart` berstatus `REQUIRES_APPROVAL`.
4. OpenClaw mengirim inline keyboard button ke Telegram:
   > ⚠️ **Persetujuan Diperlukan**  
   > Agent meminta eksekusi shell:  
   > `git pull origin main && pm2 restart payment-api`  
   > *Apakah Anda mengizinkan tindakan ini?*  
   > [ ✅ Setujui (Approve) ]  [ ❌ Tolak (Reject) ]
5. Developer menekan tombol `[ ✅ Setujui ]`.
6. OpenClaw mengeksekusi perintah di sandbox, memantau output hingga sukses, lalu mengonfirmasi: *"Service payment-api berhasil di-restart dalam 3.2 detik."*

---

## 12. Trade-offs
| Aspek | Full Autonomous (Tanpa HITL) | Sandboxed + Human-in-the-Loop |
|---|---|---|
| **Kecepatan Eksekusi** | Sangat cepat (tanpa jeda interaksi manusia) | Bergantung pada seberapa cepat manusia membalas approval |
| **Tingkat Keamanan** | Rendah (risiko tinggi jika LLM halusinasi atau dieksploitasi) | Sangat tinggi (semua tindakan kritis disetujui manusia) |
| **User Overhead** | Nol | Perlu mengecek notifikasi chat secara berkala saat deployment |
| **Kompleksitas Sistem** | Sederhana | Membutuhkan session manager, timer timeout, dan container runtime |

---

## 13. When To Use
- Agen yang memiliki akses shell terminal pada server production atau staging.
- Operasi sistem yang melibatkan modifikasi filesystem, database migrasi, atau API key deployment.
- Agen yang diakses oleh banyak pengguna dalam sebuah grup/organisasi kerja.

---

## 14. When NOT To Use
- Script pembersihan temporary file internal yang beroperasi di folder `/tmp` terisolasi.
- Query murni *read-only* seperti `git status` atau `uptime` (meminta approval untuk `ls` akan sangat mengganggu user experience).

---

## 15. Common Mistakes
1. **Menjalankan Agent sebagai `root`**: Menjalankan daemon OpenClaw langsung di host Linux menggunakan akun `root`. Celah keamanan apa pun akan langsung memberikan akses penuh ke mesin Anda.
2. **Regex Filter Naif**: Memblokir `rm -rf /` tetapi meloloskan `rm -rf /*` atau `sh -c "rm -rf /"`. Gunakan sandbox container ketat, bukan sekadar regex string matching.
3. **Tanpa Approval Timeout**: Jika user tidak membalas chat approval dalam 10 menit, thread agent menggantung selamanya. Selalu terapkan default timeout (misal 5 menit -> Auto Reject).

---

## 16. Best Practices
### Must Have
- Jalankan proses worker dalam Docker container dengan user non-privileged (UID 1000).
- Gunakan flag `--read-only` untuk filesystem root container, pasang hanya folder kerja yang diizinkan (`/workspace`) via bind mount.
- Wajibkan HITL approval untuk perintah yang mengubah state database, menghapus file, atau merestart service.

### Recommended
- Berikan batas waktu timeout otomatis (misal 3 menit) untuk setiap permohonan persetujuan.
- Simpan audit log setiap approval (siapa yang menyetujui, jam berapa, dan pesan prompt aslinya).

### Avoid / Overengineering
- Jangan meminta persetujuan untuk operasi pembacaan murni (*read-only*) seperti menampilkan daftar file atau membaca baris konfigurasi.

---

## 17. Troubleshooting
| Gejala | Kemungkinan Penyebab | Solusi |
|---|---|---|
| Agent macet (*hanging*) saat menjalankan perintah | Perintah memerlukan input terminal interaktif (seperti konfirmasi `[y/N]` dari apt-get) | Tambahkan flag non-interaktif, misal `apt-get install -y` atau pasang timeout eksekusi child process |
| Docker permission denied saat mengeksekusi file | Hak akses volume mount salah atau user container bukan owner | Sesuaikan UID/GID container dengan host (`docker run --user $(id -u):$(id -g)`) |
| Approval prompt tidak muncul di Telegram | Session ID terputus atau Webhook/Polling bot mengalami reconnecting | Periksa status koneksi channel gateway di `openclaw doctor` |

---

## 18. Exercise
1. Tulis fungsi evaluator perintah shell yang membagi input string menjadi 3 kategori: `SAFE`, `CONFIRM`, dan `DANGEROUS`.
2. Uji coba dengan 5 input: `ls -la`, `git commit -m "fix"`, `npm publish`, `rm -rf /var/log`, dan `uptime`.

---

## 19. Challenge
Rancang simulasi **HITL Interactive Flow Engine**:
- Ketika perintah `DANGEROUS` dideteksi, engine membuat tiket approval sementara dengan masa kedaluwarsa 5 detik.
- Jika ada input persetujuan sebelum 5 detik, eksekusi dilanjutkan di virtual sandbox.
- Jika waktu habis tanpa respons, perintah otomatis dibatalkan dengan status `TIMEOUT_ABORTED`.

---

## 20. Summary
- Keamanan adalah pilar paling fundamental dalam operasional autonomous agent 24/7.
- Kombinasi kebijakan berjenjang (*Allowlist/Denylist*), isolasi container sandbox, dan persetujuan manusia (*Human-in-the-Loop*) melindungi infrastruktur Anda dari halusinasi model dan eksekusi instruksi berbahaya.
- Modul praktikum lab dapat dijalankan langsung di [hands-on/m01/permission_sandbox_sim.js](file:///d:/explore/roadmap.sh%20materi/OpenClaw/BAB-07-Keamanan-Sandboxing-Risiko/hands-on/m01/permission_sandbox_sim.js).
