## SEKSI 01 — IDENTITAS MODUL

*   **Modul ID:** `GIT-CORE-05-01`
*   **Mata Pelajaran / Jalur:** Git & GitHub Core Foundations
*   **Kategori:** `01-Core-Foundations`
*   **Bab 05:** Remote Collaboration & Distributed Architectures
*   **Nama Modul:** Arsitektur Terdistribusi, Remote Repositories, dan Mekanisme Transport Git
*   **Tingkat Kesulitan:** Intermediate (Menengah)
*   **Prasyarat:**
    *   Memahami Object Model Git (Blob, Tree, Commit, Tag) — `GIT-CORE-02-01`.
    *   Menguasai Branching, Pointers, dan Manipulasi HEAD — `GIT-CORE-03-01`.
    *   Menguasai Analisis Riwayat Commit dan Log — `GIT-CORE-04-01`.
    *   Pemahaman dasar tentang protokol jaringan (SSH, HTTPS) dan Public Key Infrastructure (PKI).
*   **Estimasi Waktu Belajar:** 150 Menit (Teori: 60 Menit, Praktik Hands-On: 90 Menit)
*   **Versi Git Target:** Git versi 2.40.0 atau lebih baru (Sintaks kompatibel dengan implementasi modern).

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1.  **Mendekonstruksi Arsitektur Terdistribusi (DVCS):** Membedakan secara ontologis dan mekanis antara *Centralized VCS* (seperti Subversion/Perforce) dan *Distributed VCS* (Git), termasuk implikasinya terhadap ketersediaan (*availability*), redundansi, dan otonomi lokal.
2.  **Menganalisis Anatomi Remote Tracking References:** Menjelaskan representasi file internal dari remote references di bawah namespace `.git/refs/remotes/`, serta membedakan peran logis antara *local branch*, *remote-tracking branch*, dan *upstream branch*.
3.  **Mengoperasikan Konfigurasi Refspec dan Protokol Transport:** Mengkonfigurasi pemetaan *refspec* secara manual dalam `.git/config`, serta mengevaluasi kelebihan dan keterbatasan protokol transport Git (`ssh://`, `https://`, `git://`, dan *local file protocol*).
4.  **Membedah Siklus Sinkronisasi Objek:** Menelusuri fase *object negotiation* (protokol transmisi `ACK`/`NAK`), pembentukan *packfile*, dan pembaruan pointer selama eksekusi `git fetch`, `git push`, dan `git pull`.
5.  **Menyelesaikan Konflik Push Non-Fast-Forward Secara Deterministik:** Mengidentifikasi penyebab penolakan push (*atomic push rejection*), memitigasi bahaya destructive overwrite (`--force` vs `--force-with-lease`), dan menerapkan pola resolusi berbasis integrasi lokal yang aman.

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```text
                        +---------------------------------------+
                        |     Distributed Version Control       |
                        +---------------------------------------+
                                           |
                   +-----------------------+-----------------------+
                   |                                               |
                   v                                               v
    +-----------------------------+                 +-----------------------------+
    |     Transport Protocols     |                 |   Remote Data Structures    |
    |  (SSH, HTTPS, Git, File)    |                 |   (.git/refs/remotes/*)     |
    +-----------------------------+                 +-----------------------------+
                   |                                               |
                   +-----------------------+-----------------------+
                                           |
                                           v
                        +---------------------------------------+
                        |         Refspec Specifications        |
                        |   +refs/heads/*:refs/remotes/origin/*  |
                        +---------------------------------------+
                                           |
                   +-----------------------+-----------------------+
                   |                                               |
                   v                                               v
    +-----------------------------+                 +-----------------------------+
    |     Inbound Sync Cycle      |                 |     Outbound Sync Cycle     |
    |    (git fetch / git pull)   |                 |         (git push)          |
    +-----------------------------+                 +-----------------------------+
                   |                                               |
         [Negotiation: ACK/NAK]                          [Fast-Forward Validation]
                   |                                               |
           [Packfile Transfer]                             [packfile generation]
                   |                                               |
                   v                                               v
      [Remote-Tracking Pointer]                        [Remote Branch Reference]
```

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

Pada sistem terpusat (CVCS) seperti Subversion (SVN), *repository* tunggal bertindak sebagai *single point of failure* (SPOF) dan *arbiter* mutlak kebenaran state kode. Ketika koneksi jaringan terputus, developer kehilangan kemampuan untuk melakukan commit, melihat diff historis, membuat branch, atau memverifikasi integritas riwayat proyek.

Git mengubah paradigma ini melalui arsitektur terdistribusi (*Distributed Version Control System* / DVCS):
1. **Setiap Kloning Adalah Backup Lengkap:** Setiap workstation developer menyimpan salinan penuh dari seluruh *object database* dan riwayat komit proyek, memitigasi risiko kehilangan data bencana.
2. **Operasi Lokal Instan Tanpa Latensi Jaringan:** Operasi branching, commit, diff, dan log dieksekusi 100% secara lokal pada memori dan disk mesin kerja, menghilangkan latensi jaringan dari siklus iterasi harian developer.
3. **Fleksibilitas Topologi Kolaborasi:** Git tidak mendikte hierarki manajemen. Sebuah tim dapat mengadopsi model terpusat sederhana (*centralized hub-and-spoke*), model integrasi hierarkis (*benevolent dictator & lieutenants* seperti pada kernel Linux), atau model peer-to-peer terdistribusi murni.

