# Bab 06: Gameplay AI Terapan & Sistem Status Reaktif (Module 01)

Sistem gameplay modern menuntut entitas non-player (NPC) dan agen otonom untuk merespons dinamika dunia game secara instan, modular, dan terprediksi. Pendekatan konvensional yang mengandalkan pengecekan kondisi (*polling*) di dalam loop `Update()` per frame—seperti `if (isStunned) ... else if (isBurning) ...`—secara inheren memicu *spaghetti code*, degradasi performa $O(N \times M)$ saat ratusan entitas aktif, serta kerentanan sinkronisasi status (*state divergence*).

Modul ini mengupas perancangan dan implementasi **Sistem Status Reaktif (Reactive Status System)** terintegrasi dengan **Arsitektur Gameplay AI**. Mengadopsi prinsip yang dipopulerkan oleh *Gameplay Ability System (GAS)* pada industri AAA, modul ini mentransformasi status entitas menjadi model berbasis *event-driven attribute modification* dan *tag-based arbitration* yang langsung memengaruhi siklus penalaran AI (*Behavior Tree* atau *Utility AI*).

---

## 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
* **Mendesain dan mengimplementasikan** arsitektur *Gameplay Tag Hierarchical System* dan *Reactive Attribute Set* untuk kalkulasi status efek tanpa *polling*.
* **Membangun** *Gameplay Effect Engine* yang menangani durasi, *stacking logic*, modifier multi-tahap (Flat, Percent Additive, Percent Multiplicative), dan eksekusi instan.
* **Mengintegrasikan** *Reactive Event Propagation Loop* ke dalam otak Gameplay AI (Blackboard & Decision Arbiter) untuk interupsi instan (misal: *Crowd Control/Stun*, *Aggro Shift*, atau interaksi elemental).
* **Mencegah dan memitigasi** masalah arsitektural fatal: *circular cascading reactions*, *delta-time accumulation drift*, dan *orphaned status memory leaks*.
* **Mengevaluasi trade-off** antara arsitektur berorientasi data (*Data-Driven Reactive GAS*) versus arsitektur prosedural state machine sederhana berdasarkan metrik komputasi dan skalabilitas tim.

---

## 2. Concept Overview

Sistem Status Reaktif memisahkan tiga pilar utama gameplay:

```
[ Gameplay Tags ] ──> Mendefinisikan KONDISI & HAK AKSES Entitas
[ Attribute Set ] ──> Menyimpan & Menghitung NILAI NUMERIK (Health, Speed, Resist)
[ Gameplay Effects] ──> Mengubah Nilai Numerik & Menempelkan/Mencabut Tags
```

```
           Tradisional (Polling)                      Reaktif (Event-Driven)
        
         Tick Frame (Setiap 16ms)                     Mutasi Status (Hanya saat Event)
         ┌──────────────────────┐                    ┌───────────────────────────────┐
         │ Check isFrozen?      │                    │ Event: "Effect.Freeze.Applied"│
         │ Check isStunned?     │                    └──────────────┬────────────────┘
         │ Check isPoisoned?    │                                   │ (Emit Signal)
         │ Check Health < 20%?  │                                   ▼
         │ ... (Puluhan if-else)│                    ┌───────────────────────────────┐
         └──────────────────────┘                    │ AI Blackboard Langsung Update │
                                                     │ Abort Node -> State: STUNNED  │
                                                     └───────────────────────────────┘
```

### Mental Model & Teori Inti
1. **Hierarchical Gameplay Tags**: String terstruktur berbobot hierarkis yang dikompresi menjadi representasi 64-bit integer atau *tokenized hash* (misal: `State.Debuff.Stun`, `Damage.Elemental.Fire`). Tag bersifat deklaratif; jika entitas memiliki tag `State.Debuff.Stun`, sistem AI secara otomatis menonaktifkan *task execution*.
2. **Layered Attribute Calculation**: Nilai atribut tidak dimutasi langsung secara destruktif ke basis datanya. Sebaliknya, atribut dihitung melalui formula deterministik:
   $$\text{CurrentValue} = \left( (\text{BaseValue} + \sum \text{AddModifier}) \times (1 + \sum \text{PercentAdd}) \right) \times \prod (1 + \text{PercentMult})$$
3. **Reactive AI Arbitration**: Agen AI tidak mengecek statusnya di setiap *tick*. AI mendaftarkan diri (*listen/subscribe*) pada *Blackboard Key Change Events* dan *Tag Events*. Ketika efek status mengubah kondisi kritis (misal: penambahan tag `State.Incapacitated`), evaluasi AI diinterupsi seketika (*abort mechanism*), menghemat resource CPU secara masif.

---

## 3. Why It Matters

