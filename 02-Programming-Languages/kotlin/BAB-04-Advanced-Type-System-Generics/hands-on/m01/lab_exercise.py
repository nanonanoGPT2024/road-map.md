#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Sistem Tipe Tingkat Lanjut & Generics Kotlin
Topik: BAB-04 Advanced Type System & Generics
File: hands-on/m01/lab_exercise.py

Fitur Simulasi Teknis:
1. Variance: Covariant (out T / Producer), Contravariant (in T / Consumer), Invariant
2. Upper Bounds & Generic Constraints (<T : Comparable<T>>)
3. Type Erasure vs Reified Type Parameters (inline fun <reified T>)
4. Star Projection (* vs Any?)
5. The 'Nothing' Bottom Type & Nullable Hierarchy
"""

import sys
import time
from typing import Any, Generic, TypeVar, List, Type, Optional

# --- ANSI Color Codes ---
class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    BG_BLUE = "\033[44m"
    BG_DARK = "\033[100m"

def print_header(title: str):
    print(f"\n{Color.BG_BLUE}{Color.WHITE}{Color.BOLD} === {title.upper()} === {Color.RESET}")

def print_success(msg: str):
    print(f"{Color.GREEN}[✓ VALID / SUCCESS]{Color.RESET} {msg}")

def print_error(msg: str):
    print(f"{Color.RED}[✗ TYPE ERROR / REJECTED]{Color.RESET} {msg}")

def print_info(msg: str):
    print(f"{Color.CYAN}[i INFO]{Color.RESET} {msg}")

def print_kotlin_code(code: str):
    print(f"{Color.YELLOW}--- Kotlin Equivalent ---{Color.RESET}")
    for line in code.strip().split("\n"):
        print(f"  {Color.BOLD}{line}{Color.RESET}")
    print(f"{Color.YELLOW}--------------------------{Color.RESET}")

# ==============================================================================
# 1. HIERARKI KELAS SIMULASI (Animal -> Dog -> GoldenRetriever)
# ==============================================================================
class Animal:
    def speak(self) -> str:
        return "Generic Animal Sound"
    def __str__(self):
        return f"{Color.WHITE}Animal{Color.RESET}"

class Dog(Animal):
    def speak(self) -> str:
        return "Woof! Woof!"
    def __str__(self):
        return f"{Color.CYAN}Dog{Color.RESET}"

class GoldenRetriever(Dog):
    def speak(self) -> str:
        return "Gentle Golden Bark!"
    def __str__(self):
        return f"{Color.YELLOW}GoldenRetriever{Color.RESET}"

class Cat(Animal):
    def speak(self) -> str:
        return "Meow!"
    def __str__(self):
        return f"{Color.MAGENTA}Cat{Color.RESET}"

# ==============================================================================
# 2. SIMULASI DECLARATION-SITE VARIANCE (out vs in)
# ==============================================================================
T_co = TypeVar('T_co', covariant=True)
T_contra = TypeVar('T_contra', contravariant=True)

class Producer(Generic[T_co]):
    """Simulasi Kotlin: interface Producer<out T> { fun produce(): T }"""
    def __init__(self, item: Any, item_cls: Type):
        self._item = item
        self.item_cls = item_cls

    def produce(self) -> Any:
        return self._item

class Consumer(Generic[T_contra]):
    """Simulasi Kotlin: interface Consumer<in T> { fun consume(item: T) }"""
    def __init__(self, target_cls: Type):
        self.target_cls = target_cls

    def consume(self, item: Any):
        if not isinstance(item, self.target_cls):
            raise TypeError(f"Consumer mengharapkan {self.target_cls.__name__}, tetapi menerima {type(item).__name__}")
        print(f"    -> Mengonsumsi {item} ({type(item).__name__}) berhasil: '{item.speak()}'")

def demo_variance():
    print_header("1. Declaration-site Variance (out T vs in T)")
    print_kotlin_code("""
// Covariance: Producer (out) - aman disubstitusikan ke subtipe yang lebih umum
interface Source<out T> { fun next(): T }
val dogSource: Source<Dog> = ...
val animalSource: Source<Animal> = dogSource // LEGAL

