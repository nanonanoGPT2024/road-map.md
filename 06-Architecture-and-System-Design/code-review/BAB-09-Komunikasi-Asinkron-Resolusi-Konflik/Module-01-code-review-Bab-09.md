# KURIKULUM: CODE REVIEW DALAM ARSITEKTUR & DESAIN SISTEM

---

## SEKSI 01 — IDENTITAS MODUL

*   **Jalur Kurikulum:** 06-Architecture-and-System-Design
*   **Mata Pelajaran:** Code Review Culture, Architecture, & Socio-Technical Dynamics
*   **Modul:** Bab 09 — Modul 01
*   **Judul Modul:** Komunikasi Asinkron, Resolusi Konflik, & Mentoring: Memberikan Feedback Konstruktif, Resolusi Deadlock dalam Diskusi PR, Mentoring Insinyur Junior melalui Code Review
*   **Tingkat Kesulitan:** Advanced / Staff & Lead Engineer Track
*   **Prasyarat:** Pemahaman arsitektur perangkat lunak modular, pengalaman minimal 2 tahun dalam alur kerja Git kolaboratif (Trunk-Based / GitFlow), dan pemahaman dasar psikologi tim rekayasa perangkat lunak.
*   **Alokasi Waktu:** 8 Jam Pelatihan (Mandiri & Terpandu)

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1.  **Menganalisis (C4)** gesekan sosio-teknis dan bias kognitif dalam komunikasi asinkron pada *Pull Request* (PR) arsitektural.
2.  **Menerapkan (C3)** sintaks dan taksonomi *Conventional Comments* untuk mereduksi ambiguitas tonal dan mempercepat latensi review tim.
3.  **Merancang dan Mengoperasikan (C6)** protokol eskalasi formal untuk memecahkan kondisi *PR Deadlock* tanpa mengorbankan integritas arsitektur maupun keselamatan psikologis (*psychological safety*).
4.  **Mengevaluasi (C5)** kode dari insinyur junior menggunakan metode *Socratic Questioning* guna menumbuhkan kemampuan penalaran sistemik tanpa bersikap preskriptif atau menghambat laju *delivery*.

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```
                  ┌──────────────────────────────────────────────┐
                  │    SOSIO-TEKNIS CODE REVIEW (ASINKRON)       │
                  └──────────────────────┬───────────────────────┘
                                         │
         ┌───────────────────────────────┼───────────────────────────────┐
         ▼                               ▼                               ▼
┌──────────────────┐          ┌──────────────────────┐          ┌──────────────────┐
│   KOMUNIKASI     │          │  RESOLUSI DEADLOCK   │          │    MENTORING     │
│  KONSTRUKTIF     │          │  & ESCALATION PATH   │          │  INSINYUR JUNIOR │
└────────┬─────────┘          └──────────┬───────────┘          └────────┬─────────┘
         │                               │                               │
 ┌───────┴────────┐              ┌───────┴────────┐              ┌───────┴────────┐
 │ * Conventional │              │ * 2-Round Rule │              │ * Socratic     │
 │   Comments     │              │ * Sync Escape  │              │   Questioning  │
 │ * Intent vs    │              │   Hatch        │              │ * Cognitive    │
 │   Impact       │              │ * ADR / Tech   │              │   Scaffolding  │
 │ * Psychological│              │   Lead Tie-    │              │ * Praise vs    │
 │   Safety       │              │   Breaker      │              │   Critique     │
 └────────────────┘              └────────────────┘              └────────────────┘
```

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

Kode sumber adalah representasi fisik dari pemikiran tim, namun proses *code review* adalah aktivitas **sosio-teknis**. Studi empiris dalam industri perangkat lunak (termasuk riset dari Microsoft dan Google Engineering) membuktikan bahwa hambatan terbesar dalam siklus rilis perangkat lunak modern jarang disebabkan oleh kompilasi atau uji coba unit yang lambat, melainkan oleh **latensi review antar-manusia** dan **gesekan interpersonal**.