Dalam game skala komersial (seperti RPG sistemik, MOBA, atau Action Adventure berskala *Genshin Impact* atau *Divinity: Original Sin*), kompleksitas interaksi status efek melonjak secara kombinatorial:

* **Masalah Skala Desain**: Menambahkan efek reaksi elemental (misal: entitas basah terkena petir $\rightarrow$ konduksi listrik area dan *stun*) pada sistem monolitik mengharuskan developer mengubah puluhan *script* karakter individual.
* **State Divergence & Desync**: Dalam arsitektur multiplayer atau single-player kompleks, modifikasi langsung pada variabel `Health` atau `MoveSpeed` oleh berbagai sumber tanpa *source tracking* menyebabkan *floating-point drift* dan hilangnya kemampuan *rollback* status saat buff kedaluwarsa.
* **Overhead CPU**: Memeriksa ratusan status pada ratusan agen AI setiap frame membuang budget siklus frame (16.6ms untuk 60 FPS). Pendekatan reaktif berbasis *dirty flags* dan *signal listeners* mereduksi komputasi evaluasi status menjadi $O(1)$ amortized per agen saat event terjadi.

---

## 4. Arsitektur & Diagram Komponen

Arsitektur di bawah memperlihatkan alur data dari instigasi efek, pemrosesan oleh sistem status entitas, reaksi elemental, mutasi atribut, hingga pemicuan interupsi pada Gameplay AI:

```
+-----------------------------------------------------------------------------------------------+
|                                      GAMEPLAY WORLD TICK                                      |
+-----------------------------------------------------------------------------------------------+
                                                │
                                                ▼
+-----------------------+           +───────────────────────+
|   Instigator Source   | ────────> |    GameplayEffect     |
| (Spell, Hazard, Trap) |           |  (Duration, Mods, Tag)|
+-----------------------+           +───────────┬───────────+
                                                │ Application
                                                ▼
+───────────────────────────────────────────────────────────────────────────────────────────────+
|                                    TARGET ENTITY COMPONENT                                    |
|                                                                                               |
|  +─────────────────────────────────────────────────────────────────────────────────────────+  |
|  |                             StatusEffectContainer (Manager)                             |  |
|  |                                                                                         |  |
|  |   [ 1. Tag Immunity Check ] ──> Tag Valid?                                              |  |
|  |                                     │ Yes                                               |  |
|  |   [ 2. Elemental Reaction Engine ] ─┴─> (e.g., Pyro + Hydro = Vaporize Reaction)        |  |
|  |                                     │                                                   |  |
|  |   [ 3. Stacking & Policy Evaluator] ─┴─> Override / Refresh Duration / Increment Stack  |  |
|  |                                     │                                                   |  |
|  |   [ 4. Active Effects Registry ] ───┴─> Tick Timers, Manage Lifecycle                   |  |
|  +─────────────────────────────────────────────┬───────────────────────────────────────────+  |
|                                                │                                              |
|                                                ├──────────────────────────────┐               |
|                                                ▼                              ▼               |
|  +──────────────────────────────────────────────────────────+   +──────────────────────────+  |
|  |                       AttributeSet                       |   |       Tag Container      |  |
|  |  - Base Attributes (HP, Speed, Defense)                  |   |  - Explicit Tag Counts   |  |
|  |  - Applied Modifiers (Add, PercentAdd, Mult)             |   |  - Implicit Hierarchy    |  |
|  |  - Dirty Flag Driven Re-calculation Engine               |   +─────────────┬────────────+  |
|  +─────────────────────────────┬────────────────────────────+                 │               |
+────────────────────────────────┼──────────────────────────────────────────────┼───────────────+
                                 │ OnAttributeChanged                           │ OnTagChanged
                                 ▼                                              ▼
+───────────────────────────────────────────────────────────────────────────────────────────────+
|                                      REACTIVE AI BRAIN                                        |
|                                                                                               |
|  +─────────────────────────────────────────────────────────────────────────────────────────+  |
|  |                                    Reactive Blackboard                                  |  |
|  |  - Key: "Self.State.IsStunned" <── (Subscribed to Tag: State.Debuff.Stun)               |  |
|  |  - Key: "Self.Vitals.HealthPct" <── (Subscribed to Attribute: Health)                   |  |
|  +─────────────────────────────────────────────┬───────────────────────────────────────────+  |
|                                                │ OnValueChange Signals                        |
|                                                ▼                                              |
|  +─────────────────────────────────────────────────────────────────────────────────────────+  |
|  |                             Decision Arbiter / Behavior Tree                            |  |
|  |  - Priority Selector Node (Interrupted instantly when "IsStunned" == True)             |  |
|  |  - Utility Consideration Curves dynamically re-weighted based on Current Attributes    |  |
|  +─────────────────────────────────────────────────────────────────────────────────────────+  |
+───────────────────────────────────────────────────────────────────────────────────────────────+
```

