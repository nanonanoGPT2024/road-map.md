# BAB 09 — Quiz, Challenge, & Knowledge Check: DevSecOps & Governance

## A. Quiz Evaluasi Pemahaman

### Bagian 1: Soal Tingkat Dasar (Basic)
1. Apa risiko keamanan utama dari menyimpan konfigurasi rahasia menggunakan Kubernetes Secret bawaan tanpa konfigurasi enkripsi etcd tambahan?
2. Jelaskan konsep *Dynamic Secrets* pada HashiCorp Vault dan bagaimana perbedaannya dengan static credentials!
3. Apa fungsi mekanisme *Shamir's Secret Sharing* dalam proses inisialisasi dan unsealing HashiCorp Vault?
4. Apa yang dimaksud dengan paradigma *Shift-Left Security* dalam pipeline DevSecOps?
5. Mengapa penggunaan container image tag `:latest` sangat tidak dianjurkan di lingkungan produksi?

### Bagian 2: Soal Tingkat Menengah (Intermediate)
6. Bagaimana cara kerja Vault Agent Sidecar Injector dalam menyalurkan kredensial rahasia ke pod aplikasi tanpa memerlukan hardcoded API token di dalam kode aplikasi?
7. Apa perbedaan antara *Static Application Security Testing* (SAST) dan *Container Vulnerability Scanning* (seperti Trivy)?
8. Mengapa menjalankan container sebagai user non-root (`runAsNonRoot: true`) dan mendrop seluruh Linux capabilities (`drop: ["ALL"]`) sangat krusial untuk mencegah serangan *container breakout*?
9. Jelaskan perbedaan peran antara *Mutating Admission Webhook* dan *Validating Admission Webhook* dalam siklus hidup API server Kubernetes!
10. Bagaimana alat penandatangan gambar seperti **Cosign** (Sigstore) melindungi sistem dari serangan *man-in-the-middle* atau pembajakan repositori container registry?

### Bagian 3: Pertanyaan Skenario Nyata (Scenario-Based)
11. **Skenario 1**: Seorang developer magang secara tidak sengaja meng-push private key AWS ke commit Git publik di GitHub. Jelaskan rencana tindakan darurat (*incident response plan*) 5 langkah dalam waktu 15 menit pertama, dan instrumen apa yang harus dipasang untuk mencegah insiden ini terulang!
12. **Skenario 2**: Audit keamanan internal menemukan bahwa 40% pod di cluster Kubernetes berjalan dengan user `root` (UID 0) dan me-mount path `/var/run/docker.sock` dari node host. Rancang arsitektur kebijakan menggunakan Kyverno/Gatekeeper untuk memblokir penambahan pod baru semacam ini tanpa mematikan layanan bisnis yang sedang aktif!
13. **Skenario 3**: Sebuah database PostgreSQL production mengalami lonjakan koneksi hang hingga batas `max_connections` tercapai. Setelah diselidiki, microservice yang menggunakan HashiCorp Vault Dynamic Secrets terus meminta kredensial baru setiap kali request HTTP masuk tanpa memperpanjang (*renew*) lease sebelumnya. Bagaimana Anda mendesain arsitektur connection pooling dan lease caching yang benar di aplikasi?

---

## B. Practical Chapter Challenge: Hardened Multi-Tier DevSecOps Pipeline

### Deskripsi Skenario
Rancang arsitektur keamanan rantai pasok (*Software Supply Chain Security*) untuk aplikasi perbankan digital.

### Persyaratan Implementasi:
1. **GitHub Actions Security Gate**:
   - Menjalankan Gitleaks untuk mencegah secret leak.
   - Menjalankan Trivy scan pada image build. Gagal jika ada CVE `CRITICAL` atau `HIGH` yang memiliki patch.
   - Menghasilkan SBOM via Syft dan menandatangani image digest dengan Cosign.
2. **HashiCorp Vault Dynamic Secret Injection**:
   - Konfigurasi Vault role database PostgreSQL dengan template pembuatan user ber-TTL 1 jam.
   - Siapkan manifest deployment Kubernetes dengan anotasi Vault Agent injector yang me-render file `/vault/secrets/db-creds.json`.
3. **Kyverno Security Governance Policy**:
   - Terapkan ClusterPolicy yang memblokir pod jika:
     - `privileged: true` atau `allowPrivilegeEscalation: true`.
     - Tidak memiliki `runAsNonRoot: true`.
     - Menggunakan host filesystem mount (`hostPath`).
     - Tidak memiliki batas alokasi memori (`resources.limits.memory`).

---

## C. Knowledge Check & Mastery Checklist

### Saya Harus Memahami:
- [ ] Arsitektur HashiCorp Vault: Barrier Encryption, Storage Engine, KV v2, Dynamic Secrets, Lease Engine.
- [ ] Alur autentikasi Kubernetes ServiceAccount dengan HashiCorp Vault.
- [ ] Spektrum pengujian DevSecOps: SAST, Secret Scanning, SCA/CVE Scanning, DAST.
- [ ] Mekanisme Admission Controllers Kubernetes (Mutating & Validating Webhooks).
- [ ] Prinsip Pod Security Standards (PSS): Privileged, Baseline, Restricted.

### Saya Tidak Perlu Menghafal:
- [ ] Nomor CVE spesifik di database NVD.
- [ ] Seluruh flag CLI command `vault operator` yang jarang digunakan.

### Saya Harus Bisa Melakukan:
- [ ] Mengonfigurasi Vault KV v2 engine dan dynamic lease rotation.
- [ ] Menjalankan pemindaian container Trivy di pipeline CI/CD dengan threshold exit code.
- [ ] Menulis policy deklaratif Kyverno / OPA Gatekeeper untuk memvalidasi pod security context.
- [ ] Mengonfigurasi Kubernetes RBAC dengan prinsip hak akses terkecil (*least privilege*).

```text
Checklist Kesiapan BAB 09:
[ ] Memahami konsep DevSecOps dan Secret Management
[ ] Menjalankan hands-on Vault simulator m01
[ ] Menjalankan hands-on Trivy & Admission controller simulator m02
[ ] Mampu menjawab seluruh pertanyaan Quiz dan Skenario
```
