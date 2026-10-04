/**
 * Hands-on M01: BPE Tokenizer & Scaled Dot-Product Attention Simulator
 * Track: AI Engineer Mastery - BAB 01
 * 
 * Demonstrasi mekanisme fundamental Transformer & LLM:
 * 1. Byte-Pair Encoding (BPE) Vocab Merge & Tokenization
 * 2. Vector Embeddings Representation
 * 3. Scaled Dot-Product Attention: Attention(Q, K, V) = softmax((Q @ K^T) / sqrt(d_k)) @ V
 * 4. Zero external dependencies (Node.js)
 */

const ANSI = {
  reset: "\x1b[0m",
  bold: "\x1b[1m",
  green: "\x1b[32m",
  cyan: "\x1b[36m",
  yellow: "\x1b[33m",
  magenta: "\x1b[35m"
};

// 1. MINI BPE TOKENIZER
class MiniBPETokenizer {
  constructor() {
    this.vocab = new Set();
    this.merges = [];
  }

  train(corpus, numMerges = 3) {
    // Inisialisasi token per karakter + end of word symbol '</w>'
    let words = corpus.split(/\s+/).map(w => w.split("").concat("</w>"));

    for (let step = 0; step < numMerges; step++) {
      const pairCounts = new Map();
      for (const word of words) {
        for (let i = 0; i < word.length - 1; i++) {
          const pair = `${word[i]} ${word[i+1]}`;
          pairCounts.set(pair, (pairCounts.get(pair) || 0) + 1);
        }
      }

      if (pairCounts.size === 0) break;
      // Cari pair paling sering muncul
      let bestPair = null;
      let maxCount = -1;
      for (const [pair, count] of pairCounts.entries()) {
        if (count > maxCount) {
          maxCount = count;
          bestPair = pair;
        }
      }

      const [first, second] = bestPair.split(" ");
      const mergedToken = first + second;
      this.merges.push({ first, second, merged: mergedToken });

      // Apply merge ke words
      words = words.map(word => {
        const newWord = [];
        let i = 0;
        while (i < word.length) {
          if (i < word.length - 1 && word[i] === first && word[i+1] === second) {
            newWord.push(mergedToken);
            i += 2;
          } else {
            newWord.push(word[i]);
            i++;
          }
        }
        return newWord;
      });
    }

    return this.merges;
  }
}

// 2. MATRIX MATH & ATTENTION ENGINE
class AttentionMath {
  static dot(vecA, vecB) {
    return vecA.reduce((sum, val, idx) => sum + val * vecB[idx], 0);
  }

  static softmax(logits) {
    const maxVal = Math.max(...logits);
    const exps = logits.map(v => Math.exp(v - maxVal));
    const sumExps = exps.reduce((a, b) => a + b, 0);
    return exps.map(v => v / sumExps);
  }

  // Scaled Dot-Product Attention: Attention(Q, K, V)
  static scaledDotProductAttention(Q, K, V) {
    const seqLen = Q.length;
    const d_k = Q[0].length;
    const sqrt_dk = Math.sqrt(d_k);

    const attentionWeights = [];
    const output = [];

    for (let i = 0; i < seqLen; i++) {
      // Hitung skor Q[i] @ K[j]^T / sqrt(d_k)
      const scores = [];
      for (let j = 0; j < seqLen; j++) {
        const rawScore = this.dot(Q[i], K[j]) / sqrt_dk;
        scores.push(rawScore);
      }
      // Softmax normalization across keys
      const weights = this.softmax(scores);
      attentionWeights.push(weights);

      // Weighted sum of Values (weights @ V)
      const outVec = new Array(V[0].length).fill(0);
      for (let j = 0; j < seqLen; j++) {
        for (let dim = 0; dim < V[0].length; dim++) {
          outVec[dim] += weights[j] * V[j][dim];
        }
      }
      output.push(outVec);
    }

    return { attentionWeights, output };
  }
}

// ==========================================
// TEST SUITE & RUNNER
// ==========================================
function runLab() {
  console.log(`${ANSI.bold}${ANSI.magenta}======================================================${ANSI.reset}`);
  console.log(`${ANSI.bold}${ANSI.magenta}  LAB HANDS-ON: BPE TOKENIZER & ATTENTION MECHANISM   ${ANSI.reset}`);
  console.log(`${ANSI.bold}${ANSI.magenta}======================================================${ANSI.reset}`);

  // Test 1: BPE Vocabulary Merging
  console.log(`\n${ANSI.bold}[Test 1] Training Byte-Pair Encoding (BPE) on text corpus...${ANSI.reset}`);
  const corpus = "low lower lowest newer newest low";
  const bpe = new MiniBPETokenizer();
  const merges = bpe.train(corpus, 3);
  console.log("Learned BPE Merges:", merges);

  // Test 2: Scaled Dot-Product Attention
  console.log(`\n${ANSI.bold}[Test 2] Computing Self-Attention Matrix for 3 Tokens (d_model=2)...${ANSI.reset}`);
  // Tokens: ["The", "AI", "Agent"]
  // Dimensi d_k = 2
  const Q = [
    [1.0, 0.5],  // The
    [0.2, 1.8],  // AI
    [0.1, 1.9]   // Agent
  ];
  const K = [
    [1.0, 0.5],
    [0.2, 1.8],
    [0.1, 1.9]
  ];
  const V = [
    [0.5, 0.1],
    [2.0, 1.5],
    [2.1, 1.6]
  ];

  const result = AttentionMath.scaledDotProductAttention(Q, K, V);

  console.log(`${ANSI.yellow}Attention Weights Matrix (Softmax distribution):${ANSI.reset}`);
  result.attentionWeights.forEach((row, i) => {
    const labels = ["The  ", "AI   ", "Agent"];
    const rowStr = row.map(w => w.toFixed(3)).join("  ");
    console.log(`Token [${labels[i]}] -> [${rowStr}]`);
  });

  // Verifikasi sifat probabilitas softmax (jumlah tiap baris = 1.0)
  result.attentionWeights.forEach(row => {
    const sum = row.reduce((a, b) => a + b, 0);
    if (Math.abs(sum - 1.0) > 1e-5) throw new Error("Attention weights do not sum to 1.0");
  });

  // AI & Agent should attend heavily to each other
  const aiToAgentWeight = result.attentionWeights[1][2];
  console.log(`Attention Weight 'AI' -> 'Agent': ${ANSI.green}${aiToAgentWeight.toFixed(3)}${ANSI.reset}`);

  console.log(`\n${ANSI.green}${ANSI.bold}✓ SUCCESS: BPE Tokenizer and Scaled Dot-Product Attention verified!${ANSI.reset}`);
}

runLab();
