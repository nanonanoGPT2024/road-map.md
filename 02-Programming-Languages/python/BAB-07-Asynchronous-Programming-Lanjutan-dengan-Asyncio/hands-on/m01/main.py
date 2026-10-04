import asyncio
import logging
import random
import signal
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] (%(task_name)s) %(message)s",
)


class TaskNameFilter(logging.Filter):
    """Menyuntikkan ID/Nama Task asyncio ke dalam record log."""
    def filter(self, record: logging.LogRecord) -> bool:
        task = asyncio.current_task()
        record.task_name = task.get_name() if task else "MainEngine"
        return True


# Pasang filter logging
for handler in logging.root.handlers:
    handler.addFilter(TaskNameFilter())

logger = logging.getLogger("WebhookDispatcher")


@dataclass(frozen=True)
class WebhookPayload:
    event_id: str
    target_url: str
    payload_data: dict
    retries_left: int = 3
    base_delay_seconds: float = 0.5


class CircuitBreakerOpenException(Exception):
    """Dilempar ketika circuit breaker mendeteksi downstream offline."""
    pass


class AsyncCircuitBreaker:
    """Circuit Breaker untuk memproteksi downstream system yang tidak sehat."""
    def __init__(self, failure_threshold: int = 5, recovery_timeout: float = 5.0) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.state = "CLOSED"  # CLOSED, OPEN, HALF-OPEN
        self.last_state_change = asyncio.get_event_loop().time()
        self._lock = asyncio.Lock()

    async def can_execute(self) -> bool:
        async with self._lock:
            now = asyncio.get_event_loop().time()
            if self.state == "OPEN":
                if now - self.last_state_change > self.recovery_timeout:
                    self.state = "HALF-OPEN"
                    logger.warning("Circuit beralih ke HALF-OPEN. Menguji koneksi downstream.")
                    return True
                return False
            return True

    async def record_success(self) -> None:
        async with self._lock:
            self.failure_count = 0
            self.state = "CLOSED"

    async def record_failure(self) -> None:
        async with self._lock:
            self.failure_count += 1
            if self.failure_count >= self.failure_threshold:
                self.state = "OPEN"
                self.last_state_change = asyncio.get_event_loop().time()
                logger.error(f"Circuit tripped ke status OPEN! downstream failure >= {self.failure_threshold}")


class ResilientDispatcher:
    def __init__(self, concurrency_limit: int, max_queue_size: int) -> None:
        self.queue: asyncio.Queue[WebhookPayload] = asyncio.Queue(maxsize=max_queue_size)
        self.semaphore = asyncio.Semaphore(concurrency_limit)
        self.circuit_breaker = AsyncCircuitBreaker()
        self._shutdown_event = asyncio.Event()

    async def mock_http_post(self, target_url: str, data: dict) -> int:
        """Simulasi HTTP I/O non-blocking dengan potensi kegagalan jaringan."""
        await asyncio.sleep(random.uniform(0.05, 0.2))  # Latensi jaringan
        # Simulasi 15% downstream outage
        if random.random() < 0.15:
            raise ConnectionError("503 Service Unavailable: Remote Host Down")
        return 200

    async def _send_with_retry(self, item: WebhookPayload) -> None:
        """Worker execution unit dengan Exponential Backoff + Jitter."""
        async with self.semaphore:
            if not await self.circuit_breaker.can_execute():
                logger.warning(f"Dropping event {item.event_id}: Circuit breaker OPEN")
                return

            current_retry = 0
            while current_retry <= item.retries_left:
                try:
                    # Terapkan timeout per request individu secara eksplisit
                    async with asyncio.timeout(0.5):
                        status = await self.mock_http_post(item.target_url, item.payload_data)
                        if status == 200:
                            await self.circuit_breaker.record_success()
                            logger.info(f"Delivered event {item.event_id} successfully.")
                            return

                except (ConnectionError, TimeoutError) as exc:
                    current_retry += 1
                    await self.circuit_breaker.record_failure()
                    if current_retry > item.retries_left:
                        logger.error(f"Failed to deliver event {item.event_id} after {item.retries_left} retries: {exc}")
                        return
                    
                    # Full Jitter Exponential Backoff Calculation
                    backoff = item.base_delay_seconds * (2 ** (current_retry - 1))
                    jittered_delay = random.uniform(0, backoff)
                    logger.warning(f"Retry {current_retry} for event {item.event_id} sleeping for {jittered_delay:.2f}s")
                    await asyncio.sleep(jittered_delay)

    async def worker(self, worker_id: int) -> None:
        """Loop internal worker task."""
        while not self._shutdown_event.is_set() or not self.queue.empty():
            try:
                # Menggunakan timeout pendek agar worker secara berkala mengecek shutdown flag
                async with asyncio.timeout(0.2):
                    item = await self.queue.get()
            except TimeoutError:
                continue

            try:
                await self._send_with_retry(item)
            finally:
                self.queue.task_done()
        
        logger.info(f"Worker-{worker_id} safely exited.")

    async def enqueue_webhook(self, payload: WebhookPayload) -> bool:
        """Pintu masuk pengiriman payload dengan mekanisme non-blocking backpressure."""
        try:
            self.queue.put_nowait(payload)
            return True
        except asyncio.QueueFull:
            logger.error(f"Backpressure triggered! Queue overflow, rejecting event: {payload.event_id}")
            return False

    async def shutdown(self) -> None:
        """Graceful shutdown protocol."""
        logger.warning("Shutdown sequence diinisiasi...")
        self._shutdown_event.set()
        await self.queue.join()
        logger.info("Seluruh sisa antrean antrean berhasil diproses.")


async def main() -> None:
    dispatcher = ResilientDispatcher(concurrency_limit=10, max_queue_size=100)
    loop = asyncio.get_running_loop()

    # Setup penanganan sinyal shutdown POSIX secara asinkron
    def handle_signal():
        asyncio.create_task(dispatcher.shutdown())

    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, handle_signal)
        except NotImplementedError:
            # Fallback untuk platform tanpa dukungan sinyal penuh (seperti standard Windows IOCP loop)
            pass

    async with asyncio.TaskGroup() as tg:
        # Spawn Consumer Worker Pool
        workers = [
            tg.create_task(dispatcher.worker(i), name=f"Worker-{i}")
            for i in range(5)
        ]

        # Enqueue sample webhooks
        for i in range(25):
            payload = WebhookPayload(
                event_id=f"evt_{i:04d}",
                target_url="https://api.partner.com/webhook",
                payload_data={"transaction_id": 1000 + i, "amount": random.randint(10, 500)},
            )
            enqueued = await dispatcher.enqueue_webhook(payload)
            if not enqueued:
                break
            await asyncio.sleep(0.01)

        # Memicu shutdown otomatis untuk keperluan demonstrasi
        await dispatcher.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
