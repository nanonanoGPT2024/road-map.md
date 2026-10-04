# Bab 05: Audio Teknis, Animasi Skeletal, & Spatial Systems
## Module 01: Spatial Perception Systems, Acoustic Propagation, & Skeletal Rigging for Autonomous Agents

---

### 1. Learning Objectives (Spesifik & Terukur)

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
- **Menganalisis dan Memodelkan Perambatan Akustik Spasial**: Mengimplementasikan algoritma *ray-traced acoustic occlusion*, *transmission loss*, dan *diffraction angle calculation* untuk simulasi pendengaran agen otonom (*AI spatial hearing*) dengan latensi kalkulasi di bawah $0.5\text{ ms}$ per evaluasi.
- **Mengintegrasikan Transformasi Kinematika Skeletal (FK/IK)**: Membangun solver *Two-Bone Inverse Kinematics (IK)* dan *Look-At Constraint* berbasis quaternion tanpa artefak *gimbal lock* untuk mengarahkan orientasi visual agen secara adaptif berdasarkan stimulus spasial.
- **Mengembangkan Pipeline Sensorik Spasial Tertutup (*Closed-Loop Sensory-Motor Pipeline*)**: Menghubungkan *stimulus audio* 3D dengan *behavioral state machine* dan *pose generator* berbasis *Root Motion* untuk menghasilkan respon animasi yang deterministik dan realistis terhadap lingkungan fisik.
- **Mengoptimalkan Alokasi Thread & Sinkronisasi Komponen**: Merancang arsitektur decoupled antara subsistem *Physics/Spatial Audio Query* (asinkron) dan *Animation Evaluation* (sinkron pada *main render/game loop*) menggunakan teknik *double-buffering state*.

---

### 2. Concept Overview (Mental Model & Teori Inti)

Di dalam arsitektur game modern berstandar AAA, agen otonom (*Autonomous Agents*) tidak boleh sekadar beroperasi berdasarkan koordinat Cartesian absolut yang dibaca langsung dari memori game (*omniscient AI*). Paradigma *sensory realism* menuntut agen untuk mempersepsikan dunia melalui modalitas sensorik yang terikat pada hukum fisika spasial: **Audio Teknis** (akustik lingkungan) dan mengekspresikan keputusan melalui **Animasi Skeletal** (artikulasi fisik tubuh).

```
   [Lingkungan 3D: Geometri & Rintangan]
                     │
         (Acoustic Raycasting / BVH)
                     ▼
       ┌───────────────────────────┐
       │   Acoustic Propagation    │
       │ (Attenuation, Diffraction)│
       └─────────────┬─────────────┘
                     │ (Perceived Loudness & Angle)
                     ▼
       ┌───────────────────────────┐
       │  AI Perception / Sensory  │
       │   Blackboard Evaluator    │
       └─────────────┬─────────────┘
                     │ (Steering & Focus Target)
                     ▼
       ┌───────────────────────────┐
       │ Skeletal IK & Blend Tree  │
       │  (Head Look-At & Foot IK) │
       └─────────────┬─────────────┘
                     │
                     ▼
   [Pose Buffer Akhir / Rig Deformasi]
```

#### Mental Model: The Listener-Actuator Loop
1. **Acoustic Wavefield Approximation**: Suara dipandang sebagai paket energi (*sound rays*) yang ditembakkan dari emitor ke *listener*. Hambatan geometris menyebabkan atenuasi frekuensi tinggi (*low-pass filtering*) akibat penyerapan material (*transmission loss*) dan pelenturan gelombang di sekitar sudut (*diffraction*). Agen mengekstrak arah datang (*apparent azimuth/elevation*) dan intensitas (*sound pressure level*) untuk menentukan lokasi sumber ancaman atau distraksi.
2. **Skeletal Hierarchy as a Directed Acyclic Graph (DAG)**: Tubuh agen direpresentasikan sebagai hierarki transform ($T = [R|p]$). Setiap sendi (*bone*) mewarisi transformasi lokal dari *parent*-nya:
   $$T_{\text{world}}^{\text{bone}} = T_{\text{world}}^{\text{parent}} \times T_{\text{local}}^{\text{bone}}$$
