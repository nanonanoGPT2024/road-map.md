/**
 * SIMULATOR: BROWSER CRITICAL RENDERING PATH (CRP) & LAYOUT THRASHING DETECTOR
 * Modul 02: Browser Critical Rendering Path, DOM/CSSOM, Layout, & GPU Compositing
 *
 * Mendemonstrasikan:
 * 1. Pembangunan Render Tree (Penggabungan DOM + CSSOM & eliminasi display: none).
 * 2. Benchmark Performa: Layout Thrashing (Forced Synchronous Reflow) vs DOM Batching.
 * 3. Analisis Biaya Pipeline: Animasi 'top' (Layout+Paint+Composite) vs 'transform' (Composite Only).
 *
 * Jalankan: node browser_critical_rendering_path_sim.js
 */

// =========================================================================
// BAGIAN 1: CRITICAL RENDERING PATH (DOM + CSSOM -> RENDER TREE)
// =========================================================================

class CriticalRenderingPathEngine {
  static buildRenderTree(domNodes, cssRules) {
    const renderTree = [];

    for (const node of domNodes) {
      const computedStyle = cssRules[node.tag] || { display: 'block', visibility: 'visible' };

      // ATURAN 1: Elemen dengan display: none TIDAK dimasukkan ke Render Tree
      if (computedStyle.display === 'none') {
        console.log(`  [DIABAIKAN] <${node.tag} id="${node.id}"> memiliki 'display: none'. Dilewati dari Render Tree.`);
        continue;
      }

      // ATURAN 2: Elemen dengan visibility: hidden TETAP dimasukkan ke Render Tree
      // karena tetap membutuhkan kalkulasi ruang geometris pada tahap Layout!
      const isVisibleInLayout = true;

      renderTree.push({
        id: node.id,
        tag: node.tag,
        content: node.content,
        styles: computedStyle,
        takesLayoutSpace: isVisibleInLayout
      });
    }

    return renderTree;
  }
}

// =========================================================================
// BAGIAN 2: SIMULATOR LAYOUT THRASHING VS BATCHING
// =========================================================================

class MockDOMElement {
  constructor(id, initialHeight = 100) {
    this.id = id;
    this.height = initialHeight;
    this.style = { height: `${initialHeight}px` };
  }

  // Operasi Baca Geometri (Getter)
  get offsetHeight() {
    // Jika ada penulisan gaya yang belum dihitung ulang layoutnya,
    // pembacaan ini memaksa browser menjalankan REFLOW SEKETIKA!
    if (MockDOMElement.isLayoutDirty) {
      MockDOMElement.reflowCount++;
      MockDOMElement.isLayoutDirty = false; // Layout bersih kembali
    }
    return this.height;
  }

  // Operasi Tulis Gaya (Setter)
  setHeight(newHeight) {
    this.height = newHeight;
    this.style.height = `${newHeight}px`;
    // Menandai bahwa struktur layout sekarang KOTOR (Dirty)
    MockDOMElement.isLayoutDirty = true;
  }
}

MockDOMElement.isLayoutDirty = false;
MockDOMElement.reflowCount = 0;

// =========================================================================
// BAGIAN 3: BENCHMARK: THRASHING VS BATCHING
// =========================================================================

function benchmarkLayoutThrashing(elementCount = 100) {
  console.log('='.repeat(75));
  console.log(`BENCHMARK: FORCED SYNCHRONOUS LAYOUT (LAYOUT THRASHING) DENGAN ${elementCount} ELEMEN`);
  console.log('='.repeat(75));

  // --- SKENARIO A: KODE BURUK (LAYOUT THRASHING) ---
  const badElements = [];
  for (let i = 0; i < elementCount; i++) badElements.push(new MockDOMElement(`card-${i}`, 100));

  MockDOMElement.reflowCount = 0;
  MockDOMElement.isLayoutDirty = false;
  const startBad = process.hrtime.bigint();

  // Interleaved Read/Write: Baca -> Tulis -> Baca -> Tulis di dalam loop
  for (let i = 0; i < badElements.length; i++) {
    const currentHeight = badElements[i].offsetHeight; // BACA (Forced Reflow!)
    badElements[i].setHeight(currentHeight + 10);      // TULIS (Mark Dirty)
  }

  const endBad = process.hrtime.bigint();
  const timeBadMs = Number(endBad - startBad) / 1e6;
  const reflowsBad = MockDOMElement.reflowCount;

  console.log('HASIL SKENARIO A (KODE BURUK - INTERLEAVED READ/WRITE):');
  console.log(`- Total Reflow Paksa Dijalankan : ${reflowsBad} kali reflow! ❌`);
  console.log(`- Waktu Komputasi Main Thread   : ${timeBadMs.toFixed(3)} ms`);
  console.log(`- Dampak Pengguna               : Frame rate drop drastis ke 10-15 FPS (Jank Parah)`);

  // --- SKENARIO B: KODE OPTIMAL (DOM BATCH READ THEN BATCH WRITE) ---
  const goodElements = [];
  for (let i = 0; i < elementCount; i++) goodElements.push(new MockDOMElement(`card-${i}`, 100));

  MockDOMElement.reflowCount = 0;
  MockDOMElement.isLayoutDirty = false;
  const startGood = process.hrtime.bigint();

  // FASE 1: BATCH READ (Semua dibaca sekaligus tanpa ada gaya kotor)
  const cachedHeights = goodElements.map(el => el.offsetHeight); // Reflow terjadi 0 kali (belum ada yang kotor)

  // FASE 2: BATCH WRITE (Semua ditulis sekaligus)
  goodElements.forEach((el, index) => {
    el.setHeight(cachedHeights[index] + 10);
  });

  // Reflow hanya terjadi 1 kali saat frame monitor berikutnya dirender!
  if (MockDOMElement.isLayoutDirty) {
    MockDOMElement.reflowCount++;
    MockDOMElement.isLayoutDirty = false;
  }

  const endGood = process.hrtime.bigint();
  const timeGoodMs = Number(endGood - startGood) / 1e6;
  const reflowsGood = MockDOMElement.reflowCount;

  console.log('\nHASIL SKENARIO B (KODE OPTIMAL - DOM BATCHING):');
  console.log(`- Total Reflow Paksa Dijalankan : ${reflowsGood} kali reflow! ✅`);
  console.log(`- Waktu Komputasi Main Thread   : ${timeGoodMs.toFixed(3)} ms`);
  console.log(`- Efisiensi Siklus Reflow       : Terpangkas sebesar ${(((reflowsBad - reflowsGood) / reflowsBad) * 100).toFixed(1)}%!`);
  console.log(`- Dampak Pengguna               : 60-120 FPS Mulus Sempurna tanpa hambatan.`);
}

