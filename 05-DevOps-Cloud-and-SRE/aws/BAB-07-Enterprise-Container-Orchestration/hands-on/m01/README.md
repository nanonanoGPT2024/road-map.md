# Panduan Hands-On Lab: EKS IRSA, Karpenter, and Resilient Orchestration

Panduan ini mendemonstrasikan verifikasi arsitektur enterprise container orchestration menggunakan AWS CLI, manifest Kubernetes, dan engine simulator berbasis Python yang disertakan dalam repositori ini.

---

## 1. Persiapan Environment

Pastikan tool berikut telah terpasang di workstation Anda:
- Python 3.9 atau lebih baru.
- AWS CLI v2 (`aws --version`).
- `kubectl` (`kubectl version --client`).

---

## 2. Menjalankan Skrip Verifikasi & Simulasi

Skrip `eks_irsa_karpenter_sim.py` menyimulasikan algoritma kriptografi OIDC STS pada IRSA, perhitungan bin-packing Karpenter v1, dan circuit breaker outlier detection pada AWS Service Connect tanpa membutuhkan akun cloud berbayar.

Jalankan skrip langsung dari terminal:
```bash
python3 eks_irsa_karpenter_sim.py
```

### Hasil yang Diharapkan:
1. **TEST 1 (IRSA)**:
   - Skenario 1.a (Authorized Pod): Memvalidasi subject claim namespace dan menghasilkan STS temporary token (`ASIA...`).
   - Skenario 1.b (Rogue Pod): Secara otomatis memblokir usaha privilege escalation antar namespace dengan status `SECURE / BLOCKED`.
2. **TEST 2 (Karpenter Autoscaling)**:
   - Menghitung bin-packing 45 pod pending dan memilih komposisi instance optimal (`c6g`/`m6g` Spot).
   - Menampilkan perbandingan efisiensi biaya (> 60% saving) dan waktu booting (~38 detik vs ~320 detik pada ASG).
3. **TEST 3 (Service Connect / Envoy Mesh)**:
   - Mensimulasikan pemutusan circuit saat 3 error 5xx berturut-turut terdeteksi, menghasilkan error `503 Host Ejected`.
   - Menguji pemulihan otomatis traffic setelah masa cooldown 1.5 detik selesai.

---

## 3. Langkah Implementasi Nyata di AWS EKS (Hands-on CLI)