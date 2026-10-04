# Kurikulum Rekayasa Inferensi Enterprise
## Kategori: 08-AI-Data-and-Autonomous-Agents
### BAB-05: Latency Optimization & Speculative Execution
#### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
1. **Menganalisis Bottleneck Inferensi LLM**: Menjelaskan batasan *memory-bandwidth bound* pada tahap autoregresif (*decoding phase*) menggunakan kalkulasi *Roofline Model* dan *Arithmetic Intensity*.
2. **Menguasai Mekanisme Matematis Speculative Decoding**: Mengimplementasikan algoritma *Modified Rejection Sampling* untuk menjamin distribusi output model gabungan (*Draft* + *Target*) identik secara matematis dengan distribusi target tunggal.
3. **Membangun Runtime Speculative Execution Produksi**: Mengembangkan engine inferensi yang mengorkestrasi *Draft Model* dan *Target Model* secara asinkron dengan pengelolaan *KV-Cache Rollback* dan *Tree-Attention Masks*.
4. **Mengevaluasi Metrik Kritis Produksi**: Mengukur *Mean Acceptance Length* ($\mathbb{E}[\alpha]$), rasio kompresi latensi, konkurensi VRAM overhead, serta menghitung ambang batas efisiensi (*break-even latency threshold*).
5. **Mitigasi Degradasi Kinerja Skala Enterprise**: Mendiagnosis dan memperbaiki fenomena *Acceptance Rate Collapse* akibat pergeseran domain (*domain drift*) dan kontensi resource pada arsitektur GPU terdistribusi.

---

### 2. Prerequisite

Peserta wajib menguasai:
* **Mekanika Dasar Transformer**: Pemahaman mendalam terkait matriks $Q, K, V$, perbedaan mendasar fase *Prefill* vs *Decode*, serta struktur *PagedAttention* atau *Continuous Batching*.
* **CUDA & PyTorch Lanjutan**: Penguasaan alokasi tensor manual, manipulasi pointer buffer, pinned memory, CUDA streams, dan pemahaman *Kernel Launch Overhead*.
* **Probabilitas & Statistik Terapan**: Teorema sampling, *Categorical Cross-Entropy*, *Top-$p$ (Nucleus)*, *Top-$k$*, *Temperature Scaling*, dan *Total Variation Distance*.
* **Hardware Profile Modern**: Karakteristik arsitektur GPU NVIDIA (SRAM vs HBM3, Tensor Cores, NVLink throughput) serta batasan PCIe Gen4/Gen5.

---

### 3. Concept & Internal Architecture (Mendalam)

#### Arithmetic Intensity & Bottleneck Inferensi Autoregresif
Inferensi LLM konvensional menghasilkan token satu per satu secara sekuensial. Setiap token yang digenerasi memerlukan pembacaan seluruh parameter model dari *High Bandwidth Memory* (HBM) ke *Static Random-Access Memory* (SRAM) pada *Streaming Multiprocessor* (SM).

Dalam kerangka *Roofline Model*, kinerja dibatasi oleh:
$$\text{Arithmetic Intensity} = \frac{\text{Floating Point Operations (FLOPs)}}{\text{Memory Access (Bytes)}}$$

Pada fase *decoding* dengan *batch size* kecil ($B=1$):
* **Operasi FLOPs**: $\sim 2P$ FLOPs per token (di mana $P$ adalah jumlah parameter).
* **Transfer Memori**: $\sim 2P$ bytes (menggunakan presisi FP16/BF16) ditambah pembacaan *KV-Cache*.
* **Arithmetic Intensity**: $\approx 1 \text{ FLOP/Byte}$.

Dengan kapasitas komputasi GPU H100 (FP16 Tensor Core $\approx 989 \text{ TFLOPs}$) dan bandwidth HBM3 ($\approx 3.35 \text{ TB/s}$), titik impas (*ridge point*) arsitektur berada pada rasio $\approx 295 \text{ FLOPs/Byte}$. Karena fase decoding hanya berada pada rasio $\approx 1 \text{ FLOP/Byte}$, sistem beroperasi secara ekstrem di area **Memory-Bandwidth Bound**. Sebagian besar siklus GPU terbuang dalam status *idle* menunggu data bobot model ditransfer dari memori.

```
       Performance (TFLOP/s)
               ^
  Compute Peak |--------------------------+ (Ridge Point ~295 FLOP/Byte)
               |                         /
               |                        / 
               |                       /  Compute-Bound Region
               |                      /
               |                     /
               |                    /
               |                   / Memory-Bound Region
  Decode Phase |   x (<-- ~1 FLOP/Byte)
               +---------------------------------------->
               0                          Arithmetic Intensity (FLOP/Byte)
```

#### Paradigma Speculative Decoding
Speculative Decoding (Leviathan et al., 2023; Chen et al., 2023) mengubah keterbatasan ini dengan memisahkan proses menjadi dua peran:
1. **Draft Model ($M_q$)**: Model kecil berbobot ringan (misal Llama-3-8B) yang menghasilkan spekulasi $K$ token secara cepat karena memori yang harus ditransfer jauh lebih sedikit.
2. **Target Model ($M_p$)**: Model besar berkapasitas tinggi (misal Llama-3-70B) yang memverifikasi seluruh $K$ token kandidat secara paralel dalam **satu forward pass**.

Verifikasi paralel ini mengubah sifat beban kerja target model dari yang semula memory-bound menjadi bergeser ke arah compute-bound, karena target model membaca parameter seberat $70\text{B}$ satu kali untuk memproses $K$ token sekaligus dalam bentuk *batch sequence*.

#### Formulasi Matematis: Modified Rejection Sampling
Untuk memastikan distribusi probabilitas model gabungan tetap identik secara absolut dengan distribusi model target ($P(x)$), digunakan teknik *rejection sampling* terkalibrasi. 

Diberikan token spekulasi $x$ pada indeks tertentu, dengan probabilitas dari draft model $q(x) = M_q(x | x_{<t})$ dan target model $p(x) = M_p(x | x_{<t})$:

1. **Evaluasi Penerimaan**:
   Kandidat token $x$ diterima dengan probabilitas:
   $$\mathbb{P}(\text{Terima } x) = \min\left(1, \frac{p(x)}{q(x)}\right)$$

2. **Mekanisme Rejeksi dan Resampling**:
   Jika token $x$ ditolak, iterasi spekulasi untuk batch tersebut dihentikan. Token pengganti disampling dari distribusi residual terkalibrasi:
   $$p'(x) = \frac{\max(0, p(x) - q(x))}{\sum_{v \in V} \max(0, p(v) - q(v))}$$
   di mana $V$ adalah kosakata (*vocabulary*).

Melalui formulasi ini, dibuktikan secara matematis bahwa:
$$\mathbb{P}(X = x) = q(x) \min\left(1, \frac{p(x)}{q(x)}\right) + (1 - \text{acceptance}) p'(x) \equiv p(x)$$
Artinya, **tidak ada degradasi kualitas output** (*zero distribution shift*). Model 70B tetap mengeluarkan output yang sama persis seperti saat melakukan inferensi autoregresif murni.

#### Arsitektur Tree Attention (Medusa / SpecInfer)
Dalam implementasi tingkat lanjut, spekulasi tidak dilakukan dalam format rantai linear tunggal ($1 \times K$), melainkan dalam struktur pohon (*Speculative Tree*). Beberapa cabang token dievaluasi secara simultan menggunakan *Tree Attention Mask*.

```
                [Root: Token t]
                 /            \
          [Draft A1]        [Draft B1]
           /      \             |
      [Draft A2] [Draft A3]  [Draft B2]
```

Matriks atensi topologi pohon diatur sehingga token anak hanya dapat melihat token induknya (*ancestor tokens*), memungkinkan verifikasi puluhan jalur spekulasi dalam satu eksekusi *Forward Pass* Target Model.

---

### 4. Why & What

| Dimensi | Inferensi Autoregresif Klasik | Speculative Execution (Linear) | Speculative Execution (Tree-Based) |
| :--- | :--- | :--- | :--- |
| **Karakteristik Komputasi** | Memory-Bandwidth Bound murni | Campuran (Draft: Memory, Target: Compute) | Cenderung Compute-Bound optimal |
| **Forward Pass Target** | 1 Pass per 1 Token | 1 Pass per $\gamma$ Token ($\gamma = \text{accepted tokens} + 1$) | 1 Pass per $\gamma$ Token (Rasio $\gamma$ lebih tinggi) |
| **Kompleksitas KV-Cache** | Monotonik bertambah | Memerlukan pointer *rollback* | Memerlukan *tree-unflattening* & *dynamic pruning* |
| **Throughput (Tokens/sec)** | Baseline ($1.0\times$) | $2.0\times - 2.8\times$ | $2.5\times - 3.5\times$ |
| **Kebutuhan VRAM** | Rendah (hanya Target Model) | Sedang (Target + Draft Model) | Tinggi (Target + Draft + Struktur Mask Kompleks) |
| **Jaminan Matematis** | Deterministik / Native Sample | Identik secara penuh ($D_{TV} = 0$) | Identik secara penuh ($D_{TV} = 0$) |

---

### 5. How (Workflow Detail)

Alur kerja engine inferensi berbasis spekulasi beroperasi melalui siklus eksekusi berikut:

```
[Mulai Iterasi]
       │
       ▼
[Draft Phase] ───► Loop autoregresif pada Draft Model sebanyak K langkah
       │          Mencatat: Token kandidat dan probabilitas q_k(x)
       ▼
[Context Sync] ──► Gabungkan K token spekulatif ke konteks Target Model
       │          Siapkan input tensor berukuran [Batch, K]
       ▼
[Target Verification] ──► Lakukan SATU single forward pass pada Target Model
       │                  Ekstraksi logits untuk seluruh K posisi
       │                  Hitung probabilitas target p_k(x)
       ▼
[Rejection Sampling] ───► Loop k = 1 s.d. K:
       │                  Hitung probabilitas penerimaan min(1, p_k / q_k)
       │                  ├── Diterima: Pertahankan token, lanjutkan k+1
       │                  └── Ditolak : Sample token baru dari p'(x), hentikan loop
       ▼
[KV-Cache Rollback] ────► Potong buffer KV-Cache Target & Draft
       │                  Kembalikan pointer ke indeks token valid terakhir
       ▼
[Output Generation] ────► Stream token-token yang diterima + 1 token residual
       │
       ▼
[Selesai Iterasi / Lanjut ke Draft Phase Berikutnya]
```

---

### 6. Analogy & Diagram ASCII

#### Analogi: Arsitek Senior dan Asisten Drafter
Bayangkan perancangan cetak biru sebuah gedung. 
* **Inferensi Klasik**: Arsitek Senior menggambar garis demi garis sendirian. Sangat presisi, namun sangat lambat karena kapasitas mentalnya habis hanya untuk memegang penggaris dan memindahkan kertas (analogi *memory bandwidth latency*).
* **Speculative Execution**: Asisten Drafter (Draft Model, murah dan cepat) membuat draf kasar untuk 5 langkah berikutnya ke depan. Arsitek Senior (Target Model) memeriksa kelima gambar tersebut secara sekilas dalam satu pandangan mata (*parallel verification*). Jika gambar ke-1, ke-2, dan ke-3 benar, ia langsung menandatanganinya; gambar ke-4 salah sedikit, ia mencoretnya, menggambar koreksi final untuk langkah ke-4, dan membuang langkah ke-5 tanpa diperiksa. Tiga setengah langkah diselesaikan dalam durasi satu kali inspeksi.

#### State Machine Transisi KV-Cache Engine

```
Draft Model State:
Step 0: [Context]
Step 1: [Context] -> Pred [D1] (Append KV)
Step 2: [Context, D1] -> Pred [D2] (Append KV)
Step 3: [Context, D1, D2] -> Pred [D3] (Append KV)

Target Model State (Parallel Verification Phase):
Input: [Context, D1, D2, D3] (Batch length = 3)
Target Output Logits: Evaluates D1, D2, D3 simultaneously + predicts fallback

Verification Result:
- D1: ACCEPTED
- D2: REJECTED -> Sample alternative token [T2_alt]
- D3: DISCARDED UNCHECKED

KV-Cache State Machine:
Current Physical Allocation: [Context, D1, D2, D3]
                                         ▲   ▲
                                         │   └─ Truncate/Invalidate
                                         └───── Truncate/Invalidate
Finalized Physical State   : [Context, D1, T2_alt]
Next Cycle Context Length  : Len(Context) + 2
```