// Contravariance: Consumer (in) - aman disubstitusikan ke tipe yang lebih spesifik
interface Sink<in T> { fun accept(item: T) }
val animalSink: Sink<Animal> = ...
val dogSink: Sink<Dog> = animalSink // LEGAL
    """)

    print_info("Menguji Covariance (out T - Producer):")
    golden_producer = Producer(GoldenRetriever(), GoldenRetriever)
    print_info(f"Dibuat Producer<GoldenRetriever>. Memeriksa apakah bisa disubstitusi ke Producer<Animal>...")
    if issubclass(golden_producer.item_cls, Animal):
        print_success("Producer<GoldenRetriever> valid sebagai Producer<Animal> karena GoldenRetriever : Dog : Animal")
    
    print("\n" + Color.CYAN + "[i INFO] Menguji Contravariance (in T - Consumer):" + Color.RESET)
    animal_consumer = Consumer(Animal)
    print_info("Dibuat Consumer<Animal>. Menguji apakah aman menerima Dog & GoldenRetriever...")
    try:
        animal_consumer.consume(Dog())
        animal_consumer.consume(GoldenRetriever())
        print_success("Consumer<Animal> sukses mengonsumsi subtipe Dog & GoldenRetriever")
    except TypeError as e:
        print_error(str(e))

    print_info("Uji Kesalahan: Consumer<Dog> mencoba mengonsumsi Cat...")
    dog_consumer = Consumer(Dog)
    try:
        dog_consumer.consume(Cat())
    except TypeError as e:
        print_error(f"Ditolak compiler: {e}")

# ==============================================================================
# 3. GENERIC UPPER BOUNDS (<T : Number>, <T : Comparable<T>>)
# ==============================================================================
def demo_upper_bounds():
    print_header("2. Generic Upper Bounds & Constraints (<T : Number>)")
    print_kotlin_code("""
fun <T : Number> sumAsDouble(a: T, b: T): Double {
    return a.toDouble() + b.toDouble()
}
// Upper bound memastikan T memiliki fungsi/sifat dari Number
    """)

    def kotlin_sum_numbers(a: Any, b: Any, bound_type: Any):
        type_name = getattr(bound_type, '__name__', str(bound_type))
        if not isinstance(a, bound_type) or not isinstance(b, bound_type):
            raise TypeError(f"Constraint Violation: T harus merupakan turunan dari {type_name}")
        return float(a) + float(b)

    print_info("Memanggil sumAsDouble(10, 25.5) dengan bound Number (int/float):")
    try:
        res = kotlin_sum_numbers(10, 25.5, (int, float))
        print_success(f"Hasil Penjumlahan: {res}")
    except TypeError as e:
        print_error(str(e))

    print_info("Memanggil sumAsDouble('100', 50) dengan bound Number:")
    try:
        res = kotlin_sum_numbers("100", 50, (int, float))
        print_success(f"Hasil Penjumlahan: {res}")
    except TypeError as e:
        print_error(f"Ditolak Type Checker: {e}")

# ==============================================================================
# 4. TYPE ERASURE VS REIFIED TYPE PARAMETERS
# ==============================================================================
class KotlinGenericFunctionSim:
    @staticmethod
    def standard_generic_check(items: List[Any]):
        """Simulasi fungsi biasa tanpa reified: List<T> mengalami Type Erasure di JVM."""
        print_info("Dalam JVM biasa: List<Dog> dan List<Cat> menjadi raw List (Type Erasure).")
        print_error("Cannot check for instance of erased type: `if (items is List<Dog>)` TIDAK BISA DI-COMPILE!")

    @staticmethod
    def reified_inline_filter(items: List[Any], reified_cls: Type):
        """Simulasi inline fun <reified T> filterIsInstance(): List<T>"""
        print_success(f"Menggunakan inline fun <reified {reified_cls.__name__}> filterIsInstance()")
        filtered = [x for x in items if isinstance(x, reified_cls)]
        return filtered

def demo_reified():
    print_header("3. Type Erasure vs Reified Type Parameters")
    print_kotlin_code("""
// Standard generic (Type Erasure pada bytecode JVM):
// fun <T> checkType(list: List<Any>) { if (list is List<T>) ... } // ERROR!

// Solusi Kotlin: inline function dengan reified modifier
inline fun <reified T> List<Any>.filterIsInstance(): List<T> {
    val result = mutableListOf<T>()
    for (item in this) {
        if (item is T) result.add(item)
    }
    return result
}
    """)

    mixed_list = [Dog(), Cat(), GoldenRetriever(), Dog(), "String Non-Animal", 42]
    print_info(f"Isi List<Any>: {[str(x) for x in mixed_list]}")

    KotlinGenericFunctionSim.standard_generic_check(mixed_list)
    print()
    filtered_dogs = KotlinGenericFunctionSim.reified_inline_filter(mixed_list, Dog)
    print(f"    Hasil filterIsInstance<Dog>(): {[f'{x} ({type(x).__name__})' for x in filtered_dogs]}")
    print_success(f"Ditemukan {len(filtered_dogs)} elemen turunan Dog (termasuk GoldenRetriever).")

# ==============================================================================
# 5. STAR-PROJECTION (* Projections)
# ==============================================================================
def demo_star_projection():
    print_header("4. Star-Projection Simulation (List<*>)")
    print_kotlin_code("""
