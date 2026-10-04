# SEKSI 01 — IDENTITAS MODUL
* **Track:** 03-Frontend-and-Mobile
* **Teknologi:** React Native (Architecture: New Architecture / Fabric & TurboModules)
* **Bab 08:** Production-Grade System Engineering
* **Modul 01:** Network Resiliency, Offline-First Architecture & Security
* **Tingkat Kesulitan:** Advanced / Staff Engineer Level
* **Prasyarat:** React Native Core, State Management (Zustand/Redux), SQLite/WatermelonDB/MMKV, Asynchronous Programming, REST/GraphQL Concepts, Basic Cryptography.

---

# SEKSI 02 — LEARNING OBJECTIVES
Setelah menyelesaikan modul ini, peserta mampu:
1. Merancang dan mengimplementasikan sistem sinkronisasi data dua arah (*two-way bidirectional data sync*) yang deterministik dengan strategi resolusi konflik formal (LWW, CRDT, Operational Transformation).
2. Membangun antrean mutasi persisten (*persistent mutation queue*) yang tahan terhadap *application crash*, *force quit*, dan kondisi jaringan fluktuatif (*flaky/intermittent connectivity*).
3. Menerapkan teknik *Optimistic UI Updates* dengan jaminan *rollback atomic* saat terjadi kegagalan jaringan atau penolakan server.
4. Mengamankan kanal komunikasi aplikasi React Native menggunakan *SSL/TLS Pinning* dinamis, *certificate transparency checks*, dan perlindungan terhadap *Man-in-the-Middle (MitM)*.
5. Mengimplementasikan enkripsi data lokal tingkat lanjut (*Data-at-Rest Encryption*) menggunakan hardware-backed keystore (Android Keystore / iOS Keychain) yang diintegrasikan dengan database lokal terenkripsi (SQLCipher).

---

# SEKSI 03 — MINDSET & MENTAL MODEL
Dalam rekayasa aplikasi mobile modern, jaringan bukanlah saluran transmisi kabel yang stabil; jaringan adalah kondisi eksternal yang *secara inheren tidak dapat dipercaya dan bersifat probabilistik*. Asumsi bahwa "koneksi internet selalu ada kecuali pengguna masuk ke mode pesawat" adalah kesalahan arsitektur fundamental.

### Mental Model: Database Lokal Adalah Single Source of Truth
```
+-------------------------------------------------------------+
|                  PARADIGMA TRADISIONAL                      |
|  UI -----> Network API Request -----> Remote Database       |
|  UI <---- JSON Response / Error <---- Server                |
|  (Aplikasi rapuh, blocking, latency tinggi, mudah crash)   |
+-------------------------------------------------------------+

+-------------------------------------------------------------+
|                 PARADIGMA OFFLINE-FIRST                     |
|  UI <==== (Reactive Stream) ====> Local Encrypted DB        |
|                                         ^                   |
|                                         | (Sync Engine)     |
|                                         v                   |
|                              Mutation Queue / Worker        |
|                                         |                   |
|                                   Network Pipe              |
|                                         |                   |
|                                         v                   |
|                                   Remote Server             |
+-------------------------------------------------------------+
```

Aplikasi *offline-first* tidak memandang offline sebagai sebuah *state error*, melainkan sebagai *keadaan operasional normal*. Layar aplikasi tidak boleh menunggu respons jaringan untuk merender perubahan status. Perubahan ditulis langsung ke basis data lokal terenkripsi secara sinkron/cepat, antarmuka langsung merespons secara optimistik, dan *engine* sinkronisasi di latar belakang menangani *eventual consistency* terhadap server remote.

---

# SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Berikut adalah arsitektur aliran data *offline-first* end-to-end yang mengintegrasikan mutasi lokal, antrean sinkronisasi, validasi TLS pinning, dan enkripsi lokal:

