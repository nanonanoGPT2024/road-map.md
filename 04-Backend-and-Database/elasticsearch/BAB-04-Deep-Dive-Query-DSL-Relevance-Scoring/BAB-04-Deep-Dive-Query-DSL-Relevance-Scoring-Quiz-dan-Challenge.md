# BAB-04-Deep-Dive-Query-DSL-Relevance-Scoring: Quiz, Challenge, & Knowledge Check

Dokumen ini dirancang sebagai instrumen evaluasi teknis, pengujian pemahaman mendalam, dan asesmen kesiapan produksi untuk topik **Elasticsearch Query DSL & Relevance Scoring (BM25)**. 

---

## Petunjuk Pengerjaan

1. Kerjakan **Bagian 1 (Basic Questions)** dan **Bagian 2 (Intermediate Questions)** secara mandiri sebelum meninjau kunci jawaban dan pembahasan teknis.
2. Analisis **Bagian 3 (Skenario Kasus Nyata Produksi)** dengan membedah trade-off arsitektur, kalkulasi relevansi skor, dan performa query.
3. Eksekusi **Bagian 4 (Practical Chapter Challenge)** langsung pada cluster Elasticsearch (v7.x / v8.x) lokal atau staging Anda menggunakan tool REST (Kibana Console, `curl`, atau HTTP Client).
4. Gunakan **Bagian 5 (Checklist Pemahaman)** sebagai validasi akhir kesiapan Anda sebelum melangkah ke bab agregasi dan analitik lanjutan.

---

## Bagian 1: 5 Basic Questions

### Pertanyaan 1 (Query Context vs Filter Context)
Di dalam Query DSL Elasticsearch, apa perbedaan mendasar antara mengeksekusi klausa di dalam konteks **Query** (`query context`) dibandingkan dengan konteks **Filter** (`filter context`) terhadap kalkulasi skor `_score` dan pemanfaatan cache?

<details>
<summary><b>Kunci Jawaban & Pembahasan Teknis</b></summary>

**Kunci Jawaban:**
- **Query Context:** Menjawab pertanyaan *"Seberapa relevan dokumen ini terhadap query?"*. Elasticsearch menghitung bobot relevansi `_score` (menggunakan algoritma BM25 atau kustom scoring), tidak menggunakan node query cache bawaan (kecuali untuk beberapa optimasi tertentu), dan membutuhkan CPU cycle lebih tinggi untuk kalkulasi matematika per dokumen.
- **Filter Context:** Menjawab pertanyaan biner *"Apakah dokumen ini memenuhi syarat kriteria?"* (Ya/Tidak). Nilai `_score` tidak dihitung (bernilai `0.0` atau diabaikan), hasilnya otomatis di-cache dalam memori dalam bentuk bitsets (Roaring Bitmaps) melalui Node Query Cache jika query dieksekusi berulang kali, sehingga menghasilkan latensi eksekusi yang jauh lebih rendah.

**Best Practice:** Setiap kondisi pencarian eksak (status enum, range harga/tanggal, tenant ID, boolean flags) wajib diletakkan di dalam klausa `filter` atau `must_not` dari query `bool`, bukan di `must`.
</details>

---

### Pertanyaan 2 (Term Query vs Match Query pada Field Text)
Diberikan field `title` dengan mapping `"type": "text"` menggunakan `standard` analyzer. Dokumen berisi nilai `"Clean Architecture in Python"`. Mengapa eksekusi query berikut **tidak menghasilkan hit sama sekali**?

```json
{
  "query": {
    "term": {
      "title": "Clean Architecture"
    }
  }
}
```

<details>
<summary><b>Kunci Jawaban & Pembahasan Teknis</b></summary>

**Kunci Jawaban:**
1. **Analisis Inverted Index:** `standard` analyzer saat proses indexing memecah teks `"Clean Architecture in Python"` menjadi token huruf kecil (lowercase) individual: `["clean", "architecture", "in", "python"]`.
2. **Karakteristik Term Query:** `term` query adalah *term-level query* yang bersifat murni eksak dan **tidak melewati analyzer** pada teks query input. Query mencari token eksak `"Clean Architecture"` (dengan huruf kapital dan spasi) langsung ke inverted index.
3. Karena token `"Clean Architecture"` tidak pernah ada di dalam inverted index (yang ada adalah token terpisah `"clean"` dan `"architecture"`), query menghasilkan zero hits.
4. **Solusi:** Gunakan `match` query (`"match": { "title": "Clean Architecture" }`) agar query string dianalisis oleh analyzer yang sama menjadi token `["clean", "architecture"]`, atau gunakan `match_phrase` jika urutan token harus berdekatan, atau gunakan sub-field keyword `title.keyword` jika field dipetakan multi-field.
</details>

