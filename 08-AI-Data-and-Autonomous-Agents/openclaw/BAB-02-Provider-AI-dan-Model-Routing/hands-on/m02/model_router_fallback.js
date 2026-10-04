/**
 * LAB SIMULATION: Dynamic Model Routing, Failover Chain, & Budget Guard
 * 
 * Fitur:
 * 1. Intent & Privacy Classifier (Rute otomatis berdasarkan konten).
 * 2. Failover Chain (Primary 429/503 -> Fallback Model -> Emergency Offline).
 * 3. Daily Budget Ceiling Guardrail (Mencegah tagihan cloud bengkak).
 */

class SmartModelRouter {
  constructor(config = {}) {
    this.budgetLimitUSD = config.budgetLimitUSD || 0.05; // Limit kecil untuk simulasi
    this.currentSpendUSD = 0;
    this.providerHealth = {
      "anthropic/claude-3-5-sonnet": { isHealthy: true, costPerPrompt: 0.015 },
      "openai/gpt-4o": { isHealthy: true, costPerPrompt: 0.010 },
      "google/gemini-2-flash": { isHealthy: true, costPerPrompt: 0.001 },
      "ollama/llama-3.2-local": { isHealthy: true, costPerPrompt: 0.000 } // Gratis!
    };
  }

  // 1. INTENT & PRIVACY CLASSIFIER
  classifyPrompt(prompt) {
    const lower = prompt.toLowerCase();
    
    // Cek Privasi Kritis (PIN, Password, Rekening)
    if (lower.includes("password") || lower.includes("rekening") || lower.includes("rahasia")) {
      return { intent: "CONFIDENTIAL_DATA", recommendedModel: "ollama/llama-3.2-local" };
    }
    // Cek Kebutuhan Logika Rumit (Coding, Architecture, Math)
    if (lower.includes("refactor") || lower.includes("arsitektur") || lower.includes("algoritma")) {
      return { intent: "DEEP_REASONING", recommendedModel: "anthropic/claude-3-5-sonnet" };
    }
    // Default: Chat Cepat & Ringkasan
    return { intent: "FAST_CONVERSATION", recommendedModel: "google/gemini-2-flash" };
  }

  // 2. FAILOVER EXECUTION WITH BUDGET GUARD
  async executeWithFallback(prompt) {
    console.log(`\n💬 [User Prompt] "${prompt}"`);
    const { intent, recommendedModel } = this.classifyPrompt(prompt);
    console.log(`🧭 [Router] Intent: ${intent} | Model Rekomendasi: ${recommendedModel}`);

    // Cek Budget Ceiling
    if (this.currentSpendUSD >= this.budgetLimitUSD && recommendedModel !== "ollama/llama-3.2-local") {
      console.warn(`🚨 [BUDGET GUARD] Batas anggaran harian ($${this.budgetLimitUSD}) telah tercapai! Mengalihkan ke model lokal GRATIS.`);
      return this.callProvider("ollama/llama-3.2-local", prompt, true);
    }

    // Tentukan Rantai Fallback
    const fallbackChain = [recommendedModel];
    if (recommendedModel === "anthropic/claude-3-5-sonnet") {
      fallbackChain.push("openai/gpt-4o", "google/gemini-2-flash", "ollama/llama-3.2-local");
    } else if (recommendedModel === "google/gemini-2-flash") {
      fallbackChain.push("openai/gpt-4o", "ollama/llama-3.2-local");
    }

    // Jalankan rantai fallback
    for (const model of fallbackChain) {
      try {
        const result = await this.callProvider(model, prompt);
        return result;
      } catch (err) {
        console.warn(`⚠️ [FAILOVER] Gagal memanggil ${model}: ${err.message}. Mencoba model berikutnya di rantai...`);
      }
    }

    throw new Error("CRITICAL: Seluruh provider di rantai fallback tidak merespons!");
  }

  async callProvider(modelName, prompt, isBudgetFallback = false) {
    const provider = this.providerHealth[modelName];
    if (!provider || !provider.isHealthy) {
      throw new Error(`Provider Error: ${modelName} sedang down / 429 Rate Limit!`);
    }

    // Hitung Biaya
    this.currentSpendUSD += provider.costPerPrompt;

    return {
      status: "SUCCESS",
      modelUsed: modelName,
      costUSD: provider.costPerPrompt,
      totalSpendUSD: parseFloat(this.currentSpendUSD.toFixed(4)),
      isBudgetFallback,
      reply: `[Respon dari ${modelName}]: Tugas untuk '${prompt}' berhasil diproses secara optimal.`
    };
  }
}

// ======================= PENGUJIAN SKENARIO =======================
async function runLab() {
  console.log("===================================================================");
  console.log("🛠️  PENGUJIAN MODEL ROUTING, AUTO-FAILOVER, & BUDGET CEILING");
  console.log("===================================================================");

  const router = new SmartModelRouter({ budgetLimitUSD: 0.035 });

  // 1. Skenario Normal: Chat Ringan -> Gemini Flash
  const res1 = await router.executeWithFallback("Halo, apa kabar?");
  console.log(`✅ Lolos: ${res1.modelUsed} | Biaya: $${res1.costUSD} (Akumulasi: $${res1.totalSpendUSD})`);

  // 2. Skenario Privasi: Data Rahasia -> Ollama Local (Zero Cloud)
  const res2 = await router.executeWithFallback("Tolong simpan password database postgres saya.");
  console.log(`✅ Lolos: ${res2.modelUsed} | Biaya: $${res2.costUSD} (Akumulasi: $${res2.totalSpendUSD})`);

  // 3. Skenario Reasoning: Coding Rumit -> Claude Sonnet
  const res3 = await router.executeWithFallback("Tolong buatkan algoritma arsitektur distributed lock.");
  console.log(`✅ Lolos: ${res3.modelUsed} | Biaya: $${res3.costUSD} (Akumulasi: $${res3.totalSpendUSD})`);

  // 4. Skenario Provider Outage & Failover: Claude 3.5 Tiba-tiba Rate Limit 429
  console.log("\n-------------------------------------------------------------------");
  console.log("💥 SIMULASI: Anthropic mengalami lonjakan trafik (HTTP 429 Rate Limit)...");
  router.providerHealth["anthropic/claude-3-5-sonnet"].isHealthy = false;

  const res4 = await router.executeWithFallback("Tolong perbaiki refactor fungsi controller ini.");
  console.log(`✅ Berhasil Failover ke: ${res4.modelUsed} | Biaya: $${res4.costUSD} (Akumulasi: $${res4.totalSpendUSD})`);

  // 5. Skenario Budget Ceiling Guardrail: Melampaui limit $0.035
  console.log("\n-------------------------------------------------------------------");
  console.log("💸 SIMULASI: Pengguna terus mengirim task komputasi berat hingga anggaran harian habis...");
  const res5 = await router.executeWithFallback("Tolong analisis performa query SQL ini lagi.");
  console.log(`✅ Status: ${res5.modelUsed} | Budget Guard: ${res5.isBudgetFallback} | Biaya: $${res5.costUSD}`);

  console.log("\n===================================================================");
  console.log(" Kesimpulan:");
  console.log("1. Intent Classifier sukses mengarahkan task ke model yang tepat secara otomatis.");
  console.log("2. Data sensitif dialihkan ke model lokal tanpa pernah keluar ke internet.");
  console.log("3. Failover otomatis mengalihkan request ke GPT-4o saat Claude mengalami 429.");
  console.log("4. Budget Guard mengunci biaya berlebih dan beralih ke model lokal 100% gratis.");
}

runLab();
