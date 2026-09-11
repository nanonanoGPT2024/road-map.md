/**
 * SIMULATOR: REACT SERVER COMPONENTS (RSC) STREAMING SSR & SERVER ACTIONS ENGINE
 * Modul 01: React Server Components (RSC), Streaming SSR, & Server Actions
 *
 * Mendemonstrasikan:
 * 1. HTTP Chunked Transfer Encoding Streaming SSR dengan batasan React <Suspense>.
 * 2. Cangkang instan (Shell & Skeleton) dikirim dalam milidetik pertama (Chunk 1).
 * 3. Data query lambat dialirkan di latar belakang dan disuntikkan ke DOM (Chunk 2).
 * 4. Mesin Server Actions ('use server') dengan validasi skema input & revalidasi cache instan.
 *
 * Jalankan: node rsc_streaming_ssr_sim.js
 */

const http = require('http');

// =========================================================================
// BAGIAN 1: DATABASE PRIMER SIMULASI (AKSES LANGSUNG SERVER COMPONENT)
// =========================================================================

class MockDatabase {
  constructor() {
    this.invoices = [
      { id: 'INV-101', customer: 'PT Nusantara Jaya', amount: 15000000, status: 'PAID' },
      { id: 'INV-102', customer: 'CV Maju Lancar', amount: 4500000, status: 'PENDING' }
    ];
  }

  // Simulasi query berat yang memakan waktu (misal: agregasi histori transaksi)
  async fetchSlowInvoices() {
    await new Promise(r => setTimeout(r, 120)); // Delay 120ms
    return this.invoices;
  }

  async insertInvoice(customer, amount) {
    const newInv = {
      id: `INV-${Math.floor(100 + Math.random() * 900)}`,
      customer,
      amount: Number(amount),
      status: 'PENDING'
    };
    this.invoices.push(newInv);
    return newInv;
  }
}

const db = new MockDatabase();

// =========================================================================
// BAGIAN 2: MESIN STREAMING SSR (CHUNKED TRANSFER ENCODING)
// =========================================================================

class StreamingSSREngine {
  static async handleStreamingRequest(res) {
    // Header HTTP Chunked Transfer Encoding
    res.writeHead(200, {
      'Content-Type': 'text/html; charset=utf-8',
      'Transfer-Encoding': 'chunked',
      'X-Content-Type-Options': 'nosniff'
    });

    console.log('\n[CHUNK 1: INSTAN] Mengirimkan Cangkang Halaman & Skeleton Loader (<Suspense fallback>)...');
    
    // CHUNK 1: Navigasi, Header, dan Skeleton Loader (Langsung dikirim ke browser!)
    const chunk1 = `
      <!DOCTYPE html>
      <html lang="id">
      <head>
        <meta charset="UTF-8">
        <title>RSC Streaming SSR Demo</title>
        <style>
          body { font-family: sans-serif; padding: 20px; background: #0f172a; color: #f8fafc; }
          .skeleton { background: #334155; height: 80px; border-radius: 8px; animation: pulse 1.5s infinite; }
          @keyframes pulse { 0% { opacity: 0.6; } 50% { opacity: 1; } 100% { opacity: 0.6; } }
          table { width: 100%; border-collapse: collapse; margin-top: 10px; }
          th, td { border: 1px solid #475569; padding: 8px 12px; text-align: left; }
          th { background: #1e293b; }
        </style>
      </head>
      <body>
        <header>
          <h1>⚡ Portal Keuangan Enterprise (Next.js 14 RSC)</h1>
          <p>Navigasi Utama | Status: Online</p>
        </header>
        <hr/>
        <main>
          <h2>Daftar Faktur Pembayaran</h2>
          <!-- SUSPENSE BOUNDARY PLACEHOLDER -->
          <div id="suspense-fallback">
            <div class="skeleton"></div>
            <p>⏳ Mengalirkan data komponen lambat dari database server...</p>
          </div>
        </main>
    `;
    res.write(chunk1);

    // SERVER COMPONENT ASINKRON MENJALANKAN QUERY LAMBAT
    const invoices = await db.fetchSlowInvoices();
    console.log(`[CHUNK 2: STREAM DATA] Query DB selesai! Mengalirkan tabel faktur (${invoices.length} baris)...`);

    // CHUNK 2: Konten Asli + Script Swap Pengganti Skeleton
    const rowsHtml = invoices.map(inv => `
      <tr>
        <td>${inv.id}</td>
        <td>${inv.customer}</td>
        <td>Rp ${inv.amount.toLocaleString('id-ID')}</td>
        <td><b>${inv.status}</b></td>
      </tr>
    `).join('');

    const chunk2 = `
      <template id="invoices-content">
        <table>
          <thead><tr><th>ID Faktur</th><th>Pelanggan</th><th>Nominal</th><th>Status</th></tr></thead>
          <tbody>${rowsHtml}</tbody>
        </table>
      </template>

      <!-- SCRIPT SWAP: Mengganti skeleton dengan konten asli seketika di DOM browser -->
      <script>
        (function() {
          const fallback = document.getElementById('suspense-fallback');
          const content = document.getElementById('invoices-content');
          if (fallback && content) {
            fallback.replaceWith(content.content.cloneNode(true));
            console.log('✅ Chunks Streaming SSR berhasil disuntikkan ke DOM!');
          }
        })();
      </script>
      </body></html>
    `;

    res.write(chunk2);
    res.end(); // Akhiri stream HTTP
  }
}

