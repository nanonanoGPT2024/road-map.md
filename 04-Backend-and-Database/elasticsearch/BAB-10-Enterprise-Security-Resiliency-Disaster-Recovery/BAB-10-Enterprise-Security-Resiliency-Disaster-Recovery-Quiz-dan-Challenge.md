# BAB-10-Enterprise-Security-Resiliency-Disaster-Recovery: Quiz, Challenge, & Knowledge Check

Dokumen ini dirancang untuk menguji, memvalidasi, dan memperdalam pemahaman teknis Anda seputar arsitektur keamanan tingkat enterprise (*TLS/mTLS, RBAC, DLS, FLS, Audit Logging*), strategi ketahanan klaster (*High Availability, Quorum, Shard Allocation Awareness*), serta kesiapan pemulihan bencana (*Snapshot Lifecycle Management, Cross-Cluster Replication*).

---

## Bagian 1: Pertanyaan Konseptual & Dasar (5 Basic Questions)

### Pertanyaan 1: Perbedaan Transport TLS vs HTTP TLS
**Pertanyaan:** Dalam konfigurasi Elasticsearch Security, mengapa komunikasi *Transport Layer* (`transport.ssl`) dan *HTTP Layer* (`http.ssl`) dipisahkan, dan apa dampak fatal jika Transport Layer dibiarkan tidak terenkripsi pada klaster multi-node?

<details>
<summary><b>Jawaban & Pembahasan</b></summary>

* **Fungsi Pemisahan:**
  * **HTTP Layer (`xpack.security.http.ssl`):** Mengamankan komunikasi REST API antara klien eksternal (aplikasi, Logstash, Kibana, curl) dengan Elasticsearch node.
  * **Transport Layer (`xpack.security.transport.ssl`):** Mengamankan komunikasi internal antar-node (TCP port 9300), termasuk sinkronisasi state klaster, transfer shard, pengiriman dokumen via internal replication, dan pemilihan master node (*consensus*).
* **Dampak Fatal Jika Transport Layer Terbuka:**
  Transport layer mempercayai node lain yang terhubung. Tanpa enkripsi dan mutual TLS (`ssl.verification_mode: certificate` / `full`), node liar (rogue node) dapat bergabung ke klaster secara ilegal, mencuri seluruh data shard, merusak *cluster state*, atau memicu eksekusi perintah berbahaya melalui deserialisasi data internal tanpa otentikasi REST layer.
</details>

---

### Pertanyaan 2: Mekanisme Autentikasi vs Otorisasi (RBAC)
**Pertanyaan:** Jelaskan bagaimana *Role-Based Access Control* (RBAC) bekerja di Elasticsearch saat memetakan *User*, *Role*, *Cluster Privileges*, dan *Index Privileges*!

<details>
<summary><b>Jawaban & Pembahasan</b></summary>

* **User:** Identitas prinsipal (dapat berupa native user internal atau bersumber dari LDAP, Active Directory, SAML, OIDC).
* **Role:** Kumpulan hak akses (*privileges*) yang mengontrol apa yang boleh dilakukan oleh user.
  * **Cluster Privileges:** Mengatur operasi tingkat klaster, seperti `monitor`, `manage`, `manage_index_templates`, `manage_snapshot_restore`.
  * **Index Privileges:** Mengatur operasi terhadap indeks spesifik atau wildcard (`read`, `write`, `create_index`, `delete`, `view_index_metadata`).
* **Mekanisme Eksekusi:** Setiap request yang masuk dievaluasi berdasarkan token/kredensial pengguna. Security plugin memeriksa apakah user memiliki role dengan hak akses yang mencukupi untuk endpoint target dan resource indeks yang diakses. Jika salah satu izin tidak terpenuhi, request ditolak seketika dengan status HTTP `403 Forbidden`.
</details>

---

### Pertanyaan 3: Batasan Quorum & Formula Pemilihan Master
**Pertanyaan:** Bagaimana mekanisme voting master modern (Elasticsearch 7.x+) mencegah kondisi *Split-Brain*, dan apa peran setting `cluster.initial_master_nodes`?

<details>
<summary><b>Jawaban & Pembahasan</b></summary>