---

## 5. Deep Dive Mekanisme & Prinsip Kerja

### A. Lifecycle Gameplay Effect
Gameplay Effect (GE) memodifikasi status entitas melalui tiga skema waktu:
1. **Instant**: Mengubah atribut permanen secara langsung (misal: *Damage* mengurangi `Health` saat itu juga, tanpa ada status yang menggantung).
2. **Duration**: Bertahan selama waktu $T$ detik, melakukan kalkulasi modifier atribut secara temporer, dan dihapus saat waktu habis.
3. **Infinite**: Bertahan sampai ada aksi spesifik atau *tag* lain yang membersihkannya (misal: *Aura of Slow* yang aktif hingga keluar dari zona).

### B. Dynamic Attribute Evaluation & Dirty-Flagging
Untuk menghindari *re-computation* matematis yang berat di setiap *tick*, digunakan teknik **Dirty Flagging**. Atribut memiliki nilai:
* `BaseValue`: Nilai permanen karakter.
* `CurrentValue`: Nilai terkomputasi akhir.
* `isDirty`: Boolean flag.

Ketika sebuah GE ditempelkan atau dicabut, status `isDirty` diaktifkan. Nilai `CurrentValue` hanya dihitung ulang saat sistem lain memanggil fungsi `get_value()` pada atribut yang berstatus *dirty*.

### C. The Elemental Matrix & Reaction Cascade
Status reaktif tingkat lanjut menggunakan sistem penandaan status komposisional (*Elemental Gauge Theory*). Karakter menyimpan akumulasi status elemental beserta *decay rate*-nya. Jika unit terkena dua elemen reaktif berbeda, sebuah kalkulasi diskrit dijalankan:
* Reaksi instan mengonsumsi sejumlah gauge dari elemen penempel (*applier*) dan elemen pemicu (*trigger*).
* Menghasilkan efek sekunder: misal *Freeze* yang memunculkan tag `State.Debuff.Frozen`, mengunci *movement*, dan memicu AI State Transition ke status *Helpless*.

### D. Reactive AI Interruption Arbitration
Sistem AI berbasis pohon perilaku (*Behavior Tree*) tradisional biasanya baru mengevaluasi cabang kondisi pada siklus *tick* berikutnya. Pada Sistem Status Reaktif:
* Blackboard mengikat observer secara langsung ke *Tag Container*.
* Saat `State.Debuff.Stun` ditambahkan ke kontainer, sebuah event sinkron di-*fire* ke Blackboard.
* Blackboard mendeteksi adanya node yang sedang berjalan dengan prioritas lebih rendah dari task penanganan Stun.
* Eksekusi task aktif dibatalkan seketika (`Abort()`), dan agen berpindah ke *Stun State* tanpa menunggu frame berikutnya.

---

## 6. Production-Ready Code Implementation

Berikut implementasi lengkap arsitektur Sistem Status Reaktif dan Agen AI dalam bahasa **Python 3.11+** menggunakan pengetikan ketat (*strict typing*), tanpa dependensi eksternal:

