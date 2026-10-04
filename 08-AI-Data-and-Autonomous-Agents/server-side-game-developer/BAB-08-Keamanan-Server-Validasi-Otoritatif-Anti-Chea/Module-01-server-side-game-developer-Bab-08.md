# Bab 08: Keamanan Server, Validasi Otoritatif, & Anti-Cheat
## Module 01: Fondasi Validasi Otoritatif, Mitigasi Eksploitasi Klien, dan Deteksi Agen Otonom Malisious

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Menganalisis dan Memetakan Pola Eksploitasi Sisi Klien:** Mengidentifikasi celah keamanan pada model sinkronisasi jaringan game (misal: *speed hack*, manipulasi waktu/clock drift, *teleportation*, dan *action desync*).
- **Merancang Arsitektur Validasi State Otoritatif (*Server-Authoritative Architecture*):** Membangun pipeline pemrosesan input deterministik di mana server memegang kendali absolut terhadap mutasi state dunia game.
- **Mengimplementasikan Algoritma Validasi Kinematika & Ruang:** Menyusun logika verifikasi pergerakan berbasis hukum fisika diskret, batas akselerasi, toleransi latensi jaringan (*lag compensation envelope*), dan collision box server.
- **Membangun Sistem Deteksi Entropi Input untuk Mengidentifikasi Agen Bot/Otonom:** Menerapkan analisis statistik pada deret waktu (*time-series input stream*) untuk membedakan pergerakan pemain manusia dari otomasi skrip/bot AI.
- **Menerapkan Mekanisme Rekonsiliasi State dan Rollback Korrektif:** Menghitung deviasi state antara klien dan server serta mengembalikan (*reconcile*) state klien secara mulus saat terdeteksi anomali tanpa membebani throughput jaringan.

---

### 2. Concept Overview

Dalam arsitektur *multiplayer online game*, aturan fundamental nomor satu adalah: **"Never Trust the Client" (Klien berada di lingkungan yang sepenuhnya dapat dikompromikan oleh musuh).**

```
              ┌────────────────────────────────────────────────────────┐
              │                UNTRUSTED CLIENT BOUNDARY               │
              │  [Game Client / Memory Injection / Script / Bot Engine]│
              └──────────────────────────┬─────────────────────────────┘
                                         │ Raw Player Intents
                                         │ (e.g., Target Velocity, Inputs)
                                         ▼
              ┌────────────────────────────────────────────────────────┐
              │             NETWORK PERIMETER & INGRESS GATEWAY        │
              │  - Rate Limiting                                       │
              │  - Replay Attack Mitigation (Sequence Token Validation)│
              │  - Time-Budget Tracking (Clock Drift Protection)       │
              └──────────────────────────┬─────────────────────────────┘
                                         │ Sanitized Tick Packets
                                         ▼
              ┌────────────────────────────────────────────────────────┐
              │           AUTHORITATIVE SIMULATION PIPELINE            │
              │                                                        │
              │  ┌──────────────────┐      ┌────────────────────────┐  │
              │  │ Kinematic Engine │ ───► │ Static/Dynamic Spatial │  │
              │  │  (Euler/Verlet)  │      │ Collision Check        │  │
              │  └────────┬─────────┘      └───────────┬────────────┘  │
              │           │                            │               │
              │           ▼                            ▼               │
              │  ┌──────────────────────────────────────────────────┐  │
              │  │     Heuristic & Entropy Bot/Anomaly Detector     │  │
              │  └────────────────────────┬─────────────────────────┘  │
              └───────────────────────────┼────────────────────────────┘
                                          │
                        ┌─────────────────┴─────────────────┐
                        │ State Outcome                     │
                        ▼                                   ▼
              ┌──────────────────┐                ┌──────────────────┐
              │ State ACCEPTED   │                │ State REJECTED   │
              │ Update World     │                │ Force Correction │
              │ Broadcast Delta  │                │ (Reconciliation) │
              └──────────────────┘                └──────────────────┘
```

#### Mental Model: The Authoritative Oracle
Klien tidak pernah mengirimkan: *"Karakter saya sekarang berada di koordinat (X=150, Y=20, Z=80)"*. Tindakan ini adalah *client-authoritative* dan membuka celah manipulasi memori secara trivial. 