* **Mekanisme Modern (Raft-like Consensus):** Sejak versi 7.0, parameter manual `discovery.zen.minimum_master_nodes` digantikan oleh algoritma *cluster coordination* otomatis yang mengelola konfigurasi voting dinamis (*voting configuration*).
* **Pencegahan Split-Brain:** Klaster membutuhkan suara mayoritas (`quorum = (n/2) + 1`) dari master-eligible nodes terdaftar untuk memilih master atau mengubah metadata klaster. Jika terjadi partisi jaringan (network partition), hanya partisi yang mempertahankan mayoritas quorum yang dapat beroperasi; partisi minoritas akan menolak operasi tulis sehingga split-brain mustahil terjadi.
* **Fungsi `cluster.initial_master_nodes`:** Hanya digunakan saat proses *bootstrapping* pertama kali saat klaster baru dibentuk untuk menentukan node mana yang diizinkan memenangkan pemilihan awal. Setelah klaster terbentuk, konfigurasi voting dikelola secara dinamis dan setting ini tidak boleh lagi diaktifkan saat rolling restart.
</details>

---

### Pertanyaan 4: Snapshot Repository & Immutability
**Pertanyaan:** Mengapa *Snapshot Repository* (misal via S3, GCS, atau shared NFS) harus didaftarkan dengan opsi `readonly` ketika dihubungkan ke klaster sekunder untuk disaster recovery?

<details>
<summary><b>Jawaban & Pembahasan</b></summary>

* **Pencegahan Konflik Metadata:** Repository snapshot menyimpan file indeks chunked (`snap-*.dat`, `index-*.dat`) dan index commit point.
* **Risiko Fatal Write Non-Readonly:** Jika dua klaster berbeda menulis ke satu repository snapshot yang sama tanpa koordinasi, klaster kedua dapat menimpa indeks snapshot metadata atau menghapus segment blob yang dianggap usang oleh lifecycle policy-nya, menyebabkan kerusakan permanen (*repository corruption*) pada data backup klaster utama. Menandai repository sebagai `readonly: true` pada klaster DR menjamin klaster tersebut hanya dapat membaca dan memulihkan data tanpa merusak integritas file.
</details>

---

### Pertanyaan 5: Leader Index vs Follower Index pada CCR
**Pertanyaan:** Dalam *Cross-Cluster Replication* (CCR), apa perbedaan operasional dan status keterbukaan tulis (*writeability*) antara *Leader Index* dan *Follower Index*?

<details>
<summary><b>Jawaban & Pembahasan</b></summary>

* **Leader Index:** Berada di klaster primer (*remote cluster*). Indeks ini menerima operasi indexing aktif (Create, Read, Update, Delete) secara langsung dari aplikasi. Indeks mempertahankan retention lease pada operasi Lucene untuk melacak riwayat perubahan.
* **Follower Index:** Berada di klaster lokal (klaster DR/sekunder). Indeks ini bersifat *read-only* bagi aplikasi eksternal. Daemon CCR secara aktif menarik (*pull*) log operasi dari leader shard dan mengeksekusikannya ke follower shard. Follower index baru dapat menerima operasi tulis langsung jika koneksi CCR diputus secara sengaja melalui API `_ccr/unfollow`.
</details>

---

## Bagian 2: Pertanyaan Tingkat Menengah (5 Intermediate Questions)

### Pertanyaan 6: Document-Level Security (DLS) vs Field-Level Security (FLS)
**Pertanyaan:** Jelaskan implementasi teknis Document-Level Security (DLS) dan Field-Level Security (FLS) pada definisi role! Bagaimana kinerja search query dipengaruhi oleh DLS?

<details>
<summary><b>Jawaban & Pembahasan</b></summary>

* **Field-Level Security (FLS):** Membatasi akses kolom/atribut tertentu pada dokumen JSON. Dikonfigurasi dalam field `fields: ["customer_id", "status"]` atau pengecualian `fields: ["*"], except: ["salary", "ssn"]`. Atribut yang di-mask tidak akan diekspos dalam response search, agg, maupun source.
* **Document-Level Security (DLS):** Membatasi dokumen mana yang boleh dilihat pengguna berdasarkan query Lucene, misal:
  ```json
  "query": {
    "term": { "tenant_id": "${_user.metadata.tenant_id}" }
  }
  ```