Memahami cara kerja remote bukan sekadar menghafal perintah `git push` dan `git pull`. Kesalahan pemahaman pada layer ini sering kali berujung pada hilangnya riwayat commit produksi akibat *force push* yang ceroboh, polusi git history akibat *unintended merge commits*, dan kegagalan otomatisasi pipeline CI/CD akibat miskonfigurasi branch tracking dan protokol transport.

---

## SEKSI 05 — APA ITU (WHAT)

### Konsep Remote Repository
Secara teknis, **Remote Repository** di Git hanyalah salinan repository lain dari proyek yang sama yang dihubungkan melalui alias jaringan (seperti `origin` atau `upstream`). Pada dasarnya tidak ada perbedaan struktur internal antara repositori lokal Anda dan repositori di server GitHub/GitLab, kecuali fakta bahwa repositori server biasanya diinisialisasi sebagai **Bare Repository** (repositori tanpa *Working Tree*, ditandai dengan opsi `--bare`, yang hanya memuat isi direktori internal `.git/`).

### Bare vs Non-Bare Repository
*   **Non-Bare Repository:** Menyimpan direktori `.git/` bersama salinan kerja file nyata (*Working Tree*). Digunakan oleh manusia untuk mengedit kode.
*   **Bare Repository:** Hanya menyimpan object store (`objects/`), metadata referensi (`refs/`), file konfigurasi (`config`), dan HEAD. Repositori ini tidak memiliki file kerja yang dapat diedit langsung. Target `git push` dari developer **harus** berupa bare repository untuk mencegah konflik inkonsistensi antara state index dan file di working tree server.

### Tiga Kategori Cabang (Branching Taxonomy)
Dalam kolaborasi terdistribusi, kita harus membedakan tiga entitas branch:
1.  **Local Branch:** Pointer lokal independen yang dapat digerakkan secara bebas oleh commit developer (contoh: `refs/heads/main`).
2.  **Remote-Tracking Branch:** Salinan *read-only* (proxy) dari status terakhir remote branch saat koneksi jaringan terakhir kali dibuat. Terletak di namespace `.git/refs/remotes/<remote>/<branch>` (contoh: `origin/main`). Developer tidak dapat memindahkan pointer ini secara manual; pointer ini hanya diperbarui oleh `git fetch`, `git pull`, atau `git push`.
3.  **Upstream Branch (Tracking Configuration):** Hubungan keterikatan (konfigurasi relasional) antara *Local Branch* dan *Remote-Tracking Branch*. Jika `main` dikonfigurasi untuk melacak `origin/main`, Git mengetahui ke mana data harus dikirim atau diambil saat developer hanya mengetik `git push` atau `git pull` tanpa argumen.

---

## SEKSI 06 — BAGAIMANA CARA KERJA (HOW)

### 1. Anatomi Protokol Transportasi
Git mendukung empat protokol utama untuk memindahkan objek antar-repositori:

| Protokol | Skema URL | Enkripsi / Autentikasi | Efisiensi Kinerja | Mekanisme Daemon |
| :--- | :--- | :--- | :--- | :--- |
| **Local** | `/path/to/repo.git` atau `file:///path/` | POSIX File Permissions | Paling Cepat (Hardlink jika memungkinkan) | Akses lokal filesystem |
| **Smart HTTPS**| `https://host/repo.git` | TLS, HTTP Basic Auth / Bearer Token | Cepat (Packfile compression), firewall-friendly | Dijalankan via HTTP endpoints (`git-upload-pack`) |
| **SSH** | `git@host:repo.git` atau `ssh://...` | Public Key Cryptography (Ed25519/RSA) | Sangat Cepat, overhead enkripsi minimal | Memanggil binary Git langsung via SSH remote shell |
| **Git Protocol**| `git://host/repo.git` | **Nol Enkripsi**, Nol Autentikasi | Tercepat secara raw throughput, port 9418 | Git Daemon internal (hanya read-only public) |

### 2. Anatomi Refspec (Reference Specifications)
Refspec memetakan referensi repositori lokal ke repositori remote, atau sebaliknya. Konfigurasi ini disimpan di `.git/config`:

```ini
[remote "origin"]
    url = git@github.com:octocat/example.git
    fetch = +refs/heads/*:refs/remotes/origin/*
```

Sintaks Refspec memiliki format: `[+]<source_ref>:<destination_ref>`
*   Tanda `+` (opsional): Menginstruksikan Git untuk memperbarui referensi tujuan bahkan jika itu bukan operasi *fast-forward* (override safety).
*   `<source_ref>`: Pola referensi sumber pada sisi remote (dalam kasus fetch).
*   `<destination_ref>`: Lokasi namespace lokal tempat referensi tersebut akan dipetakan.
*   Pola di atas berarti: *"Ambil seluruh branch di bawah `refs/heads/` pada remote `origin`, lalu simpan secara lokal di bawah namespace `refs/remotes/origin/`."*