// =========================================================================
// BAGIAN 4: ANALISIS PROPERTI CSS: CPU REFLOW VS GPU COMPOSITING
// =========================================================================

function compareCssPropertiesCost() {
  console.log('\n' + '-'.repeat(75));
  console.log('KOMPARASI BIAYA PROPERTI CSS ANIMASI (CPU VS GPU):');
  console.log('-'.repeat(75));

  const animations = [
    { property: 'top / left', layout: true, paint: true, composite: true, fps: '~30-45 FPS', cost: 'Tinggi (CPU Reflow)' },
    { property: 'width / height', layout: true, paint: true, composite: true, fps: '~25-40 FPS', cost: 'Ekstrem (Full Reflow)' },
    { property: 'background-color', layout: false, paint: true, composite: true, fps: '~50-60 FPS', cost: 'Sedang (Repaint Piksel)' },
    { property: 'transform (translate/scale)', layout: false, paint: false, composite: true, fps: '120 FPS Mulus', cost: 'Sangat Murah (100% GPU)' },
    { property: 'opacity', layout: false, paint: false, composite: true, fps: '120 FPS Mulus', cost: 'Sangat Murah (100% GPU)' }
  ];

  console.log('Properti CSS'.padEnd(30) + 'Layout?'.padEnd(10) + 'Paint?'.padEnd(10) + 'Composite?'.padEnd(14) + 'Karakteristik Biaya');
  console.log('-'.repeat(75));

  animations.forEach(a => {
    console.log(
      a.property.padEnd(30) +
      (a.layout ? 'YA (CPU)' : 'TIDAK').padEnd(10) +
      (a.paint ? 'YA (CPU)' : 'TIDAK').padEnd(10) +
      (a.composite ? 'YA (GPU)' : 'TIDAK').padEnd(14) +
      `${a.cost} [${a.fps}]`
    );
  });
}

// =========================================================================
// BAGIAN 5: EKSEKUSI PENGUJIAN LENGKAP
// =========================================================================

function main() {
  console.log('='.repeat(75));
  console.log('SIMULASI: CRITICAL RENDERING PATH & BROWSER PIPELINE OPTIMIZATION');
  console.log('='.repeat(75));

  // 1. Uji Konstruksi Render Tree
  console.log('\n1. Membangun Render Tree dari DOM dan CSSOM:');
  const domNodes = [
    { id: 'header', tag: 'header', content: 'Header Navigasi Utama' },
    { id: 'hidden-banner', tag: 'aside', content: 'Promo Popup Tersembunyi' },
    { id: 'ghost-spacer', tag: 'div', content: 'Kotak Transparan Pengisi Ruang' },
    { id: 'main-article', tag: 'article', content: 'Isi Berita Utama' }
  ];

  const cssRules = {
    header: { display: 'block', visibility: 'visible' },
    aside: { display: 'none', visibility: 'visible' },        // Tidak masuk Render Tree!
    div: { display: 'block', visibility: 'hidden' },          // Tetap masuk Render Tree!
    article: { display: 'block', visibility: 'visible' }
  };

  const renderTree = CriticalRenderingPathEngine.buildRenderTree(domNodes, cssRules);
  console.log('\nElemen yang Lolos Masuk ke Render Tree:');
  renderTree.forEach(node => {
    console.log(`  ✅ <${node.tag} id="${node.id}"> -> Memakan Ruang Layout: ${node.takesLayoutSpace}`);
  });

  // 2. Uji Benchmark Layout Thrashing
  benchmarkLayoutThrashing(100);

  // 3. Komparasi Biaya Properti CSS
  compareCssPropertiesCost();

  console.log('\n' + '='.repeat(75));
  console.log('SIMULASI BERHASIL: Pipeline rendering browser terbukti dan teroptimasi!');
  console.log('='.repeat(75));
}

main();
