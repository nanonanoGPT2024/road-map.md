# Kurikulum Inference Engineering
## Kategori 08: AI, Data, and Autonomous Agents
### Bab 05: Latency Optimization & Speculative Execution
#### Modul 01: Speculative Decoding Engine Mechanics & Dynamic Verification

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:

1. **Menganalisis Bottleneck Memory Bandwidth**: Mengidentifikasi limitasi *Arithmetic Intensity* pada inferensi *autoregressive* menggunakan prinsip *Roofline Model*.
2. **Merancang Algoritma Speculative Decoding**: Mengimplementasikan *Modified Rejection Sampling* untuk menjamin distribusi output model target tidak terdistorsi secara matematis ($P_{target}(x) \equiv P_{speculative}(x)$).
3. **Mengelola Sinkronisasi KV Cache**: Mengembangkan mekanisme rollback status *Key-Value (KV) Cache* berbasis tensor pointer ketika token spekulatif ditolak (*rejected*).
4. **Mengimplementasikan Dynamic Draft Length Controller**: Merancang algoritma adaptif untuk menyesuaikan panjang horizon spekulasi ($K$) berdasarkan running acceptance rate ($\alpha$) guna meminimalisasi latensi komputasi terbuang.
5. **Mengevaluasi Metrik Kinerja Inferensi**: Mengukur dan membandingkan *Inter-Token Latency* (ITL), *Time-to-First-Token* (TTFT), serta *Effective Speedup Factor* antara inferensi *naive autoregressive* dan *speculative execution*.

---

### 2. Concept Overview

Model autoregresif berbasis Transformer (seperti LLaMA, Mistral, atau GPT) memiliki karakteristik komputasi yang terikat pada memori (*Memory-Bound*) saat tahap decoding. Setiap token yang dihasilkan membutuhkan pemanggilan seluruh bobot model dari High Bandwidth Memory (HBM) ke SRAM/Register GPU, meskipun operasi komputasi per token relatif kecil.

```
Arithmetic Intensity (FLOPs/Byte) = Total Floating Point Operations / Total Memory Access Bytes
```

Pada *batch size* kecil ($B=1$), *Arithmetic Intensity* pada tahap decoding berada jauh di bawah titik saturasi komputasi GPU (Compute Roofline). 

```
Latency vs Memory Bandwidth
===========================
Compute Capacity [TFLOPs]  ▲                 /---------- (Compute Bound)
                           │                /
                           │               /
                           │              /
Operational Region (Decode)│  [x]        /
                           │ (Memory    /
                           │  Bound)   /
                           └──────────┴────────────────────────►
                                    Arithmetic Intensity (FLOPs/Byte)
```

**Speculative Decoding** menyelesaikan masalah ini dengan mendepolimerisasi proses inferensi menjadi dua peran komplementer:
1. **Draft Model (Small, Fast)**: Menghasilkan deret kandidat token sebanyak $K$ langkah ke depan secara cepat dengan asumsi komputasi rendah ($q(x)$).
2. **Target Model (Large, Accurate)**: Melakukan validasi paralel terhadap $K$ token tersebut dalam **satu single forward pass** ($p(x)$).

Karena pemrosesan $K$ token dalam satu *forward pass* mengubah operasi memori-bound menjadi terikat komputasi (*Compute-Bound*), GPU dapat mengeksekusi verifikasi tersebut dengan latensi yang hampir identik dengan inferensi satu token tunggal.

Distribusi token akhir dijamin identik dengan distribusi model target melalui teknik **Modified Rejection Sampling**. Apabila token spekulatif ke-$i$ ditolak, seluruh token $i+1 \dots K$ dibuang, state KV Cache di-*rewind*, dan token pengganti diambil langsung dari distribusi residual yang dikoreksi.

---

### 3. Why It Matters

Dalam implementasi skala enterprise, tantangan utama penyediaan LLM interaktif (seperti *Voice Agents*, *Code Completion Engines*, dan *Real-time Chat*) terletak pada **Inter-Token Latency (ITL)**. Mengurangi ITL tanpa degradasi akurasi model adalah prioritas mutlak.