3. **Procedural Kinematics Injection**: Ketika agen mendeteksi stimulus audio, animasi skeletal tidak langsung memutar klip animasi diskrit (*canned animation*). Sebaliknya, *procedural layer* (Inverse Kinematics) menyuntikkan koreksi transform pada leher, tulang belakang (*spine*), dan ekstremitas bawah (*foot placement*) di atas animasi dasar (*locomotion blend tree*).

---

### 3. Why It Matters (Masalah di Dunia Nyata & Kebutuhan Enterprise)

Pada pengembangan game berskala enterprise (misalnya game aksi taktis atau *survival horror* berbasis stealth):
- **Eradikasi "Wall-Hacking AI"**: Pemain merasa dirugikan jika NPC dapat mendeteksi keberadaan mereka di balik dinding beton padat setebal 1 meter. Menggunakan jarak Euclidean sederhana ($d = \|\vec{x}_{\text{agent}} - \vec{x}_{\text{player}}\|$) merusak suspensi ketidakpercayaan (*immersion breaking*). Pendekatan akustik berbasis raycast/voxel memastikan NPC hanya mendengar suara jika energi suara cukup menembus dinding (*transmission*) atau merambat lewat pintu/celah terbuka (*diffraction*).
- **Koreksi Visual Spasial (Foot-Sliding & Head Alignment)**: Agen yang tidak mengarahkan pandangannya tepat ke sumber suara terlihat kaku dan tidak bernyawa (*uncanny valley*). Lebih buruk lagi, perpindahan navigasi agen di medan miring yang hanya mengandalkan *root motion* tanpa *foot IK* menyebabkan kaki agen melayang (*hovering*) atau menembus tanah (*clipping*).
- **Skalabilitas CPU Core**: Menghitung perambatan audio spasial dan ribuan matriks tulang untuk puluhan NPC secara bersamaan dapat menyebabkan *frame drop* fatal. Integrasi yang efisien menuntut kalkulasi matematis yang *cache-friendly*, vektorisasi (SIMD), dan alokasi memori linear.

---

### 4. Arsitektur & Diagram Komponen

Arsitektur berikut mengisolasi domain kalkulasi komputasional audio, integrasi sensorik AI, dan subsistem deformasi skeletal:

```
+---------------------------------------------------------------------------------------+
|                                    GAME WORLD                                         |
|  +--------------------+                         +----------------------------------+  |
|  | SoundEmitterEntity |                         | Static/Dynamic Collision Meshes  |  |
|  +---------+----------+                         +----------------+-----------------+  |
+------------|-----------------------------------------------------|--------------------+
             |                                                     |
             v                                                     v
+---------------------------------------------------------------------------------------+
|                              SPATIAL ACOUSTIC SUBSYSTEM                               |
|  +---------------------------------------------------------------------------------+  |
|  | AcousticRaytracer: BVH Raycast Traversal                                        |  |
|  | - Line-of-Sight Occlusion Check                                                 |  |
|  | - Material Absorption Calculation (Transmission Loss: dBs)                      |  |
|  | - Edge-Finding Algorithm (Diffraction Paths)                                    |  |
|  +----------------------------------------+----------------------------------------+  |
+-------------------------------------------|-------------------------------------------+
                                            | AuditoryStimulusEvent { Source, Spl, Dir }
                                            v
+---------------------------------------------------------------------------------------+
|                               AUTONOMOUS AGENT AI BRAIN                               |
|  +---------------------------------------------------------------------------------+  |
|  | Perception Module -> Stimulus Memory Pool -> Action Planner (Behavior Tree/GOAP)|  |
|  | Outputs:                                                                        |  |
|  | - Movement Velocity & Trajectory                                                |  |
|  | - FocusTargetPosition (World Space)                                             |  |
|  +----------------------------------------+----------------------------------------+  |
+-------------------------------------------|-------------------------------------------+
                                            | Desired States: Motion Vector & Focus Target
                                            v
+---------------------------------------------------------------------------------------+
|                               SKELETAL ANIMATION PIPELINE                             |
|  +---------------------------------------------------------------------------------+  |
|  | BlendTree Evaluator: Locomotion Base (Forward, Strafe, Idle Poses)               |  |
|  +----------------------------------------+----------------------------------------+  |
|                                           | Local Pose
|                                           v
|  +---------------------------------------------------------------------------------+  |
|  | Inverse Kinematics Layer:                                                       |  |
|  | - Look-At Solver (Quaternion Constrained Damped Tracking -> Head/Spine)         |  |
|  | - Two-Bone IK Solver (Terrain Adaptation -> Pelvis, Knees, Feet)                |  |
|  +----------------------------------------+----------------------------------------+  |
|                                           | Global Pose Matrices
|                                           v
|  +---------------------------------------------------------------------------------+  |
|  | Final Skinning Palette Buffer -> Render Hardware (GPU Vertex Shader)            |  |
+---------------------------------------------------------------------------------------+
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### 5.1 Fisika Propagasi Akustik Spasial
Intensitas suara yang diterima oleh agen dinyatakan oleh model atenuasi logaritmik:
$$SPL_{\text{received}} = SPL_{\text{source}} - 20 \log_{10}\left(\frac{d}{d_0}\right) - \sum_{i} TL_i - \alpha_{\text{diff}}$$

Dimana:
- $SPL_{\text{source}}$: *Sound Pressure Level* referensi pada jarak $d_0$ (dB).
- $20 \log_{10}(d / d_0)$: *Geometric spreading attenuation* (hukum kuadrat terbalik).
- $TL_i$: *Transmission Loss* (dB) dari material rintangan ke-$i$ yang dipotong oleh *ray* transmisi:
  $$TL_i = 10 \log_{10}\left(\frac{1}{1 - \alpha_i}\right)$$
  dengan $\alpha_i$ sebagai koefisien absorpsi material.
- $\alpha_{\text{diff}}$: Kerugian akibat difraksi sudut gelombang di sekitar sudut (*corner diffraction*). Difraksi diestimasi menggunakan formulasi variasi sudut belok $\theta$:
  $$\alpha_{\text{diff}} = 10 \log_{10}(3 + 20 \cdot N_f)$$
  di mana $N_f$ adalah *Fresnel Number*, $N_f = \frac{2}{\lambda} (d_1 + d_2 - d_{\text{direct}})$.

#### 5.2 Kinematika Skeletal: Look-At & Two-Bone IK
##### Look-At Damped Quaternion Solver
Untuk mengarahkan kepala agen ke target suara $\vec{P}_{\text{target}}$ dari posisi sendi kepala $\vec{P}_{\text{head}}$:
1. Dapatkan vektor arah saat ini $\vec{v}_{\text{current}} = R_{\text{head}} \cdot \vec{f}_{\text{bone}}$ (di mana $\vec{f}_{\text{bone}}$ adalah *forward vector default* sendi, biasanya $(0, 0, 1)$).
2. Dapatkan vektor arah target:
   $$\vec{v}_{\text{target}} = \frac{\vec{P}_{\text{target}} - \vec{P}_{\text{head}}}{\|\vec{P}_{\text{target}} - \vec{P}_{\text{head}}\|}$$
3. Hitung sumbu rotasi $\vec{a} = \vec{v}_{\text{current}} \times \vec{v}_{\text{target}}$ dan sudut $\phi = \arccos(\vec{v}_{\text{current}} \cdot \vec{v}_{\text{target}})$.
4. Batasi $\phi$ dengan batas anatomis kranial $[\phi_{\min}, \phi_{\max}]$ (misal: rotasi leher maksimal $\pm 75^\circ$).
5. Hitung kuaternion rotasi koreksi $\Delta q = \text{AngleAxis}(\phi_{\text{clamped}}, \vec{a})$, lalu haluskan pergerakan menggunakan *Spherical Linear Interpolation* (SLERP) untuk menghindari snapping:
   $$q_{\text{final}} = \text{SLERP}(R_{\text{head}}, \Delta q \times R_{\text{head}}, \Delta t \cdot \omega)$$

##### Two-Bone Analytical IK (Algoritma Trigonometrik Kosinus)
Digunakan untuk menempatkan kaki agen pada kontur medan tanah. Diberikan posisi pangkal paha/sendi panggul ($A$), target telapak kaki ($T$), panjang paha ($L_1$), dan panjang betis ($L_2$):
1. Jarak ke target: $D = \|\vec{T} - \vec{A}\|$.
2. Batasi jangkauan: $D = \min(D, (L_1 + L_2) \cdot 0.9999)$.
3. Berdasarkan hukum kosinus:
   $$\cos(\beta) = \frac{L_1^2 + L_2^2 - D^2}{2 L_1 L_2}$$
   $$\beta = \arccos(\cos(\beta)) \quad \text{(Sudut rotasi internal lutut)}$$
4. Sudut elevasi paha terhadap garis lurus target:
   $$\cos(\alpha) = \frac{L_1^2 + D^2 - L_2^2}{2 L_1 D}$$
   $$\alpha = \arccos(\cos(\alpha))$$
5. Matriks orientasi dievaluasi ulang dengan memperhitungkan *pole vector* (vektor preferensi lutut menekuk ke depan).

---

### 6. Production-Ready Code Implementation

Berikut adalah implementasi referensi berstandar produksi dalam Python (dengan static typing dan pustaka `numpy`) yang merepresentasikan subsistem:
1. Pemroses perambatan akustik berbasis raycast linier.
2. Solver Two-Bone IK analitis.
3. Kontroler Integrasi Agen yang menghubungkan stimulus audio ke respons skeletal visual.

```python
"""
Spatio-Acoustic Skeletal Perception Module
Author: Principal Systems Architect
Standard: GEMINI High-Performance Game Runtime Standard
"""

