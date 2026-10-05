# BAB-08-Network-Resiliency-Offline-First-Architecture-dan-Secur: Quiz, Challenge, & Knowledge Check

Uji pemahaman komprehensif, evaluasi arsitektur, dan implementasi praktis terkait ketahanan jaringan (Network Resiliency), arsitektur Offline-First (Local-First Synchronization & Conflict Resolution), serta hardening keamanan (Mobile Security, SSL Pinning, Biometric Authentication, Keystore/Keyring) pada aplikasi React Native level enterprise.

---

## Bagian 1: 5 Pertanyaan Fundamental (Basic Questions)

### Soal 1: NetInfo vs Active Ping
**Pertanyaan:** Mengapa mendengarkan event konektivitas melalui `@react-native-community/netinfo` saja tidak menjamin bahwa request HTTP/GraphQL ke backend server pasti berhasil dieksekusi?
<details>
<summary>Jawaban & Analisis Teknis</summary>

`NetInfo` hanya mendeteksi interface level OS (apakah perangkat terhubung ke Wi-Fi AP, Cellular Radio, atau Ethernet) serta flags default OS (`isInternetReachable`). Kondisi ini rentan terhadap fenomena **Captive Portal** (misal Wi-Fi hotel/kafe yang memerlukan login web), **DNS Blackhole**, dan **High-Latency Packet Loss / Flaky Network** di mana sinyal radio aktif namun gateway tidak dapat merutekan paket ke edge server tujuan.

**Solusi Arsitektural:**
Kombinasikan status `NetInfo` dengan mekanisme **Healthcheck / Heartbeat Probe** (active light ping ke endpoint HTTP 204 seperti `GET /health` atau probe Cloudflare/AWS) sebelum memutuskan konektivitas jaringan benar-benar *reachable*.
</details>

---

### Soal 2: AsyncStorage vs SecureStore / Keychain
**Pertanyaan:** Mengapa menyimpan JWT Access Token atau Refresh Token di `@react-native-async-storage/async-storage` sangat dilarang dalam aplikasi finansial dan enterprise? Di manakah lokasi penyimpanan yang tepat?
<details>
<summary>Jawaban & Analisis Teknis</summary>

`AsyncStorage` menyimpan data dalam bentuk unencrypted key-value plain text:
- Pada **Android**, data tersimpan di SQLite database atau XML file di dalam direktori internal sandbox app (`/data/data/<package_name>/databases/RKStorage.db`). Pada perangkat yang di-root atau melalui backup ADB (`adb backup`), file ini dapat diekstraksi tanpa proteksi.
- Pada **iOS**, data disimpan di file serialisasi plist tanpa enkripsi hardware-backed.

**Solusi Standar:**
Gunakan hardware-backed storage via **Android Keystore System** (dengan enkripsi AES-GCM 256) dan **iOS Keychain Services** (Secure Enclave). Di React Native, gunakan library seperti `react-native-keychain` atau `expo-secure-store` dengan flag akses `kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly` dan `BIOMETRIC_ANY`.
</details>

---

### Soal 3: Idempotency Key pada Network Mutation
**Pertanyaan:** Jelaskan fungsi dari header `Idempotency-Key` (UUID v4) dalam transaksi mutasi saat aplikasi mengalami network drop atau timeout di tengah proses request!
<details>
<summary>Jawaban & Analisis Teknis</summary>

Ketika mobile client mengirim HTTP `POST /api/v1/payments/checkout`, jika koneksi terputus saat request sedang diproses di server atau saat response dalam perjalanan pulang, client akan menerima `SocketTimeoutException` atau `Network Error`. Tanpa mekanisme khusus, retry otomatis oleh client akan memicu *double charge* (duplikasi transaksi).

Dengan menyertakan header `Idempotency-Key: <unique-uuid>`, backend (biasanya memanfaatkan Redis locking / table idempotency) memeriksa apakah kunci tersebut pernah diterima:
1. Jika sedang diproses: return status `409 In Progress`.
2. Jika sudah selesai diproses: return cached response dari transaksi pertama tanpa mengeksekusi mutasi ulang pada database bisnis.
3. Jika belum pernah ada: proses transaksi secara normal dan simpan statusnya.
</details>

