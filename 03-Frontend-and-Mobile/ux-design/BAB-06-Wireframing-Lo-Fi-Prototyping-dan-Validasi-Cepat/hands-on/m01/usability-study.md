<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Lo-Fi Validation Prototype: Multi-Step Checkout Flow</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <style>
    /* Lo-Fi Image Placeholder Wireframe Diagonal Pattern */
    .wireframe-img-placeholder {
      background: linear-gradient(to top right, transparent calc(50% - 1px), #9ca3af 50%, transparent calc(50% + 1px)),
                  linear-gradient(to bottom right, transparent calc(50% - 1px), #9ca3af 50%, transparent calc(50% + 1px));
      background-color: #e5e7eb;
    }
  </style>
</head>
<body class="bg-gray-100 text-gray-900 font-mono antialiased min-h-screen flex flex-col justify-between">

  <!-- Header Navigasi Struktural Monokrom -->
  <header class="border-b-2 border-dashed border-gray-400 bg-white p-4">
    <div class="max-w-4xl mx-auto flex justify-between items-center">
      <div class="font-bold text-lg tracking-widest uppercase border-2 border-black px-2 py-1">[LOGO]</div>
      <nav class="flex space-x-4 text-sm text-gray-600">
        <span class="underline">01. Keranjang</span>
        <span class="font-bold text-black border-b-2 border-black">02. Pembayaran</span>
        <span class="text-gray-400">03. Review</span>
      </nav>
    </div>
  </header>

  <!-- Kontainer Utama Task Validasi -->
  <main class="max-w-4xl mx-auto w-full p-4 my-6 grid grid-cols-1 md:grid-cols-3 gap-6 flex-grow">
    
    <!-- Kolom Kiri: Formulir Interaksi (2 Kolom) -->
    <section class="md:col-span-2 bg-white border-2 border-gray-800 p-6 shadow-[4px_4px_0px_0px_rgba(0,0,0,1)]">
      <h1 class="text-xl font-bold mb-4 border-b-2 border-gray-200 pb-2">Informasi Penagihan & Alamat</h1>
      
      <form id="checkout-form" class="space-y-4" novalidate>
        <div>
          <label for="fullName" class="block text-xs uppercase font-bold text-gray-700 mb-1">Nama Lengkap Sesuai KTP *</label>
          <input 
            type="text" 
            id="fullName" 
            name="fullName" 
            required 
            placeholder="John Doe" 
            class="w-full border-2 border-gray-400 p-2 text-sm focus:border-black focus:outline-none transition-colors"
          />
          <span class="text-xs text-red-600 hidden font-sans mt-1" id="err-fullName">Bidang ini wajib diisi dengan benar.</span>
        </div>

        <div>
          <label for="address" class="block text-xs uppercase font-bold text-gray-700 mb-1">Alamat Pengiriman Lengkap *</label>
          <textarea 
            id="address" 
            name="address" 
            rows="3" 
            required
            placeholder="Jl. Sudirman No. 42, Kavling 3, Jakarta Selatan" 
            class="w-full border-2 border-gray-400 p-2 text-sm focus:border-black focus:outline-none transition-colors"
          ></textarea>
          <span class="text-xs text-red-600 hidden font-sans mt-1" id="err-address">Alamat harus diisi lengkap.</span>
        </div>

        <fieldset class="border-2 border-gray-300 p-3">
          <legend class="text-xs font-bold uppercase px-1 text-gray-600">Metode Pengiriman</legend>
          <div class="space-y-2 mt-1">
            <label class="flex items-center space-x-2 text-sm cursor-pointer">
              <input type="radio" name="shippingMethod" value="express" class="accent-black" checked>
              <span>Express Next-Day (Rp 30.000)</span>
            </label>
            <label class="flex items-center space-x-2 text-sm cursor-pointer">
              <input type="radio" name="shippingMethod" value="standard" class="accent-black">
              <span>Reguler Ekonomi (Rp 15.000)</span>
            </label>
          </div>
        </fieldset>

        <button 
          type="submit" 
          id="btn-submit" 
          class="w-full bg-black text-white py-3 uppercase tracking-wider font-bold text-sm hover:bg-gray-800 active:translate-y-0.5 transition-all cursor-pointer"
        >
          Lanjut ke Konfirmasi &rarr;
        </button>
      </form>
    </section>

    <!-- Kolom Kanan: Spatial Anchor Summary (1 Kolom) -->
    <aside class="bg-gray-50 border-2 border-gray-300 p-4 h-fit space-y-4">
      <h2 class="text-xs font-bold uppercase text-gray-500 tracking-wider">Ringkasan Pesanan</h2>
      
      <!-- Visual Placeholder Wireframe -->
      <div class="flex items-center space-x-3">
        <div class="w-16 h-16 wireframe-img-placeholder border border-gray-400 flex-shrink-0"></div>
        <div class="space-y-1 w-full">
          <div class="h-3 bg-gray-300 rounded w-3/4"></div>
          <div class="h-3 bg-gray-200 rounded w-1/2"></div>
          <div class="text-xs font-bold text-gray-700 mt-1">1x Rp 1.250.000</div>
        </div>
      </div>

      <div class="border-t border-dashed border-gray-300 pt-3 space-y-2 text-xs">
        <div class="flex justify-between">
          <span class="text-gray-500">Subtotal</span>
          <span>Rp 1.250.000</span>
        </div>
        <div class="flex justify-between">
          <span class="text-gray-500">Estimasi Pajak</span>
          <span>Rp 137.500</span>
        </div>
        <div class="flex justify-between font-bold text-sm border-t border-gray-400 pt-2">
          <span>Total Akhir</span>
          <span>Rp 1.387.500</span>
        </div>
      </div>
    </aside>
  </main>

  <!-- Instrumentasi Telemetri Pengujian UX -->
  <footer class="bg-gray-900 text-gray-400 p-4 text-xs font-mono">
    <div class="max-w-4xl mx-auto flex flex-col md:flex-row justify-between items-center gap-2">
      <div>Telemetri Validasi: Status Rekam Aktif</div>
      <div id="telemetry-display" class="text-yellow-400">Time-on-Task: 0.00s | Dead/Rage Clicks: 0</div>
    </div>
  </footer>

  <script>
    (function initUsabilityTestingEngine() {
      const startTime = performance.now();
      let deadClickCount = 0;
      let lastClickTimestamp = 0;
      let rapidClickCount = 0;
      const metricsPayload = {
        taskId: "task_checkout_phase_1",
        timeOnTaskMs: 0,
        misclicks: 0,
        validationErrors: 0,
        completionStatus: "abandoned"
      };

      // Timer real-time untuk display telemetri
      const timerInterval = setInterval(() => {
        const currentToT = ((performance.now() - startTime) / 1000).toFixed(2);
        document.getElementById("telemetry-display").innerText = 
          `Time-on-Task: ${currentToT}s | Dead/Rage Clicks: ${deadClickCount}`;
      }, 100);

      // Dead Click and Rage Click Interceptor
      document.addEventListener("click", (e) => {
        const now = performance.now();
        const interactiveTarget = e.target.closest("button, input, textarea, a, label");

        if (!interactiveTarget) {
          deadClickCount++;
        }

        if (now - lastClickTimestamp < 400) {
          rapidClickCount++;
          if (rapidClickCount >= 3) {
            console.warn("[UX TELEMETRY] RAGE CLICK DETECTED pada Node:", e.target);
            deadClickCount++;
            rapidClickCount = 0;
          }
        } else {
          rapidClickCount = 1;
        }
        lastClickTimestamp = now;
      });

      // Validasi Form dan Event Completion
      const form = document.getElementById("checkout-form");
      form.addEventListener("submit", (e) => {
        e.preventDefault();
        let hasError = false;

        const fullName = document.getElementById("fullName");
        const address = document.getElementById("address");
        const errFullName = document.getElementById("err-fullName");
        const errAddress = document.getElementById("err-address");

        if (!fullName.value.trim()) {
          errFullName.classList.remove("hidden");
          fullName.classList.add("border-red-600");
          hasError = true;
        } else {
          errFullName.classList.add("hidden");
          fullName.classList.remove("border-red-600");
        }

        if (!address.value.trim()) {
          errAddress.classList.remove("hidden");
          address.classList.add("border-red-600");
          hasError = true;
        } else {
          errAddress.classList.add("hidden");
          address.classList.remove("border-red-600");
        }

        if (hasError) {
          metricsPayload.validationErrors++;
          return;
        }

        // Sukses Task
        clearInterval(timerInterval);
        metricsPayload.timeOnTaskMs = Math.round(performance.now() - startTime);
        metricsPayload.misclicks = deadClickCount;
        metricsPayload.completionStatus = "success";

        console.info("[UX TELEMETRY COMPLETE] Task Dispatching Data:", metricsPayload);
        alert(`Task Sukses divalidasi!\nTime on Task: ${(metricsPayload.timeOnTaskMs / 1000).toFixed(2)} detik\nTotal Misclicks: ${metricsPayload.misclicks}\nForm Errors: ${metricsPayload.validationErrors}`);
      });
    })();
  </script>
</body>
</html>