### 3. Fase Sinkronisasi Fetch (Object Negotiation)
Ketika perintah `git fetch origin` dieksekusi:
1.  **Handshake Discovery:** Client menghubungi remote daemon (`git-upload-pack`). Remote mengirimkan daftar commit SHA-1 terbaru untuk setiap referensi yang dimilikinya.
2.  **Negotiation (ACK/NAK):** Client membandingkan daftar referensi remote dengan object database lokalnya. Client mengirimkan pesan `want <SHA-1>` untuk commit baru yang belum dimilikinya, dan `have <SHA-1>` untuk commit tertua yang sudah dimilikinya.
3.  **Packfile Generation:** Server menerima sinyal tersebut, menentukan batas commit yang hilang (*delta window*), mengemas objek-objek tersebut ke dalam satu file terkompresi (**Packfile**), dan mengirimkannya melalui pipe jaringan.
4.  **Index & Reference Update:** Client menerima packfile, memverifikasi checksum SHA, mengekstrak objek ke `.git/objects/`, dan memperbarui file referensi remote-tracking di `.git/refs/remotes/origin/<branch>`.
5.  **State Working Tree:** Pada titik ini, working tree dan branch lokal **sama sekali tidak berubah**.

```text
CLIENT (Local)                                              SERVER (Remote)
      |                                                            |
      | -------- 1. Request refs (ssh/https connection) ---------> |
      | <------- 2. List of refs & SHAs (Advertisement) ---------- |
      |                                                            |
      | -------- 3. "want <SHA_A>" / "have <SHA_B>" -------------> |
      | <------- 4. ACK/NAK response ----------------------------- |
      |                                                            |
      | <------- 5. Multiplexed Packfile Stream ------------------ |
      |                                                            |
      | 6. Index packfile locally                                  |
      | 7. Update .git/refs/remotes/origin/*                       |
      v                                                            v
```

### 4. Fast-Forward vs Non-Fast-Forward Push
Ketika client menjalankan `git push origin main`:
*   Client meminta server (`git-receive-pack`) untuk memperbarui pointer referensi `refs/heads/main` di server dari $SHA_{old}$ ke $SHA_{new}$.
*   **Fast-Forward Check:** Server memeriksa apakah $SHA_{old}$ merupakan *ancestor* (leluhur langsung) dari $SHA_{new}$ di dalam Directed Acyclic Graph (DAG).
    *   Jika **YA (Fast-Forward)**: Server memindahkan pointer ke $SHA_{new}$. Ini adalah operasi yang aman karena riwayat commit tidak terputus.
    *   Jika **TIDAK (Non-Fast-Forward)**: Server menolak pembaruan (*Push Rejected*). Kondisi ini terjadi jika ada commit lain di server yang belum ditarik oleh client. Menimpa pointer ini secara paksa akan menyebabkan commit di server terisolasi dan menjadi *dangling objects* (kehilangan commit).

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

Berikut adalah visualisasi arsitektur pemisahan memori/disk antara Repositori Lokal, Remote Tracking, dan Server Bare Repository:

```text
========================================================================================================
                        LOKAL REPOSITORY (DEVELOPER WORKSTATION)
========================================================================================================
[ WORKING TREE ]              [ STAGING AREA (INDEX) ]              [ LOCAL OBJECT DATABASE (.git) ]
(File fisik yang diedit)       (File siap dicommit)                 (Immutable Object Graphs)
       |                                |                                           |
       |  git add                       |                                           |
       +------------------------------->|                                           |
       |                                |  git commit                               |
       |                                +------------------------------------------>|
       |                                                                            |
       |                                                         Local Branch:      |
       |                                                         [refs/heads/main]  |
       |                                                                |           |
       |                                                                v           |
       |                                                         Commit C3 -------->|
       |                                                                |           |
       |                                                                v           |
       |                                                         Commit C2          |
       |                                                                |           |
       |                                                         Commit C1          |
       |                                                                            |
       |                                                         Remote-Tracking:   |
       |                                                         [refs/remotes/     |
       |                                                          origin/main]      |
       |                                                                |           |
       |                                                                v           |
       |                                                         Commit C2          |
       |                                                                            |
====================================================================================|===================
                                            ^                                       |
                   git fetch origin         |              git push origin main     |
                   (Download objects &      |              (Upload objects C3 &     |
                    update tracking)        |               update remote pointer)  |
                                            |                                       v
========================================================================================================
                          REMOTE BARE REPOSITORY (GITHUB / SERVER)
========================================================================================================
[ SERVER OBJECT STORE ]
       Commit C3 (Hanya ada setelah push)
            |
            v
       Commit C2 <----------------------------------------------- Remote Pointer:
            |                                                     [refs/heads/main]
            v                                                     (Menunjuk C2 sebelum push,
       Commit C1                                                   menunjuk C3 setelah push)
========================================================================================================
```

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

Menghubungkan repository lokal baru ke remote bare repository dan menganalisis mutasi referensi internal.

### 1. Inisialisasi Repositori
```bash
# Buat repositori lokal baru
mkdir project-local && cd project-local
git init -b main

# Tambahkan satu file dan buat commit awal
echo "console.log('v1.0.0');" > app.js
git add app.js
git commit -m "feat: initial commit"
```