from __future__ import annotations
import math
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
import numpy as np
from numpy.typing import NDArray

# ==============================================================================
# 1. CORE TYPES & MATH PRIMITIVES
# ==============================================================================

Vector3 = NDArray[np.float64]

def normalize(v: Vector3) -> Vector3:
    norm = np.linalg.norm(v)
    if norm < 1e-9:
        return np.array([0.0, 0.0, 0.0], dtype=np.float64)
    return v / norm

@dataclass(frozen=True)
class Ray:
    origin: Vector3
    direction: Vector3  # Must be normalized

@dataclass
class RaycastHit:
    hit: bool
    point: Vector3 = field(default_factory=lambda: np.zeros(3, dtype=np.float64))
    normal: Vector3 = field(default_factory=lambda: np.array([0.0, 1.0, 0.0], dtype=np.float64))
    material_transmission_loss: float = 0.0  # In decibels (dB)

@dataclass
class SoundEvent:
    source_position: Vector3
    initial_spl_db: float  # Sound Pressure Level at 1 meter
    frequency_hz: float

@dataclass
class PerceivedSoundStimulus:
    apparent_direction: Vector3
    perceived_spl_db: float
    occluded: bool

# ==============================================================================
# 2. ACOUSTIC PROPAGATION SUBSYSTEM
# ==============================================================================

class AcousticEnvironment:
    """Simulates physical obstructions and acoustic medium traits."""
    
    def __init__(self) -> None:
        # Represents planar static geometry in the environment
        # Tuple: (Plane Point, Plane Normal, Material Transmission Loss dB, Half-Extent Bound)
        self.barriers: List[Tuple[Vector3, Vector3, float, float]] = []

    def add_barrier(self, center: Vector3, normal: Vector3, transmission_loss_db: float, size: float) -> None:
        self.barriers.append((center, normalize(normal), transmission_loss_db, size))

    def cast_ray(self, ray: Ray, max_distance: float) -> Optional[RaycastHit]:
        """Simple ray-plane segment intersection test."""
        closest_hit: Optional[RaycastHit] = None
        min_dist = max_distance

        for center, normal, tl_db, size in self.barriers:
            denom = np.dot(normal, ray.direction)
            if abs(denom) > 1e-6:
                diff = center - ray.origin
                t = np.dot(diff, normal) / denom
                if 0.0 < t < min_dist:
                    intersection = ray.origin + t * ray.direction
                    # Check boundary box
                    in_bound = np.all(np.abs(intersection - center) <= size)
                    if in_bound:
                        min_dist = t
                        closest_hit = RaycastHit(
                            hit=True,
                            point=intersection,
                            normal=normal,
                            material_transmission_loss=tl_db
                        )
        return closest_hit

