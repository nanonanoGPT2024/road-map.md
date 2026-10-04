# test_portfolio_engine.py
import cProfile
import pstats
from dataclasses import dataclass
from decimal import Decimal
from io import StringIO
from typing import Protocol
from unittest.mock import create_autospec

import pytest
from hypothesis import given, strategies as st


# ==========================================
# 1. CORE DOMAIN LOGIC UNDER TEST
# ==========================================
class FXRateService(Protocol):
    """Port interface untuk layanan nilai tukar mata uang."""
    def get_rate(self, base: str, target: str) -> Decimal:
        ...


@dataclass(frozen=True, slots=True)
class AssetPosition:
    symbol: str
    quantity: Decimal
    base_currency: str


class PortfolioEvaluator:
    def __init__(self, fx_service: FXRateService) -> None:
        self._fx_service = fx_service

    def calculate_total_value(
        self, positions: list[AssetPosition], target_currency: str
    ) -> Decimal:
        if not positions:
            return Decimal("0.0")

        total = Decimal("0.0")
        for pos in positions:
            if pos.quantity < Decimal("0.0"):
                raise ValueError(f"Kuantitas posisi tidak boleh negatif: {pos.quantity}")
            
            rate = Decimal("1.0")
            if pos.base_currency != target_currency:
                rate = self._fx_service.get_rate(pos.base_currency, target_currency)
            
            total += pos.quantity * rate
        return total


# ==========================================
# 2. TESTING SUITE (FIXTURES, MOCKS, HYPOTHESIS)
# ==========================================

@pytest.fixture
def mock_fx_service() -> FXRateService:
    """Fixture untuk menyediakan interface mock terspesifikasi."""
    mock = create_autospec(FXRateService, instance=True)
    # Default behavior: 1 USD = 15000 IDR
    mock.get_rate.return_value = Decimal("15000.00")
    return mock


@pytest.fixture
def sample_positions() -> list[AssetPosition]:
    """Fixture penyedia data posisi portofolio acuan."""
    return [
        AssetPosition(symbol="AAPL", quantity=Decimal("10"), base_currency="USD"),
        AssetPosition(symbol="BBCA", quantity=Decimal("100"), base_currency="IDR"),
    ]


def test_calculate_total_value_with_fx_conversion(
    mock_fx_service: FXRateService, sample_positions: list[AssetPosition]
) -> None:
    """Menguji konversi valuta menggunakan mock FX service."""
    # Setup
    evaluator = PortfolioEvaluator(fx_service=mock_fx_service)

    # Execution
    total_in_idr = evaluator.calculate_total_value(sample_positions, target_currency="IDR")

    # Assertions
    # 10 AAPL * 15000 = 150,000 IDR
    # 100 BBCA = 100 IDR
    # Total = 150,100 IDR
    assert total_in_idr == Decimal("150100.00")
    mock_fx_service.get_rate.assert_called_once_with("USD", "IDR")


def test_negative_quantity_raises_value_error(mock_fx_service: FXRateService) -> None:
    """Memastikan invarian error tervalidasi saat input kuantitas invalid."""
    evaluator = PortfolioEvaluator(fx_service=mock_fx_service)
    invalid_positions = [
        AssetPosition(symbol="FRAUD", quantity=Decimal("-5"), base_currency="USD")
    ]

    with pytest.raises(ValueError, match="Kuantitas posisi tidak boleh negatif"):
        evaluator.calculate_total_value(invalid_positions, target_currency="USD")


# Property-Based Testing Invariant
@given(
    quantities=st.lists(
        st.decimals(min_value=Decimal("0.0"), max_value=Decimal("1000000.0"), places=2),
        min_size=1,
        max_size=50,
    )
)
def test_portfolio_monotonicity_property(quantities: list[Decimal]) -> None:
    """Invarian: Menambahkan kuantitas positif tidak boleh mengurangi total nilai."""
    mock_service = create_autospec(FXRateService, instance=True)
    mock_service.get_rate.return_value = Decimal("1.0")
    evaluator = PortfolioEvaluator(fx_service=mock_service)

    positions = [
        AssetPosition(symbol=f"ASSET_{i}", quantity=q, base_currency="USD")
        for i, q in enumerate(quantities)
    ]

    total_base = evaluator.calculate_total_value(positions, target_currency="USD")

    # Modifikasi: Tambahkan satu aset dengan quantity > 0
    additional_position = AssetPosition(
        symbol="ADDON", quantity=Decimal("10.0"), base_currency="USD"
    )
    total_extended = evaluator.calculate_total_value(
        positions + [additional_position], target_currency="USD"
    )

    # Invarian Monotonik
    assert total_extended > total_base


# ==========================================
# 3. RUNTIME PROFILING INSTRUMENTATION
# ==========================================
def profile_portfolio_calculation() -> None:
    """Instrumentasi Profiling terintegrasi menggunakan cProfile."""
    mock_service = create_autospec(FXRateService, instance=True)
    mock_service.get_rate.return_value = Decimal("1.5")
    evaluator = PortfolioEvaluator(fx_service=mock_service)

    # Simulasi 100,000 posisi aset untuk memicu beban komputasi
    large_dataset = [
        AssetPosition(symbol=f"SYM_{i}", quantity=Decimal(f"{i}.5"), base_currency="USD")
        for i in range(100_000)
    ]

    profiler = cProfile.Profile()
    profiler.enable()

    # Eksekusi fungsi target
    evaluator.calculate_total_value(large_dataset, target_currency="EUR")

    profiler.disable()

    # Ekstraksi dan pemformatan metrik profiling
    stream = StringIO()
    stats = pstats.Stats(profiler, stream=stream).sort_stats(pstats.SortKey.CUMULATIVE)
    stats.print_stats(10)  # Cetak top 10 baris termahal
    print(stream.getvalue())


if __name__ == "__main__":
    profile_portfolio_calculation()