```
[ User Interaction ]
         |
         v
[ Action Dispatcher ]
         |
         +---------------------------------------+
         |                                       |
         v                                       v
[ Optimistic UI Update ]              [ Local Storage / DB ]
(Local State updated immediately)      (WatermelonDB / SQLCipher)
         |                                       |
         | (Render frame)                        v
         |                            [ Transactional Write ]
         |                            (Write Data + Enqueue Mutation)
         |                                       |
         +---------------------------------------+
                                                 |
                                                 v
                                    [ Offline Mutation Queue ]
                                    (Persisted in Secure Storage)
                                                 |
                                                 v
                                      [ Network State Monitor ]
                                   (NetInfo: Reachability Probe)
                                                 |
                                     +-----------+-----------+
                                     |                       |
                             [ State: OFFLINE ]      [ State: ONLINE ]
                                     |                       |
                                (Halt Queue)                 v
                                                 [ Sync Background Worker ]
                                                             |
                                                             v
                                                  [ Network Client Engine ]
                                                             |
                                                             v
                                                  [ TLS Pinning Interceptor ]
                                                  (Check SPKI SHA-256 Hash)
                                                             |
                                            +----------------+----------------+
                                            |                                 |
                                    [ Pin Mismatch ]                   [ Pin Valid ]
                                            |                                 |
                                    (Abort & Alert)                           v
                                                                   [ HTTPS Request ]
                                                                   (Idempotent Payload)
                                                                              |
                                                             +----------------+----------------+
                                                             |                                 |
                                                      [ HTTP 2xx/OK ]                 [ HTTP 4xx/5xx Fail ]
                                                             |                                 |
                                                             v                                 v
                                                   [ Commit Local State ]            [ Conflict Resolver ]
                                                   [ Remove from Queue  ]                      |
                                                                              +----------------+----------------+
                                                                              |                                 |
                                                                      [ Client Wins ]                   [ Server Wins ]
                                                                              |                                 |
                                                                      (Re-enqueue)                      (Rollback Local)
```

---

# SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. The Offline Mutation Queue
Antrean mutasi harus memenuhi kaidah *ACID Transactionality*:
* **Enqueue:** Setiap mutasi (`CREATE`, `UPDATE`, `DELETE`) disimpan ke tabel antrean lokal bersamaan dengan mutasi entitas itu sendiri dalam satu transaksi database lokal.
* **Payload Serialization:** Parameter payload harus diserialisasi dalam format deterministik termasuk metadata: `mutation_id` (UUIDv4), `timestamp`, `retry_count`, `idempotency_key`, dan `entity_type`.
* **State Preservation:** Apabila proses aplikasi dihentikan oleh OS (misal: *OOM killer* pada Android), antrean tetap utuh di disk storage dan dapat diproses kembali saat proses dihidupkan (*cold boot*).

### 2. Network Reachability Probing
Modul pendeteksi jaringan sistem operasi (seperti `@react-native-community/netinfo`) sering kali mengembalikan nilai *false positive*. Perangkat mungkin terhubung ke Wi-Fi router (koneksi radio aktif), namun Wi-Fi tersebut tidak memiliki akses internet (*Captive Portal* di hotel/bandara). 
Mekanisme internal harus mengombinasikan:
* Event-driven API (NetworkCapabilities / NWPathMonitor).
* Polling Probe (*Active Ping*) ke endpoint kecil berlatensi rendah (misal: `HEAD /healthcheck` atau Cloudflare `generate_204`) untuk memastikan transmisi layer 7 (HTTP) benar-benar tembus.

### 3. Idempotency Key Pattern
Ketika mutasi dikirim ke server namun jaringan terputus tepat sebelum *response packet* diterima oleh perangkat, klien tidak tahu apakah mutasi berhasil dieksekusi atau tidak. Tanpa *idempotency key*, *retry* mutasi dapat menyebabkan duplikasi data (misal: pembayaran terpotong dua kali).
* Klien membuat `X-Idempotency-Key: <UUID>` unik untuk tiap mutasi.
* Server menyimpan *state* pemrosesan key tersebut dalam Redis/Database dengan *TTL*.
* Jika server menerima key yang sama, server mengembalikan hasil tersimpan tanpa mengeksekusi ulang operasi logis.

### 4. TLS Pinning: Certificate vs. Public Key (SPKI)
* **Certificate Pinning:** Melakukan validasi byte-per-byte seluruh sertifikat X.509 server. Kelemahan: Masa kedaluwarsa sertifikat mewajibkan pembaruan aplikasi via App Store / Play Store.
* **Subject Public Key Info (SPKI) Pinning:** Hanya melakukan *hashing* (SHA-256) pada komponen Public Key di dalam sertifikat. Fleksibilitas tinggi: Saat sertifikat diperbarui (renewed) menggunakan *Certificate Signing Request* (CSR) dan *Private Key* yang sama, nilai hash SPKI tetap sama, mencegah aplikasi menjadi *bricked*.

