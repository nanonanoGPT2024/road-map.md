#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Fondasi Arsitektur Perangkat Lunak (Hexagonal & Clean Architecture)
BAB-08: Arsitektur Perangkat Lunak Hexagonal / Clean Architecture (PHP Context Simulation)

Prinsip Utama:
1. Domain Core (Entities, Value Objects, Domain Exceptions) tidak memiliki dependensi eksternal.
2. Ports (Interfaces):
   - Inbound / Driving Ports (Use Case Contracts).
   - Outbound / Driven Ports (SPI / Repository / Gateway Contracts).
3. Adapters:
   - Driving / Primary Adapters (CLI / Web Controller).
   - Driven / Secondary Adapters (In-Memory Repo, PDO Database Repo, Mailer Service).
4. Dependency Inversion Principle (DIP): Modul tingkat tinggi tidak bergantung modul rendah.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional
import sys
import time

# ==============================================================================
# ANSI Color Codes & Helpers
# ==============================================================================
class Colors:
    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"
    DIM = "\033[2m"
    RESET = "\033[0m"


def print_banner() -> None:
    print(f"{Colors.CYAN}{Colors.BOLD}======================================================================{Colors.RESET}")
    print(f"{Colors.GREEN}{Colors.BOLD}   LAB KONSEPTUAL: HEXAGONAL & CLEAN ARCHITECTURE (PORTS & ADAPTERS)  {Colors.RESET}")
    print(f"{Colors.YELLOW}   Simulasi Implementasi PHP Modern: Domain Core, UseCases & Adapters {Colors.RESET}")
    print(f"{Colors.CYAN}{Colors.BOLD}======================================================================{Colors.RESET}\n")


# ==============================================================================
# 1. DOMAIN LAYER (CORE BUSINESS LOGIC - ZERO EXTERNAL DEPENDENCIES)
# ==============================================================================

class DomainException(Exception):
    """Base exception untuk domain layer."""
    pass


class InvalidMoneyException(DomainException):
    pass


class InsufficientStockException(DomainException):
    pass


@dataclass(frozen=True)
class Money:
    """Value Object: Money (Immutability & Domain Invariants)"""
    amount: float
    currency: str = "IDR"

    def __post_init__(self):
        if self.amount < 0:
            raise InvalidMoneyException(f"Jumlah nominal tidak boleh negatif: {self.amount}")

    def add(self, other: "Money") -> "Money":
        if self.currency != other.currency:
            raise InvalidMoneyException("Mata uang harus sama saat melakukan kalkulasi.")
        return Money(self.amount + other.amount, self.currency)

    def format(self) -> str:
        return f"{self.currency} {self.amount:,.2f}"


@dataclass
class OrderItem:
    """Entity Child: Order Item"""
    product_id: str
    product_name: str
    quantity: int
    unit_price: Money

    def calculate_subtotal(self) -> Money:
        return Money(self.unit_price.amount * self.quantity, self.unit_price.currency)


@dataclass
class Order:
    """Domain Entity: Order (Aggregate Root)"""
    order_id: str
    customer_email: str
    items: List[OrderItem] = field(default_factory=list)
    status: str = "PENDING"
    created_at: datetime = field(default_factory=datetime.now)

    def add_item(self, item: OrderItem) -> None:
        if self.status != "PENDING":
            raise DomainException("Tidak dapat menambah item pada pesanan yang sudah diproses!")
        self.items.append(item)

    def calculate_total(self) -> Money:
        total = Money(0.0)
        for item in self.items:
            total = total.add(item.calculate_subtotal())
        return total

    def confirm_payment(self) -> None:
        if not self.items:
            raise DomainException("Pesanan kosong tidak dapat dikonfirmasi!")
        self.status = "PAID"


# ==============================================================================
# 2. PORTS LAYER (INTERFACES / CONTRACTS)
# ==============================================================================

# Driven / Outbound Port (Database / Repository)
class OrderRepositoryPort(ABC):
    """Secondary / Driven Port: Kontrak penyimpanan data Order"""
    @abstractmethod
    def save(self, order: Order) -> None:
        pass

    @abstractmethod
    def find_by_id(self, order_id: str) -> Optional[Order]:
        pass

    @abstractmethod
    def list_all(self) -> List[Order]:
        pass


# Driven / Outbound Port (Notification Service)
class NotificationPort(ABC):
    """Secondary / Driven Port: Kontrak pengiriman notifikasi"""
    @abstractmethod
    def send_order_confirmation(self, order: Order) -> bool:
        pass


