# BAB 05: Quiz, Challenge, & Knowledge Check
**Array, String Idiom, & Zero-Copy Buffer Processing**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Semantika *Array Decay* dan Perbedaan Tipe Fundamental
Jelaskan secara presisi pada level sistem dan kompilator apa yang terjadi saat array C mengalami *array-to-pointer decay*. Mengapa ekspresi `sizeof(arr)` dan `&arr` mengevaluasi tipe yang berbeda secara fundamental dibandingkan saat `arr` diteruskan sebagai argumen fungsi `void process(int arr[])`? Jelaskan representasi tipe (*type representation*) pada tabel simbol kompilator untuk kedua skenario tersebut!

### Soal 1.2: Idiom *Null-Terminated String* vs *Explicit Length Slice*
Bahasa C secara historis menggunakan konvensi *sentinel-terminated string* (karakter `'\0'`). Analisis konsekuensi arsitektural dari desain ini terhadap kompleksitas komputasi ($O(N)$ vs $O(1)$ untuk operasi dasar seperti *length checking* dan *concatenation*), risiko kerentanan keamanan (*unbounded reads*), serta ketidakmampuannya menangani representasi *substring* secara efisien tanpa mutasi memori (*zero-copy slice*).

### Soal 1.3: Mekanisme *Pointer Arithmetic* dan *Scaling Factor*
Diberikan deklarasi:
```c
uint32_t buffer[8];
uint32_t *ptr = buffer + 3;
```
Jelaskan perhitungan aritmetika pointer pada level instruksi mesin (assembly/register level) yang dilakukan oleh kompilator. Mengapa penambahan skalar `+ 3` pada pointer bertipe `uint32_t*` menghasilkan pergeseran alamat sebesar 12 byte, sedangkan penambahan yang sama pada pointer bertipe `void*` (jika menggunakan ekstensi GNU) atau `uint8_t*` hanya menghasilkan pergeseran 3 byte? Apa implikasi ketatnya terhadap kepatuhan batas perataan (*memory alignment compliance*)?

### Soal 1.4: Layout Memori: Multidimensional Array vs Array of Pointers
Bandingkan layout memori fisik, *spatial locality*, *cache utilization* (L1/L2 hits vs misses), dan *pointer chasing overhead* antara dua deklarasi berikut:
1. `char matrix_contiguous[1024][1024];`
2. `char *matrix_ragged[1024];` (di mana setiap elemen dialokasikan secara independen via `malloc(1024)`).

Gambarkan skema pemetaan alamat memori virtual dan implikasinya pada algoritma yang memproses data secara *row-major* vs *column-major*.

### Soal 1.5: Kontrak Semantik `memcpy` vs `memmove` dan Aturan *Restrict Aliasing*
Jelaskan perbedaan spesifikasi C Standard antara `memcpy` dan `memmove`. Apa signifikansi kata kunci `restrict` pada prototipe `void *memcpy(void *restrict dest, const void *restrict src, size_t n)`? Jelaskan skenario *overlapping memory* di mana penggunaan `memcpy` menghasilkan *Undefined Behavior* (UB) akibat optimasi kompilator berbasis instruksi vektor (SIMD, SSE/AVX), dan mengapa `memmove` menjamin determinisme dalam kondisi tersebut.

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Analisis Kegagalan Bounded String APIs (`strncpy` vs `snprintf` vs Custom Slice)
Tinjau potongan kode berikut yang dirancang untuk menyalin input jaringan ke dalam buffer lokal:
```c
void ingest_token(const char *network_stream, size_t max_len) {
    char local_buf[32];
    strncpy(local_buf, network_stream, sizeof(local_buf));
    printf("Token: %s\n", local_buf);
}
```
Identifikasi dua kerentanan fatal/kondisi *Undefined Behavior* yang dapat dipicu oleh implementasi ini ketika `network_stream` memiliki panjang $\ge 32$ byte atau ketika `network_stream` mengandung data biner `0x00`. Mengapa `strncpy` secara historis bukan fungsi pemotongan string yang aman, dan bagaimana Anda merancang fungsi copy string dengan garansi terminasi null yang deterministik tanpa *performance penalty*?