---

### Soal 4: Optimistic UI Updates vs Pessimistic UI Updates
**Pertanyaan:** Apa perbedaan fundamental antara Optimistic UI dan Pessimistic UI dalam konteks arsitektur offline-first, dan apa konsekuensinya terhadap state rollback ketika mutasi ditolak oleh server?
<details>
<summary>Jawaban & Analisis Teknis</summary>

- **Pessimistic UI:** Aplikasi menampilkan loading indicator (spinner/skeleton) dan menahan perubahan state lokal hingga server mengembalikan respons `200 OK`. Jika offline atau flaky, interaksi pengguna terblokir.
- **Optimistic UI:** State lokal (Redux/Zustand/TanStack Cache) langsung di-update seketika saat user melakukan aksi, mengasumsikan mutasi akan sukses, sehingga UI terasa instan (0ms latency).

**Konsekuensi Rollback:**
Optimistic UI mewajibkan adanya snapshot rollback cache (`onMutate` -> context -> `onError`). Jika server mengembalikan `4xx/5xx` atau conflict validation:
1. State lokal harus direvert kembali ke snapshot sebelum mutasi.
2. User harus diberikan feedback kontekstual (misal toast banner dengan tombol "Retry" atau "Dismiss").
3. Local optimistic ID (misal `temp_uuid`) harus dibersihkan agar tidak mereferensikan entitas yang gagal dibuat di persistent local DB.
</details>

---

### Soal 5: Konsep SSL/TLS Pinning
**Pertanyaan:** Apa kerentanan yang dicegah oleh SSL Pinning pada mobile app, dan apa risiko operasional yang harus dimitigasi saat melakukan certificate pinning?
<details>
<summary>Jawaban & Analisis Teknis</summary>

**Kerentanan yang Dicegah:**
Mencegah serangan **Man-in-the-Middle (MITM)**. Penyerang yang menginstal Root Certificate palsu ke dalam user trust store (misal via proxy tools seperti Charles Proxy, Burp Suite, atau malware di perangkat yang di-root/jailbreak) tidak akan bisa mendekripsi payload HTTPS aplikasi, karena aplikasi hanya mempercayai hash Public Key SubjectPublicKeyInfo (SPKI) tertentu yang di-*pin* di binary aplikasi.

**Risiko Operasional & Mitigasi:**
- **Sertifikat Kedaluwarsa (App Brick):** Jika sertifikat TLS di server dirotasi tanpa pembaruan hash pin di mobile app, seluruh request network akan di-reject (SSL Handshake Exception), melumpuhkan aplikasi secara permanen hingga user melakukan update via App Store / Play Store.
- **Mitigasi:** Gunakan **Public Key Pinning (SPKI sha256)** alih-alih Leaf Certificate pinning, dan wajib menyertakan minimal 1 Backup Pin (cadangan public key intermediate CA atau CSR periode berikutnya) serta backup mechanism via dynamic remote config yang terlindungi signature kriptografis.
</details>

---

## Bagian 2: 5 Pertanyaan Menengah (Intermediate Questions)

### Soal 6: Outbox Pattern dan Transactional Queue pada Local-First
**Pertanyaan:** Bagaimana arsitektur persistent queue (Outbox Pattern) diimplementasikan di React Native untuk menjamin operasi mutasi offline dieksekusi secara FIFO, atomik, dan tahan terhadap crash aplikasi?
<details>
<summary>Jawaban & Analisis Teknis</summary>

Outbox Pattern pada mobile client memisahkan antara *UI Action Dispatch* dengan *Network Transport Execution*:
1. **Local Atomic Transaction:** Ketika user melakukan aksi (misal `UPDATE_INVENTORY`), perubahan data bisnis disimpan ke database lokal (WatermelonDB / SQLite / Nitro SQLite) bersamaan dengan record antrean baru di tabel `mutation_outbox` dalam satu transaksi ACID lokal:
   ```sql
   BEGIN TRANSACTION;
   UPDATE items SET stock = stock - 1 WHERE id = 'item_101';
   INSERT INTO mutation_outbox (id, endpoint, method, payload, created_at, status, retry_count)
   VALUES ('uuid_1', '/api/v1/stock/decrement', 'POST', '{"id":"item_101","qty":1}', 1720000000, 'PENDING', 0);
   COMMIT;
   ```
