# Bab 02: HCL2 Deep Dive & Ekspresi Dinamis

---

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta didik mampu:
- Mengonstruksikan skema variabel Terraform berbasis *type system* HCL2 tingkat lanjut (*primitive*, *collection*, dan *structural typing*) dengan validasi integritas data kustom (*custom validation rules*).
- Mengimplementasikan manipulasi data kompleks menggunakan kombinasi *dynamic expressions* (`for`, percabangan ternary, *splat syntax* `[*]`) dan fungsi bawaan (*built-in functions*: `flatten`, `merge`, `lookup`, `try`, `can`).
- Menganalisis dan menentukan trade-off arsitektural antara meta-argument `count` dan `for_each` guna mencegah *resource recreation churn* akibat *index-shifting*.
- Merekayasa blok deklaratif bersarang (*nested declarative blocks*) secara dinamis menggunakan konstruksi `dynamic` dan `content` block pada resource cloud skala enterprise.

---

## 2. Prerequisite
Sebelum mempelajari modul ini, pastikan Anda telah memahami:
- Pengetahuan fundamental Terraform: CLI workflow (`terraform init`, `plan`, `apply`, `destroy`), resource blocks, dan pengelolaan `terraform.tfstate`.
- Konsep dasar variabel input (`variable`), output (`output`), dan local values (`locals`).
- Familiaritas dengan format serialisasi data JSON dan YAML.
- Pemahaman dasar arsitektur jaringan cloud (CIDR block, subnet, firewall/Security Group rules).

---

## 3. Concept
HashiCorp Configuration Language versi 2 (HCL2) adalah bahasa konfigurasi deklaratif yang dirancang untuk menjembatani keterbacaan manusia (*human-readability*) dengan kapabilitas komputasi terstruktur tingkat tinggi. Berbeda dari format statis murni seperti JSON atau YAML mentah, HCL2 mengintegrasikan *lexical parser* dan *type system* berbasis HCL Core Engine dan cty library.

HCL2 bukan bahasa imperatif (seperti Python atau Go), melainkan bahasa deklaratif berorientasi ekspresi (*expression-oriented declarative language*). Setiap nilai di dalam blok resource dapat diturunkan dari evaluasi ekspresi matematis, transformasi data kolektif, dan kalkulasi kondisional. HCL2 memungkinkan engineer menulis modul infrastruktur yang tidak hanya dapat digunakan kembali (*reusable*), namun juga memiliki toleransi kesalahan (*fault-tolerant*) dan perlindungan tipe yang ketat (*strictly typed*).

---