### Soal 2.2: *Signedness Trap* dan *Integer Underflow* pada Pemindaian Buffer Mundur
Analisis cacat logika (*flaw*) pada pola traversal buffer berikut:
```c
void scan_reverse(const uint8_t *buf, size_t len) {
    for (size_t i = len - 1; i >= 0; --i) {
        if (buf[i] == 0xFF) {
            handle_marker(i);
        }
    }
}
```
Jelaskan mengapa loop di atas memicu *infinite loop* dan akses memori di luar batas (*Out-of-Bounds memory access* / *SIGSEGV*). Bagaimana kompilator modern mengoptimalkan ekspresi ini, dan apa solusi idiomatis C yang aman tanpa mengubah tipe data dasar indeks menjadi *signed integer* yang rentan overflow?

### Soal 2.3: Konsekuensi Mutasi Data pada Zero-Copy Parser: Toksikasi `strtok`
Sebuah parser protokol biner/teks performa tinggi menggunakan `strtok` untuk memecah paket HTTP yang diterima langsung dari ring buffer soket.
Jelaskan secara struktural mengapa `strtok` melanggar prinsip *reentrancy* (*thread-safety*), merusak data asli pada buffer input (menginjeksi `\0`), dan menyebabkan malafungsi fatal jika buffer tersebut dipetakan menggunakan `mmap(..., PROT_READ, MAP_SHARED, ...)`. Apa perbedaan arsitektural penggunaan `strtok_r` vs abstraksi *read-only token slice* `{const char *ptr, size_t len}`?

### Soal 2.4: *Unaligned Pointer Type Punning* dari Raw Byte Stream
Pertimbangkan kode deserialisasi jaringan berikut:
```c
struct __attribute__((packed)) TelemetryHeader {
    uint8_t  magic;
    uint32_t sequence_id;
    uint64_t timestamp;
};

void parse_packet(const uint8_t *raw_wire_buffer) {
    // raw_wire_buffer berada pada alamat memori ganjil (misal: 0x7fff0001)
    const struct TelemetryHeader *header = (const struct TelemetryHeader *)(raw_wire_buffer + 1);
    printf("Seq: %u\n", header->sequence_id);
}
```
Jelaskan mengapa *direct pointer casting* dari byte buffer ke struct pointer memicu *Undefined Behavior* (UB) menurut standar ISO C (C11/C17 §6.3.2.3). Analisis dampak arsitekturalnya pada CPU non-x86 (seperti ARM Cortex-M0/M3 atau arsitektur SPARC) berupa *hardware alignment fault* (*bus error*), serta penalti siklus CPU pada arsitektur x86_64 modern. Bagaimana teknik deserialisasi *zero-copy* yang aman dan portabel tanpa melanggar aturan alignment?

### Soal 2.5: Invalidation of Pointers pada Resizing Buffer Dinamis
Diberikan arsitektur string dinamis sederhana berbasis slice:
```c
typedef struct {
    char *data;
    size_t len;
    size_t cap;
} DynamicBuffer;

typedef struct {
    const char *start;
    size_t length;
} StringView;

StringView extract_prefix(const DynamicBuffer *buf, size_t prefix_len) {
    return (StringView){ .start = buf->data, .length = prefix_len };
}

void append_data(DynamicBuffer *buf, const char *new_data, size_t n) {
    if (buf->len + n > buf->cap) {
        buf->cap = (buf->cap + n) * 2;
        buf->data = realloc(buf->data, buf->cap);
    }
    memcpy(buf->data + buf->len, new_data, n);
    buf->len += n;
}
```
Lacak kondisi kegagalan sistem (*dangling pointer/use-after-free*) yang muncul jika sebuah aplikasi memanggil `extract_prefix`, kemudian mengeksekusi `append_data`, dan selanjutnya mencoba membaca data dari `StringView` yang telah dibuat sebelumnya. Jelaskan mitigasi arsitektural sistem untuk mencegah *aliasing-invalidation* semacam ini dalam ekosistem C yang tidak memiliki borrow checker bawaan.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Insiden Bottleneck Latensi P99 pada Pipeline Ingestion Jaringan Multi-Gigabit
* **Konteks:** Anda memimpin tim arsitektur mesin *telemetry processing* (10 Juta pesan/detik). Sistem menerima paket biner UDP berukuran 1500 byte, mengekstrak field string nama metrik, me-resolve metrik tersebut ke hash table, dan menyimpan agregasi metrik.
* **Gejala:** Profiling CPU menggunakan `perf` menunjukkan latensi p99 melonjak hingga 45ms. Sebanyak 72% total siklus CPU terbuang di dalam rutinitas `malloc`, `free`, dan `strlen` yang dipanggil oleh modul parsing:
  ```c
  // Implementasi parsing legacy
  char *metric_name = malloc(token_len + 1);
  memcpy(metric_name, packet_payload + offset, token_len);
  metric_name[token_len] = '\0';
  metric_table_lookup(metric_name); // lookup membutuhkan string null-terminated
  free(metric_name);
  ```