2. **Background Sync Worker / Queue Processor:** Sebuah background service atau event listener memproses antrean berstatus `PENDING` secara FIFO:
   - Ambil job teratas, tandai status `PROCESSING`.
   - Eksekusi HTTP call dengan `Idempotency-Key: uuid_1`.
   - Jika sukses (HTTP 200/201): tandai `COMPLETED` atau hapus dari outbox.
   - Jika flaky error (Network timeout, 502/503): terapkan **Exponential Backoff with Jitter** dan kembalikan ke `PENDING`.
   - Jika client-side crash terjadi di tengah jalan, status yang tersimpan di disk memastikan queue resume saat app cold-boot tanpa ada data yang hilang.
</details>

---

### Soal 7: Conflict Resolution Strategy (LWW vs CRDTs vs Vector Clocks)
**Pertanyaan:** Bandingkan strategi resolusi konflik *Last-Write-Wins (LWW)* dengan *Conflict-free Replicated Data Types (CRDTs)* pada sinkronisasi multi-device offline. Kapan LWW menyebabkan *data loss*, dan kapan CRDT wajib digunakan?
<details>
<summary>Jawaban & Analisis Teknis</summary>

**1. Last-Write-Wins (LWW):**
- Menggunakan timestamp (`updated_at`) untuk menentukan record mana yang menimpa record lain.
- **Kelemahan & Data Loss:** Sangat rentan terhadap **Clock Drift** pada perangkat mobile (waktu jam user tidak sinkron dengan NTP server). Jika User A offline pada jam 10:00 dan mengedit paragraph 1, lalu User B online pada jam 10:05 mengedit paragraph 2, jika User A kemudian online dengan timestamp yang salah (misal jam 10:10), mutasi User A akan menimpa seluruh dokumen User B, menghapus perubahan User B secara permanen (*blind overwrites*).

**2. CRDTs (Conflict-free Replicated Data Types):**
- Struktur data matematika yang secara deterministik menggabungkan (merge) concurrent writes tanpa koordinasi terpusat (contoh: Yjs, Automerge, state-based PN-Counters, text-editing RGA/Fugue).
- **Penggunaan Wajib:** Aplikasi kolaboratif realtime/offline (rich text editor, kanban board, collaborative drawing, shared shopping carts) di mana perubahan granular pada field yang sama harus digabungkan tanpa kehilangan data antar kontributor.
</details>

---

### Soal 8: TanStack Query (React Query) Offline Persister & Mutation Resume
**Pertanyaan:** Jelaskan mekanisme kerja `createSyncStoragePersister` / `createAsyncStoragePersister` bersama `onlineManager` pada `@tanstack/react-query` v5 dalam menangani dehidrasi cache dan resuming mutation queue saat cold restart aplikasi!
<details>
<summary>Jawaban & Analisis Teknis</summary>

1. **Hydration & Dehydration Lifecycle:**
   - Saat runtime, `queryClient` menyimpan query cache dan mutation cache di memory.
   - `persistQueryClient` mendehidrasi state in-memory ke format JSON dan menyimpannya ke persistent storage (misal MMKV via `createSyncStoragePersister` yang jauh lebih cepat dibanding AsyncStorage).
   - Saat aplikasi cold restart tanpa koneksi internet, persister me-rehidrasi cache dari storage ke memory, sehingga UI langsung menampilkan data snapshot terakhir (stale data) tanpa blank screen.

2. **Mutation Queue Resumption:**
   - TanStack Query v5 menyediakan konfigurasi `resumePausedMutations()`.
   - Ketika mutation di-trigger saat offline, mutation tersebut masuk ke status `paused` jika fungsi `mutationFn` mendeteksi `onlineManager.isOnline() === false`.
   - Jika app ditutup paksa (killed) lalu dibuka kembali, persister memulihkan paused mutations dari disk. Begitu `onlineManager.setOnline(true)` terpanggil via NetInfo listener, TanStack Query otomatis melanjutkan eksekusi mutation queue tersebut secara berurutan sesuai urutan pendaftaran.
