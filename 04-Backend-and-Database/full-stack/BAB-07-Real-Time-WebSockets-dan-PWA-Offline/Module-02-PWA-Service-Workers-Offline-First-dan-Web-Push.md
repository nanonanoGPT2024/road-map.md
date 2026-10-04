---
[⬅️ Module 01: Real-Time & WebSockets](./Module-01-WebSockets-SSE-dan-Redis-PubSub-Clustering.md) | [📋 Silabus Induk](../README.md) | [BAB 07 Quiz & Challenge ➡️](./BAB-07-Quiz-dan-Challenge.md)
---

# Module 02: Progressive Web Apps (PWA): Service Workers, Cache API, Offline-First Sync, & Web Push Notifications

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
- Memahami konsep dasar dan arsitektur **Progressive Web Apps (PWA)** serta standar kepatuhan instalasi aplikasi (*Web App Manifest* dan Service Worker).
- Menguasai siklus hidup (*Lifecycle*) **Service Worker**: fase `install`, `activate`, dan intersepsi request jaringan melalui event `fetch`.
- Menerapkan berbagai strategi caching menggunakan **Cache API bawaan browser**: *Cache-First*, *Network-First*, dan *Stale-While-Revalidate*.
- Merancang arsitektur **Offline-First Application** dengan memanfaatkan **IndexedDB** untuk penyimpanan data lokal dan **Background Sync API** untuk sinkronisasi mutasi tertunda saat koneksi pulih.
- Mengimplementasikan sistem **Web Push Notifications** lintas platform menggunakan standar protokol Web Push (RFC 8291/8292) dan kriptografi **VAPID (Voluntary Application Server Identification)**.

---

## 2. Prerequisite
- Memahami Event Loop dan asynchronous programming di JavaScript.
- Memahami Web Storage APIs (`localStorage`, `sessionStorage`, `IndexedDB`).
- Memahami konsep HTTP Request/Response dan Service Worker environment (Web Worker tanpa akses DOM langsung).

---

## 3. Concept
Secara default, aplikasi web konvensional sepenuhnya bergantung pada koneksi internet aktif. Jika koneksi terputus (*offline*), browser akan menampilkan gambar dinosaurus Google Chrome yang terkenal (*Offline Error*), dan pengguna tidak dapat mengakses apapun.

**Progressive Web Apps (PWA)** mengubah aplikasi web menjadi aplikasi kelas satu (*first-class application*) yang sebanding dengan native mobile app. Inti dari PWA adalah **Service Worker**: sebuah skrip JavaScript yang berjalan di thread latar belakang (*background thread* terpisah dari UI), bertindak sebagai **Programmable Network Proxy** di dalam browser pengguna.

```
[ BROWSER UI (Komponen React / Next.js) ]
                   |
            fetch('/api/feed')
                   v
+--------------------------------------------------------+
| SERVICE WORKER (Network Proxy di Browser Pengguna)     |
|                                                        |
| Event: `self.addEventListener('fetch', (event) => ...)`|
|                                                        |
|  1. Cek Cache API Lokal (Offline Storage)              |
|     Ada? ---> Kembalikan instan (0ms)                  |
|                                                        |
|  2. Ada Jaringan? ---> Teruskan ke Server              |
|     Offline? ---> Antrekan mutasi ke IndexedDB         |
+--------------------------------------------------------+
                   |
      (Jaringan Internet Eksternal)
                   v
         [ BACKEND SERVER API ]
```

Setiap request HTTP yang dikirim oleh halaman web **dicegat terlebih dahulu** oleh Service Worker. Service Worker dapat memutuskan apakah request tersebut dilayani dari memori cache lokal, diambil dari jaringan internet, atau disimpan ke antrean lokal untuk disinkronkan nanti!

---

