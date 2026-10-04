// sla_calculator.js
// Kalkulator Ketersediaan Sistem, Toleransi Downtime, & Simulator Error Budget (SLI/SLO)

function calculateDowntime(availabilityPercentage) {
  const minutesPerYear = 365.25 * 24 * 60;
  const minutesPerMonth = (365.25 / 12) * 24 * 60;
  const minutesPerDay = 24 * 60;

  const downtimeFraction = 1 - (availabilityPercentage / 100);

  function formatDuration(totalMinutes) {
    if (totalMinutes >= 1440) {
      const days = Math.floor(totalMinutes / 1440);
      const hours = Math.floor((totalMinutes % 1440) / 60);
      return `${days} hari ${hours} jam`;
    }
    if (totalMinutes >= 60) {
      const hours = Math.floor(totalMinutes / 60);
      const mins = (totalMinutes % 60).toFixed(1);
      return `${hours} jam ${mins} mnt`;
    }
    if (totalMinutes >= 1) {
      const mins = Math.floor(totalMinutes);
      const secs = ((totalMinutes % 1) * 60).toFixed(0);
      return `${mins} mnt ${secs} dtk`;
    }
    const secs = (totalMinutes * 60).toFixed(2);
    return `${secs} detik`;
  }

  return {
    "Availability (%)": `${availabilityPercentage}%`,
    "Downtime / Tahun": formatDuration(minutesPerYear * downtimeFraction),
    "Downtime / Bulan": formatDuration(minutesPerMonth * downtimeFraction),
    "Downtime / Hari": formatDuration(minutesPerDay * downtimeFraction),
  };
}

function runErrorBudgetSimulation() {
  console.log("\n===================================================================");
  console.log("            SIMULASI PENGAWASAN SLI / SLO & ERROR BUDGET           ");
  console.log("===================================================================");

  const TOTAL_REQUESTS = 20000;
  const TARGET_SLO = 99.9; // Target 99.9% ketersediaan
  const allowedErrorFraction = (100 - TARGET_SLO) / 100;
  const totalErrorBudgetRequests = Math.floor(TOTAL_REQUESTS * allowedErrorFraction);

  console.log(`[TARGET SISTEM]:`);
  console.log(` - Total Request Diawasi: ${TOTAL_REQUESTS.toLocaleString()}`);
  console.log(` - Target SLO Internal  : ${TARGET_SLO}%`);
  console.log(` - Kuota Error Budget   : Maksimal ${totalErrorBudgetRequests} request gagal diizinkan\n`);

  // Simulasi 20.000 requests dengan satu lonjakan insiden (outage)
  let successfulRequests = 0;
  let failedRequests = 0;

  for (let i = 1; i <= TOTAL_REQUESTS; i++) {
    // Simulasi insiden terjadi pada request 8.000 hingga 8.015 (16 request gagal)
    const isOutagePeriod = (i >= 8000 && i <= 8015);
    const randomFailure = Math.random() < 0.0001;

    if (isOutagePeriod || randomFailure) {
      failedRequests++;
    } else {
      successfulRequests++;
    }
  }

  const realSLI = (successfulRequests / TOTAL_REQUESTS) * 100;
  const errorBudgetConsumed = (failedRequests / totalErrorBudgetRequests) * 100;
  const errorBudgetRemaining = Math.max(0, 100 - errorBudgetConsumed);

  console.log(`[HASIL OPERASIONAL NYATA]:`);
  console.log(` - Request Berhasil (2xx/3xx): ${successfulRequests.toLocaleString()}`);
  console.log(` - Request Gagal (5xx)       : ${failedRequests.toLocaleString()}`);
  console.log(` - SLI Aktual                : ${realSLI.toFixed(4)}%`);
  console.log(` - Error Budget Terpakai     : ${errorBudgetConsumed.toFixed(1)}%`);
  console.log(` - Sisa Error Budget         : ${errorBudgetRemaining.toFixed(1)}%`);

  console.log(`\n[KEPUTUSAN ENGINEERING]:`);
  if (realSLI >= TARGET_SLO) {
    console.log(` ✅ TARGET SLO TERCAPAI! Sisa budget ${errorBudgetRemaining.toFixed(1)}%. Tim bebas melanjutkan rilis fitur baru.`);
  } else {
    console.log(` ❌ TARGET SLO GAGAL! Error budget habis terlampaui. Lakukan FEATURE FREEZE dan perbaiki resiliensi sistem.`);
  }
  console.log("===================================================================\n");
}

function main() {
  console.log("===================================================================");
  console.log("           TABEL TOLERANSI DOWNTIME (NINES OF AVAILABILITY)        ");
  console.log("===================================================================");

  const levels = [99.0, 99.9, 99.95, 99.99, 99.999];
  const tableData = levels.map(l => calculateDowntime(l));
  console.table(tableData);

  runErrorBudgetSimulation();
}

main();