* **Dampak Performa:**
  DLS menyematkan klausa filter secara otomatis ke dalam setiap query Lucene tingkat shard sebelum eksekusi. Dampaknya:
  1. Overhead parsing dan evaluasi bitset cache untuk setiap pencarian.
  2. Cache query shard terfragmentasi per user/per tenant context, mengurangi rasio cache hit dibandingkan pencarian non-DLS.
</details>

---

### Pertanyaan 7: Shard Allocation Awareness & Forced Awareness
**Pertanyaan:** Dalam arsitektur multi-AZ (Availability Zone), apa perbedaan antara `cluster.routing.allocation.awareness.attributes: zone` biasa dengan *Forced Awareness* (`cluster.routing.allocation.awareness.force.zone.values`)?

<details>
<summary><b>Jawaban & Pembahasan</b></summary>

* **Awareness Biasa:**
  Elasticsearch mendistribusikan primary dan replica shard antar atribut kustom (misal node attribute `node.attr.zone: us-east-1a` dan `us-east-1b`). Tujuannya adalah memastikan primary dan replica tidak berada pada zona yang sama. Namun, jika salah satu zona *down*, Elasticsearch akan mengalokasikan seluruh replica ke zona yang masih hidup, berpotensi membebani disk dan resource I/O hingga 200%.
* **Forced Awareness:**
  Mengunci batas kapasitas zona dengan mendaftarkan seluruh zona yang valid secara eksplisit:
  ```yaml
  cluster.routing.allocation.awareness.force.zone.values: "zone-a,zone-b"
  ```
  Jika `zone-b` padam seluruhnya, Elasticsearch menolak mengalokasikan replica cadangan ke `zone-a`. Klaster akan berada pada status `YELLOW`, namun resource node pada `zone-a` terlindungi dari overload disk spillover dan memory exhaustion.
</details>

---

### Pertanyaan 8: Snapshot Lifecycle Management (SLM) & Retain Policy
**Pertanyaan:** Analisis skenario berikut: Klaster memproduksi 500GB log per hari. Tim devops menyetel jadwal SLM setiap jam (`0 0 * * * ?`) dengan retention policy: `expire_after: 7d`, `min_count: 5`, `max_count: 50`. Apa yang terjadi jika proses retention dijalankan dan ada 120 snapshot yang berumur kurang dari 7 hari?

<details>
<summary><b>Jawaban & Pembahasan</b></summary>

* **Evaluasi Aturan Retensi:**
  1. `expire_after: 7d`: Menghapus snapshot yang lebih tua dari 7 hari.
  2. `min_count: 5`: Memastikan minimal 5 snapshot tetap dipertahankan meski umurnya sudah melebihi 7 hari.
  3. `max_count: 50`: Membatasi jumlah absolut snapshot di repository.
* **Hasil:**
  Karena terdapat 120 snapshot yang umurnya masih kurang dari 7 hari, aturan `max_count: 50` memicu penghapusan 70 snapshot tertua di antara kumpulan tersebut hingga total snapshot tersisa tepat 50. Parameter `max_count` memiliki prioritas pembatasan kapasitas fisik repository untuk mencegah pembengkakan biaya storage objek.
</details>

---

### Pertanyaan 9: Soft Deletes & CCR Engine
**Pertanyaan:** Mengapa fitur `index.soft_deletes.enabled` wajib aktif (default sejak 7.0) pada indeks yang ingin direplikasi menggunakan Cross-Cluster Replication (CCR), dan apa konsekuensi dari parameter `index.soft_deletes.retention_lease.period`?

<details>
<summary><b>Jawaban & Pembahasan</b></summary>

* **Fungsi Soft Deletes:**
  Pada Lucene tradisional, dokumen yang dihapus atau di-update ditandai sebagai deleted bit dan dibuang secara fisik saat background segment merge. CCR membutuhkan sejarah operasi berurutan (*history of mutations*) untuk mengejar ketertinggalan follower shard. Soft deletes menahan dokumen yang dihapus di storage Lucene selama periode tertentu.
* **Peran Retention Lease:**
  Follower shard mendaftarkan *retention lease* pada leader shard. Leader menjamin segment yang memuat dokumen termutasi tidak akan di-merge/dibersihkan secara permanen selama follower aktif mereplikasi dalam jangka waktu `retention_lease.period` (default 12 jam). Jika follower mati lebih lama dari periode ini, lease kedaluwarsa, leader membuang tombstones, dan follower tidak bisa melanjutkan replay mutasi inkremental sehingga harus di-bootstrap ulang secara total (*fault/bootstrap resync*).