## 4. Why? (Mengapa Kita Memerlukan Offline-First?)
1. **Keandalan Akses Tanpa Sinyal**: Pengguna di kereta bawah tanah, lift, atau daerah terpencil tetap dapat membuka catatan, melihat katalog, atau menyusun draft pesan tanpa terganggu oleh hilangnya koneksi seluler.
2. **Kecepatan Loading Mendekati 0ms (Instant Load)**: Dengan strategi *Cache-First*, seluruh aset statis aplikasi (HTML, CSS, JS, Icon) disajikan langsung dari disk lokal pengguna, menghasilkan skor *Core Web Vitals* yang sempurna.
3. **Pemberitahuan Re-Engagement (Push Notification)**: Memungkinkan aplikasi web mengirimkan notifikasi penting (seperti diskon e-commerce atau konfirmasi pembayaran) langsung ke notification drawer Android/Windows/macOS bahkan ketika browser sedang ditutup.

---

## 5. What? (Pola Caching Utama pada Cache API)

### A. Cache-First (Fallback ke Network)
- **Cara Kerja**: Periksa Cache API terlebih dahulu. Jika data ditemukan (*Cache Hit*), kembalikan instan. Jika tidak ada (*Cache Miss*), ambil dari jaringan dan simpan ke cache untuk request berikutnya.
- **Use Case**: Aset statis yang tidak pernah berubah (gambar ber-hash, font web, file bundle JS/CSS hasil build webpack/vite).

### B. Network-First (Fallback ke Cache)
- **Cara Kerja**: Coba ambil data terbaru dari jaringan server terlebih dahulu. Jika jaringan gagal/offline, baru gunakan data versi terakhir yang tersimpan di cache.
- **Use Case**: Data dinamis yang sering berubah tetapi tetap berguna saat offline (feed berita, saldo dompet, data profil pengguna).

### C. Stale-While-Revalidate (SWR)
- **Cara Kerja**: Kembalikan data lama dari cache secepat mungkin (*Instant Paint*), sembari secara asinkron mengambil data terbaru dari jaringan untuk memperbarui cache di latar belakang.
- **Use Case**: Data semi-dinamis di mana pengguna memprioritaskan kecepatan visual daripada data yang 100% mutakhir di detik pertama (katalog produk, daftar artikel).

---

## 6. How? (Implementasi Service Worker & Web Push)

### 1. File Service Worker Lengkap (public/sw.js)
```javascript
const CACHE_NAME = "enterprise-pwa-v1";
const STATIC_ASSETS = [
  "/",
  "/offline.html",
  "/favicon.ico",
  "/manifest.json",
];

// 1. Fase Install: Pre-caching aset statis penting
self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      console.log("[SW] Pre-caching static assets...");
      return cache.addAll(STATIC_ASSETS);
    })
  );
  self.skipWaiting();
});

// 2. Fase Activate: Bersihkan cache versi lama
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))
      );
    })
  );
  self.clients.claim();
});

// 3. Fase Fetch: Intersepsi Request Jaringan (Stale-While-Revalidate)
self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);

  // Jangan cache API mutasi atau rute otentikasi
  if (url.pathname.startsWith("/api/auth") || event.request.method !== "GET") {
    return;
  }

  event.respondWith(
    caches.open(CACHE_NAME).then(async (cache) => {
      const cachedResponse = await cache.match(event.request);

      const fetchPromise = fetch(event.request)
        .then((networkResponse) => {
          if (networkResponse.status === 200) {
            cache.put(event.request, networkResponse.clone());
          }
          return networkResponse;
        })
        .catch(() => {
          // Jika offline dan tidak ada cache, tampilkan halaman offline cadangan
          if (event.request.mode === "navigate") {
            return cache.match("/offline.html");
          }
        });

      return cachedResponse || fetchPromise;
    })
  );
});

// 4. Penanganan Notifikasi Web Push
self.addEventListener("push", (event) => {
  const data = event.data ? event.data.json() : { title: "Notifikasi Baru", body: "Ada pembaruan untuk Anda!" };
  event.waitUntil(
    self.registration.showNotification(data.title, {
      body: data.body,
      icon: "/icons/icon-192x192.png",
      badge: "/icons/badge-72x72.png",
      data: { url: data.url || "/" },
    })
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  event.waitUntil(clients.openWindow(event.notification.data.url));
});
```