1. **Penurunan Biaya Per Satuan Throughput**: Speculative decoding dapat meningkatkan *throughput* per GPU sebesar $1.8\times$ hingga $2.8\times$ tanpa melakukan kuantisasi destruktif (seperti INT4/FP4) atau *knowledge distillation* yang mengorbankan kualitas penalaran (*reasoning*).
2. **SLA Ketat pada Agentic Workflows**: Agen otonom multi-langkah (*multi-step autonomous agents*) membutuhkan puluhan pemanggilan inferensi untuk merampungkan rencana. Penghematan 30ms per token berakumulasi menjadi penghematan puluhan detik per eksekusi *agent cycle*.
3. **Pemanfaatan Kapasitas Idle Tensor Core**: Pada inferensi single-user, tensor core modern (seperti NVIDIA H100 Hopper/A100 Ampere) mengalami *under-utilization* signifikan (sering kali $<15\%$ compute utilization). Speculative verification memaksa utilisasi Tensor Core masuk ke rezim yang efisien.

---

### 4. Arsitektur & Diagram Komponen

Diagram berikut mengilustrasikan siklus hidup eksekusi spekulatif, interaksi KV Cache, dan gerbang sampling verifikasi.

```
+--------------------------------------------------------------------------------------------------+
|                                    SPECULATIVE DECODING ENGINE                                   |
+--------------------------------------------------------------------------------------------------+
                                                   │ Input Context (X_0...X_t)
                                                   ▼
                                       ┌───────────────────────┐
                                       │ Initialize KV Caches  │
                                       │   (Draft & Target)    │
                                       └───────────────────────┘
                                                   │
                   ┌───────────────────────────────┴───────────────────────────────┐
                   ▼                                                               ▼
        [Draft Model KV Cache]                                          [Target Model KV Cache]
                   │                                                               │
+──────────────────┴───────────────────────────────────────────────────────────────┴───────────────+
| LOOP: Speculative Iteration Step                                                                 |
|                                                                                                  |
|  1. Draft Generation Phase (Autoregressive, K steps)                                             |
|     For step = 1 to K:                                                                           |
|       γ_i ~ q(x | Context + γ_<i)                                                                |
|       Draft Cache Append(γ_i)                                                                    |
|                                                                                                  |
|     Result: Candidate tokens sequence [γ_1, γ_2, ..., γ_K]                                       |
|                                                                                                  |
|  2. Target Verification Phase (Parallel Batch Forward Pass)                                      |
|     Concat: [Current Token, γ_1, γ_2, ..., γ_K] -> Input to Target Model                         |
|     Compute Logits: P(x_1), P(x_2), ..., P(x_K), P(x_{K+1}) in a SINGLE pass                      |
|                                                                                                  |
|  3. Modified Rejection Sampling & Rollback                                                       |
|                                                                                                  |
|     +-------------+    Accept     +---------------+                                              |
|     |  Evaluate   |-------------->|  Keep Token   |                                              |
|     |  Token γ_i  |               |  Commit KV    |                                              |
|     +-------------+               +---------------+                                              |
|            │                              │                                                      |
|            │ Reject                       ▼ Advance to γ_{i+1}                                   |
|            ▼                              │                                                      |
|     +-------------------------+           │                                                      |
|     | Sample from P'_res(x)   |           │                                                      |
|     | Invalidate tokens i...K |           │                                                      |
|     | Rewind Target KV Cache  |<──────────┘ (On Termination or First Reject)                     |
|     | Rollback Draft KV Cache |                                                                  |
|     +-------------------------+                                                                  |
|                  │                                                                               |
+──────────────────┼───────────────────────────────────────────────────────────────────────────────+
                   ▼
       Emit Accepted Tokens + 1 Corrected Token
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### 5.1 Modified Rejection Sampling Mathematics
Tujuan utama algoritma sampling pada speculative decoding adalah memastikan probabilitas kemunculan token $x$ mengikuti distribusi target $p(x)$, bukan distribusi draft $q(x)$.

Misalkan kita memvalidasi token kandidat $\tilde{x} \sim q(x)$. Nilai probabilitas penerimaan token didefinisikan sebagai:

$$P(\text{accept } \tilde{x}) = \min\left(1, \frac{p(\tilde{x})}{q(\tilde{x})}\right)$$

Jika $\tilde{x}$ diterima, token tersebut ditambahkan secara permanen ke sekuens output. Jika ditolak pada indeks ke-$n$, token $\tilde{x}_n$ tidak digunakan. Sebagai gantinya, token baru disampel dari distribusi residual yang dinormalisasi:

$$p_{\text{residual}}(x) = \frac{\max(0, p(x) - q(x))}{\sum_{x'} \max(0, p(x') - q(x'))}$$

Semua token kandidat setelah indeks $n$ ($\tilde{x}_{n+1}, \dots, \tilde{x}_K$) dibatalkan.

*Bukti Kesetaraan Distribusi*:
Distribusi marginal output yang dihasilkan:
$$P(X = x) = q(x) \cdot \min\left(1, \frac{p(x)}{q(x)}\right) + \left(1 - \sum_{x'} q(x') \min\left(1, \frac{p(x')}{q(x')}\right)\right) \cdot p_{\text{residual}}(x)$$

Dengan mendistribusikan suku-suku di atas, diperoleh identitas:
$$q(x) \min\left(1, \frac{p(x)}{q(x)}\right) = \min(q(x), p(x))$$
$$p_{\text{residual}}(x) \left( 1 - \sum_{x'} \min(q(x'), p(x')) \right) = \max(0, p(x) - q(x))$$
Karena $\min(a, b) + \max(0, a - b) = a$, maka $P(X = x) = p(x)$ secara eksak tanpa deviasi statistik.

#### 5.2 KV Cache Slicing & Rollback Strategy
Pada inferensi sekuensial standar, KV Cache hanya menerima penambahan data (*append-only*). Namun pada speculative execution:
1. Target Model membutuhkan context awal + $K$ token kandidat untuk dievaluasi secara paralel.
2. Tensor KV Cache Target Model harus mencakup panjang $T + K$.
3. Jika hanya $M$ token yang diterima ($M < K$), status KV Cache pada Target dan Draft Model dari indeks $T + M + 1$ hingga $T + K$ menjadi tidak valid (*stale*).
4. **Mekanisme Rollback**:
   - Jika sistem menggunakan alokasi statis: tensor cache dipotong (*sliced*) kembali ke panjang $T + M + 1$ via *in-place tensor narrowing* atau manipulasi tensor metadata `sequence_length`.
   - Jika sistem menggunakan *PagedAttention*: blok memori fisik yang dialokasikan untuk token spekulatif yang ditolak dikembalikan ke *free block pool*.

#### 5.3 Dynamic Acceptance Rate & Latency Breakeven
Keuntungan latensi ditentukan oleh rasio berikut:

$$\text{Speedup} = \frac{\alpha \cdot K + 1}{1 + \frac{c}{C} \cdot K}$$

Dimana:
- $\alpha$: Rata-rata tingkat penerimaan token (*acceptance rate*), $\alpha \in [0, 1]$.
- $K$: Jumlah token spekulasi per siklus.
- $c$: Waktu satu forward pass Draft Model.
- $C$: Waktu satu forward pass Target Model.

Jika $\alpha < \frac{c}{C}$, speculative decoding justru menyebabkan *latency regression* (lebih lambat dari inferensi autoregresif standar). Oleh karena itu, $K$ harus diatur secara adaptif.

---

### 6. Production-Ready Code Implementation

Berikut adalah implementasi lengkap mesin inferensi spekulatif berbasis PyTorch dengan integrasi Hugging Face. Kode ini mencakup *rejection sampling*, *KV-cache rollback management*, dan *dynamic horizon adjustment*.

```python
import time
from dataclasses import dataclass
from typing import List, Optional, Tuple