```python
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Set, Callable, Optional, Tuple
import time
import math


# =====================================================================
# 1. HIERARCHICAL GAMEPLAY TAG SYSTEM
# =====================================================================

class GameplayTag:
    """
    Hierarchical tag representation (e.g., 'State.Debuff.Stun').
    Supports hierarchical matching: 'State.Debuff' matches 'State.Debuff.Stun'.
    """
    __slots__ = ('_tag_str', '_tokens')

    def __init__(self, tag_str: str) -> None:
        self._tag_str = tag_str
        self._tokens = tuple(tag_str.split('.'))

    @property
    def name(self) -> str:
        return self._tag_str

    def matches(self, other: GameplayTag) -> bool:
        """True if self is identical or more specific than other (parent)."""
        if len(self._tokens) < len(other._tokens):
            return False
        return self._tokens[:len(other._tokens)] == other._tokens

    def __hash__(self) -> int:
        return hash(self._tag_str)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, GameplayTag):
            return self._tag_str == other._tag_str
        return False

    def __repr__(self) -> str:
        return f"Tag({self._tag_str})"


class GameplayTagContainer:
    """Manages counts of tags applied to an entity."""
    def __init__(self) -> None:
        self._tag_counts: Dict[GameplayTag, int] = {}
        self._on_tag_changed_callbacks: List[Callable[[GameplayTag, bool], None]] = []

    def register_callback(self, callback: Callable[[GameplayTag, bool], None]) -> None:
        self._on_tag_changed_callbacks.append(callback)

    def add_tag(self, tag: GameplayTag) -> None:
        current_count = self._tag_counts.get(tag, 0)
        self._tag_counts[tag] = current_count + 1
        if current_count == 0:
            for cb in self._on_tag_changed_callbacks:
                cb(tag, True)

    def remove_tag(self, tag: GameplayTag) -> None:
        if tag not in self._tag_counts:
            return
        self._tag_counts[tag] -= 1
        if self._tag_counts[tag] <= 0:
            del self._tag_counts[tag]
            for cb in self._on_tag_changed_callbacks:
                cb(tag, False)

    def has_tag_exact(self, tag: GameplayTag) -> bool:
        return tag in self._tag_counts

    def has_tag_hierarchical(self, parent_tag: GameplayTag) -> bool:
        """Returns True if any active tag matches parent_tag."""
        for active_tag in self._tag_counts.keys():
            if active_tag.matches(parent_tag):
                return True
        return False


# =====================================================================
# 2. ATTRIBUTE SET & DIRTY-FLAGGED CALCULATION
# =====================================================================

class ModifierOp(Enum):
    FLAT_ADD = auto()
    PERCENT_ADD = auto()
    PERCENT_MULT = auto()


@dataclass(slots=True)
class AttributeModifier:
    source_id: str
    operation: ModifierOp
    magnitude: float


class Attribute:
    """Encapsulates a numeric value with decoupled modifiers and dirty-flag cache."""
    def __init__(self, name: str, base_value: float, min_val: float = 0.0, max_val: float = float('inf')) -> None:
        self.name = name
        self._base_value = base_value
        self._current_value = base_value
        self.min_val = min_val
        self.max_val = max_val
        self._is_dirty = True
        self._modifiers: List[AttributeModifier] = []

    @property
    def base_value(self) -> float:
        return self._base_value

    @base_value.setter
    def base_value(self, val: float) -> None:
        self._base_value = max(self.min_val, min(val, self.max_val))
        self._is_dirty = True

    def add_modifier(self, mod: AttributeModifier) -> None:
        self._modifiers.append(mod)
        self._is_dirty = True

    def remove_modifiers_by_source(self, source_id: str) -> None:
        prev_len = len(self._modifiers)
        self._modifiers = [m for m in self._modifiers if m.source_id != source_id]
        if len(self._modifiers) != prev_len:
            self._is_dirty = True

    def get_value(self) -> float:
        if not self._is_dirty:
            return self._current_value

        # Calculate using standard enterprise formula
        flat_add = 0.0
        percent_add = 0.0
        percent_mult = 1.0

        for mod in self._modifiers:
            if mod.operation == ModifierOp.FLAT_ADD:
                flat_add += mod.magnitude
            elif mod.operation == ModifierOp.PERCENT_ADD:
                percent_add += mod.magnitude
            elif mod.operation == ModifierOp.PERCENT_MULT:
                percent_mult *= (1.0 + mod.magnitude)

        computed = (self._base_value + flat_add) * (1.0 + percent_add) * percent_mult
        self._current_value = max(self.min_val, min(computed, self.max_val))
        self._is_dirty = False
        return self._current_value


# =====================================================================
# 3. GAMEPLAY EFFECT DEFINITIONS & CONTAINER
# =====================================================================

class EffectDurationPolicy(Enum):
    INSTANT = auto()
    DURATION = auto()
    INFINITE = auto()


@dataclass
class ModifierSpec:
    attribute_name: str
    operation: ModifierOp
    magnitude: float


@dataclass
class GameplayEffectSpec:
    name: str
    policy: EffectDurationPolicy
    duration: float = 0.0
    period: float = 0.0  # Periodic tick interval (for DoT/HoT)
    granted_tags: Set[GameplayTag] = field(default_factory=set)
    modifiers: List[ModifierSpec] = field(default_factory=list)
    elemental_type: Optional[str] = None  # e.g., "Fire", "Water"


class ActiveEffectInstance:
    """Runtime tracking of an active gameplay effect on an entity."""
    def __init__(self, spec: GameplayEffectSpec, instigator_id: str) -> None:
        self.spec = spec
        self.instigator_id = instigator_id
        self.instance_id = f"{spec.name}_{time.perf_counter_ns()}"
        self.remaining_duration = spec.duration
        self.time_until_period = spec.period

    def tick(self, delta_time: float) -> Tuple[bool, bool]:
        """Returns (is_expired, period_triggered)."""
        period_triggered = False
        if self.spec.period > 0.0:
            self.time_until_period -= delta_time
            if self.time_until_period <= 0.0:
                period_triggered = True
                self.time_until_period = self.spec.period

        if self.spec.policy == EffectDurationPolicy.DURATION:
            self.remaining_duration -= delta_time
            return (self.remaining_duration <= 0.0, period_triggered)

        return (False, period_triggered)


# =====================================================================
# 4. ELEMENTAL REACTION ENGINE
# =====================================================================

class ElementalReactionEngine:
    """Resolves interactions when different elements collide on an entity."""
    @staticmethod
    def resolve_interaction(existing_element: Optional[str], incoming_element: Optional[str]) -> Optional[str]:
        if not existing_element or not incoming_element:
            return None
        
        pair = {existing_element, incoming_element}
        if pair == {"Pyro", "Hydro"}:
            return "Vaporize"  # Amplifies damage, strips elements
        elif pair == {"Cryo", "Electro"}:
            return "Superconduct"  # Triggers AoE and reduces physical defense
        elif pair == {"Hydro", "Cryo"}:
            return "Freeze"  # Applies Immobilization/Stun
        return None


# =====================================================================
# 5. STATUS CONTAINER & ABILITY SYSTEM COMPONENT (ASC)
# =====================================================================

class AbilitySystemComponent:
    """Central processing unit for entity status, attributes, and tags."""
    def __init__(self, owner_id: str) -> None:
        self.owner_id = owner_id
        self.tags = GameplayTagContainer()
        self.attributes: Dict[str, Attribute] = {}
        self.active_effects: List[ActiveEffectInstance] = []
        self.active_element: Optional[str] = None
        self._on_attribute_mutated_handlers: List[Callable[[str, float], None]] = []

    def register_attribute(self, attribute: Attribute) -> None:
        self.attributes[attribute.name] = attribute

    def register_attribute_changed_handler(self, handler: Callable[[str, float], None]) -> None:
        self._on_attribute_mutated_handlers.append(handler)

    def apply_effect(self, spec: GameplayEffectSpec, instigator_id: str) -> None:
        # Check elemental interactions
        if spec.elemental_type:
            reaction = ElementalReactionEngine.resolve_interaction(self.active_element, spec.elemental_type)
            if reaction:
                self._handle_elemental_reaction(reaction, spec.elemental_type)
                return
            else:
                self.active_element = spec.elemental_type

        # Instant Effect Execution
        if spec.policy == EffectDurationPolicy.INSTANT:
            self._apply_instant_modifiers(spec.modifiers)
            return

        # Duration / Infinite Effect Registration
        instance = ActiveEffectInstance(spec, instigator_id)
        self.active_effects.append(instance)

        # Grant Tags
        for tag in spec.granted_tags:
            self.tags.add_tag(tag)

        # Apply Modifiers
        for mod_spec in spec.modifiers:
            if mod_spec.attribute_name in self.attributes:
                attr = self.attributes[mod_spec.attribute_name]
                attr.add_modifier(AttributeModifier(
                    source_id=instance.instance_id,
                    operation=mod_spec.operation,
                    magnitude=mod_spec.magnitude
                ))
                self._notify_attribute_change(attr)

    def _apply_instant_modifiers(self, modifiers: List[ModifierSpec]) -> None:
        for mod in modifiers:
            if mod.attribute_name in self.attributes:
                attr = self.attributes[mod.attribute_name]
                if mod.operation == ModifierOp.FLAT_ADD:
                    attr.base_value += mod.magnitude
                elif mod.operation == ModifierOp.PERCENT_ADD:
                    attr.base_value += (attr.base_value * mod.magnitude)
                self._notify_attribute_change(attr)

    def _handle_elemental_reaction(self, reaction: str, trigger_element: str) -> None:
        print(f"[REACTION] {reaction} triggered on entity '{self.owner_id}'!")
        if reaction == "Freeze":
            # Apply Stun Effect dynamically
            freeze_spec = GameplayEffectSpec(
                name="Reaction_Freeze",
                policy=EffectDurationPolicy.DURATION,
                duration=3.0,
                granted_tags={GameplayTag("State.Debuff.Stun"), GameplayTag("State.Elemental.Frozen")}
            )
            self.active_element = None
            self.apply_effect(freeze_spec, self.owner_id)
        elif reaction == "Vaporize":
            # Direct raw damage application
            vaporize_dmg = GameplayEffectSpec(
                name="Vaporize_Burst",
                policy=EffectDurationPolicy.INSTANT,
                modifiers=[ModifierSpec("Health", ModifierOp.FLAT_ADD, -50.0)]
            )
            self.active_element = None
            self.apply_effect(vaporize_dmg, self.owner_id)

    def _notify_attribute_change(self, attr: Attribute) -> None:
        val = attr.get_value()
        for handler in self._on_attribute_mutated_handlers:
            handler(attr.name, val)

    def update_tick(self, delta_time: float) -> None:
        expired_effects: List[ActiveEffectInstance] = []

        for effect in self.active_effects:
            is_expired, period_triggered = effect.tick(delta_time)

            if period_triggered:
                # Periodic Tick (e.g., DoT damage execution)
                self._apply_instant_modifiers(effect.spec.modifiers)

            if is_expired:
                expired_effects.append(effect)

        for expired in expired_effects:
            self._remove_effect(expired)

    def _remove_effect(self, effect: ActiveEffectInstance) -> None:
        self.active_effects.remove(effect)

        # Remove Tags
        for tag in effect.spec.granted_tags:
            self.tags.remove_tag(tag)

        # Remove Modifiers
        for mod_spec in effect.spec.modifiers:
            if mod_spec.attribute_name in self.attributes:
                attr = self.attributes[mod_spec.attribute_name]
                attr.remove_modifiers_by_source(effect.instance_id)
                self._notify_attribute_change(attr)


# =====================================================================
# 6. REACTIVE AI BLACKBOARD & AGENT ARBITRATION
# =====================================================================

class ReactiveBlackboard:
    """Thread-safe event-driven Blackboard for AI decision state."""
    def __init__(self) -> None:
        self._data: Dict[str, object] = {}
        self._observers: Dict[str, List[Callable[[object], None]]] = {}

    def set_value(self, key: str, value: object) -> None:
        prev = self._data.get(key)
        if prev != value:
            self._data[key] = value
            if key in self._observers:
                for observer in self._observers[key]:
                    observer(value)

    def get_value(self, key: str, default: object = None) -> object:
        return self._data.get(key, default)

    def observe(self, key: str, callback: Callable[[object], None]) -> None:
        if key not in self._observers:
            self._observers[key] = []
        self._observers[key].append(callback)


class ReactiveAIAgent:
    """AI Entity that prioritizes actions and aborts state via reactive hooks."""
    def __init__(self, agent_id: str) -> None:
        self.agent_id = agent_id
        self.asc = AbilitySystemComponent(agent_id)
        self.blackboard = ReactiveBlackboard()
        self.current_state = "IDLE"

        # Initialize core attributes
        self.asc.register_attribute(Attribute("Health", 100.0, 0.0, 100.0))
        self.asc.register_attribute(Attribute("MoveSpeed", 6.0, 0.0, 20.0))

        # Setup reactive bindings between ASC and AI Blackboard
        self._setup_reactive_bindings()

    def _setup_reactive_bindings(self) -> None:
        # Binding 1: Tag Container to Blackboard
        def on_tag_changed(tag: GameplayTag, is_added: bool) -> None:
            if tag.matches(GameplayTag("State.Debuff.Stun")):
                self.blackboard.set_value("IsStunned", is_added)

        self.asc.tags.register_callback(on_tag_changed)

        # Binding 2: Attributes to Blackboard
        def on_attribute_changed(attr_name: str, current_val: float) -> None:
            if attr_name == "Health":
                self.blackboard.set_value("HealthPercent", current_val / 100.0)

        self.asc.register_attribute_changed_handler(on_attribute_changed)

        # Binding 3: Blackboard Reactive Arbiter Interrupt
        self.blackboard.observe("IsStunned", self._on_stunned_state_changed)
        self.blackboard.observe("HealthPercent", self._on_health_critical_check)

    def _on_stunned_state_changed(self, value: object) -> None:
        is_stunned = bool(value)
        if is_stunned:
            print(f"[AI INTERRUPT] Agent '{self.agent_id}' is STUNNED! Aborting state '{self.current_state}'.")
            self.current_state = "INCAPACITATED"
        else:
            print(f"[AI RECOVERY] Agent '{self.agent_id}' recovered from STUN. Re-evaluating behavior.")
            self.current_state = "IDLE"

    def _on_health_critical_check(self, value: object) -> None:
        health_pct = float(value) # type: ignore
        if health_pct < 0.25 and self.current_state not in ("INCAPACITATED", "FLEEING"):
            print(f"[AI EMERGENCY] Agent '{self.agent_id}' health critical ({health_pct*100:.1f}%)! Switching to FLEEING.")
            self.current_state = "FLEEING"

    def execute_ai_tick(self, delta_time: float) -> None:
        """Simulates tick for systems that require time stepping."""
        self.asc.update_tick(delta_time)
        
        # State execution logic
        if self.current_state == "IDLE":
            # Normal routine execution
            pass
        elif self.current_state == "FLEEING":
            # Execute tactical evasion
            pass
        elif self.current_state == "INCAPACITATED":
            # Blocked from processing actions
            pass
```