Sebaliknya, klien mengirimkan intensi (*intents/inputs*): *"Pada frame N, tombol 'W' ditekan selama $\Delta t = 16.6\text{ ms}$ dengan sudut rotasi yaw $\theta = 45^\circ$"*. Server bertindak sebagai *Authoritative Oracle*:
1. Mengambil input tersebut dari *jitter buffer*.
2. Memverifikasi apakah klien memiliki hak eksekusi waktu (*time debt budget*).
3. Mensimulasikan pergerakan menggunakan fungsi transisi state deterministik: 
   $$S_{t+1} = f(S_t, I_t, \Delta t)$$
4. Menolak mutasi jika melanggar hukum pergerakan atau menembus geometri level.
5. Mengirimkan *Server World State Snapshot* kembali ke klien.

#### Paradigma AI & Agen Otonom Malisious
Dalam lanskap modern, ancaman tidak terbatas pada modifikasi memori biner (*hex patching*), melainkan agen otonom berbasis *Computer Vision* atau pembacaan paket yang menginjeksikan input secara sintetis (*aimbots*, *farming bots*, *pixel-clickers*). Menghadapi ini, validasi tidak hanya menguji: *"Apakah pergerakan ini valid secara fisika?"*, tetapi juga: *"Apakah distribusi entropi dan variansi koordinat input ini konsisten dengan fisiologi neuromuskular manusia?"*

---

### 3. Why It Matters

1. **Integritas Kompetitif dan Retensi Pemain:** Pada game berbasis kompetitif (FPS, MOBA, Battle Royale), penetrasi *cheater* sebesar 1% dari basis pemain aktif dapat merusak pengalaman bermain hingga 15% pertandingan secara agregat, memicu *churn rate* katastropik dan kegagalan finansial game.
2. **Perlindungan Ekonomi Dalam Game (*Game Economy Integrity*):** Eksploitasi validasi inventory atau movement berimplikasi langsung pada duplikasi item, *speed-farming bots*, dan inflasi mata uang in-game yang meruntuhkan monetisasi enterprise.
3. **Beban Komputasi Cloud (*Infrastructure Overload*):** Skrip *denial-of-service* mikro di mana klien sengaja membanjiri server dengan paket input diskor (*out-of-order packets* atau *impossible paths*) dapat memicu lonjakan kalkulasi raycasting server, mengakibatkan degradasi performa tick (*tick-rate drop*) di seluruh kontainer game server.

---

### 4. Arsitektur & Diagram Komponen

Berikut adalah arsitektur *low-latency authoritative anti-cheat ingestion pipeline* yang dirancang untuk game server real-time (tick rate: 60Hz).

