# Module 02: Integrasi Model Context Protocol (MCP) Tools

## 1. Learning Objective
Setelah menyelesaikan modul ini, Anda akan mampu:
- Memahami arsitektur dan standar terbuka **Model Context Protocol (MCP)** yang dipelopori oleh Anthropic.
- Menjelaskan hubungan antara **MCP Host (OpenClaw)**, **MCP Client**, dan **MCP Server**.
- Membedakan dua mekanisme transport MCP: **`stdio`** (proses subprocess lokal) dan **`SSE`** (Server-Sent Events via HTTP).
- Menghubungkan ekosistem MCP Server resmi (PostgreSQL, GitHub, Filesystem, Google Drive) ke dalam agen OpenClaw tanpa menulis kode integrasi kustom.

## 2. Prerequisite
- Memahami konsep Skills dan Tool Calling dari Module 01.
- Pemahaman dasar tentang standard input/output (`stdin`/`stdout`) dan JSON-RPC 2.0.

## 3. Concept
Sebelum adanya standar terbuka, setiap platform AI membangun format plugin-nya sendiri: OpenAI memiliki ChatGPT Plugins/Actions, LangChain memiliki Tools, dan OpenClaw memiliki format skills sendiri. Jika sebuah perusahaan database (seperti PostgreSQL atau Snowflake) ingin agar produknya bisa diakses oleh AI, mereka harus menulis 10 plugin berbeda untuk 10 framework AI yang berbeda.

**Model Context Protocol (MCP)** adalah standar terbuka universal (diumumkan oleh Anthropic pada akhir 2024) yang menjadi "kabel USB-C" bagi dunia AI.  
Dengan MCP:
- Pengembang aplikasi (PostgreSQL, GitHub, Slack, Notion) hanya perlu membangun **satu MCP Server**.
- Klien AI manapun yang mendukung standar MCP (termasuk Claude Desktop dan **OpenClaw**) dapat langsung menyolok (*plug-and-play*) server tersebut dan mengakses seluruh data serta tools di dalamnya seketika!

## 4. Why?
- **Akses Langsung ke Ratusan Alat Komersial & Open-Source**: Anda tidak perlu membuat tool integrasi GitHub atau Postgres sendiri; gunakan MCP Server resmi yang dirawat oleh vendor resminya.
- **Isolasi Proses yang Sangat Aman**: MCP Server berjalan sebagai proses terpisah (di luar proses gateway OpenClaw). Jika server database mengalami error atau crash, proses utama OpenClaw tetap berjalan stabil.
- **Standarisasi Tiga Primitif Utama**: MCP tidak hanya menyediakan eksekusi fungsi (*Tools*), tetapi juga *Resources* (dokumen bacaan) dan *Prompts* (template instruksi teruji).

## 5. What?
### Tiga Komponen Utama Protokol MCP:
1. **MCP Host (OpenClaw)**: Aplikasi agen pengendali yang mengoordinasikan interaksi pengguna, LLM, dan koneksi server.
2. **MCP Client**: Modul internal di dalam OpenClaw yang memegang koneksi 1-to-1 ke masing-masing MCP Server melalui protokol JSON-RPC 2.0.
3. **MCP Server**: Program mandiri ringan yang mengekspos kapabilitas khusus (misal: server database lokal, server sistem file, server API GitHub).

### Tiga Primitif MCP (Capabilities):
- **Tools**: Fungsi yang dapat dipanggil LLM untuk mengambil aksi (misal: `execute_sql_query`, `create_github_issue`).
- **Resources**: Data pasif yang dapat dibaca oleh LLM (seperti file log, skema tabel database).
- **Prompts**: Template prompt pra-konfigurasi yang disediakan oleh pembuat server (misal: prompt *"Analisis Rencana Eksekusi Query"*).

### Dua Mekanisme Transport:
1. **`stdio` (Standard I/O)**: Client menjalankan MCP server sebagai subprocess lokal di komputer yang sama dan berkomunikasi melalui stream `stdin` dan `stdout`. Paling cepat, aman, dan tanpa overhead jaringan.
2. **`SSE` (Server-Sent Events over HTTP)**: Client terhubung ke MCP server jarak jauh (*remote server*) melalui internet via HTTP POST dan SSE stream.

