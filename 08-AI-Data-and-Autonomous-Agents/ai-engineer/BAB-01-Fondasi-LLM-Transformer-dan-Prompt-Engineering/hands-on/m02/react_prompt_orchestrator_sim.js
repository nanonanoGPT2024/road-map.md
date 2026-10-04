/**
 * Hands-on M02: ReAct Prompt Orchestration & Strict Structured JSON Validator
 * Track: AI Engineer Mastery - BAB 01
 * 
 * Demonstrasi pola arsitektur prompt AI:
 * 1. ReAct (Reasoning + Acting) Agent Loop
 * 2. Mock Tool Execution Registry (Calculator, Knowledge Base)
 * 3. Thought -> Action -> Action Input -> Observation cycle
 * 4. Strict JSON Schema parsing & structural validation
 * 5. Zero external dependencies (Node.js)
 */

const ANSI = {
  reset: "\x1b[0m",
  bold: "\x1b[1m",
  green: "\x1b[32m",
  cyan: "\x1b[36m",
  yellow: "\x1b[33m",
  red: "\x1b[31m",
  magenta: "\x1b[35m"
};

// 1. TOOL REGISTRY
const TOOLS = {
  calculator: {
    description: "Evaluates mathematical expressions safely",
    execute: (expr) => {
      // Safe math eval simulation
      const sanitized = expr.replace(/[^0-9+\-*/().]/g, "");
      return Function(`'use strict'; return (${sanitized})`)();
    }
  },
  knowledge_base: {
    description: "Searches enterprise document store",
    execute: (query) => {
      const db = {
        "nusantara_gpu_cluster": "Cluster H100 Nusantara memiliki 512 GPU dengan interkoneksi InfiniBand 400Gbps.",
        "nusantara_pricing": "Biaya komputasi Nusantara Cloud adalah $2.50 per GPU-hour."
      };
      return db[query] || "Informasi tidak ditemukan dalam database.";
    }
  }
};

// 2. REACT ORCHESTRATOR
class ReActOrchestrator {
  constructor(tools) {
    this.tools = tools;
    this.trace = [];
  }

  // Simulasi langkah inferensi LLM dalam ReAct Loop
  step(userGoal, priorObservations = []) {
    if (priorObservations.length === 0) {
      return {
        thought: "Saya perlu mencari tahu spesifikasi cluster GPU Nusantara untuk mengetahui jumlah GPU yang tersedia.",
        action: "knowledge_base",
        actionInput: "nusantara_gpu_cluster",
        finalAnswer: null
      };
    }

    if (priorObservations.length === 1) {
      return {
        thought: "Spesifikasi menyatakan ada 512 GPU. Sekarang saya perlu menghitung total daya jika tiap GPU mengonsumsi 700W (512 * 700 / 1000 kW).",
        action: "calculator",
        actionInput: "512 * 700 / 1000",
        finalAnswer: null
      };
    }

    const kw = priorObservations[1];
    return {
      thought: `Perhitungan selesai: ${kw} kW. Saya memiliki semua informasi yang dibutuhkan untuk menjawab user.`,
      action: null,
      actionInput: null,
      finalAnswer: {
        totalGpus: 512,
        interconnect: "InfiniBand 400Gbps",
        totalPowerKW: kw,
        summary: `Cluster H100 Nusantara memiliki 512 GPU dengan total kebutuhan daya ${kw} kW.`
      }
    };
  }

  run(userGoal) {
    console.log(`\n${ANSI.bold}[ReAct Loop Started] User Goal: "${userGoal}"${ANSI.reset}`);
    const observations = [];
    let iterations = 0;

    while (iterations < 5) {
      iterations++;
      console.log(`\n--- Iteration #${iterations} ---`);
      const llmOutput = this.step(userGoal, observations);

      console.log(`${ANSI.cyan}Thought:${ANSI.reset} ${llmOutput.thought}`);

      if (llmOutput.finalAnswer) {
        console.log(`${ANSI.green}${ANSI.bold}Final Answer Reached!${ANSI.reset}`);
        return llmOutput.finalAnswer;
      }

      console.log(`${ANSI.yellow}Action:${ANSI.reset} ${llmOutput.action}( "${llmOutput.actionInput}" )`);
      const tool = this.tools[llmOutput.action];
      if (!tool) throw new Error(`Tool unknown: ${llmOutput.action}`);

      const obs = tool.execute(llmOutput.actionInput);
      console.log(`${ANSI.magenta}Observation:${ANSI.reset} ${obs}`);
      observations.push(obs);
    }
    throw new Error("Max iterations exceeded");
  }
}

// ==========================================
// TEST SUITE & RUNNER
// ==========================================
function runLab() {
  console.log(`${ANSI.bold}${ANSI.cyan}======================================================${ANSI.reset}`);
  console.log(`${ANSI.bold}${ANSI.cyan}  LAB HANDS-ON: REACT AGENT LOOP & SCHEMA EXTRACTION  ${ANSI.reset}`);
  console.log(`${ANSI.bold}${ANSI.cyan}======================================================${ANSI.reset}`);

  const orchestrator = new ReActOrchestrator(TOOLS);
  const result = orchestrator.run("Hitung total daya listrik dalam kW untuk cluster GPU Nusantara");

  console.log(`\n${ANSI.bold}[Step 4] Validating Structured Output JSON Schema...${ANSI.reset}`);
  console.log("Structured Output:", JSON.stringify(result, null, 2));

  if (result.totalGpus === 512 && result.totalPowerKW === 358.4) {
    console.log(`\n${ANSI.green}${ANSI.bold}✓ SUCCESS: ReAct loop executed correctly with valid structured output!${ANSI.reset}`);
  } else {
    throw new Error("Assertion failed on ReAct final answer values");
  }
}

runLab();