---

### Pertanyaan 3 (BM25: Parameter k1 dan b)
Pada formula ranking relevansi Okapi BM25 default Elasticsearch, jelaskan fungsi teknis dari parameter `k1` (default `1.2`) dan `b` (default `0.75`).

<details>
<summary><b>Kunci Jawaban & Pembahasan Teknis</b></summary>

**Kunci Jawaban:**
1. **Parameter `k1` (Term Frequency Saturation Control):**
   - Mengatur seberapa cepat skor relevansi jenuh (saturate) saat frekuensi kemunculan sebuah kata (TF) bertambah dalam satu dokumen.
   - Nilai default adalah `1.2`. Jika `k1 = 0`, term frequency sepenuhnya diabaikan (hanya ada/tidaknya term yang dinilai). Nilai `k1` yang lebih tinggi memperlambat kurva saturasi, memberikan bobot lebih besar bagi dokumen yang mengulang term query berkali-kali.
2. **Parameter `b` (Document Length Normalization):**
   - Mengontrol penalti terhadap panjang dokumen relatif terhadap rata-rata panjang dokumen di seluruh indeks (*average document length*).
   - Nilai berada pada rentang `0.0` sampai `1.0` (default `0.75`).
   - `b = 1.0` memberikan normalisasi penuh (dokumen yang sangat panjang dengan jumlah kata banyak akan terkena penalti berat jika term hanya muncul sedikit).
   - `b = 0.0` mematikan normalisasi panjang dokumen secara total (panjang teks dokumen tidak mempengaruhi skor).
</details>

---

### Pertanyaan 4 (Perilaku Klausa should pada Boolean Query)
Kapan klausa `should` di dalam query `bool` bersifat wajib lolos (*mandatory match*), dan kapan bersifat opsional hanya sebagai penambah skor relevansi?

<details>
<summary><b>Kunci Jawaban & Pembahasan Teknis</b></summary>

**Kunci Jawaban:**
- **Bersifat Opsional:** Jika query `bool` memiliki setidaknya satu klausa `must` atau klausa `filter`, klausa `should` secara default bersifat opsional (`minimum_should_match = 0`). Dokumen tidak harus mencocokkan `should` untuk masuk ke search hit, tetapi dokumen yang cocok dengan `should` akan mendapat penambahan nilai `_score`.
- **Bersifat Wajib:** Jika di dalam query `bool` **tidak ada** klausa `must` dan **tidak ada** klausa `filter`, maka secara default `minimum_should_match = 1`. Artinya, minimal salah satu klausa `should` wajib bernilai cocok agar dokumen lolos seleksi.
- **Catatan:** Anda dapat meng-override perilaku ini secara eksplisit dengan mendefinisikan parameter `"minimum_should_match": 1` (atau persentase / formula khusus) di level root query `bool`.
</details>

---

### Pertanyaan 5 (Match Phrase dan Parameter Slop)
Apa fungsi parameter `slop` pada `match_phrase` query? Jika query mencari `"docker kubernetes"` dengan `"slop": 2`, jelaskan apakah dokumen dengan isi `"docker compose and kubernetes"` akan cocok.

<details>
<summary><b>Kunci Jawaban & Pembahasan Teknis</b></summary>

**Kunci Jawaban:**
- **Fungsi `slop`:** Menentukan berapa kali token kata diperbolehkan berpindah posisi (transposisi / movement steps) agar cocok dengan urutan frasa yang dicari. Default `slop` adalah `0` (posisi token harus berdampingan persis tanpa kata perantara).
- **Kasus Dokumen:** `"docker compose and kubernetes"`
  - Posisi token di dokumen: `docker` (posisi 1), `compose` (posisi 2), `and` (posisi 3), `kubernetes` (posisi 4).
  - Jarak token `kubernetes` terhadap `docker` adalah `4 - 1 = 3`.
  - Pada pencarian frasa berdampingan standar (`slop: 0`), posisi `kubernetes` harus di posisi 2 (`jarak = 1`).
  - Untuk berpindah dari posisi 2 ke posisi 4 dibutuhkan 2 step perpindahan (`slop = 2`).
  - **Kesimpulan:** Dokumen tersebut **cocok (match)** karena perbedaan posisi token kata tepat berada dalam batas toleransi `slop: 2`.