1.  **Dampak pada Latensi Pengiriman (Throughput):** Diskusi yang berputar-putar tanpa struktur dapat menahan PR selama berminggu-minggu (*review stalling*). Ini menyebabkan *merge debt*, *context switching*, dan frustrasi massal.
2.  **Degradasi Arsitektur Akibat Apatis:** Ketika proses review dirasa menghakimi atau menyakitkan, insinyur cenderung melakukan *silent approval* (menyetujui tanpa membaca) untuk menghindari konflik, meloloskan cacat arsitektur ke tahap produksi.
3.  **Retensi dan Pertumbuhan Talenta:** Review yang buruk menghancurkan *psychological safety* insinyur junior, memicu sindrom *imposter*, dan menurunkan efektivitas tim secara eksponensial.

---

## SEKSI 05 — APA ITU (WHAT)

### 1. Komunikasi Asinkron yang Konstruktif
Komunikasi asinkron adalah pertukaran informasi yang terpisah oleh waktu. Ketiadaan modulasi suara, ekspresi wajah, dan gestur tubuh menciptakan defisit konteks. Tanpa aturan baku, pembaca secara alami mengasumsikan niat negatif (*negative bias*). Komunikasi konstruktif di sini mengacu pada pemberian umpan balik yang berorientasi pada kode (objektif), bukan pada individu (personal), serta menyertakan justifikasi arsitektural eksplisit.

### 2. PR Deadlock
Kondisi di mana author dan reviewer berada dalam perselisihan teknis yang buntu—misalnya terkait pemilihan pola desain, batas domain (*domain boundaries*), atau abstraksi database—di mana reviewer menolak menyetujui (*Change Requested*) dan author menolak merombak kode.

### 3. Mentoring Berbasis Penyelidikan (Socratic Mentoring)
Bentuk transfer pengetahuan di mana reviewer senior tidak memberikan solusi mentah secara langsung, melainkan mengajukan pertanyaan terarah yang menuntun insinyur junior untuk menyadari batasan, kegagalan tersembunyi (*edge cases*), atau pelanggaran modularitas dari desain yang mereka buat.

---

## SEKSI 06 — BAGAIMANA BEKERJA (HOW)

### Alur 1: Taksonomi Conventional Comments
Untuk menghilangkan ambiguitas intensi, seluruh komentar review harus menggunakan label terstandarisasi dengan format:
`label [dekorator]: subjek (alasan teknis & saran perbaikan)`

| Label | Arti Operasional | Wajib Diselesaikan Sebelum Merge? |
| :--- | :--- | :--- |
| **`praise:`** | Mengapresiasi solusi elegan, pola yang tepat, atau uji coba komprehensif. | Tidak |
| **`nitpick:`** | Hal sepele (tata letak, penamaan minor sesuai konvensi). Reviewer tidak memblokir PR. | Opsional (Author boleh abaikan) |
| **`suggestion:`** | Alternatif implementasi yang lebih efisien atau rapi. Tidak kritis. | Opsional/Diskusikan |
| **`issue:`** | Masalah arsitektural, bug nyata, lubang keamanan, atau pelanggaran pola. | **YA (Blocker)** |
| **`question:`** | Reviewer tidak memahami intensi kode; butuh klarifikasi sebelum approval. | **YA (Harus dijawab)** |
| **`thought:`** | Ide eksploratif untuk masa depan, bukan bagian dari cakupan PR saat ini. | Tidak |

### Alur 2: Protokol Resolusi Deadlock (Prosedur 3-Langkah)

