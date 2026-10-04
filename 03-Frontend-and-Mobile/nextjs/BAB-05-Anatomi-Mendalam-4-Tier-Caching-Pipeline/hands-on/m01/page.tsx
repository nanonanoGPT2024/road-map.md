// src/app/products/[sku]/page.tsx
import { Suspense } from 'react';
import { notFound } from 'next/navigation';
import { purchaseItemAction } from '@/app/actions/inventory-actions';

interface ProductDetailPageProps {
  params: Promise<{ sku: string }>;
}

// 1. FUNGSI DATA CACHE DENGAN TAG & PENANGANAN ERROR RESILIEN
async function getInventoryStock(sku: string): Promise<number> {
  const res = await fetch(`https://api.enterprise.internal/v1/inventory/stock/${sku}`, {
    method: 'GET',
    headers: { 'Accept': 'application/json' },
    next: {
      // Revalidasi periodik jika mutation webhook miss (fail-safe)
      revalidate: 5,
      tags: [`inventory-${sku}`],
    },
  });

  if (res.status === 404) notFound();
  if (!res.ok) {
    // Graceful fallback strategi daripada crashing seluruh pohon render
    console.error(`Inventory fetch degraded for SKU: ${sku}`);
    return 0;
  }

  const data = await res.json();
  return data.availableUnits;
}

// 2. ISOLATED COMPONENT DENGAN RUNTIME OPTIMIZATION
async function InventoryBadge({ sku }: { sku: string }) {
  const stock = await getInventoryStock(sku);

  return (
    <div className="flex items-center gap-2 mt-4">
      <span className={`inline-block w-3 h-3 rounded-full ${stock > 0 ? 'bg-emerald-500' : 'bg-rose-500'}`} />
      <span className="font-semibold text-sm">
        {stock > 0 ? `Tersisa ${stock} unit di gudang` : 'Stok Habis'}
      </span>
    </div>
  );
}

// 3. ROOT PAGE: MENGISOLASI STATIC SHELL & DYNAMIC COMPONENT
export default async function ProductPage({ params }: ProductDetailPageProps) {
  const { sku } = await params;

  return (
    <div className="p-8 max-w-xl mx-auto border rounded-xl shadow-lg bg-white">
      {/* Shell Statis: Cached via Full Route Cache jika di-build secara static */}
      <h1 className="text-3xl font-extrabold tracking-tight text-gray-900">
        Enterprise SKU: {sku}
      </h1>
      <p className="text-sm text-gray-500 mt-1">Sistem Pemesanan Terdesentralisasi</p>

      {/* Dynamic Boundary: Streaming boundary yang tidak memblokir parsing initial route */}
      <Suspense fallback={<div className="h-6 w-32 bg-gray-200 animate-pulse rounded mt-4" />}>
        <InventoryBadge sku={sku} />
      </Suspense>

      <form action={purchaseItemAction.bind(null, sku, 1)} className="mt-6">
        <button
          type="submit"
          className="w-full bg-blue-600 hover:bg-blue-700 text-white font-medium py-2.5 px-4 rounded-lg transition-colors"
        >
          Beli Sekarang (Instant Checkout)
        </button>
      </form>
    </div>
  );
}