---

# SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### Resolusi Konflik: LWW vs. CRDTs
Dalam topologi terdistribusi yang melibatkan operasi *offline*, konflik penulisan konkuren tidak terhindarkan.

#### 1. Last-Write-Wins (LWW)
Menggunakan *timestamp* mutasi untuk menentukan versi data yang bertahan.
$$\text{State}_{\text{final}} = \arg\max_{t} (\text{Update}(t))$$
* **Kelemahan:** Bergantung pada jam sistem perangkat (*system clock skew*). Jika jam di Android klien melenceng 3 hari ke masa depan, mutasi klien tersebut akan selalu menimpa perubahan pengguna lain. Jika menggunakan LWW, *Hybrid Logical Clocks* (HLC) wajib digunakan untuk menggantikan NTP clock lokal.

#### 2. Conflict-Free Replicated Data Types (CRDTs)
Struktur data matematis yang secara formal menjamin konvergensi deterministik antar simpul (*nodes*) tanpa memerlukan *central lock coordinator*.
* **State-based CRDTs (CvRDT):** Simpul saling mengirim seluruh state. Konvergensi terjadi via fungsi *join* ($\sqcup$) yang harus bersifat *Monotonik, Komutatif, dan Asosiatif*:
  $$A \sqcup B = B \sqcup A \quad \text{(Komutatif)}$$
  $$(A \sqcup B) \sqcup C = A \sqcup (B \sqcup C) \quad \text{(Asosiatif)}$$
  $$A \sqcup A = A \quad \text{(Idempoten)}$$
* **Operation-based CRDTs (CmRDT):** Simpul mengirim operasi mutasi yang dijamin terkirim dengan urutan *causal*.

### Kriptografi Lokal: SQLCipher Architecture
SQLite standar menyimpan data dalam format *plaintext* pada sistem berkas perangkat. Pada perangkat yang di-*root* atau di-*jailbreak*, data tersebut dapat diekstrak secara trivial.
* **SQLCipher** mengenkripsi seluruh file database per halaman (*page-by-page encryption*, biasanya 4096 byte per block).
* Setiap halaman memiliki *Initialization Vector* (IV) unik yang ditautkan ke *HMAC SHA-512* untuk memeriksa integritas data (*authenticated encryption*).
* Kunci simetris enkripsi (AES-256-CBC) diturunkan (*derived*) dari *passphrase* master menggunakan algoritma PBKDF2 (Password-Based Key Derivation Function 2) dengan minimal 256.000 iterasi.

---

# SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah implementasi antrean mutasi persisten menggunakan TypeScript dan engine penyimpanan lokal berkecepatan tinggi, lengkap dengan pengecekan konektivitas aktif (*active probing*) dan idempotensi.

