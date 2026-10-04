#!/usr/bin/env python3
"""
asg_lifecycle_simulation.py
Simulasi Pemrosesan Graceful Shutdown dan ASG Lifecycle Hook Handler.

Skrip ini mendemonstrasikan bagaimana aplikasi produksi di AWS EC2
merespons sinyal terminasi (baik dari Auto Scaling Lifecycle Hook maupun
EC2 Spot Interruption Warning) dengan melakukan graceful connection draining
dan menyelesaikan aksi siklus hidup (CompleteLifecycleAction).

Dapat dijalankan secara lokal (mock mode) atau di atas EC2 Instance nyata.
"""

import os
import sys
import time
import signal
import logging
import urllib.request
import urllib.error
import json
from datetime import datetime

# Setup logging berstandar produksi
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] [%(process)d] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("ASGLifecycleHandler")

# Flag kontrol graceful shutdown
SHUTDOWN_REQUESTED = False

def sigterm_handler(signum, frame):
    """Menangkap POSIX signal SIGTERM dari OS atau systemd."""
    global SHUTDOWN_REQUESTED
    logger.warning(f"Sinyal POSIX diterima (Signal: {signum}). Menandai status graceful shutdown...")
    SHUTDOWN_REQUESTED = True

# Daftarkan signal handler
signal.signal(signal.SIGTERM, sigterm_handler)
signal.signal(signal.SIGINT, sigterm_handler)

def get_imds_v2_token():
    """Mengambil token autentikasi IMDSv2."""
    url = "http://169.254.169.254/latest/api/token"
    headers = {"X-aws-ec2-metadata-token-ttl-seconds": "60"}
    req = urllib.request.Request(url, headers=headers, method="PUT")
    try:
        with urllib.request.urlopen(req, timeout=2) as resp:
            return resp.read().decode('utf-8')
    except (urllib.error.URLError, TimeoutError):
        return None

def check_spot_interruption(token):
    """Mengecek apakah ada notifikasi interupsi Spot 2 menit di IMDS."""
    if not token:
        return False
    url = "http://169.254.169.254/latest/meta-data/spot/instance-action"
    headers = {"X-aws-ec2-metadata-token": token}
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=2) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode('utf-8'))
                logger.critical(f"SPOT INTERRUPTION DETECTED! Action details: {data}")
                return True
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return False # Tidak ada interupsi
    except Exception:
        return False
    return False

def complete_lifecycle_action(asg_name, hook_name, instance_id, result="CONTINUE"):
    """
    Mengirimkan sinyal CompleteLifecycleAction ke AWS Auto Scaling API.
    Memerlukan library boto3 dan IAM Role yang sesuai jika di production.
    """
    logger.info(f"Mengirim CompleteLifecycleAction: Result={result} untuk Instance={instance_id}...")
    try:
        import boto3
        client = boto3.client('autoscaling')
        response = client.complete_lifecycle_action(
            LifecycleHookName=hook_name,
            AutoScalingGroupName=asg_name,
            LifecycleActionResult=result,
            InstanceId=instance_id
        )
        logger.info(f"Berhasil merespons ASG Hook. Response: {response.get('ResponseMetadata', {}).get('HTTPStatusCode')}")
        return True
    except ImportError:
        logger.warning("[MOCK MODE] AWS SDK (boto3) tidak terinstall. Menjalankan simulasi API call.")
        time.sleep(1)
        logger.info(f"[MOCK SUCCESS] Lifecycle action {result} tersimulasikan.")
        return True
    except Exception as e:
        logger.error(f"Gagal menyelesaikan lifecycle action: {str(e)}")
        return False

def drain_connections(active_tasks_count=5):
    """
    Mensimulasikan proses graceful connection draining:
    1. Berhenti menerima request baru.
    2. Menyelesaikan request / batch jobs yang sedang berjalan (in-flight).
    3. Menutup koneksi database pool.
    """
    logger.info("--- MEMULAI PROSES CONNECTION DRAINING ---")
    logger.info("Status Listener: CLOSED (Tolak koneksi baru / Deregister target dari ALB)")
    
    current_tasks = active_tasks_count
    while current_tasks > 0:
        logger.info(f"Draining: Menyelesaikan {current_tasks} active in-flight request(s)...")
        time.sleep(2) # Simulasi pemrosesan
        current_tasks -= 1
        
    logger.info("Semua in-flight request telah selesai dengan kode status 200 OK.")
    logger.info("Menutup koneksi connection pool database & flushing local buffer metrics...")
    time.sleep(1)
    logger.info("--- CONNECTION DRAINING SELESAI DENGAN SUKSES ---")

def main():
    logger.info("=== Memulai Daemon Microservice Worker ===")
    
    # Ambil metadata instans atau gunakan nilai mock jika dijalankan di lokal
    token = get_imds_v2_token()
    if token:
        logger.info("Terhubung dengan IMDSv2 fisik AWS.")
    else:
        logger.info("Berjalan dalam LOCAL/MOCK environment (IMDS tidak terdeteksi).")

    asg_name = os.getenv("ASG_NAME", "production-backend-asg")
    hook_name = os.getenv("HOOK_NAME", "graceful-shutdown-hook")
    instance_id = os.getenv("INSTANCE_ID", "i-mock0123456789abcdef0")

    loop_count = 0
    try:
        while not SHUTDOWN_REQUESTED:
            loop_count += 1
            logger.info(f"[Heartbeat] Worker aktif beroperasi. Memproses antrean pesan... (Cycle: {loop_count})")
            
            # Cek Interupsi Spot jika berjalan di AWS
            if token and check_spot_interruption(token):
                logger.warning("Memicu graceful shutdown akibat Spot Interruption Notice!")
                break
                
            # Simulasi interupsi manual di lokal setelah 5 siklus jika tidak ada interupsi eksternal
            if not token and loop_count >= 5:
                logger.info("[Simulasi Lokal] Memicu shutdown simulasi otomatis setelah 5 siklus...")
                break

            time.sleep(3)
            
    except KeyboardInterrupt:
        logger.info("Interupsi keyboard (CTRL+C) diterima.")

    # Eksekusi Graceful Draining
    drain_connections(active_tasks_count=3)

    # Kirim sinyal ke AWS Auto Scaling Lifecycle Hook
    complete_lifecycle_action(asg_name, hook_name, instance_id, result="CONTINUE")
    
    logger.info("Proses shutdown aplikasi selesai secara elegan. Sistem siap dihentikan.")
    sys.exit(0)

if __name__ == "__main__":
    main()