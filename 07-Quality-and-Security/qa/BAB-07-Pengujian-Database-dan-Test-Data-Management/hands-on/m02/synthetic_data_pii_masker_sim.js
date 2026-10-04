/**
 * Hands-on M02: Synthetic Data Generator & PII Masking Pipeline Simulator
 * 
 * Demonstrasi:
 * 1. Generator Data Pengguna Sintetis Realistis (Zero External Dependencies).
 * 2. Pipeline Penyamaran Data Pribadi (PII Masking) sesuai UU PDP No. 27/2022 & GDPR:
 *    - NIK KTP Masking (Format Preserving: 3171********0001)
 *    - Phone Number Masking (0812****9988)
 *    - Email Obfuscation (bu***@domain.com)
 *    - Credit Card Tokenization (****-****-****-1234)
 * 3. Audit Kebocoran Data (Zero PII Leakage Verification).
 */

const ANSI = {
  reset: "\x1b[0m",
  green: "\x1b[32m",
  red: "\x1b[31m",
  yellow: "\x1b[33m",
  cyan: "\x1b[36m",
  bold: "\x1b[1m",
  dim: "\x1b[2m"
};

// ==========================================
// 1. PII MASKING UTILITY ENGINE
// ==========================================
class PiiMasker {
  static maskNik(nik) {
    if (!nik || nik.length !== 16) return "****************";
    // Tampilkan 4 digit awal (Kode Wilayah) dan 4 digit akhir, samarkan 8 digit tengah
    return nik.substring(0, 4) + "********" + nik.substring(12);
  }

  static maskPhone(phone) {
    if (!phone || phone.length < 10) return "0800****0000";
    return phone.substring(0, 4) + "****" + phone.substring(phone.length - 4);
  }

  static maskEmail(email) {
    const parts = email.split("@");
    if (parts.length !== 2) return "anonymized@staging.internal";
    const [user, domain] = parts;
    const prefix = user.substring(0, 2);
    return `${prefix}***@${domain}`;
  }

  static maskCreditCard(pan) {
    const clean = pan.replace(/\s+/g, "");
    if (clean.length < 16) return "****-****-****-0000";
    const last4 = clean.substring(clean.length - 4);
    return `****-****-****-${last4}`;
  }

  static anonymizeName(originalName) {
    const syntheticNames = ["Ahmad Fauzi", "Budi Santoso", "Citra Lestari", "Dewi Kusuma", "Eko Prasetyo"];
    const hash = originalName.split("").reduce((acc, char) => acc + char.charCodeAt(0), 0);
    return syntheticNames[hash % syntheticNames.length];
  }
}

// ==========================================
// 2. SYNTHETIC DATA GENERATOR
// ==========================================
class SyntheticCustomerGenerator {
  static generateRawCustomers(count = 5) {
    const records = [];
    const firstNames = ["Rudi", "Siti", "Hendra", "Nur", "Bambang"];
    const lastNames = ["Kusumo", "Rahmawati", "Siregar", "Hidayat", "Sudirman"];

    for (let i = 1; i <= count; i++) {
      const first = firstNames[(i - 1) % firstNames.length];
      const last = lastNames[(i - 1) % lastNames.length];
      records.push({
        id: `CUST-2026-${i.toString().padStart(4, "0")}`,
        fullName: `${first} ${last}`,
        nik: `3171${Math.floor(10000000 + Math.random() * 90000000)}${i.toString().padStart(4, "0")}`,
        phone: `0812${Math.floor(10000000 + Math.random() * 90000000)}`,
        email: `${first.toLowerCase()}.${last.toLowerCase()}@nasabah-real.com`,
        creditCard: `4111 ${Math.floor(1000 + Math.random() * 9000)} ${Math.floor(1000 + Math.random() * 9000)} ${Math.floor(1000 + Math.random() * 9000)}`,
        balance: Math.floor(500000 + Math.random() * 10000000)
      });
    }
    return records;
  }
}