Output:
```text
[main (root-commit) 4a8b12c] feat: initial commit
 1 file changed, 1 insertion(+)
 create mode 100644 app.js
```

### 2. Hubungkan Remote Repository
```bash
# Menambahkan remote dengan alias 'origin'
git remote add origin git@github.com:company/project-core.git

# Verifikasi konfigurasi URL
git remote -v
```

Output:
```text
origin  git@github.com:company/project-core.git (fetch)
origin  git@github.com:company/project-core.git (push)
```

### 3. Push Pertama Kali dengan Penandaan Upstream (`-u`)
```bash
git push -u origin main
```

Output:
```text
Enumerating objects: 3, done.
Counting objects: 100% (3/3), done.
Writing objects: 100% (3/3), 228 bytes | 228.00 KiB/s, done.
Total 3 (delta 0), reused 0 (delta 0), pack-reused 0
To github.com:company/project-core.git
 * [new branch]      main -> main
branch 'main' set up to track 'origin/main'.
```

### 4. Inspeksi Perubahan Internal `.git/config`
Jalankan perintah untuk membaca file konfigurasi lokal:
```bash
cat .git/config
```

Cuplikan output baru yang dihasilkan oleh argumen `-u` (`--set-upstream`):
```ini
[remote "origin"]
	url = git@github.com:company/project-core.git
	fetch = +refs/heads/*:refs/remotes/origin/*
[branch "main"]
	remote = origin
	merge = refs/heads/main
```
*Artinya: Branch lokal `main` sekarang secara otomatis mengarah ke remote `origin`, melacak perubahan referensi `refs/heads/main` di server.*

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

### Skenario: Arsitektur Multi-Remote (Forking Workflow Enterprise)
Developer "Alice" berkontribusi pada repositori inti organisasi (*Upstream*) melalui repository forking pribadinya (*Origin*). Alice perlu menyinkronkan branch pekerjaannya dengan rilis terbaru organisasi tanpa merusak linearitas commit.

```text
[ Upstream Central Repo ] (Canonical Organization)
        ^
        | git fetch upstream
        |
[ Local Workstation (Alice) ] -- git push origin my-feature --> [ Origin Fork Repo ]
                                                                       |
                                                               Pull Request (PR)
                                                                       v
                                                           [ Upstream Central Repo ]
```

#### Langkah 1: Konfigurasi Multi-Remote
```bash
# Kloning dari repositori personal fork
git clone git@github.com:alice/core-engine.git
cd core-engine

# Daftarkan canonical upstream repository
git remote add upstream git@github.com:enterprise-org/core-engine.git

# Inspeksi seluruh remote yang terkonfigurasi
git remote -v
```

Output:
```text
origin    git@github.com:alice/core-engine.git (fetch)
origin    git@github.com:alice/core-engine.git (push)
upstream  git@github.com:enterprise-org/core-engine.git (fetch)
upstream  git@github.com:enterprise-org/core-engine.git (push)
```

#### Langkah 2: Mengambil Pembaruan dari Upstream Tanpa Mengubah Working Directory
```bash
# Fetch seluruh referensi dan objek baru dari enterprise upstream
git fetch upstream
```

Output:
```text
remote: Enumerating objects: 12, done.
remote: Counting objects: 100% (12/12), done.
remote: Compressing objects: 100% (8/8), done.
remote: Total 12 (delta 4), reused 8 (delta 2)
Unpacking objects: 100% (12/12), 3.45 KiB | 590.00 KiB/s, done.
From github.com:enterprise-org/core-engine
 * [new branch]      main       -> upstream/main
 * [new branch]      release-v2 -> upstream/release-v2
```

#### Langkah 3: Integrasi Aman ke Fitur Lokal
Alice sedang bekerja di branch `feature-auth`. Alice perlu mengintegrasikan `upstream/main` terbaru menggunakan rebase untuk mempertahankan commit tree yang bersih:

```bash
git checkout feature-auth

# Rebase fitur lokal di atas upstream tracking branch
git rebase upstream/main
```

Output:
```text
Successfully rebased and updated refs/heads/feature-auth.
```

#### Langkah 4: Publikasi ke Fork Pribadi
```bash
# Push hasil kerja ke fork Alice (origin), bukan ke upstream
git push -u origin feature-auth
```

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

Ketika merancang alur kerja remote dan memilih mekanisme sinkronisasi, pertimbangkan trade-off berikut:

### 1. SSH Protocol vs Smart HTTPS Protocol

| Kriteria | SSH (`git@host:...`) | Smart HTTPS (`https://...`) |
| :--- | :--- | :--- |
| **Autentikasi** | Kunci Asimetris (Public/Private Key). Tanpa password interaktif (via `ssh-agent`). | Personal Access Tokens (PAT) atau OAuth via Credential Manager. |
| **Keamanan Perusahaan**| Membutuhkan port 22 terbuka. Sering diblokir firewall korporat ketat. | Melalui port standar 443. Selalu lolos firewall/proxy HTTP. |
| **Granularitas Akses** | Akses SSH tingkat mesin sering kali all-or-nothing (kecuali dibungkus software layer). | Memungkinkan delegasi scope token berbutir halus (fine-grained PAT). |
| **Automasi / CI/CD** | Sangat mudah via *Deploy Keys* tanpa terikat akun pengguna individu. | Membutuhkan *Machine Users* atau short-lived identity federation (OIDC). |

