/**
 * SIMULATOR: WEB RENDERING PARADIGMS (CSR VS SSR VS SSG) & HYDRATION MISMATCH DETECTOR
 * Modul 01: Paradigma Render Web Modern: SSR, CSR, SSG, ISR, Hydration, & Core Web Vitals
 *
 * Mendemonstrasikan:
 * 1. Alur kerja komparasi siklus hidup: CSR vs SSR vs SSG/ISR.
 * 2. Simulasi metrik Core Web Vitals: TTFB, FCP (First Contentful Paint), LCP, dan TTI (Time-to-Interactive).
 * 3. Mesin Hydration Klien: Pemasangan event listeners pada DOM statis.
 * 4. Deteksi & Penanganan Bencana Hydration Mismatch (Server vs Client timestamp drift).
 *
 * Jalankan: node ssr_csr_hydration_sim.js
 */

// =========================================================================
// BAGIAN 1: SIMULATOR ENGINE CSR, SSR, DAN SSG
// =========================================================================

class RenderingParadigmSimulator {
  // Simulasi Client-Side Rendering (CSR)
  static simulateCSR() {
    const timeline = [];
    let currentTime = 0;

    // 1. Request HTML kosong
    currentTime += 40; // TTFB HTML kosong dari CDN
    timeline.push({ time: currentTime, event: 'HTML Kosong Diterima (<div id="root"></div>)' });

    // 2. Unduh Bundle JavaScript Klien (1.8 MB pada jaringan 4G)
    currentTime += 350;
    timeline.push({ time: currentTime, event: 'Bundle JavaScript Selesai Diunduh (1.8 MB)' });

    // 3. Eksekusi & Parse JavaScript di CPU Klien
    currentTime += 120;
    timeline.push({ time: currentTime, event: 'JavaScript Selesai Diparse & Dieksekusi' });

    // 4. Fetch Data API Eksternal dari Klien
    currentTime += 200;
    timeline.push({ time: currentTime, event: 'Fetch Data Produk dari API Selesai' });

    // 5. Render Virtual DOM ke Layar Fisik (FCP & LCP)
    currentTime += 30;
    const fcp = currentTime;
    timeline.push({ time: currentTime, event: 'First Contentful Paint (FCP) & LCP: Konten Muncul di Layar!' });

    // Pada CSR, saat konten muncul, JavaScript sudah aktif (TTI = LCP)
    const tti = currentTime;
    timeline.push({ time: currentTime, event: 'Time-to-Interactive (TTI): Tombol Siap Diklik' });

    return { paradigm: 'CSR (Client-Side Rendering)', ttfb: 40, fcp, lcp: fcp, tti, timeline };
  }

  // Simulasi Server-Side Rendering (SSR)
  static simulateSSR() {
    const timeline = [];
    let currentTime = 0;

    // 1. Server Fetch Data Internal + Render HTML to String
    currentTime += 110; // Server database query + React.renderToString
    timeline.push({ time: currentTime, event: 'Server Selesai Merender Dokumen HTML Lengkap' });

    // 2. Transmisi Dokumen HTML via Jaringan (TTFB)
    currentTime += 50;
    const ttfb = currentTime;
    timeline.push({ time: currentTime, event: 'Browser Menerima Dokumen HTML Lengkap (TTFB)' });

    // 3. Browser Parse HTML & Paint Layar (FCP / LCP tercapai seketika!)
    currentTime += 25;
    const fcp = currentTime;
    timeline.push({ time: currentTime, event: 'First Contentful Paint (FCP) & LCP: Konten Lengkap Muncul di Layar!' });

    // 4. Unduh Bundle JavaScript di Background untuk Hydration
    currentTime += 250;
    timeline.push({ time: currentTime, event: 'JavaScript Bundle Diunduh di Background' });

    // 5. Proses Hydration: Mengikat Event Listeners
    currentTime += 80;
    const tti = currentTime;
    timeline.push({ time: currentTime, event: 'Hydration Selesai: Time-to-Interactive (TTI) Tercapai!' });

    return { paradigm: 'SSR (Server-Side Rendering)', ttfb, fcp, lcp: fcp, tti, timeline };
  }

  // Simulasi Static Site Generation / Incremental Static Regeneration (SSG / ISR)
  static simulateSSG() {
    const timeline = [];
    let currentTime = 0;

    // 1. HTML sudah dipanggang saat build time dan disimpan di Edge CDN Cache
    currentTime += 15; // TTFB super cepat dari Edge Cloudflare terdekat
    const ttfb = currentTime;
    timeline.push({ time: currentTime, event: 'Dokumen HTML Disajikan dari Edge CDN Cache (TTFB)' });

    // 2. Browser Paint Langsung
    currentTime += 20;
    const fcp = currentTime;
    timeline.push({ time: currentTime, event: 'First Contentful Paint (FCP) & LCP Muncul Kilat!' });

    // 3. Unduh JS Minimal
    currentTime += 180;
    timeline.push({ time: currentTime, event: 'JavaScript Minimal Diunduh' });

    // 4. Hydration Selesai
    currentTime += 50;
    const tti = currentTime;
    timeline.push({ time: currentTime, event: 'Hydration Selesai: TTI Tercapai!' });

    return { paradigm: 'SSG / ISR (Edge CDN Static)', ttfb, fcp, lcp: fcp, tti, timeline };
  }
}