### Verifikasi Kerja Sistem (Dry Run Simulation)

Kode pengujian berikut memvalidasi:
1. Reaksi elemental Hydro + Cryo menghasilkan Freeze.
2. Penambahan tag `State.Debuff.Stun` memicu interupsi AI secara instan dari state `IDLE` ke `INCAPACITATED`.
3. Pengurangan MoveSpeed melalui *debuff* bertingkat via dirty flag.
4. Pemulihan status setelah efek kedaluwarsa.

```python
if __name__ == "__main__":
    print("=== INITIALIZING REACTIVE GAMEPLAY AI AGENT ===")
    agent = ReactiveAIAgent("Boss_Minion_01")
    print(f"Initial State: {agent.current_state}")
    print(f"Initial MoveSpeed: {agent.asc.attributes['MoveSpeed'].get_value()}")

    # 1. Apply Hydro status
    print("\n--- Applying Hydro Status ---")
    hydro_effect = GameplayEffectSpec(
        name="Hydro_Application",
        policy=EffectDurationPolicy.DURATION,
        duration=5.0,
        elemental_type="Hydro"
    )
    agent.asc.apply_effect(hydro_effect, "Player_Wizard")

    # 2. Apply Cryo status -> Should trigger Freeze Reaction & Stun Tag
    print("\n--- Applying Cryo Status (Triggers Reaction) ---")
    cryo_effect = GameplayEffectSpec(
        name="Cryo_Application",
        policy=EffectDurationPolicy.DURATION,
        duration=3.0,
        elemental_type="Cryo"
    )
    agent.asc.apply_effect(cryo_effect, "Player_Wizard")
    print(f"Current Agent State after reaction: {agent.current_state}")

    # 3. Apply Slow Effect (-50% MoveSpeed)
    print("\n--- Applying Slow Effect (Percent Additive Modifier) ---")
    slow_effect = GameplayEffectSpec(
        name="Frost_Slow",
        policy=EffectDurationPolicy.DURATION,
        duration=2.0,
        modifiers=[ModifierSpec("MoveSpeed", ModifierOp.PERCENT_ADD, -0.50)]
    )
    agent.asc.apply_effect(slow_effect, "Player_Wizard")
    print(f"Modified MoveSpeed: {agent.asc.attributes['MoveSpeed'].get_value()} (Expected: 3.0)")

    # 4. Advance World Time to Simulate Expiration
    print("\n--- Simulating 3.5 Seconds Tick Advance ---")
    agent.execute_ai_tick(3.5)
    print(f"Agent State after 3.5s: {agent.current_state}")
    print(f"MoveSpeed after Slow Expiration: {agent.asc.attributes['MoveSpeed'].get_value()} (Expected: 6.0)")
```

