#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Sistem Pengetikan Tingkat Lanjut Scala (BAB-05)
Topik Inti:
  1. Variance: Invariant [T], Covariant [+T], Contravariant [-T]
  2. Upper Bound [T <: Bound] & Lower Bound [T >: Bound]
  3. Path-Dependent Types (outer.Inner)
  4. Self-Type Annotations (trait Foo { this: Bar => })
  5. Phantom Types (Compile-time Type State Pattern)
"""

import sys
import time
from typing import Any, Generic, TypeVar, Optional, Callable


# ============================================================================
# ANSI Color Formatting Helper
# ============================================================================
class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"

def print_header(title: str) -> None:
    print(f"\n{Color.BOLD}{Color.CYAN}{'=' * 65}{Color.RESET}")
    print(f"{Color.BOLD}{Color.YELLOW}  [SCALA TYPE SYSTEM SIMULATION] :: {title}{Color.RESET}")
    print(f"{Color.BOLD}{Color.CYAN}{'=' * 65}{Color.RESET}")

def print_success(msg: str) -> None:
    print(f"{Color.GREEN}✓ [TYPECHECK OK] {msg}{Color.RESET}")

def print_type_error(expected: str, got: str, reason: str) -> None:
    print(f"{Color.RED}✗ [TYPE MISMATCH ERROR]{Color.RESET}")
    print(f"  {Color.BOLD}Expected:{Color.RESET} {expected}")
    print(f"  {Color.BOLD}Found:   {Color.RESET} {got}")
    print(f"  {Color.RED}Reason:  {reason}{Color.RESET}")

def print_info(label: str, detail: str) -> None:
    print(f"  {Color.BLUE}➜ {label}:{Color.RESET} {detail}")


# ============================================================================
# 1. Domain Model Hierarchy (Subtyping Base)
# ============================================================================
class Animal:
    def sound(self) -> str:
        return "Generic Animal Sound"

class Dog(Animal):
    def sound(self) -> str:
        return "Woof Woof!"

class Puppy(Dog):
    def sound(self) -> str:
        return "Yip Yip!"

class Cat(Animal):
    def sound(self) -> str:
        return "Meow Meow!"


# ============================================================================
# 2. Simulation: Invariance, Covariance, Contravariance
# ============================================================================
# Scala:
# class InvariantContainer[T](val item: T)
# class CovariantList[+T](val head: T)
# trait ContravariantConsumer[-T] { def consume(item: T): Unit }

class InvariantContainer:
    """Simulasi Invariant Container [T]: Hanya menerima tipe persis T"""
    def __init__(self, declared_type: type, item: Any):
        if type(item) is not declared_type:
            raise TypeError(f"Invariant: {type(item).__name__} bukan tipe persis {declared_type.__name__}")
        self.item = item
        self.declared_type = declared_type

class CovariantList:
    """Simulasi Covariant List [+T]: Subtype dari T sah diterima"""
    def __init__(self, declared_type: type, items: list):
        for item in items:
            if not issubclass(type(item), declared_type):
                raise TypeError(f"Covariance: {type(item).__name__} bukan turunan dari {declared_type.__name__}")
        self.declared_type = declared_type
        self.items = items

class ContravariantConsumer:
    """Simulasi Contravariant Consumer [-T]: Menerima handler supertype dari T"""
    def __init__(self, target_type: type, handler_type: type, handler: Callable[[Any], None]):
        # Handler supertype mampu menangani subtype T
        if not issubclass(target_type, handler_type):
            raise TypeError(f"Contravariance: Handler {handler_type.__name__} tidak bisa menangani target {target_type.__name__}")
        self.target_type = target_type
        self.handler_type = handler_type
        self.handler = handler

    def process(self, item: Any) -> None:
        self.handler(item)


def demo_variance() -> None:
    print_header("1. Variance Annotations ([T], [+T], [-T])")
    
    # Invariance Test
    print(f"\n{Color.BOLD}A. Invariance Box[Dog]{Color.RESET}")
    try:
        box_dog = InvariantContainer(Dog, Dog())
        print_success("InvariantContainer(Dog, Dog()) valid.")
    except TypeError as e:
        print_type_error("Dog", "Unknown", str(e))

    try:
        print_info("Uji Coba", "Memasukkan Puppy ke Box[Dog] yang bersifat invariant...")
        # Di Scala Invariant, Box[Puppy] BUKAN subtype dari Box[Dog]
        box_invalid = InvariantContainer(Dog, Puppy())
        print_success("InvariantContainer menerima Puppy (Salah jika invariant murni)!")
    except TypeError as e:
        print_type_error("Dog (Exact Type)", "Puppy", str(e))

    # Covariance Test
    print(f"\n{Color.BOLD}B. Covariance List[+Animal]{Color.RESET}")
    print_info("Konsep", "Jika Dog <: Animal, maka List[Dog] <: List[Animal]")
    try:
        dogs = [Dog(), Puppy()]
        co_list = CovariantList(Animal, dogs)
        print_success("CovariantList[Animal] berhasil menampung [Dog, Puppy]!")
    except TypeError as e:
        print_type_error("Animal or Subtypes", "Invalid Item", str(e))

    # Contravariance Test
    print(f"\n{Color.BOLD}C. Contravariance Consumer[-Dog]{Color.RESET}")
    print_info("Konsep", "Jika Dog <: Animal, maka Consumer[Animal] <: Consumer[Dog]")
    def animal_doctor(a: Animal) -> None:
        print_info("Vaksinasi", f"Memvaksin hewan jenis {type(a).__name__}: {a.sound()}")

    try:
        # Handler untuk Animal sah dipakai sebagai Consumer untuk Dog
        dog_consumer = ContravariantConsumer(Dog, Animal, animal_doctor)
        dog_consumer.process(Dog())
        print_success("ContravariantConsumer berhasil mengadopsi Handler Animal untuk Dog!")
    except TypeError as e:
        print_type_error("Supertype of Dog (e.g. Animal)", "Invalid", str(e))


# ============================================================================
# 3. Simulation: Upper & Lower Type Bounds ([T <: Upper], [T >: Lower])
# ============================================================================
def rescue_animal(target: Any, bound: type = Animal) -> None:
    """Scala: def rescue[T <: Animal](target: T): Unit"""
    if not issubclass(type(target), bound):
        raise TypeError(f"Upper Bound Violation: {type(target).__name__} tidak memenuhi boundary <: {bound.__name__}")
    print_success(f"Rescue berhasil untuk {type(target).__name__} (Upper bound <: {bound.__name__})")

def append_to_dog_list(existing_type: type, new_type: type, lower_bound: type = Dog) -> type:
    """Scala: def append[B >: Dog](elem: B): List[B]"""
    # Lower bound: Tipe baru harus berupa superclass dari Dog atau Dog itu sendiri
    if not issubclass(lower_bound, new_type):
        raise TypeError(f"Lower Bound Violation: {new_type.__name__} bukan supertype dari {lower_bound.__name__} (>: {lower_bound.__name__})")
    print_success(f"Type widened secara aman ke: {new_type.__name__} (Memenuhi >: {lower_bound.__name__})")
    return new_type


def demo_type_bounds() -> None:
    print_header("2. Type Bounds (<: Upper Bound & >: Lower Bound)")
    
    print(f"\n{Color.BOLD}A. Upper Bound (T <: Animal){Color.RESET}")
    rescue_animal(Dog())
    rescue_animal(Cat())
    
    class Robot:
        pass
        
    try:
        print_info("Uji Coba", "Memanggil rescue_animal dengan Robot (bukan Animal)...")
        rescue_animal(Robot())
    except TypeError as e:
        print_type_error("T <: Animal", "Robot", str(e))

    print(f"\n{Color.BOLD}B. Lower Bound (B >: Dog){Color.RESET}")
    print_info("Konsep", "Menambahkan supertype Animal ke koleksi Dog me-widen type menjadi Animal")
    append_to_dog_list(Dog, Animal)
    
    try:
        print_info("Uji Coba", "Mencoba lower bound dengan Puppy (>: Dog gagal karena Puppy adalah subtype)...")
        append_to_dog_list(Dog, Puppy)
    except TypeError as e:
        print_type_error("B >: Dog (Supertype)", "Puppy (Subtype)", str(e))


# ============================================================================
# 4. Simulation: Path-Dependent Types
# ============================================================================
class Network:
    """
    Scala:
    class Network(val name: String) {
      class Member(val username: String)
      def connect(p1: Member, p2: Member): Unit
    }
    """
    def __init__(self, name: str):
        self.name = name

    class Member:
        def __init__(self, network: 'Network', username: str):
            self.network = network
            self.username = username

        def __repr__(self) -> str:
            return f"Member({self.username} @ {self.network.name})"

    def create_member(self, username: str) -> 'Network.Member':
        return Network.Member(self, username)

    def connect(self, p1: 'Network.Member', p2: 'Network.Member') -> None:
        if p1.network is not self or p2.network is not self:
            raise TypeError(
                f"Path-Dependent Type Mismatch: Anggota harus berasal dari path '{self.name}'. "
                f"Ditemukan {p1} atau {p2} dari network berbeda!"
            )
        print_success(f"Terhubung dalam {self.name}: {p1.username} <---> {p2.username}")


def demo_path_dependent_types() -> None:
    print_header("3. Path-Dependent Types (instance.Type)")
    net_alpha = Network("AlphaNet")
    net_beta = Network("BetaNet")

    alice = net_alpha.create_member("Alice")
    bob = net_alpha.create_member("Bob")
    charlie = net_beta.create_member("Charlie")

    print_info("Konteks", f"Alice & Bob di AlphaNet, Charlie di BetaNet")
    net_alpha.connect(alice, bob)

    try:
        print_info("Uji Coba", "Mengkoneksikan Alice (AlphaNet) dengan Charlie (BetaNet) di AlphaNet...")
        net_alpha.connect(alice, charlie)
    except TypeError as e:
        print_type_error("net_alpha.Member", "net_beta.Member", str(e))


# ============================================================================
# 5. Simulation: Self-Type Annotation
# ============================================================================
class DatabaseConnection:
    def execute_query(self, sql: str) -> str:
        return f"OK: Executed '{sql}'"

class UserRepository:
    """
    Scala:
    trait UserRepository {
      this: DatabaseConnection =>
      def findUser(id: Long) = execute_query(s"SELECT * FROM users WHERE id=$id")
    }
    """
    def __init__(self, host_instance: Any):
        # Memastikan host mengimplementasikan kontrak DatabaseConnection
        if not isinstance(host_instance, DatabaseConnection):
            raise TypeError(
                f"Self-Type Violation: UserRepository membutuhkan implementasi 'DatabaseConnection'. "
                f"Kelas '{type(host_instance).__name__}' tidak memenuhi self-type!"
            )
        self._db = host_instance

    def find_user(self, user_id: int) -> str:
        return self._db.execute_query(f"SELECT * FROM users WHERE id = {user_id}")


class ValidUserService(DatabaseConnection):
    def __init__(self):
        self.repo = UserRepository(self)

class InvalidUserService:
    def __init__(self):
        self.repo = UserRepository(self)


def demo_self_type() -> None:
    print_header("4. Self-Type Annotations (this: Dependency =>)")
    try:
        service = ValidUserService()
        res = service.repo.find_user(42)
        print_success(f"ValidUserService memenuhi self-type DatabaseConnection: {res}")
    except TypeError as e:
        print_type_error("DatabaseConnection", "Unknown", str(e))

    try:
        print_info("Uji Coba", "Instansiasi InvalidUserService tanpa inheritance DatabaseConnection...")
        bad_service = InvalidUserService()
    except TypeError as e:
        print_type_error("this: DatabaseConnection", "InvalidUserService", str(e))


# ============================================================================
# 6. Simulation: Phantom Types (Type-Safe State Machine)
# ============================================================================
# Scala:
# sealed trait Status
# trait Draft extends Status
# trait Approved extends Status
# trait Published extends Status
# class Document[S <: Status] private (...)

class DraftState: pass
class ApprovedState: pass
class PublishedState: pass

class Document(Generic[TypeVar('S')]):
    def __init__(self, title: str, state_type: type = DraftState):
        self.title = title
        self._state_type = state_type

    @classmethod
    def create(cls, title: str) -> 'Document[DraftState]':
        print_info("Draft Created", f"Dokumen '{title}' berstatus [Draft]")
        return Document(title, DraftState)

    def approve(self) -> 'Document[ApprovedState]':
        if self._state_type is not DraftState:
            raise TypeError(f"Invalid Transition: Hanya Document[Draft] yang bisa di-approve!")
        print_success(f"Dokumen '{self.title}' beralih status -> [Approved]")
        return Document(self.title, ApprovedState)

    def publish(self) -> 'Document[PublishedState]':
        if self._state_type is not ApprovedState:
            raise TypeError(
                f"Phantom Type Guard: Hanya Document[Approved] yang bisa dipublish! "
                f"Status saat ini adalah [{self._state_type.__name__}]"
            )
        print_success(f"Dokumen '{self.title}' beralih status -> [Published]")
        return Document(self.title, PublishedState)


def demo_phantom_types() -> None:
    print_header("5. Phantom Types (Compile-Time State Verification)")
    doc = Document.create("Scala 3 Type System Specs")
    
    # Transisi Legal: Draft -> Approved -> Published
    approved_doc = doc.approve()
    published_doc = approved_doc.publish()
    
    # Transisi Ilegal: Draft langsung publish tanpa approve
    print_info("Uji Coba", "Mencoba publish langsung dari draft (melewati approval)...")
    try:
        illegal_doc = Document.create("Bypass Security Doc")
        illegal_doc.publish()
    except TypeError as e:
        print_type_error("Document[ApprovedState]", "Document[DraftState]", str(e))


# ============================================================================
# Main Interactive Runner
# ============================================================================
def run_all() -> None:
    demo_variance()
    demo_type_bounds()
    demo_path_dependent_types()
    demo_self_type()
    demo_phantom_types()
    
    print(f"\n{Color.BOLD}{Color.GREEN}{'=' * 65}")
    print(f"  SELURUH SIMULASI SISTEM PENGETIKAN SCALA SELESAI DENGAN SUKSES!")
    print(f"{'=' * 65}{Color.RESET}\n")

def interactive_menu() -> None:
    while True:
        print(f"\n{Color.BOLD}{Color.MAGENTA}=== MENU LABORATORIUM SISTEM PENGETIKAN SCALA (BAB-05) ==={Color.RESET}")
        print("1. Jalankan Simulasi 1: Variance ([T], [+T], [-T])")
        print("2. Jalankan Simulasi 2: Type Bounds (<: Upper, >: Lower)")
        print("3. Jalankan Simulasi 3: Path-Dependent Types (outer.Inner)")
        print("4. Jalankan Simulasi 4: Self-Type Annotations (this: Dependency =>)")
        print("5. Jalankan Simulasi 5: Phantom Types (Type-Safe Builder State)")
        print("6. Jalankan Semua Simulasi Sekaligus")
        print("0. Keluar")
        choice = input(f"{Color.CYAN}Pilih opsi (0-6): {Color.RESET}").strip()

        if choice == '1':
            demo_variance()
        elif choice == '2':
            demo_type_bounds()
        elif choice == '3':
            demo_path_dependent_types()
        elif choice == '4':
            demo_self_type()
        elif choice == '5':
            demo_phantom_types()
        elif choice == '6':
            run_all()
        elif choice == '0':
            print(f"{Color.YELLOW}Keluar dari lab. Sampai jumpa!{Color.RESET}")
            break
        else:
            print(f"{Color.RED}Pilihan tidak valid. Silakan coba lagi.{Color.RESET}")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ("--all", "-a", "--batch"):
        run_all()
    elif not sys.stdin.isatty():
        # Running in headless / automated pipe mode
        run_all()
    else:
        interactive_menu()