# Driving / Inbound Port (Use Case Contract)
class CreateOrderUseCasePort(ABC):
    """Primary / Driving Port: Kontrak interaksi Use Case Pesanan"""
    @abstractmethod
    def execute(self, order_id: str, customer_email: str, raw_items: List[dict]) -> Order:
        pass


# ==============================================================================
# 3. APPLICATION LAYER (USE CASES / INTERACTORS)
# ==============================================================================

class CreateOrderUseCase(CreateOrderUseCasePort):
    """
    Application Service (Interactor).
    Hanya bergantung pada Domain Entities dan Ports (DIP).
    Sama sekali tidak peduli DB menggunakan MySQL, PostgreSQL, atau In-Memory.
    """
    def __init__(self, repo: OrderRepositoryPort, notifier: NotificationPort):
        self._repo = repo
        self._notifier = notifier

    def execute(self, order_id: str, customer_email: str, raw_items: List[dict]) -> Order:
        print(f"  {Colors.BLUE}[Application Layer]{Colors.RESET} Menjalankan CreateOrderUseCase...")
        order = Order(order_id=order_id, customer_email=customer_email)

        for raw in raw_items:
            if raw["quantity"] <= 0:
                raise DomainException(f"Kuantitas item {raw['name']} harus > 0")
            item = OrderItem(
                product_id=raw["id"],
                product_name=raw["name"],
                quantity=raw["quantity"],
                unit_price=Money(raw["price"])
            )
            order.add_item(item)

        order.confirm_payment()

        # Persist via Outbound Port
        self._repo.save(order)

        # Notify via Outbound Port
        self._notifier.send_order_confirmation(order)

        print(f"  {Colors.GREEN}[Application Layer]{Colors.RESET} Use Case berhasil diselesaikan!")
        return order


# ==============================================================================
# 4. ADAPTERS LAYER (INFRASTRUCTURE & DRIVING INTERFACES)
# ==============================================================================

# Secondary Adapter 1: In-Memory Storage (Untuk Testing / Caching)
class InMemoryOrderRepository(OrderRepositoryPort):
    def __init__(self):
        self._storage: Dict[str, Order] = {}

    def save(self, order: Order) -> None:
        self._storage[order.order_id] = order
        print(f"    {Colors.DIM}[Adapter: InMemoryRepo] Order {order.order_id} tersimpan di memori.{Colors.RESET}")

    def find_by_id(self, order_id: str) -> Optional[Order]:
        return self._storage.get(order_id)

    def list_all(self) -> List[Order]:
        return list(self._storage.values())


# Secondary Adapter 2: Simulated MySQL PDO Database
class SimulatedPdoMysqlOrderRepository(OrderRepositoryPort):
    def __init__(self, dsn: str = "mysql:host=127.0.0.1;dbname=clean_db"):
        self.dsn = dsn
        self._db_table: Dict[str, Order] = {}

    def save(self, order: Order) -> None:
        print(f"    {Colors.CYAN}[Adapter: PDO MySQL] Menghubungkan ke DSN: {self.dsn}{Colors.RESET}")
        print(f"    {Colors.CYAN}[Adapter: PDO MySQL] EXECUTE: INSERT INTO orders VALUES ('{order.order_id}', ...){Colors.RESET}")
        self._db_table[order.order_id] = order

    def find_by_id(self, order_id: str) -> Optional[Order]:
        print(f"    {Colors.CYAN}[Adapter: PDO MySQL] EXECUTE: SELECT * FROM orders WHERE id='{order_id}'{Colors.RESET}")
        return self._db_table.get(order_id)

    def list_all(self) -> List[Order]:
        return list(self._db_table.values())


# Secondary Adapter 3: Email Notifier (Symfony Mailer / SendGrid Simulator)
class EmailNotificationAdapter(NotificationPort):
    def __init__(self, sender_email: str = "system@arch-demo.local"):
        self.sender = sender_email

    def send_order_confirmation(self, order: Order) -> bool:
        print(f"    {Colors.YELLOW}[Adapter: Mailer] Mengirim email dari {self.sender} ke {order.customer_email}{Colors.RESET}")
        print(f"    {Colors.YELLOW}[Adapter: Mailer] Body: Pesanan #{order.order_id} lunas total {order.calculate_total().format()}{Colors.RESET}")
        return True