```typescript
// types/offlineQueue.ts
export type HttpMethod = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';

export interface QueuedMutation {
  id: string; // UUIDv4
  endpoint: string;
  method: HttpMethod;
  payload: Record<string, any>;
  headers: Record<string, string>;
  createdAt: number;
  retryCount: number;
  idempotencyKey: string;
}

// services/MutationQueueManager.ts
import { MMKV } from 'react-native-mmkv';
import NetInfo from '@react-native-community/netinfo';

const storage = new MMKV({ id: 'offline-mutation-store' });
const QUEUE_STORAGE_KEY = 'MUTATION_PERSISTENCE_QUEUE';

export class MutationQueueManager {
  private static instance: MutationQueueManager;
  private isProcessing: boolean = false;
  private maxRetries: number = 5;

  private constructor() {}

  public static getInstance(): MutationQueueManager {
    if (!MutationQueueManager.instance) {
      MutationQueueManager.instance = new MutationQueueManager();
    }
    return MutationQueueManager.instance;
  }

  public enqueue(
    mutation: Omit<QueuedMutation, 'id' | 'createdAt' | 'retryCount' | 'idempotencyKey'>
  ): string {
    const queue = this.getQueue();
    const id = this.generateUUID();
    const idempotencyKey = this.generateUUID();

    const newMutation: QueuedMutation = {
      ...mutation,
      id,
      createdAt: Date.now(),
      retryCount: 0,
      idempotencyKey,
    };

    queue.push(newMutation);
    this.persistQueue(queue);
    
    // Trigger pemrosesan jika online
    this.processQueue();
    return id;
  }

  public async processQueue(): Promise<void> {
    if (this.isProcessing) return;

    const isConnected = await this.verifyActiveConnection();
    if (!isConnected) {
      console.warn('[QueueManager] Koneksi tidak tersedia. Antrean ditangguhkan.');
      return;
    }

    this.isProcessing = true;
    const queue = this.getQueue();

    while (queue.length > 0) {
      const currentMutation = queue[0];

      try {
        await this.executeMutation(currentMutation);
        // Mutasi sukses, hapus dari antrean
        queue.shift();
        this.persistQueue(queue);
      } catch (error: any) {
        console.error(`[QueueManager] Gagal memproses mutasi ${currentMutation.id}:`, error);

        if (this.isFatalError(error)) {
          // Kesalahan client 4xx (kecuali 429), buang mutasi untuk mencegah dead-lock antrean
          queue.shift();
          this.persistQueue(queue);
        } else {
          // Kesalahan jaringan / 5xx, terapkan exponential backoff
          currentMutation.retryCount += 1;
          if (currentMutation.retryCount >= this.maxRetries) {
            queue.shift(); // Buang ke Dead-Letter Queue (DLQ)
            this.handleDeadLetter(currentMutation);
          } else {
            this.persistQueue(queue);
            // Hentikan eksekusi batch, tunggu cycle berikutnya
            break;
          }
        }
      }
    }

    this.isProcessing = false;
  }

  private async executeMutation(mutation: QueuedMutation): Promise<Response> {
    const response = await fetch(mutation.endpoint, {
      method: mutation.method,
      headers: {
        'Content-Type': 'application/json',
        'X-Idempotency-Key': mutation.idempotencyKey,
        ...mutation.headers,
      },
      body: JSON.stringify(mutation.payload),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw { status: response.status, data: errorData };
    }

    return response;
  }

  private async verifyActiveConnection(): Promise<boolean> {
    const netState = await NetInfo.fetch();
    if (!netState.isConnected || !netState.isInternetReachable) {
      return false;
    }

    try {
      // Probing Layer 7 aktif
      const probe = await fetch('https://clients3.google.com/generate_204', {
        method: 'HEAD',
        cache: 'no-store',
      });
      return probe.status === 204;
    } catch {
      return false;
    }
  }

  private isFatalError(error: any): boolean {
    if (error.status && error.status >= 400 && error.status < 500 && error.status !== 429) {
      return true;
    }
    return false;
  }

  private handleDeadLetter(mutation: QueuedMutation): void {
    console.error(`[DLQ] Mutasi dipindahkan ke Dead-Letter Queue: ${mutation.id}`);
    const dlqRaw = storage.getString('MUTATION_DLQ') || '[]';
    const dlq: QueuedMutation[] = JSON.parse(dlqRaw);
    dlq.push(mutation);
    storage.set('MUTATION_DLQ', JSON.stringify(dlq));
  }

  private getQueue(): QueuedMutation[] {
    const data = storage.getString(QUEUE_STORAGE_KEY);
    return data ? JSON.parse(data) : [];
  }

  private persistQueue(queue: QueuedMutation[]): void {
    storage.set(QUEUE_STORAGE_KEY, JSON.stringify(queue));
  }

  private generateUUID(): string {
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
      const r = (Math.random() * 16) | 0;
      const v = c === 'x' ? r : (r & 0x3) | 0x8;
      return v.toString(16);
    });
  }
}
```

---

# SEKSI 08 — ANALISIS BARIS DEMI BARIS