</details>

---

## Bagian 2: 5 Intermediate Questions

### Pertanyaan 6 (Multi Match Types: best_fields vs cross_fields)
Pada skenario pencarian profil user dengan field `first_name` dan `last_name`, pengguna memasukkan query `"John Doe"`. Bandingkan perilaku eksekusi type `"best_fields"` versus `"cross_fields"`. Mana yang tepat untuk kasus ini dan mengapa?

<details>
<summary><b>Kunci Jawaban & Pembahasan Teknis</b></summary>

**Kunci Jawaban:**
1. **Tipe `best_fields` (Default Multi-match):**
   - Mencari kecocokan per field secara independen (menjalankan query `dis_max` di balik layar).
   - Skor akhir diambil dari field tunggal dengan skor tertinggi (skor `best field`).
   - Masalah: Jika token `"John"` ada di field `first_name` dan `"Doe"` ada di field `last_name`, tidak ada satu pun field tunggal yang memiliki kedua token tersebut secara bersamaan. Akibatnya dokumen ini kalah relevan dibanding dokumen yang memiliki kata `"John"` berulang kali hanya di field `first_name`.
2. **Tipe `cross_fields`:**
   - Memperlakukan beberapa field seolah-olah digabung menjadi satu field besar yang homogen (*entity search approach*).
   - Menganalisis term query `"John"` dan `"Doe"` lalu mencari kemunculannya di seluruh field yang didaftarkan. Token `"John"` boleh ditemukan di `first_name` dan `"Doe"` ditemukan di `last_name`.
   - Menggunakan kalkulasi IDF (Inverse Document Frequency) terpadu antar field sehingga term langka tidak membiaskan skor secara timpang antar field.
3. **Kesimpulan:** Untuk entitas nama orang atau alamat multi-field, type `"cross_fields"` adalah pilihan arsitektur yang benar.
</details>

---

### Pertanyaan 7 (Function Score vs Script Score)
Kapan tim engineer harus memilih `script_score` (menggunakan script Painless) daripada `function_score` bawaan (seperti `field_value_factor`, `gauss`, `random_score`)? Jelaskan implikasi performa masing-masing!

<details>
<summary><b>Kunci Jawaban & Pembahasan Teknis</b></summary>

**Kunci Jawaban:**
- **Function Score:**
  - Cocok untuk transformasi matematis standar yang sudah dioptimalkan di native C++/Java Lucene (misalnya decay function linier/gauss untuk koordinat GPS atau tanggal, penggandaan logaritmik view count).
  - Namun, `function_score` sudah berstatus maintenance/legacy di Elasticsearch versi terbaru dan memiliki overhead pipeline yang kaku jika logic skor melibatkan percabangan kondisi (if-else).
- **Script Score:**
  - Diperkenalkan sebagai pengganti modern yang lebih fleksibel, dieksekusi via `painless` script.
  - Sangat ideal ketika logika scoring membutuhkan kombinasi matematis kompleks: conditional branching (`if (doc['is_promoted'].value) ...`), integrasi dot-product vector search (`dense_vector`), atau manipulasi nilai dinamis berdasarkan payload context pengguna saat runtime.
- **Implikasi Performa:**
  - Script Painless di-compile secara just-in-time (JIT) dan di-cache dalam internal script cache.
  - Namun, mengakses field melalui `doc['field_name'].value` membaca data dari Doc Values (kolumnar di disk/OS page cache). Jika query match jutaan dokumen sebelum script dijalankan, `script_score` akan sangat membebani CPU. Solusi: Gunakan query filter ketat terlebih dahulu atau gunakan feature `rescore` window agar `script_score` hanya mengevaluasi Top-N (misal Top 100) dokumen teratas.
</details>

---

### Pertanyaan 8 (Anatomi Explain API untuk Bedah Skor BM25)
Diberikan output parsial dari `GET /articles/_explain/42` berikut:

```json
{
  "_explanation": {
    "value": 2.845123,
    "description": "weight(title:elasticsearch in 0) [PerFieldSimilarity], result of:",
    "details": [
      {
        "value": 2.845123,
        "description": "score(freq=2.0), computed as boost * idf * tf from:",
        "details": [
          { "value": 2.2, "description": "boost" },
          { "value": 1.45892, "description": "idf, computed as log(1 + (N - n + 0.5) / (n + 0.5)) from:" },
          { "value": 0.88641, "description": "tf, computed as freq / (freq + k1 * (1 - b + b * dl / avgdl)) from:" }
        ]
      }
    ]
  }
}
```

Jelaskan apa yang terjadi pada komponen:
1. `idf` (Inverse Document Frequency)
2. `tf` (Term Frequency termodifikasi BM25)
3. Mengapa terdapat faktor `boost: 2.2`?

<details>
<summary><b>Kunci Jawaban & Pembahasan Teknis</b></summary>

**Kunci Jawaban:**
1. **Komponen `idf`:** Mengukur tingkat kelangkaan term `"elasticsearch"` di seluruh koleksi dokumen shard tersebut. Dihitung dengan rumus $log(1 + \frac{N - n + 0.5}{n + 0.5})$ di mana $N$ adalah total dokumen di shard dan $n$ adalah jumlah dokumen yang mengandung term tersebut. Semakin langka term, nilai `idf` semakin tinggi.
2. **Komponen `tf`:** Mengukur kontribusi frekuensi kemunculan term dalam dokumen target (`freq = 2.0`). Pada BM25, frekuensi ini dinormalisasi dengan panjang dokumen target ($dl$) terhadap rata-rata panjang dokumen ($avgdl$) serta faktor saturasi $k1$ dan $b$. Output `0.88641` adalah rasio akhir saturasi TF setelah normalisasi panjang field dokumen.
3. **Faktor `boost: 2.2`:** Dokumen ini dikenai boosting eksplisit sebesar `2.2` pada query time (misalnya `"title^2.2"`) atau mapping time. Nilai akhir `_score` ($2.845123$) merupakan perkalian dari: $2.2 \times 1.45892 \times 0.88641 \approx 2.8451$.
</details>

---

### Pertanyaan 9 (Tuning Skor dengan Negative Boosting)
Jelaskan perbedaan mendasar antara mengecualikan dokumen menggunakan klausa `must_not` dengan mendegradasi peringkat dokumen menggunakan `boosting` query (dengan parameter `negative` dan `negative_boost`). Kapan Anda wajib menggunakan `boosting` query?

<details>
<summary><b>Kunci Jawaban & Pembahasan Teknis</b></summary>

**Kunci Jawaban:**
- **Klausa `must_not`:** Bersifat hard-exclusion (biner). Dokumen yang memenuhi kondisi `must_not` langsung dibuang dari hasil pencarian (skor menjadi null dan dokumen tidak muncul di array `hits.hits`).
- **`boosting` Query (`positive` vs `negative`):**
  - Dokumen yang memenuhi klausa `positive` tetap dipertahankan di hasil pencarian.
  - Jika dokumen tersebut juga memenuhi kriteria klausa `negative`, dokumen tersebut **tidak dibuang**, melainkan skor akhirnya dikalikan dengan faktor desimal `negative_boost` (misal `0.2`).
- **Use Case Produksi:**
  - Pada sistem pencarian pekerjaan (Job Board), user mencari `"Software Engineer"`. Pekerjaan yang menawarkan status "Magang" atau "Internship" sebaiknya tidak dibuang sepenuhnya (karena mungkin relevan jika kuota lowongan full-time sedikit), tetapi diturunkan posisinya ke halaman belakang.
  - Pada E-Commerce, produk yang berstatus *out-of-stock* (habis) tetap harus dapat dicari tetapi diletakkan di urutan paling bawah katalog dengan mengalikan skor menggunakan `negative_boost: 0.1`.
</details>

---

### Pertanyaan 10 (Nested vs Parent-Child Scoring Pitfalls)
Ketika melakukan query terhadap relasi bertingkat, bagaimana kalkulasi skor relevansi diwariskan ke dokumen induk pada:
1. `nested` query dengan parameter `score_mode`
2. `has_child` query dengan parameter `score_mode`
Apa konsekuensi arsitektural pemilihan `score_mode: "none"`?