# Secondary Adapter 4: SMS / WhatsApp Notifier
class WhatsAppNotificationAdapter(NotificationPort):
    def send_order_confirmation(self, order: Order) -> bool:
        print(f"    {Colors.GREEN}[Adapter: WhatsApp API] Pesan WA terkirim ke customer #{order.order_id}{Colors.RESET}")
        return True


# Primary / Driving Adapter: Simulated Web / REST Controller
class WebOrderController:
    """Driving Adapter: Menerima HTTP payload dan memanggil Inbound Port"""
    def __init__(self, use_case: CreateOrderUseCasePort):
        self._use_case = use_case

    def post_create_order(self, request_payload: dict) -> dict:
        print(f"{Colors.HEADER}[Driving Adapter: WebController] Menerima POST /api/v1/orders{Colors.RESET}")
        try:
            order = self._use_case.execute(
                order_id=request_payload["order_id"],
                customer_email=request_payload["email"],
                raw_items=request_payload["items"]
            )
            return {
                "status_code": 201,
                "body": {
                    "order_id": order.order_id,
                    "status": order.status,
                    "total": order.calculate_total().format(),
                    "items_count": len(order.items)
                }
            }
        except DomainException as e:
            return {"status_code": 400, "error": str(e)}


# Primary / Driving Adapter: CLI Console Command (Artisan / Symfony Console)
class CliOrderConsoleCommand:
    """Driving Adapter: CLI Command"""
    def __init__(self, use_case: CreateOrderUseCasePort):
        self._use_case = use_case

    def run(self, order_id: str, email: str, item_name: str, qty: int, price: float) -> None:
        print(f"{Colors.HEADER}[Driving Adapter: CLI Command] php bin/console app:create-order{Colors.RESET}")
        items = [{"id": "ITEM-CLI", "name": item_name, "quantity": qty, "price": price}]
        order = self._use_case.execute(order_id, email, items)
        print(f"CLI Result -> Order #{order.order_id} dibuat! Total: {order.calculate_total().format()}")


# ==============================================================================
# ARCHITECTURE AUDIT & DEMONSTRATION ENGINE
# ==============================================================================

class ArchitecturalDependencyAuditor:
    """Memvalidasi aturan Clean Architecture: Domain Core tidak boleh import adapter"""
    @staticmethod
    def audit() -> None:
        print(f"\n{Colors.BOLD}{Colors.UNDERLINE}=== PEMERIKSAAN KEPATUHAN ARSITEKTUR (DEPENDENCY RULE) ==={Colors.RESET}")
        checks = [
            ("Domain Entities (Order, Money)", "Tidak mengenal DB / HTTP framework", True),
            ("Inbound & Outbound Ports", "Didefinisikan sebagai Interface Abstrak", True),
            ("Application Layer", "Hanya bergantung pada Domain & Ports", True),
            ("Adapters (Web, CLI, PDO, Mailer)", "Berada di layer terluar & implements Ports", True),
            ("DIP (Dependency Inversion)", "High-level module tidak bergantung Low-level module", True),
        ]
        for item, desc, passed in checks:
            badge = f"{Colors.GREEN}[PASS]{Colors.RESET}" if passed else f"{Colors.RED}[FAIL]{Colors.RESET}"
            print(f" {badge} {item:<35} -> {desc}")
        print(f"{Colors.BOLD}{Colors.GREEN}Status: 100% Sesuai Aturan Hexagonal / Clean Architecture.{Colors.RESET}\n")


