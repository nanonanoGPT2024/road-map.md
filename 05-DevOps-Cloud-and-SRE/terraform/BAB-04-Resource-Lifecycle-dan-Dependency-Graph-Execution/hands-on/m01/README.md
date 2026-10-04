# Hands-On Lab M01: Menguasai Resource Lifecycle, DAG Engine, dan Graphviz Visualization

Selamat datang di lab hands-on Bab 04. Pada lab ini, Anda akan membedah cara kerja internal Terraform Core dalam menyusun Directed Acyclic Graph (DAG), menyimulasikan siklus hidup eksekusi paralel, mengamati pencegahan bencana *destroy*, dan merender visualisasi graf infrastruktur secara nyata.

---

## 1. Persiapan Lingkungan (Prerequisites)
Pastikan sistem operasi Anda (Linux/macOS/WSL2) telah terinstal peralatan berikut:
- **Terraform CLI** (versi >= 1.5.0): [Download Terraform](https://developer.hashicorp.com/terraform/downloads)
- **Python 3** (versi >= 3.8) untuk menjalankan engine DAG simulator internal.
- **Graphviz** untuk mengubah format `.dot` menjadi gambar `.png` atau `.svg`.

### Instalasi Graphviz
- **Ubuntu/Debian**:
  ```bash
  sudo apt-get update && sudo apt-get install -y graphviz
  ```
- **macOS (Homebrew)**:
  ```bash
  brew install graphviz
  ```
- **RHEL/CentOS**:
  ```bash
  sudo yum install graphviz
  ```

---

## 2. Bagian 1: Menjalankan DAG Dependency & Lifecycle Simulator

Di dalam folder ini tersedia script simulator Python mandiri (`dag_dependency_resolver.py`) yang mereproduksi algoritma topological sorting, DFS cycle checking, dan lifecycle state transition Terraform.

### Langkah 1.1: Eksekusi Simulator
Jalankan simulator secara langsung:
```bash
python3 dag_dependency_resolver.py
```

### Langkah 1.2: Bedah Hasil Eksekusi
Amati output di terminal Anda:
1. **Pewarnaan Aksi**: Perhatikan bagaimana `terraform_data.ami_rotator` yang berubah memicu status `REPLACE` pada `aws_instance.app_server` akibat `replace_triggered_by`.
2. **Create Before Destroy**: Amati log eksekusi `[CBD Mode]`, di mana instance baru di-create terlebih dahulu sebelum instans lama di-destroy.
3. **Paralelisme Worker**: Perhatikan bagaimana `aws_subnet.public_a` dan `aws_subnet.public_b` dieksekusi secara serentak di thread worker yang berbeda karena memiliki derajat dependensi yang sama.

### Langkah 1.3: Uji Coba Simulasi `prevent_destroy`
Buka `dag_dependency_resolver.py`, cari baris:
```python
db.prevent_destroy = False
```
Ubah menjadi:
```python
db.prevent_destroy = True
db.action = "DESTROY" # Simulasikan rencana penghapusan database
```
Jalankan kembali script:
```bash
python3 dag_dependency_resolver.py
```
*Hasil yang diharapkan*: Engine langsung membatalkan eksekusi (*panic halt*) dengan melempar exception:
`CRITICAL STATE REJECTED: Resource 'aws_db_instance.primary_db' memiliki lifecycle.prevent_destroy = true.`

---

## 3. Bagian 2: Praktik Konfigurasi Riil Terraform & Graphviz

Sekarang kita akan menerapkan konsep ini menggunakan Terraform CLI secara nyata.

### Langkah 2.1: Buat Skenario Deklarasi Terraform
Buat file `main.tf` di direktori kerja hands-on ini:

```hcl
terraform {
  required_version = ">= 1.5.0"
  required_providers {
    local = {
      source  = "hashicorp/local"
      version = "~> 2.4"
    }
  }
}

# Simpul Hulu: Root Config
resource "local_file" "db_credentials" {
  filename = "${path.module}/database.json"
  content  = jsonencode({
    host     = "10.0.1.50"
    username = "dbadmin"
    port     = 5432
  })

  lifecycle {
    prevent_destroy = false
  }
}

# Simpul Pemicu Replacement
resource "terraform_data" "app_version" {
  input = "v1.0.0"
}

# Simpul Downstream dengan Lifecycle Hooks
resource "local_file" "application_manifest" {
  filename = "${path.module}/app_deployment_${terraform_data.app_version.output}.txt"
  content  = "Running with DB: ${local_file.db_credentials.id} at version ${terraform_data.app_version.output}"

  lifecycle {
    create_before_destroy = true
    replace_triggered_by = [
      terraform_data.app_version
    ]
  }
}

# Simpul Dependensi Prosedural Murni
resource "local_file" "telemetry_ping" {
  filename = "${path.module}/telemetry.log"
  content  = "App manifest generated successfully."

  depends_on = [
    local_file.application_manifest
  ]
}
```

### Langkah 2.2: Inisialisasi dan Render Visualisasi Graphviz
Inisialisasi provider:
```bash
terraform init
```

Ekspor seluruh rencana DAG Terraform ke dalam format grafik Graphviz `.dot`, kemudian render ke gambar format `.png`:
```bash
terraform graph | dot -Tpng -o terraform_dag.png
```
Buka file `terraform_dag.png` pada image viewer Anda. Anda akan melihat pohon graf yang merefleksikan simpul provider, dependensi implicit via HCL reference, dan simpul eksplisit `depends_on`.

### Langkah 2.3: Uji Coba Replacement Trigger dan Create Before Destroy
1. Lakukan deployment awal:
   ```bash
   terraform apply -auto-approve
   ```
2. Buka `main.tf`, ubah nilai input versi pada `terraform_data.app_version`:
   ```hcl
   resource "terraform_data" "app_version" {
     input = "v2.0.0" # Ubah versi aplikasi
   }
   ```
3. Jalankan `terraform apply` dengan flag konkurensi eksplisit:
   ```bash
   terraform apply -parallelism=2
   ```
4. **Evaluasi Output**: Perhatikan plan review. Terraform akan membuat file `app_deployment_v2.0.0.txt` terlebih dahulu sebelum menghapus file deployment `v1.0.0` lama.

### Langkah 2.4: Menguji Batas Toleransi `-target`
Jalankan apply yang diisolasi secara sempit:
```bash
terraform apply -target=local_file.db_credentials -auto-approve
```
Perhatikan *Warning Box* kuning besar yang dikeluarkan oleh Terraform CLI:
`Warning: Resource targeting is in effect... This can lead to an incomplete view of the infrastructure.`
Pahami mengapa mode ini dilarang keras di production kecuali untuk kebutuhan *break-glass rescue*.

---

## 4. Pembersihan Resource (Clean Up)
Untuk membersihkan seluruh artefak pengujian:
```bash
terraform destroy -auto-approve
rm -f terraform_dag.png *.txt *.json *.log
```