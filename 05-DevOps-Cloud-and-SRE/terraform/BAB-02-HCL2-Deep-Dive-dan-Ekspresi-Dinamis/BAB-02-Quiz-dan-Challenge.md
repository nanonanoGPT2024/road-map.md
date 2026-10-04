# Evaluasi Bab 02: HCL2 Deep Dive & Ekspresi Dinamis

---

## 1. Basic Questions (5 Soal)

### Soal 1
Manakah tipe data HCL2 di bawah ini yang tergolong ke dalam kategori **structural type**?
A. `list(string)`  
B. `map(number)`  
C. `object({ name = string, port = number })`  
D. `set(string)`  

> **Kunci Jawaban:** C  
> **Penjelasan:** `list`, `map`, dan `set` adalah *collection types* yang mewajibkan seluruh elemen bernilai homogen (tipe data yang sama). Sedangkan `object` dan `tuple` adalah *structural types* yang memungkinkan elemen di dalamnya memiliki tipe data yang heterogen (berbeda-beda).

---

### Soal 2
Ekspresi mana yang menghasilkan format Indented Heredoc yang membersihkan *leading whitespace* pada HCL2?
A. `<<<EOF ... EOF`  
B. `<<-EOF ... EOF`  
C. `<<EOF ... EOF`  
D. `""EOF ... EOF""`  

> **Kunci Jawaban:** B  
> **Penjelasan:** Sintaks `<<-EOF` memberitahu parser HCL2 untuk memotong indentasi tab atau spasi di baris penutup dan baris isi (*trimmed leading whitespace*), menghasilkan output string yang rapi tanpa spasi berlebih.

---

### Soal 3
Apa perbedaan mendasar antara generalized splat `[*]` dan legacy splat `.*`?
A. Generalized splat mengevaluasi dictionary, legacy splat mengevaluasi list.  
B. Generalized splat aman dievaluasi pada nilai non-list dan `null`, sedangkan legacy splat akan melempar fatal error jika diterapkan pada nilai non-list.  
C. Legacy splat membalikkan urutan elemen list.  
D. Generalized splat hanya dapat digunakan di blok `locals`.  

> **Kunci Jawaban:** B  
> **Penjelasan:** Operator `[*]` (generalized splat) memperlakukan nilai primitif atau non-list sebagai single-element list, dan jika nilainya `null`, ia secara aman menghasilkan empty list `[]`. Legacy splat `.*` kaku dan memicu terminasi error saat tipe data tidak sesuai ekspektasi.

---

### Soal 4
Fungsi HCL2 manakah yang paling tepat digunakan untuk menggabungkan beberapa array bersarang multi-dimensi menjadi satu array satu dimensi datar?
A. `concat()`  
B. `compact()`  
C. `flatten()`  
D. `distinct()`  

> **Kunci Jawaban:** C  
> **Penjelasan:** `flatten()` mengeliminasi tingkatan bersarang (*nested hierarchies*) dari list of lists dan menghasilkan list datar 1D. `concat()` hanya menggabungkan dua atau lebih list pada level hierarki yang sama.

---

### Soal 5
Mengapa ekspresi regex pada custom validation rule disarankan dibungkus dengan fungsi `can()`?
A. Karena fungsi regex membutuhkan permission IAM.  
B. Karena fungsi regex melempar fatal error jika polanya tidak cocok (*no match found*), bukan mengembalikan nilai boolean `false`.  
C. Agar regex berjalan secara asinkron.  
D. Karena HCL2 tidak mendukung ekspresi reguler secara native.  

> **Kunci Jawaban:** B  
> **Penjelasan:** Pada HCL2, jika fungsi `regex(pattern, string)` tidak menemukan kecocokan, evaluasi fungsi langsung melempar error dan menghentikan Terraform. Membungkusnya dengan `can(regex(...))` mengubah error tersebut menjadi nilai boolean `false`, sehingga custom validation block dapat memproses kegagalan validasi secara elegan dan menampilkan `error_message`.

---

## 2. Intermediate Questions (5 Soal)