* **Pertanyaan Diagnostik:**
  1. Rancang arsitektur refaktorisasi ke model *zero-copy processing* menggunakan primitif *String View/Slice* (`{const char *ptr, size_t len}`).
  2. Bagaimana Anda memodifikasi fungsi hashing dan modul hash table (`metric_table_lookup`) agar dapat beroperasi langsung pada *read-only un-terminated slice* tanpa alokasi heap dan tanpa mutasi byte stream asli?
  3. Jelaskan estimasi perbaikan performa cache ($L1/L2$) dan eliminasi *TLB thrashing* dari perubahan arsitektur tersebut!

---

### Skenario B: Kerusakan Data (*Data Corruption*) & Heisenbug pada *Ring Buffer Shared Memory* Multi-Thread
* **Konteks:** Sistem perdagangan frekuensi tinggi (*High-Frequency Trading*) menggunakan *lock-free ring buffer* berbasis *Shared Memory* (`mmap` antar proses) untuk mentransmisikan *order-book updates*. Modul pemrosesan hilir mengeksekusi parsing pesan menggunakan pointer langsung ke dalam ring buffer:
  ```c
  void process_order(RingBuffer *rb) {
      const char *raw_msg = ring_buffer_peek(rb);
      // Parsing in-place:
      // Pengembang mengubah spasi pembatas menjadi '\0' untuk menggunakan atoi() dan strcmp()
      char *delimiter = strchr(raw_msg, ' ');
      *delimiter = '\0'; // In-place mutation
      
      uint64_t order_id = strtoull(raw_msg, NULL, 10);
      // Lanjutkan eksekusi...
      *delimiter = ' '; // Mengembalikan delimiter
      ring_buffer_advance(rb);
  }
  ```
* **Gejala:** Di bawah beban transmisi tinggi, terjadi anomali transmisi di mana sistem analitik membaca pesan yang rusak (*corrupted payload*), parser crash secara sporadis (*SIGSEGV*), dan terjadi kegagalan audit data.
* **Pertanyaan Diagnostik:**
  1. Identifikasi *race condition* dan *memory hazard* yang terjadi jika produsen (*producer process*) atau thread auditor lain membaca segmen ring buffer tersebut saat mutasi in-place `*delimiter = '\0'` sedang berlangsung!
  2. Jelaskan bahaya *speculative execution*, *compiler reordering*, dan kebutuhan *memory barriers* terkait mutasi langsung pada buffer bersama (*shared memory*).
  3. Rancang strategi parsing tanpa mutasi (*mutation-free parsing*) menggunakan parser berbasis *cursor arithmetic* dan konversi integer adaptif (seperti parsing manual atau `fast_float`/`from_chars` idiom) yang beroperasi langsung pada batas `[start, end)`.

---