</details>

---

### Soal 9: Memory vs Disk Encryption pada MMKV & SQLite (SQLCipher)
**Pertanyaan:** Mengapa enkripsi di level database file (misal SQLCipher dengan AES-256) tetap rentan terhadap memory inspection jika cryptographic key disimpan secara statis di JavaScript bundle? Bagaimana arsitektur manajemen kunci yang aman?
<details>
<summary>Jawaban & Analisis Teknis</summary>

**Kelemahan Static Key:**
Jika encryption key di-hardcode di file `.env` atau JavaScript bundle (contoh: `const DB_KEY = "my-secret-key"`), bundle tersebut dapat dengan mudah diekstrak menggunakan reverse-engineering tools seperti `jadx`, `apktool`, atau memeriksa `index.android.bundle`. Penyerang dapat langsung membaca key dan mendekripsi database SQLCipher/MMKV dari filesystem.

**Arsitektur Secure Key Management:**
1. **Dynamic Key Generation:** Saat app pertama kali diinstal (first launch), generate kunci acak berkekuatan tinggi (kriptografis 256-bit secure random bytes).
2. **Hardware Security Module Storage:**
   - Simpan kunci tersebut ke dalam **Android Keystore** (menggunakan `KeyGenParameterSpec.Builder` dengan flag `PURPOSE_ENCRYPT | PURPOSE_DECRYPT`) dan **iOS Keychain** (`kSecAttrAccessibleAfterFirstUnlock`).
3. **Runtime Decryption:** Saat inisialisasi database di C++ native bridge (Nitro / JSI), ambil master key langsung dari hardware secure enclave via native module tanpa pernah mengekspos raw encryption key ke JavaScript thread secara plain text.
</details>

---

### Soal 10: Jailbreak & Root Detection Evasion
**Pertanyaan:** Mengapa pengecekan jailbreak/root sederhana berbasis file path (misal mengecek keberadaan `/system/bin/su` atau `/Applications/Cydia.app`) mudah di-bypass menggunakan Frida atau Magisk DenyList, dan bagaimana strategi *Defense-in-Depth* untuk memitigasinya?
<details>
<summary>Jawaban & Analisis Teknis</summary>

**Mekanisme Bypass Frida/Magisk:**
Framework hooking dinamis seperti **Frida** atau kernel-level root hiding seperti **Magisk Zygisk / Shamiko** dapat meng-intersep panggilan sistem:
- Hooking fungsi `java.io.File.exists()` atau system call C `access()` / `stat()`, memanipulasi return value menjadi `false` ketika aplikasi memeriksa path `su`, `busybox`, atau `Cydia`.
- Menginjeksi library di level Zygote sehingga isolated process tidak memiliki trace file root sama sekali.

**Strategi Defense-in-Depth:**
1. **Multi-layer Heuristics:**
   - Periksa read-only filesystem mount flags (apakah `/system` dapat di-remount sebagai read-write).
   - Deteksi port debugging ADB yang terbuka secara tidak wajar atau port server Frida default (`27042`).
   - Periksa `test-keys` pada `Build.TAGS` di Android.
2. **Native C/C++ Implementation:** Implementasikan deteksi root di native code (via JNI/NDK) dengan obfuscation (OLLVM), bukan di layer JavaScript React Native yang rentan di-patch.
3. **Attestation API:** Gunakan hardware-backed attestation resmi: **Google Play Integrity API** (Android) dan **DeviceCheck / App Attest API** (iOS). Token yang di-generate divalidasi secara kriptografis di backend server, bukan diverifikasi lokal di sisi client.
</details>

---

## Bagian 3: 3 Skenario Kasus Nyata Produksi (Real-World Production Scenarios)

### Skenario 1: Post-Mortem "The $120,000 Ghost Order Duplication"
**Konteks Masalah:**
Aplikasi e-commerce logistik B2B mengalami lonjakan request berulang saat armada kurir mengantarkan barang di area remote pedesaan (sinyal 3G flaky). Kurir mengklik tombol "Selesaikan Pengiriman & Bayar COD", namun UI freeze karena latency 15 detik. Kurir menekan tombol berulang kali (4-8 kali). Ketika koneksi pulih, backend memproses 4 transaksi terpisah yang memotong deposit agen hingga minus $120,000 secara kumulatif.