import torch
import torch.nn.functional as F
from transformers import AutoModelForCausalLM, AutoTokenizer, PreTrainedModel, PreTrainedTokenizerBase


@dataclass
class SpeculativeMetrics:
    total_tokens_emitted: int = 0
    draft_tokens_proposed: int = 0
    draft_tokens_accepted: int = 0
    target_forward_passes: int = 0
    total_wall_time_sec: float = 0.0

    @property
    def acceptance_rate(self) -> float:
        if self.draft_tokens_proposed == 0:
            return 0.0
        return self.draft_tokens_accepted / self.draft_tokens_proposed

    @property
    def tokens_per_second(self) -> float:
        if self.total_wall_time_sec == 0:
            return 0.0
        return self.total_tokens_emitted / self.total_wall_time_sec


class SpeculativeInferenceEngine:
    def __init__(
        self,
        target_model: PreTrainedModel,
        draft_model: PreTrainedModel,
        tokenizer: PreTrainedTokenizerBase,
        device: torch.device,
        initial_k: int = 4,
        min_k: int = 1,
        max_k: int = 8,
    ):
        self.target_model = target_model.to(device).eval()
        self.draft_model = draft_model.to(device).eval()
        self.tokenizer = tokenizer
        self.device = device
        
        self.k = initial_k
        self.min_k = min_k
        self.max_k = max_k
        
        # Guard checking vocabulary compatibility
        if self.target_model.config.vocab_size != self.draft_model.config.vocab_size:
            raise ValueError(
                f"Vocab size mismatch! Target: {self.target_model.config.vocab_size}, "
                f"Draft: {self.draft_model.config.vocab_size}. Tokenizers must be identical."
            )

    @torch.inference_mode()
    def _sample_from_logits(
        self, logits: torch.Tensor, temperature: float = 1.0, top_p: float = 0.0
    ) -> torch.Tensor:
        """Helper untuk sampling probabilitas dari tensor logit."""
        if temperature == 0.0:
            return torch.argmax(logits, dim=-1, keepdim=True)
            
        scaled_logits = logits / temperature
        probs = F.softmax(scaled_logits, dim=-1)
        
        if top_p > 0.0 and top_p < 1.0:
            sorted_probs, sorted_indices = torch.sort(probs, descending=True)
            cumulative_probs = torch.cumsum(sorted_probs, dim=-1)
            sorted_indices_to_remove = cumulative_probs > top_p
            sorted_indices_to_remove[..., 1:] = sorted_indices_to_remove[..., :-1].clone()
            sorted_indices_to_remove[..., 0] = 0
            indices_to_remove = sorted_indices_to_remove.scatter(
                dim=-1, index=sorted_indices, src=sorted_indices_to_remove
            )
            probs = probs.masked_fill(indices_to_remove, 0.0)
            probs = probs / torch.sum(probs, dim=-1, keepdim=True)

        return torch.multinomial(probs, num_samples=1)

    def _rollback_kv_cache(self, past_key_values: Tuple[Tuple[torch.Tensor, ...], ...], num_valid_tokens: int) -> Tuple[Tuple[torch.Tensor, ...], ...]:
        """
        Memangkas sequence length pada KV Cache kembali ke ukuran yang diterima.
        Format KV cache: List/Tuple of Layers -> (key, value)
        Shape per tensor: [batch_size, num_heads, seq_len, head_dim]
        """
        if past_key_values is None:
            return None
        
        trimmed_cache = []
        for layer in past_key_values:
            trimmed_layer = []
            for tensor in layer:
                # Slicing dimensi seq_len (dimensi ke-2)
                trimmed_tensor = tensor[:, :, :num_valid_tokens, :]
                trimmed_layer.append(trimmed_tensor)
            trimmed_cache.append(tuple(trimmed_layer))
        return tuple(trimmed_cache)

    @torch.inference_mode()
    def generate(
        self,
        prompt: str,
        max_new_tokens: int = 128,
        temperature: float = 0.7,
        top_p: float = 0.9,
    ) -> Tuple[str, SpeculativeMetrics]:
        metrics = SpeculativeMetrics()
        input_ids = self.tokenizer.encode(prompt, return_tensors="pt").to(self.device)
        start_time = time.perf_counter()

        # Prefill phase untuk context awal
        draft_cache = None
        target_cache = None

        # Warm up target context
        target_outputs = self.target_model(input_ids=input_ids, use_cache=True)
        target_cache = target_outputs.past_key_values
        last_accepted_token = self._sample_from_logits(
            target_outputs.logits[:, -1, :], temperature, top_p
        )
        
        # Warm up draft context
        draft_outputs = self.draft_model(input_ids=input_ids, use_cache=True)
        draft_cache = draft_outputs.past_key_values

        generated_tokens = [last_accepted_token.item()]
        metrics.total_tokens_emitted += 1
        
        current_seq_len = input_ids.shape[1]

        while len(generated_tokens) < max_new_tokens:
            iter_k = min(self.k, max_new_tokens - len(generated_tokens))
            if iter_k <= 0:
                break

            draft_tokens = []
            draft_probs_list = []
            
            # --- PHASE 1: Draft Auto-Regressive Speculation ---
            current_draft_input = last_accepted_token
            for _ in range(iter_k):
                d_out = self.draft_model(
                    input_ids=current_draft_input,
                    past_key_values=draft_cache,
                    use_cache=True,
                )
                draft_cache = d_out.past_key_values
                draft_logits = d_out.logits[:, -1, :]
                
                draft_prob = F.softmax(draft_logits / max(temperature, 1e-5), dim=-1)
                next_draft_token = self._sample_from_logits(draft_logits, temperature, top_p)
                
                draft_tokens.append(next_draft_token)
                draft_probs_list.append(draft_prob)
                current_draft_input = next_draft_token

            draft_tensor = torch.cat(draft_tokens, dim=-1) # [1, K]
            metrics.draft_tokens_proposed += iter_k

            # --- PHASE 2: Target Verification in One Parallel Pass ---
            # Input adalah token terkonfirmasi terakhir digabung dengan token draf
            target_verification_input = torch.cat([last_accepted_token, draft_tensor], dim=-1)
            
            t_out = self.target_model(
                input_ids=target_verification_input,
                past_key_values=target_cache,
                use_cache=True,
            )
            metrics.target_forward_passes += 1
            target_cache = t_out.past_key_values
            target_logits = t_out.logits # [1, K+1, Vocab]

            # --- PHASE 3: Verification & Rejection Sampling ---
            num_accepted = 0
            n_eval = draft_tensor.shape[1]
            terminal_token_needed = True

            for i in range(n_eval):
                t_logits_step = target_logits[:, i, :]
                t_prob = F.softmax(t_logits_step / max(temperature, 1e-5), dim=-1)
                
                candidate_token = draft_tensor[:, i : i + 1]
                q_p = draft_probs_list[i].gather(dim=-1, index=candidate_token).squeeze()
                p_p = t_prob.gather(dim=-1, index=candidate_token).squeeze()

                # Rejection Sampling Criterion
                r = torch.rand(1, device=self.device)
                ratio = p_p / torch.clamp(q_p, min=1e-8)
                
                if r <= torch.minimum(torch.ones_like(ratio), ratio):
                    # Token Diterima
                    num_accepted += 1
                    generated_tokens.append(candidate_token.item())
                    last_accepted_token = candidate_token
                else:
                    # Token Ditolak: Bentuk distribusi residual ter-koreksi
                    diff = F.relu(t_prob - draft_probs_list[i])
                    residual_sum = torch.sum(diff, dim=-1, keepdim=True)
                    if residual_sum > 0:
                        norm_p = diff / residual_sum
                    else:
                        norm_p = t_prob # Fallback jika numerical underflow
                    
                    replacement_token = torch.multinomial(norm_p, num_samples=1)
                    generated_tokens.append(replacement_token.item())
                    last_accepted_token = replacement_token
                    terminal_token_needed = False
                    break

            metrics.draft_tokens_accepted += num_accepted
            
            # Jika semua token spekulatif diterima, sampel token bonus dari output logit target ke-K
            if terminal_token_needed and len(generated_tokens) < max_new_tokens:
                bonus_logits = target_logits[:, -1, :]
                bonus_token = self._sample_from_logits(bonus_logits, temperature, top_p)
                generated_tokens.append(bonus_token.item())
                last_accepted_token = bonus_token
                num_accepted += 1

            # Hitung total token valid pada iterasi ini
            # Total panjang context yang sah = context_awal + accepted_tokens_sequence
            metrics.total_tokens_emitted = len(generated_tokens)
            current_seq_len += num_accepted

            # --- PHASE 4: Rollback KV Cache State ---
            # Rollback Target & Draft KV Cache ke indeks yang terbukti absah
            target_cache = self._rollback_kv_cache(target_cache, current_seq_len)
            draft_cache = self._rollback_kv_cache(draft_cache, current_seq_len)

            # --- PHASE 5: Adaptive Draft Horizon Tuning ---
            running_alpha = (num_accepted) / (iter_k + 1)
            if running_alpha > 0.8 and self.k < self.max_k:
                self.k += 1
            elif running_alpha < 0.4 and self.k > self.min_k:
                self.k -= 1

            if last_accepted_token.item() == self.tokenizer.eos_token_id:
                break

        metrics.total_wall_time_sec = time.perf_counter() - start_time
        decoded_text = self.tokenizer.decode(generated_tokens, skip_special_tokens=True)
        return decoded_text, metrics