## 6. How?
### Mendaftarkan MCP Server di `~/.openclaw/config.json`:
```json
{
  "mcpServers": {
    "postgres": {
      "transport": "stdio",
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-postgres", "postgresql://user:pass@localhost:5432/mydb"]
    },
    "github": {
      "transport": "stdio",
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "${env:GITHUB_TOKEN}"
      }
    },
    "filesystem": {
      "transport": "stdio",
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/Users/budi/projects"]
    }
  }
}
```

## 7. Analogy
- **Dunia Sebelum MCP = Zaman Colokan Handphone Tahun 2000-an**: Nokia punya colokan jarum kecil, Sony Ericsson punya colokan lebar bergerigi, Motorola punya colokan mini. Anda harus membawa 5 charger berbeda di tas.
- **Model Context Protocol (MCP) = Standar USB Type-C**: Satu kabel standar universal yang sama dapat digunakan untuk men-charge laptop, menyambungkan monitor eksternal, menghubungkan harddisk eksternal, dan menghubungkan mouse tanpa peduli siapa pabrikan perangkat tersebut.

## 8. Diagram

```text
================ ARSITEKTUR OPENCLAW MCP INTEGRATION ================

              ┌────────────────────────────────────────┐
              │          OPENCLAW GATEWAY DAEMON       │
              │                                        │
              │  ┌──────────────────────────────────┐  │
              │  │      OpenClaw MCP Client         │  │
              │  └──────────────────┬───────────────┘  │
              └─────────────────────┼──────────────────┘
                                    │ (JSON-RPC 2.0 via stdio / SSE)
         ┌──────────────────────────┼──────────────────────────┐
         ▼                          ▼                          ▼
┌─────────────────┐        ┌─────────────────┐        ┌─────────────────┐
│ MCP Server:     │        │ MCP Server:     │        │ MCP Server:     │
│ PostgreSQL      │        │ GitHub API      │        │ Filesystem      │
├─────────────────┤        ├─────────────────┤        ├─────────────────┤
│ Tools:          │        │ Tools:          │        │ Tools:          │
│ - run_query     │        │ - open_pr       │        │ - read_file     │
│ - describe_table│        │ - create_issue  │        │ - list_directory│
└────────┬────────┘        └────────┬────────┘        └────────┬────────┘
         ▼                          ▼                          ▼
   [Local Database]          [GitHub Cloud]             [Folder Lokal]
```

## 9. Simple Example: Format Protokol JSON-RPC 2.0 pada MCP
1. **Client Meminta Daftar Tool (`tools/list`)**:
   ```json
   {
     "jsonrpc": "2.0",
     "id": 1,
     "method": "tools/list"
   }
   ```
2. **Server Mengembalikan Deklarasi Tool**:
   ```json
   {
     "jsonrpc": "2.0",
     "id": 1,
     "result": {
       "tools": [
         {
           "name": "query_database",
           "description": "Menjalankan query SELECT SQL read-only pada database perusahaan",
           "inputSchema": {
             "type": "object",
             "properties": { "sql": { "type": "string" } },
             "required": ["sql"]
           }
         }
       ]
     }
   }
   ```
3. **Client Memanggil Tool (`tools/call`)**:
   ```json
   {
     "jsonrpc": "2.0",
     "id": 2,
     "method": "tools/call",
     "params": {
       "name": "query_database",
       "arguments": { "sql": "SELECT count(*) FROM users;" }
     }
   }
   ```

## 10. Practical Example: Tanya Jawab Database via Chat Telegram
Setelah menghubungkan MCP Server PostgreSQL ke OpenClaw:
1. Anda membuka Telegram dan mengirim pesan: *"Berapa total pengguna baru yang mendaftar hari ini?"*
2. OpenClaw membaca deskripsi tool dari MCP Server PostgreSQL.
3. LLM menghasilkan panggilan: `query_database("SELECT count(*) FROM users WHERE created_at >= CURRENT_DATE")`.
4. MCP Client mengirimkan RPC ke MCP Server PostgreSQL, mengeksekusi query, dan menerima hasil: `[{ count: 142 }]`.
5. OpenClaw membalas di Telegram: *"Hari ini terdapat 142 pengguna baru yang terdaftar di platform."*.
**Anda baru saja membuat antarmuka Business Intelligence mobile tanpa menulis sebaris kode backend pun!**