```
+--------------------------------------------------------------------------------------------------+
|                                    GAME ENGINE SERVER CORE                                       |
+--------------------------------------------------------------------------------------------------+
                                                    |
       [Inbound Network Layer (UDP/KCP/WebSockets)] | Raw Datagrams
                                                    v
+--------------------------------------------------------------------------------------------------+
| 1. INGRESS SANITIZATION & SECURITY LAYER                                                         |
|    - Anti-Replay: Sliding Window Sequence ID Tracking                                            |
|    - Rate-Limiter: Token Bucket per Connection (Limit max packets/sec)                           |
|    - Time Drift Analyzer: Token Credit vs Client Clock Simulation                                |
+--------------------------------------------------------------------------------------------------+
                                                    | Sanitized Input Packets
                                                    v
+--------------------------------------------------------------------------------------------------+
| 2. JITTER BUFFER & CLIENT FRAME UNPACKER                                                         |
|    - Ring Buffer per Entity: Menyusun input sesuai Sequence Number                               |
|    - Desync & Drop Detector: Mendeteksi lonjakan delta waktu mencurigakan                        |
+--------------------------------------------------------------------------------------------------+
                                                    | Ordered Fixed-Tick Inputs
                                                    v
+--------------------------------------------------------------------------------------------------+
| 3. AUTHORITATIVE VALIDATION PIPELINE (Executed inside Tick Loop)                                 |
|                                                                                                  |
|   [Step 3A: Kinematics Validator]                                                                |
|   - Compute: V_max = BaseSpeed * BuffModifiers                                                   |
|   - Tolerance check: ||P_client - P_simulated|| <= Epsilon(Latency, Jitter)                      |
|                                                                                                  |
|   [Step 3B: Spatial & Collision Boundary Validation]                                            |
|   - Raycast/AABB sweep check against static spatial hash tree                                    |
|   - Wall-phase & Out-of-bounds prevention                                                        |
|                                                                                                  |
|   [Step 3C: Input Entropy & Behavioral Heuristics]                                               |
|   - Shannon Entropy calculation over delta angles (Yaw/Pitch)                                    |
|   - Minimum human muscle tremor threshold (Detecting zero-variance snaps)                        |
+--------------------------------------------------------------------------------------------------+
                     |                                                    |
        (Valid Input Execution)                              (Invalid Input / Exploit)
                     v                                                    v
+------------------------------------------+       +-----------------------------------------------+
| 4A. STATE COMMITMENT                     |       | 4B. RECONCILIATION & PENALTY ENGINE           |
| - Commit New Position to World Component |       | - Discard client input                        |
| - Update Spatial Hash / Grid Index       |       | - Teleport entity back to Last Known Good Pos |
| - Mark Entity Dirty for Replication      |       | - Increment Suspicion Score (Cheat Flag)      |
|                                          |       | - Queue Overriding State Correction RPC       |
+------------------------------------------+       +-----------------------------------------------+
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### A. Speed Hack Mitigation: The Token-Bucket Time Budget
Manipulasi kecepatan (*speed hacking*) umumnya dicapai dengan memodifikasi fungsi API waktu sistem operasi di sisi klien (misal: *hooking* `QueryPerformanceCounter` pada Windows). Hal ini membuat game loop klien berjalan lebih cepat dari waktu riil, mengirimkan 120 paket per detik alih-alih 60.

Server menerapkan skema **Time Debt Tracking**:
1. Server menetapkan waktu klien yang diizinkan bertambah sebesar $\Delta t_{server}$ setiap tick server.
2. Setiap kali input klien dieksekusi dengan durasi klaim $\Delta t_{client}$, saldo waktu dikurangi:
   $$\text{Balance}_{t} = \text{Balance}_{t-1} + \Delta t_{server} - \Delta t_{client}$$
3. Jika $\text{Balance}_{t}$ turun di bawah ambang batas negatif tertentu (misal: $-100\text{ ms}$), server menolak eksekusi input dan menandai bahwa klien berusaha mengonsumsi waktu lebih cepat dari waktu fisik (*clock acceleration*).

#### B. Kinematika Ruang dan Toleransi Jitter (*Movement Verification*)
Perpindahan posisi tidak boleh divalidasi hanya dengan rumus sederhana $d = v \times t$. Jaringan internet memiliki variansi latensi (*jitter*) yang menyebabkan dua paket yang dikirim terpisah 16.6ms dapat tiba di server secara simultan (*packet bunching*).

Validasi kinematika server harus menghitung batas perpindahan maksimum ($D_{\max}$) yang diizinkan untuk interval $\Delta t$:
$$D_{\max} = \left( V_{\max} \cdot \Delta t \right) + \frac{1}{2} A_{\max} (\Delta t)^2 + \epsilon_{\text{jitter}}$$

Di mana:
- $V_{\max}$ adalah kecepatan maksimal entitas (memperhitungkan efek status/buff).
- $A_{\max}$ adalah batas akselerasi entitas.
- $\epsilon_{\text{jitter}}$ adalah margin toleransi berbasis deviasi standar latensi round-trip (RTT) pemain:
  $$\epsilon_{\text{jitter}} = \kappa \cdot \sigma_{\text{RTT}} \cdot V_{\max}$$
  ($\kappa$ umumnya bernilai antara $1.5$ hingga $2.0$).

Jika jarak $\| P_{\text{target}} - P_{\text{current}} \| > D_{\max}$, server menolak pergerakan tersebut, membatalkan translasi, dan memicu *state correction*.

#### C. Deteksi Agen Otonom (Bot) Melalui Entropi Input
Bot yang mengeksekusi pathing otonom atau aimbot memiliki karakteristik non-manusia:
1. **Zero Angle Variance:** Aimbot linear menggerakkan sudut pandang (*yaw/pitch*) dengan kecepatan konstan tanpa mikrotremor otot manusia.
2. **Instant Snap:** Perubahan sudut pandang instan dalam 1 tick tanpa kurva akselerasi/deselerasi.
3. **Pola Distribusi Sempurna:** Entropi Shannon dari input pergerakan yang dihasilkan oleh bot terprogram sering kali menunjukkan *uniformity* atau pengulangan matematis (*cyclostationary patterns*).

Entropi Shannon $H(X)$ dari deret perubahan arah sudut dihitung per jendela geser (*sliding window*) $N$ sampel:
$$H(X) = -\sum_{i=1}^{k} P(x_i) \log_2 P(x_i)$$

Jika $H(X) < H_{\text{threshold}}$ pada saat terjadi pergerakan intensif, probabilitas input dihasilkan oleh skrip/agen deterministik meningkat secara signifikan.

---

### 6. Production-Ready Code Implementation

Berikut adalah implementasi **Authoritative Movement & Anti-Cheat Pipeline** menggunakan **Go**. Sistem ini menangani otorisasi pergerakan, pemantauan *clock drift*, deteksi *speed hack*, dan mitigasi bot berbasis entropi sudut.

```go
package security