### 2. Registrasi Service Worker di React / Next.js
```typescript
// components/PWARegistration.tsx
"use client";
import { useEffect } from "react";

export function PWARegistration() {
  useEffect(() => {
    if ("serviceWorker" in navigator && process.env.NODE_ENV === "production") {
      navigator.serviceWorker
        .register("/sw.js")
        .then((reg) => console.log("Service Worker terdaftar dengan scope:", reg.scope))
        .catch((err) => console.error("Gagal mendaftarkan Service Worker:", err));
    }
  }, []);

  return null;
}
```

---

## 7. Analogy
Bayangkan seorang juru masak pribadi di rumah Anda:
- **Web Tradisional**: Setiap kali Anda lapar (ingin makan nasi goreng), Anda harus memesan ke restoran di kota seberang. Jika jalanan longsor (*koneksi internet mati*), Anda kelaparan (*Browser Error Dinosaurus*).
- **Service Worker & Cache API**: Anda memiliki kulkas pintar di dapur (*Local Cache*) dan juru masak setia (*Service Worker*). Saat Anda minta makan, juru masak memeriksa kulkas: jika ada persediaan, makanan disajikan dalam 30 detik! Sementara Anda makan, ia menelepon kurir secara santai di latar belakang untuk mengisi ulang stok bahan yang baru (*Stale-While-Revalidate*). Anda tidak pernah kelaparan lagi!

---

## 8. Diagram Arsitektur Offline-First Mutation Queue

```
[ PENGGUNA MEMBUAT CATATAN BARU SAAT OFFLINE ]
                      |
                      v
      (Apakah Ada Jaringan Internet?)
           /                    \
        [ YA ]                [ TIDAK ]
          |                       |
[ Kirim Langsung ke Server ]  [ Simpan Aksi ke IndexedDB 'outbox_queue' ]
          |                       |
     (Selesai)                [ Tampilkan UI Optimistic: 'Tersimpan Offline' ]
                                  |
                      (Koneksi Internet Kembali Pulih)
                                  v
                    [ Event: 'sync' atau 'online' ]
                                  v
             [ Service Worker Membaca Seluruh Antrean IndexedDB ]
                                  v
               [ Mengirimkan Request POST/PUT ke Backend ]
                                  v
              [ Kosongkan Antrean 'outbox_queue' & Tampilkan Notif ]
```

---

## 9. Simple Example: Web App Manifest (public/manifest.json)
File deklarasi metadata yang memungkinkan browser menawarkan prompt "Install App" ke home screen smartphone atau desktop:

```json
{
  "name": "Enterprise Collaborative Workspace",
  "short_name": "Workspace",
  "start_url": "/?source=pwa",
  "display": "standalone",
  "background_color": "#0f172a",
  "theme_color": "#3b82f6",
  "icons": [
    {
      "src": "/icons/icon-192x192.png",
      "sizes": "192x192",
      "type": "image/png",
      "purpose": "any maskable"
    },
    {
      "src": "/icons/icon-512x512.png",
      "sizes": "512x512",
      "type": "image/png"
    }
  ]
}
```

---

## 10. Practical Example: Background Sync Queue dengan IndexedDB
Menyimpan mutasi saat offline dan memprosesnya secara otomatis saat kembali online:

```typescript
// utils/offlineQueue.ts
const DB_NAME = "PWA_OFFLINE_DB";
const STORE_NAME = "mutation_queue";

export async function queueOfflineMutation(endpoint: string, payload: any) {
  const db = await openDatabase();
  const tx = db.transaction(STORE_NAME, "readwrite");
  tx.objectStore(STORE_NAME).add({
    endpoint,
    payload,
    timestamp: Date.now(),
  });

  // Minta browser menjalankan background sync saat online
  if ("serviceWorker" in navigator && "SyncManager" in window) {
    const reg = await navigator.serviceWorker.ready;
    await (reg as any).sync.register("sync-pending-mutations");
  }
}
```

---

## 11. Real-World Example: VAPID Web Push Delivery dari Backend Node.js
Mengirimkan notifikasi push dari server ke browser menggunakan protokol VAPID:

```typescript
import webpush from "web-push";

// Konfigurasi VAPID Keys
webpush.setVapidDetails(
  "mailto:admin@perusahaan.com",
  process.env.VAPID_PUBLIC_KEY!,
  process.env.VAPID_PRIVATE_KEY!
);

export async function sendOrderShippedNotification(userSubscription: webpush.PushSubscription, orderId: string) {
  const payload = JSON.stringify({
    title: "Pesanan Dikirim! 📦",
    body: `Paket pesanan ${orderId} Anda sedang dalam perjalanan oleh kurir.`,
    url: `/orders/${orderId}`,
  });

  try {
    await webpush.sendNotification(userSubscription, payload);
    return { success: true };
  } catch (error: any) {
    if (error.statusCode === 410) {
      // 410 Gone: Pengguna mencabut izin notifikasi, hapus langganan dari database!
      console.log("Subscription kadaluwarsa, menghapus dari DB...");
    }
    throw error;
  }
}
```

---

## 12. Trade-offs: Caching Strategies Comparison

| Strategi Caching | Kecepatan Respon | Kemutakhiran Data (Freshness) | Dukungan Offline | Kebutuhan Bandwidth |
| :--- | :--- | :--- | :--- | :--- |
| **Cache-First** | **Tercepat (<2ms)** | Rendah (Bisa kadaluwarsa) | **Sempurna** | Paling Hemat |
| **Network-First**| Lambat (Tergantung sinyal)| **Tinggi (Selalu Terkini)** | Parsial (Hanya jika gagal) | Boros |
| **Stale-While-Revalidate** | **Sangat Cepat (<5ms)** | Menengah (Baru pada reload ke-2) | **Sempurna** | Seimbang |
| **Network-Only** | Paling Lambat | Tertinggi | **Nol (Crash saat offline)** | Paling Boros |

---

## 13. When To Use PWA & Service Workers
- Aplikasi SaaS produktivitas (Notion/Trello/Figma clone) di mana pengguna sering bepergian dan membutuhkan akses dokumen tanpa terputus sinyal.
- E-commerce di pasar berkembang dengan kualitas koneksi seluler 3G/4G yang tidak stabil.
- Platform media atau berita yang ingin memberikan pengalaman baca artikel offline.

---

## 14. When NOT To Use
- Aplikasi admin intranet yang memiliki transaksi perbankan real-time ultra-ketat di mana tampilan data kadaluwarsa bahkan 1 detik sekalipun merupakan pelanggaran regulasi finansial.
- Aplikasi web yang sangat jarang diakses (hanya sekali pakai setahun, seperti formulir pajak tahunan).

---

## 15. Common Mistakes
1. **Meng-cache File `sw.js` dengan Durasi HTTP Cache Panjang**:
   - Jika server Nginx Anda mengirimkan header `Cache-Control: max-age=31536000` untuk file `sw.js`, browser pengguna tidak akan pernah mengunduh kode Service Worker versi terbaru Anda!
   - *Solusi*: Selalu set `Cache-Control: no-cache, no-store, must-revalidate` untuk file `sw.js`.
2. **Menyimpan Payload Besar yang Tidak Terpakai di Cache API**:
   - Menumpuk ratusan megabyte file video atau log ke dalam cache hingga kuota penyimpanan browser habis (*QuotaExceededError*).
3. **Lupa Menangani Error 410 Gone pada Web Push**:
   - Terus-menerus mengirim push notification ke endpoint subscription yang sudah ditolak atau di-uninstall oleh pengguna, menyebabkan penalti reputasi dari FCM (Firebase Cloud Messaging) atau Apple Push Service.

---

## 16. Best Practices

### Must Have
- Sajikan seluruh aset PWA melalui protokol HTTPS terenkripsi (Service Worker diblokir total oleh browser pada HTTP biasa).
- Sediakan file `offline.html` cadangan yang ramah pengguna saat seluruh koneksi jaringan terputus.

