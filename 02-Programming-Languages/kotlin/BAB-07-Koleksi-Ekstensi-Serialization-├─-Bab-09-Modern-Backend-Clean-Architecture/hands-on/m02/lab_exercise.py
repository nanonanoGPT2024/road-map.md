#!/usr/bin/env python3
"""
Lab Hands-on: Kotlin Concepts Deep-Dive in Python
Bab 07: Koleksi, Ekstensi & Serialization (Modul 02 Deep Dive)

Deskripsi:
Script ini memodelkan dan merekayasa ulang arsitektur internal Kotlin ke dalam Python:
1. Kotlin Sequence (Lazy Evaluation) vs Iterable (Eager Evaluation) Pipeline.
2. Kotlin Dynamic Extension Functions via Type Descriptors & Monkey Patching.
3. Kotlinx-Style Polymorphic Serialization Engine dengan `@SerialName` & Type Discriminators.
"""

import sys
import time
import json
from typing import Callable, Any, Generator, Dict, List, Type, TypeVar, Optional
from dataclasses import dataclass, asdict, field

# --- Terminal ANSI Styling ---
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_RED = "\033[91m"
CLR_GREEN = "\033[92m"
CLR_YELLOW = "\033[93m"
CLR_BLUE = "\033[94m"
CLR_CYAN = "\033[96m"

def print_header(title: str):
    print(f"\n{CLR_BOLD}{CLR_BLUE}{'=' * 75}{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN} [KOTLIN CORE SIMULATOR] :: {title.upper()}{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_BLUE}{'=' * 75}{CLR_RESET}")

def print_sub(title: str):
    print(f"\n{CLR_BOLD}{CLR_YELLOW}---> {title}{CLR_RESET}")

T = TypeVar('T')
R = TypeVar('R')

# ==============================================================================
# 1. KOLEKSI: EAGER (ITERABLE) VS LAZY (SEQUENCE) ENGINE
# ==============================================================================

class KotlinSequence:
    """
    Simulasi kotlin.sequences.Sequence.
    Evaluasi lazy berantai (step-by-step element evaluation) dengan short-circuiting.
    """
    def __init__(self, source_gen_func: Callable[[], Generator[Any, None, None]]):
        self._source_func = source_gen_func

    def __iter__(self):
        return self._source_func()

    def filter(self, predicate: Callable[[Any], bool]) -> 'KotlinSequence':
        def _gen():
            for item in self:
                if predicate(item):
                    yield item
        return KotlinSequence(_gen)

    def map(self, transform: Callable[[Any], Any]) -> 'KotlinSequence':
        def _gen():
            for item in self:
                yield transform(item)
        return KotlinSequence(_gen)

    def take(self, count: int) -> 'KotlinSequence':
        def _gen():
            taken = 0
            for item in self:
                if taken >= count:
                    break
                yield item
                taken += 1
        return KotlinSequence(_gen)

    def to_list(self) -> List[Any]:
        return list(self)


class EagerCollection:
    """
    Simulasi kotlin.collections.List (Eager / Intermediate Collections).
    Membuat intermediate buffer setiap kali filter/map dipanggil.
    """
    def __init__(self, items: List[Any]):
        self._items = list(items)

    def filter(self, predicate: Callable[[Any], bool], stats: Dict[str, int]) -> 'EagerCollection':
        result = []
        for x in self._items:
            stats["eager_ops"] += 1
            if predicate(x):
                result.append(x)
        return EagerCollection(result)

    def map(self, transform: Callable[[Any], Any], stats: Dict[str, int]) -> 'EagerCollection':
        result = []
        for x in self._items:
            stats["eager_ops"] += 1
            result.append(transform(x))
        return EagerCollection(result)

    def take(self, count: int) -> 'EagerCollection':
        return EagerCollection(self._items[:count])

    def to_list(self) -> List[Any]:
        return self._items


# ==============================================================================
# 2. EKSTENSI: EXTENSION FUNCTIONS ARCHITECTURE
# ==============================================================================

class ExtensionHost:
    """
    Mensimulasikan deklarasi ekstensi Kotlin:
    fun Receiver.extensionName(args) -> ReturnType
    """
    _registered_extensions: Dict[str, Dict[str, Callable]] = {}

    @classmethod
    def register(cls, target_cls: Type, method_name: str, func: Callable):
        cls_name = target_cls.__qualname__
        if cls_name not in cls._registered_extensions:
            cls._registered_extensions[cls_name] = {}
        cls._registered_extensions[cls_name][method_name] = func

        # Dynamic binding ke class (simulasi static resolution resolution di Kotlin)
        def wrapper(self, *args, **kwargs):
            return func(self, *args, **kwargs)

        setattr(target_cls, method_name, wrapper)

