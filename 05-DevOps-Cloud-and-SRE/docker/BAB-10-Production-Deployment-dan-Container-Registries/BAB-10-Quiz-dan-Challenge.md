# BAB 10 — Quiz & Chapter Challenge: Production Deployment & Container Registries

Dokumen ini menguji penguasaan Anda terhadap arsitektur distribusi image kontainer (OCI Distribution Specification, Harbor, ECR, GHCR), keamanan autentikasi & credential helpers, strategi tagging immutability, integrasi Linux init system (Systemd Unit Files), otomasi deployment (Watchtower), dan pemeliharaan disk berkala (Automated Pruning).

---

## Bagian 1: Basic Quiz (5 Pertanyaan)

### Soal 1
Mengapa penggunaan tag `:latest` (misal `myorg/api:latest`) sangat dilarang untuk file deployment produksi di Kubernetes atau Docker Compose?
- A. Karena Docker CLI menolak men-download tag yang mengandung kata "latest".
- B. Karena tag `:latest` bersifat mutable (dapat ditimpa kapan saja), sehingga tidak memberikan jaminan deterministik tentang versi kode mana yang sebenarnya sedang berjalan dan menyulitkan proses rollback saat insiden.
- C. Karena tag `:latest` otomatis mengonsumsi RAM dua kali lipat.
- D. Karena tag `:latest` tidak mendukung SSL.

### Soal 2
Apa fungsi utama dari **Docker Credential Helper** (`wincred`, `secretservice`, atau `osxkeychain`)?
- A. Mempercepat koneksi internet saat mengunduh image.
- B. Mencegah penyimpanan password dan auth token registry dalam format teks terbuka (base64 plaintext) di file `~/.docker/config.json` dengan menyimpannya di keychain/vault terenkripsi tingkat sistem operasi.
- C. Menghapus image lama secara otomatis.
- D. Mengubah format biner Dockerfile.

### Soal 3
Perintah CLI manakah yang paling aman untuk membersihkan dangling images, container yang sudah mati (exited), dan cache build yang lebih lama dari 7 hari (168 jam) tanpa menghapus data volume persisten?
- A. `docker rm -f $(docker ps -aq)`
- B. `docker system prune -af --filter "until=168h"`
- C. `rm -rf /var/lib/docker`
- D. `docker volume rm $(docker volume ls -q)`

### Soal 4
Direktif Systemd Unit manakah di bagian `[Unit]` yang wajib disertakan untuk memastikan service Docker Compose hanya dijalankan setelah Docker Engine daemon dan koneksi jaringan siap?
- A. `Before=kernel.target`
- B. `Requires=docker.service` dan `After=docker.service network-online.target`
- C. `Restart=never`
- D. `Alias=docker-app`

### Soal 5
Bagaimana Watchtower mendeteksi adanya pembaruan aplikasi pada container yang sedang berjalan?
- A. Dengan membaca git log developer di GitHub.
- B. Dengan melakukan polling secara berkala ke container registry untuk membandingkan image SHA256 digest container lokal dengan digest terbaru di registry.
- C. Dengan mendengarkan port HTTP 80.
- D. Dengan membaca log terminal Linux host.

---

## Bagian 2: Intermediate Quiz (5 Pertanyaan)

### Soal 6
Dalam OCI Distribution Specification, mengapa pengunggahan dua image berbeda yang sama-sama berbasis `alpine:3.19` hanya memakan sedikit bandwidth internet saat push image kedua?
- A. Karena registry mengompresi gambar menggunakan algoritma AI.
- B. Karena registry menggunakan model Content-Addressable Storage (CAS) berbasis SHA256 layer blob; client melakukan query `HEAD /v2/.../blobs/<digest>` dan registry merespons bahwa blob sudah ada (Deduplication), sehingga upload dilewati.
- C. Karena Docker Engine kedua berjalan dalam mode rootless.
- D. Karena file sistem dienkripsi oleh SSH.

### Soal 7
Apa yang dimaksud dengan aturan **Tag Immutability** pada enterprise container registry seperti CNCF Harbor atau AWS ECR?
- A. Aturan yang melarang developer menghapus akun registry mereka.
- B. Fitur keamanan yang mencegah penimpaan (overwriting) tag image yang sudah pernah di-push sebelumnya, sehingga integritas supply-chain rilis terjamin dan tidak dapat dirusak oleh pihak mana pun.
- C. Fitur untuk mengunci port registry agar tidak bisa diakses dari internet.
- D. Aturan yang mengharuskan nama image diawali huruf kapital.

### Soal 8
Mengapa pada service unit Systemd untuk Docker Compose kita menggunakan `Type=oneshot` dan `RemainAfterExit=yes`?
- A. Karena perintah `docker compose up -d` langsung mengembalikan kontrol ke shell setelah container dibuat di background, dan `RemainAfterExit=yes` memberitahu Systemd bahwa service tersebut tetap dianggap berstatus aktif (running).
- B. Karena Systemd tidak mendukung Docker.
- C. Agar CPU server tidak melebihi 50%.
- D. Agar container otomatis di-pause setiap malam.

### Soal 9
Bagaimana cara membatasi Watchtower agar HANYA memperbarui microservice backend tertentu dan TIDAK menyentuh database PostgreSQL yang berjalan di host yang sama?
- A. Menjalankan dua instance Docker Engine di server yang sama.
- B. Menyetel environment variable `WATCHTOWER_LABEL_ENABLE=true` pada Watchtower, lalu hanya menyematkan label `com.centurylinklabs.watchtower.enable=true` pada container backend yang diizinkan.
- C. Mengunci password user postgres di Linux.
- D. Mematikan service Watchtower saat jam kerja.

