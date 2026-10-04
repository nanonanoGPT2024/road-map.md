import { Suspense } from 'react';
import { getFleetMetrics } from '@/domain/cargo/api';
import { CustomsTable } from '@/components/cargo/customs-table';

export const experimental_ppr = true;

// Komponen metrik cepat: dipanggil langsung di root async RSC
async function FastFleetCards() {
  const fleet = await getFleetMetrics();

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      <div className="p-4 bg-slate-900 border border-slate-800 rounded-xl">
        <span className="text-xs text-slate-400 uppercase font-semibold">Truk Aktif Beroperasi</span>
        <p className="text-2xl font-bold text-white mt-1">{fleet.activeTrucks}</p>
      </div>
      <div className="p-4 bg-slate-900 border border-slate-800 rounded-xl">
        <span className="text-xs text-slate-400 uppercase font-semibold">Pengiriman Tertunda (Delay)</span>
        <p className="text-2xl font-bold text-amber-500 mt-1">{fleet.delayedShipments}</p>
      </div>
      <div className="p-4 bg-slate-900 border border-slate-800 rounded-xl">
        <span className="text-xs text-slate-400 uppercase font-semibold">Tertahan Otoritas Pabean</span>
        <p className="text-2xl font-bold text-rose-500 mt-1">{fleet.customsHoldCount}</p>
      </div>
    </div>
  );
}

function TableSkeletonLoader() {
  return (
    <div className="w-full space-y-2 animate-pulse">
      <div className="h-10 bg-slate-800/80 rounded w-full" />
      <div className="h-12 bg-slate-800/40 rounded w-full" />
      <div className="h-12 bg-slate-800/40 rounded w-full" />
      <div className="h-12 bg-slate-800/40 rounded w-full" />
    </div>
  );
}

export default function CargoOperationsPage() {
  return (
    <div className="p-8 space-y-8 bg-black min-h-screen text-slate-100">
      {/* BAGIAN 1: Static Shell (Instant Pre-render via Edge) */}
      <section className="flex flex-col gap-2">
        <span className="text-xs font-mono text-emerald-400 tracking-wider">SECURE DISPATCH NODE // REGION AP-SOUTHEAST-1</span>
        <h1 className="text-3xl font-extrabold text-white">Konsol Monitoring Operasional Kargo</h1>
      </section>

      {/* BAGIAN 2: Fast Tier Dynamic Stream (Tercapai dalam <150ms) */}
      <section className="space-y-3">
        <h2 className="text-sm font-semibold text-slate-400">Ringkasan Armada Global</h2>
        <Suspense fallback={<div className="h-20 bg-slate-900 animate-pulse rounded-xl" />}>
          <FastFleetCards />
        </Suspense>
      </section>

      {/* BAGIAN 3: Heavy Tier Dynamic Stream (Tergantung koneksi legacy) */}
      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-slate-400">Log Verifikasi Kliring Kepabeanan Real-Time</h2>
          <span className="text-xs text-slate-500 font-mono">Stream Id: customs-audit-stream</span>
        </div>
        <Suspense fallback={<TableSkeletonLoader />}>
          <CustomsTable />
        </Suspense>
      </section>
    </div>
  );
}