**1. Analisis Akar Masalah (Root Cause):**
- Tombol aksi tidak di-*disable* secara debounce/throttle saat mutation berstatus `isPending`.
- Client tidak mengimplementasikan unique `Idempotency-Key` di header transaksi per-sesi checkout.
- Tidak ada database outbox lokal yang mendeduplikasi aksi berbasis hash pesanan lokal.

**2. Solusi Rekayasa Arsitektur:**
```typescript
// Implementasi resilient client mutation dengan Idempotency & Lock Guard
import { useState, useRef } from 'react';
import NetInfo from '@react-native-community/netinfo';
import { mmkvStorage } from '../storage/mmkv';

interface CheckoutPayload {
  orderId: string;
  amount: number;
  paymentMethod: 'COD' | 'BALANCE';
}

export function useResilientCheckout() {
  const [isProcessing, setIsProcessing] = useState(false);
  const activeLockRef = useRef<boolean>(false);

  const executeCheckout = async (payload: CheckoutPayload) => {
    // 1. In-memory Atomic Guard (mencegah double tap fisik)
    if (activeLockRef.current || isProcessing) {
      console.warn('[Checkout] Action locked. Duplicate execution prevented.');
      return;
    }

    activeLockRef.current = true;
    setIsProcessing(true);

    try {
      // 2. Stable Idempotency Key (persist per unique order attempt)
      const idempotencyStorageKey = `idempotency_checkout_${payload.orderId}`;
      let idempotencyKey = mmkvStorage.getString(idempotencyStorageKey);
      
      if (!idempotencyKey) {
        idempotencyKey = `${payload.orderId}-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
        mmkvStorage.set(idempotencyStorageKey, idempotencyKey);
      }

      // 3. Network pre-flight check
      const netState = await NetInfo.fetch();
      if (!netState.isConnected) {
        // Enqueue ke Persistent Outbox SQLite/MMKV untuk dieksekusi oleh Background Sync
        await enqueueOutboxMutation({
          id: idempotencyKey,
          endpoint: '/api/v1/orders/complete',
          payload,
        });
        showToast('Tersimpan di antrean offline. Akan disinkronkan otomatis saat ada sinyal.');
        return;
      }

      // 4. Remote Execution dengan strict Timeout & Idempotency Header
      const response = await fetchWithTimeout('https://api.logistik.com/api/v1/orders/complete', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Idempotency-Key': idempotencyKey,
        },
        body: JSON.stringify(payload),
        timeoutMs: 10000,
      });

      if (response.ok) {
        // Hapus idempotency token setelah konfirmasi final
        mmkvStorage.delete(idempotencyStorageKey);
        showToast('Pengiriman berhasil diselesaikan.');
      } else {
        throw new Error(`Server returned status: ${response.status}`);
      }
    } catch (error: any) {
      console.error('[Checkout Error]', error.message);
      // Tangani fallback: jangan izinkan user re-submit tanpa konfirmasi server
      showRetryModal(payload);
    } finally {
      activeLockRef.current = false;
      setIsProcessing(false);
    }
  };

  return { executeCheckout, isProcessing };
}
```

---

### Skenario 2: Insiden SSL Pinning Brick Saat Rotasi Sertifikat Cloudflare
**Konteks Masalah:**
Tim DevOps melakukan pembaharuan sertifikat edge Cloudflare dari DigiCert ke Let's Encrypt karena jadwal tahunan. Begitu sertifikat baru aktif, 450,000 pengguna aktif aplikasi React Native di iOS dan Android mendapati aplikasi mereka blank total dengan error `javax.net.ssl.SSLPeerUnverifiedException` dan `NSURLErrorDomain -1202`.

**1. Analisis Akar Masalah (Root Cause):**
- Mobile app mengonfigurasi certificate pinning menggunakan hash SHA-256 dari **Leaf Certificate** tunggal yang hardcoded di library pinning (`react-native-ssl-pinning` / network security config).
- Tidak ada cadangan **Backup Pins** untuk Intermediate CA atau Public Key CSR berikutnya.
- Mobile client tidak memiliki bypass contingency plan yang tersertifikasi kriptografis.

**2. Solusi Rekayasa & Best Practice:**
- **Pin pada SubjectPublicKeyInfo (SPKI):** Lakukan pinning pada hash public key, bukan leaf certificate, sehingga saat sertifikat di-*renew* dengan private key yang sama, pin tetap valid.
- **Konfigurasi Android Network Security Config dengan Backup Pin:**
```xml
<!-- android/app/src/main/res/xml/network_security_config.xml -->
<?xml version="1.0" encoding="utf-8"?>
<network-security-config>
    <domain-config>
        <domain includeSubdomains="true">api.perusahaan.com</domain>
        <pin-set expiration="2027-01-01">
            <!-- Primary Pin: Current Production SPKI -->
            <pin digest="SHA-256">WoiWRbUb2FyPmO0XTGf8YZ3YTJyMD+W5RdyShUhG3xU=</pin>
            <!-- Backup Pin 1: Disaster Recovery Intermediate / Secondary Keypair -->
            <pin digest="SHA-256">k2ErWTvE4JVbvQC9N05gNZysUsub9YSQKFsRqABZJCo=</pin>
            <!-- Backup Pin 2: Root CA Fallback Pin -->
            <pin digest="SHA-256">r/mIkG3eEpVdm+u/ko/cwxzOMo1bk4TyHIlByibiA5E=</pin>
        </pin-set>
    </domain-config>