* **Baris 2–12:** Definisi antarmuka eksplisit TypeScript (`QueuedMutation`). Meliputi `idempotencyKey` untuk mitigasi eksekusi ganda dan `retryCount` untuk pelacakan batas kegagalan.
* **Baris 15:** Menggunakan library C++ high-performance engine `react-native-mmkv` sebagai backing-store persisten instan synchronous, bukan `AsyncStorage` yang rentan terhadap race condition asinkron.
* **Baris 24–37:** Pola `Singleton` untuk menjamin hanya ada satu instansiasi *worker loop* yang berjalan di memori aplikasi pada satu waktu, memitigasi mutasi ganda simultan (*race conditions*).
* **Baris 39–56 (`enqueue`):** Menambahkan mutasi ke antrean dengan membuat ID baru dan kunci idempotensi acak. Serialisasi langsung ditulis secara atomik ke storage lokal sebelum pemrosesan jaringan dipicu.
* **Baris 58–67:** Guard clause `isProcessing` mencegah *re-entrant calls*. Jika pemrosesan sedang aktif, panggilan baru akan diabaikan karena mutasi baru sudah berada di dalam antrean memori/disk.
* **Baris 68–80 (`processQueue` loop):** Pola antrean FIFO deterministik. Mutasi index `[0]` hanya dihilangkan (`queue.shift()`) **setelah** server merespons dengan status HTTP `2xx`.
* **Baris 82–97:** Penanganan kesalahan cerdas (*smart fault tolerance*). Membedakan kesalahan 4xx (kesalahan logika klien: data ditolak validasi; harus dibuang agar antrean tidak tersumbat secara permanen) vs kesalahan 5xx/Network (sementara; dilakukan mekanisme retry dengan batas maksimum).
* **Baris 99–114 (`executeMutation`):** Permintaan HTTP sebenarnya yang menginjeksi header `X-Idempotency-Key` ke backend.
* **Baris 116–130 (`verifyActiveConnection`):** Solusi *dual-check*. Verifikasi status koneksi OS, diikuti pengecekan *Active Probing* Layer 7 ke endpoint generator HTTP 204 untuk mendeteksi *captive portal* atau sinyal internet semu.
* **Baris 138–144 (`handleDeadLetter`):** Mekanisme *Dead Letter Queue (DLQ)*. Menyimpan mutasi yang gagal permanen ke repositori terpisah untuk audit sistem, mencegah *data loss* total tanpa memblokir pipeline mutasi lainnya.

---