```
[Mulai Diskusi Asinkron]
         │
         ▼
[Round 1: Reviewer memberikan kritik arsitektur]
         │
         ▼
[Round 2: Author mendebat / mempertahankan pilihan]
         │
         ▼
Apakah tercapai konsensus teknis?
  ├── YA ──► [Implementasikan Solusi & Merge]
  └── TIDAK ──► 
         │
         ▼
[TRIGGER: 2-Round Max Rule Terlampaui]
         │
         ▼
[STEP 1: Sinkronisasi 10-Menit (Huddle/Call)]
  ├── Kesepakatan tercapai ──► [Author dokumentasikan rangkuman ke PR]
  └── Tetap Deadlock ──►
         │
         ▼
[STEP 2: Eskalasi ke Tech Lead / Arsitek (Tie-Breaker)]
  ├── Tech Lead memutuskan arah arsitektur
  └── Keputusan dituangkan dalam ADR (Architectural Decision Record) singkat di PR
         │
         ▼
[STEP 3: "Disagree and Commit" — PR Diperbarui & Disetujui]
```

### Alur 3: Pola Socratic Mentoring untuk Insinyur Junior
Penerapan mentoring melalui code review dibagi dalam tiga tingkatan abstraksi:
1.  **Level 1: Syntax & Idiom:** Apakah kode mengikuti idiom bahasa pemrograman? (Biarkan linter menangani hal ini otomatis; jangan buang waktu review manual).
2.  **Level 2: Defensive Design & Edge Cases:** Tuntun junior dengan pertanyaan konsekuensi (contoh: *"Apa yang terjadi pada transaksi ini jika API gateway memutus koneksi di baris ke-42?"*).
3.  **Level 3: Domain & Maintainability:** Tuntun junior memahami dampak decoupling (contoh: *"Jika kebutuhan bisnis mengharuskan kita mengganti Redis dengan DynamoDB bulan depan, modul mana saja yang terdampak oleh implementasi kelas ini?"*).

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

Berikut adalah alur mesin status penanganan Pull Request sejak pembukaan hingga resolusi deadlock dan penyelesaian mentoring.

```
       AUTHOR                                    REVIEWER
         │                                          │
         ├──────────── 1. Buka PR (Draft/Ready) ───►│
         │                                          │
         │                                          ├─── [Analisis: Domain,
         │                                          │     Keamanan, Concurrency]
         │                                          │
         │◄─── 2. Beri Feedback (Conventional) ─────┤
         │        (issue / suggestion / praise)     │
         │                                          │
┌────────┴──────────────────────────────────────────┴────────┐
│                        DISKUSI ASINKRON                    │
└────────┬──────────────────────────────────────────┬────────┘
         │                                          │
         ├──── 3. Penjelasan / Komit Baru ─────────►│
         │                                          │
  [KONSENSUS?]                                [KONSENSUS?]
         │                                          │
         ├─── TIDAK: Terjadi Ping-Pong (> 2 Putaran)┤
         │                                          │
         ▼                                          ▼
┌────────────────────────────────────────────────────────────┐
│              ESKALASI DEADLOCK: PROTOKOL SINKRON           │
├────────────────────────────────────────────────────────────┤
│ 1. Berhenti mengetik di PR.                                │
│ 2. Jadwalkan Sinkronisasi Tatap Muka/Video 10 Menit.       │
│ 3. Analisis Trade-off (Latensi vs Kompleksitas).           │
│                                                            │
│ Buntu? Panggil Lead/Principal Engineer sebagai Tie-Breaker │
└─────────────────────────────┬──────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────┐
│                    DOKUMENTASI KEPUTUSAN                   │
├────────────────────────────────────────────────────────────┤
│ Author menulis ringkasan keputusan di thread PR:           │
│ "Berdasarkan sync dengan @lead, kita memilih Opsi B        │
│  karena X, Y, Z. Tracking tech debt dibuat via Tiket-102" │
└─────────────────────────────┬──────────────────────────────┘
                              │
         ┌────────────────────┴─────────────────────┐
         ▼                                          ▼
  [Update Kode Selesai]                      [Approve PR]
         │                                          │
         └────────────── 4. Merge Kode ────────────►│
```

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