</network-security-config>
```

---

### Skenario 3: Penetrasi Reverse Engineering & Token Leakage via Memory Dump
**Konteks Masalah:**
Aplikasi fintech perbankan menemukan adanya request liar ke private API transfer dana dari IP luar negeri. Investigasi menunjukkan penyerang membeli HP Android second-hand dari pengguna, melakukan dump memori RAM menggunakan Frida (`frida-memory-dump`), dan berhasil mengekstraksi refresh token JWT berumur panjang (30 hari) yang disimpan plain text di memori instance singleton Axios.

**1. Analisis Akar Masalah (Root Cause):**
- Refresh token disimpan dalam global JavaScript variable/closure yang tidak pernah di-purge dari heap memory.
- Token JWT tidak diikat dengan hardware footprint (device fingerprinting/binding).
- Refresh token tidak menerapkan mekanisme **Token Rotation** (Refresh Token Reuse Detection).

**2. Langkah Mitigasi Arsitektur:**
1. **Hardware-Bound Token Storage:** Simpan Refresh Token murni di Secure Enclave / Android Keystore dengan atribut `setUserAuthenticationRequired(true)` sehingga pembacaan token wajib diautentikasi biometrik pengguna.
2. **Refresh Token Rotation (RTR):** Setiap kali endpoint `/auth/refresh` dipanggil, server wajib menginvalidasi refresh token lama dan menerbitkan pasangan access token + refresh token yang baru. Jika token lama digunakan dua kali, server otomatis memblokir seluruh sesi user terkait.
3. **Memory Scrubbing & Root Protection:** Gunakan code obfuscation (ProGuard/R8 + DexGuard) serta aktifkan flag `android:hasFragileUserData="false"` dan blokir screen capture/dump via `react-native-prevent-screenshot-ios-android` (`FLAG_SECURE`).

---

## Bagian 4: Practical Chapter Challenge: Resilient Offline-First Sync Engine

### Objektif Tantangan
Rancang dan implementasikan sebuah modul TypeScript independen bernama **`ResilientSyncEngine`** untuk aplikasi field inspector di React Native yang bertugas mencatat laporan inspeksi gedung saat berada di basement tanpa sinyal.

### Spesifikasi Kebutuhan Teknis:
1. **Persistent Local Outbox:** Menggunakan SQLite (atau abstraksi key-value atomik) untuk menyimpan mutasi pending.
2. **State Machine Status:** Tiap job di outbox harus memiliki state: `IDLE` -> `ENQUEUED` -> `PROCESSING` -> `SUCCESS` | `FAILED_RETRYABLE` | `DEAD_LETTER`.
3. **Exponential Backoff with Full Jitter:** Formula waktu tunggu:
   $$\text{Sleep} = \text{random}(0, \min(M, B \times 2^{\text{retryCount}}))$$
   dengan $B = 1000\text{ms}$ dan $M = 30000\text{ms}$.
4. **Network Reconnection Trigger:** Sinkronisasi otomatis aktif seketika saat NetInfo mendeteksi koneksi pulih.
5. **Concurrent Lock:** Mencegah 2 thread sync berjalan bersamaan (*race condition prevention*).

---

### Implementasi Referensi Solusi (`ResilientSyncEngine.ts`):

```typescript
import NetInfo, { NetInfoState } from '@react-native-community/netinfo';