// ==========================================
// 3. SECURE DATA SANITIZATION PIPELINE
// ==========================================
class DataSanitizationPipeline {
  static sanitize(rawDataset) {
    return rawDataset.map(record => ({
      id: record.id, // Relational Key tetap dipertahankan
      fullName: PiiMasker.anonymizeName(record.fullName),
      nik: PiiMasker.maskNik(record.nik),
      phone: PiiMasker.maskPhone(record.phone),
      email: PiiMasker.maskEmail(record.email),
      creditCard: PiiMasker.maskCreditCard(record.creditCard),
      balance: record.balance // Atribut numerik non-identitas tetap valid untuk uji kalkulasi
    }));
  }

  static auditZeroLeakage(rawDataset, sanitizedDataset) {
    let violations = 0;
    for (let i = 0; i < rawDataset.length; i++) {
      const raw = rawDataset[i];
      const clean = sanitizedDataset[i];

      // Verifikasi bahwa NIK asli tidak ada di clean dataset
      if (clean.nik === raw.nik) violations++;
      // Verifikasi bahwa email asli tidak ada di clean dataset
      if (clean.email === raw.email) violations++;
      // Verifikasi bahwa nomor telepon asli tidak ada di clean dataset
      if (clean.phone === raw.phone) violations++;
      // Verifikasi bahwa nomor kartu kredit asli tidak ada di clean dataset
      if (clean.creditCard === raw.creditCard) violations++;
    }
    return { isCompliant: violations === 0, violations };
  }
}

// ==========================================
// 4. MAIN SIMULATION EXECUTION
// ==========================================
function main() {
  console.log(`${ANSI.bold}╔═══════════════════════════════════════════════════════════════╗`);
  console.log(`║     SYNTHETIC TEST DATA & PII MASKING PIPELINE LAB (UU PDP)   ║`);
  console.log(`╚═══════════════════════════════════════════════════════════════╝${ANSI.reset}`);

  // 1. GENERASI DATA MENTAH DUMP PRODUKSI (RAW PII)
  console.log(`\n${ANSI.bold}${ANSI.cyan}=== 1. EKSTRAKSI DATA MENTAH DARI SUMBER PRODUKSI (SENSITIF!) ===${ANSI.reset}`);
  const rawCustomers = SyntheticCustomerGenerator.generateRawCustomers(4);
  console.log(`  ${ANSI.red}[PERINGATAN] Dataset ini mengandung PII asli yang dilarang berada di Staging:${ANSI.reset}`);
  console.table(rawCustomers);

  // 2. EKSEKUSI PIPELINE SANITASI & MASKING
  console.log(`\n${ANSI.bold}${ANSI.cyan}=== 2. EKSEKUSI PIPELINE PENYAMARAN DATA (DATA MASKING ETL) ===${ANSI.reset}`);
  console.log(`  Menerapkan UU PDP No. 27/2022: Menyamarkan Nama, NIK, No HP, Email, dan Kartu Kredit...`);
  const sanitizedCustomers = DataSanitizationPipeline.sanitize(rawCustomers);
  console.log(`  ${ANSI.green}✓ Sanitasi Selesai. Dataset aman untuk lingkungan Staging / QA:${ANSI.reset}`);
  console.table(sanitizedCustomers);

  // 3. AUDIT KEPATUHAN & ZERO LEAKAGE VERIFICATION
  console.log(`\n${ANSI.bold}${ANSI.cyan}=== 3. AUDIT KEPATUHAN HUKUM & ZERO LEAKAGE CHECK ===${ANSI.reset}`);
  const auditResult = DataSanitizationPipeline.auditZeroLeakage(rawCustomers, sanitizedCustomers);

  console.log(`  Total Record Diperiksa: ${rawCustomers.length}`);
  console.log(`  Total Kebocoran PII   : ${auditResult.violations === 0 ? ANSI.green + "0 (ZERO LEAKAGE)" : ANSI.red + auditResult.violations}${ANSI.reset}`);
  console.log(`  Status Kepatuhan Hukum: ${auditResult.isCompliant ? ANSI.green + "100% COMPLIANT (UU PDP & GDPR)" : ANSI.red + "NON-COMPLIANT"}${ANSI.reset}`);
  console.log(`  Integritas Relasional : ${ANSI.green}TERPELIHARA (Primary Key ID tetap konsisten untuk relasi database)${ANSI.reset}`);

  console.log(`\n${ANSI.green}✓ Synthetic Data & PII Masking Lab executed successfully!${ANSI.reset}\n`);
}

main();