</details>

---

### Pertanyaan 10: Security Audit Logging Hardening
**Pertanyaan:** Mengapa mengaktifkan Audit Logging (`xpack.security.audit.enabled: true`) tanpa filter event (`xpack.security.audit.logfile.events.include/exclude`) dapat menimbulkan DoS (*Denial of Service*) internal pada cluster Elasticsearch produksi berkapasitas tinggi?

<details>
<summary><b>Jawaban & Pembahasan</b></summary>

* **Trafik & I/O Amplification:**
  Secara default tanpa filtering ketat, audit log merekam event `transport_request`, `authentication_success`, `anonymous_access_denied`, dan `access_granted` untuk setiap operasi REST dan internal node traffic.
* **Risiko DoS:**
  Pada klaster yang melayani puluhan ribu QPS, logging audit yang tidak terfilter akan menulis ratusan megabyte teks terstruktur per detik ke disk log node. Hal ini menyebabkan:
  1. Disk I/O bottleneck drastis yang menahan proses flush & commit Lucene data node.
  2. Partisi disk log cepat penuh (*disk watermark violation*).
  3. Lonjakan thread contention pada logging framework (Log4j2 async appender queue full), yang berakibat pada penolakan request (*thread pool exhaustion*).
* **Solusi Best Practice:** Eksklusikan event rutin internal seperti `transport_request` dan filter kategori hanya untuk security incident: `authentication_failed`, `access_denied`, dan `tampered_request`.
</details>

---

## Bagian 3: Skenario Kasus Nyata Produksi (3 Real-World Case Studies)

### Skenario 1: Cluster Health RED Pasca Data Center Maintenance (Split Brain & Corrupted Translog)

#### Kondisi Lapangan:
Sebuah perusahaan finansial memiliki klaster 7-node Elasticsearch yang terdistribusi di dua server room (Room-A: 4 node [2 master-eligible, 2 data], Room-B: 3 node [1 master-eligible, 2 data]). Setelah insiden pemadaman kabel fiber optik inter-rack selama 15 menit, klaster gagal pulih:
* Status klaster menjadi **RED**.
* Node di Room-B menolak bergabung ke master di Room-A.
* Log pada Node-01 Room-A menunjukkan: `master not discovered / voting configuration mismatch`.
* Tiga indeks utama transaksi (`idx-transactions-2026.10`) memiliki 4 unassigned primary shards dengan pesan: `[corrupt_index_exception] Translog corruption detected`.

#### Tugas Anda:
1. Analisis akar masalah arsitektur voting dan quorum yang keliru pada distribusi master-eligible node.
2. Tuliskan langkah penanganan (*incident response SOP*) untuk memulihkan unassigned primary shard yang korup translog-nya dengan risiko kehilangan data seminimal mungkin.

<details>
<summary><b>Panduan Solusi & Analisis</b></summary>

1. **Akar Masalah Quorum:**
   * Total master-eligible node = 3 (2 di Room-A, 1 di Room-B). Mayoritas quorum membutuhkan `floor(3/2) + 1 = 2` suara.
   * Ketika Room-A dan Room-B terputus, Room-A memiliki 2 master-eligible node sehingga dapat membentuk quorum, sedangkan Room-B hanya memiliki 1 master-eligible (minoritas) sehingga isolasi voting terpicu.
   * Namun penempatan jumlah master ganjil pada dua DC tanpa *tiebreaker third site* selalu berisiko bila DC mayoritas mengalami power surge parsial.