export type JobStatus = 'IDLE' | 'ENQUEUED' | 'PROCESSING' | 'SUCCESS' | 'FAILED_RETRYABLE' | 'DEAD_LETTER';

export interface SyncJob<T = any> {
  id: string; // UUID v4
  endpoint: string;
  method: 'POST' | 'PUT' | 'PATCH';
  payload: T;
  retryCount: number;
  maxRetries: number;
  status: JobStatus;
  lastError?: string;
  createdAt: number;
  updatedAt: number;
}

export interface IStorageAdapter {
  getAllJobs(): Promise<SyncJob[]>;
  saveJob(job: SyncJob): Promise<void>;
  updateJob(job: SyncJob): Promise<void>;
  deleteJob(id: string): Promise<void>;
}

export class ResilientSyncEngine {
  private isSynchronizing: boolean = false;
  private unsubscribeNetInfo: (() => void) | null = null;
  private readonly BASE_DELAY_MS = 1000;
  private readonly MAX_DELAY_MS = 30000;

  constructor(
    private storage: IStorageAdapter,
    private baseUrl: string
  ) {}

  public init(): void {
    // Daftarkan listener konektivitas jaringan
    this.unsubscribeNetInfo = NetInfo.addEventListener((state: NetInfoState) => {
      if (state.isConnected && state.isInternetReachable !== false) {
        console.log('[SyncEngine] Network restored. Triggering processQueue().');
        this.processQueue();
      }
    });
  }

  public destroy(): void {
    if (this.unsubscribeNetInfo) {
      this.unsubscribeNetInfo();
    }
  }

  public async enqueueMutation<T>(endpoint: string, method: 'POST' | 'PUT' | 'PATCH', payload: T): Promise<string> {
    const job: SyncJob<T> = {
      id: this.generateUUID(),
      endpoint,
      method,
      payload,
      retryCount: 0,
      maxRetries: 5,
      status: 'ENQUEUED',
      createdAt: Date.now(),
      updatedAt: Date.now(),
    };

    await this.storage.saveJob(job);
    // Jalankan queue secara asinkron tanpa memblokir pemanggil
    this.processQueue();
    return job.id;
  }

  public async processQueue(): Promise<void> {
    // Concurrency Lock: Cegah overlapping executions
    if (this.isSynchronizing) {
      console.log('[SyncEngine] Queue already processing. Skipping cycle.');
      return;
    }

    const netState = await NetInfo.fetch();
    if (!netState.isConnected || netState.isInternetReachable === false) {
      console.log('[SyncEngine] Device offline. Halting queue.');
      return;
    }

    this.isSynchronizing = true;

    try {
      const allJobs = await this.storage.getAllJobs();
      const pendingJobs = allJobs
        .filter(j => j.status === 'ENQUEUED' || j.status === 'FAILED_RETRYABLE')
        .sort((a, b) => a.createdAt - b.createdAt); // FIFO order

      for (const job of pendingJobs) {
        await this.executeJobWithBackoff(job);
      }
    } finally {
      this.isSynchronizing = false;
    }
  }