import (
	"errors"
	"math"
	"sync"
	"time"
)

// Vector3 merepresentasikan koordinat 3D spasial dengan presisi float64.
type Vector3 struct {
	X float64 `json:"x"`
	Y float64 `json:"y"`
	Z float64 `json:"z"`
}

// DistanceTo menghitung jarak Euclidean antar dua vektor.
func (v Vector3) DistanceTo(target Vector3) float64 {
	dx := v.X - target.X
	dy := v.Y - target.Y
	dz := v.Z - target.Z
	return math.Sqrt(dx*dx + dy*dy + dz*dz)
}

// Subtraksi vektor: v - o
func (v Vector3) Sub(o Vector3) Vector3 {
	return Vector3{X: v.X - o.X, Y: v.Y - o.Y, Z: v.Z - o.Z}
}

// InputPayload merepresentasikan payload input yang diterima dari game client.
type InputPayload struct {
	Sequence      uint64    `json:"seq"`
	ClientDeltaMs float64   `json:"delta_ms"`
	TargetPos     Vector3   `json:"target_pos"`
	Yaw           float64   `json:"yaw"`
	Pitch         float64   `json:"pitch"`
	ClientSentAt  time.Time `json:"sent_at"`
}

// EntityState merepresentasikan state otoritatif dari suatu entitas di server.
type EntityState struct {
	EntityID        string
	Position        Vector3
	BaseSpeed       float64 // unit per detik
	MaxAcceleration float64 // unit per detik^2
	LastSequence    uint64
	LastValidatedAt time.Time
}

// ValidationResult merepresentasikan status akhir evaluasi keamanan input.
type ValidationResult struct {
	IsAccepted       bool
	CorrectedPos     Vector3
	ViolationsDetected []string
	SuspicionScoreDelta float64
}

// ValidationConfig memuat batasan konfigurasi keamanan runtime.
type ValidationConfig struct {
	MaxTimeDebtMs       float64
	MinShannonEntropy   float64
	EntropyWindowSize   int
	JitterEpsilonMargin float64
}

// AuthoritativeMovementValidator mengelola validasi otoritatif dan anti-cheat.
type AuthoritativeMovementValidator struct {
	mu            sync.RWMutex
	config        ValidationConfig
	entityState   EntityState
	timeBalanceMs float64
	yawHistory    []float64
	suspicionScore float64
}

// NewAuthoritativeMovementValidator menginisialisasi validator untuk satu entitas.
func NewAuthoritativeMovementValidator(initialState EntityState, config ValidationConfig) *AuthoritativeMovementValidator {
	return &AuthoritativeMovementValidator{
		config:        config,
		entityState:   initialState,
		timeBalanceMs: 0.0,
		yawHistory:    make([]float64, 0, config.EntropyWindowSize),
	}
}