Berikut adalah komparasi langsung gaya umpan balik (feedback) dalam komentar PR:

### Kasus: Insinyur junior membuat koneksi database baru di dalam handler HTTP alih-alih menggunakan dependency injection / connection pool.

#### Contoh Buruk (Toksik, Ambigu, Menyerang Pribadi):
> *"Jangan lakukan ini! Kenapa kamu instansiasi DB di sini? Ini bikin lambat dan boros koneksi. Tolong baca lagi dokumentasi arsitektur kita."*

#### Mengapa Buruk?
- Nada bicara agresif dan condescending (*"Kenapa kamu..."*).
- Menyerang individu, bukan fokus pada implikasi kode.
- Tidak memberikan jalur aksi yang jelas atau bahan pembelajaran terstruktur.

#### Contoh Baik (Konstruktif, Menggunakan Conventional Comments & Socratic Mentoring):
> **`issue (blocking):`** Terjadi inisialisasi koneksi database langsung di dalam `PaymentHandler.ServeHTTP`.
>
> Setiap ada request masuk, runtime Go akan membuka *TCP handshake* baru ke PostgreSQL. Di bawah beban 500 RPS, ini akan menghabiskan batas *connection pool* database dalam beberapa detik dan menyebabkan *cascading failure* (error 503).
>
> **`suggestion:`** Bisakah kita memindahkan dependensi `*sql.DB` ke dalam struct `PaymentHandler` via *Constructor Injection*?
> 
> Referensi arsitektur modular kita ada di `docs/architecture/di.md`. Coba periksa implementasi serupa di `UserHandler` (`handlers/user.go:line 24`). Bagaimana pandanganmu terkait pendekatan tersebut?

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

Mari kita bedah skenario dunia nyata yang melibatkan konflik arsitektural dan pembimbingan junior.

### Konteks Kode: 
Seorang insinyur junior mengajukan implementasi pemrosesan pesanan di modul e-commerce menggunakan TypeScript/Node.js.

```typescript
// order.service.ts
import { db } from "../infrastructure/database";
import { EmailClient } from "../infrastructure/email";

export class OrderService {
  // PR Junior: Logika dicampur langsung di satu tempat
  async processOrder(orderId: string, userId: string): Promise<void> {
    const order = await db.orders.findById(orderId);
    if (!order) throw new Error("Order not found");

    if (order.status !== "PENDING") {
      throw new Error("Invalid order state");
    }

    // Melakukan mutasi state langsung
    order.status = "PAID";
    await db.orders.update(order);

    // Side-effect eksternal dijalankan sinkron tanpa proteksi transaksi
    const user = await db.users.findById(userId);
    const emailClient = new EmailClient();
    await emailClient.sendReceipt(user.email, order.total);
    
    // Audit log
    await db.logs.insert({ action: "ORDER_PROCESSED", orderId, timestamp: new Date() });
  }
}
```

### Review Asinkron & Dialog Resolusi

#### Reviewer (Senior Engineer):
```markdown
praise: Logika alur proses dasar dari status PENDING hingga PAID sudah runut dan mudah dibaca!

issue (blocking): Pemrosesan order ini menggabungkan mutasi status basis data dengan side-effect jaringan eksternal (`emailClient.sendReceipt`) tanpa jaminan konsistensi transaksional.
Jika server email mengalami timeout atau error 500:
1. Status pesanan di database sudah berubah menjadi PAID.
2. Eksekusi fungsi melempar error, sehingga klien mengira pesanan gagal.
3. Audit log tidak pernah dieksekusi.

question: Bagaimana jika `emailClient` gagal merespons dalam 10 detik di bawah beban tinggi? Apa dampaknya terhadap thread runtime dan koneksi database yang sedang menggantung?

suggestion: 
Mari kita terapkan *Outbox Pattern* atau pisahkan pengiriman email ke event listener asinkron (misal: RabbitMQ/Kafka domain event). Dengan begitu:
- Transaksi database hanya fokus pada mutasi pesanan & pembuatan record event.
- Kegagalan email dapat di-retry secara independen tanpa membatalkan order.

Bagaimana menurutmu jika kita buatkan abstraksi `DomainEventPublisher` di sini?
```