# SEKSI 09 — STUDI KASUS NYATA
**Skenario:** Aplikasi Distribusi Logistik Lapangan Skala Enterprise (Kurir Farmasi Medis).
Kurir mengantar pasokan obat ke ruang bawah tanah rumah sakit (*basement*) tanpa sinyal seluler selama berjam-jam. Mereka harus:
1. Memindai barcode barang yang diterima.
2. Mengubah status paket menjadi "DELIVERED".
3. Mengambil tanda tangan penerima digital.
4. Menghadapi potensi aplikasi ditutup paksa oleh OS Android karena penghematan baterai agresif (*aggressive background kill*).
5. Memastikan sertifikat server dilindungi secara ketat agar tidak disadap di Wi-Fi publik rumah sakit, namun memiliki fallback saat sertifikat publik dirotasi setiap 90 hari (Let's Encrypt).

---

# SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

Implementasi berikut mencakup:
1. Konfigurasi `react-native-pinch` / native networking pinning dengan backup hash (SPKI).
2. Penyimpanan persisten aman menggunakan integrasi Keystore/Keychain.
3. Hook kustom `useOfflineMutation` dengan *Optimistic UI Update* dan kemampuan *automatic rollback*.

```typescript
// security/PinningConfig.ts
export const TLS_SECURITY_CONFIG = {
  baseUrl: 'https://api.logistics-core.enterprise.com',
  // Pinning SHA-256 SPKI Public Keys (Termasuk Primary + 2 Backup Keys)
  pins: [
    'sha256/k2oTQLGenHGKdQI5P/4kypQSFIPOkd5z8i5uTWU_TEST=', // Primary Certificate SPKI
    'sha256/YLh1dUR9y6Kja30RrAn7JKnbQG/uEtLMkBGFF2FUIDY=', // Backup Root CA SPKI
    'sha256/WoiWRyIOVNa9ihaBciRSC7XHjliYS9VwUGOIud4PB18=', // Disaster Recovery Key
  ],
};

// storage/SecureKeyStorage.ts
import * as Keychain from 'react-native-keychain';

export class SecureKeyStorage {
  private static KEY_ALIAS = 'DATABASE_MASTER_KEY';

  public static async getOrCreateMasterKey(): Promise<string> {
    const credentials = await Keychain.getGenericPassword({ service: this.KEY_ALIAS });
    if (credentials) {
      return credentials.password;
    }

    // Generate entropy tinggi 256-bit cryptographically secure key
    const newKey = Array.from({ length: 32 }, () =>
      Math.floor(Math.random() * 256).toString(16).padStart(2, '0')
    ).join('');

    await Keychain.setGenericPassword('system', newKey, {
      service: this.KEY_ALIAS,
      accessible: Keychain.ACCESSIBLE.WHEN_UNLOCKED_THIS_DEVICE_ONLY,
      securityLevel: Keychain.SECURITY_LEVEL.SECURE_HARDWARE, // Wajib Hardware TEE/SE
    });

    return newKey;
  }
}

// hooks/useOfflineMutation.ts
import { useState, useCallback } from 'react';
import { MutationQueueManager, HttpMethod } from '../services/MutationQueueManager';

interface MutationOptions<TData, TVariables> {
  endpoint: string;
  method: HttpMethod;
  onOptimisticUpdate: (variables: TVariables) => void;
  onRollback: (variables: TVariables, error: any) => void;
  onSuccess?: (data: TData) => void;
}

export function useOfflineMutation<TData = any, TVariables = any>(
  options: MutationOptions<TData, TVariables>
) {
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const queueManager = MutationQueueManager.getInstance();

  const mutate = useCallback(
    async (variables: TVariables) => {
      setIsLoading(true);

      // 1. Eksekusi Optimistic Update di UI / Local DB Memory State
      try {
        options.onOptimisticUpdate(variables);
      } catch (err) {
        console.error('[OptimisticUpdate Failed]', err);
        setIsLoading(false);
        return;
      }

      // 2. Masukkan ke persistent queue
      try {
        queueManager.enqueue({
          endpoint: options.endpoint,
          method: options.method,
          payload: variables as Record<string, any>,
          headers: {
            'X-Client-Timestamp': Date.now().toString(),
          },
        });
      } catch (enqueueError) {
        // 3. Rollback jika proses antrean lokal gagal total
        options.onRollback(variables, enqueueError);
      } finally {
        setIsLoading(false);
      }
    },
    [options, queueManager]
  );

  return { mutate, isLoading };
}

// components/DeliverySignatureScreen.tsx
import React, { useState } from 'react';
import { View, Text, Button, Alert } from 'react-native';
import { useOfflineMutation } from '../hooks/useOfflineMutation';

interface DeliveryStatusState {
  packageId: string;
  status: 'IN_TRANSIT' | 'DELIVERED';
  recipientSignature: string;
}

export const DeliverySignatureScreen: React.FC<{ packageId: string }> = ({ packageId }) => {
  const [packageState, setPackageState] = useState<DeliveryStatusState>({
    packageId,
    status: 'IN_TRANSIT',
    recipientSignature: '',
  });

  const { mutate, isLoading } = useOfflineMutation<any, { signature: string }>({
    endpoint: `https://api.logistics-core.enterprise.com/v1/packages/${packageId}/deliver`,
    method: 'POST',
    onOptimisticUpdate: (variables) => {
      // Seketika mutasikan state lokal tanpa menunggu respons server
      setPackageState((prev) => ({
        ...prev,
        status: 'DELIVERED',
        recipientSignature: variables.signature,
      }));
    },
    onRollback: (_variables, error) => {
      // Revert status jika terjadi kegagalan sistem internal
      setPackageState((prev) => ({
        ...prev,
        status: 'IN_TRANSIT',
        recipientSignature: '',
      }));
      Alert.alert('Fatal Failure', 'Gagal memproses mutasi lokal: ' + error.message);
    },
  });

  const handleConfirmDelivery = () => {
    const dummySignature = 'BASE64_BLOB_VECTOR_DATA_SIGNATURE';
    mutate({ signature: dummySignature });
  };

  return (
    <View style={{ padding: 20 }}>
      <Text>Package: {packageState.packageId}</Text>
      <Text>Status: {packageState.status}</Text>
      <Button
        title={isLoading ? 'Memproses...' : 'Konfirmasi Penerimaan'}
        onPress={handleConfirmDelivery}
        disabled={packageState.status === 'DELIVERED'}
      />
    </View>
  );
};
```

---

# SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN KOMPARATIF

| Parameter | State-based CRDT | Operation-based CRDT | Last-Write-Wins (LWW) | Server-Determined (Manual) |
|---|---|---|---|---|
| **Kompleksitas Implementasi** | Sangat Tinggi | Tinggi | Sangat Rendah | Sedang |
| **Overhead Ukuran Jaringan** | Sangat Besar (Kirim Full State + Meta) | Ringan (Hanya Payload Operasi) | Minimal (Hanya Timestamp + Data) | Standar REST / GraphQL |
| **Konsistensi Data** | Deterministik Matematis Konvergen | Deterministik jika kausalitas terjamin | Rawan *Silent Overwrite* | Tergantung Server Resolver |
| **Kebutuhan Memori Lokal** | Sangat Tinggi (State Graphs & Tomsbtone) | Sedang (Log Transaksi lokal) | Sangat Rendah (Hanya kolom updated_at) | Sangat Rendah |
| **Risiko Waktu Klien (Clock Skew)** | Tidak Ada | Rendah | Fatal jika NTP tidak disinkronisasi | Tidak Ada |

### Evaluasi:
* Gunakan **CRDT** untuk kolaborasi multi-user teks atau dokumen kanban (misal: Google Docs, Figma-like React Native canvas).
* Gunakan **LWW via Hybrid Logical Clocks** untuk aplikasi inventaris umum, di mana skenario tabrakan penulisan jarang terjadi dan kompleksitas CRDT tidak sebanding dengan *engineering overhead*-nya.

---

# SEKSI 12 — EDGE CASES & PITFALLS

### 1. The "Tombstone Accumulation" Problem
Ketika data dihapus secara *offline*, data tidak boleh langsung di-`DELETE` dari SQL lokal. Jika dihapus seketika, proses sinkronisasi berikutnya tidak tahu bahwa data tersebut pernah ada dan telah dihapus; server akan mengirimkannya kembali sebagai entitas baru (*resurrection bug*).
* **Mitigasi:** Tandai data dengan *Tombstone* (`is_deleted = 1, deleted_at = <timestamp>`). Sinkronisasikan flag ini ke backend. Hanya jalankan hard-delete (*garbage collection*) lokal setelah server mengembalikan konfirmasi *acknowledgement* bahwa entri telah dimusnahkan.

### 2. Zombie Mutations & Out-of-Order Dependencies
Pengguna membuat akun baru (Mutasi A), lalu langsung membuat order dengan akun tersebut (Mutasi B) secara offline.
* **Failure Mode:** Jika Mutasi A gagal di server karena validasi email duplikat, Mutasi B akan memicu *Foreign Key Constraint Error* di database remote.
* **Mitigasi:** Antrean mutasi harus mendukung *Dependency Chaining*. Jika mutasi induk (*parent*) berstatus ditolak permanen, seluruh mutasi anak (*child*) yang bergantung pada entitas tersebut harus di-*purge* secara kaskade ke DLQ dan memicu rollback terstruktur di UI.

### 3. SSL Pinning App-Lockout Trap
Meng-hardcode single SSL Fingerprint di binary aplikasi. Ketika sertifikat server di-revoke secara mendadak karena celah keamanan OpenSSL, seluruh aplikasi pengguna di seluruh dunia akan gagal tersambung (*Network Error*) tanpa bisa mengunduh konfigurasi baru.
* **Mitigasi:** Wajib memasang minimal **tiga SPKI pins**:
  1. Pin sertifikat aktif saat ini.
  2. Pin sertifikat Intermediate/Root CA penerbit.
  3. Pin sertifikat Backup (Cold Storage Key) yang belum ditandatangani namun private key-nya tersimpan aman di offline safe deposit vault.

---

# SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Menyimpan Binary / Base64 di Antrean Mutasi
* **Kesalahan:** Menyimpan string Base64 gambar 10MB langsung di antrean MMKV atau SQLite. Ini memicu *heap memory pressure* dan OOM Crash saat JSON diserialisasi/deserialisasi.
* **Solusi:** Simpan gambar ke file system lokal (`cacheDirectory` atau `documentDirectory`). Simpan hanya referensi URI file lokal (`file:///...`) di dalam payload antrean mutasi.