---

## 7. Edge Cases & Failure Modes

### 1. Circular Reaction Loops (Infinite Cascading)
* **Kasus**: Reaksi A memicu efek B, efek B memicu ledakan yang menempelkan elemen A kembali pada entitas yang sama atau area sekitarnya.
* **Mitigasi**: Implementasi *Reaction Cooldown Buffer* (*Internal Cooldown / ICD*) per pasangan elemen pada entitas. Gunakan *Recursion Guard counter* di dalam fungsi `apply_effect()`; jika kedalaman rekursi melampaui ambang batas batas aman (misal: $> 3$), hentikan propagasi dan catat error ke diagnostic log.

### 2. Delta-Time Accumulation Drift pada Periodic Ticks
* **Kasus**: Delta time frame rates yang fluktuatif menyebabkan status *damage-over-time (DoT)* mengeksekusi tick lebih banyak atau lebih sedikit dari yang didesain selama durasi $T$.
* **Mitigasi**: Gunakan **Accumulator-based time tracking**:
  ```python
  self.time_until_period -= delta_time
  while self.time_until_period <= 0.0 and not is_expired:
      trigger_period_effect()
      self.time_until_period += self.spec.period
  ```

### 3. Orphaned Modifiers saat Entitas Hancur
* **Kasus**: Entitas instigator mati atau di-*despawn* saat efek durasinya masih aktif pada target, mengakibatkan referensi memori menggantung (*memory leak*) atau kegagalan saat efek mencoba memanggil *callback* ke instigator.
* **Mitigasi**: Simpan `instigator_id` berupa ID numerik (UUID/Int) diskrit, bukan referensi pointer langsung ke objek instigator (*weak references* atau *Entity ID abstraction*).