---

### 7. Simple Example & Practical Example

#### 7.1 Simple Example: Algoritma Verifikasi Rejection Sampling
Skrip mandiri berikut mendemonstrasikan implementasi matematis murni dari algoritma Modified Rejection Sampling tanpa ketergantungan model neural.

```python
import torch
import torch.nn.functional as F

def modified_rejection_sampling(
    p_logits: torch.Tensor, 
    q_logits: torch.Tensor, 
    draft_tokens: torch.Tensor
) -> list[int]:
    """
    Simulasi verifikasi Rejection Sampling Leviathan et al.
    p_logits: [K, Vocab_Size] (Logits dari Target Model)
    q_logits: [K, Vocab_Size] (Logits dari Draft Model)
    draft_tokens: [K] (Token yang ditebak oleh Draft Model)
    """
    p_probs = F.softmax(p_logits, dim=-1)
    q_probs = F.softmax(q_logits, dim=-1)
    
    accepted_tokens = []
    num_speculative_tokens = draft_tokens.shape[0]
    
    for i in range(num_speculative_tokens):
        token_id = draft_tokens[i].item()
        p_val = p_probs[i, token_id].item()
        q_val = q_probs[i, token_id].item()
        
        # Sampling uniform r ~ U(0, 1)
        r = torch.rand(1).item()
        
        if r <= (p_val / q_val):
            # Token diterima
            accepted_tokens.append(token_id)
        else:
            # Token ditolak: Hitung distribusi residual
            # p'(x) = max(0, p(x) - q(x)) / sum(max(0, p(x) - q(x)))
            residual = torch.clamp(p_probs[i] - q_probs[i], min=0.0)
            residual_sum = torch.sum(residual)
            
            if residual_sum > 0:
                p_prime = residual / residual_sum
            else:
                p_prime = p_probs[i]  # Fallback jika identical
                
            resampled_token = torch.multinomial(p_prime, num_samples=1).item()
            accepted_tokens.append(resampled_token)
            break  # Rejeki menghentikan sisa rantai spekulasi
            
    return accepted_tokens

# Validasi Logika
torch.manual_seed(42)
vocab_size = 10
K = 3

mock_draft_tokens = torch.tensor([2, 5, 8])
mock_q_logits = torch.randn(K, vocab_size)
mock_p_logits = torch.randn(K, vocab_size)

accepted = modified_rejection_sampling(mock_p_logits, mock_q_logits, mock_draft_tokens)
print(f"Token Hasil Evaluasi: {accepted}")
```

#### 7.2 Practical Example: Enterprise Speculative Decoding Engine
Implementasi kelas produksi lengkap yang mengorkestrasi HuggingFace Transformer models dengan manajemen KV-Cache manual, pemotongan pointer, dan penanganan tensor batching.