// =========================================================================
// BAGIAN 3: MESIN SERVER ACTIONS ('USE SERVER')
// =========================================================================

class ServerActionsEngine {
  // Simulasi pemanggilan Server Action dari form submit
  static async executeAction(actionId, payload) {
    console.log(`\n▶️ [SERVER ACTION INVOKED] ID: ${actionId}`);

    if (actionId === 'action_create_invoice') {
      const { customer, amount } = payload;

      // 1. Validasi Skema (Zod-like validation)
      if (!customer || customer.trim().length < 3) {
        throw new Error('Validasi Gagal: Nama pelanggan minimal 3 karakter!');
      }
      if (!amount || isNaN(amount) || amount <= 0) {
        throw new Error('Validasi Gagal: Nominal faktur harus bernilai positif!');
      }

      // 2. Eksekusi Mutasi Database Langsung
      const created = await db.insertInvoice(customer, amount);
      console.log(`  ✅ [DATABASE MUTATION] Faktur berhasil dibuat: ${created.id} (Rp ${created.amount.toLocaleString('id-ID')})`);

      // 3. Revalidasi Cache Halaman (revalidatePath)
      console.log('  🔄 [REVALIDATE CACHE] revalidatePath("/invoices") memicu regenerasi RSC payload.');

      return {
        success: true,
        data: created,
        revalidatedPaths: ['/invoices']
      };
    }

    throw new Error(`Server Action tidak dikenali: ${actionId}`);
  }
}

// =========================================================================
// BAGIAN 4: EKSEKUSI PENGUJIAN SKENARIO LENGKAP
// =========================================================================

async function main() {
  console.log('='.repeat(75));
  console.log('SIMULASI: REACT SERVER COMPONENTS (RSC), STREAMING SSR & SERVER ACTIONS');
  console.log('='.repeat(75));

  // --- PENGUJIAN A: STREAMING SSR SERVER ---
  console.log('\nA. Memulai Server Mock Streaming SSR di Port 3456...');

  const server = http.createServer(async (req, res) => {
    if (req.method === 'GET') {
      await StreamingSSREngine.handleStreamingRequest(res);
    }
  });

  server.listen(3456, async () => {
    console.log('  Server aktif di http://localhost:3456');
    console.log('  Melakukan HTTP Client Request untuk merekam aliran Chunks...');

    // Simulasi client HTTP yang membaca chunk demi chunk
    http.get('http://localhost:3456', (res) => {
      let chunkIndex = 1;
      res.on('data', (chunk) => {
        console.log(`  📥 [CLIENT RECEIVE CHUNK #${chunkIndex++}] Menerima ${chunk.length} bytes data stream.`);
      });

      res.on('end', async () => {
        console.log('  🏁 Client selesai menerima seluruh stream HTML.');
        server.close();

        // --- PENGUJIAN B: SERVER ACTIONS MUTATION ---
        console.log('\n' + '-'.repeat(75));
        console.log('B. Pengujian Mutasi Data via Server Actions ("use server"):');
        console.log('-'.repeat(75));

        // Kasus 1: Input Sah
        try {
          await ServerActionsEngine.executeAction('action_create_invoice', {
            customer: 'PT Mega Korpora',
            amount: 25000000
          });
        } catch (err) {
          console.error(`  ❌ Error: ${err.message}`);
        }

        // Kasus 2: Input Cacat (Validasi Gagal)
        try {
          console.log('\nMenguji pemanggilan Server Action dengan input nominal negatif:');
          await ServerActionsEngine.executeAction('action_create_invoice', {
            customer: 'Budi',
            amount: -5000
          });
        } catch (err) {
          console.log(`  🛡️ [VALIDASI INPUT DITEGAKKAN] ${err.message}`);
        }

        console.log('\n' + '='.repeat(75));
        console.log('SIMULASI BERHASIL: Streaming SSR & Server Actions berjalan sempurna!');
        console.log('='.repeat(75));
      });
    });
  });
}

main();