// ValidateClientInput adalah fungsi inti yang mengeksekusi pipeline validasi deterministik.
func (v *AuthoritativeMovementValidator) ValidateClientInput(
	input InputPayload,
	serverDeltaMs float64,
	clientRTT time.Duration,
) (ValidationResult, error) {
	v.mu.Lock()
	defer v.mu.Unlock()

	result := ValidationResult{
		IsAccepted:       true,
		CorrectedPos:     v.entityState.Position,
		ViolationsDetected: make([]string, 0),
		SuspicionScoreDelta: 0.0,
	}

	// 1. Validasi Urutan Paket (Anti-Replay / Out-of-Order Mitigations)
	if input.Sequence <= v.entityState.LastSequence {
		result.IsAccepted = false
		result.ViolationsDetected = append(result.ViolationsDetected, "STALE_OR_REPLAYED_SEQUENCE")
		return result, errors.New("input sequence rejected: stale packet")
	}

	// 2. Clock Manipulation / Speed Hack Mitigation (Time Token-Bucket)
	// Server mengalokasikan kredit waktu setara waktu server yang telah berlalu.
	v.timeBalanceMs += serverDeltaMs
	v.timeBalanceMs -= input.ClientDeltaMs

	// Jika saldo waktu klien berada di bawah batas toleransi utang waktu, tolak input.
	if v.timeBalanceMs < -v.config.MaxTimeDebtMs {
		result.IsAccepted = false
		result.ViolationsDetected = append(result.ViolationsDetected, "SPEED_HACK_TIME_ACCELERATION")
		result.SuspicionScoreDelta += 25.0
		// Batasi saldo agar tidak turun tanpa batas akibat serangan terstruktur
		v.timeBalanceMs = -v.config.MaxTimeDebtMs
		return result, nil
	}

	// 3. Validasi Kinematika Pergerakan
	deltaSec := input.ClientDeltaMs / 1000.0
	if deltaSec <= 0.0 {
		result.IsAccepted = false
		result.ViolationsDetected = append(result.ViolationsDetected, "INVALID_DELTA_TIME")
		return result, errors.New("delta time must be positive")
	}

	actualDistance := v.entityState.Position.DistanceTo(input.TargetPos)

	// Hitung jitter allowance dinamis berbasis RTT
	rttMs := float64(clientRTT.Milliseconds())
	jitterAllowance := (rttMs / 1000.0) * v.entityState.BaseSpeed * v.config.JitterEpsilonMargin

	// Max distance = (V * dt) + (0.5 * A * dt^2) + Margin
	maxAllowedDistance := (v.entityState.BaseSpeed * deltaSec) +
		(0.5 * v.entityState.MaxAcceleration * math.Pow(deltaSec, 2)) +
		jitterAllowance

	if actualDistance > maxAllowedDistance {
		result.IsAccepted = false
		result.ViolationsDetected = append(result.ViolationsDetected, "TELEPORT_OR_SPEED_VIOLATION")
		result.SuspicionScoreDelta += 15.0
		// Kirim koreksi berupa posisi terakhir yang sah di server
		result.CorrectedPos = v.entityState.Position
		return result, nil
	}

	// 4. Analisis Perilaku Input dan Entropi (Bot/Aimbot Mitigation)
	v.yawHistory = append(v.yawHistory, input.Yaw)
	if len(v.yawHistory) > v.config.EntropyWindowSize {
		v.yawHistory = v.yawHistory[1:]
	}

	if len(v.yawHistory) == v.config.EntropyWindowSize {
		entropy := v.calculateAngleEntropy(v.yawHistory)
		if entropy < v.config.MinShannonEntropy {
			// Entropi sangat rendah menunjukkan perubahan sudut non-manusia (artifisial sempurna)
			result.ViolationsDetected = append(result.ViolationsDetected, "LOW_ENTROPY_SYNTHETIC_INPUT")
			result.SuspicionScoreDelta += 5.0
		}
	}

	// 5. Commit State jika Lolos Seluruh Validasi
	v.entityState.Position = input.TargetPos
	v.entityState.LastSequence = input.Sequence
	v.entityState.LastValidatedAt = time.Now()
	v.suspicionScore += result.SuspicionScoreDelta

	result.CorrectedPos = v.entityState.Position
	return result, nil
}

// calculateAngleEntropy menghitung Shannon Entropy dari perubahan selisih sudut.
func (v *AuthoritativeMovementValidator) calculateAngleEntropy(angles []float64) float64 {
	if len(angles) < 2 {
		return 1.0
	}

	// Hitung delta sudut absolut
	deltas := make([]float64, len(angles)-1)
	for i := 0; i < len(angles)-1; i++ {
		diff := math.Abs(angles[i+1] - angles[i])
		// Normalisasi diskritisasi sudut ke dalam bucket representatif (presisi 1 derajat)
		deltas[i] = math.Round(diff)
	}

	// Hitung frekuensi kejadian tiap bucket
	frequencies := make(map[float64]float64)
	for _, val := range deltas {
		frequencies[val]++
	}

	// Hitung Shannon Entropy: -sum(p * log2(p))
	var entropy float64
	totalSamples := float64(len(deltas))
	for _, count := range frequencies {
		p := count / totalSamples
		if p > 0 {
			entropy -= p * math.Log2(p)
		}
	}

	return entropy
}