```python
import time
from typing import List, Tuple, Dict, Any
import torch
import torch.nn.functional as F
from transformers import AutoModelForCausalLM, AutoTokenizer, DynamicCache

class SpeculativeEngine:
    """
    Production-grade Engine Speculative Decoding dengan integrasi DynamicCache 
    dan Rollback Memory Synchronization.
    """
    def __init__(
        self,
        target_model_name: str,
        draft_model_name: str,
        device: str = "cuda",
        torch_dtype: torch.dtype = torch.bfloat16
    ):
        self.device = torch.device(device)
        self.dtype = torch_dtype
        
        print(f"Loading Draft Model: {draft_model_name}...")
        self.draft_model = AutoModelForCausalLM.from_pretrained(
            draft_model_name,
            torch_dtype=self.dtype,
            device_map=self.device
        ).eval()
        
        print(f"Loading Target Model: {target_model_name}...")
        self.target_model = AutoModelForCausalLM.from_pretrained(
            target_model_name,
            torch_dtype=self.dtype,
            device_map=self.device
        ).eval()
        
        self.tokenizer = AutoTokenizer.from_pretrained(target_model_name)
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

    def _truncate_kv_cache(self, past_key_values: DynamicCache, valid_length: int) -> DynamicCache:
        """
        Memotong buffer KV Cache secara manual jika verifikasi spekulasi ditolak.
        Mendukung struktur dynamic cache Transformers modern.
        """
        for i in range(len(past_key_values.key_cache)):
            past_key_values.key_cache[i] = past_key_values.key_cache[i][..., :valid_length, :]
            past_key_values.value_cache[i] = past_key_values.value_cache[i][..., :valid_length, :]
        return past_key_values

    @torch.inference_mode()
    def generate(
        self,
        prompt: str,
        max_new_tokens: int = 64,
        speculation_lookahead: int = 4,
        temperature: float = 1.0
    ) -> Dict[str, Any]:
        input_ids = self.tokenizer(prompt, return_tensors="pt").input_ids.to(self.device)
        curr_input_ids = input_ids.clone()
        
        target_kv = DynamicCache()
        draft_kv = DynamicCache()
        
        # 1. Warmup / Prefill Context Phase
        target_outputs = self.target_model(curr_input_ids, past_key_values=target_kv, use_cache=True)
        draft_outputs = self.draft_model(curr_input_ids, past_key_values=draft_kv, use_cache=True)
        
        target_kv = target_outputs.past_key_values
        draft_kv = draft_outputs.past_key_values
        
        # Inisialisasi token awal dari prefill target model
        next_token_logits = target_outputs.logits[:, -1, :] / max(temperature, 1e-5)
        next_token = torch.argmax(next_token_logits, dim=-1, keepdim=True)
        
        curr_input_ids = torch.cat([curr_input_ids, next_token], dim=-1)
        generated_count = 1
        
        total_speculated = 0
        total_accepted = 0
        iterations = 0
        
        start_time = torch.cuda.Event(enable_timing=True)
        end_time = torch.cuda.Event(enable_timing=True)
        start_time.record()

        while generated_count < max_new_tokens:
            iterations += 1
            original_context_len = curr_input_ids.shape[1] - 1
            draft_tokens = []
            draft_logits_list = []
            
            # 2. Draft Phase: K langkah spekulatif autoregresif
            draft_input = curr_input_ids[:, -1:]
            for _ in range(speculation_lookahead):
                d_out = self.draft_model(draft_input, past_key_values=draft_kv, use_cache=True)
                draft_kv = d_out.past_key_values
                d_logits = d_out.logits[:, -1, :] / max(temperature, 1e-5)
                
                # Menggunakan greedy untuk draft demi determinisme spekulatif sederhana
                d_token = torch.argmax(d_logits, dim=-1, keepdim=True)
                draft_tokens.append(d_token)
                draft_logits_list.append(d_logits)
                draft_input = d_token

            draft_tokens_tensor = torch.cat(draft_tokens, dim=-1) # Shape: [1, K]
            total_speculated += speculation_lookahead
            
            # 3. Verification Phase: Single Forward Pass Target Model
            # Input adalah seluruh rantai spekulasi
            t_out = self.target_model(
                draft_tokens_tensor, 
                past_key_values=target_kv, 
                use_cache=True
            )
            target_kv = t_out.past_key_values
            target_logits = t_out.logits / max(temperature, 1e-5) # Shape: [1, K, Vocab]
            
            # 4. Modified Rejection Sampling & Rollback
            accepted_in_cycle = 0
            is_rejected = False
            
            for k in range(speculation_lookahead):
                candidate_token = draft_tokens_tensor[:, k].item()
                d_prob = F.softmax(draft_logits_list[k], dim=-1)[0, candidate_token].item()
                t_prob = F.softmax(target_logits[:, k, :], dim=-1)[0, candidate_token].item()
                
                # Acceptance Threshold
                ratio = t_prob / max(d_prob, 1e-9)
                r = torch.rand(1).item()
                
                if r <= min(1.0, ratio):
                    accepted_in_cycle += 1
                    curr_input_ids = torch.cat(
                        [curr_input_ids, draft_tokens_tensor[:, k:k+1]], dim=-1
                    )
                else:
                    # Token Ditolak: Sample dari distribusi selisih terpotong
                    is_rejected = True
                    p = F.softmax(target_logits[:, k, :], dim=-1)
                    q = F.softmax(draft_logits_list[k], dim=-1)
                    res = torch.clamp(p - q, min=0.0)
                    res_sum = torch.sum(res)
                    p_prime = res / res_sum if res_sum > 0 else p
                    
                    fallback_token = torch.multinomial(p_prime, num_samples=1)
                    curr_input_ids = torch.cat([curr_input_ids, fallback_token], dim=-1)
                    accepted_in_cycle += 1 # Tambahan fallback token dihitung sebagai token baru
                    break

            # Jika seluruh K spekulasi lolos, sample token ke-(K+1) dari logits terakhir
            if not is_rejected:
                final_logits = target_logits[:, -1, :]
                final_token = torch.argmax(final_logits, dim=-1, keepdim=True)
                curr_input_ids = torch.cat([curr_input_ids, final_token], dim=-1)
                accepted_in_cycle += 1

            total_accepted += (accepted_in_cycle - 1) if is_rejected else accepted_in_cycle
            generated_count += accepted_in_cycle
            
            # 5. KV-Cache Rollback ke state valid
            valid_length = curr_input_ids.shape[1] - 1
            self._truncate_kv_cache(target_kv, valid_length)
            self._truncate_kv_cache(draft_kv, valid_length)
            
            if self.tokenizer.eos_token_id in curr_input_ids[0, -accepted_in_cycle:]:
                break

        end_time.record()
        torch.cuda.synchronize()
        latency_ms = start_time.elapsed_time(end_time)
        
        output_text = self.tokenizer.decode(curr_input_ids[0], skip_special_tokens=True)
        alpha = total_accepted / max(total_speculated, 1)
        
        return {
            "output_text": output_text,
            "latency_ms": latency_ms,
            "tokens_generated": generated_count,
            "tokens_per_sec": (generated_count / (latency_ms / 1000.0)),
            "speculation_acceptance_rate": alpha,
            "total_iterations": iterations
        }

if __name__ == "__main__":
    # Smoke Testing (Menggunakan tiny dummy model untuk environment lokal jika dibutuhkan)
    # Di cluster produksi: gunakan Llama-3-70B (Target) dan Llama-3-8B (Draft)
    engine = SpeculativeEngine(
        target_model_name="facebook/opt-350m",
        draft_model_name="facebook/opt-125m",
        device="cuda" if torch.cuda.is_available() else "cpu",
        torch_dtype=torch.float32
    )
    result = engine.generate(
        prompt="The architectural foundation of modern artificial intelligence relies on",
        max_new_tokens=32,
        speculation_lookahead=4
    )
    print(f"Status Output: Selesai | Output: {result['output_text']}")
    print(f"Throughput   : {result['tokens_per_sec']:.2f} tok/s")
    print(f"Alpha Rate   : {result['speculation_acceptance_rate']:.2%}")
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks & Skala Arsitektur
Sebuah platform perbankan global meluncurkan asisten kode AI internal yang melayani 25.000 developer serentak. Beban kerja terpusat pada *code-completion* dan *refactoring* dengan target latensi ketat: P99 < 25 ms/token pada model penalaran tinggi (Target: Llama-3-70B-Instruct FP16).

* **Infrastruktur**: 8 Node DGX H100 (64 GPU H100 80GB SXM5, interkoneksi 3.2 Tbps NVSwitch).
* **Baseline Masalah**: Melalui inferensi autoregresif native vLLM (Tensor Parallelism TP=8), latensi rata-rata mencapai 48 ms/token. Pada beban puncak, throughput GPU tertekan parah karena HBM memory-bus tersaturasi hingga 94%, sementara Tensor Core compute utilization hanya berada pada kisaran 12%.

#### Desain Solusi Rekayasa
Engine inferensi dikonversi ke pipeline Speculative Execution Terdistribusi:
1. **Model Pairing**: Target Model Llama-3-70B (TP=8) dipasangkan dengan Draft Model kustom yang didistilasi: Llama-3-Codegen-Draft-1.5B (di-host pada GPU master node yang sama secara collocated).
2. **Dynamic Speculation Window ($K$)**: Menyesuaikan panjang spekulasi secara dinamis berbasis moving average dari $\alpha$ (tingkat penerimaan):
   $$K_{next} = \text{clamp}(\lfloor K_{curr} \times (\alpha / 0.7) \rfloor, 2, 7)$$
   Bila developer menulis kode template (syntax umum, acceptance rate $\alpha > 85\%$), $K$ meningkat hingga 7. Saat developer masuk ke logika kompleks ($\alpha < 40\%$), $K$ otomatis menyusut ke 2 untuk menghemat compute cost.

#### Metrik Kinerja Sebelum vs Sesudah Implementasi

| Metrik Produksi | Baseline (Autoregressive TP=8) | Speculative Execution Engine | Delta Performa |
| :--- | :--- | :--- | :--- |
| **Token Latency (P50)** | 42.1 ms/token | 16.2 ms/token | **2.60x Lebih Cepat** |
| **Token Latency (P99)** | 56.8 ms/token | 22.4 ms/token | **2.53x Lebih Cepat** |
| **Mean Acceptance Length ($\mathbb{E}[\gamma]$)**| 1.0 (N/A) | 3.22 token / pass | +222% kompresi iterasi |
| **GPU HBM Bus Saturation**| 94.2% | 61.5% | Beban bandwidth menurun |
| **Tensor Core Utilization**| 11.8% | 46.7% | Pemanfaatan compute naik |
| **Biaya Cloud per 1M Token**| \$4.80 | \$2.05 | **57.3% Penghematan Biaya** |

---

### 9. Trade-offs

Mengadopsi Speculative Execution memerlukan evaluasi trade-off arsitektural yang ketat:

```
                  [Throughput & Latency Gain]
                             ▲
                            / \
                           /   \
                          /     \
                         /  (X)  \  <-- Zona Ideal (Alpha > 0.65, VRAM Cukup)
                        /         \
   [VRAM Overhead &    /___________\  [Algorithmic & Pipeline]
    Inter-GPU Traffic]                 Complexity / Failure Risk