class SpatialAcousticEngine:
    """Evaluates sound propagation including geometric decay, absorption, and transmission."""
    
    AIR_ATTENUATION_COEFF: float = 0.005  # dB per meter in standard humidity

    def __init__(self, env: AcousticEnvironment) -> None:
        self.env = env

    def evaluate_propagation(self, sound: SoundEvent, listener_position: Vector3) -> PerceivedSoundStimulus:
        delta = sound.source_position - listener_position
        distance = np.linalg.norm(delta)

        if distance < 1e-6:
            return PerceivedSoundStimulus(
                apparent_direction=np.array([0.0, 0.0, 1.0]),
                perceived_spl_db=sound.initial_spl_db,
                occluded=False
            )

        direction = delta / distance
        
        # 1. Geometric Spreading Loss (Inverse Square Law)
        geometric_loss = 20.0 * math.log10(max(distance, 1.0))
        
        # 2. Atmospheric Absorption
        air_loss = self.AIR_ATTENUATION_COEFF * distance
        
        # 3. Obstacle Transmission Loss
        transmission_loss = 0.0
        occluded = False
        ray = Ray(origin=listener_position, direction=direction)
        hit = self.env.cast_ray(ray, distance)
        
        if hit and hit.hit:
            occluded = True
            transmission_loss += hit.material_transmission_loss

        # Calculate final received decibels
        received_spl = sound.initial_spl_db - geometric_loss - air_loss - transmission_loss
        received_spl = max(0.0, received_spl)  # Clamp to absolute silence threshold

        return PerceivedSoundStimulus(
            apparent_direction=direction,
            perceived_spl_db=received_spl,
            occluded=occluded
        )

# ==============================================================================
# 3. PROCEDURAL SKELETAL RIGGING & KINEMATICS (IK)
# ==============================================================================

class TwoBoneIKSolver:
    """
    Analytical Two-Bone Inverse Kinematics solver.
    Computes exact joint positions for two limbs (e.g., Hip -> Knee -> Foot).
    """

    @staticmethod
    def solve(
        root_pos: Vector3,
        target_pos: Vector3,
        pole_vector: Vector3,
        length_1: float,
        length_2: float
    ) -> Tuple[Vector3, Vector3, Vector3]:
        """
        Returns:
            Tuple[Joint1 (Root), Joint2 (Knee/Elbow), Joint3 (Effector/Foot)]
        """
        line = target_pos - root_pos
        dist = np.linalg.norm(line)

        # Clamping distance to valid kinematic range
        max_reach = (length_1 + length_2) * 0.9999
        min_reach = abs(length_1 - length_2) * 1.0001
        clamped_dist = np.clip(dist, min_reach, max_reach)

        dir_line = line / dist if dist > 1e-9 else np.array([0.0, -1.0, 0.0])
        
        # Law of Cosines for Joint 2 Angle
        cos_knee = (length_1**2 + length_2**2 - clamped_dist**2) / (2.0 * length_1 * length_2)
        cos_knee = np.clip(cos_knee, -1.0, 1.0)
        
        # Law of Cosines for Joint 1 Elevation
        cos_root = (length_1**2 + clamped_dist**2 - length_2**2) / (2.0 * length_1 * clamped_dist)
        cos_root = np.clip(cos_root, -1.0, 1.0)
        angle_root = math.acos(cos_root)

        # Determine reference bend plane using pole vector
        pole_dir = pole_vector - root_pos
        normal = np.cross(dir_line, pole_dir)
        if np.linalg.norm(normal) < 1e-6:
            # Fallback normal if vectors are parallel
            normal = np.array([0.0, 0.0, 1.0])
        else:
            normal = normalize(normal)

        bend_dir = normalize(np.cross(normal, dir_line))

        # Joint 2 (Midpoint / Knee) calculation
        mid_pos = (
            root_pos 
            + (dir_line * math.cos(angle_root) * length_1) 
            + (bend_dir * math.sin(angle_root) * length_1)
        )
        
        # Effector snapped to constrained target
        effector_pos = root_pos + dir_line * clamped_dist

        return root_pos, mid_pos, effector_pos