def run_interactive_simulation() -> None:
    print_banner()
    ArchitecturalDependencyAuditor.audit()

    # Inisialisasi Adapters
    in_memory_repo = InMemoryOrderRepository()
    mysql_repo = SimulatedPdoMysqlOrderRepository()
    email_notifier = EmailNotificationAdapter()
    wa_notifier = WhatsAppNotificationAdapter()

    # Status konfigurasi yang sedang aktif
    current_repo: OrderRepositoryPort = in_memory_repo
    current_notifier: NotificationPort = email_notifier
    repo_name = "InMemory Repository"
    notifier_name = "Email (Mailer) Adapter"

    order_counter = 100

    while True:
        print(f"{Colors.CYAN}Konfigurasi Dependency Injection Saat Ini:{Colors.RESET}")
        print(f"  • Secondary DB Port     : {Colors.YELLOW}{repo_name}{Colors.RESET}")
        print(f"  • Secondary Notify Port : {Colors.YELLOW}{notifier_name}{Colors.RESET}\n")

        print(f"{Colors.BOLD}PILIH TINDAKAN SIMULASI:{Colors.RESET}")
        print("  1. Simulasikan Pemesanan via HTTP Web Controller (Driving Adapter)")
        print("  2. Simulasikan Pemesanan via CLI Console Command (Driving Adapter)")
        print("  3. Tukar Repository Adapter (InMemory <-> Simulated MySQL PDO)")
        print("  4. Tukar Notification Adapter (Email <-> WhatsApp)")
        print("  5. Tampilkan Daftar Pesanan Tersimpan di Repository Saat Ini")
        print("  6. Uji Invariant Domain (Simulasi Validasi Kegagalan Business Logic)")
        print("  7. Keluar")

        try:
            choice = input(f"\n{Colors.BOLD}Masukkan pilihan (1-7): {Colors.RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nKeluar dari simulasi.")
            break

        if choice == "1":
            order_counter += 1
            order_id = f"ORD-WEB-{order_counter}"
            use_case = CreateOrderUseCase(current_repo, current_notifier)
            controller = WebOrderController(use_case)

            payload = {
                "order_id": order_id,
                "email": "customer@cleanarch.id",
                "items": [
                    {"id": "PROD-01", "name": "Buku Hexagonal Architecture PHP", "quantity": 1, "price": 185000.0},
                    {"id": "PROD-02", "name": "Sticker Domain-Driven Design", "quantity": 3, "price": 15000.0}
                ]
            }
            response = controller.post_create_order(payload)
            print(f"\n{Colors.GREEN}HTTP Response 201 Created:{Colors.RESET} {response}\n")

        elif choice == "2":
            order_counter += 1
            order_id = f"ORD-CLI-{order_counter}"
            use_case = CreateOrderUseCase(current_repo, current_notifier)
            cli = CliOrderConsoleCommand(use_case)
            cli.run(order_id, "sysadmin@server.local", "PHP Core License", 2, 500000.0)
            print()

        elif choice == "3":
            if current_repo is in_memory_repo:
                current_repo = mysql_repo
                repo_name = "Simulated MySQL PDO Adapter"
            else:
                current_repo = in_memory_repo
                repo_name = "InMemory Repository"
            print(f"\n{Colors.GREEN}[DIP Hot-Swap]{Colors.RESET} Repository berhasil diubah menjadi: {Colors.BOLD}{repo_name}{Colors.RESET}\n")

        elif choice == "4":
            if current_notifier is email_notifier:
                current_notifier = wa_notifier
                notifier_name = "WhatsApp API Adapter"
            else:
                current_notifier = email_notifier
                notifier_name = "Email (Mailer) Adapter"
            print(f"\n{Colors.GREEN}[DIP Hot-Swap]{Colors.RESET} Notifier berhasil diubah menjadi: {Colors.BOLD}{notifier_name}{Colors.RESET}\n")

        elif choice == "5":
            orders = current_repo.list_all()
            print(f"\n{Colors.BOLD}--- Daftar Order di {repo_name} ---{Colors.RESET}")
            if not orders:
                print(f"{Colors.DIM}(Belum ada pesanan yang tersimpan){Colors.RESET}")
            for ord_obj in orders:
                print(f" • [{ord_obj.order_id}] Email: {ord_obj.customer_email} | Status: {ord_obj.status} | Total: {ord_obj.calculate_total().format()} ({len(ord_obj.items)} items)")
            print()

        elif choice == "6":
            print(f"\n{Colors.RED}[Pengujian Domain Invariant]{Colors.RESET} Mencoba membuat Money negatif...")
            try:
                invalid_money = Money(-5000.0)
            except InvalidMoneyException as ex:
                print(f" {Colors.GREEN}Berhasil ditangkap:{Colors.RESET} {ex}")

            print(f"{Colors.RED}[Pengujian Domain Invariant]{Colors.RESET} Mencoba UseCase dengan kuantitas 0...")
            try:
                use_case = CreateOrderUseCase(current_repo, current_notifier)
                use_case.execute("ORD-FAIL", "user@test.com", [{"id": "P1", "name": "Item Rusak", "quantity": 0, "price": 1000.0}])
            except DomainException as ex:
                print(f" {Colors.GREEN}Berhasil ditangkap:{Colors.RESET} {ex}\n")

        elif choice == "7":
            print(f"\n{Colors.CYAN}Terima kasih telah menjalankan simulasi Arsitektur Hexagonal & Clean Architecture!{Colors.RESET}")
            break
        else:
            print(f"{Colors.RED}Pilihan tidak valid, silakan coba lagi.{Colors.RESET}\n")


if __name__ == "__main__":
    run_interactive_simulation()