def kotlin_extension(target_type: Type):
    """Decorator untuk mensimulasikan sintaks deklarasi ekstensi Kotlin."""
    def decorator(fn: Callable):
        ExtensionHost.register(target_type, fn.__name__, fn)
        return fn
    return decorator


# ==============================================================================
# 3. SERIALIZATION: KOTLINX.SERIALIZATION POLYMORPHIC SIMULATOR
# ==============================================================================

class KSerializer:
    """
    Engine serializer berbasis format Kotlinx.Serialization.
    Mendukung class discriminator (_type) dan custom SerialName.
    """
    _type_registry: Dict[str, Type] = {}
    _tag_registry: Dict[Type, str] = {}

    @classmethod
    def register_sealed_subclass(cls, serial_name: str):
        def decorator(subclass: Type):
            cls._type_registry[serial_name] = subclass
            cls._tag_registry[subclass] = serial_name
            return subclass
        return decorator

    @classmethod
    def encode_to_json(cls, obj: Any) -> str:
        obj_type = type(obj)
        if obj_type in cls._tag_registry:
            raw_dict = asdict(obj)
            # Inject polymorphic type discriminator
            raw_dict["@type"] = cls._tag_registry[obj_type]
            return json.dumps(raw_dict, indent=2)
        elif hasattr(obj, "__dict__"):
            return json.dumps(asdict(obj) if hasattr(obj, '__dataclass_fields__') else obj.__dict__, indent=2)
        return json.dumps(obj)

    @classmethod
    def decode_from_json(cls, json_str: str, base_cls: Optional[Type] = None) -> Any:
        data = json.loads(json_str)
        if isinstance(data, dict) and "@type" in data:
            type_tag = data.pop("@type")
            target_cls = cls._type_registry.get(type_tag)
            if not target_cls:
                raise ValueError(f"Serializer error: Unregistered type tag '{type_tag}'")
            return target_cls(**data)
        elif base_cls:
            return base_cls(**data)
        return data


# Definisi Model Data (Simulasi Sealed Interface di Kotlin)
class CoreEvent:
    pass

@KSerializer.register_sealed_subclass("events.LoginEvent")
@dataclass
class LoginEvent(CoreEvent):
    user_id: str
    ip_address: str
    timestamp: int = field(default_factory=lambda: int(time.time()))

@KSerializer.register_sealed_subclass("events.PaymentEvent")
@dataclass
class PaymentEvent(CoreEvent):
    user_id: str
    amount: float
    currency: str
    status: str = "PENDING"


# ==============================================================================
# LAB DEMO EXECUTION
# ==============================================================================

def run_collection_deep_dive():
    print_sub("1. Koleksi: Intermediate Collections vs Lazy Sequences")
    DATASET_SIZE = 100_000
    TARGET_TAKE = 3

    print(f"Dataset ukuran: {CLR_BOLD}{DATASET_SIZE:,}{CLR_RESET} integers.")
    print(f"Pipeline: filter(genap) -> map(kali 10) -> take({TARGET_TAKE})")

    # --- Test 1: Eager / Iterable Evaluation ---
    eager_stats = {"eager_ops": 0}
    raw_data = list(range(DATASET_SIZE))
    
    t0 = time.perf_counter()
    eager_col = EagerCollection(raw_data)
    eager_res = (eager_col
                 .filter(lambda x: x % 2 == 0, eager_stats)
                 .map(lambda x: x * 10, eager_stats)
                 .take(TARGET_TAKE)
                 .to_list())
    eager_duration = (time.perf_counter() - t0) * 1000

    print(f"\n{CLR_RED}[Eager / List Pipeline]{CLR_RESET}")
    print(f"  Hasil Output           : {eager_res}")
    print(f"  Total Operasi Komputasi : {eager_stats['eager_ops']:,} operations")
    print(f"  Waktu Eksekusi         : {eager_duration:.2f} ms")

    # --- Test 2: Sequence / Lazy Evaluation ---
    seq_ops = 0
    def sequence_source():
        for x in range(DATASET_SIZE):
            yield x

    def tracked_filter(x):
        nonlocal seq_ops
        seq_ops += 1
        return x % 2 == 0

    def tracked_map(x):
        nonlocal seq_ops
        seq_ops += 1
        return x * 10

    t0 = time.perf_counter()
    seq_pipeline = (KotlinSequence(sequence_source)
                    .filter(tracked_filter)
                    .map(tracked_map)
                    .take(TARGET_TAKE))
    seq_res = seq_pipeline.to_list()
    seq_duration = (time.perf_counter() - t0) * 1000

    print(f"\n{CLR_GREEN}[Lazy / Sequence Pipeline]{CLR_RESET}")
    print(f"  Hasil Output           : {seq_res}")
    print(f"  Total Operasi Komputasi : {seq_ops} operations (Short-circuited!)")
    print(f"  Waktu Eksekusi         : {seq_duration:.2f} ms")

    diff = (eager_stats['eager_ops'] - seq_ops)
    print(f"\n{CLR_CYAN}Efisiensi Operasi: Menghemat {diff:,} eksekusi berkat Sequence lazy pipeline.{CLR_RESET}")