### Soal 6
Perhatikan potongan kode HCL2 berikut:
```hcl
variable "ports" {
  type    = list(number)
  default = [80, 443, 8080]
}

output "mapped" {
  value = { for idx, p in var.ports : p => idx if p > 100 }
}
```
Berapakah hasil evaluasi output `mapped`?
A. `{"80" = 0, "443" = 1, "8080" = 2}`  
B. `{"443" = 1, "8080" = 2}`  
C. `[443, 8080]`  
D. `{ 1 = 443, 2 = 8080 }`  

> **Kunci Jawaban:** B  
> **Penjelasan:** Sintaks `{ for key, val in collection : key_expr => val_expr if condition }` menghasilkan map. Elemen `80` difilter keluar oleh klausa `if p > 100`. Elemen `443` memiliki index 1 dan elemen `8080` memiliki index 2. Maka key adalah nilai port dan value adalah indeks: `{"443" = 1, "8080" = 2}`.

---

### Soal 7
Apa yang terjadi secara internal pada Terraform state ketika sebuah elemen di posisi indeks `0` dihapus dari variabel list yang digunakan oleh resource dengan `count`?
A. Terraform hanya menghapus resource pada index 0 dan membiarkan resource lain tetap utuh.  
B. Terjadi *index-shifting*; resource pada index 1 bermutasi ke index 0, memicu penghancuran dan re-creation pada resource yang sebenarnya tidak berubah secara logika konfigurasi.  
C. Terraform otomatis mengubah strategi provisioning menjadi `for_each`.  
D. Terjadi compile error karena Terraform menolak perubahan skema array pada runtime.  

> **Kunci Jawaban:** B  
> **Penjelasan:** `count` mengidentifikasi resource dalam state menggunakan indeks numerik integer `[0]`, `[1]`, dst. Jika elemen pertama dihapus, seluruh state address bergeser mundur. Terraform membandingkan deklarasi baru dengan state lama dan mendeteksi bahwa atribut pada `[0]` berubah menjadi nilai `[1]`, dan resource pada indeks terakhir hilang, sehingga memicu re-creation massal yang berisiko tinggi terhadap downtime produksi.

---

### Soal 8
Bagaimana cara mengakses iterator atribut di dalam blok `dynamic "setting"` jika argumen `iterator` tidak dideklarasikan secara eksplisit?
A. Menggunakan `setting.value`  
B. Menggunakan `each.value`  
C. Menggunakan `self.value`  
D. Menggunakan `item.value`  

> **Kunci Jawaban:** A  
> **Penjelasan:** Jika argumen `iterator` tidak dideklarasikan secara manual di dalam blok `dynamic "LABEL"`, nama iterator default yang diinisialisasi oleh HCL2 adalah sama persis dengan label blok dynamic tersebut (`LABEL.value` dan `LABEL.key`).

---

### Soal 9
Diberikan konfigurasi berikut:
```hcl
variable "config" {
  type = any
  default = {}
}

locals {
  app_port = try(var.config.server.port, var.config.network.port, 8080)
}
```
Jika `var.config` diisi `{ network = { host = "localhost" } }`, berapakah nilai `local.app_port`?
A. `null`  
B. Melempar error `KeyNotFound`  
C. `8080`  
D. `""` (string kosong)  

> **Kunci Jawaban:** C  
> **Penjelasan:** Fungsi `try()` mengevaluasi ekspresi dari kiri ke kanan. Evaluasi pertama `var.config.server.port` gagal karena atribut `server` tidak ada. Evaluasi kedua `var.config.network.port` gagal karena atribut `port` tidak ada pada map `network`. Evaluasi ketiga bernilai primitif konstan `8080`, yang sukses dievaluasi, sehingga `8080` menjadi nilai akhir.

---

### Soal 10
Kapan sebuah tipe data `set(string)` diwajibkan sebagai input `for_each` pada resource, alih-alih tipe data `list(string)`?
A. `for_each` tidak pernah menerima `set(string)`.  
B. `for_each` pada resource hanya menerima `map` atau `set(string)`; jika input berbentuk `list(string)`, ia harus dikonversi terlebih dahulu menggunakan fungsi `toset()`.  
C. List selalu diwajibkan jika ingin mempertahankan urutan eksekusi resource.  
D. Tidak ada batasan; `for_each` menerima semua tipe data tanpa konversi.  