```

---

### 7. Edge Cases & Failure Modes

Dalam lingkungan produksi skala besar, speculative decoding dapat mengalami kegagalan operasional (*silent failures* atau degradasi performa):

| Failure Mode | Trigger Mechanism | Mitigasi Engineering |
|---|---|---|
| **Negative Latency Acceleration (Slowing Down)** | Domain drift yang ekstrem (misal teks umum vs kode assembly kompleks) menyebabkan *Acceptance Rate* jatuh mendekati 0 ($\alpha \to 0$). Verifikasi paralel memakan komputasi tanpa menghasilkan token yang valid. | **Circuit Breaker Pattern**: Lacak rolling average acceptance rate ($\bar{\alpha}_{10}$). Jika $\bar{\alpha}_{10} < 0.2$, nonaktifkan speculative mode sementara dan jalankan mode autoregresif langsung. |
| **KV Cache Index Desynchronization** | Off-by-one error pada slicing KV tensor menyebabkan pergeseran positional embedding pada token berikutnya. Hasil output berupa halusinasi total (garbage output). | Unit test wajib menggunakan **Logits Difference Verification**: bandingkan output logits speculative run dengan deterministic standard run pada `temperature=0.0`. Keduanya harus menghasilkan *Bitwise Identical Output*. |
| **Target OOM saat Verification Burst** | Target model menerima input berukuran $(1 + K)$ token secara mendadak saat sisa alokasi memori VRAM GPU tipis. | Pre-allocate scratchpad tensors untuk verifikasi dan gunakan implementasi paging memory (misal vLLM Page pool) alih-alih dynamic reallocation `torch.cat`. |
| **Probability Underflow pada Residual Sampling** | Nilai residual $\max(0, p(x) - q(x))$ memiliki sum mendekati nol akibat diskrepansi floating-point precision (FP16/BF16 roundoff). | Terapkan epsilon conditioning: $\epsilon = 10^{-8}$. Jika $\sum (p(x) - q(x)) < \epsilon$, resample langsung dari distribusi probabilitas Target Model murni $p(x)$. |

---

### 8. Trade-offs & Alternatif Solusi

Implementasi draft-model-based speculative execution bukan satu-satunya pendekatan latensi. Tabel berikut menyajikan analisis komparatif arsitektur alternatif:

| Parameter | Draft-Model Speculation (Leviathan et al.) | Medusa Heads (Multi-Head Speculation) | Prompt Lookup Decoding (PLD) |
|---|---|---|---|
| **Arsitektur Tambahan** | Model kecil terpisah (misal LLaMA-68M untuk LLaMA-70B) | Multi-head regression layers di atas Target Model | Tidak ada (Pattern matching string murni) |
| **Memory Footprint** | Tambahan VRAM untuk model draft + KV Cache draft terpisah | Tambahan bobot kecil untuk Medusa heads ($<5\%$ VRAM) | **Zero Additional Memory** |
| **Acceptance Rate ($\alpha$)** | Tinggi untuk tugas general reasoning ($\approx 0.6 - 0.8$) | Moderat hingga Tinggi ($\approx 0.5 - 0.75$) | Sangat tinggi hanya pada tugas Retrieval/Summarization ($\approx 0.8$), buruk di logika murni |
| **Training Overhead** | Harus melatih atau mencari model draft dengan tokenizer identik | Memerlukan pelatihan fine-tuning Medusa Heads pada model target | **Zero Training Required** |
| **Deployment Complexity** | Tinggi (Sinkronisasi dual model runner, parallel inference stream) | Menengah (Modifikasi target forward graph) | Rendah (Algoritma string buffer di pre-inference) |

---

### 9. Best Practices & Standard Industri

1. **Rasio Ukuran Parameter Optimal**:
   Gunakan model draft dengan parameter sekitar **5% hingga 10%** dari total parameter target model.
   - Target: 70B parameter $\to$ Draft: 1B hingga 7B parameter.
   - Target: 8B parameter $\to$ Draft: 68M hingga 135M parameter.
2. **Kesesuaian Arsitektur dan Tokenizer**:
   Draft model dan Target model **wajib** menggunakan Vocabulary dan Tokenizer yang sama persis. Perbedaan tokenization boundary akan merusak kesahihan token rejection sampling.
3. **Penyatuan GPU Context (Co-location)**:
   Tempatkan Draft Model dan Target Model pada perangkat GPU fisik yang sama untuk menghindari latensi PCI-e transfer saat memindahkan token spekulasi antar memory bus. Gunakan *Unified CUDA Stream* atau *CUDA Graphs* untuk memangkas overhead pemanggilan kernel (*kernel launch overhead*).
4. **PagedAttention Speculative Slicing**:
   Hindari operasi pemotongan tensor (`tensor[:, :, :len]`) berbasis memory re-allocation pada PyTorch runtime. Integrasikan speculative decoding ke dalam engine seperti **vLLM** atau **TensorRT-LLM** yang mengelola cache berbasis block index pointers (cukup mengembalikan pointer blok ke allocator).

---

### 10. Hands-on Lab Exercise

#### Skenario Lab
Anda diminta membangun harness evaluasi performa inferensi untuk membuktikan efektivitas Speculative Decoding melawan Standard Autoregressive Decoding. Anda akan mengukur *Time to First Token* (TTFT), *Inter-Token Latency* (ITL), dan *Overall Speedup Factor*.

#### Step-by-Step Implementation

1. **Persiapan Environtment**:
```bash
pip install torch transformers accelerate
```

2. **Eksekusi Script Benchmark (`speculative_bench.py`)**:
```python
import time
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from speculative_engine import SpeculativeInferenceEngine  # Implementasi dari Section 6