class LookAtConstraint:
    """Spherical dampening solver for orientation-based bone tracking (Head/Spine)."""
    
    def __init__(self, max_angular_velocity_rad_s: float = math.radians(180.0)):
        self.max_angular_velocity = max_angular_velocity_rad_s
        self.current_forward = np.array([0.0, 0.0, 1.0], dtype=np.float64)

    def update(self, current_head_pos: Vector3, target_focus: Vector3, delta_time: float) -> Vector3:
        target_dir = target_focus - current_head_pos
        norm = np.linalg.norm(target_dir)
        if norm < 1e-6:
            return self.current_forward

        desired_forward = target_dir / norm
        
        # Calculate angle difference
        dot_val = np.clip(np.dot(self.current_forward, desired_forward), -1.0, 1.0)
        angle = math.acos(dot_val)

        if angle < 1e-5:
            self.current_forward = desired_forward
            return self.current_forward

        # Slerp-like vector step
        max_step = self.max_angular_velocity * delta_time
        alpha = min(1.0, max_step / angle)
        
        # Intermediate spherical step
        step_dir = (1.0 - alpha) * self.current_forward + alpha * desired_forward
        self.current_forward = normalize(step_dir)
        return self.current_forward

# ==============================================================================
# 4. AUTONOMOUS AGENT CONTROLLER (INTEGRATION ROOT)
# ==============================================================================

class AutonomousSkeletalAgent:
    """Autonomous agent encapsulating spatial acoustics, perception, and skeletal updates."""
    
    AUDITORY_THRESHOLD_DB: float = 25.0  # Decibel limit below which sound is unheard

    def __init__(self, agent_id: str, world_position: Vector3) -> None:
        self.agent_id = agent_id
        self.position = np.array(world_position, dtype=np.float64)
        self.head_local_offset = np.array([0.0, 1.75, 0.0], dtype=np.float64)
        
        # Skeletal subsystems
        self.look_at_rig = LookAtConstraint()
        self.two_bone_ik = TwoBoneIKSolver()
        
        # Rig Configuration (Meters)
        self.thigh_length = 0.5
        self.calf_length = 0.5
        self.hip_left_offset = np.array([-0.2, 0.9, 0.0], dtype=np.float64)
        
        # Perception State
        self.current_look_target: Vector3 = self.get_head_position() + np.array([0.0, 0.0, 5.0])

    def get_head_position(self) -> Vector3:
        return self.position + self.head_local_offset

    def process_acoustic_stimulus(self, stimulus: PerceivedSoundStimulus, sound_world_origin: Vector3) -> None:
        """AI decision branch responding to sound perception."""
        if stimulus.perceived_spl_db >= self.AUDITORY_THRESHOLD_DB:
            # Shift gaze/head towards the perceived apparent direction
            # If occluded, awareness decreases but target is still locked
            self.current_look_target = sound_world_origin

    def tick(self, delta_time: float, ground_elevation: float) -> Tuple[Vector3, Tuple[Vector3, Vector3, Vector3]]:
        """
        Executes frame update:
        1. Animates Head Look-At vector
        2. Adjusts Leg Kinematics to dynamic ground height
        """
        head_pos = self.get_head_position()
        
        # Update Head Rig
        updated_facing = self.look_at_rig.update(head_pos, self.current_look_target, delta_time)
        
        # Update Left Leg Rig (Two-Bone IK) for ground conformity
        left_hip_pos = self.position + self.hip_left_offset
        left_foot_target = np.array([left_hip_pos[0], ground_elevation, left_hip_pos[2]], dtype=np.float64)
        pole_vector = left_hip_pos + np.array([0.0, 0.0, 1.0])  # Knee bends forward
        
        hip, knee, foot = self.two_bone_ik.solve(
            root_pos=left_hip_pos,
            target_pos=left_foot_target,
            pole_vector=pole_vector,
            length_1=self.thigh_length,
            length_2=self.calf_length
        )
        
        return updated_facing, (hip, knee, foot)

# ==============================================================================
# 5. EXECUTION & VALIDATION RUNNER
# ==============================================================================

