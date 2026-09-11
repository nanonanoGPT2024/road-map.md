# BAB 03 — Quiz, Challenge, & Knowledge Check: Dockerfile Engineering & Optimization

## A. Quiz Evaluasi Pemahaman

### Bagian 1: Soal Tingkat Dasar (Basic)
1. Apa perbedaan mendasar antara instruksi `COPY` dan `ADD` di Dockerfile, dan mengapa `COPY` lebih direkomendasikan?
2. Mengapa urutan instruksi di dalam Dockerfile sangat menentukan kecepatan build berikutnya (*Build Cache*)?
3. Apa perbedaan antara variabel `ARG` dan `ENV` dalam hal siklus hidup (kapan variabel tersebut ada)?
4. Jelaskan perbedaan antara *Exec Form* (`CMD ["node", "app.js"]`) dan *Shell Form* (`CMD node app.js`) dalam menangani sinyal `SIGTERM`!
5. Sebutkan 3 folder atau file yang wajib dimasukkan ke dalam file `.dockerignore` pada proyek Node.js atau Python!

### Bagian 2: Soal Tingkat Menengah (Intermediate)
6. Bagaimana cara kerja instruksi `COPY --from=<stage>` pada pola Multi-Stage Build dalam memangkas ukuran image akhir?
7. Mengapa menggabungkan perintah instalasi dan pembersihan cache (`apt-get update && apt-get install ... && rm -rf /var/lib/apt/lists/*`) dalam satu baris instruksi `RUN` sangat penting dalam arsitektur OverlayFS?
8. Apa perbedaan teknis antara base image **Alpine Linux** dan **Google Distroless**, serta mengapa Distroless dianggap memiliki tingkat keamanan lebih tinggi?
9. Apa yang terjadi jika sebuah binary Go yang dikompilasi secara dinamis (*dynamically linked*) dijalankan di atas base image `scratch`?
10. Mengapa menyalin file `package.json` dan menjalankan `npm ci` sebelum menyalin source code (`COPY . .`) dianggap sebagai *Best Practice* paling fundamental di Dockerfile?

### Bagian 3: Pertanyaan Skenario Nyata (Scenario-Based)
11. **Skenario 1**: Seorang developer mengeluh bahwa pipeline CI GitHub Actions selalu memakan waktu 12 menit setiap kali ada commit baru, padahal ia hanya mengubah satu baris komentar di file `index.ts`. Setelah memeriksa Dockerfile, baris pertama adalah `COPY . .` diikuti oleh `RUN npm install`. Jelaskan analisis Anda dan tuliskan urutan instruksi yang benar!
12. **Skenario 2**: Sebuah audit keamanan menemukan bahwa image produksi container Java Spring Boot berukuran 1.4GB dan memiliki 38 kerentanan keamanan level `HIGH` pada paket sistem operasi Debian. Rancang strategi Multi-Stage Build menggunakan base image Distroless Java untuk mengeliminasi seluruh kerentanan tersebut!
13. **Skenario 3**: Sebuah binary microservice Go yang dideploy di dalam base image `scratch` gagal melakukan panggilan HTTP request ke payment gateway pihak ketiga dengan error `x509: certificate signed by unknown authority`. Jelaskan akar masalahnya dan bagaimana memperbaikinya di Dockerfile!

---

## B. Practical Chapter Challenge: Ultra-Lean Production Microservice Dockerfile

### Deskripsi Skenario
Rancang Dockerfile multi-stage tingkat enterprise untuk aplikasi REST API TypeScript/Node.js atau Go yang memenuhi standar keamanan dan optimasi tertinggi.

### Persyaratan Implementasi:
1. **Multi-Stage Architecture**:
   - **Stage 1 (Builder)**: Menggunakan SDK image lengkap untuk kompilasi TypeScript atau Go, dengan isolasi cache dependensi.
   - **Stage 2 (Production Release)**: Menggunakan minimal base image (Alpine Slim atau Distroless).
2. **Layer Caching Optimization**:
   - Manifes paket dependensi harus disalin terlebih dahulu sebelum source code.
   - Bersihkan seluruh cache package manager di layer yang sama.
3. **Security Hardening**:
   - Gunakan user non-root eksplisit (misal UID 1000 atau `USER nonroot`).
   - Sertakan file `.dockerignore` komprehensif.
   - Gunakan Exec Form untuk seluruh instruksi execution (`ENTRYPOINT` / `CMD`).
4. **Target Metrik**:
   - Ukuran image final wajib di bawah 150MB (untuk Node.js) atau di bawah 25MB (untuk Go).
   - Zero vulnerability level `CRITICAL` saat dipindai.

---

## C. Knowledge Check & Mastery Checklist

### Saya Harus Memahami:
- [ ] Struktur internal OCI Image layers dan Content Addressable Storage (SHA-256).
- [ ] Aturan main Docker Build Cache Invalidation.
- [ ] Perbedaan Exec Form vs Shell Form.
- [ ] Paradigma Multi-Stage Build (`FROM ... AS`, `COPY --from`).
- [ ] Karakteristik base image: Ubuntu, Alpine (`musl`), Distroless, dan `scratch`.

### Saya Tidak Perlu Menghafal:
- [ ] Seluruh puluhan flag compiler biner Go/Rust (cukup pahami `CGO_ENABLED=0`).
- [ ] Seluruh syntax regex file `.dockerignore` yang rumit.

### Saya Harus Bisa Melakukan:
- [ ] Menulis Dockerfile multi-stage yang memisahkan build tools dari runtime.
- [ ] Menyusun urutan instruksi Dockerfile agar cache dependensi tidak rusak saat source code diedit.
- [ ] Membuat file `.dockerignore` yang mencegah kebocoran rahasia dan folder `.git`.
- [ ] Menjalankan aplikasi sebagai non-root user di dalam container.

```text
Checklist Kesiapan BAB 03:
[ ] Memahami anatomi layer & caching Dockerfile
[ ] Menjalankan hands-on layer cache simulator m01
[ ] Menjalankan hands-on multi-stage compressor m02
[ ] Mampu menjawab seluruh pertanyaan Quiz dan Skenario
```