### Skenario C: Dilema Desain ABI: Fat Pointer Slice vs C-String Null-Terminated
* **Konteks:** Tim infrastruktur Anda sedang membangun *high-performance system library* modular dalam C yang akan digunakan sebagai fondasi backend database relasional baru. Modul ini menyediakan operasi dasar manipulasi teks: pemotongan (*slicing*), penggabungan (*concatenation*), *search*, dan serialisasi.
* **Pertukaran (*Trade-Off*):**
  * **Opsi 1:** Menggunakan *Zero-Copy Fat Pointer* (struktural: `typedef struct { const char *data; size_t len; } StringView;`).
  * **Opsi 2:** Menggunakan standar tradisional C *Null-Terminated String* (`const char *str`).
* **Pertanyaan Diagnostik:**
  1. Evaluasi kedua pendekatan dari sudut pandang *ABI compatibility*, biaya pemanggilan fungsi (*passing by value* struct vs *scalar register passing* pada System V AMD64 ABI), dan potensi *memory footprint* jika jutaan *slice* disimpan di dalam array pada memori utama!
  2. Bagaimana Anda menyelesaikan batasan Opsi 1 saat harus berinteraksi dengan API POSIX kernel (seperti `open(const char *path, ...)` atau `unlink(...)`) yang secara ketat mewajibkan terminator null tanpa mengorbankan integritas *zero-copy* sistem internal?
  3. Rancang pola kompromi (*hybrid pattern*) yang digunakan oleh sistem skala produksi (misalnya: *Small String Optimization* (SSO) atau *String with Inline Capacity*) yang memadukan keamanan batas (*bounds safety*) dengan efisiensi interop C-string.

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Throughput Zero-Copy HTTP/1.1 Protocol Header & Query Parameter Parser

#### 1. Deskripsi Masalah
Dalam rekayasa sistem berkecepatan tinggi (*event-driven web engines*), operasi parsing teks HTTP tidak boleh membebani heap memory manager (`malloc`/`free`) atau melakukan mutasi pada buffer I/O soket yang diterima. Tugas Anda adalah membangun pustaka parser HTTP/1.1 *zero-copy* berspesifikasi tinggi yang membedah *Request Line* dan *Headers* menjadi representasi struktural berbasis *read-only slices*.

#### 2. Kebutuhan Teknis (*Technical Requirements*)
1. **Definisi Struktur Slice:**
   Implementasikan tipe data dasar:
   ```c
   typedef struct {
       const char *ptr;
       size_t len;
   } str_view_t;
   ```
2. **Definisi Struktur Request:**
   Parser harus memetakan seluruh metadata request ke dalam struktur:
   ```c
   #define MAX_HEADERS 64

   typedef struct {
       str_view_t name;
       str_view_t value;
   } http_header_t;

   typedef struct {
       str_view_t method;
       str_view_t path;
       str_view_t query_string; // Opsional (jika ada '?', kosongkan jika tidak)
       int http_major;
       int http_minor;
       http_header_t headers[MAX_HEADERS];
       size_t num_headers;
       str_view_t body;
   } http_request_t;
   ```
3. **Fungsi Inti Parser:**
   ```c
   int http_parse_request(const char *raw_buf, size_t buf_len, http_request_t *out_req);
   ```
   * Fungsi mengembalikan `0` jika parsing sukses.
   * Mengembalikan `-1` jika sintaks HTTP cacat (*malformed*).
   * Mengembalikan `1` jika buffer tidak lengkap (*partial/incomplete*, membutuhkan operasi read soket lebih lanjut).
4. **Fasilitas Lookup & Perbandingan *Zero-Copy*:**
   * Bangun fungsi pembantu:
     ```c
     bool str_view_equals_ci(str_view_t a, const char *null_term_b);
     ```
     Melakukan komparasi *case-insensitive* tanpa mutasi dan tanpa alokasi baru (penting untuk nama header HTTP seperti `Content-Type` vs `content-type`).
   * Bangun fungsi ekstraksi query parameter:
     ```c
     bool http_get_query_param(str_view_t query_string, const char *key, str_view_t *out_val);
     ```