### 2. Mekanisme Sinkronisasi: `git pull` vs `git fetch` + Manual Merge/Rebase

```text
git pull  ==  git fetch + git merge (secara default)
```

*   **Trade-off Menggunakan `git pull` Langsung:**
    *   *Keuntungan:* Cepat, satu baris perintah.
    *   *Risiko:* Secara otomatis mengeksekusi merge commit jika ada divergensi riwayat. Ini mengaburkan graph commit dengan *"Merge branch 'main' of ... into main"*, serta memaksa developer menyelesaikan konflik di tengah operasi yang tidak disadari penuh.
*   **Trade-off Menggunakan `git fetch` lalu `git merge/rebase` Terpisah:**
    *   *Keuntungan:* Memberikan fase observasi kritis. Developer dapat memeriksa apa yang berubah (`git log HEAD..origin/main`) sebelum memutuskan strategi penggabungan (`--ff-only`, `--rebase`, atau `--merge`).
    *   *Risiko:* Memerlukan dua langkah eksekusi manual.

---

## SEKSI 11 — BEST PRACTICES

1.  **Gunakan Selalu Kunci Kriptografi Modern untuk Transport SSH:**
    Hindari pembuatan kunci RSA legacy. Gunakan kurva Edwards-curve Digital Signature Algorithm (Ed25519):
    ```bash
    ssh-keygen -t ed25519 -C "developer@enterprise.domain"
    ```
2.  **Konfigurasi Default Pull Menjadi Rebase atau Fast-Forward Only:**
    Cegah polusi riwayat commit lokal dengan merge commit yang tidak disengaja melalui konfigurasi global:
    ```bash
    git config --global pull.rebase true
    # ATAU
    git config --global pull.ff only
    ```
3.  **Gunakan `--force-with-lease` Menggantikan `--force` Mentah:**
    Jika terpaksa melakukan overwrite pada remote branch setelah interaktif rebase, jangan pernah gunakan `git push --force`. Gunakan:
    ```bash
    git push --force-with-lease
    ```
    *Mekanisme:* Perintah ini memverifikasi bahwa pointer remote-tracking branch lokal kita (`origin/feature`) identik dengan pointer aktual di server sebelum menimpa. Jika ada rekan tim yang melakukan push commit baru ke branch tersebut tanpa sepengetahuan Anda, push akan ditolak dan mencegah terhapusnya pekerjaan orang lain.
4.  **Lakukan Pembersihan Rutin Remote Branch yang Kadaluarsa (*Pruning*):**
    Ketika branch dihapus di remote repository, local remote-tracking branches tidak terhapus otomatis secara default. Bersihkan stale references secara periodik:
    ```bash
    git fetch --prune origin
    ```
    Atau aktifkan secara global:
    ```bash
    git config --global fetch.prune true
    ```

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

### 1. The "Detached HEAD" Trap Melalui Checkout Remote Branch
*   **Kesalahan:** Developer menjalankan `git checkout origin/main` alih-alih `git checkout main`.
*   **Dampak:** Git beralih ke status **Detached HEAD**. Segala commit baru yang dibuat di status ini tidak memiliki branch lokal penampung dan akan hilang tersapu garbage collector (`git gc`) saat developer berpindah branch lain.
*   **Pencegahan/Solusi:** Remote-tracking branches (`origin/*`) bersifat *read-only proxy*. Selalu checkout branch lokal. Jika ingin membuat branch baru dari state remote:
    ```bash
    git checkout -b local-feature origin/main
    ```

### 2. Mengabaikan Status `[rejected - non-fast-forward]`
*   **Kesalahan:** Mengalami kegagalan push, lalu langsung mengeksekusi `git push -f` tanpa membaca pesan kesalahan:
    ```text
    ! [rejected]        main -> main (non-fast-forward)
    error: failed to push some refs to 'git@github.com:...'
    hint: Updates were rejected because the tip of your current branch is behind
    hint: its remote counterpart.
    ```
*   **Dampak:** Terhapusnya riwayat commit rekan kerja yang telah dipublikasikan di remote server.
*   **Pencegahan:** Selalu lakukan `git fetch origin`, lakukan inspeksi log (`git log HEAD..origin/main`), gabungkan perubahan remote secara lokal via rebase atau merge, baru lakukan push kembali.

### 3. Mengasumsikan `git fetch` Mengubah Kode Sumber
*   **Kesalahan:** Menjalankan `git fetch`, lalu panik atau heran mengapa bug di file lokal belum terupdate.
*   **Dampak:** Kebingungan operasional. `git fetch` **hanya** memperbarui local object database dan pointer `refs/remotes/`. File di working directory tidak tersentuh sebelum dilakukan instruksi integrasi (`merge` / `rebase`).

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Latihan 1: Simulasi Lingkungan Remote Lokal Menggunakan Bare Repository (Guided)
**Tujuan:** Memahami bagaimana Git berkomunikasi via protokol filesystem lokal tanpa memerlukan akun GitHub/GitLab.