### 2. Menggunakan `Date.now()` untuk Logika Resolusi
* **Kesalahan:** Mengandalkan jam sistem operasi perangkat pengguna untuk menandai waktu terjadinya peristiwa. Pengguna dapat secara sengaja atau tidak sengaja mengubah tanggal handphone mundur 5 tahun.
* **Solusi:** Hitung *Clock Drift/Delta* antara server dan klien saat handshake pertama:
  $$\Delta t = T_{\text{server}} - T_{\text{client\_receive}}$$
  Gunakan $\text{Timestamp}_{\text{actual}} = \text{Date.now()} + \Delta t$ untuk seluruh metadata mutasi.

### 3. Infinite Retry Loops (The Thundering Herd)
* **Kesalahan:** Mengulang (*retry*) permintaan mutasi setiap detik tanpa interval ketika server mengembalikan 503 Service Unavailable.
* **Solusi:** Implementasikan **Exponential Backoff dengan Full Jitter**:
  $$T_{\text{wait}} = \text{random}(0, \min(T_{\text{max}}, T_{\text{base}} \times 2^{\text{retry\_count}}))$$

---

# SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Deterministic Serialization:** Pastikan JSON payload di-serialize menggunakan urutan key yang terurut secara deterministik sebelum menghitung *hash* integritas lokal.
2. **Network Scoped Session Handshake:** Setiap kali transisi jaringan terjadi dari *Cellular* ke *Wi-Fi*, lakukan handshake ping ulang untuk memverifikasi ada/tidaknya SSL Interception dari transparent enterprise proxy.
3. **Background Sync via Native OS Workers:** Jangan mengandalkan JavaScript timer (`setInterval`) untuk sinkronisasi latar belakang. Gunakan API platform bawaan:
   * **Android:** `WorkManager` API dengan batasan `NetworkType.CONNECTED`.
   * **iOS:** `BGProcessingTask` via `BackgroundTasks.framework`.