// Star projection List<*> berarti kita tidak tahu tipe argumennya secara spesifik.
// Pembacaan aman: elemen yang diambil bertipe Any? (Covariant out Any?)
// Penulisan dilarang: kita tidak bisa menambahkan apapun selain Nothing/null (Contravariant in Nothing)
fun printAnyList(list: List<*>) {
    for (item in list) {
        val safeItem: Any? = item // Safe!
        println(safeItem)
    }
    // list.add(...) // ERROR: Type mismatch, Required: CapturedType(*)
}
    """)

    def simulate_star_projected_list(items: List[Any]):
        print_info("Membaca dari List<*>:")
        for idx, item in enumerate(items):
            print(f"    Index {idx}: {item} -> Dibaca aman sebagai Any? ({type(item).__name__})")
        print_info("Mencoba menulis ke List<*>:")
        print_error("Write dilarang! Kompiler Kotlin menolak penambahan item ke collection dengan star-projection.")

    simulate_star_projected_list([Dog(), "Hello Kotlin", 3.14159])

# ==============================================================================
# 6. THE 'NOTHING' BOTTOM TYPE & TYPE HIERARCHY
# ==============================================================================
def demo_nothing_type():
    print_header("5. The 'Nothing' Bottom Type & Nullable System")
    print_kotlin_code("""
// Kotlin Type Hierarchy:
//            Any?
//           /    \\
//        Any      null (Type of null is Nothing?)
//       /   \\        /
//   String   Int   ...
//       \\   /        /
//        Nothing  ---
//
// Nothing adalah subtipe dari semua tipe (Bottom Type).
// Sebuah fungsi bertipe Nothing tidak pernah mengembalikan nilai secara normal (selalu throw / infinite loop).
fun fail(message: String): Nothing {
    throw IllegalStateException(message)
}
val data: String = nullableValue ?: fail("Value must not be null")
    """)

    def kotlin_fail(message: str) -> None:
        raise RuntimeError(f"FATAL EXCEPTION [Nothing]: {message}")

    nullable_val: Optional[str] = None
    print_info(f"Menguji ekspresi elvis `val s: String = nullable_val ?: fail(...)`")
    try:
        val_result = nullable_val if nullable_val is not None else kotlin_fail("Nilai konfigurasi kosong!")
        print(val_result)
    except RuntimeError as ex:
        print_success(f"Ekspresi Nothing dieksekusi dengan aman menghentikan alur kode: {ex}")

# ==============================================================================
# MENU UTAMA INTERAKTIF
# ==============================================================================
def main():
    while True:
        print(f"\n{Color.BG_DARK}{Color.WHITE}{Color.BOLD} ==================================================================== {Color.RESET}")
        print(f"{Color.CYAN}{Color.BOLD}  KOTLIN ADVANCED TYPE SYSTEM & GENERICS INTERACTIVE SIMULATOR (BAB-04) {Color.RESET}")
        print(f"{Color.BG_DARK}{Color.WHITE}{Color.BOLD} ==================================================================== {Color.RESET}")
        print(f"  {Color.BOLD}1.{Color.RESET} Declaration-site Variance (out T / in T / Invariance)")
        print(f"  {Color.BOLD}2.{Color.RESET} Generic Upper Bounds & Constraints (<T : Number>)")
        print(f"  {Color.BOLD}3.{Color.RESET} Type Erasure vs Reified Type Parameters (inline fun <reified T>)")
        print(f"  {Color.BOLD}4.{Color.RESET} Star-Projections (List<*>)")
        print(f"  {Color.BOLD}5.{Color.RESET} Nothing Bottom Type & Null Safety Hierarchy")
        print(f"  {Color.BOLD}6.{Color.RESET} Jalankan Seluruh Demo Simulasi (Full Suite)")
        print(f"  {Color.BOLD}0.{Color.RESET} Keluar")
        print(f"{Color.WHITE}--------------------------------------------------------------------{Color.RESET}")

        if len(sys.argv) > 1 and sys.argv[1] == "--all":
            choice = "6"
        else:
            try:
                choice = input(f"{Color.YELLOW}Pilih modul simulasi [0-6]: {Color.RESET}").strip()
            except (EOFError, KeyboardInterrupt):
                print(f"\n{Color.RED}Selesai.{Color.RESET}")
                break

        if choice == "1":
            demo_variance()
        elif choice == "2":
            demo_upper_bounds()
        elif choice == "3":
            demo_reified()
        elif choice == "4":
            demo_star_projection()
        elif choice == "5":
            demo_nothing_type()
        elif choice == "6":
            demo_variance()
            time.sleep(0.5)
            demo_upper_bounds()
            time.sleep(0.5)
            demo_reified()
            time.sleep(0.5)
            demo_star_projection()
            time.sleep(0.5)
            demo_nothing_type()
            if len(sys.argv) > 1:
                break
        elif choice == "0":
            print(f"{Color.GREEN}Terima kasih! Sesi simulasi BAB-04 selesai.{Color.RESET}")
            break
        else:
            print(f"{Color.RED}Pilihan tidak valid. Silakan masukkan angka 0-6.{Color.RESET}")

if __name__ == "__main__":
    main()