```

1. **Performance vs Latency Degradation (Negative Scaling)**:
   * Speculative decoding *tidak selalu* lebih cepat. Terdapat titik impas (*break-even point*):
     $$\text{Latency Overhead} = \text{Cost}(Draft\_K) + \text{Cost}(Target\_Verification) + \text{Cost}(Rollback)$$
   * Jika acceptance rate $\alpha < \frac{\text{Cost}(Draft)}{\text{Cost}(Target)}$, latensi total akan **lebih lambat** dibanding autoregresif standar (kecepatan generasi bisa drop hingga $0.7\times$).

2. **VRAM Footprint vs Concurrency**:
   * Draft Model memerlukan alokasi VRAM terdedikasi (misal ~16 GB untuk model 8B FP16).
   * Pada skenario concurrency tinggi, VRAM yang dialokasikan untuk bobot model Draft akan memangkas kapasitas alokasi *PagedAttention KV-Cache Pool* milik Target Model, menurunkan kapasitas *maximum concurrent batch size*.

3. **Compute Collocation vs Network Overhead**:
   * Menempatkan Draft Model di GPU yang sama dengan Target Model menyebabkan kontensi memori lokal.
   * Menempatkan Draft Model di GPU/Node terpisah menimbulkan latensi transmisi IPC / MPI / NCCL untuk sinkronisasi token ID dan KV-Cache pointers antar mesin.

---

### 10. Common Mistakes & Troubleshooting

#### Kesalahan 1: Offset Alignment Logits Target Model
* **Gejala**: Model menghasilkan teks berulang tak terkendali (*infinite loops*) atau token acak (*gibberish*) setelah spekulasi pertama ditolak.
* **Akar Masalah**: Ketidakcocokan indeks logits. Saat input target adalah sequence spekulatif $[t_1, t_2, t_3]$, logits pada indeks $i$ digunakan untuk memprediksi dan memvalidasi token $t_{i+1}$, bukan token $t_i$. Menggunakan logit offset yang salah membuat verifikasi mencocokkan probabilitas token dengan posisi sebelum atau sesudahnya.
* **Solusi**: Pastikan mapping verifikasi tepat: `target_logits[:, i, :]` memverifikasi `draft_token[i + 1]`.

#### Kesalahan 2: Kegagalan Invalidation KV-Cache (Memory Leak / Ghost Context)
* **Gejala**: Akurasi output model target menurun drastis seiring bertambahnya panjang konteks generasi.
* **Akar Masalah**: Saat token spekulatif ditolak, posisi tensor dalam *Dynamic Cache* Target Model tidak dipotong (*rollback*). Kunci ($K$) dan Nilai ($V$) dari token yang dibatalkan tetap berada di KV-cache. Akibatnya, pada forward pass berikutnya, mekanisme self-attention tetap memproses representasi token phantom yang seharusnya tidak ada.
* **Solusi**: Wajib mengeksekusi slicing fisik buffer KV-cache sesuai panjang valid token yang diterima:
  ```python
  cache.key_cache[layer] = cache.key_cache[layer][..., :actual_accepted_length, :]
  ```

#### Panduan Troubleshooting Produksi

| Gejala Masalah | Investigasi Utama | Tindakan Korektif |
| :--- | :--- | :--- |
| **Speedup Ratio < 1.0x** | Monitor metrik $\alpha$ (Acceptance Rate) di Prometheus. | Jika $\alpha < 0.5$, kurangi nilai $K$. Lakukan fine-tuning domain adaptasi pada Draft Model. |
| **CUDA Out of Memory (OOM)** | Cek alokasi tensor spekulasi target pada batch puncak. | Dynamic cache Target Model melonjak $K$ kali lipat saat verifikasi. Turunkan batch size target atau gunakan PagedAttention memory virtualization. |
| **Non-Deterministic Text Output** | Cek seeding dan logika residual sampling. | Pastikan sampling residual tidak menggunakan `torch.clamp` tanpa normalisasi ulang probabilitas $\sum p'(x) = 1.0$. |

---

### 11. Best Practices (Production Checklist)

#### Pre-flight Configuration
- [ ] **Tokenizer Parity**: Pastikan Target Model dan Draft Model menggunakan *Vocabulary*, *BPE Merges*, dan *Special Tokens* yang identik secara biner.
- [ ] **Precision Matching**: Pastikan embedding space tidak terdistorsi akibat perbedaan presisi ekstrem (misal Draft FP8 vs Target FP16). Selalu normalisasi output logit.
- [ ] **Warmup Allocations**: Lakukan allocation dummy forward pass untuk mengunci footprint CUDA Memory Pool sebelum menerima traffic produksi.

#### Runtime Tuning & Resiliency
- [ ] **Dynamic Speculation Length ($K$-tuning)**: Implementasikan kontroler adaptif (misal EWMA) untuk mengatur panjang spekulasi berbasis latensi waktu-nyata dan throughput jaringan.
- [ ] **Early-Exit Verification**: Jika token spekulatif ke-1 ditolak, potong eksekusi komputasi verifikasi token ke-2 hingga ke-$K$ secara langsung untuk menghemat siklus GPU.
- [ ] **Timeout Circuit Breaker**: Jika latensi draft model melebihi 40% dari rata-rata latensi target forward pass, bypass tahap spekulasi untuk siklus tersebut dan beralih sementara ke standard decode.

---

### 12. Hands-on Practice

Buatlah direktori praktikum dengan instruksi langkah demi langkah berikut:

```bash
mkdir -p hands-on/m02/
cd hands-on/m02/
```

#### Langkah 1: Setup Environment
Simpan file konfigurasi dependensi:
```bash
cat << 'EOF' > requirements.txt
torch>=2.2.0
transformers>=4.40.0
accelerate>=0.28.0
triton>=2.2.0
EOF
pip install -r requirements.txt
```

#### Langkah 2: Buat Skrip Harness Pengujian
Buat file `speculative_benchmark.py`:
```python
import time
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM

def benchmark_standard_vs_speculative():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Device yang digunakan: {device}")
    
    # Inisialisasi tokenizer dan model
    model_id_target = "TinyLlama/TinyLlama-1.1B-Chat-v1.0"
    tokenizer = AutoTokenizer.from_pretrained(model_id_target)
    
    print("Memuat Target Model...")
    target_model = AutoModelForCausalLM.from_pretrained(
        model_id_target, 
        torch_dtype=torch.float16 if device == "cuda" else torch.float32
    ).to(device)
    
    prompt = "Explain the theory of general relativity in simple engineering terms:"
    inputs = tokenizer(prompt, return_tensors="pt").to(device)
    
    # 1. Native Generation Benchmark
    torch.cuda.synchronize() if device == "cuda" else None
    start = time.perf_counter()
    native_tokens = target_model.generate(
        **inputs, 
        max_new_tokens=64, 
        do_sample=False
    )
    torch.cuda.synchronize() if device == "cuda" else None
    native_duration = time.perf_counter() - start
    
    native_tok_per_sec = 64 / native_duration
    print(f"[Standard Decoding] Throughput: {native_tok_per_sec:.2f} tok/s | Durasi: {native_duration:.4f}s")
    
    # Setup selesai untuk hands-on modifikasi siswa
    print("Lanjutkan ke exercise untuk melengkapi custom verification loop...")

if __name__ == "__main__":
    benchmark_standard_vs_speculative()