2. **SOP Pemulihan Shard Corrupt Translog:**
   * **Langkah 1 - Identifikasi Shard Bermasalah:**
     ```bash
     curl -s -u elastic:password -XGET "localhost:9200/_cat/shards?v=true&h=index,shard,prirep,state,unassigned.reason" | grep UNASSIGNED
     ```
   * **Langkah 2 - Analisis Tingkat Kerusakan Translog:**
     Periksa log spesifik shard di direktori data node yang memegang shard unassigned:
     `data/nodes/0/indices/<index-uuid>/<shard-id>/translog/`
   * **Langkah 3 - Truncate Translog Menggunakan Tool Resmi (Offline CLI):**
     Hentikan instance node yang bersangkutan, lalu jalankan utility bawaan:
     ```bash
     /usr/share/elasticsearch/bin/elasticsearch-translog truncate -d /var/lib/elasticsearch/data/nodes/0/indices/<INDEX_UUID>/<SHARD_ID>
     ```
     *Catatan:* Perintah ini membuang operasi yang belum sempat di-commit ke Lucene segment dari translog yang korup, namun menyelamatkan keseluruhan segment data historis.
   * **Langkah 4 - Start Node & Force Allocation jika Diperlukan:**
     Nyalakan kembali node. Jika primary shard masih unassigned karena lock flag:
     ```json
     POST /_cluster/reroute
     {
       "commands": [
         {
           "allocate_stale_primary": {
             "index": "idx-transactions-2026.10",
             "shard": 2,
             "node": "node-data-roomA-01",
             "accept_data_loss": true
           }
         }
       ]
     }
     ```
   * **Langkah 5 - Verifikasi Integritas:** Jalankan refresh dan index recovery check hingga status kembali `GREEN`.
</details>

---

### Skenario 2: Kebocoran Data Multi-Tenant via Field Injection & Privilege Escalation

#### Kondisi Lapangan:
Sebuah platform SaaS log analitik membagi data pelanggan dalam satu indeks terpusat (`customer-telemetry-2026`). Akses user dibatasi menggunakan Document-Level Security (DLS) dengan parameter:
```json
{
  "query": {
    "term": { "org_id": "${_user.metadata.tenant_code}" }
  }
}
```
Seorang security researcher melaporkan bahwa user dari `tenant_code: "TENANT_A"` berhasil mengintip log server `TENANT_B` ketika mengeksekusi payload agregasi tertentu melalui Kibana dev console menggunakan custom terms aggregations pada nested metadata atau script fields. Di saat yang sama, kredensial service account backend bocor ke repositori publik.

#### Tugas Anda:
1. Bedah titik lemah konfigurasi DLS dan skrip yang memungkinkan terjadinya *information leakage*.
2. Rancang arsitektur keamanan bertingkat (*defense-in-depth*) yang menggantikan desain *shared single index* tersebut.
3. Rancang rencana mitigasi kebocoran kredensial service account tanpa memicu *downtime* layanan backend.

<details>
<summary><b>Panduan Solusi & Analisis</b></summary>

1. **Titik Lemah:**
   * **Painless Scripting & Script Fields:** Script fields atau script query yang memiliki akses ke `doc['field']` atau `params['_source']` terkadang dapat mengekstraksi nilai dari index inverted files jika DLS filter tidak mengikat pada konteks script cache secara tepat atau jika ada celah bypass pada caching layer query level.
   * **Kelemahan Shared Index:** Berbagi satu indeks fisik antar tenant dengan isolasi hanya di tingkat software query filter memiliki *attack surface* tinggi.
2. **Desain Defense-in-Depth Baru:**
   * **Index-per-Tenant Isolation:**
     Ganti satu indeks bersama menjadi format terpisah: `customer-telemetry-{tenant_code}-*`.
   * **Role & Index Template Isolation:**
     Gunakan Role Templates dinamis:
     ```json
     {
       "indices": [
         {
           "names": [ "customer-telemetry-${_user.metadata.tenant_code}-*" ],
           "privileges": [ "read", "view_index_metadata" ],
           "field_security": {
             "grant": [ "timestamp", "log_level", "message", "host" ]
           }
         }
       ]
     }
     ```
   * Nonaktifkan `script_fields` dan inline runtime scripting untuk user dengan privilege rendah via role privileges (`cluster: [ "monitor" ]`, cabut hak eksekusi script global).
3. **Mitigasi Rotasi Kredensial Zero-Downtime:**
   * Buat API Key baru khusus backend services dengan role berbatas terkecil (*least privilege*):
     ```json
     POST /_security/api_key
     {
       "name": "backend-ingestion-v2",
       "role_descriptors": {
         "ingest_only": {
           "cluster": ["monitor"],
           "index": [
             {
               "names": ["customer-telemetry-*"],
               "privileges": ["write", "create_doc"]
             }
           ]
         }
       }
     }
     ```
   * Deploy API Key baru ke instance backend secara rolling update.
   * Setelah seluruh traffic beralih ke key baru, invalidate API Key lama atau ubah password native user yang bocor secara instan via API `POST /_security/api_key/_invalidate`.
</details>