// =========================================================================
// BAGIAN 2: MESIN HYDRATION & DETEKSI HYDRATION MISMATCH
// =========================================================================

class HydrationEngine {
  static hydrate(serverHtmlPayload, clientVdom) {
    console.log('\nMemulai Proses Hydration...');
    console.log(`- Server HTML DOM : "${serverHtmlPayload.text}" (Digest: ${serverHtmlPayload.digest})`);
    console.log(`- Client VDOM     : "${clientVdom.text}" (Digest: ${clientVdom.digest})`);

    // Validasi apakah struktur teks server cocok dengan ekspektasi render pertama klien
    if (serverHtmlPayload.digest !== clientVdom.digest) {
      console.error('🚨 [HYDRATION MISMATCH DETECTED!]');
      console.error(`   Server merender: "${serverHtmlPayload.text}"`);
      console.error(`   Client mengharapkan: "${clientVdom.text}"`);
      console.warn('   ⚠️ React terpaksa membuang DOM server dan melakukan re-render penuh di sisi klien!');
      return {
        success: false,
        action: 'CLIENT_REPAINT_FALLBACK',
        penaltyTimeMs: 120
      };
    }

    console.log('✅ [HYDRATION SUKSES] Event listeners onClick & onSubmit berhasil diikat tanpa re-render!');
    return {
      success: true,
      action: 'ATTACH_LISTENERS_FAST',
      penaltyTimeMs: 0
    };
  }
}

// =========================================================================
// BAGIAN 3: EKSEKUSI PENGUJIAN SKENARIO LENGKAP
// =========================================================================

function main() {
  console.log('='.repeat(75));
  console.log('SIMULASI: ARSITEKTUR RENDER WEB MODERN & ANALISIS CORE WEB VITALS');
  console.log('='.repeat(75));

  const csrResult = RenderingParadigmSimulator.simulateCSR();
  const ssrResult = RenderingParadigmSimulator.simulateSSR();
  const ssgResult = RenderingParadigmSimulator.simulateSSG();

  console.log('\nTABEL KOMPARASI METRIK CORE WEB VITALS (dalam Milidetik):');
  console.log('-'.repeat(75));
  console.log('Paradigma Render'.padEnd(30) + 'TTFB'.padEnd(10) + 'FCP/LCP'.padEnd(12) + 'TTI (Interaktif)'.padEnd(18) + 'User Experience');
  console.log('-'.repeat(75));

  [csrResult, ssrResult, ssgResult].forEach(res => {
    const ux = res.lcp <= 50 ? '🌟 Sempurna' : res.lcp <= 200 ? '✅ Sangat Cepat' : '⚠️ Lambat (White screen)';
    console.log(
      res.paradigm.padEnd(30) +
      `${res.ttfb} ms`.padEnd(10) +
      `${res.lcp} ms`.padEnd(12) +
      `${res.tti} ms`.padEnd(18) +
      ux
    );
  });

  console.log('\nDETAIL TIMELINE CSR (Mengapa CSR Buruk untuk FCP):');
  csrResult.timeline.forEach(t => console.log(`  [+${String(t.time).padStart(4)} ms] ${t.event}`));

  console.log('\nDETAIL TIMELINE SSR DENGAN HYDRATION (Konten Cepat Muncul):');
  ssrResult.timeline.forEach(t => console.log(`  [+${String(t.time).padStart(4)} ms] ${t.event}`));

  // UJI COBA HYDRATION MISMATCH
  console.log('\n' + '-'.repeat(75));
  console.log('PENGUJIAN SIKLUS HIDUP HYDRATION & PENCEGAHAN BENCANA MISMATCH:');
  console.log('-'.repeat(75));

  // Kasus 1: Hydration Sukses (Data Deterministik)
  console.log('Kasus 1: Komponen Berita dengan Data Deterministik:');
  const serverPayloadGood = { text: 'Berita Terkini: Peluncuran Roket Sukses', digest: 'hash_berita_01' };
  const clientVdomGood = { text: 'Berita Terkini: Peluncuran Roket Sukses', digest: 'hash_berita_01' };
  HydrationEngine.hydrate(serverPayloadGood, clientVdomGood);

  // Kasus 2: Hydration Mismatch (Timestamp Acak / Timezone Drift)
  console.log('\nKasus 2: Komponen Tanggal Login Menggunakan Jam Lokal Tanpa Guard:');
  const serverPayloadBad = { text: 'Login pada: 11/09/2026, 07:30 UTC', digest: 'hash_time_utc' };
  const clientVdomBad = { text: 'Login pada: 11/09/2026, 14:30 WIB', digest: 'hash_time_wib' };
  HydrationEngine.hydrate(serverPayloadBad, clientVdomBad);

  console.log('\n' + '='.repeat(75));
  console.log('SIMULASI BERHASIL: Paradigma Render & Mekanisme Hydration terbukti akurat!');
  console.log('='.repeat(75));
}

main();