1.  Buat direktori kerja baru dan inisialisasi bare repository sebagai representasi "Server Pusat":
    ```bash
    mkdir -p /tmp/git-lab/central-server.git
    cd /tmp/git-lab/central-server.git
    git init --bare
    ```
2.  Buka terminal baru, buat repository developer "Alice":
    ```bash
    mkdir -p /tmp/git-lab/alice-workstation
    cd /tmp/git-lab/alice-workstation
    git init -b main
    echo "Feature A by Alice" > feature.txt
    git add feature.txt
    git commit -m "feat: initial commit by Alice"
    ```
3.  Hubungkan repositori Alice ke bare repository server dan lakukan push upstream:
    ```bash
    git remote add origin /tmp/git-lab/central-server.git
    git push -u origin main
    ```
4.  Verifikasi bahwa branch dan objek berhasil tersimpan pada bare repository:
    ```bash
    cd /tmp/git-lab/central-server.git
    git branch -a
    git log -1
    ```

### Latihan 2: Deteksi dan Investigasi Divergensi Branch (Semi-Guided)
**Tujuan:** Mensimulasikan persaingan push (race condition) antar-developer dan membedah state DAG.

1.  Di direktori `/tmp/git-lab/`, kloning repositori server sebagai "Bob":
    ```bash
    cd /tmp/git-lab
    git clone /tmp/git-lab/central-server.git bob-workstation
    ```
2.  Sebagai Bob: Tambahkan commit baru dan push ke server:
    ```bash
    cd /tmp/git-lab/bob-workstation
    echo "Update by Bob" >> feature.txt
    git commit -am "fix: Bob patch"
    git push origin main
    ```
3.  Kembali ke workstation Alice (`cd /tmp/git-lab/alice-workstation`):
    Buat commit lokal *tanpa* melakukan fetch/pull terlebih dahulu:
    ```bash
    echo "Conflicting update by Alice" >> feature.txt
    git commit -am "fix: Alice conflicting patch"
    ```
4.  Coba lakukan push dari sisi Alice:
    ```bash
    git push origin main
    ```
    *Amati pesan penolakan non-fast-forward.*
5.  Gunakan `git fetch origin` untuk mendownload commit Bob tanpa menyentuh working tree Alice.
6.  Jalankan perintah ini untuk melihat titik divergensi graph commit:
    ```bash
    git log --graph --oneline --all
    ```
7.  Integrasikan commit Bob dengan aman:
    ```bash
    git rebase origin/main
    # Jika terjadi konflik file, selesaikan secara manual, kemudian:
    # git add feature.txt && git rebase --continue
    ```
8.  Push kembali dari workstation Alice.

### Latihan 3: Menangani Skenario Stale Remote References (Challenge)
**Tujuan:** Mengelola referensi remote-tracking yang tertinggal pasca-penghapusan branch di remote server.

1.  Dari workstation Bob, buat dan push branch baru bernama `hotfix/login-bug`:
    ```bash
    git checkout -b hotfix/login-bug
    echo "fix" > fix.txt
    git add fix.txt && git commit -m "fix: login bug"
    git push -u origin hotfix/login-bug
    ```
2.  Dari workstation Alice, ambil branch baru tersebut:
    ```bash
    git fetch origin
    git branch -r  # Pastikan origin/hotfix/login-bug terlihat
    ```
3.  Simulasikan penghapusan branch langsung pada Server Pusat:
    ```bash
    git push origin --delete hotfix/login-bug
    ```
4.  Periksa kembali daftar remote branch di sisi Alice (`git branch -r`). Anda akan melihat referensi `origin/hotfix/login-bug` masih ada meskipun branch fisiknya telah lenyap di server!
5.  Tuliskan dan eksekusi perintah Git untuk membersihkan pointer "hantu" (*stale reference*) tersebut dari workstation Alice.
6.  Verifikasi bahwa pointer lokal telah sinkron sempurna dengan server.

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

Jawablah pertanyaan-pertanyaan berikut untuk menguji pemahaman konseptual dan teknis Anda:

1. **Apa perbedaan mendasar antara perintah `git fetch` dan `git pull`?**
    * A. `git fetch` hanya dapat digunakan melalui protokol SSH, sedangkan `git pull` menggunakan HTTPS.
    * B. `git fetch` mengunduh objek dan memperbarui `refs/remotes/` tanpa mengubah working directory; `git pull` menjalankan `git fetch` lalu menggabungkan (*merge/rebase*) commit tersebut ke branch lokal aktif saat ini.
    * C. `git fetch` menghapus local commit yang belum di-push; `git pull` mempertahankannya.
    * D. `git fetch` memindahkan HEAD lokal secara langsung ke commit terbaru server.

