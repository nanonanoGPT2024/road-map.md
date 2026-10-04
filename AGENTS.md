# RULES & OPERATIONAL DIRECTIVES

File ini berisi aturan operasional permanen untuk Hermes Agent di repositori ini.

---

### 1. Larangan Keras Meta-Scripting (Direct Execution Rule)
- **DILARANG KERAS MEMBUAT SCRIPT PYTHON PERANTARA UNTUK MENULIS DOKUMEN/MATERI:**
  - Jangan pernah membuat script Python (`.py`) yang memanggil API AI atau melakukan looping liar hanya untuk menghasilkan materi teks/Markdown/dokumen.
  - Jika membuat dokumen teks, Markdown, atau silabus: **TULIS LANGSUNG KE FILE TUJUAN** menggunakan tool `write_file` / `patch` tanpa script perantara.
  - Jika tugasnya kodingan masif proyek atau refactoring: **DELEGASIKAN LANGSUNG KE SPECIALIST CODING CLI** (seperti Kilo CLI `kilo run ...` atau Antigravity `agy ...`) secara headless dan terukur.
  - Dilarang meninggalkan file `.py` sampah, script generator perantara, atau daemon lokal yang mengunci resource/database.

---

### 2. Standar Integritas & Anti Asumsi (Quality Gate)
- Jangan pernah menyatakan tugas selesai jika belum diverifikasi fisik di disk (`ls`, `wc -l`, runnable test).
- Setiap BAB kurikulum wajib memiliki 4 pilar: Modul 01, Modul 02, File Kuis Mandiri (`BAB-XX-Quiz-dan-Challenge.md` >2 KB), dan Hands-on Lab nyata (`hands-on/` >400 byte runnable). Dilarang membuat file stub palsu.
- Tiket Kanban hanya boleh pindah ke `done` jika 100% materi di kategori tersebut lolos audit fisik.