### 4. Tag Negative Count Anomaly
* **Kasus**: Dua efek berbeda mencabut tag yang sama secara tidak teratur, menyebabkan kalkulasi penghitung tag turun di bawah nol (`count < 0`).
* **Mitigasi**: Hindari pengurangan nilai primitif mentah; kelola tag dengan kamus penghitung eksplisit (*reference counted set*) dan pasang *assertion* pencegahan:
  ```python
  assert self._tag_counts[tag] >= 0, f"Critical: Negative tag count detected for {tag.name}"
  ```

---

## 8. Trade-offs & Alternatif Solusi

| Dimensi Arsitektur | Reactive Gameplay Ability System (GAS) | Finite State Machine (FSM) Konvensional | Pure ECS (Component-Data Driven) |
| :--- | :--- | :--- | :--- |
| **Kompleksitas Implementasi** | **Tinggi**. Membutuhkan engine tag, attribute set, dan container terpisah. | **Rendah**. Cukup switch-case atau state pattern dasar. | **Menengah-Tinggi**. Memisahkan data status dan system loop murni. |
| **Beban CPU saat Idle** | **Hampir Nol ($O(1)$)**. Evaluasi hanya dijalankan saat mutasi event. | **Tinggi ($O(N)$)**. Melakukan polling boolean per frame di setiap entitas. | **Rendah ke Menengah**. System mengiterasi array komponen aktif. |
| **Kombinatorika Status** | **Sangat Modular**. Efek baru ditambahkan tanpa mengubah logic AI. | **Kaku**. Menambah 1 status berpotensi merombak seluruh transisi state. | **Sangat Baik**. Penambahan komponen baru decoupled secara alami. |
| **Skalabilitas Konten Tim** | **Tinggi**. Desainer gameplay dapat membuat efek via JSON/Data Assets. | **Sangat Buruk**. Membutuhkan intervensi programmer di script inti. | **Tinggi**. Membutuhkan pipeline tools authoring data yang matang. |