#### 3. Batasan Operasional (*Hard Constraints*)
* **Zero Allocation:** Terlarang menggunakan `malloc`, `calloc`, `realloc`, `strdup`, atau *memory allocation routines* lainnya di seluruh siklus hidup parser.
* **Zero Mutation:** Parameter `raw_buf` bersifat `const char *`. Tidak diizinkan menulis nilai `\0` ke dalam buffer untuk mempermudah parsing.
* **Deterministic Bounds Checking:** Setiap iterasi pembacaan buffer harus terlindungi dari *buffer over-read*. Tidak boleh ada dereferensi pointer yang melampaui `raw_buf + buf_len`.
* **Standard Compliant:** Kode harus *clean* dari *Undefined Behavior*, dikompilasi dengan bendera:
  `-Wall -Wextra -Werror -Wpedantic -std=c11 -fsanitize=address,undefined`.

#### 4. Expected Output & Kasus Verifikasi
Implementasikan file verifikasi sederhana yang menguji:
1. Parsing request valid:
   ```http
   GET /api/v1/metrics?node=alpha&interval=60s HTTP/1.1\r\n
   Host: system.internal\r\n
   User-Agent: TelemetryProbe/2.0\r\n
   Accept: */*\r\n
   \r\n
   ```
2. Pengecekan parsing parsial (*partial stream injection* byte-per-byte).
3. Pengecekan *resilience* terhadap skenario *buffer overrun injection* (request line sangat panjang tanpa `\r\n` atau melampaui `buf_len`).
4. Output verifikasi harus mencetak nilai seluruh slice menggunakan penentu format precision spesifik: `printf("%.*s", (int)view.len, view.ptr);`.

---

## 5. Knowledge Check & Checklist

Gunakan checklist ini untuk mengukur kesiapan teknis sebelum melangkah ke topik memori tingkat lanjut.

### Saya harus memahami:
- [ ] Mekanisme internal kompilator saat melakukan *decay* dari tipe `T[N]` ke `T*`, serta perkecualiannya pada operator `sizeof` dan address-of `&`.
- [ ] Perbedaan fisik layout memori antara *contiguous flat multidimensional array* dengan *ragged array-of-pointers*, serta pengaruhnya pada *cache line utilization* (spasial dan temporal).
- [ ] Semantika kata kunci `restrict` pada pointer array, bagaimana pointer aliasing menghambat vektorisasi otomatis (*auto-vectorization*), dan mengapa `memcpy` memanfaatkannya.
- [ ] Bahaya desimal dan performa dari konvensi *sentinel-terminated string* (`\0`) pada sistem komputasi berlatensi ultra-rendah.
- [ ] Aturan perataan memori (*memory alignment constraints*) arsitektur CPU dan mengapa memetakan buffer byte sembarangan (`uint8_t*`) ke pointer tipe skalar/struktur adalah *Undefined Behavior*.

### Saya tidak perlu menghafal:
- [ ] Setiap variasi fungsi usang pustaka string C standar yang tidak aman (seperti `gets`, `strcat`, `rindex`).
- [ ] Implementasi instruksi assembly mikro internal arsitektur tertentu untuk `rep movsb` vs AVX-512 copy routines (cukup pahami kontrak abstraksinya).
- [ ] Nilai numerik tabel ASCII di luar karakter kontrol fundamental (`\0`, `\r`, `\n`, spasi).

### Saya harus bisa melakukan:
- [ ] Merancang dan mengimplementasikan abstraksi *String View / Slice* (`{ptr, len}`) yang aman, read-only, dan berkinerja tinggi dalam C tanpa alokasi dinamis.
- [ ] Memvalidasi dan mendeteksi potensi *out-of-bounds reading/writing* pada array menggunakan AddressSanitizer (`-fsanitize=address`) dan static analysis (`-fanalyzer`).
- [ ] Menulis algoritma pemindaian buffer dua arah (*bidirectional scanning*) tanpa memicu *integer underflow* pada tipe data tanpa tanda (*unsigned* seperti `size_t`).
- [ ] Melakukan deserialisasi biner dari buffer I/O secara aman menggunakan `memcpy` teroptimasi kompilator untuk menghindari *alignment fault* pada arsitektur non-x86.
- [ ] Menulis parser protokol berbasis teks berkecepatan tinggi yang sepenuhnya bersifat *non-destructive* (tidak mengubah buffer sumber) dan deterministik.