<details>
<summary><b>Kunci Jawaban & Pembahasan Teknis</b></summary>

**Kunci Jawaban:**
1. **`nested` Query:** Objek nested tersimpan di segmen Lucene yang sama persis sebagai hidden document yang berdampingan dengan parent doc. Saat melakukan query nested, parameter `score_mode` menentukan bagaimana skor anak-anak nested diagregasi ke parent document:
   - `avg` (rata-rata skor seluruh nested doc yang cocok).
   - `max` (skor tertinggi dari anak yang cocok - default).
   - `sum` (penjumlahan skor semua anak yang cocok).
   - `min` (skor terendah).
2. **`has_child` Query:** Child document disimpan di dokumen independen (bisa beda segmen Lucene, namun dipaksa berada di shard yang sama via routing ID). Parameter `score_mode` memiliki opsi serupa (`avg`, `sum`, `max`, `min`, `none`). Proses agregasi skor melibatkan join lookup via Global Ordinals yang membutuhkan memory map internal.
3. **Konsekuensi `score_mode: "none"`:**
   - Elasticsearch mengabaikan seluruh kalkulasi relevansi skor anak (menghilangkan overhead perhitungan BM25 di level child).
   - Parent document hanya dinilai berdasarkan kecocokan biner (lolos/tidak lolos). Ini menghemat penggunaan CPU secara signifikan dan memungkinkan filter caching bekerja optimal pada segmen child.
</details>

---

## Bagian 3: 3 Skenario Kasus Nyata Produksi

---

### Skenario 1: Krisis Relevansi Pencarian E-Commerce Akibat Keyword Stuffing
**Konteks Masalah:**
Sebuah platform marketplace elektronik mengalami keluhan pengguna di mana pencarian kata `"Laptop ASUS Zenbook"` justru menampilkan kabel charger pihak ketiga dan stiker laptop di halaman 1, sementara laptop ASUS Zenbook seharga Rp 20 juta terlempar ke halaman 2.

**Audit Mapping & Query Saat Ini:**
Field `title`, `description`, dan `tags` seluruhnya bertipe `text` dengan standard analyzer.
Query yang digunakan di backend adalah:
```json
{
  "query": {
    "multi_match": {
      "query": "Laptop ASUS Zenbook",
      "fields": ["title", "description", "tags"]
    }
  }
}
```

**Akar Masalah:**
1. Penjual kabel charger melakukan keyword stuffing di field `description` dengan menuliskan kata `"ASUS Zenbook Laptop"` puluhan kali.
2. Karena default `multi_match` menggunakan `best_fields`, field `description` pada produk charger mendapatkan skor BM25 sangat tinggi akibat tingginya Term Frequency (`freq`).
3. Deskripsi produk charger sangat pendek tetapi berulang, memicu nilai normalisasi panjang dokumen yang tinggi.

**Solusi Arsitektur & Rekomendasi Query DSL:**
1. Ubah strategi `multi_match` dari `best_fields` menjadi `cross_fields` atau gunakan `most_fields` dengan field boosting terkontrol.
2. Berikan bobot utama pada field `title` menggunakan caret boost (`title^4`), bobot sedang pada `tags^2`, dan bobot rendah pada `description^0.5`.
3. Tambahkan klausa `tie_breaker` (misal `0.3`) agar field lain tetap berkontribusi tanpa mendominasi.
4. Implementasikan `rescore` window dengan `match_phrase` untuk memberikan bonus ranking masif pada produk yang kata `"Laptop ASUS Zenbook"` muncul berurutan di judul.

**Implementasi Solusi Query DSL Produksi:**
```json
POST /products/_search
{
  "query": {
    "bool": {
      "must": [
        {
          "multi_match": {
            "query": "Laptop ASUS Zenbook",
            "type": "cross_fields",
            "fields": [
              "title^5",
              "tags^2",
              "description^0.5"
            ],
            "operator": "and"
          }
        }
      ],
      "filter": [
        { "term": { "status": "active" } },
        { "term": { "category_id": "laptops-and-computers" } }
      ]
    }
  },
  "rescore": {
    "window_size": 50,
    "query": {
      "rescore_query": {
        "match_phrase": {
          "title": {
            "query": "Laptop ASUS Zenbook",
            "slop": 1
          }
        }
      },
      "query_weight": 1.0,
      "rescore_query_weight": 3.0
    }
  }
}
```