---

### Skenario 3: Desain Active-Passive Cross-Region DR dengan RPO < 5 Menit & RTO < 15 Menit

#### Kondisi Lapangan:
Platform perbankan digital memiliki Primary Cluster di AWS Region `ap-southeast-1` (Singapura) dan Secondary Cluster di `ap-southeast-3` (Jakarta). Arsitek sistem menuntut:
* **Recovery Point Objective (RPO):** Maksimal 5 menit.
* **Recovery Time Objective (RTO):** Maksimal 15 menit saat terjadi failover regional.
* Volume data ingest: 50.000 dokumen/detik, 24/7.
* Latensi jaringan inter-region: ~35ms.

#### Tugas Anda:
1. Tentukan strategi sinkronisasi data yang sesuai (Snapshot vs CCR vs Dual-Write Kafka) beserta argumen teknis perbandingannya.
2. Buat matriks failover teknis runbook ketika Region Singapura mengalami pemadaman total (*total blackout*).

<details>
<summary><b>Panduan Solusi & Analisis</b></summary>

1. **Pemilihan Solusi Sinkronisasi:**
   * **Snapshot & Restore:** RPO 5 menit mustahil dicapai secara andal karena snapshot segment upload ke S3 dan metadata exchange membutuhkan waktu 10-20 menit per batch.
   * **Dual-Write dari Aplikasi/Kafka:** Membebani producer, rawan divergensi urutan dokumen (*out-of-order execution*), dan sulit menangani penghapusan dokumen secara deterministik antar-region.
   * **Pilihan Terbaik: Cross-Cluster Replication (CCR):**
     * CCR bekerja pada tingkat Lucene operation engine secara asinkron.
     * Latensi replikasi di atas link 35ms umumnya hanya berkisar 100ms - 2 detik, memenuhi RPO < 5 menit dengan margin sangat aman.
     * Mendukung auto-follow patterns untuk indeks berbasis waktu/data stream.
2. **Matriks Runbook Failover Regional (RTO < 15 Menit):**

| Menit Ke- | Aktor / Komponen | Tindakan Teknis |
|---|---|---|
| **00:00 - 02:00** | Monitoring / SRE Lead | Validasi blackout Region Singapura (Heartbeat loss confirmation). Deklarasi darurat DR. |
| **02:00 - 05:00** | Automation Engine / SRE | Eksekusi script convert Follower Index menjadi Regular Index pada Jakarta Cluster: <br>`POST /_ccr/auto_follow/telem_pattern/pause`<br>`POST /<index-name>/_ccr/pause_follow`<br>`POST /<index-name>/_ccr/unfollow`<br>`POST /<index-name>/_open` |
| **05:00 - 08:00** | Network / Route53 DNS | Alihkan traffic write ingress dari API Gateway SG ke Jakarta Endpoint (DNS Failover / Anycast IP switch). |
| **08:00 - 11:00** | Message Broker / Ingestion | Resume consumer worker pada Kafka cluster Jakarta untuk menembak endpoint cluster Jakarta yang kini bersifat read-write. |
| **11:00 - 14:00** | QA / Smoke Testing | Verifikasi health cluster Jakarta, eksekusi synthetic search & ingestion test. |
| **14:00** | Incident Commander | Layanan resmi dialihkan penuh ke Jakarta (RTO tercapai dalam ~14 menit). |
</details>

---

## Bagian 4: Practical Chapter Challenge (Hands-on Challenge)

### Judul Challenge: "Securing & Fortifying the Core: Zero-Trust Cluster Hardening & Disaster Recovery Drill"

#### Sasaran Praktik:
1. Mengonfigurasi mTLS Transport Encryption pada cluster 2-node.
2. Mengonfigurasi Role, User, Document-Level Security (DLS), dan Field-Level Security (FLS).
3. Mendaftarkan Local Filesystem / S3 Mockup Snapshot Repository dengan Snapshot Lifecycle Management (SLM).
4. Melakukan simulasi *Data Corruption Disaster* dan pemulihan data (*Restoration drill*).

---

### Langkah 1: Persiapan Node Certificates & TLS Configuration
Buka terminal dan buat sertifikat untuk kedua node menggunakan utilitas `elasticsearch-certutil`:

```bash
# 1. Generate Certificate Authority (CA)
/usr/share/elasticsearch/bin/elasticsearch-certutil ca --silent --pem --out /tmp/elastic-ca.zip
unzip /tmp/elastic-ca.zip -d /etc/elasticsearch/certs/

# 2. Generate Certs untuk Node dengan SAN (Subject Alternative Names)
cat << 'EOF' > /tmp/instances.yml
instances:
  - name: "node-1"
    ip: ["127.0.0.1", "172.20.0.2"]
    dns: ["node1.internal.domain"]
  - name: "node-2"
    ip: ["127.0.0.1", "172.20.0.3"]
    dns: ["node2.internal.domain"]
EOF

/usr/share/elasticsearch/bin/elasticsearch-certutil cert \
  --silent \
  --pem \
  --ca-cert /etc/elasticsearch/certs/ca/ca.crt \
  --ca-key /etc/elasticsearch/certs/ca/ca.key \
  --in /tmp/instances.yml \
  --out /tmp/node-certs.zip

unzip /tmp/node-certs.zip -d /etc/elasticsearch/certs/
```

Konfigurasikan pada `elasticsearch.yml` untuk setiap node:
```yaml
xpack.security.enabled: true
xpack.security.transport.ssl.enabled: true
xpack.security.transport.ssl.verification_mode: certificate
xpack.security.transport.ssl.key: /etc/elasticsearch/certs/node-1/node-1.key
xpack.security.transport.ssl.certificate: /etc/elasticsearch/certs/node-1/node-1.crt
xpack.security.transport.ssl.certificate_authorities: [ "/etc/elasticsearch/certs/ca/ca.crt" ]

xpack.security.http.ssl.enabled: true
xpack.security.http.ssl.key: /etc/elasticsearch/certs/node-1/node-1.key
xpack.security.http.ssl.certificate: /etc/elasticsearch/certs/node-1/node-1.crt
xpack.security.http.ssl.certificate_authorities: [ "/etc/elasticsearch/certs/ca/ca.crt" ]
```

---

### Langkah 2: Setup Role Granular (DLS + FLS)
Jalankan perintah HTTP API untuk membuat role `finance_restricted_role`:
* Hanya boleh melihat dokumen dengan `department: "finance"`.
* Dilarang melihat kolom `credit_card_number` dan `account_balance` (FLS exclusion).

```bash
curl -k -u elastic:SecurePassword123! -XPOST "https://localhost:9200/_security/role/finance_restricted_role" \
-H "Content-Type: application/json" -d '{
  "cluster": ["monitor"],
  "indices": [
    {
      "names": [ "audit-financial-*" ],
      "privileges": [ "read", "view_index_metadata" ],
      "field_security": {
        "grant": [ "*" ],
        "except": [ "credit_card_number", "account_balance" ]
      },
      "query": {
        "term": {
          "department.keyword": "finance"
        }
      }
    }
  ]
}'
```

Buat user `auditor_user` dan assign role tersebut:
```bash
curl -k -u elastic:SecurePassword123! -XPOST "https://localhost:9200/_security/user/auditor_user" \
-H "Content-Type: application/json" -d '{
  "password" : "AuditorStrongPassword2026!",
  "roles" : [ "finance_restricted_role" ],
  "full_name" : "Auditor Internal",
  "email" : "auditor@company.internal"
}'
```

---

### Langkah 3: Konfigurasi Snapshot Repository & SLM Policy
1. Tambahkan path repository pada `elasticsearch.yml`:
   ```yaml
   path.repo: ["/mnt/es_backups"]
   ```
2. Daftarkan repository via REST API:
   ```bash
   curl -k -u elastic:SecurePassword123! -XPOST "https://localhost:9200/_snapshot/fs_backup_repo" \
   -H "Content-Type: application/json" -d '{
     "type": "fs",
     "settings": {
       "location": "/mnt/es_backups",
       "compress": true
     }
   }'
   ```
3. Pasang Snapshot Lifecycle Management (SLM) Policy:
   ```bash
   curl -k -u elastic:SecurePassword123! -XPUT "https://localhost:9200/_slm/policy/daily-audit-snapshots" \
   -H "Content-Type: application/json" -d '{
     "schedule": "0 30 1 * * ?", 
     "name": "<audit-snap-{now/d}>",
     "repository": "fs_backup_repo",
     "config": {
       "indices": ["audit-financial-*"],
       "include_global_state": false
     },
     "retention": {
       "expire_after": "30d",
       "min_count": 7,
       "max_count": 30
     }
   }'
   ```