// GetSuspicionScore mengambil total skor kecurigaan entitas.
func (v *AuthoritativeMovementValidator) GetSuspicionScore() float64 {
	v.mu.RLock()
	defer v.mu.RUnlock()
	return v.suspicionScore
}
```

---

### 7. Edge Cases & Failure Modes

| Skenario Kegagalan | Penyebab Akar (*Root Cause*) | Manifestasi Masalah | Mekanisme Pemulihan & Mitigasi |
| :--- | :--- | :--- | :--- |
| **Burst Packet Loss / Lag Spike** | Kemacetan rute jaringan publik UDP; beberapa frame input hilang beruntun kemudian tiba sekaligus. | Klien terlihat melompat secara tiba-tiba (*snapping*); jarak perpindahan total melebihi toleransi per tick. | **Input Consolidation Windowing:** Server mengakumulasikan total $\Delta t$ paket burst tersebut hingga batas aman (maks $250\text{ ms}$), memvalidasi akumulasi perpindahan relatif terhadap total waktu yang tertahan. |
| **Rubberbanding Akibat False Positive** | Margin toleransi jitter ($\epsilon_{\text{jitter}}$) disetel terlalu sempit pada kondisi ping tinggi yang fluktuatif. | Pemain legal ditarik paksa kembali ke posisi lama secara berulang-ulang saat bergerak, memicu frustrasi UX. | **Adaptive Jitter Tolerance:** Tingkatkan toleransi secara dinamis menggunakan nilai Moving Average RTT dan Standard Deviation ($\sigma_{\text{RTT}}$) real-time dari handshake ping. |
| **Server Tick Drop (Server Lag)** | Thread game loop server terblokir oleh I/O atau GC pause sehingga server tick rate jatuh dari 60Hz ke 30Hz. | Saldo *time debt* klien menjadi defisit tidak valid karena `serverDeltaMs` tertunda di loop server. | **Decoupled Monotonic Clock:** Menghitung waktu otorisasi server menggunakan *steady hardware clock* terisolasi, bukan semata-mata mengandalkan estimasi frame loop variabel. |
| **Replay Attacks pada Input** | Adversary menduplikasi paket input valid berulang kali untuk mempercepat laju tembakan atau aksi pergerakan. | Karakter mengeksekusi aksi berulang tanpa memotong saldo *resource* yang sesuai. | **Strict Monotonic Sequence Enforcement:** Menolak tanpa eksekusi semua paket dengan Sequence ID $\le \text{LastSequence}$ dan batalkan koneksi jika menerima urutan mundur secara persisten. |

---

### 8. Trade-offs & Alternatif Solusi

#### Perbandingan Model Otoritas State Game

| Parameter Evaluasi | Client-Authoritative with Server Audit | Fully Authoritative Simulation (Server-Side Physics) | Deterministic Lockstep with Input Broadcast |
| :--- | :--- | :--- | :--- |
| **Resistensi Cheat** | Sangat Rendah; rentan memori hacking & spoofing. | **Maksimal; server memegang absolute state truth.** | Tinggi, namun jika 1 node dimanipulasi memori desync dapat terjadi. |
| **Beban CPU Server** | Sangat Rendah (Server hanya me-relay koordinat). | **Tinggi (Server menghitung fisika, raycast, pathing).** | Sangat Rendah (Server hanya relay array input). |
| **Latensi yang Dirasakan Pemain** | Nir-latensi (*instant feel*). | Membutuhkan *Client-Side Prediction* & *Reconciliation*. | Terikat pada pemain dengan latensi paling buruk (*highest ping node*). |
| **Kebutuhan Bandwidth Jaringan** | Rendah. | Sedang hingga Tinggi (Snapshot replication). | **Sangat Rendah (Hanya input vectors).** |
| **Kesesuaian Genre** | Game kasual single/co-op sederhana. | **FPS Kompetitif, MMO, Action RPG, Battle Royale.** | RTS (StarCraft), Fighting Games (Rollback Netcode/GGPO). |

#### Heuristik Berbasis Aturan vs. Server-Side ML Anomaly Detection
- **Pilihan 1: Deterministic Heuristic Limits (Implementasi di atas)**
  - *Kelebihan:* Eksekusi mikrodetik ($O(1)$), deterministik, tidak ada *cold-start problem*, mudah di-debug secara matematis.
  - *Kekurangan:* Membutuhkan *fine-tuning* parameter secara konstan seiring perubahan meta-game, senjata, atau mekanika gerak.
- **Pilihan 2: Machine Learning Model Ingestion (Inference on Server)**
  - *Kelebihan:* Unggul dalam mendeteksi *stealth/humanized aimbots* dan bot farming berbasis pola kompleks yang lolos aturan kinematika.
  - *Kekurangan:* Latensi inferensi tinggi (tidak dapat dijalankan inline di tick loop 60Hz), konsumsi resource GPU/Tensor core di cluster server, dan risiko *black-box false positives*.

---

### 9. Best Practices & Standard Industri

1. **Strict Input Cleansing:** Anggap seluruh array byte yang diterima dari soket UDP sebagai data yang telah dieksploitasi sampai diverifikasi lolos sanitasi ukuran, batas numerik (*NaN/Inf bounds checking*), dan urutan monotonic.
2. **Lag Compensation Envelope Limit:** Ketika menerapkan rekonsiliasi mundur (*server rollback for hit validation*), jangan pernah mengizinkan klien melakukan *rewind* lebih lama dari batas manusiawi (standar industri: maksimal $200\text{ ms} - 250\text{ ms}$). Pemain dengan latensi di atas itu harus menerima konsekuensi penalti bidikan (*favor the defender*).
3. **Decouple Physics from Frame Rendering:** Pastikan kalkulasi pada klien dan server berjalan pada interval *Fixed Timestep* (misal: tepat 16.666ms per tick) menggunakan integrasi Euler semi-implisit atau Verlet guna mencegah desinkronisasi numerik antar kompilasi platform.
4. **Isolasi Logika Anti-Cheat:** Pisahkan deteksi (*detection/flagging*) dari sanksi langsung (*immediate kick/ban*). Kumpulkan bukti pelanggaran ke dalam skor kecurigaan akumulatif (*Suspicion Score Metric*). Melakukan tendangan (*kick*) instan memberitahu pembuat cheat secara langsung nilai ambang batas toleransi server, memudahkan proses *reverse-engineering* mereka.

---

### 10. Hands-on Lab Exercise

#### Skenario Lab
Anda ditugaskan menguji ketahanan server terhadap dua vektor serangan bot/eksploitasi:
1. **Speed-Hack Attack:** Injeksi paket dengan $\Delta t$ klien yang dipalsukan lebih kecil dari kenyataan untuk melipatgandakan kecepatan gerak.
2. **Deterministic Linear Bot:** Input pergerakan dengan entropi sudut konstan/flat (aiming robotik tanpa getaran manusia).

#### Langkah-Langkah Pengerjaan

##### Langkah 1: Persiapan Environment
Pastikan runtime Go (v1.20+) telah terpasang. Buat berkas direktori pengujian:
```bash
mkdir -p game-security-lab
cd game-security-lab
go mod init game-security-lab
```

##### Langkah 2: Buat Test Harness Implementasi
Simpan kode modul implementasi di Section 6 ke dalam berkas `validator.go`. Kemudian, buat berkas pengujian `validator_test.go` berikut:

```go
package security

