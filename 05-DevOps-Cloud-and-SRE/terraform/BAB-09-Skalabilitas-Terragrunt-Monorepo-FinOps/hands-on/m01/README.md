# Panduan Hands-On Lab: Terragrunt Monorepo, DAG Dependency & FinOps Engine

Modul lab ini memvalidasi konsep pengelolaan monorepo skala enterprise: penguraian Directed Acyclic Graph (DAG), mitigasi circular dependency, penegakan tata kelola *default_tags*, dan evaluasi *shift-left FinOps* menggunakan skrip simulator mandiri.

---

## Prasyarat Lingkungan
- Mesin Linux, macOS, atau Windows Subsystem for Linux (WSL).
- Python versi 3.8 ke atas (menggunakan library standar bawaan tanpa perlu instalasi `pip` tambahan).

---

## Langkah 1: Eksplorasi Skrip Simulasi
Buka berkas `terragrunt_dry_catalog_sim.py` dan perhatikan bagaimana arsitektur enterprise dimodelkan:
- `CatalogNode`: Merepresentasikan blok deklarasi leaf `terragrunt.hcl`.
- `TerragruntDAGOrchestrator`: Menghitung urutan eksekusi bertahap (*topological levels*) untuk meminimalkan *blast radius*.
- `GovernanceAndFinOpsEngine`: Menggabungkan root `default_tags` dengan local tags serta menghitung delta cost layaknya Infracost.

---

## Langkah 2: Menjalankan Skrip Standar (Valid Baseline)
Berikan izin eksekusi dan jalankan simulator:

```bash
chmod +x terragrunt_dry_catalog_sim.py
python3 terragrunt_dry_catalog_sim.py
```

### Hasil yang Diharapkan:
```text
================================================================================
  TERRAGRUNT MONOREPO ARCHITECTURE & FINOPS SIMULATION ENGINE
================================================================================
... [INFO] Modul terdaftar: prod/ap-southeast-1/network/vpc (Path: ...)
... [INFO] DAG Check PASS: Tidak ada siklus sirkular. Struktur dependency valid.

----------------------------------------
FASE 2: ORKESTRASI URUTAN EKSEKUSI (BLAST RADIUS ISOLATION)
----------------------------------------
  [Tahap Eksekusi 1]:
    └── Leaf Module: prod/ap-southeast-1/network/vpc
  [Tahap Eksekusi 2]:
    └── Leaf Module: prod/ap-southeast-1/compute/eks-cluster
    └── Leaf Module: prod/ap-southeast-1/data/rds-postgres
  [Tahap Eksekusi 3]:
    └── Leaf Module: prod/ap-southeast-1/app/ingress-alb

... [INFO] Tag Compliance PASS: prod/ap-southeast-1/network/vpc
... [INFO] FinOps Gate APPROVED: Estimasi biaya berada di bawah ambang batas delta maksimum.
================================================================================
  SIMULASI BERHASIL: SELURUH PARAMETER SKALABILITAS TERVERIFIKASI AMAN.
================================================================================
```

---

## Langkah 3: Pengujian Skenario Kegagalan (Chaos Testing)

### Skenario A: Menguji Deteksi Circular Dependency
1. Buka file `terragrunt_dry_catalog_sim.py`.
2. Ubah konfigurasi node `vpc_node` agar memiliki dependensi balik ke `alb_node`:
   ```python
   vpc_node = CatalogNode(
       node_id="prod/ap-southeast-1/network/vpc",
       path="live/prod/ap-southeast-1/network/vpc/terragrunt.hcl",
       dependencies=["prod/ap-southeast-1/app/ingress-alb"], # <-- TAMBAHKAN SIKLUS INI
       ...
   )
   ```
3. Jalankan kembali script:
   ```bash
   python3 terragrunt_dry_catalog_sim.py
   ```
4. **Verifikasi**: Sistem harus memblokir proses pada FASE 1 dan melempar log `CRITICAL: Circular dependency terdeteksi`.

---

### Skenario B: Menguji Pelanggaran FinOps Guardrail
1. Kembalikan perubahan Skenario A.
2. Ubah biaya bulanan pada node EKS dari `$830.00` menjadi `$2800.00` (mensimulasikan provision node group GPU berlebih secara tidak sengaja):
   ```python
   eks_node = CatalogNode(
       node_id="prod/ap-southeast-1/compute/eks-cluster",
       ...
       monthly_cost_usd=2800.00
   )
   ```
3. Jalankan kembali script:
   ```bash
   python3 terragrunt_dry_catalog_sim.py
   ```
4. **Verifikasi**: Sistem akan lulus verifikasi DAG dan Tagging, namun gagal pada FASE 4 dengan status `[DENY]` serta melempar error exit code `1`.

---

## Kesimpulan Hands-On
Melalui simulasi ini, Anda telah mempraktikkan bagaimana Terragrunt secara matematis mengatur orkestrasi paralel, mengisolasi titik kegagalan infrastruktur, serta mengunci kepatuhan tagging dan batas finansial sebelum provisioning cloud dieksekusi.