---

### Langkah 4: Disaster Simulation & Recovery Verification Drill
1. **Ingest Data Uji:**
   ```bash
   curl -k -u elastic:SecurePassword123! -XPOST "https://localhost:9200/audit-financial-2026.10/_doc/1" \
   -H "Content-Type: application/json" -d '{
     "timestamp": "2026-10-06T10:00:00Z",
     "department": "finance",
     "transaction_id": "TX-9901",
     "credit_card_number": "4111-2222-3333-4444",
     "account_balance": 150000000,
     "amount": 25000
   }'
   ```
2. **Trigger Manual Snapshot:**
   ```bash
   curl -k -u elastic:SecurePassword123! -XPOST "https://localhost:9200/_slm/policy/daily-audit-snapshots/_execute"
   ```
   *Tunggu beberapa detik dan verifikasi snapshot selesai:*
   ```bash
   curl -k -u elastic:SecurePassword123! -XGET "https://localhost:9200/_snapshot/fs_backup_repo/_all?v=true"
   ```
3. **Simulasi Disaster (Indeks Terhapus Tidak Sengaja):**
   ```bash
   curl -k -u elastic:SecurePassword123! -XDELETE "https://localhost:9200/audit-financial-2026.10"
   ```
4. **Eksekusi Prosedur Restore:**
   ```bash
   # Ambil nama snapshot terbaru dari daftar
   LATEST_SNAP=$(curl -sk -u elastic:SecurePassword123! -XGET "https://localhost:9200/_snapshot/fs_backup_repo/_all" | jq -r '.snapshots[-1].snapshot')

   # Restore index
   curl -k -u elastic:SecurePassword123! -XPOST "https://localhost:9200/_snapshot/fs_backup_repo/${LATEST_SNAP}/_restore" \
   -H "Content-Type: application/json" -d '{
     "indices": "audit-financial-2026.10",
     "rename_replacement": "audit-financial-2026.10"
   }'
   ```
5. **Validasi RBAC / DLS / FLS Sebagai Auditor:**
   ```bash
   curl -k -u auditor_user:AuditorStrongPassword2026! -XGET "https://localhost:9200/audit-financial-2026.10/_search?pretty"
   ```
   *Kriteria Kelulusan:*
   * Dokumen `TX-9901` berhasil ditemukan.
   * Field `credit_card_number` dan `account_balance` **TIDAK ADA** pada field `_source` hasil search auditor.

---

## Bagian 5: Checklist Pemahaman Mandiri

Gunakan daftar periksa ini untuk mengevaluasi kesiapan operasional Anda sebelum mengelola klaster produksi tingkat enterprise:

| Topik Utama | Poin Verifikasi Kompetensi | Status (Paham / Butuh Review) |
|---|---|---|
| **TLS & mTLS** | Saya mampu mendiagnosis error SSL handshake pada transport layer menggunakan tool openSSL dan logs Elasticsearch. | [ ] |
| **Certificate Rotation** | Saya memahami cara melakukan rolling update pembaruan SSL certificate sebelum masa kedaluwarsa tanpa mematikan klaster. | [ ] |
| **RBAC, DLS & FLS** | Saya dapat merancang template role dinamis berdasarkan metadata pengguna dan mengamankan data sensitif PII / PCI-DSS. | [ ] |
| **Audit Logging** | Saya mengetahui cara memfilter event security log agar disk tidak mengalami bottleneck I/O. | [ ] |
| **Quorum & Voting** | Saya mengerti formula konfigurasi master eligible node dan mitigasi risiko partisi jaringan (network partition). | [ ] |
| **Zone Awareness** | Saya mampu mengonfigurasi rack/zone allocation awareness beserta forced awareness untuk cluster multi-datacenter. | [ ] |
| **SLM Automation** | Saya dapat merancang jadwal backup otomatis lengkap dengan batasan retensi umur serta kapasitas storage. | [ ] |
| **CCR Replication** | Saya paham cara kerja retention lease, soft deletes, serta urutan langkah pemutusan replikasi saat disaster recovery failover. | [ ] |
| **Restore Verification** | Saya secara rutin mampu menguji coba pemulihan data snapshot ke klaster staging terisolasi secara otomatis. | [ ] |