if __name__ == "__main__":
    # Setup Virtual World
    env = AcousticEnvironment()
    # Add a concrete wall: Center=(0, 1.5, 5), Normal Facing (0, 0, -1), TL=35dB, Half-Size=5m
    env.add_barrier(
        center=np.array([0.0, 1.5, 5.0]), 
        normal=np.array([0.0, 0.0, -1.0]), 
        transmission_loss_db=35.0, 
        size=5.0
    )
    
    acoustic_engine = SpatialAcousticEngine(env)
    
    # Initialize Agent at (0, 0, 0)
    agent = AutonomousSkeletalAgent("Agent_Spectre", np.array([0.0, 0.0, 0.0]))
    
    # Generate Distant Gunfire Sound Event behind the wall: (0, 1.5, 10.0), 90 dB SPL
    gunfire = SoundEvent(
        source_position=np.array([0.0, 1.5, 10.0]),
        initial_spl_db=90.0,
        frequency_hz=1000.0
    )
    
    # Step 1: Acoustic Propagation pass
    stimulus = acoustic_engine.evaluate_propagation(gunfire, agent.get_head_position())
    print(f"[Acoustics Engine] Received SPL: {stimulus.perceived_spl_db:.2f} dB (Occluded: {stimulus.occluded})")
    
    # Step 2: Feed auditory perception to agent
    agent.process_acoustic_stimulus(stimulus, gunfire.source_position)
    
    # Step 3: Run Simulation Frame
    delta_time = 0.016  # ~60 FPS
    ground_height = -0.15  # Uneven terrain drop
    
    head_facing, (hip, knee, foot) = agent.tick(delta_time, ground_height)
    
    print(f"[Agent Animation] New Facing Forward: {np.round(head_facing, 3)}")
    print(f"[Agent Skeletal IK] Hip: {np.round(hip, 3)} -> Knee: {np.round(knee, 3)} -> Foot: {np.round(foot, 3)}")