## 4. Why
Konfigurasi infrastruktur statis berskala besar menimbulkan masalah skalabilitas:
1. **Redundansi Kode (Code Duplication):** Menggandakan blok deklarasi untuk ratusan subnet atau firewall rules memicu pelanggaran prinsip DRY (*Don't Repeat Yourself*), meningkatkan risiko *human error* dan *configuration drift*.
2. **Index-Shifting Hazards:** Penggunaan `count` naif berbasis array numerik menyebabkan penghancuran dan pembuatan ulang (*destroy-and-recreate*) resource produksi secara massal ketika elemen di tengah array dihapus.
3. **Integritas Input yang Rendah:** Modul yang menerima sembarang tipe data tanpa validasi struktural runtime menyebabkan *failure* di tengah-tengah provisioning AWS/GCP/Azure API yang memakan waktu dan meninggalkan *dangling resources*.
4. **Keterbatasan Nested Blocks:** Banyak provider API (seperti `aws_security_group` dengan `ingress`/`egress`, atau `azurerm_virtual_network` dengan `subnet`) menggunakan skema blok deklaratif bersarang yang tidak dapat diulang menggunakan `for_each` biasa tanpa blok `dynamic`.

HCL2 menyelesaikan masalah-masalah di atas dengan menyediakan ekspresi dinamis yang dievaluasi saat *compile/plan phase*, memungkinkan penulisan infrastruktur yang ringkas, aman, dan adaptif terhadap perubahan skema.

---

## 5. What (Deep-Dive Teknis Lengkap)

### 5.1 Type System HCL2
HCL2 menerapkan klasifikasi tipe data yang rigid:

```
                          Type System HCL2
                                 │
     ┌───────────────────────────┼───────────────────────────┐
     │                           │                           │
 Primitive                  Collection                  Structural
     │                           │                           │
  ├── string                  ├── list(T)                 ├── tuple([T1, T2])
  ├── number                  ├── set(T)                  └── object({k1 = T1, ...})
  └── bool                    └── map(T)
```

- **Primitive Types:**
  - `string`: Rangkaian karakter Unicode (contoh: `"ami-0c55b159cbfafe1f0"`).
  - `number`: Bilangan bulat atau desimal (cty mendukung presisi arbitrer, contoh: `443`, `10.0`).
  - `bool`: Nilai logika boolean (`true` atau `false`).

- **Collection Types (Homogen):**
  - `list(T)`: Urutan nilai bertipe sama dengan indeks berbasis 0 (`[0, 1, 2]`).
  - `set(T)`: Kumpulan nilai unik bertipe sama tanpa indeks terurut. Duplikasi otomatis dieliminasi.
  - `map(T)`: Pasangan *key-value* di mana semua *value* harus memiliki tipe data `T` yang sama, dan *key* bertipe `string`.

- **Structural Types (Heterogen):**
  - `object({ <attribute> = <type>, ... })`: Struktur kompleks dengan nama atribut spesifik dan tipe data yang dapat berbeda antar atribut. Mendukung `optional()` modifier sejak Terraform 1.3.
  - `tuple([<type>, ...])`: Urutan elemen dengan jumlah elemen tetap dan tipe data berbeda di setiap posisi indeks.

- **Dynamic Typing:**
  - `any`: Placeholder tipe yang memerintahkan Terraform menyimpulkan (*infer*) tipe konkret saat evaluasi. `any` bukan tipe data *union* bebas tanpa aturan; setelah tipe di-infer, batasan konsistensi tipe tetap berlaku.

### 5.2 Dynamic Expressions & For Expressions
*For expression* memungkinkan komprehensi dan transformasi data:
- **Transformasi List ke List:**
  ```hcl
  [for s in var.subnets : cidrsubnet(s.cidr, 4, 1) if s.is_public]
  ```
- **Transformasi List/Set ke Map:**
  ```hcl
  { for inst in var.instances : inst.name => inst.private_ip }
  ```
- **Map Grouping (`...` operator):**
  Mengelompokkan nilai dengan key yang sama menjadi sebuah list:
  ```hcl
  { for inst in var.instances : inst.role => inst.id... }
  ```

### 5.3 `for_each` vs `count`
Perbandingan arsitektural internal:
- **`count`**: Menggunakan integer index (`resource.type.name[0]`, `name[1]`). Jika item ke-0 dihapus dari daftar sumber, seluruh resource berikutnya akan mengalami *state address mutation* (indeks bergeser mundur), memicu Terraform merencanakan *destruction* dan *creation* ulang pada resource yang sebenarnya tidak berubah.
- **`for_each`**: Menggunakan string keys (`resource.type.name["subnet-a"]`). Elemen dilacak secara deterministik berdasarkan identifier unik. Penambahan, modifikasi, atau penghapusan satu elemen tidak memengaruhi resource lain dalam kumpulan data tersebut. Hanya menerima tipe `map` atau `set(string)`.

### 5.4 Dynamic Blocks
Blok `dynamic` mereplikasi blok konfigurasi bersarang di dalam resource:
- `for_each`: Koleksi data yang diiterasi.
- `iterator`: (Opsional) Mengubah nama variabel iterator default (default: nama blok dynamic).
- `content`: Blok logika yang memproyeksikan nilai iterator ke dalam argumen target.

### 5.5 Built-in Functions Tingkat Lanjut
- `flatten(list)`: Mengurai struktur list bersarang (*nested lists*) menjadi satu dimensi flat list.
- `merge(map1, map2, ...)`: Menggabungkan beberapa map menjadi satu. Key pada argumen sebelah kanan menimpa argumen di sebelah kiri jika terjadi konflik key.
- `lookup(map, key, default)`: Mengambil nilai dari map dengan fallback ke nilai default jika key tidak ditemukan tanpa memicu fatal error.
- `try(expr1, expr2, ...)`: Mengevaluasi urutan ekspresi dan mengembalikan nilai dari ekspresi pertama yang berhasil tanpa error runtime/akses indeks nil.
- `can(expr)`: Mengembalikan `true` jika ekspresi berhasil dievaluasi tanpa error, dan `false` jika memicu error (sangat berguna di dalam custom validation).

### 5.6 Heredoc Syntax (`<<EOF` vs `<<-EOF`)
- `<<EOF`: Mempertahankan seluruh spasi dan karakter *newline* dari baris deklarasi.
- `<<-EOF`: *Indented Heredoc*, memotong indentasi spasi/tab awal (*leading whitespace*) secara otomatis berdasarkan level indentasi string penutup `EOF`.

### 5.7 Splat Syntax (`.*` vs `[*]`)
- Legacy Splat (`.*`): Terbatas pada tipe list; memicu error jika diterapkan pada non-list atau nilai null.
- Modern Generalized Splat (`[*]`): Mengonversi nilai tunggal, null, atau list secara aman. Jika ekspresi di sebelah kiri adalah `null`, `[*]` mengembalikan list kosong alih-alih melempar error terminasi.

### 5.8 Custom Variable Validation
Menerapkan blok `validation` di dalam definisi `variable` dengan parameter:
- `condition`: Ekspresi boolean yang menentukan validitas input (harus mengembalikan `true` agar valid).
- `error_message`: Pesan error yang diinstruksikan kepada operator jika `condition` bernilai `false`. Harus berupa kalimat lengkap diawali huruf kapital dan diakhiri titik.

---

## 6. How
Prosedur implementasi konfigurasi HCL2 tingkat lanjut:

1. **Definisikan Skema Variabel Terstruktur:** Hindari penggunaan `type = any`. Gunakan kombinasi `object()` dengan atribut `optional()` dan sertakan blok `validation` menggunakan fungsi logika (`can()`, `regex()`, `alltrue()`).
2. **Normalisasi Data di `locals`:** Gunakan ekspresi `for`, `flatten()`, dan `merge()` untuk menyusun koleksi perantara berstruktur key-value deterministik.
3. **Petakan Koleksi ke Resources Menggunakan `for_each`:** Hindari penggunaan `count` jika elemen infrastruktur memiliki siklus hidup independen.
4. **Abstraksikan Nested Blocks Menggunakan `dynamic`:** Iterasikan koleksi data lokal yang telah dinormalisasi ke dalam blok bersarang target.
5. **Amankan Evaluasi Properti Dinamis:** Gunakan `try()` atau operator ternary untuk menangani kasus nilai atribut opsional yang mungkin bernilai null.

---

## 7. Analogy
Bayangkan Anda adalah manajer katering pesta pernikahan:
- **`count` (Nomor Antrean Statis):** Anda membagikan nomor antrean 1 sampai 10 kepada tamu. Jika tamu nomor 3 tiba-tiba pulang sebelum makan, Anda memaksa tamu nomor 4 untuk mengganti bajunya menjadi tamu nomor 3, tamu 5 menjadi nomor 4, dan seterusnya. Ini menimbulkan kekacauan total (*state churn*).
- **`for_each` (Tanda Nama Meja):** Anda menandai meja tamu berdasarkan nama unik ("Budi", "Siti", "Agus"). Jika "Siti" berhalangan hadir, kursinya cukup diangkat. Meja Budi dan Agus sama sekali tidak terganggu.
- **Dynamic Block:** Seperti menu katering custom. Alih-alih mencetak format menu kaku yang harus identik di setiap piring, Anda memiliki mesin pembuat kartu menu fleksibel yang membaca daftar pantangan makanan masing-masing tamu secara dinamis dan hanya mencetak item yang relevan.

---

## 8. Diagram (ASCII)

### Transformasi Data Matrix Menggunakan `flatten` dan For-Expressions

```
[Input Data: Struktur Hierarkis]
Map of VPCs -> List of Subnets per VPC
vpc-prod ──────┬── Subnet-1 (10.0.1.0/24, Zone A)
               └── Subnet-2 (10.0.2.0/24, Zone B)
vpc-stage ─────┬── Subnet-3 (10.1.1.0/24, Zone A)
               └── Subnet-4 (10.1.2.0/24, Zone B)

                         │
                         ▼  [Transformation Pipeline]
        locals {
          flat_subnets = flatten([
            for vpc_key, vpc_data in var.vpcs : [
              for subnet_key, subnet_data in vpc_data.subnets : {
                key         = "${vpc_key}/${subnet_key}"
                vpc_id      = vpc_key
                cidr_block  = subnet_data.cidr
                zone        = subnet_data.zone
              }
            ]
          ])
          subnets_map = { for s in local.flat_subnets : s.key => s }
        }
                         │
                         ▼
[Output Data: 1-Dimensional Map for for_each consumption]
{
  "vpc-prod/Subnet-1"  => { vpc_id = "vpc-prod",  cidr = "10.0.1.0/24", zone = "A" },
  "vpc-prod/Subnet-2"  => { vpc_id = "vpc-prod",  cidr = "10.0.2.0/24", zone = "B" },
  "vpc-stage/Subnet-3" => { vpc_id = "vpc-stage", cidr = "10.1.1.0/24", zone = "A" },
  "vpc-stage/Subnet-4" => { vpc_id = "vpc-stage", cidr = "10.1.2.0/24", zone = "B" }
}
                         │
                         ▼
        resource "aws_subnet" "network" {
          for_each = local.subnets_map
          # Zero state shift risk during deletion of single elements
        }
```

---

## 9. Simple Example
Implementasi manipulasi ekspresi dasar, ternary operator, dan heredoc:

```hcl
variable "environment" {
  type        = string
  default     = "production"
  description = "Target deployment environment."

  validation {
    condition     = contains(["development", "staging", "production"], var.environment)
    error_message = "Variabel environment harus bernilai 'development', 'staging', atau 'production'."
  }
}

variable "base_port" {
  type    = number
  default = 8080
}

locals {
  is_production = var.environment == "production"
  
  # Ternary expression
  allocated_memory = local.is_production ? 16384 : 4096

  # Indented Heredoc (<<-EOF)
  init_script = <<-EOF
    #!/usr/bin/env bash
    echo "Configuring environment: ${upper(var.environment)}"
    echo "Allocated Memory: ${local.allocated_memory}MB"
    listen_port=${var.base_port}
  EOF
}

output "summary" {
  value = {
    env    = var.environment
    memory = local.allocated_memory
    script = local.init_script
  }
}
```

---

## 10. Practical Example (Konfigurasi Produksi HCL2)
Arsitektur AWS Security Group tingkat lanjut dengan Nested Dynamic Blocks, Custom Structural Types, Fallback Functions, dan Splat Operator.

### `variables.tf`
```hcl
variable "security_group_matrix" {
  type = map(object({
    description = string
    vpc_id      = string
    rules = list(object({
      description = string
      port        = number
      protocol    = string
      cidr_blocks = optional(list(string), ["10.0.0.0/8"])
      self_ref    = optional(bool, false)
    }))
  }))
  description = "Matrix spesifikasi security group beserta aturan ingress yang kompleks."

  validation {
    condition = alltrue([
      for sg_key, sg_val in var.security_group_matrix : (
        length(sg_val.rules) > 0 &&
        alltrue([
          for r in sg_val.rules : r.port >= 1 && r.port <= 65535
        ])
      )
    ])
    error_message = "Setiap Security Group harus memiliki minimal satu rule dengan port valid (1-65535)."
  }
}

variable "global_tags" {
  type    = map(string)
  default = {}
}
```

### `main.tf`
```hcl
terraform {
  required_version = ">= 1.5.0"
}

locals {
  default_tags = {
    ManagedBy = "Terraform-Enterprise"
    Engine    = "HCL2-Engine"
  }

  # Merge function
  resolved_tags = merge(local.default_tags, var.global_tags)
}

# Dummy target representation / Native AWS implementation
resource "aws_security_group" "dynamic_matrix" {
  for_each = var.security_group_matrix

  name        = each.key
  description = each.value.description
  vpc_id      = each.value.vpc_id

  # Dynamic Block Implementation
  dynamic "ingress" {
    for_each = each.value.rules
    iterator = rule

    content {
      description = rule.value.description
      from_port   = rule.value.port
      to_port     = rule.value.port
      protocol    = rule.value.protocol
      
      # Fallback expression dengan coalesce & try
      cidr_blocks = rule.value.self_ref ? null : try(rule.value.cidr_blocks, ["10.0.0.0/8"])
      self        = rule.value.self_ref
    }
  }

  tags = merge(
    local.resolved_tags,
    {
      Name = each.key
    }
  )
}
```

### `outputs.tf`
```hcl
output "security_group_arns" {
  # Generalized Splat syntax pada values collection
  value       = values(aws_security_group.dynamic_matrix)[*].arn
  description = "Daftar seluruh ARN Security Group yang terbentuk menggunakan generalized splat."
}

output "flattened_rules_audit" {
  # Flatten nested list comprehension
  value = flatten([
    for sg_key, sg_data in var.security_group_matrix : [
      for rule in sg_data.rules : {
        security_group = sg_key
        port           = rule.port
        protocol       = rule.protocol
        is_internal    = rule.self_ref
      }
    ]
  ])
  description = "Audit log terstruktur hasil flattening seluruh dynamic rules."
}
```

---

## 11. Real World Example
Kasus: Arsitektur Multi-Tier Network Enterprise.
Organisasi membutuhkan generator subnetting otomatis di berbagai availability zone dengan pembagian Public, Private, dan Database subnet tanpa menulis resource berulang kali.

### `main.tf`
```hcl
locals {
  vpc_config = {
    cidr_block = "10.100.0.0/16"
    azs        = ["ap-southeast-1a", "ap-southeast-1b", "ap-southeast-1c"]
    tiers = {
      public = {
        net_offset = 0
        is_public  = true
      }
      application = {
        net_offset = 10
        is_public  = false
      }
      database = {
        net_offset = 20
        is_public  = false
      }
    }
  }

  # Matriks kalkulasi CIDR dan AZ menggunakan nested for expressions
  tier_matrix = flatten([
    for tier_name, tier_info in local.vpc_config.tiers : [
      for idx, az in local.vpc_config.azs : {
        key               = "${tier_name}-${az}"
        tier              = tier_name
        az                = az
        cidr_block        = cidrsubnet(local.vpc_config.cidr_block, 8, tier_info.net_offset + idx)
        map_public_ip     = tier_info.is_public
      }
    ]
  ])

  subnets_map = { for item in local.tier_matrix : item.key => item }
}

resource "aws_vpc" "main" {
  cidr_block           = local.vpc_config.cidr_block
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name = "enterprise-vpc"
  }
}

resource "aws_subnet" "tiers" {
  for_each = local.subnets_map

  vpc_id                  = aws_vpc.main.id
  cidr_block              = each.value.cidr_block
  availability_zone       = each.value.az
  map_public_ip_on_launch = each.value.map_public_ip

  tags = {
    Name = "subnet-${each.key}"
    Tier = each.value.tier
  }
}
```

---

## 12. Trade-offs

| Pendekatan | Keuntungan | Kerugian |
| :--- | :--- | :--- |
| **`for_each` vs `count`** | Identifikasi resource deterministik; aman dari indeks pergeseran (*shift-resilient*). | Memerlukan key string eksplisit; sintaks deklarasi awal sedikit lebih kompleks dibandingkan integer count. |
| **`dynamic` blocks vs Explicit blocks** | Kode sangat bersih (*DRY*); konfigurasi dikendalikan oleh data structures eksternal. | Mengurangi keterbacaan kode (*code readability*) jika level bersarang (*nesting level*) > 2 tingkat; debugging error lebih sulit. |
| **Complex Structural Objects vs Primitive Maps** | Tipe data kuat (*type safety*), autocompletion IDE presisi, validasi skema runtime instan. | Perubahan skema membutuhkan refactoring pada seluruh pemanggil modul (*strict contract*). |
| **Dynamic `try()` / `can()` vs Strict Validation** | Mencegah Terraform berhenti mendadak saat mengakses nilai null atau key hilang. | Menyamarkan bugs konfigurasi nyata yang seharusnya diperbaiki oleh pemanggil (*swallowing critical errors*). |

---

## 13. When To Use
- Gunakan **`for_each`** untuk seluruh resource mandiri yang memiliki identitas persisten (VPC, Subnet, Database instances, IAM Users, DNS records).
- Gunakan **Structural Objects (`object({...})`)** ketika merancang reusable module tingkat enterprise yang dikonsumsi oleh tim lain.
- Gunakan **`dynamic` blocks** ketika provider API mewajibkan parameter berulang di dalam satu deklarasi resource (misalnya rules Security Group, auto-scaling tags, listener rules pada Load Balancer).
- Gunakan **Custom Validations** untuk menghentikan workflow CI/CD sedini mungkin sebelum mengeksekusi API calls ke cloud.

---

## 14. When NOT To Use
- Jangan gunakan **`for_each`** ketika jumlah instance murni anonim dan identik tanpa dependensi siklus hidup (misalnya membuat 10 worker node transient sementara dalam testing, di mana `count` lebih sederhana).
- Hindari **`dynamic` blocks** jika konfigurasi bersarang hanya memiliki 1 atau 2 atribut statis yang pasti tidak berubah. Penulisan eksplisit lebih mudah dibaca tim non-developer.
- Jangan menyalahgunakan fungsi **`try()`** untuk menyembunyikan kesalahan logika penulisan konfigurasi (contoh: menyembunyikan referensi resource yang typo).

---

## 15. Common Mistakes
1. **Index-Shifting recreation bug:**
   ```hcl
   # SALAH: Menggunakan count pada list resource penting
   variable "subnets" { default = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"] }
   resource "aws_subnet" "nodes" {
     count      = length(var.subnets)
     cidr_block = var.subnets[count.index]
   }
   # Jika subnets[0] dihapus, Terraform menghancurkan subnet[1] dan subnet[2]!
   ```
2. **Dynamic block name mismatch:** Menggunakan nama blok `dynamic` yang salah atau iterator yang tidak merujuk pada nama resource target.
3. **Menggunakan `.*` (Legacy Splat) pada Objek Nullable:**
   ```hcl
   # SALAH (Crash jika var.load_balancers null):
   output "dns" { value = var.load_balancers.*.dns_name }

   # BENAR:
   output "dns" { value = var.load_balancers[*].dns_name }
   ```
4. **Pola Regex Validation Tanpa `can()`:**
   Menulis `condition = regex("^ami-", var.ami_id)` akan melempar fatal parsing error jika regex gagal cocok. Seharusnya gunakan `condition = can(regex("^ami-", var.ami_id))`.

---

## 16. Best Practices
1. **Gunakan Deterministic Keys pada Maps:** Saat mentransformasikan list menjadi map untuk `for_each`, buat string kunci unik berbasis atribut fungsional (misal: `"${region}-${name}"`).
2. **Minimalkan Nesting Level Dynamic Blocks:** Batasi kompleksitas dynamic blocks maksimal 2 tingkat. Jika butuh lebih dari 2 tingkat bersarang, sederhanakan desain modul arsitektur Anda.
3. **Kombinasikan `optional()` dengan Default Values:** Sejak Terraform 1.3+, gunakan `optional(string, "default_val")` pada definisi object untuk menghindari ekspresi `coalesce` atau `lookup` yang bertele-tele.
4. **Validasi Semantik Variabel:** Terapkan custom validation untuk format CIDR, batasan rentang port, dan penamaan resource konvensional (*naming convention*).

---

## 17. Troubleshooting
- **Error: `Invalid dynamic for_each value`:**
  - *Penyebab:* Nilai yang dioper ke `dynamic.for_each` bukan bertipe `list`, `set`, atau `map`, melainkan primitive atau objek `null`.
  - *Solusi:* Bungkus dengan `try(local.items, [])` atau pastikan input bertipe koleksi eksplisit.
- **Error: `The given key does not identify an element in this collection value`:**
  - *Penyebab:* Penggunaan akses map langsung `var.map[key]` ketika key tidak dijamin ada.
  - *Solusi:* Ganti dengan fungsi `lookup(var.map, key, fallback_value)`.
- **Error: `Error in function call: can() only works with expressions`:**
  - *Penyebab:* Meletakkan operasi non-ekspresi atau pernyataan imperatif di dalam `can()`. Pastikan hanya argumen evaluasi nilai yang disematkan.

---

## 18. Exercise
1. Buatlah variabel bertipe `list(string)` berisi 5 nama server: `["app-01", "db-01", "app-02", "cache-01", "db-02"]`.
2. Gunakan `for` expression tunggal dengan klausul `if` untuk menghasilkan list baru yang hanya berisi server yang mengandung kata `"db"`.
3. Tuliskan blok ekspresi `for` lain yang menghasilkan map, di mana `key` adalah nama server dan `value` adalah panjang karakter nama server tersebut.

---

## 19. Challenge
Rancang sebuah modul Terraform HCL2 murni (tanpa resource cloud eksternal, gunakan resource `terraform_data` atau `null_resource`) yang mampu menerima konfigurasi:
```hcl
variable "firewall_zones" { ... }
```
Struktur data variabel ini adalah map heterogen bertingkat yang menampung multiple Zone jaringan (misal: "DMZ", "Core", "Internal"). Setiap Zone memiliki daftar Rules protokol (`TCP`, `UDP`, `ICMP`), rentang port dinamis, dan daftar IP target. Modul Anda harus:
1. Memvalidasi bahwa setiap nama Zone harus huruf kapital murni (`DMZ`, `CORE`).
2. Menggunakan `flatten` dan manipulasi logika untuk membongkar seluruh nested data tersebut ke dalam satu map datar yang aman dikonsumsi oleh `terraform_data.rule_nodes` menggunakan `for_each`.
3. Menghasilkan audit summary output dalam format valid JSON string menggunakan indented heredoc `<<-EOF`.

---

## 20. Summary
- **HCL2 Type System** menyediakan keamanan tipe ketat melalui primitive, homogen collection, dan heterogen structural types.
- **`for_each`** adalah standar baku industri untuk provisioning sumber daya mandiri karena mencegah anomali penghancuran resource akibat *index-shifting* pada `count`.
- **Dynamic Blocks** membuka jalan bagi abstraksi konfigurasi deklaratif tingkat tinggi, mengonversi struktur data kompleks menjadi nested schema provider.
- Kombinasi fungsi-fungsi manipulasi data seperti **`flatten`**, **`merge`**, **`lookup`**, dan **`can`** dengan **Custom Validations** memastikan modul Terraform resilient, self-documenting, dan production-ready.

---