2. **Diberikan entri `.git/config` berikut: `fetch = +refs/heads/*:refs/remotes/origin/*`. Apakah fungsi dari simbol tanda tambah (`+`) di awal refspec tersebut?**
    * A. Mewajibkan penambahan tanda tangan digital GPG pada commit yang di-fetch.
    * B. Mengizinkan pembaruan referensi lokal remote-tracking meskipun pembaruan tersebut bukan merupakan operasi *fast-forward*.
    * C. Menambahkan file baru yang ada di server ke Staging Area lokal secara otomatis.
    * D. Menginstruksikan Git untuk menyalin seluruh commit history secara rekursif termasuk submodule.

3. **Mengapa sebuah repositori di server produksi/pusat (seperti remote hub) harus selalu diinisialisasi dengan konfigurasi `--bare`?**
    * A. Repositori bare mengompresi data dua kali lebih padat dibanding repositori standar.
    * B. Mencegah terjadinya konflik inkonsistensi antara Working Tree server dengan operasi push yang dikirim oleh developer.
    * C. Karena repositori non-bare tidak mendukung protokol enkripsi SSH.
    * D. Agar Git daemon dapat mengeksekusi script hook tanpa hak akses root.

4. **Skenario: Developer A dan Developer B bekerja pada branch yang sama. Developer B telah melakukan push commit baru ke remote. Developer A, yang belum menarik commit B, mencoba menjalankan `git push --force`. Apa yang terjadi pada repositori remote?**
    * A. Git server mendeteksi anomali dan secara otomatis memisahkan commit B ke branch baru bernama `orphaned`.
    * B. Push Developer A ditolak karena server mendeteksi commit Developer B memiliki timestamp yang lebih lama.
    * C. Commit Developer B pada remote branch akan tertimpa dan terlepas dari riwayat branch (menjadi *dangling objects*), menyebabkan pekerjaan Developer B hilang dari commit history aktif.
    * D. Server secara otomatis melakukan 3-way merge antara perubahan Developer A dan Developer B.

5. **Apa fungsi dari flag `--force-with-lease` dibandingkan dengan `--force` biasa?**
    * A. Mengunci repositori remote agar developer lain tidak dapat membaca kode selama proses push berlangsung.
    * B. Membatasi ukuran packfile yang dikirim ke server maksimal 50 MB.
    * C. Memastikan operasi push paksa hanya akan berhasil jika nilai SHA-1 remote-tracking branch lokal identik dengan nilai SHA-1 branch di remote server saat ini.
    * D. Memberikan lisensi open-source secara otomatis pada commit yang dipaksa masuk ke server.

---

### Kunci Jawaban & Evaluasi

1.  **Jawaban: B.** `git fetch` melakukan transfer data murni dan memperbarui remote tracking branches di namespace internal `.git/refs/remotes/`. Working tree tidak termutasi. `git pull` setara dengan `git fetch` disusul instruksi integrasi (`git merge` atau `git rebase`).
2.  **Jawaban: B.** Karakter `+` pada refspec menonaktifkan pengecekan default *fast-forward safety check* untuk update referensi lokal tracking tersebut.
3.  **Jawaban: B.** Jika push dilakukan ke repositori non-bare yang memiliki working tree aktif pada branch yang sama, index dan file di disk server akan mengalami *de-synchronization* instan yang fatal terhadap commit HEAD terbaru.
4.  **Jawaban: C.** Perintah `--force` mentah mengabaikan status branch di remote server secara mutlak dan memaksa remote pointer berpindah ke commit lokal Developer A, menyingkirkan commit Developer B ke status unreferenced/dangling commit.
5.  **Jawaban: C.** Flag `--force-with-lease` bertindak sebagai *atomic conditional check*: operasi push hanya dieksekusi jika tidak ada perubahan baru di remote yang belum diketahui/di-fetch oleh client lokal.

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

1.  **Buku Resmi:**
    *   *Pro Git* (Second Edition) oleh Scott Chacon dan Ben Straub — **Chapter 2.5: Git Basics - Working with Remotes** dan **Chapter 10.5: Git Internals - The Refspec**. (Akses gratis via: `https://git-scm.com/book`).
2.  **Dokumentasi Resmi Git Manual Pages:**
    *   `git-remote(1)` — *Manage set of tracked repositories*.
    *   `git-fetch(1)` — *Download objects and refs from another repository*.
    *   `git-push(1)` — *Update remote refs along with associated objects*.
    *   `gitnamespaces(7)` — *Git namespaces architecture*.
3.  **Spesifikasi Protokol Internal Git:**
    *   *Git Transfer Protocols documentation* — `Documentation/technical/pack-protocol.txt` pada repositori source code Git (`https://github.com/git/git`).
4.  **Standar Kriptografi Terkait:**
    *   RFC 8709: *Ed25519 and Ed448 Public Keys in the Secure Shell (SSH) Protocol*.

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