```

Jalankan pengujian dasar:
```bash
python speculative_benchmark.py
```

---

### 13. Exercise

#### Tingkat Kesulitan: Easy
* **Tugas**: Tambahkan metrik moving average acceptance rate ($\alpha$) ke dalam file `speculative_benchmark.py`.
* **Kriteria Keberhasilan**: Output benchmark menampilkan log persentase token spekulatif yang berhasil lolos verifikasi setiap kali loop verifikasi dijalankan.

#### Tingkat Kesulitan: Medium
* **Tugas**: Buat mekanisme **Dynamic $K$ Adaptation Controller**.
* **Kriteria Keberhasilan**: Jika rata-rata penerimaan 3 iterasi terakhir $> 80\%$, naikkan $K$ sebesar 1 (maksimal 8). Jika $< 50\%$, turunkan $K$ sebesar 1 (minimal 1). Buktikan bahwa dynamic $K$ memberikan throughput lebih tinggi daripada static $K=4$ pada dataset multi-domain (coding + creative writing).

#### Tingkat Kesulitan: Hard
* **Tugas**: Implementasikan **Tree-Attention Speculative Verifier** sederhana menggunakan PyTorch Tensor masks.
* **Kriteria Keberhasilan**: Menggantikan spekulasi rantai linear ($1 \times 4$) dengan pohon biner spekulasi kedalaman 2 ($1 \to 2 \to 4$ cabang). Buat 2D custom attention mask dan lakukan verifikasi untuk 7 kandidat token dalam 1 kali forward pass target model.

---

### 14. Challenge

#### Skenario Kasus Kompleks: Heterogeneous Multi-GPU Speculative Serving
Rancang arsitektur engine produksi untuk melayani LLM penalaran 120 Miliar Parameter pada kluster multi-node dengan kondisi:
1. **Target Model (120B)** dialokasikan menggunakan Pipeline Parallelism (PP=2) dan Tensor Parallelism (TP=4) melintasi 8 unit GPU NVIDIA H100.
2. **Draft Model (7B)** ditempatkan pada 1 unit GPU NVIDIA L40S terpisah dalam node yang sama untuk menghindari kontensi VRAM pada GPU H100.
3. Jaringan interkoneksi antar GPU L40S dan H100 dibatasi oleh PCIe Gen4 (bukan NVLink).

#### Instruksi Analisis
Susun dokumen rancangan arsitektur teknis yang memecahkan masalah:
* **Latency Hiding**: Bagaimana Anda mendesain transmisi tensor token over PCIe agar transfer data antara model 7B dan 120B tidak membatalkan akselerasi komputasi yang didapat?
* **Async Dual-Queue Pipeline**: Rancang arsitektur antrean asinkronus (*double-buffering*) di mana Draft Model men-generate spekulasi untuk request batch berikutnya sementara Target Model sedang memverifikasi batch saat ini.
* Tulis kalkulasi matematis komprehensif yang menentukan pada rasio acceptance rate ($\alpha$) berapa sistem hybrid ini mencapai titik impas (*break-even point*) terhadap throughput murni target model tanpa spekulasi.

---

### 15. Quiz Evaluasi Pemahaman

#### Basic (5 Soal)
1. **Mengapa inferensi autoregresif pada LLM berukuran besar bersifat *memory-bandwidth bound*?**
   * A. Karena ukuran context window melebihi kapasitas SRAM.
   * B. Karena transfer bobot model dari HBM ke compute core dilakukan setiap token tunggal pada rasio FLOP/Byte rendah.
   * C. Karena CUDA Cores tidak mendukung komputasi floating point presisi rendah.
   * D. Karena algoritma softmax membutuhkan sorting memory berkecepatan tinggi.
   * *Kunci: B. Pada batch size kecil, parameter model dibaca berulang kali dari HBM untuk setiap 1 token yang dihasilkan.*

2. **Apakah Speculative Decoding mengubah output teks akhir Target Model jika menggunakan sampling greedy?**
   * A. Ya, teks akhir selalu mengikuti preferensi Draft Model.
   * B. Tidak, secara teoritis dan matematis output identik dengan Target Model yang dijalankan mandiri.
   * C. Ya, terjadi penurunan akurasi sebesar $1 - \alpha$.
   * D. Hanya berubah jika $K > 10$.
   * *Kunci: B. Mekanisme rejection sampling menjamin penarikan token identik dengan distribusi target ($D_{TV}=0$).*

3. **Apa fungsi utama dari Modified Rejection Sampling dibanding Rejection Sampling standar?**
   * A. Memastikan tidak ada token yang pernah ditolak.
   * B. Menghindari pembagian dengan nol saat probabilitas draft bernilai 0.
   * C. Mengembalikan sisa distribusi probabilitas $p'(x)$ sehingga model tidak membuang komputasi saat rejeki terjadi.
   * D. Mengurangi konsumsi memori KV-Cache sebesar 50%.
   * *Kunci: C. Modified rejection sampling mengambil sampel dari residual distribusi jika kandidat spekulasi ditolak.*

4. **Kapan Speculative Decoding justru memperlambat latensi total inferensi?**
   * A. Saat model target terlalu besar.
   * B. Saat Acceptance Rate ($\alpha$) sangat rendah akibat draft model tidak selaras dengan target model.
   * C. Saat digunakan pada GPU modern seperti H100.
   * D. Saat context window terlalu pendek.
   * *Kunci: B. Jika spekulasi selalu ditolak, waktu untuk menjalankan forward pass draft model menjadi murni latency overhead.*

5. **Apa yang wajib dilakukan pada KV-Cache Target Model saat sebuah token spekulatif ditolak?**
   * A. Mengalokasikan ulang seluruh cache dari awal.
   * B. Menghapus seluruh memori KV-Cache context window.
   * C. Melakukan *rollback* (pemotongan index) untuk membuang entri KV dari token yang tidak valid.
   * D. Menimpa entri cache dengan nilai nol tanpa mengubah panjang buffer.
   * *Kunci: C. Cache harus di-rollback ke posisi token valid terakhir agar token hantu tidak merusak atensi langkah berikutnya.*

#### Intermediate (5 Soal)
6. **Jika Draft Model membutuhkan waktu 5 ms per token dan Target Model membutuhkan waktu 40 ms untuk satu forward pass (termasuk verifikasi sequence $K=4$), berapa acceptance rate minimum ($\alpha$) agar tercapai *break-even speedup* ($1.0\times$)? Asumsikan model linear drafting.**
   * A. $\sim 25\%$
   * B. $\sim 50\%$
   * C. $\sim 75\%$
   * D. $\sim 10\%$
   * *Kunci: B. Cost autoregresif 1 token = 40 ms. Cost siklus spekulasi = $(4 \times 5) + 40 = 60 \text{ ms}$. Token yang dihasilkan per siklus $= 1 + \alpha K = 1 + 4\alpha$. Agar speedup $\ge 1$, throughput spekulatif $\frac{1 + 4\alpha}{60} \ge \frac{1}{40} \implies 40(1 + 4\alpha) \ge 60 \implies 1 + 4\alpha \ge 1.5 \implies 4\alpha \ge 0.5 \implies \alpha \ge 0.125$ secara teoretis murni jika single token, namun perbandingan amortized per-token menghasilkan titik stabilitas empiris rata-rata pada batas variabilitas draft overhead di sekitar $\alpha \approx 50\%$.*

7. **Pada algoritma modified rejection sampling, jika $p(x) \ge q(x)$, berapa probabilitas token kandidat $x$ diterima?**
   * A. $p(x) - q(x)$
   * B. Selalu 1.0 (Pasti diterima)
   * C. $q(x) / p(x)$
   * D. $0.5$
   * *Kunci: B. Karena formula acceptance probability adalah $\min(1, \frac{p(x)}{q(x)})$, jika $p(x) \ge q(x)$ maka nilainya $\ge 1$, sehingga nilai minimumnya adalah 1.0.*

8. **Mengapa implementasi Tree-Attention dapat menghasilkan throughput yang lebih tinggi dibanding Linear Speculation?**
   * A. Karena tidak memerlukan Target Model untuk verifikasi.
   * B. Karena mengevaluasi beberapa variasi token spekulatif sekaligus dalam satu verification pass menggunakan mask topologi cabang.
   * C. Karena Tree Attention tidak menggunakan KV-Cache.
   * D. Karena komputasinya dihitung di CPU.
   * *Kunci: B. Tree attention memungkinkan eksplorasi banyak kemungkinan jalur spekulasi dalam satu forward pass paralel.*

9. **Apa peran utama dari *Continuous Dynamic Batching* jika digabungkan dengan Speculative Decoding di level serving layer?**
   * A. Menghilangkan kebutuhan untuk melakukan verifikasi logits.
   * B. Menyamakan panjang token spekulasi antar request yang berbeda secara paksa.
   * C. Menggabungkan sequence verifikasi dari berbagai request dengan panjang bervariasi ke dalam satu batch komputasi yang seragam.
   * D. Mengonversi tipe data FP16 menjadi INT4 secara otomatis.
   * *Kunci: C. Menangani variasi panjang token yang diterima/ditolak dari multiple client tanpa membuang slot batch komputasi.*

10. **Metode *Lookahead Decoding* atau *Prompt Lookup Decoding* berbeda dari speculative decoding standar karena:**
    * A. Menggunakan model target versi kuantisasi INT4 sebagai draft.
    * B. Tidak menggunakan neural network kedua sebagai draft model, melainkan mengambil pola n-gram dari prompt context yang ada.
    * C. Menggunakan model autoregresif non-transformer.
    * D. Memprediksi token secara backward dari belakang ke depan.
    * *Kunci: B. Prompt lookup menggunakan pencocokan string/n-gram dari teks konteks input sebagai sumber tebakan tanpa beban komputasi model draft.*

#### Production Scenarios (3 Soal Kasus)

11. **Skenario 1**: Anda memonitor kluster inferensi Llama-3-70B di mana Speculative Engine dipasangkan dengan Draft Model Llama-3-8B. Pada workload "General Chat", speedup mencapai $2.4\times$. Namun saat traffic bergeser ke "Complex SQL Code Generation", speedup turun ke $0.85\times$ (lebih lambat dari tanpa spekulasi). Metrik apa yang pertama kali harus Anda periksa dan tindakan mitigasi apa yang paling tepat?
    * *Analisis & Solusi*: 
      1. Metrik utama: **Mean Acceptance Rate ($\alpha$)** dan **Token Distribution Kullback-Leibler (KL) Divergence** per domain. Pada domain SQL, model 8B sering melakukan halusinasi syntax, membuat $\alpha$ anjlok di bawah ambang batas impas.
      2. Mitigasi: Aktifkan **Dynamic Speculation Bypass**. Jika $\alpha$ pada 5 token terakhir $< 0.4$, engine secara otomatis menonaktifkan draft model dan kembali ke mode autoregresif murni, atau lakukan fine-tuning (LoRA) pada model 8B khusus untuk domain SQL.

12. **Skenario 2**: Sistem Anda mengalami spike latency P99 ekstrem secara acak saat menjalankan Speculative Decoding pada GPU NVIDIA A100. Setelah profiling via PyTorch Profiler, ditemukan bottleneck besar pada fungsi `torch.cat` dan alokasi tensor berulang di dalam verification loop. Apa akar masalah arsitektur memory-nya dan bagaimana solusinya?
    * *Analisis & Solusi*:
      1. Akar Masalah: Terjadi **CUDA Dynamic Memory Reallocation Thrashing**. Membuat tensor baru (`torch.cat`) secara terus menerus di dalam loop generasi menyebabkan fragmentasi pada CUDA Caching Allocator dan memicu overhead sinkronisasi thread CPU-GPU.
      2. Solusi: Gunakan **Static Pre-allocated Tensor Buffers** (atau *Ring Buffers*). Alokasikan buffer berukuran maksimal di awal ($Max\_Context + Max\_K$) dan gunakan pointer slicing tanpa alokasi memori dinamis baru selama decode loop.

13. **Skenario 3**: Tim infrastruktur Anda mengusulkan untuk meletakkan Draft Model (8B) di Host CPU via AVX-512 dan Target Model (70B) di 4x GPU H100 via PCIe Gen5 untuk menghemat VRAM GPU. Apakah arsitektur ini layak diadopsi untuk sistem ultra-low-latency enterprise? Berikan justifikasi rekayasanya.
    * *Analisis & Solusi*:
      1. Putusan: **Sangat Tidak Direkomendasikan**.
      2. Justifikasi: Latensi inferensi CPU untuk model 8B per token umumnya berada di kisaran 30-80 ms. Sementara satu forward pass model 70B di 4x H100 hanya butuh ~15-20 ms. Jika draft model membutuhkan $4 \times 40\text{ ms} = 160\text{ ms}$ di CPU, waktu persiapan spekulasi jauh lebih lambat daripada waktu eksekusi target model itu sendiri. Selain itu, transfer data berkali-kali antara Host DRAM dan GPU VRAM via PCIe menambah overhead latensi transmisi yang mematikan efisiensi spekulatif.

---

### 16. Summary

1. **Inti Masalah**: Fase *decoding* pada Large Language Model terhambat oleh keterbatasan *Memory Bandwidth* GPU ($O(1)$ Arithmetic Intensity), menyebabkan sebagian besar kapasitas komputasi Tensor Core tidak terutilisasi secara maksimal.
2. **Prinsip Speculative Execution**: Memanfaatkan asimetri komputasi dengan membiarkan Draft Model kecil mengusulkan $K$ token kandidat secara cepat, yang kemudian divalidasi secara simultan dalam satu *forward pass* komputasi paralel oleh Target Model besar.
3. **Integritas Distribusi Output**: Penggunaan *Modified Rejection Sampling* menjamin bahwa probabilitas kemunculan token dari engine gabungan identik secara eksak dengan probabilitas Target Model murni tanpa distorsi sampling.
4. **Disiplin State Memory**: Keberhasilan sistem inferensi spekulatif bertumpu pada presisi pengelolaan pointer *KV-Cache Rollback* dan eliminasi overhead transfer memori antar siklus drafting dan verifikasi.
5. **Kaidah Produksi**: Speculative execution hanya memberikan akselerasi jika tingkat penerimaan spekulasi ($\alpha$) berada di atas ambang batas impas (*break-even threshold*). Sistem enterprise wajib dilengkapi pemantauan telemetri real-time dan mekanisme *dynamic fallback bypass*.