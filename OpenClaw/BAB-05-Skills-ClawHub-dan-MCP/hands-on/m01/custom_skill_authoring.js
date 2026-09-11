/**
 * LAB SIMULATION: Custom Skill Authoring & Execution Engine
 * 
 * Mensimulasikan:
 * 1. Definisi Manifest Skill (skill.json specification).
 * 2. Strict Parameter Validation (JSON Schema Enforcement).
 * 3. Execution Handler Runtime (API call & business logic).
 * 4. Error Handling & Formatted Chat Output Generation.
 */

// 1. MANIFEST DECLARATION (skill.json)
const cryptoSkillManifest = {
  name: "crypto_currency_ticker",
  version: "1.0.0",
  description: "Mengambil harga mata uang kripto terkini (BTC, ETH, SOL) dalam mata uang IDR atau USD.",
  parameters: {
    type: "object",
    properties: {
      coin: {
        type: "string",
        description: "Simbol aset kripto",
        enum: ["BTC", "ETH", "SOL"]
      },
      currency: {
        type: "string",
        description: "Mata uang fiat pembanding",
        enum: ["IDR", "USD"],
        default: "IDR"
      }
    },
    required: ["coin"]
  }
};

// 2. EXECUTION HANDLER (index.js)
async function cryptoSkillHandler(args) {
  const { coin, currency = "IDR" } = args;

  // Simulasi real-time API market data
  const marketData = {
    BTC: { IDR: 1455000000, USD: 92500, change24h: "+3.4%" },
    ETH: { IDR: 53200000, USD: 3380, change24h: "+1.8%" },
    SOL: { IDR: 3250000, USD: 207, change24h: "+7.2%" }
  };

  const asset = marketData[coin];
  if (!asset) {
    throw new Error(`Koin '${coin}' tidak didukung dalam sistem.`);
  }

  const price = asset[currency];
  return {
    success: true,
    coin,
    currency,
    price,
    change24h: asset.change24h,
    formattedPrice: currency === "IDR" 
      ? `Rp ${price.toLocaleString('id-ID')}` 
      : `$${price.toLocaleString('en-US')}`,
    lastUpdated: new Date().toLocaleTimeString()
  };
}

// 3. OPENCLAW SKILL RUNNER & VALIDATOR
class OpenClawSkillRunner {
  constructor() {
    this.registry = new Map();
  }

  registerSkill(manifest, handlerFn) {
    this.registry.set(manifest.name, { manifest, handler: handlerFn });
    console.log(`📦 [Skill Registered] '${manifest.name}' v${manifest.version}`);
  }

  validateArgs(manifest, args) {
    const schema = manifest.parameters;
    
    // Cek Required Fields
    for (const reqField of schema.required) {
      if (args[reqField] === undefined || args[reqField] === null) {
        throw new Error(`Validasi Gagal: Parameter wajib '${reqField}' tidak ditemukan.`);
      }
    }

    // Cek Enums
    for (const [propName, propRules] of Object.entries(schema.properties)) {
      if (args[propName] && propRules.enum) {
        if (!propRules.enum.includes(args[propName])) {
          throw new Error(`Validasi Gagal: Nilai '${args[propName]}' tidak valid untuk '${propName}'. Pilihan: [${propRules.enum.join(", ")}]`);
        }
      }
    }

    // Apply Defaults
    const resolvedArgs = { ...args };
    for (const [propName, propRules] of Object.entries(schema.properties)) {
      if (resolvedArgs[propName] === undefined && propRules.default) {
        resolvedArgs[propName] = propRules.default;
      }
    }

    return resolvedArgs;
  }

  async executeSkill(skillName, rawArgs) {
    const skill = this.registry.get(skillName);
    if (!skill) throw new Error(`Skill '${skillName}' tidak terdaftar!`);

    console.log(`\n⚙️  [Executing Skill] '${skillName}' dengan argumen:`, JSON.stringify(rawArgs));

    // Validasi
    const validatedArgs = this.validateArgs(skill.manifest, rawArgs);
    console.log(`🛡️  [Validation Passed] Argumen tervalidasi:`, JSON.stringify(validatedArgs));

    // Eksekusi
    const result = await skill.handler(validatedArgs);
    return result;
  }
}

// ======================= PENGUJIAN SKENARIO =======================
async function runLab() {
  console.log("===================================================================");
  console.log("🛠️  PENGUJIAN OPENCLAW CUSTOM SKILL LIFECYCLE");
  console.log("===================================================================\n");

  const runner = new OpenClawSkillRunner();
  runner.registerSkill(cryptoSkillManifest, cryptoSkillHandler);

  // Skenario 1: Eksekusi Sukses (Menggunakan Default Currency IDR)
  console.log("\n--- Skenario 1: Input Sah dari LLM Tool Call ---");
  const res1 = await runner.executeSkill("crypto_currency_ticker", { coin: "BTC" });
  console.log("📊 Data Mentah:", res1);
  console.log(`💬 [Format Chat]: "Harga ${res1.coin} terkini adalah ${res1.formattedPrice} (24h: ${res1.change24h}) pada ${res1.lastUpdated}."`);

  // Skenario 2: Eksekusi Sukses dengan Mata Uang USD
  console.log("\n-------------------------------------------------------------------");
  console.log("--- Skenario 2: Input Spesifik (Coin: SOL, Currency: USD) ---");
  const res2 = await runner.executeSkill("crypto_currency_ticker", { coin: "SOL", currency: "USD" });
  console.log(`💬 [Format Chat]: "Harga ${res2.coin} terkini adalah ${res2.formattedPrice} (24h: ${res2.change24h})."`);

  // Skenario 3: Input Gagal Validasi (Koin tidak terdaftar dalam enum)
  console.log("\n-------------------------------------------------------------------");
  console.log("--- Skenario 3: Penanganan Input Rusak / Tidak Valid dari LLM ---");
  try {
    await runner.executeSkill("crypto_currency_ticker", { coin: "DOGE" });
  } catch (err) {
    console.error(`❌ ${err.message}`);
  }

  console.log("\n===================================================================");
  console.log(" Kesimpulan:");
  console.log("1. Manifest mendefinisikan kontrak parameter yang dapat dipahami LLM.");
  console.log("2. Runner memvalidasi parameter ketat sebelum mengeksekusi kode.");
  console.log("3. Data JSON terstruktur memudahkan LLM merespons dalam format ramah manusia.");
}

runLab();