---

### Skenario 2: Geo-Temporal Ranking pada Aplikasi Food Delivery
**Konteks Masalah:**
Aplikasi pesan antar makanan ingin menampilkan restoran berdasarkan pencarian teks pengguna (misal `"Kopi Susu Gula Aren"`), namun hasil pencarian harus:
1. Menghukum restoran yang jaraknya lebih dari 5 km (jarak ideal < 2 km).
2. Memprioritaskan restoran yang memiliki rating ulasan bintang tinggi (`average_rating` 1.0 - 5.0).
3. Hanya restoran berstatus `is_open: true` yang boleh muncul.
4. Latensi p99 pencarian harus di bawah 40 ms pada 500 QPS.

**Solusi Arsitektur Menggunakan Function Score Query:**
- Gunakan `bool` query dengan pemisahan tegas antara filter biner (`is_open`) dan scoring relevansi teks.
- Gunakan `function_score` dengan `gauss` decay untuk parameter geo-distance (titik asal lokasi user).
- Gunakan `field_value_factor` dengan kurva modifier `log1p` untuk skor rating agar tidak menelan skor teks murni.
- Atur parameter `boost_mode: "multiply"` atau `"sum"` serta batasi evaluasi skor dengan filter awal yang ketat.

**Implementasi Query DSL Produksi:**
```json
POST /merchants/_search
{
  "query": {
    "function_score": {
      "query": {
        "bool": {
          "must": [
            {
              "multi_match": {
                "query": "Kopi Susu Gula Aren",
                "fields": ["name^3", "menu_items.name^2", "cuisine_tags"]
              }
            }
          ],
          "filter": [
            { "term": { "is_open": true } },
            {
              "geo_distance": {
                "distance": "10km",
                "location": {
                  "lat": -6.2088,
                  "lon": 106.8456
                }
              }
            }
          ]
        }
      },
      "functions": [
        {
          "gauss": {
            "location": {
              "origin": { "lat": -6.2088, "lon": 106.8456 },
              "scale": "2km",
              "offset": "0.5km",
              "decay": 0.5
            }
          },
          "weight": 2.0
        },
        {
          "field_value_factor": {
            "field": "average_rating",
            "factor": 1.2,
            "modifier": "log1p",
            "missing": 3.0
          },
          "weight": 1.5
        }
      ],
      "score_mode": "sum",
      "boost_mode": "multiply"
    }
  },
  "size": 20
}
```

---

### Skenario 3: Diagnosis Lonjakan Latensi Query & Slow Log pada Multi-Tenant SaaS
**Konteks Masalah:**
Sebuah platform HR SaaS multi-tenant dengan 50 juta dokumen log karyawan mengalami penurunan performa drastis. Slow log mencatat query pencarian karyawan memakan waktu hingga 3.200 ms.

**Temuan Query dari Audit Backend:**
```json
{
  "query": {
    "bool": {
      "must": [
        { "term": { "tenant_id": "tenant-corp-9941" } },
        { "term": { "is_active": true } },
        { "range": { "joined_date": { "gte": "2023-01-01" } } },
        { "wildcard": { "full_name": "*budi*" } }
      ]
    }
  }
}
```

**Analisis Akar Masalah:**
1. **Scoring Overhead pada Data Eksak:** Kondisi `tenant_id`, `is_active`, dan `joined_date` ditaruh di dalam klausa `must`. Elasticsearch menghitung skor BM25 untuk tenant ID dan boolean flag, yang sama sekali tidak memiliki arti relevansi teks.
2. **Hilangnya Cache Bitset:** Karena berada di `must`, hasil pencocokan `tenant_id` tidak pernah masuk ke Node Query Cache.
3. **Leading Wildcard Query (`*budi*`):** Wildcard dengan bintang di depan memaksa Lucene melakukan linear scan pada seluruh term dictionary di shard memory, mematikan seluruh keunggulan struktur Inverted Index.

**Tindakan Remidiasi Produksi:**
1. Pindahkan `tenant_id`, `is_active`, dan `joined_date` ke dalam klausa `filter`. Ini langsung mengaktifkan caching bitset dan meniadakan scoring CPU overhead.
2. Atur routing dokumen menggunakan `tenant_id` (`_routing = tenant-corp-9941`) saat indexing sehingga query hanya diarahkan ke 1 shard spesifik, bukan di-broadcast ke seluruh node cluster.
3. Ganti leading wildcard dengan field mapping khusus: gunakan `wildcard` field type (tersedia di ES 7.9+) atau gunakan analyzer `edge_ngram` / `ngram` pada field `full_name` agar pencarian parsial berjalan pada kompleksitas inverted index $O(1)$.