  private async executeJobWithBackoff(job: SyncJob): Promise<void> {
    job.status = 'PROCESSING';
    job.updatedAt = Date.now();
    await this.storage.updateJob(job);

    try {
      const response = await fetch(`${this.baseUrl}${job.endpoint}`, {
        method: job.method,
        headers: {
          'Content-Type': 'application/json',
          'Idempotency-Key': job.id,
        },
        body: JSON.stringify(job.payload),
      });

      if (response.ok) {
        job.status = 'SUCCESS';
        await this.storage.deleteJob(job.id);
        console.log(`[SyncEngine] Job ${job.id} synced successfully.`);
      } else if (response.status >= 400 && response.status < 500 && response.status !== 408 && response.status !== 429) {
        // Unrecoverable Client Error (Bad Request, Unauthorized, Unprocessable)
        job.status = 'DEAD_LETTER';
        job.lastError = `HTTP ${response.status}: Client validation failure`;
        await this.storage.updateJob(job);
        console.error(`[SyncEngine] Job ${job.id} marked as DEAD_LETTER.`);
      } else {
        // Server Error (5xx) atau 429 Too Many Requests -> Retryable
        throw new Error(`Transient HTTP Status: ${response.status}`);
      }
    } catch (error: any) {
      job.retryCount += 1;
      job.lastError = error.message || 'Unknown network error';

      if (job.retryCount >= job.maxRetries) {
        job.status = 'DEAD_LETTER';
        console.error(`[SyncEngine] Job ${job.id} reached max retries. Moved to DEAD_LETTER.`);
      } else {
        job.status = 'FAILED_RETRYABLE';
        const delay = this.calculateJitterBackoff(job.retryCount);
        console.warn(`[SyncEngine] Job ${job.id} failed (attempt ${job.retryCount}). Next retry in ${delay}ms.`);
        await this.sleep(delay);
      }

      await this.storage.updateJob(job);
    }
  }

  private calculateJitterBackoff(retryCount: number): number {
    // Formula: Sleep = random(0, min(MAX_DELAY, BASE_DELAY * 2^retryCount))
    const exponentialDelay = Math.min(this.MAX_DELAY_MS, this.BASE_DELAY_MS * Math.pow(2, retryCount));
    return Math.floor(Math.random() * exponentialDelay);
  }

  private sleep(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  private generateUUID(): string {
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
      const r = (Math.random() * 16) | 0;
      const v = c === 'x' ? r : (r & 0x3) | 0x8;
      return v.toString(16);
    });
  }
}
```

---

## Bagian 5: Checklist Pemahaman (Self-Assessment Checklist)

Beri tanda centang $(\checkmark)$ pada daftar di bawah ini untuk mengonfirmasi penguasaan kompetensi arsitektur Bab 08:

- [ ] **Network Resiliency Diagnostics:**
  - Mampu membedakan interface radio connectivity (`NetInfo`) dengan active internet transit reachability (204 ping probe).
  - Memahami cara menangani connection timeout, socket hang up, DNS resolution failure, dan implementasi retry policy berbasis exponential backoff dengan jitter.

- [ ] **Offline-First Data Architecture:**
  - Menguasai implementasi Outbox Pattern untuk menampung mutasi lokal dengan jaminan eksekusi FIFO dan persistent state preservation.
  - Memahami perbedaan tradeoff antara Last-Write-Wins (LWW) dengan CRDTs (Conflict-free Replicated Data Types) saat merge data multi-device.
  - Menguasai integrasi TanStack Query v5 offline storage persister (`createSyncStoragePersister` / MMKV) dan hydration lifecycle.

- [ ] **Idempotency & Safe Mutation:**
  - Mampu merancang header `Idempotency-Key` (UUID) pada setiap request mutasi kritis untuk mencegah duplikasi data saat network flapping.
  - Mengimplementasikan optimistic UI updates beserta snapshot rollback mechanism (`onMutate` -> `onError`) yang stabil.

- [ ] **Mobile Hardening & Security:**
  - Mengetahui batas keamanan `AsyncStorage` dan mampu menggantikannya dengan `react-native-keychain` / `expo-secure-store` yang terintegrasi dengan hardware Keystore / Keychain (Secure Enclave).
  - Menguasai konsep dan implementasi SSL/TLS Public Key Pinning (SPKI SHA-256) serta mitigasi risiko brick melalui backup pin.
  - Memahami teknik mitigasi root/jailbreak detection evasion, hooking Frida, serta implementasi Play Integrity API / DeviceCheck di production.
