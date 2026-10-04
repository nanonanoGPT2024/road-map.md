#!/usr/bin/env python3
"""
Simulasi Pengiriman Metrik, Injeksi Anomali, dan Evaluasi Metric Math CloudWatch.
Dirancang untuk demonstrasi observabilitas dan evaluasi SLI/SLO di lingkungan AWS.

Kebutuhan Library:
    pip install boto3

Kebutuhan Hak Akses AWS (IAM):
    cloudwatch:PutMetricData
    cloudwatch:GetMetricData
    cloudwatch:PutMetricAlarm
"""

import time
import math
import random
import logging
import argparse
import sys
from datetime import datetime, timedelta, timezone
import boto3
from botocore.exceptions import ClientError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("TelemetrySimulator")


class CloudWatchObservabilitySimulator:
    def __init__(self, namespace: str, region_name: str = "ap-southeast-1"):
        self.namespace = namespace
        self.region_name = region_name
        self.cw_client = boto3.client("cloudwatch", region_name=region_name)
        logger.info(f"Menginisialisasi CloudWatch Simulator pada Region: {self.region_name} | Namespace: {self.namespace}")

    def generate_and_push_metrics(self, duration_minutes: int, inject_anomaly: bool = True):
        """
        Mengirim metrik sintetis HTTP RequestCount dan 5XX Errors ke CloudWatch.
        Mensimulasikan pola diurnal normal dan injeksi lonjakan error buatan.
        """
        logger.info(f"Memulai pengiriman metrik selama {duration_minutes} menit...")
        total_steps = duration_minutes * 6  # Interval per 10 detik
        start_time = datetime.now(timezone.utc)

        for step in range(total_steps):
            current_time = datetime.now(timezone.utc)
            step_progress = step / total_steps

            # 1. Hitung baseline request count normal dengan kurva sinus
            sine_wave = math.sin(step_progress * math.pi * 2)
            base_request_count = int(500 + (sine_wave * 200) + random.randint(-20, 20))
            if base_request_count < 10:
                base_request_count = 10

            # 2. Logika Injeksi Anomali (Error Spike) di tengah durasi simulasi
            # Terjadi pada 40% - 60% progress simulasi
            if inject_anomaly and (0.40 <= step_progress <= 0.60):
                # Anomali: Terjadi lonjakan error 5XX hingga 25% dari total trafik
                error_percentage = random.uniform(0.18, 0.30)
                error_5xx_count = int(base_request_count * error_percentage)
                logger.warning(f"[ANOMALY INJECTED] Step {step+1}/{total_steps}: Lonjakan Error 5XX sebesar {error_percentage*100:.2f}%!")
            else:
                # Kondisi normal: Error rate sangat rendah (< 0.5%)
                error_percentage = random.uniform(0.0001, 0.005)
                error_5xx_count = int(base_request_count * error_percentage)

            # 3. Payload data metrik
            metric_data = [
                {
                    "MetricName": "RequestCount",
                    "Dimensions": [
                        {"Name": "ServiceName", "Value": "PaymentGatewayService"},
                        {"Name": "Environment", "Value": "Production"}
                    ],
                    "Timestamp": current_time,
                    "Value": float(base_request_count),
                    "Unit": "Count",
                    "StorageResolution": 1  # High-Resolution Metric (1 detik)
                },
                {
                    "MetricName": "HTTPCode_Target_5XX_Count",
                    "Dimensions": [
                        {"Name": "ServiceName", "Value": "PaymentGatewayService"},
                        {"Name": "Environment", "Value": "Production"}
                    ],
                    "Timestamp": current_time,
                    "Value": float(error_5xx_count),
                    "Unit": "Count",
                    "StorageResolution": 1
                }
            ]

            try:
                self.cw_client.put_metric_data(
                    Namespace=self.namespace,
                    MetricData=metric_data
                )
                logger.info(
                    f"Timestamp: {current_time.strftime('%H:%M:%S')} | "
                    f"Total Requests: {base_request_count} | 5xx Errors: {error_5xx_count} "
                    f"({(error_5xx_count/base_request_count)*100:.2f}%)"
                )
            except ClientError as e:
                logger.error(f"Gagal mengirimkan metrik ke CloudWatch: {e}")
                raise e

            time.sleep(10)

        logger.info("Pengiriman metrik telemetri selesai secara sukses.")

    def evaluate_metric_math_error_rate(self, window_minutes: int = 15):
        """
        Mengeksekusi GetMetricData API dengan ekspresi Metric Math
        Formula: (HTTPCode_Target_5XX_Count / RequestCount) * 100
        """
        logger.info(f"Mengevaluasi Error Rate menggunakan Metric Math pada rentang {window_minutes} menit terakhir...")
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(minutes=window_minutes)

        query = [
            {
                "Id": "calculated_error_rate",
                "Expression": "(m2 / m1) * 100",
                "Label": "Error Rate Percentage",
                "ReturnData": True
            },
            {
                "Id": "m1",
                "MetricStat": {
                    "Metric": {
                        "Namespace": self.namespace,
                        "MetricName": "RequestCount",
                        "Dimensions": [
                            {"Name": "ServiceName", "Value": "PaymentGatewayService"},
                            {"Name": "Environment", "Value": "Production"}
                        ]
                    },
                    "Period": 60,
                    "Stat": "Sum"
                },
                "ReturnData": False
            },
            {
                "Id": "m2",
                "MetricStat": {
                    "Metric": {
                        "Namespace": self.namespace,
                        "MetricName": "HTTPCode_Target_5XX_Count",
                        "Dimensions": [
                            {"Name": "ServiceName", "Value": "PaymentGatewayService"},
                            {"Name": "Environment", "Value": "Production"}
                        ]
                    },
                    "Period": 60,
                    "Stat": "Sum"
                },
                "ReturnData": False
            }
        ]

        try:
            response = self.cw_client.get_metric_data(
                MetricDataQueries=query,
                StartTime=start_time,
                EndTime=end_time,
                ScanBy="TimestampAscending"
            )

            results = response.get("MetricDataResults", [])
            if not results or not results[0].get("Timestamps"):
                logger.warning("Tidak ada data ditemukan pada rentang waktu yang ditentukan.")
                return

            error_rate_result = results[0]
            logger.info("=== HASIL EVALUASI METRIC MATH ERROR RATE ===")
            for timestamp, value in zip(error_rate_result["Timestamps"], error_rate_result["Values"]):
                status_flag = "🚨 BREACH SLO (>5%)" if value > 5.0 else "✅ OK"
                logger.info(f"[{timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}] Error Rate: {value:.3f}% | Status: {status_flag}")

        except ClientError as e:
            logger.error(f"Gagal mengambil metrik via Metric Math: {e}")
            raise e


def parse_arguments():
    parser = argparse.ArgumentParser(description="CloudWatch Telemetry & Metric Math Simulator")
    parser.add_argument("--namespace", type=str, default="Enterprise/FinTechPlatform", help="Namespace CloudWatch")
    parser.add_argument("--region", type=str, default="ap-southeast-1", help="Region AWS target")
    parser.add_argument("--duration", type=int, default=5, help="Durasi simulasi pengiriman data dalam menit (default: 5)")
    parser.add_argument("--skip-anomaly", action="store_true", help="Jangan injeksi anomali spike error")
    parser.add_argument("--eval-only", action="store_true", help="Lewati pengiriman metrik dan hanya jalankan evaluasi query Metric Math")
    return parser.parse_args()


def main():
    args = parse_arguments()
    simulator = CloudWatchObservabilitySimulator(namespace=args.namespace, region_name=args.region)

    if not args.eval_only:
        simulator.generate_and_push_metrics(
            duration_minutes=args.duration,
            inject_anomaly=(not args.skip_anomaly)
        )

    simulator.evaluate_metric_math_error_rate(window_minutes=max(args.duration, 15))


if __name__ == "__main__":
    main()