def run_extensions_deep_dive():
    print_sub("2. Kotlin Dynamic Extension Functions")

    # Mendaftarkan Extension pada tipe bawaan str
    @kotlin_extension(str)
    def mask_credentials(self: str, unmasked_suffix: int = 4) -> str:
        """Ekstensi String: fun String.maskCredentials()"""
        if len(self) <= unmasked_suffix:
            return "*" * len(self)
        return ("*" * (len(self) - unmasked_suffix)) + self[-unmasked_suffix:]

    @kotlin_extension(list)
    def chunked_pairs(self: list) -> List[tuple]:
        """Ekstensi List: fun <T> List<T>.chunkedPairs()"""
        return [(self[i], self[i+1]) for i in range(0, len(self) - 1, 2)]

    token = "secret_api_key_live_9988223344"
    data_list = [10, 20, 30, 40, 50, 60]

    # Eksekusi langsung sebagai method milik instance
    print(f"Target String Asli        : {token}")
    print(f"Hasil Extension Masking   : {CLR_GREEN}{token.mask_credentials(6)}{CLR_RESET}") # type: ignore
    
    print(f"\nTarget List Asli          : {data_list}")
    print(f"Hasil Extension Chunking  : {CLR_GREEN}{data_list.chunked_pairs()}{CLR_RESET}") # type: ignore


def run_serialization_deep_dive():
    print_sub("3. kotlinx.serialization Polymorphism Engine")

    events: List[CoreEvent] = [
        LoginEvent(user_id="usr_prod_101", ip_address="192.168.1.15"),
        PaymentEvent(user_id="usr_prod_101", amount=150.75, currency="USD", status="SETTLED"),
        PaymentEvent(user_id="usr_prod_202", amount=49.99, currency="IDR", status="DECLINED")
    ]

    print("Mengonversi polimorfik sealed interface hierarchy ke Kotlinx-compliant JSON payload:")
    
    serialized_payloads = []
    for ev in events:
        json_output = KSerializer.encode_to_json(ev)
        serialized_payloads.append(json_output)
        print(f"{CLR_YELLOW}{json_output}{CLR_RESET}")

    print(f"\n{CLR_BOLD}Mendekode balik dari Serialized JSON ke Strong Dynamic Instances:{CLR_RESET}")
    for idx, payload in enumerate(serialized_payloads):
        decoded_obj = KSerializer.decode_from_json(payload)
        print(f"[{idx+1}] Tipe Hasil: {CLR_GREEN}{type(decoded_obj).__name__}{CLR_RESET} -> Nilai: {decoded_obj}")


def main():
    print_header("Simulasi Kotlin 07: Koleksi, Ekstensi & Serialization")
    run_collection_deep_dive()
    run_extensions_deep_dive()
    run_serialization_deep_dive()
    print_sub("Kesimpulan Teknis")
    print(f"{CLR_GREEN}✓ Lazy sequences meminimalkan memory footprint dan operasi tidak perlu.{CLR_RESET}")
    print(f"{CLR_GREEN}✓ Dynamic extensions memperluas fungsionalitas tanpa polusi inheritance.{CLR_RESET}")
    print(f"{CLR_GREEN}✓ Polymorphic serialization memungkinkan interoperabilitas data polymorphic yang aman.{CLR_RESET}\n")

if __name__ == "__main__":
    main()