#### Author (Junior Engineer):
```markdown
Terima kasih sarannya Kak! Saya paham masalahnya sekarang.
Tapi kalau harus pasang message broker (RabbitMQ) di PR ini, scope-nya jadi terlalu besar dan rilis tiket ini bisa terlambat 3 hari sprint ini. 
Bolehkah saya pakai `try-catch` di sekitar `emailClient` dulu, dan kita buat tiket terpisah untuk Outbox Pattern?
```

#### Reviewer (Menerapkan Deadlock Avoidance & Trade-off):
```markdown
thought: Memasukkan broker pesan penuh memang berisiko *scope creep* untuk tiket ini. Kompromi yang bagus!

suggestion (non-blocking): 
Mari kita sepakati jalan tengah pragmatis:
1. Di PR ini, bungkus `emailClient.sendReceipt` dalam blok `try-catch`. Jika gagal, catat error di logging tapi jangan gagalkan eksekusi mutasi pesanan dan audit log.
2. Pindahkan inisialisasi `new EmailClient()` ke constructor `OrderService` agar kita tidak membuat instance baru setiap kali fungsi dipanggil.
3. Buatkan tiket Jira baru untuk "Implementasi Transactional Outbox Pattern pada Order Service", dan cantumkan nomor tiketnya di komentar kode (TODO).

Jika kamu setuju dengan pendekatan ini, silakan push perbaikannya, dan saya akan langsung berikan approval!
```

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

| Pendekatan | Keuntungan | Kerugian / Risiko | Mitigasi |
| :--- | :--- | :--- | :--- |
| **Socratic Mentoring (Bertanya Terarah)** | Membangun kemandirian kognitif junior; melatih pemikiran sistemik jangka panjang. | Membutuhkan waktu lebih lama; berisiko memperlambat PR kritis jika berlebihan. | Gunakan hanya untuk PR fitur reguler. Pada insiden/hotfix, gunakan pendekatan preskriptif langsung. |
| **Prescriptive Feedback (Langsung Beri Solusi/Patch)** | Eksekusi cepat; tidak ada ruang untuk misinterpretasi kode teknis. | Junior menjadi operator pasif (*copy-paster*); *learned helplessness*; ego author tertekan. | Selalu sertakan alasan *mengapa* solusi tersebut dipilih setelah memberikan cuplikan kode. |
| **Pemisahan PR Kecil vs PR Arsitektur Masif** | Reviewer fokus; deteksi kecacatan logika jauh lebih tinggi; minim deadlock. | Memerlukan koordinasi feature toggling dan integrasi branch bertahap yang disiplin. | Buat arsitektur modular dan gunakan strategi *Trunk-Based Development* dengan *Branch by Abstraction*. |
| **Strict Escalation Policy (Aturan 2 Putaran)** | Menghentikan *bikeshedding* dan debat ego tak berujung secara asinkron. | Sering memicu meeting sinkron jika tim belum terbiasa berdialog terstruktur. | Batasi meeting sinkron maksimal 10 menit dengan agenda eksplisit: *memilih trade-off*. |

---

## SEKSI 11 — BEST PRACTICES

1.  **Gunakan Prinsip "Code is Not You":** Pisahkan identitas insinyur dari kode yang mereka hasilkan. Gunakan kata ganti pasif atau fokus pada data:
    *   *Buruk:* "Kamu lupa membersihkan alokasi memory di sini."
    *   *Benar:* "Pointer ini belum dibebaskan dari heap, yang berpotensi memicu memory leak."
