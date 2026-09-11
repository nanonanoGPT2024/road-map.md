# BAB 06 — Quiz, Challenge, & Knowledge Check: Multi-Container dengan Docker Compose V2

## A. Quiz Evaluasi Pemahaman

### Bagian 1: Soal Tingkat Dasar (Basic)
1. Apa perbedaan mendasar antara Docker Compose V1 (`docker-compose`) dan Docker Compose V2 (`docker compose`) dalam hal bahasa pemrograman dan cara instalasinya?
2. Mengapa sintaks `depends_on: [database]` sederhana tanpa atribut tambahan seringkali menyebabkan aplikasi API crash saat pertama kali dijalankan?
3. Apa nama file konfigurasi resmi yang direkomendasikan oleh Compose Specification modern?
4. Bagaimana cara otomatisasi Docker Compose dalam membuat nama network dan volume jika Anda tidak mendefinisikannya secara manual di YAML?
5. Perintah apa yang digunakan untuk mematikan seluruh layanan Docker Compose sekaligus menghapus seluruh Named Volumes yang terikat padanya?

### Bagian 2: Soal Tingkat Menengah (Intermediate)
6. Jelaskan bagaimana atribut `condition: service_healthy` pada `depends_on` bekerja sama dengan blok `healthcheck` untuk menjamin kesiapan database sebelum aplikasi backend dihidupkan!
7. Bagaimana Docker Compose menangani penggabungan file (*deep merge*) saat Anda menjalankan `docker compose -f compose.yaml -f compose.prod.yaml up`?
8. Apa fungsi dari fitur **Docker Compose Profiles** (`profiles: ["..."]`) dan bagaimana fitur ini menghemat penggunaan memori RAM laptop developer?
9. Mengapa file `compose.override.yaml` berbahaya jika secara tidak sengaja tertinggal di direktori server produksi saat Anda menjalankan `docker compose up`?
10. Bagaimana mekanisme Docker Compose Secrets mengamankan kredensial database dibandingkan meletakkan password langsung di file `.env`?

### Bagian 3: Pertanyaan Skenario Nyata (Scenario-Based)
11. **Skenario 1**: Sebuah tim QA mengeluh bahwa pengujian otomatis di pipeline CI sering gagal acak (flaky). Log menunjukkan backend melempar error `ECONNREFUSED` ke Redis saat detik pertama pengujian dimulai. Tuliskan potongan konfigurasi `compose.yaml` menggunakan healthcheck dan `depends_on` untuk menyelesaikan masalah ini secara permanen!
12. **Skenario 2**: Laptop developer junior memiliki RAM 16GB. Proyek memiliki 14 microservices ditambah Kafka, Elasticsearch, Kibana, dan Prometheus. Menjalankan seluruh service membuat laptop freeze. Rancang strategi Docker Compose Profiles agar developer dapat memilih untuk hanya menyalakan service inti ditambah profil yang sedang dikerjakannya!
13. **Skenario 3**: Sebuah tim ingin menggunakan file `compose.yaml` yang sama untuk local dev dan server produksi AWS. Di dev, mereka butuh live-reload bind mount, sedangkan di prod mereka butuh image registry resmi dan batasan memory cgroups. Tunjukkan struktur pemisahan file `compose.yaml`, `compose.override.yaml`, dan `compose.prod.yaml`!

---

## B. Practical Chapter Challenge: Enterprise Multi-Tier Microservices with Profiles

### Deskripsi Skenario
Rancang arsitektur Docker Compose V2 modular yang menyajikan aplikasi Three-Tier lengkap dengan pemisahan lingkungan dan profil monitoring opsional.

### Persyaratan Implementasi:
1. **File Basis (`compose.yaml`)**:
   - Service `database` (PostgreSQL 16) dengan Named Volume `db_data` dan probe healthcheck `pg_isready`.
   - Service `cache` (Redis 7) dengan probe healthcheck `redis-cli ping`.
   - Service `api` yang bergantung pada `database` dan `cache` menggunakan `condition: service_healthy`.
   - Service opsional `prometheus` dan `grafana` yang hanya aktif jika profil `monitoring` dipanggil.
2. **File Dev Override (`compose.override.yaml`)**:
   - Menambahkan bind mount source code lokal ke service `api`.
   - Membuka port 5432 dan 6379 ke host untuk kemudahan inspeksi database developer.
3. **File Prod Override (`compose.prod.yaml`)**:
   - Menggunakan image resmi dengan tag semver: `myregistry.io/api:v1.0.0`.
   - Mengikat port API hanya ke `127.0.0.1:3000:3000`.
   - Menetapkan batas alokasi cgroups: maksimal 1GB RAM dan 1.0 CPU core untuk API, serta 2GB RAM untuk Database.
   - Mengaktifkan `restart: unless-stopped`.
4. **Validasi**:
   - Verifikasi hasil merge konfigurasi produksi menggunakan `docker compose -f compose.yaml -f compose.prod.yaml config`.

---

## C. Knowledge Check & Mastery Checklist

### Saya Harus Memahami:
- [ ] Spesifikasi Compose V2 dan struktur hirarki YAML.
- [ ] Mekanisme penanganan race condition dengan `condition: service_healthy`.
- [ ] Aturan deep merge antara base compose dan override files.
- [ ] Konsep pengelompokan service menggunakan Compose Profiles.
- [ ] Substitusi variabel lingkungan via `.env` dan Docker Secrets.

### Saya Tidak Perlu Menghafal:
- [ ] Seluruh puluhan atribut usang dari spesifikasi Docker Compose v1.
- [ ] Sintaks khusus platform swarm (`deploy.placement.constraints`).

### Saya Harus Bisa Melakukan:
- [ ] Menulis file `compose.yaml` lengkap dengan dependensi healthcheck.
- [ ] Menjalankan layanan spesifik dengan profil via `--profile <name>`.
- [ ] Mengonfigurasi pemisahan environment development dan production tanpa duplikasi kode.
- [ ] Menjalankan perintah debugging dengan `docker compose exec` dan `docker compose logs`.

```text
Checklist Kesiapan BAB 06:
[ ] Memahami Compose V2 deklaratif & dependencies
[ ] Menjalankan hands-on dependency engine m01
[ ] Menjalankan hands-on overrides & profiles simulator m02
[ ] Mampu menjawab seluruh pertanyaan Quiz dan Skenario
```