import (
	"fmt"
	"math/rand"
	"testing"
	"time"
)

func TestAuthoritativeValidator(t *testing.T) {
	config := ValidationConfig{
		MaxTimeDebtMs:       100.0,
		MinShannonEntropy:   1.5,
		EntropyWindowSize:   10,
		JitterEpsilonMargin: 1.5,
	}

	initialState := EntityState{
		EntityID:        "player_hero_1",
		Position:        Vector3{X: 0, Y: 0, Z: 0},
		BaseSpeed:       10.0, // 10 unit/detik
		MaxAcceleration: 5.0,
		LastSequence:    0,
		LastValidatedAt: time.Now(),
	}

	validator := NewAuthoritativeMovementValidator(initialState, config)
	rtt := 50 * time.Millisecond

	t.Run("Scenario 1: Legitimate Player Movement (Should Pass)", func(t *testing.T) {
		currentPos := Vector3{X: 0, Y: 0, Z: 0}
		for seq := uint64(1); seq <= 10; seq++ {
			// Bergerak lurus sebesar 0.16 unit per 16.6ms frame (Kecepatan ~ 9.6 unit/sec < 10)
			currentPos.X += 0.16
			// Input rotasi manusiawi dengan sedikit variasi acak (noise)
			simulatedHumanYaw := 45.0 + (rand.Float64()*4.0 - 2.0)

			payload := InputPayload{
				Sequence:      seq,
				ClientDeltaMs: 16.6,
				TargetPos:     currentPos,
				Yaw:           simulatedHumanYaw,
				Pitch:         0.0,
				ClientSentAt:  time.Now(),
			}

			result, err := validator.ValidateClientInput(payload, 16.6, rtt)
			if err != nil || !result.IsAccepted {
				t.Fatalf("Legitimate movement rejected at sequence %d: %v", seq, result.ViolationsDetected)
			}
		}
		t.Logf("Scenario 1 Passed: Legitimate movement verified smoothly.")
	})

	t.Run("Scenario 2: Speed-Hack Simulation (Should be Flagged)", func(t *testing.T) {
		// Eksploit: Klien mengirim target perpindahan 50 unit dalam waktu 16.6ms
		maliciousPayload := InputPayload{
			Sequence:      11,
			ClientDeltaMs: 16.6,
			TargetPos:     Vector3{X: 50.0, Y: 0, Z: 0},
			Yaw:           45.0,
			Pitch:         0.0,
			ClientSentAt:  time.Now(),
		}

		result, _ := validator.ValidateClientInput(maliciousPayload, 16.6, rtt)
		if result.IsAccepted {
			t.Errorf("Security Breach: Speed-hack input was accepted!")
		}

		foundKinematicViolation := false
		for _, v := range result.ViolationsDetected {
			if v == "TELEPORT_OR_SPEED_VIOLATION" {
				foundKinematicViolation = true
				break
			}
		}

		if !foundKinematicViolation {
			t.Errorf("Expected TELEPORT_OR_SPEED_VIOLATION, got: %v", result.ViolationsDetected)
		} else {
			t.Logf("Scenario 2 Passed: Speed-hack rejected successfully. Corrected Pos: %+v", result.CorrectedPos)
		}
	})

	t.Run("Scenario 3: Synthetic / Aimbot Low Entropy (Should Increase Suspicion)", func(t *testing.T) {
		initialSuspicion := validator.GetSuspicionScore()
		currentPos := validator.entityState.Position

		// Mensimulasikan bot dengan sudut Yaw identik/flat sempurna (tanpa jitter manusia)
		for seq := uint64(12); seq <= 25; seq++ {
			currentPos.X += 0.05
			flatBotYaw := 90.00000 // Entropi nol

			payload := InputPayload{
				Sequence:      seq,
				ClientDeltaMs: 16.6,
				TargetPos:     currentPos,
				Yaw:           flatBotYaw,
				Pitch:         0.0,
				ClientSentAt:  time.Now(),
			}

			_, _ = validator.ValidateClientInput(payload, 16.6, rtt)
		}

		finalSuspicion := validator.GetSuspicionScore()
		if finalSuspicion <= initialSuspicion {
			t.Errorf("Bot Detection Failed: Suspicion score did not increment for robotic flat input.")
		} else {
			t.Logf("Scenario 3 Passed: Low entropy flagged. Suspicion delta: %.2f", finalSuspicion-initialSuspicion)
		}
	})
}
```

##### Langkah 3: Eksekusi dan Verifikasi
Jalankan pengujian menggunakan flag verbose:
```bash
go test -v ./...
```

##### Hasil yang Diharapkan:
```text
=== RUN   TestAuthoritativeValidator
=== RUN   TestAuthoritativeValidator/Scenario 1:_Legitimate_Player_Movement_(Should_Pass)
    validator_test.go:49: Scenario 1 Passed: Legitimate movement verified smoothly.
=== RUN   TestAuthoritativeValidator/Scenario 2:_Speed-Hack_Simulation_(Should_be_Flagged)
    validator_test.go:76: Scenario 2 Passed: Speed-hack rejected successfully. Corrected Pos: {X:1.6 Y:0 Z:0}
=== RUN   TestAuthoritativeValidator/Scenario 3:_Synthetic_/_Aimbot_Low_Entropy_(Should_Increase_Suspicion)
    validator_test.go:107: Scenario 3 Passed: Low entropy flagged. Suspicion delta: 20.00
--- PASS: TestAuthoritativeValidator (0.00s)
PASS
ok      game-security-lab       0.004s
```