2.  **Batasi Ukuran Pull Request:** Ukuran optimal untuk mempertahankan atensi kognitif reviewer adalah **200-400 baris perubahan (LOC)** di luar file auto-generated/lockfile. Lebih dari 500 LOC menurunkan efektivitas penemuan bug secara drastis.
3.  **Wajibkan PR Description Berbasis Konteks:** Setiap PR arsitektur harus menjawab:
    *   *What changed?* (Apa yang berubah)
    *   *Why this architecture?* (Mengapa arsitektur ini dipilih)
    *   *Trade-offs considered?* (Alternatif apa yang ditolak dan alasannya)
4.  **Standarisasi Tanda Tangan Nitpick:** Tegaskan dalam dokumen tim bahwa label `nit:` atau `nitpick:` **bukan pemblokir**. Jika semua thread lain selesai, PR dapat langsung di-merge meskipun author memilih tidak mengimplementasikan saran nitpick tersebut.
5.  **Apresiasi Solusi Positif Secara Eksplisit:** Sisipkan setidaknya satu komentar `praise:` pada setiap review jika menemukan implementasi yang elegan, pola desain yang bersih, atau test case yang rapi. Ini membangun *psychological safety* yang kokoh.

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

1.  **Bikeshedding (The Law of Triviality):** Menghabiskan 40 komentar memperdebatkan nama variabel atau kurung kurawal, tetapi melewatkan ketiadaan indeks database pada query yang memproses miliaran baris data.
    *   *Solusi:* Serahkan gaya kode pada linter otomatis (*Prettier*, *golangci-lint*, *Ruff*). Manusia hanya me-review arsitektur, konsistensi data, dan keamanan.
2.  **Ghosting & Review Stalling:** Reviewer membiarkan PR menggantung tanpa status lebih dari 24 jam kerja, memaksa author memohon-mohon status review.
    *   *Solusi:* Terapkan SLA review tim (misal: *first-review < 4 business hours*).
3.  **Moving Goalposts (Menggeser Target):** Reviewer meminta perbaikan A. Setelah author memperbaiki A, reviewer meminta perbaikan B, C, dan D yang sebenarnya berada di luar cakupan awal PR.
    *   *Solusi:* Batasi ulasan baru hanya pada kode yang berubah sejak putaran pertama. Catat temuan di luar lingkup sebagai tiket tech-debt terpisah.
4.  **Passive-Aggressive Code Reviews:** Menggunakan sarkasme, tanda seru ganda, atau emoji yang mengejek (contoh: *"Menarik sekali cara ini... yakin jalan di prod?"*).
    *   *Solusi:* Terapkan aturan *zero-tolerance* untuk sarkasme dalam channel teknis asinkron.

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Skenario Latihan:
Anda adalah seorang Lead Architect. Tiga insinyur di tim Anda mengalami masalah dalam review PR. Terapkan protokol yang telah dipelajari untuk menyelesaikan kasus-kasus berikut:

#### Kasus 1: Mengubah Komentar Destruktif
Ubah ulasan berikut menjadi format **Conventional Comments** yang edukatif, konstruktif, dan aman secara psikologis:
> *"Ini kacau banget. Kenapa manggil repository langsung dari controller? Bersihin ini, bikin arsitektur kita berantakan aja."*

#### Kasus 2: Penanganan PR Deadlock
Junior Engineer (Author) bersikeras menggunakan *polimorfisme hierarkis yang rumit (Inheritance 4 lapis)* untuk memvalidasi transaksi diskon. Reviewer (Mid-level) menginginkan *Strategy Pattern berbasis komposisi murni*. 
Perdebatan sudah berlangsung selama 14 komentar dalam 3 hari, dan sprint tinggal menyisakan 2 hari lagi.
*Tugas Anda:* Susun draf intervensi Anda sebagai Lead Engineer di thread PR tersebut untuk memecahkan kebuntuan menggunakan protokol 3-langkah.

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

Jawablah pertanyaan berikut untuk menguji pemahaman Anda:

1.  **Apa perbedaan mendasar antara komentar berlabel `issue:` dan `suggestion:` dalam taksonomi Conventional Comments?**
    *   *A)* Tidak ada bedanya; keduanya wajib diperbaiki sebelum merge.
    *   *B)* `issue:` wajib diselesaikan karena memblokir merge (cacat teknis/bug), sedangkan `suggestion:` bersifat opsional dan menawarkan alternatif perbaikan.
    *   *C)* `suggestion:` hanya boleh ditulis oleh Tech Lead.
    *   *D)* `issue:` hanya untuk masalah linter, `suggestion:` untuk logika bisnis.

2.  **Kapan aturan "Escalation to Sync Hatch" harus dieksekusi dalam proses review?**
    *   *A)* Segera setelah reviewer pertama kali membaca kode.
    *   *B)* Ketika author dan reviewer telah bertukar argumen asinkron lebih dari 2 putaran tanpa tanda-tanda konsensus.
    *   *C)* Hanya jika code coverage turun di bawah 50%.
    *   *D)* Ketika pull request berisi lebih dari 200 baris kode.

3.  **Bagaimana pendekatan Socratic Questioning membantu insinyur junior dalam mendesain sistem?**
    *   *A)* Dengan menunjukkan bahwa senior engineer selalu tahu segalanya.
    *   *B)* Mengurangi kebutuhan untuk menulis automated test.
    *   *C)* Mengembangkan model mental sistemik junior dengan menanyakan skenario kegagalan, batasan skalabilitas, dan edge cases sehingga mereka menemukan solusinya sendiri.
    *   *D)* Memaksa junior menghafal seluruh Design Patterns dari buku GoF.

4.  **Apa itu fenomena *Bikeshedding* dalam code review?**
    *   *A)* Membangun infrastruktur server secara manual.
    *   *B)* Kecenderungan tim untuk menghabiskan waktu dan energi secara berlebihan mendebatkan hal-hal sepele, sementara isu-isu arsitektural yang masif diabaikan.
    *   *C)* Mengabaikan PR selama lebih dari dua minggu.
    *   *D)* Memberikan approval tanpa memeriksa kode sama sekali.

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