### Recommended
- Gunakan pustaka **Workbox** (dari Google Chrome team) untuk mengotomatisasi konfigurasi routing dan caching Service Worker yang kompleks.
- Lakukan pembersihan cache versi lama (*Cache Invalidation*) di dalam event handler `activate`.

### Advanced
- Gabungkan Service Worker dengan **Web Periodic Background Sync API** untuk mengunduh berita harian secara otomatis di latar belakang saat smartphone pengguna terhubung ke Wi-Fi di malam hari.

### Avoid
- Jangan pernah mencegat dan menyimpan request mutasi `POST`, `PUT`, atau `DELETE` ke dalam Cache API. Cache API hanya dirancang untuk request idempotent `GET`.

---

## 17. Troubleshooting Guide

| Gejala Masalah | Kemungkinan Akar Masalah | Solusi |
| :--- | :--- | :--- |
| Prompt "Install App" tidak pernah muncul di browser. | Manifest JSON tidak valid, tidak ada icon 192px/512px, atau Service Worker belum aktif. | Periksa tab *Application > Manifest* di Chrome DevTools untuk melihat audit kepatuhan PWA. |
| Fitur baru tidak muncul di browser pengguna meskipun sudah di-deploy. | Service Worker versi lama masih memegang kendali (*waiting to activate*). | Tambahkan `self.skipWaiting()` di event `install` dan tombol "Update Tersedia: Klik untuk Refresh" di UI. |
| Error `DOMException: Quota exceeded` saat caching aset. | Penyimpanan perangkat pengguna penuh atau cache aplikasi melebihi kuota domain. | Terapkan mekanisme pemangkasan cache LRU (*Least Recently Used*) untuk menghapus aset terlama. |

---

## 18. Exercise
- **Easy**: Buat file `manifest.json` lengkap dengan konfigurasi warna tema dan dua icon resolusi standar.
- **Medium**: Tulis Service Worker yang mengimplementasikan strategi *Network-First with Cache Fallback* untuk endpoint `/api/articles`.
- **Hard**: Implementasikan *IndexedDB Outbox Manager* yang mampu mendeteksi event `window.addEventListener('online')` dan mengirimkan seluruh draft postingan tertunda ke server.

---

## 19. Challenge
Rancang arsitektur aplikasi e-commerce Offline-First lengkap: pengguna dapat menjelajahi katalog produk, menambahkan barang ke keranjang belanja, dan menekan tombol "Checkout" saat smartphone berada dalam mode pesawat (*Airplane Mode*). Saat mode pesawat dimatikan, sistem harus menyinkronkan keranjang belanja ke server, memvalidasi ketersediaan stok terbaru, dan memicu Web Push Notification yang mengonfirmasi bahwa pesanan berhasil diproses.

---

## 20. Summary
- **Progressive Web Apps (PWA)** menjembatani jurang kemampuan antara web dan native application tanpa memerlukan proses instalasi toko aplikasi yang kaku.
- **Service Worker** adalah fondasi utama PWA yang bertindak sebagai network proxy pintar di sisi browser pengguna.
- Menguasai strategi caching (**Cache-First, Network-First, SWR**) memungkinkan arsitek full-stack merancang aplikasi yang super cepat (*Instant TTFB*) dan tangguh dalam berbagai kondisi jaringan.
- **Web Push Notifications & Background Sync** melengkapi pengalaman pengguna, memastikan aplikasi tetap relevan, aktif, dan dapat diandalkan sepanjang waktu.

---

## Hands-on Practice: Simulasi Service Worker Cache & Offline Sync Queue
Jalankan simulator intersepsi jaringan Service Worker, strategi Stale-While-Revalidate, dan antrean sinkronisasi IndexedDB mandiri:

```bash
node Full-Stack/BAB-07-Real-Time-WebSockets-dan-PWA-Offline/hands-on/m02/service_worker_offline_sync_sim.js
```

---
[⬅️ Module 01: Real-Time & WebSockets](./Module-01-WebSockets-SSE-dan-Redis-PubSub-Clustering.md) | [📋 Silabus Induk](../README.md) | [BAB 07 Quiz & Challenge ➡️](./BAB-07-Quiz-dan-Challenge.md)
---
