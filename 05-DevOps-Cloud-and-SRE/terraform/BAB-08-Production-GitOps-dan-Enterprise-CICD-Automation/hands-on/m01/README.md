# Panduan Lab Hands-on: Production GitOps & Enterprise CI/CD Simulator

## 1. Deskripsi Laboratorium
Hands-on lab ini dirancang untuk mendemonstrasikan secara visual dan komprehensif bagaimana mesin GitOps enterprise (seperti **Atlantis**, **Spacelift**, dan **GitHub Actions**) mengelola alur kerja Terraform di dunia nyata tanpa memerlukan akun cloud berbayar.

Skrip simulator `atlantis_gitops_pipeline_sim.py` mengimplementasikan 4 pilar arsitektur GitOps:
1. **Concurrency Lock Engine**: Mencegah race condition ketika dua PR beroperasi di workspace/direktori yang sama.
2. **Speculative Plan Generation**: Menghasilkan artefak diff tanpa mengubah state backend.
3. **Role-Based Approval Gates (RBAC)**: Memvalidasi role pengguna sebelum mengizinkan eksekusi `apply` ke lingkungan produksi.
4. **Drift Detection Cron Pipeline**: Mendeteksi deviasi out-of-band antara remote state dan live cloud provider dengan emulasi `detailed-exitcode`.

---

## 2. Struktur Direktori
```text
hands-on/
└── m01/
    ├── README.md
    └── atlantis_gitops_pipeline_sim.py
```

---

## 3. Prasyarat Sistem
- Python versi 3.8 atau lebih baru.
- Sistem operasi Linux, macOS, atau Windows Subsystem for Linux (WSL).
- Terminal yang mendukung pewarnaan ANSI.

---

## 4. Langkah Pengujian Laboratorium

### Langkah 1: Berikan Izin Eksekusi pada Skrip
Buka terminal Anda, arahkan ke direktori lab, dan jadikan skrip dapat dieksekusi:
```bash
cd hands-on/m01
chmod +x atlantis_gitops_pipeline_sim.py
```

### Langkah 2: Jalankan Engine Simulasi
Eksekusi program secara langsung menggunakan Python 3:
```bash
python3 atlantis_gitops_pipeline_sim.py
```

---

## 5. Analisis Hasil Eksekusi Lab

Saat Anda menjalankan skrip, amati 6 fase pipeline yang disimulasikan:

1. **Skenario 1 (PR Speculative Plan)**:
   - User `alice_dev` memicu plan di environment `staging`.
   - Lock workspace `staging` berhasil diakuisisi untuk PR #101.
   - Artefak binary `/tmp/tfplan-staging-pr101.bin` dibuat.

2. **Skenario 2 (Collision Handling)**:
   - User `bob_sre` mencoba membuat plan di environment `staging` pada PR #102.
   - Simulator melempar error `LOCK REJECTED` karena PR #101 sedang aktif memegang lock.

3. **Skenario 3 (Staging Apply)**:
   - `alice_dev` mengeksekusi apply pada staging. Mutasi berhasil dan lock dilepaskan.

4. **Skenario 4 (RBAC Gate Denial)**:
   - `alice_dev` (Junior-Developer) mencoba melakukan apply perubahan destruktif pada `production`.
   - Gate menolak eksekusi dengan pesan `PERMISSION DENIED`.

5. **Skenario 5 (SRE Approval Apply)**:
   - `bob_sre` (Lead-SRE) mengeksekusi apply pada PR produksi yang sama. Otorisasi diterima dan plan dieksekusi ke state.

6. **Skenario 6 (Drift Detection Cron)**:
   - Staging diperiksa -> menghasilkan `Exit Code 0` (Clean).
   - Production diperiksa -> menghasilkan `Exit Code 2` (Drift Terdeteksi karena atribut RDS cluster `instance_class` diubah manual di luar Terraform).

---

## 6. Tugas Eksperimen Mandiri (Self-Study Exercise)
1. Buka file `atlantis_gitops_pipeline_sim.py` menggunakan teks editor Anda.
2. Tambahkan user baru `"diana_manager": "Engineering-Manager"` pada dictionary `self.user_roles`.
3. Modifikasi fungsi `run_real_apply()` agar user dengan role `Engineering-Manager` dapat memberikan approval bypass khusus ketika `destroys == 0`.
4. Jalankan ulang simulator dan amati apakah logika baru Anda berjalan sesuai prinsip GitOps!