> **Kunci Jawaban:** B  
> **Penjelasan:** Spesifikasi HCL2 mewajibkan setiap instance yang dibuat melalui `for_each` memiliki identitas key yang unik dan tidak berurutan (*unordered and unique keys*). Oleh karena itu, HCL2 secara tegas menolak tipe `list` langsung dan mewajibkan tipe data berupa `map` atau `set(string)`.

---

## 3. Scenario-Based Questions (3 Soal Kasus Industri)

### Skenario 1: Bencana State Shifting pada AWS Security Group
Sebuah tim SRE mengelola daftar egress security group rules menggunakan konfigurasi berikut:
```hcl
variable "egress_cidrs" {
  type    = list(string)
  default = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24", "10.0.4.0/24"]
}

resource "aws_security_group_rule" "egress_rules" {
  count             = length(var.egress_cidrs)
  type              = "egress"
  from_port         = 443
  to_port           = 443
  protocol          = "tcp"
  cidr_blocks       = [var.egress_cidrs[count.index]]
  security_group_id = "sg-0123456789abcdef0"
}
```
Seorang engineer junior menghapus `"10.0.1.0/24"` dari variabel tersebut. Jelaskan dampak arsitektural yang terjadi pada `terraform apply` berikutnya, dan berikan solusi refactoring kode terbaik tanpa mengubah fungsionalitas aturan yang tersisa.

> **Analisis & Solusi:**
> 1. **Dampak Arsitektural:** Terjadi *state-address mismatch* drastis. Indeks 0 yang sebelumnya mengarah ke `10.0.1.0/24` kini menampung `10.0.2.0/24`, indeks 1 menampung `10.0.3.0/24`, dan indeks 3 dihapus. Terraform akan mendeteksi perubahan konfigurasi *in-place modification* atau *destroy-and-recreate* pada seluruh rules 0, 1, dan 2, serta menghapus rule ke-3. Selama proses re-creation, koneksi TCP port 443 dari CIDR-CIDR tersebut ke database/API eksternal berpotensi putus sesaat (*intermittent packet drop*).
> 2. **Refactoring Solusi:** Ubah representasi array menjadi `set(string)` menggunakan `for_each`:
> ```hcl
> variable "egress_cidrs" {
>   type    = set(string)
>   default = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24", "10.0.4.0/24"]
> }
> 
> resource "aws_security_group_rule" "egress_rules" {
>   for_each          = var.egress_cidrs
>   type              = "egress"
>   from_port         = 443
>   to_port           = 443
>   protocol          = "tcp"
>   cidr_blocks       = [each.value]
>   security_group_id = "sg-0123456789abcdef0"
> }
> ```
> *(Catatan: Perlu eksekusi `terraform state mv` atau blok `moved {}` untuk memindahkan resource address lama ke format baru tanpa downtime).*

---

### Skenario 2: Validasi Format Naming Policy Enterprise Multi-Account
Organisasi Anda memiliki standar kepatuhan tata kelola penamaan (*resource naming governance*) yang sangat ketat untuk Cloud Storage Bucket. Format nama bucket harus memenuhi kriteria:
1. Diawali dengan prefix identitas lingkungan: `prd-`, `stg-`, atau `dev-`.
2. Diikuti kode region: `aps1` (Singapore) atau `id1` (Jakarta).
3. Diakhiri fungsi aplikasi berupa alfanumerik huruf kecil dan strip (kebab-case) dengan panjang antara 3 hingga 15 karakter.
4. Total panjang nama tidak boleh melebihi 32 karakter.

Tuliskan blok deklarasi `variable "bucket_name"` lengkap beserta `validation` block yang mengeksekusi pemeriksaan aturan tersebut secara native di HCL2.