*   **Arsitektur Terdistribusi (DVCS):** Setiap workstation developer memiliki replika lengkap dari *database* proyek. Ketergantungan terhadap server pusat hanya bersifat konvensional untuk kebutuhan kolaborasi tim, bukan ketergantungan arsitektural internal Git.
*   **Bare vs Non-Bare:** Server kolaboratif bersama (GitHub/GitLab/Server Internal) harus menggunakan *Bare Repository* (`--bare`) yang meniadakan working tree guna mencegah desinkronisasi fatal saat menerima `push`.
*   **Remote-Tracking Branches:** Namespace internal `.git/refs/remotes/<remote>/<branch>` bertindak sebagai cermin (*proxy snapshot*) dari kondisi terakhir server. File ini hanya diupdate melalui operasi sinkronisasi jaringan (`fetch`, `pull`, `push`) dan tidak boleh diedit langsung via `checkout`.
*   **Mekanisme Refspec:** Memetakan skema transfer commit antara namespace server dan namespace client lokal (`+refs/heads/*:refs/remotes/origin/*`).
*   **Protokol Transportasi:** SSH menawarkan otentikasi kunci asimetris tingkat tinggi untuk workstation developer, sedangkan Smart HTTPS memfasilitasi integrasi firewall-friendly serta manajemen token modern.
*   **Protokol Keselamatan:** Hindari penggunaan `git push --force` mentah di lingkungan kolaboratif. Gunakan konfigurasi `git push --force-with-lease` untuk memvalidasi bahwa Anda tidak menimpa pekerjaan developer lain secara buta.

---

## SEKSI 17 — GLOSARIUM

*   **Bare Repository:** Repositori Git yang hanya memuat metadata database internal `.git` tanpa adanya working tree untuk mengedit file secara langsung.
*   **Remote Tracking Branch:** Referensi lokal read-only yang memetakan status branch di repositori remote (contoh: `origin/main`).
*   **Upstream Branch:** Keterikatan eksplisit yang dikonfigurasi antara sebuah local branch ke remote tracking branch tertentu (diatur lewat `git branch -u` atau `git push -u`).
*   **Refspec:** Format string deklaratif yang memetakan referensi lokal dan referensi remote untuk operasi fetch dan push.
*   **Packfile:** Satu file biner terkompresi (`.pack`) yang memuat representasi zlib/delta dari banyak objek Git untuk meminimalkan beban transfer jaringan.
*   **Fast-Forward:** Suatu kondisi merge atau push di mana pointer target cabang dapat diperbarui secara linier hanya dengan memindahkannya ke depan, karena commit tujuan merupakan turunan langsung (*descendant*) dari commit asal.
*   **Object Negotiation:** Fase komunikasi antara Git client dan Git server di mana kedua pihak bertukar payload `want` dan `have` untuk meminimalkan transfer objek yang duplikat.
*   **Dangling Object:** Objek commit, blob, atau tree di dalam database Git yang kehilangan pointer referensi (tidak dapat dijangkau dari branch atau tag manapun).

---

## SEKSI 18 — CATATAN INSTRUKTUR

### Petunjuk Pedagogis
*   **Visualisasikan DAG Terlebih Dahulu:** Jangan biarkan siswa membayangkan branch sebagai "wadah file". Tekankan berulang-ulang bahwa branch hanyalah pointer 40-karakter (atau 64-karakter SHA-256) yang menunjuk ke sebuah commit. `origin/main` hanyalah file teks biasa di dalam direktori `.git/refs/remotes/origin/main`.
*   **Bongkar Mitos `git pull`:** Banyak pemula berasumsi `git pull` adalah perintah tunggal yang atomik. Buka direktori `.git/FETCH_HEAD` di depan kelas setelah mengeksekusi `git fetch` agar siswa melihat bukti fisik bahwa data telah masuk ke disk tanpa menyentuh file proyek mereka.
*   **Demonstrasi "Bencana Data":** Sangat direkomendasikan untuk mendemonstrasikan kecerobohan `git push --force` di depan kelas menggunakan dua direktori lokal terminal terpisah (simulasi Alice dan Bob). Tunjukkan bagaimana commit rekan kerja hilang, kemudian tunjukkan cara pemulihan melalui `reflog` repositori lokal Bob.

### Setup Laboratorium
*   Siswa tidak wajib memiliki koneksi internet publik ke GitHub/GitLab untuk modul ini. Semua latihan hands-on di atas dirancang 100% menggunakan protokol lokal (`file://` atau path absolut filesystem POSIX) menggunakan utilitas `git init --bare`. Ini menghindari isu blokir port jaringan kampus atau rate limit token.

---

## SEKSI 19 — CHANGELOG & VERSI

*   **Versi 1.0.0 (Oktober 2023):**
    *   Rilis kurikulum awal.
    *   Cakupan komprehensif konsep DVCS, Refspec, Object Negotiation, dan Simulasi Multi-Remote.
    *   Standarisasi materi berbasis Git versi 2.40+.
    *   Implementasi pedoman keamanan migrasi dari SSH RSA ke Ed25519 dan mitigasi destruktif `--force-with-lease`.

---

## SEKSI 20 — NAVIGASI KURIKULUM

*   **Modul Sebelumnya:** `GIT-CORE-04-01` — Deep-Dive Git Log, History Traversing, dan Revision Selection.
*   **Modul Saat Ini:** `GIT-CORE-05-01` — Arsitektur Terdistribusi, Remote Repositories, dan Mekanisme Transport Git.
*   **Modul Berikutnya:** `GIT-CORE-05-02` — Protokol Penggabungan Lanjutan: 3-Way Merges, Fast-Forward, dan Algoritma Recursive/ORT.