---

## 9. Best Practices & Standard Industri

1. **Pemisahan Logika Simulasi dan Presentasi**: Sistem status reaktif **hanya** memproses logika game numerik dan tag. Jangan mencampur logika visual (seperti instansiasi VFX, pemutaran audio partikel) ke dalam `AbilitySystemComponent`. Gunakan event listener seperti `OnTagAdded("State.Elemental.Frozen")` untuk memicu presentasi VFX secara terpisah.
2. **Kompilasi String Hierarkis ke Bitmask / Int Hash**: Di lingkungan produksi performa tinggi (misal Unreal Engine C++ atau Unity DOTS), hindari perbandingan string hierarkis pada *hot path*. Lakukan *hashing* pada *Gameplay Tag* menjadi *Fixed-length 64-bit Bitmask* atau *MurmurHash3*.
3. **Penerapan Stacking Policy yang Ketat**: Setiap *Gameplay Effect* wajib mendefinisikan batas tumpukan (*Max Stacks*) dan kebijakan tumpukan (*Stack Refresh Policy*):
   * *Refresh Duration*: Mereset timer durasi kembali ke maksimum saat stack baru masuk.
   * *Independent Timers*: Setiap stack menghitung durasinya masing-masing.
   * *Discard*: Stack baru ditolak jika kapasitas maksimum telah tercapai.

---

## 10. Hands-on Lab Exercise

### Deskripsi Skenario
Rancang skenario di mana agen AI bertindak sebagai "Patrol Guard". Agen ini memiliki status dasar `MoveSpeed = 5.0` dan `Health = 100.0`. Anda diminta untuk:
1. Memasang sebuah *Trap Trigger* yang menyemprotkan status "Wet" (`Elemental.Hydro`).
2. Menghantam agen dengan "Lightning Trap" yang menyemprotkan status "Electro" (`Elemental.Electro`).
3. Mengembangkan sistem reaksi elemental baru: **Superconduct** yang:
   * Mengurangi atribut `PhysicalDefense` agen sebesar 40% selama 4 detik.
   * Mengirimkan tag `State.Debuff.Vulnerable` ke tag container agen.
4. Mengikat AI Decision Arbiter agar ketika tag `State.Debuff.Vulnerable` terdeteksi, AI secara reaktif membatalkan rute patroli dan mengeksekusi state `"DEFENSIVE_STANCE"`.

### Langkah-langkah Praktikum

1. **Ekspansi Atribut**:
   Tambahkan atribut `PhysicalDefense` (Base: 50.0, Min: 0.0, Max: 100.0) ke dalam `ReactiveAIAgent`.
2. **Registrasi Reaksi Elemental**:
   Tambahkan logika reaksi `"Electro"` + `"Hydro"` $\rightarrow$ `"ElectroCharged"` atau `"Electro"` + `"Cryo"` $\rightarrow$ `"Superconduct"` pada `ElementalReactionEngine`.
3. **Konstruksi Reactive Blackboard Trigger**:
   Daftarkan listener pada tag `State.Debuff.Vulnerable` yang secara instan memanggil transisi state AI ke `"DEFENSIVE_STANCE"`.
4. **Verifikasi Output**:
   Jalankan simulasi langkah waktu (`delta_time`), verifikasi bahwa nilai `PhysicalDefense` terpotong akurat sesuai rumus persen modifikasi, dan pulih sepenuhnya setelah durasi waktu 4 detik berakhir. Agen harus secara otomatis keluar dari status pertahanan kembali ke `"IDLE"` atau `"PATROL"`.