1.  **Google Engineering Practices Documentation:** *How to do a code review* & *The Standard of Code Review* (https://google.github.io/eng-practices/review/)
2.  **Conventional Comments Specification:** *A standard for formatting comments in code reviews* (https://conventionalcomments.org/)
3.  **Buku:** *Nonviolent Communication: A Language of Life* oleh Marshall B. Rosenberg (Fondasi psikologis untuk komunikasi tim dan resolusi konflik).
4.  **Buku:** *Accelerate: The Science of Lean Software and DevOps* oleh Nicole Forsgren, Jez Humble, & Gene Kim (Dampak review latency terhadap DORA metrics dan throughput rekayasa perangkat lunak).
5.  **Riset Empiris Microsoft:** *Expectations, Outcomes, and Challenges of Modern Code Review* oleh Bacchelli & Bird (Analisis sosio-teknis interaksi review insinyur perangkat lunak).

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

*   **Code Review adalah Proses Sosio-Teknis:** Kegagalan code review hampir selalu bermula dari gesekan komunikasi, kegagalan tata kelola konflik, dan ketiadaan *psychological safety*, bukan ketidakmampuan teknis sintaktis.
*   **Kejelasan Asinkron Menghilangkan Gesekan:** Penggunaan format standar seperti **Conventional Comments** mengeliminasi bias tonal negatif dan membedakan secara tegas hal-hal yang memblokir rilis (*issue*) dari saran non-kritis (*suggestion*, *nitpick*).
*   **Deadlock Harus Dikelola dengan Protokol, Bukan Dibiarkan:** Terapkan aturan batas 2 putaran (*2-Round Rule*). Hindari perdebatan tak berujung di komentar PR dengan beralih ke sinkronisasi singkat (10 menit) atau eskalasi berbasis peran (*Tech Lead tie-breaker*) melalui artefak ADR.
*   **Mentoring Bertujuan Mencetak Kemandirian:** Melalui *Socratic Mentoring*, insinyur senior membimbing junior untuk melihat batas-batas arsitektur (*trade-offs*, *concurrency*, *failover*) menggunakan pertanyaan terarah, bukan memaksakan opini preskriptif yang mematikan penalaran kritis.

---

## SEKSI 17 — GLOSARIUM

*   **Conventional Comments:** Standar struktural untuk memberi label pada komentar PR guna memperjelas intensi, bobot keparahan (*severity*), dan status wajib/tidaknya perbaikan dilakukan.
*   **Psychological Safety:** Kondisi di mana anggota tim merasa aman untuk mengambil risiko interpersonal, mengakui ketidaktahuan, membuat kesalahan yang wajar, dan mengemukakan ide tanpa takut dipermalukan.
*   **PR Deadlock:** Situasi kebuntuan di mana dua pihak atau lebih dalam code review tidak dapat mencapai konsensus teknis untuk melakukan merge, menghentikan progres pengiriman kode.
*   **Socratic Questioning:** Metode dialog tanya-jawab bertingkat untuk menstimulasi pemikiran kritis dan memunculkan ide-ide mendasar serta asumsi yang melandasi suatu keputusan desain.
*   **Bikeshedding (Law of Triviality):** Kecenderungan alokasi waktu dan perdebatan yang terbalik secara proporsional terhadap kepentingan teknis suatu masalah (fokus berlebihan pada hal sepele).
*   **Disagree and Commit:** Prinsip kepemimpinan di mana anggota tim dapat mendebatkan suatu keputusan secara agresif pada tahap diskusi, tetapi begitu keputusan final diambil oleh penanggung jawab, semua pihak berkomitmen 100% mengeksekusinya tanpa sabotase pasif.
*   **Architectural Decision Record (ADR):** Dokumen ringkas yang menangkap keputusan arsitektur penting bersama konteks dan konsekuensinya.

---

## SEKSI 18 — CATATAN INSTRUKTUR

*   **Pola Pengajaran:** Jangan biarkan modul ini menjadi sekadar ceramah teori etika kerja. Tekankan aspek rekayasa sistemik. Tunjukkan bagaimana komentar review yang buruk berbanding lurus dengan peningkatan *lead time for changes* dan *change failure rate* (DORA metrics).
*   **Latihan Bermain Peran (Roleplay):** Dalam sesi kelompok, pasangkan dua peserta didik di mana satu peserta berperan sebagai author yang defensif dan peserta lain berperan sebagai reviewer yang harus mengidentifikasi *race condition* tanpa memicu eskalasi emosional.
*   **Otomasi Linter:** Ingatkan peserta bahwa tugas manusia adalah me-review domain dan arsitektur. Jika kelas menemukan ada perdebatan format spasi, kurung, atau penamaan variabel di luar domain konteks, ingatkan bahwa itu adalah kegagalan konfigurasi tooling (*CI linters*), bukan tugas manusia.

---

## SEKSI 19 — CHANGELOG & VERSI

*   **Versi 1.0.0 (Maret 2025):** 
    *   Rilis awal materi kurikulum arsitektur standar GEMINI.md.
    *   Integrasi taksonomi Conventional Comments.
    *   Penyusunan protokol mitigasi PR Deadlock 3-Langkah dan template Socratic Mentoring.

---

## SEKSI 20 — NAVIGASI KURIKULUM

*   **Modul Sebelumnya:** Bab 08 — Modul 02: *Otomasi CI/CD, Linters, dan Static Analysis Security Testing (SAST) dalam Pipeline Code Review*
*   **Modul Berikutnya:** Bab 09 — Modul 02: *Desain Architectural Decision Records (ADR) dan Tata Kelola Perubahan Skala Enterprise melalui PR*