### Soal 10
Mengapa perintah `docker system prune -af --volumes` sangat berbahaya jika dijalankan di server produksi database tanpa kehati-hatian ekstra?
- A. Karena dapat merusak BIOS motherboard server.
- B. Karena flag `--volumes` akan menghapus seluruh unnamed (anonymous) volume persisten yang tidak sedang terpasang pada container aktif saat itu, berpotensi memicu kehilangan data permanen.
- C. Karena perintah tersebut membatalkan lisensi kernel Linux.
- D. Karena port database akan berpindah secara acak.

---

## Bagian 3: Scenario-Based Questions (3 Skenario)

### Skenario 1: Supply Chain Tampering Incident
Sebuah perusahaan e-commerce mengalami insiden keamanan: image `mycompany/checkout-api:v2.1.0` yang berjalan di production tiba-tiba mengandung script pencuri data kartu kredit, meskipun tidak ada commit baru di branch `main` repositori Git mereka.
Hasil audit menunjukkan seorang oknum developer yang kredensialnya bocor berhasil melakukan `docker push` menimpa tag `v2.1.0` yang lama dengan image modifikasi berbahaya.
- **Pertanyaan**: Jelaskan mengapa insiden ini bisa terjadi, dan rancang kebijakan governance registry (Tag Immutability, Scopes, Cryptographic Signing) untuk mencegah sabotase semacam ini secara menyeluruh!

### Skenario 2: Downtime Akibat Server Reboot Unscheduled
Penyedia cloud VPS melakukan pembaruan hardware darurat dan me-reboot mesin host yang menjalankan 5 microservices via `docker compose`.
Ketika server selesai boot, aplikasi tidak bisa diakses selama 3 jam karena developer sedang offline dan tidak ada orang yang login via SSH untuk mengetik `docker compose up -d`.
- **Pertanyaan**: Rancang file Systemd Service Unit lengkap yang dapat ditempatkan di `/etc/systemd/system/` agar stack Docker Compose tersebut otomatis bangkit secara mandiri setiap kali server host di-reboot atau crash!

### Skenario 3: Host Disk Full Tiap Hari Senin
Sebuah tim mengadopsi pipeline CI/CD yang sangat aktif (membangun 60 image Docker per hari di runner host tunggal).
Setiap hari Senin pagi, runner selalu gagal dengan error: `no space left on device` karena akumulasi cache BuildKit dan dangling layers dari build minggu sebelumnya.
- **Pertanyaan**: Rancang solusi automated housekeeping menggunakan pasangan file `systemd.service` dan `systemd.timer` untuk membersihkan cache usang tanpa mengganggu sesi build yang sedang berjalan!

---

## Bagian 4: Chapter Challenge

### Tantangan Praktis: Production Single-Host Infrastructure Architect
1. **Skenario**:
   Anda diminta menyiapkan infrastruktur rilis satu node (single-node production host) untuk aplikasi fintech:
   - Stack aplikasi terdiri dari API backend dan Reverse Proxy Nginx.
   - Stack harus dikelola oleh Systemd service unit `/etc/systemd/system/fintech-stack.service`.
   - Menyiapkan Watchtower dengan mode label-only dan webhook notifikasi rilis.
   - Menyiapkan housekeeping cron/timer mingguan yang membersihkan layer berumur > 7 hari.
2. **Deliverables**:
   - File `docker-compose.prod.yml` dengan konfigurasi labels, healthchecks, dan logging rotation.
   - File Systemd Unit `fintech-stack.service` yang siap di-deploy.
   - File Systemd Timer `docker-housekeeping.timer` dan `docker-housekeeping.service`.

---

## Bagian 5: Knowledge Check & Checklist

### Saya Harus Memahami:
- [ ] Anatomi OCI Registry (Blob store content-addressable vs Manifest document).
- [ ] Alur autentikasi OAuth2/Bearer Token antara Docker Client dan Registry.
- [ ] Mengapa Docker Credential Helpers krusial untuk keamanan kredensial.
- [ ] Prinsip Triple-Tagging (SemVer, Git Commit SHA, Floating track).
- [ ] Konsep Tag Immutability untuk integritas supply-chain rilis.
- [ ] Peran Systemd Unit File dalam mengotomasi lifecycle Docker di OS Linux.
- [ ] Mekanisme continuous update Watchtower dan isolasi proteksi database.
- [ ] Strategi pembersihan berkala `docker system prune` dengan filter waktu.

### Saya Tidak Perlu Menghafal:
- Seluruh spesifikasi RFC OAuth2 token header secara detail.
- Syntax lengkap semua format systemd unit directives (cukup ketahui `Requires`, `After`, `ExecStart`, `ExecStop`).

### Saya Harus Bisa Melakukan:
- [ ] Melakukan `docker login` menggunakan token aman via `--password-stdin`.
- [ ] Mengonfigurasi credential helper (`wincred`, `secretservice`).
- [ ] Menulis file Systemd unit untuk menjalankan Docker Compose saat OS boot.
- [ ] Mengonfigurasi Watchtower dengan selective labels di `docker-compose.yml`.
- [ ] Membuat Systemd Timer untuk pembersihan otomatis berkala dengan filter durasi.
- [ ] Mencegah anti-pattern penggunaan tag `:latest` di lingkungan rilis.
