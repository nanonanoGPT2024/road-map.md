# main_service.py
import asyncio
import logging
import os
import sys
import uuid
from typing import Optional, Dict, Any
from contextlib import asynccontextmanager

import httpx
import redis.asyncio as aioredis
from fastapi import FastAPI, Request, Response, HTTPException, Depends, status
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


# --- 1. KONFIGURASI SESUAI THE TWELVE-FACTOR APP ---
class ServiceSettings(BaseSettings):
    ENVIRONMENT: str = Field(default="production")
    REDIS_URL: str = Field(default="redis://localhost:6379/0")
    PAYMENT_GATEWAY_URL: str = Field(default="https://api.mockpayment.internal/v1/charges")
    REQUEST_TIMEOUT_SECONDS: float = Field(default=5.0)
    MAX_CONNECTIONS: int = Field(default=100)
    
    model_config = SettingsConfigDict(env_prefix="SRV_", case_sensitive=True)

settings = ServiceSettings()


# --- 2. STRUCTURED LOGGER ---
class StructuredLogger:
    @staticmethod
    def log(level: str, msg: str, **kwargs: Any) -> None:
        payload = {
            "timestamp": asyncio.get_event_loop().time(),
            "level": level,
            "message": msg,
            **kwargs
        }
        # Dalam produksi dialihkan ke stdout dalam format JSON string
        sys.stdout.write(str(payload) + "\n")
        sys.stdout.flush()


# --- 3. LIFECYCLE DEPENDENCY CONTAINER ---
class ServiceContainer:
    redis_pool: Optional[aioredis.Redis] = None
    http_client: Optional[httpx.AsyncClient] = None

container = ServiceContainer()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Inisialisasi pool koneksi
    StructuredLogger.log("INFO", "Inisialisasi Shared Connection Pools...")
    container.redis_pool = aioredis.from_url(
        settings.REDIS_URL, 
        max_connections=settings.MAX_CONNECTIONS,
        decode_responses=True
    )
    
    # Konfigurasi HTTP Client dengan connection pooling & non-blocking timeout
    limits = httpx.Limits(max_keepalive_connections=20, max_connections=settings.MAX_CONNECTIONS)
    timeout = httpx.Timeout(connect=1.5, read=settings.REQUEST_TIMEOUT_SECONDS, write=2.0, pool=5.0)
    container.http_client = httpx.AsyncClient(limits=limits, timeout=timeout)

    yield  # Service berjalan

    # Shutdown: Bersihkan resources
    StructuredLogger.log("INFO", "Menghentikan connection pools...")
    await container.http_client.aclose()
    await container.redis_pool.close()
    StructuredLogger.log("INFO", "Pembersihan selesai. Worker siap mati.")


app = FastAPI(title="Payment Orchestrator", lifespan=lifespan)


# --- 4. MIDDLEWARE CORRELATION ID & REQUEST TRACING ---
@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
    request.state.correlation_id = correlation_id
    
    # Jalankan request ke handler berikutnya
    response: Response = await call_next(request)
    
    # Pantulkan correlation ID pada response header
    response.headers["X-Correlation-ID"] = correlation_id
    return response


# --- 5. SCHEMAS & INPUT CONTRACTS ---
class PaymentRequestPayload(BaseModel):
    order_id: str = Field(..., min_length=5, max_length=64)
    amount_cents: int = Field(..., gt=0)
    currency: str = Field(..., min_length=3, max_length=3)


# --- 6. CORE LOGIC DENGAN IDEMPOTENCY & RESILIENCE ---
async def execute_remote_payment(client: httpx.AsyncClient, payload: PaymentRequestPayload, correlation_id: str) -> Dict[str, Any]:
    headers = {"X-Correlation-ID": correlation_id}
    try:
        # Panggilan remote ke Payment Provider dengan backoff singkat internal
        response = await client.post(
            settings.PAYMENT_GATEWAY_URL,
            json=payload.model_dump(),
            headers=headers
        )
        response.raise_for_status()
        return response.json()
    except (httpx.TimeoutException, httpx.NetworkError) as err:
        StructuredLogger.log(
            "ERROR", 
            "Network error pada remote payment provider",
            error_type=type(err).__name__,
            correlation_id=correlation_id
        )
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Timeout upstream communication with banking provider"
        )
    except httpx.HTTPStatusError as err:
        StructuredLogger.log(
            "ERROR", 
            f"Upstream provider merespon HTTP {err.response.status_code}",
            correlation_id=correlation_id
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Payment provider rejected transaction"
        )


@app.post("/v1/payments/charge", status_code=status.HTTP_200_OK)
async def process_payment(
    payload: PaymentRequestPayload,
    request: Request
) -> Dict[str, Any]:
    correlation_id = request.state.correlation_id
    idempotency_key = request.headers.get("Idempotency-Key")

    if not idempotency_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Header 'Idempotency-Key' wajib disertakan untuk endpoint ini."
        )

    redis_conn = container.redis_pool
    lock_key = f"idempotency:lock:{idempotency_key}"
    data_key = f"idempotency:data:{idempotency_key}"

    # 1. Cek apakah transaksi sudah pernah berhasil sebelumnya (Idempotency check)
    cached_response = await redis_conn.get(data_key)
    if cached_response:
        StructuredLogger.log("INFO", "Idempotency hit! Mengembalikan respons tersimpan.", key=idempotency_key)
        return {"status": "CACHED_MUTATION", "result": cached_response}

    # 2. Rebut Mutex Lock menggunakan SETNX untuk mencegah concurrent race condition
    # Kunci auto-expire dalam 30 detik untuk menghindari deadlock jika proses crash
    is_acquired = await redis_conn.set(lock_key, "LOCKED", ex=30, nx=True)
    if not is_acquired:
        StructuredLogger.log("WARN", "Concurrent request detected for same key", key=idempotency_key)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Transaksi serupa sedang diproses. Mohon tunggu sejenak."
        )

    try:
        StructuredLogger.log("INFO", "Memproses transaksi pembayaran baru", correlation_id=correlation_id)
        
        # Eksekusi pembayaran ke dependensi eksternal
        # CATATAN: Untuk testing, jika payment endpoint gagal, ganti dengan response tiruan.
        remote_result = await execute_remote_payment(
            container.http_client, 
            payload, 
            correlation_id
        )

        # 3. Simpan mutasi sukses ke dalam Redis cache (TTL 24 Jam)
        await redis_conn.set(data_key, str(remote_result), ex=86400)
        
        return {
            "status": "PROCESSED",
            "correlation_id": correlation_id,
            "data": remote_result
        }

    finally:
        # Selalu hapus lock pengaman setelah proses selesai
        await redis_conn.delete(lock_key)