```

---

### 7. Edge Cases & Failure Modes

1. **Acoustic Ray-Leakage (*Thin Geometry Glitch*)**:
   - *Problem*: Geometri dinding tipis atau *double-sided plane* dengan batas titik presisi floating-point yang tidak rapat menyebabkan raycast meleset, membuat agen mendengar suara tanpa atenuasi transmisi (*sound pop*).
   - *Mitigation*: Gunakan *fat-ray sweeping* (sphere-casting atau capsule-casting) alih-alih raycast linier tanpa dimensi, atau gunakan representasi *voxelized acoustic volume* untuk memeriksa status keterhubungan ruang.
2. **Kinematic Singularity (*Two-Bone Knee Lockup*)**:
   - *Problem*: Jika jarak antara panggul dan target kaki sama persis dengan $L_1 + L_2$, determinan matriks rotasi mendekati singularitas, memicu getaran keras (*jittering/snapping*) saat agen bergerak mendekati atau menjauhi jangkauan maksimum.
   - *Mitigation*: Selalu jepit panjang target maksimum pada $99.99\%$ dari panjang total tulang ($D_{\max} = (L_1 + L_2) \cdot 0.9999$) dan gunakan kurva pemulus sigmoid (*soft-clamping*) saat mendekati batas maksimal.
3. **Gimbal Lock & Target Flipping pada Look-At**:
   - *Problem*: Jika sumber suara berada persis di atas kepala agen atau vertikal tegak lurus terhadap sumbu leher, operasi *cross product* $\vec{v}_{\text{current}} \times \vec{v}_{\text{target}}$ menghasilkan vektor nol, menghasilkan nilai $\text{NaN}$ pada rotasi.
   - *Mitigation*: Lakukan pengecekan magnitudo cross-product ($\|\vec{a}\| < \epsilon$). Jika terdeteksi degenerate case, lakukan interpolasi rotasi paksa menggunakan sumbu yaw bawaan transform lokal agen.

---

### 8. Trade-offs & Alternatif Solusi

| Parameter / Arsitektur | Real-Time Ray-Traced Acoustics | Precomputed Acoustic Wavefields (PRT) |
| :--- | :--- | :--- |
| **Kebutuhan Memori** | Sangat Rendah ($\mathcal{O}(1)$ runtime overhead). | Tinggi ($\mathcal{O}(N^3)$ voxel memory probes). |
| **Beban CPU** | Tinggi saat scene memiliki geometri poligon padat. | Sangat Rendah (hanya interpolasi probe). |
| **Dukungan Dynamic Destruction** | Alami (raycast langsung berinteraksi dengan BVH dinamis). | Sangat Buruk (membutuhkan re-baking lokal yang mahal). |

| Metode Rigging/IK | Two-Bone Analytical IK | FABRIK / CCD Iterative IK |
| :--- | :--- | :--- |
| **Biaya Komputasi** | Deterministik, instan ($<1 \mu\text{s}$ per anggota badan). | Berfluktuasi tergantung jumlah iterasi ($5-15\times$ lebih mahal). |
| **Fleksibilitas Rantai Tulang** | Terbatas ketat pada rantai 2-tulang (Paha/Betis). | Skalabel untuk tentakel, ekor, atau tulang belakang multi-tulang. |
| **Stabilitas Kinematik** | 100% stabil, tidak berisiko terjebak pada *local minima*. | Rentan terhadap osilasi pose jika konvergensi iterasi tidak tercapai. |

---

### 9. Best Practices & Standard Industri

- **Decoupled Update Frequency**: Jalankan *Spatial Acoustic Raytracing* pada *Fixed Tick* berfrekuensi rendah (misal: 10 Hz atau 20 Hz) menggunakan thread pekerja latar belakang (*Worker Thread Pool*). Simpan stimulus dalam *Perception Buffer*. Sebaliknya, evaluasi *Skeletal Pose & IK* pada frekuensi *Render Frame Rate* penuh (60–120 Hz) dengan interpolasi pose halus.
- **Bone Transform Alignment Convention**: Pertahankan konvensi ortonormal seragam di seluruh engine. Jangan campur aduk model transform Left-Handed vs Right-Handed secara implisit. Simpan semua transform sendi internal dalam representasi *Dual Quaternions* atau *Unit Quaternion + Translation Vector* untuk mencegah degradasi skala matriks secara bertahap (*matrix shear*).
- **SIMD Layout untuk Evaluasi Pose**: Dalam implementasi engine C++/Rust komersial, susun *Pose Palette* dalam struktur data SoA (*Structure of Arrays*): alokasikan seluruh quaternion $(x, y, z, w)$ dalam satu array contiguous berurutan 16-byte aligned untuk memproses perbanyakan transformasi hierarkis menggunakan instruksi AVX2/NEON.

---

### 10. Hands-on Lab Exercise: Reactive Hearing & Procedural Kinematics

#### Skenario Lab
Anda ditugaskan membangun prototipe sistem pendengaran taktis dan visualisasi artikulasi tubuh untuk NPC penjaga:
1. Agen harus berada di posisi $(0, 0, 0)$.
2. Sebuah proyektil meledak secara dinamis di balik rintangan pada koordinat $(4, 0, 4)$.
3. Tembok pemisah berada di antara agen dan ledakan dengan *Transmission Loss* sebesar $20\text{ dB}$.
4. Terapkan solver yang menghitung tingkat keterdengaran ledakan, dan jika tingkat SPL $> 30\text{ dB}$, gerakkan leher agen secara prosedural menghadap ke lokasi tersebut, sementara posisi lutut kanan dan kiri beradaptasi terhadap permukaan miring lereng sebesar $+0.2\text{ meter}$.

#### Langkah Pengerjaan
1. Instansiasi `AcousticEnvironment` dan definisikan dinding penghalang vertikal dengan konfigurasi yang tepat di antara posisi agen dan emitor.
2. Buat objek `SoundEvent` dengan nilai $SPL = 85\text{ dB}$ pada koordinat ledakan.
3. Jalankan pipeline `evaluate_propagation` untuk memverifikasi apakah proyektil terdengar melampaui batas *auditory threshold*.
4. Lakukan looping evaluasi runtime selama 60 frame (1 detik simulasi) untuk mengamati bagaimana `LookAtConstraint` menginterpolasi arah hadap kepala agen tanpa jittering.
5. Panggil `TwoBoneIKSolver` untuk kaki kanan dan kiri dengan target ketinggian tanah $+0.2\text{ meter}$ untuk memvalidasi posisi tekukan sendi lutut.

#### Kriteria Keberhasilan Verifikasi
- Nilai akhir apparent look vector agen memiliki selisih sudut $< 1^\circ$ dari normalized vector ledakan setelah 60 tick iterasi.
- Panjang segmen paha (`hip` ke `knee`) dan betis (`knee` ke `foot`) pasca-IK tetap konsisten matematis sebesar $0.5\text{ meter} \pm 0.0001\text{ meter}$ (tidak ada deformasi skala tulang).
- Sistem mencatat status *occluded* secara akurat tanpa memicu diskontinuitas nilai transform.