def run_benchmark():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using target device: {device}")

    # Menggunakan model kecil untuk testing lokal
    target_model_id = "facebook/opt-1.3b"
    draft_model_id = "facebook/opt-125m"

    print("Loading tokenizers and models...")
    tokenizer = AutoTokenizer.from_pretrained(target_model_id)
    target_model = AutoModelForCausalLM.from_pretrained(
        target_model_id, torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32
    )
    draft_model = AutoModelForCausalLM.from_pretrained(
        draft_model_id, torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32
    )

    test_prompt = (
        "In distributed system architecture, consensus algorithms play a critical role "
        "in maintaining state consistency across multiple nodes. The Raft consensus algorithm "
        "was specifically designed to be more understandable than Paxos. It works by "
    )

    engine = SpeculativeInferenceEngine(
        target_model=target_model,
        draft_model=draft_model,
        tokenizer=tokenizer,
        device=device,
        initial_k=4
    )

    # 1. Warmup Run
    print("Running Warmup...")
    _ = engine.generate(test_prompt, max_new_tokens=16, temperature=0.0)

    # 2. Benchmarking Speculative Execution
    print("\n--- Running Speculative Execution Benchmark ---")
    spec_text, spec_metrics = engine.generate(
        test_prompt, max_new_tokens=64, temperature=0.7, top_p=0.9
    )
    
    print(f"Generated text: {spec_text[:100]}...")
    print(f"Speculative Time: {spec_metrics.total_wall_time_sec:.4f} sec")
    print(f"Tokens Generated: {spec_metrics.total_tokens_emitted}")
    print(f"Acceptance Rate: {spec_metrics.acceptance_rate * 100:.2f}%")
    print(f"Speculative Throughput: {spec_metrics.tokens_per_second:.2f} tokens/sec")

    # 3. Benchmarking Baseline Autoregressive Target Model
    print("\n--- Running Baseline Autoregressive Benchmark ---")
    input_ids = tokenizer.encode(test_prompt, return_tensors="pt").to(device)
    
    baseline_start = time.perf_counter()
    with torch.inference_mode():
        baseline_out = target_model.generate(
            input_ids=input_ids,
            max_new_tokens=64,
            do_sample=True,
            temperature=0.7,
            top_p=0.9,
            use_cache=True
        )
    baseline_time = time.perf_counter() - baseline_start
    baseline_tokens = baseline_out.shape[1] - input_ids.shape[1]
    baseline_tps = baseline_tokens / baseline_time

    print(f"Baseline Time: {baseline_time:.4f} sec")
    print(f"Tokens Generated: {baseline_tokens}")
    print(f"Baseline Throughput: {baseline_tps:.2f} tokens/sec")

    # 4. Result Synthesis
    speedup = spec_metrics.tokens_per_second / baseline_tps
    print("\n================ BENCHMARK RESULT ================")
    print(f"Net Speedup Factor: {speedup:.2f}x")
    print("==================================================")
    
    assert speedup > 0.0, "Execution failed to compute speedup."

if __name__ == "__main__":
    run_benchmark()
```

#### Verification Criteria
- Nilai throughput (`tokens_per_second`) pada mode speculative harus melampaui baseline ($\text{Speedup} > 1.0$) pada GPU yang memiliki compute capability modern (misal NVIDIA T4, A10, A100).
- Verifikasi nilai `acceptance_rate` rata-rata berada pada rentang $50\% - 85\%$ untuk model turunan arsitektur yang sama.
- Output logit konsisten secara distribusi teks tanpa degradasi koherensi gramatikal.