**Implementasi Remidiasi Query:**
```json
POST /employees/_search?routing=tenant-corp-9941
{
  "query": {
    "bool": {
      "must": [
        {
          "match": {
            "full_name.ngram": {
              "query": "budi",
              "operator": "and"
            }
          }
        }
      ],
      "filter": [
        { "term": { "tenant_id": "tenant-corp-9941" } },
        { "term": { "is_active": true } },
        { "range": { "joined_date": { "gte": "2023-01-01" } } }
      ]
    }
  }
}
```

---

## Bagian 4: 1 Practical Chapter Challenge

### Tantangan Hands-on: Merancang Custom Search Recommender Query

**Tujuan:**
Bangun indeks katalog buku teknis berskala enterprise bernama `books_catalog`, masukkan dataset sampel, dan buat query pencarian komprehensif yang memadukan:
1. `bool` query dengan pemisahan konteks `must`, `should`, dan `filter`.
2. Multi-match dengan tipe `cross_fields` dan field boosting.
3. Parameter `tie_breaker`.
4. Script score / Function score untuk memperhitungkan bobot popularitas buku (`sales_count`) dan diskon.
5. Window `rescore` menggunakan `match_phrase` dengan `slop`.

---

### Langkah 1: Pembuatan Index Mapping
Eksekusi di Kibana Console atau terminal:

```json
PUT /books_catalog
{
  "settings": {
    "number_of_shards": 1,
    "number_of_replicas": 0,
    "analysis": {
      "analyzer": {
        "autocomplete_analyzer": {
          "tokenizer": "autocomplete_tokenizer",
          "filter": ["lowercase"]
        }
      },
      "tokenizer": {
        "autocomplete_tokenizer": {
          "type": "edge_ngram",
          "min_gram": 2,
          "max_gram": 15,
          "token_chars": ["letter", "digit"]
        }
      }
    }
  },
  "mappings": {
    "properties": {
      "title": {
        "type": "text",
        "fields": {
          "suggest": {
            "type": "text",
            "analyzer": "autocomplete_analyzer"
          },
          "keyword": {
            "type": "keyword"
          }
        }
      },
      "summary": { "type": "text" },
      "author": {
        "type": "text",
        "fields": { "keyword": { "type": "keyword" } }
      },
      "category": { "type": "keyword" },
      "in_stock": { "type": "boolean" },
      "price": { "type": "scaled_float", "scaling_factor": 100 },
      "sales_count": { "type": "integer" },
      "rating": { "type": "half_float" },
      "published_date": { "type": "date" }
    }
  }
}
```

---

### Langkah 2: Ingest Sample Documents
```json
POST /books_catalog/_bulk
{ "index": { "_id": "1" } }
{ "title": "Designing Data-Intensive Applications", "summary": "The definitive guide to distributed data systems, reliability, and scalability by Martin Kleppmann.", "author": "Martin Kleppmann", "category": "Distributed Systems", "in_stock": true, "price": 45.00, "sales_count": 12500, "rating": 4.9, "published_date": "2017-03-16" }
{ "index": { "_id": "2" } }
{ "title": "Distributed Systems Architecture and Practice", "summary": "Comprehensive patterns for microservices and data pipelines.", "author": "Brendan Burns", "category": "Distributed Systems", "in_stock": true, "price": 38.50, "sales_count": 3400, "rating": 4.5, "published_date": "2021-06-10" }
{ "index": { "_id": "3" } }
{ "title": "Building Distributed Systems with Go", "summary": "Hands-on guide to building network services and consensus in Go.", "author": "Travis Jeffery", "category": "Distributed Systems", "in_stock": false, "price": 32.00, "sales_count": 890, "rating": 4.2, "published_date": "2021-03-01" }
{ "index": { "_id": "4" } }
{ "title": "Python Data Science Handbook", "summary": "Essential tools for working with data in Python.", "author": "Jake VanderPlas", "category": "Data Science", "in_stock": true, "price": 42.00, "sales_count": 7800, "rating": 4.7, "published_date": "2016-11-21" }
{ "index": { "_id": "5" } }
{ "title": "Database Internals: A Deep Dive into How Distributed Systems Store Data", "summary": "Storage engines, B-Trees, LSM-Trees, and consensus mechanisms.", "author": "Alex Petrov", "category": "Databases", "in_stock": true, "price": 50.00, "sales_count": 4200, "rating": 4.8, "published_date": "2019-10-15" }
```