> **Solusi Konfigurasi:**
> ```hcl
> variable "bucket_name" {
>   type        = string
>   description = "Nama bucket S3 yang memenuhi tata kelola penamaan organisasi."
> 
>   validation {
>     condition = (
>       length(var.bucket_name) <= 32 &&
>       can(regex("^(prd|stg|dev)-(aps1|id1)-[a-z0-9-]{3,15}$", var.bucket_name))
>     )
>     error_message = "Format nama bucket tidak valid. Nama harus memenuhi format: '(prd|stg|dev)-(aps1|id1)-<kebab-case-app>' dengan panjang maksimal 32 karakter."
>   }
> }
> ```

---

### Skenario 3: Dynamic Nested Content Injection untuk Ingress Rules
Platform Engineer Anda diminta membuat modul Terraform untuk resource Load Balancer Listener Rule. Modul ini menerima input sebuah objek yang mendefinisikan routing berbasis path dan host headers. Beberapa rule membutuhkan `path_pattern`, beberapa membutuhkan `host_header`, dan beberapa membutuhkan keduanya secara bersamaan. Jika salah satu kondisi tidak ditentukan, blok kondisi tersebut tidak boleh dibuat di provider API AWS.

Diberikan variabel:
```hcl
variable "routing_rules" {
  type = map(object({
    priority     = number
    action_arn   = string
    path_pattern = optional(list(string))
    host_headers = optional(list(string))
  }))
}
```
Tuliskan blok `resource "aws_lb_listener_rule"` yang mengimplementasikan blok dinamis bersyarat (*conditional dynamic nested blocks*) untuk `condition` block.

> **Solusi Konfigurasi:**
> ```hcl
> resource "aws_lb_listener_rule" "routing" {
>   for_each     = var.routing_rules
>   listener_arn = "arn:aws:elasticloadbalancing:ap-southeast-1:123456789012:listener/app/my-lb/123"
>   priority     = each.value.priority
> 
>   action {
>     type             = "forward"
>     target_group_arn = each.value.action_arn
>   }
> 
>   # Dynamic block untuk path_pattern (hanya dibuat jika path_pattern != null)
>   dynamic "condition" {
>     for_each = each.value.path_pattern != null ? [1] : []
>     content {
>       path_pattern {
>         values = each.value.path_pattern
>       }
>     }
>   }
> 
>   # Dynamic block untuk host_header (hanya dibuat jika host_headers != null)
>   dynamic "condition" {
>     for_each = each.value.host_headers != null ? [1] : []
>     content {
>       host_header {
>         values = each.value.host_headers
>       }
>     }
>   }
> }
> ```

---

## 4. Practical Chapter Challenge

### Judul Tantangan:
**Architecting Complex Dynamic Multi-Tenant Network Topology with HCL2 Transformation Engine**

### Deskripsi Skenario:
Anda ditugaskan mendesain mesin pembuat topologi VPC multi-tenant (*VPC Peering Mesh & Subnet Directory*) menggunakan data JSON kompleks. Seluruh logika provisioning harus divalidasi, dinormalisasi, dan direkayasa tanpa menggunakan provider cloud eksternal (cukup menggunakan resource bawaan `terraform_data`).

### Kebutuhan Teknis:
1. **Validasi Skema Input Ketat:**
   - Parameter input menerima daftar tenant dengan spesifikasi CIDR IPV4.
   - Buat validasi bahwa CIDR tenant tidak boleh menggunakan default route `0.0.0.0/0` dan subnet mask harus berada di antara `/16` hingga `/24`.
2. **Flattening Matrix Engine:**
   - Setiap tenant memiliki daftar mikroservis yang memerlukan subnet private mandiri.
   - Lakukan proyeksi matrix data hierarkis multi-tier tenant menjadi representasi map 1D flat menggunakan ekspresi `flatten` dan `for`.
3. **Dynamic Topology Construction:**
   - Gunakan `terraform_data` dengan `for_each` untuk mensimulasikan pembuatan subnet.
   - Terapkan `dynamic` block di dalam metadata output `terraform_data` untuk mencatat access control list (ACL).
4. **Audit Reporting Output:**
   - Sediakan output audit ringkas menggunakan generalized splat syntax `[*]` dan cetak manifest laporan JSON menggunakan Indented Heredoc `<<-EOF`.

---