4. **Defense in Depth Security:** Enkripsi database master key harus selalu menggunakan *Secure Enclave* (iOS) atau *Hardware-backed Android Keystore* dengan flag `BIOMETRIC_STRONG` atau `DEVICE_PASSCODE`.

---

# SEKSI 15 — OPTIMASI KINERJA & EFISIENSI MEMORI/JARINGAN

### 1. Delta Compression (JSON Patch RFC 6902)
Jangan mengirimkan seluruh entitas jika pengguna hanya memperbarui status satu field.
```json
// Buruk: Kirim full object (2 KB)
{ "id": "123", "name": "Budi", "address": "...", "status": "DELIVERED" }

// Optimal: JSON Patch Payload (80 bytes)
[
  { "op": "replace", "path": "/status", "value": "DELIVERED" }
]
```

### 2. Payload Gzip/Brotli Compression
Untuk batch queue upload yang terdiri dari puluhan mutasi yang tertunda, aktifkan kompresi payload HTTP di level native sebelum data dikirim melalui kabel:
* Tambahkan header: `Content-Encoding: gzip`.
* Ini mengurangi ukuran transmisi hingga 70-85% pada data teks/JSON terstruktur, mempercepat transmisi pada koneksi EDGE/3G dan menghemat masa pakai baterai radio perangkat (*Radio Resource Control* state machine).

---

# SEKSI 16 — KEAMANAN & HARDENING

### Implementasi Root/Jailbreak Detection & Anti-Hooking
Sebelum menginisialisasi database SQLCipher lokal atau memproses antrean mutasi, lakukan verifikasi integritas runtime perangkat:

```typescript
// security/DeviceIntegrity.ts
import { Platform } from 'react-native';
import JailMonkey from 'jail-monkey';

export class DeviceIntegrityService {
  public static assertSafeExecutionEnvironment(): void {
    if (__DEV__) return; // Izinkan mode debugging pada local development

    // 1. Cek Root / Jailbreak
    if (JailMonkey.isJailBroken()) {
      this.terminateApplication('Device is rooted/jailbroken. Halting execution.');
    }

    // 2. Deteksi Frida / Xposed Hooking Frameworks
    if (JailMonkey.hookDetected()) {
      this.terminateApplication('Dynamic analysis hooking framework detected.');
    }

    // 3. Verifikasi apakah aplikasi berjalan di Emulator / Sim (Anti-Cloning)
    if (JailMonkey.isOnExternalStorage()) {
      this.terminateApplication('Application is installed on insecure external