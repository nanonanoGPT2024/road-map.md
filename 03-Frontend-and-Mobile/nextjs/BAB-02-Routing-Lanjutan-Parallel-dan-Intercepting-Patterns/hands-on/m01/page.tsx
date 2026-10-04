+--------------------------------------------------------------------------------------------------+
| BROWSER ACTION                                                                                   |
| User clicks <Link href="/photos/101"> inside /feed                                               |
+--------------------------------------------------------------------------------------------------+
                                           |
                                           v
+--------------------------------------------------------------------------------------------------+
| NEXT.JS CLIENT ROUTER EVALUATION ENGINE                                                          |
| 1. Periksa route segment tree saat ini: ['feed']                                                 |
| 2. Resolusi target: '/photos/101'                                                                |
| 3. Deteksi Interception Rules pada Segment:                                                      |
|    - Cek eksistensi direktori layout aktif                                                       |
|    - Ditemukan: app/feed/@modal/(.)photos/[id]                                                   |
+--------------------------------------------------------------------------------------------------+
                                           |
             +-----------------------------+-----------------------------+
             |                                                           |
      [ Soft Navigation ]                                         [ Hard Refresh ]
             |                                                           |
             v                                                           v
+------------------------------------------+    +--------------------------------------------------+
| RSC FETCH ENGINE (FLIGHT PROTOCOL)       |    | HTTP GET REQUEST ke Server Engine                |
| - Header: RSC=1                          |    | URL: /photos/101                                 |
| - Header: Next-Url: /feed                |    +--------------------------------------------------+
+------------------------------------------+                             |
             |                                                           v
             v                                          +----------------------------------+
+------------------------------------------+    | RENDER FULL PAGE HIERARCHY       |
| PARALLEL SLOT RESOLUTION                 |    | app/layout.tsx                   |
| 1. Layout aktif (/feed) tetap mounted    |    |   └── app/photos/[id]/page.tsx   |
| 2. Slot `@modal` diarahkan ke:           |    +----------------------------------+
|    app/feed/@modal/(.)photos/[id]        |                             |
| 3. Main children slot:                   |                             v
|    Tetap merender /feed (dipertahankan)  |                 +-----------------------+
| 4. Parallel slots lainnya:               |                 | Render Complete Document|
|    Fallback ke default.tsx jika tdk match|                 | (Clean Standalone DOM)|
+------------------------------------------+                 +-----------------------+
             |
             v
+------------------------------------------+
| REACT CLIENT RECONCILER                  |
| 1. Mempertahankan state feed tree        |
| 2. Mengisi slot `@modal` dengan RSC tree |
|    hasil render intercepted view         |
| 3. History pushState: URL jadi /photos/101|
+------------------------------------------+