## 11. Real World Example
- **Automasi Incident Response SRE**: Tim DevOps menghubungkan MCP Server Kubernetes dan MCP Server Datadog ke OpenClaw. Ketika ada laporan service lambat, insinyur cukup chat di Discord: *"Tolong tampilkan pod yang mengalami restart terbanyak dalam 1 jam terakhir dan cek grafik penggunaan memorinya"*. Agen memanfaatkan kedua MCP Server tersebut untuk mengumpulkan metrik dan log secara instan.

## 12. Trade-offs

| Parameter | Native OpenClaw Skills | Model Context Protocol (MCP) |
|---|---|---|
| **Standar Ekosistem** | Proprietary OpenClaw | **Standar Industri Terbuka (Anthropic)** |
| **Portabilitas** | Hanya berjalan di OpenClaw | Berjalan di Claude Desktop, Cursor, OpenClaw |
| **Isolasi Proses** | Berjalan di dalam proses daemon | Berjalan di proses subprocess / remote terpisah |
| **Koleksi Server** | Spesifik ClawHub | Ratusan MCP Server resmi dari vendor dunia |

## 13. When To Use MCP
- Menghubungkan agen ke sistem enterprise pihak ketiga yang sudah memiliki MCP Server resmi (PostgreSQL, GitHub, GitLab, Docker, Jira, Google Drive).

## 14. When NOT To Use MCP
- Fungsi logika kecil yang hanya terdiri dari 5 baris kode utilitas lokal (lebih ringan menggunakan Custom Skill langsung daripada membuat server JSON-RPC terpisah).

## 15. Common Mistakes
1. **Memberikan Izin Akses Tulis Penuh pada MCP Database Server**: Menghubungkan database produksi dengan kredensial user superadmin (`postgres`). Jika LLM salah paham atau terkena prompt injection, LLM bisa mengeksekusi `DROP TABLE`! Selalu gunakan kredensial read-only (`SELECT` only) untuk MCP Server database.
2. **Koneksi Subprocess Hang Tanpa Timeout**: MCP server lokal mengalami deadlock saat mengeksekusi proses berat, menyebabkan stream `stdin`/`stdout` macet dan gateway menunggu tanpa batas. Pasang batas waktu timeout RPC (misal 30 detik).
3. **Menghabiskan RAM dengan Membuka Terlalu Banyak MCP Server**: Menjalankan 20 subprocess MCP Server berbasis Node.js/Python di server VPS kecil akan menghabiskan memori RAM. Aktifkan hanya server yang benar-benar dibutuhkan.

## 16. Best Practices
- **Prinsip Read-Only Connection**: Batasi hak akses kredensial yang diberikan kepada MCP Server ke tingkat seminimal mungkin.
- **Audit Tool List Dinamis**: Nonaktifkan tool MCP yang tidak relevan agar daftar deklarasi tool di system prompt tidak memakan ribuan token konteks secara sia-sia.
- **Gunakan Transport `stdio` untuk Keamanan Maksimal**: Hindari mengekspos MCP server via remote SSE HTTP tanpa otentikasi token Bearer dan TLS.

## 17. Troubleshooting
- **Masalah: Error `Spawn error: npx ENOENT` saat OpenClaw mencoba menyalakan MCP Server**.
  - *Sebab*: Node.js / `npx` tidak berada di dalam path global sistem lingkungan daemon.
  - *Solusi*: Tentukan path absolut ke binary executable di konfigurasi:
    `"command": "/usr/local/bin/npx"`.

## 18. Hands-on Practice
Mari kita buktikan arsitektur protokol MCP secara langsung dengan membangun simulasi lengkap MCP Client dan MCP Server berbasis JSON-RPC 2.0 di `hands-on/m02/mcp_server_client_sim.js`.

## 19. Exercises & Challenge
- **Exercise**: Tuliskan struktur JSON-RPC 2.0 respon error standar ketika sebuah MCP server menolak eksekusi query karena pelanggaran hak akses read-only.
- **Challenge**: Rancang skema *Multi-Tenant MCP Isolation* di mana pengguna reguler hanya boleh memanggil MCP Filesystem pada folder pribadinya (`/home/user1/`), sedangkan admin dapat mengakses direktori sistem.

## 20. Summary
Model Context Protocol (MCP) adalah standar emas industri yang merevolusi cara agen AI berinteraksi dengan dunia luar. Dengan mengadopsi MCP di OpenClaw, asisten AI pribadi Anda dapat langsung terhubung ke ratusan basis data, perkakas pengembang, dan layanan komputasi global melalui satu antarmuka yang seragam, aman, dan berstandar internasional.
