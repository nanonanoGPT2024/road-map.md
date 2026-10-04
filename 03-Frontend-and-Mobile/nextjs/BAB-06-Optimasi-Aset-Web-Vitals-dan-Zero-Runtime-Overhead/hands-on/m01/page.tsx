import { notFound } from 'next/navigation';
import { ProductGallery } from '@/components/product-gallery';
import { generateOptimizedBlur } from '@/lib/image-utils';
import Script from 'next/script';

interface ProductPageProps {
  params: Promise<{ slug: string }>;
}

async function getProductData(slug: string) {
  // Simulasi data fetch dari Backend Microservice
  if (slug !== 'hyper-sneaker-x') return null;

  const rawImages = [
    'https://assets.enterprise.cdn.com/media/sneaker-main.jpg',
    'https://assets.enterprise.cdn.com/media/sneaker-angle.jpg',
    'https://assets.enterprise.cdn.com/media/sneaker-sole.jpg',
  ];

  // Pipeline parallel processing server-side blurhash placeholders
  const processedImages = await Promise.all(
    rawImages.map((url) => generateOptimizedBlur(url))
  );

  return {
    id: 'prod_987123',
    name: 'Nike Air VaporMax Enterprise Edition',
    price: '$220.00',
    description: 'Precision engineered zero-runtime high performance footwear.',
    images: processedImages,
  };
}

export default async function ProductPage({ params }: ProductPageProps) {
  const { slug } = await params;
  const product = await getProductData(slug);

  if (!product) {
    notFound();
  }

  return (
    <div className="max-w-7xl mx-auto px-4 py-8 lg:py-12">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 items-start">
        {/* Render Critical Image Pipeline */}
        <ProductGallery media={product.images} productName={product.name} />

        {/* Product Details Section */}
        <div className="flex flex-col space-y-6">
          <div className="space-y-2">
            <span className="text-sm font-semibold tracking-wider text-indigo-400 uppercase">
              Limited Tier Release
            </span>
            <h1 className="text-3xl sm:text-4xl font-black text-slate-100">
              {product.name}
            </h1>
            <p className="text-2xl font-mono text-emerald-400 font-bold">
              {product.price}
            </p>
          </div>

          <p className="text-slate-400 leading-relaxed">
            {product.description}
          </p>

          <button
            type="button"
            className="w-full h-14 bg-indigo-600 hover:bg-indigo-500 active:scale-[0.99] font-medium rounded-xl transition-all shadow-lg shadow-indigo-600/20"
          >
            Add to Bag
          </button>
        </div>
      </div>

      {/* Heavy Third-Party Script Offloading */}
      {/* 1. Hotjar Analytics: lazyOnload to save initial main-thread */}
      <Script id="hotjar-analytics" strategy="lazyOnload">
        {`
          (function(h,o,t,j,a,r){
              h.hj=h.hj||function(){(h.hj.q=h.hj.q||[]).push(arguments)};
              h._hjSettings={hjid:3000000,hjsv:6};
              a=o.getElementsByTagName('head')[0];
              r=o.createElement('script');r.async=1;
              r.src=t+h._hjSettings.hjid+j+h._hjSettings.hjsv;
              a.appendChild(r);
          })(window,document,'https://static.hotjar.com/c/hotjar-','.js?sv=');
        `}
      </Script>

      {/* 2. Worker Strategy: Menjalankan eksekusi skrip analitik di Background Thread via Partytown */}
      <Script
        src="https://connect.facebook.net/en_US/fbevents.js"
        strategy="worker"
      />
    </div>
  );
}