---

### Langkah 3: Final Challenge Query Payload
Tulis dan jalankan query berikut untuk mencari `"distributed data systems"`:

```json
POST /books_catalog/_search
{
  "query": {
    "function_score": {
      "query": {
        "bool": {
          "must": [
            {
              "multi_match": {
                "query": "distributed data systems",
                "type": "cross_fields",
                "fields": [
                  "title^4",
                  "summary^1.5",
                  "author"
                ],
                "tie_breaker": 0.3,
                "operator": "or"
              }
            }
          ],
          "filter": [
            { "term": { "in_stock": true } },
            { "range": { "price": { "lte": 50.0 } } }
          ],
          "should": [
            {
              "term": {
                "category": {
                  "value": "Distributed Systems",
                  "boost": 2.0
                }
              }
            }
          ]
        }
      },
      "functions": [
        {
          "field_value_factor": {
            "field": "sales_count",
            "factor": 0.0001,
            "modifier": "log1p",
            "missing": 1
          },
          "weight": 1.2
        },
        {
          "field_value_factor": {
            "field": "rating",
            "factor": 1.0,
            "modifier": "none",
            "missing": 3.0
          },
          "weight": 0.8
        }
      ],
      "score_mode": "sum",
      "boost_mode": "multiply"
    }
  },
  "rescore": {
    "window_size": 10,
    "query": {
      "rescore_query": {
        "match_phrase": {
          "title": {
            "query": "distributed data systems",
            "slop": 2
          }
        }
      },
      "query_weight": 1.0,
      "rescore_query_weight": 2.5
    }
  },
  "_source": ["title", "author", "price", "sales_count", "rating", "category"]
}
```

---

### Kriteria Kelulusan Challenge:
1. Dokumen ID `1` (*Designing Data-Intensive Applications*) harus menempati **Peringkat #1** karena mencakup kombinasi judul relevan, kategori cocok, rating tinggi (4.9), dan volume penjualan masif.
2. Dokumen ID `3` **tidak boleh muncul** di dalam hasil pencarian karena berstatus `"in_stock": false` dan tertolak oleh filter context.
3. Dokumen ID `5` (*Database Internals*) menempati posisi relevan berkat pencocokan cross-fields pada frasa data dan distributed systems di field `title` dan `summary`.

---

## Bagian 5: Checklist Pemahaman Mandiri

Gunakan checklist ini untuk menguji kesiapan arsitektur pencarian Anda sebelum melangkah ke topik agregasi dan performa kluster tingkat lanjut:

- [ ] **Konteks Query vs Filter:** Saya paham kapan harus menggunakan `must` versus `filter` dan dampaknya terhadap Node Query Cache serta konsumsi CPU.
- [ ] **Mekanika Term vs Full-text:** Saya bisa memprediksi token inverted index yang dihasilkan analyzer dan menghindari kegagalan pencarian `term` pada field bertipe `text`.
- [ ] **Parameter BM25 ($k_1$ dan $b$):** Saya memahami cara kerja saturasi term frequency dan normalisasi panjang dokumen dalam penentuan relevansi skor.
- [ ] **Multi-Match Strategies:** Saya tahu perbedaan teknis penggunaan `best_fields`, `most_fields`, dan `cross_fields` beserta mitigasi bias IDF.
- [ ] **Boosting Kontrol:** Saya dapat menerapkan boosting (`^`), negative boosting, dan `tie_breaker` tanpa menyebabkan lonjakan skor liar.
- [ ] **Explainability Debugging:** Saya mampu membaca dan membedah output `_explain` API untuk memverifikasi komponen perhitungan skor Lucene per shard.
- [ ] **Rescoring Performance:** Saya memahami kapan harus memindahkan kalkulasi berat (seperti script score atau phrase matching) ke dalam pipeline `rescore` window demi mempertahankan latensi SLA sub-50ms.
