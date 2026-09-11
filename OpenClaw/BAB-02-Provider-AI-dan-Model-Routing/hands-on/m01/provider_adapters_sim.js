/**
 * LAB SIMULATION: OpenClaw Universal Provider Adapters
 * 
 * Mensimulasikan Adapter Pattern yang menormalisasi format permintaan
 * dan tanggapan lintas 4 provider AI utama:
 * 1. Anthropic Claude (Messages API)
 * 2. OpenAI (Chat Completions API)
 * 3. Google Gemini (Generative Language API)
 * 4. Ollama (Local Daemon API)
 */

class UniversalAIAdapter {
  // Input standar OpenClaw
  static createUnifiedRequest(userPrompt, systemInstruction, toolName = null) {
    return {
      prompt: userPrompt,
      system: systemInstruction,
      temperature: 0.7,
      tool: toolName ? { name: toolName, description: "Ambil data sistem", parameters: { type: "object", properties: { query: { type: "string" } } } } : null
    };
  }

  // 1. ANTHROPIC CLAUDE ADAPTER
  static formatForAnthropic(req, apiKey) {
    const payload = {
      model: "claude-3-5-sonnet-20241022",
      max_tokens: 1024,
      system: req.system,
      messages: [{ role: "user", content: req.prompt }]
    };
    if (req.tool) {
      payload.tools = [{
        name: req.tool.name,
        description: req.tool.description,
        input_schema: req.tool.parameters
      }];
    }
    const headers = {
      "x-api-key": apiKey.substring(0, 7) + "...",
      "anthropic-version": "2023-06-01",
      "content-type": "application/json"
    };
    return { provider: "Anthropic", endpoint: "https://api.anthropic.com/v1/messages", headers, payload };
  }

  // 2. OPENAI ADAPTER
  static formatForOpenAI(req, apiKey) {
    const payload = {
      model: "gpt-4o",
      messages: [
        { role: "system", content: req.system },
        { role: "user", content: req.prompt }
      ],
      temperature: req.temperature
    };
    if (req.tool) {
      payload.tools = [{
        type: "function",
        function: {
          name: req.tool.name,
          description: req.tool.description,
          parameters: req.tool.parameters
        }
      }];
    }
    const headers = {
      "Authorization": `Bearer ${apiKey.substring(0, 7)}...`,
      "content-type": "application/json"
    };
    return { provider: "OpenAI", endpoint: "https://api.openai.com/v1/chat/completions", headers, payload };
  }

  // 3. GOOGLE GEMINI ADAPTER
  static formatForGemini(req, apiKey) {
    const payload = {
      systemInstruction: { parts: [{ text: req.system }] },
      contents: [{ role: "user", parts: [{ text: req.prompt }] }]
    };
    if (req.tool) {
      payload.tools = [{
        functionDeclarations: [{
          name: req.tool.name,
          description: req.tool.description,
          parameters: req.tool.parameters
        }]
      }];
    }
    const headers = {
      "x-goog-api-key": apiKey.substring(0, 7) + "...",
      "content-type": "application/json"
    };
    return { provider: "Google Gemini", endpoint: "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent", headers, payload };
  }

  // 4. OLLAMA LOCAL ADAPTER (ZERO CLOUD, ZERO AUTH)
  static formatForOllama(req) {
    const payload = {
      model: "llama3.2:3b",
      messages: [
        { role: "system", content: req.system },
        { role: "user", content: req.prompt }
      ],
      stream: false
    };
    const headers = {
      "content-type": "application/json"
    };
    return { provider: "Ollama Local", endpoint: "http://localhost:11434/api/chat", headers, payload };
  }
}

// ======================= PENGUJIAN NORMALISASI =======================
console.log("===================================================================");
console.log("🛠️  PENGUJIAN MULTI-PROVIDER ADAPTER TRANSLATION");
console.log("===================================================================\n");

const sampleRequest = UniversalAIAdapter.createUnifiedRequest(
  "Tolong periksa status server produksi!",
  "Anda adalah asisten DevOps otonom bernama OpenClaw.",
  "check_server"
);

console.log("📝 Permintaan Terpadu Asli (OpenClaw Internal Format):");
console.log(JSON.stringify(sampleRequest, null, 2));

console.log("\n-------------------------------------------------------------------");
console.log("1. Format Payload untuk Anthropic Claude Messages API:");
const anthropicReq = UniversalAIAdapter.formatForAnthropic(sampleRequest, "sk-ant-api03-secret12345");
console.log(`Endpoint: ${anthropicReq.endpoint}`);
console.log(`Headers : ${JSON.stringify(anthropicReq.headers)}`);
console.log(`Payload : ${JSON.stringify(anthropicReq.payload, null, 2)}`);

console.log("\n-------------------------------------------------------------------");
console.log("2. Format Payload untuk OpenAI Chat Completions API:");
const openAiReq = UniversalAIAdapter.formatForOpenAI(sampleRequest, "sk-proj-openai998877");
console.log(`Endpoint: ${openAiReq.endpoint}`);
console.log(`Headers : ${JSON.stringify(openAiReq.headers)}`);
console.log(`Payload : ${JSON.stringify(openAiReq.payload, null, 2)}`);

console.log("\n-------------------------------------------------------------------");
console.log("3. Format Payload untuk Google Gemini Generative API:");
const geminiReq = UniversalAIAdapter.formatForGemini(sampleRequest, "AIzaSyGeminiKey9911");
console.log(`Endpoint: ${geminiReq.endpoint}`);
console.log(`Headers : ${JSON.stringify(geminiReq.headers)}`);
console.log(`Payload : ${JSON.stringify(geminiReq.payload, null, 2)}`);

console.log("\n-------------------------------------------------------------------");
console.log("4. Format Payload untuk Ollama Local Daemon (100% Offline):");
const ollamaReq = UniversalAIAdapter.formatForOllama(sampleRequest);
console.log(`Endpoint: ${ollamaReq.endpoint}`);
console.log(`Headers : ${JSON.stringify(ollamaReq.headers)}`);
console.log(`Payload : ${JSON.stringify(ollamaReq.payload, null, 2)}`);

console.log("\n===================================================================");
console.log(" Kesimpulan:");
console.log("1. Satu prompt terpadu berhasil diterjemahkan ke 4 format payload vendor berbeda.");
console.log("2. Skema tool calling otomatis di-adaptasi (Anthropic input_schema vs OpenAI function vs Gemini functionDeclarations).");
console.log("3. Ollama berjalan secara lokal tanpa memerlukan API key eksternal.");
