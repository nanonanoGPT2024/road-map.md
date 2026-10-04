// src/experiments/CheckoutFlowExperiment.tsx
import React, { useState, useMemo } from 'react';
import { WireframeProvider, WireframeBox, WireframePlaceholderText, TelemetryPayload } from '../components/wireframe/WireframePrimitives';

// ---------------------------------------------------------------------
// DETERMINISTIC HASH FUNCTION (MURMUR-LIKE SIMPLE HASH)
// ---------------------------------------------------------------------
function hashUserVariant(userId: string): 'variant-a' | 'variant-b' {
  let hash = 0;
  for (let i = 0; i < userId.length; i++) {
    const char = userId.charCodeAt(i);
    hash = (hash << 5) - hash + char;
    hash |= 0; // Convert to 32bit integer
  }
  return Math.abs(hash) % 2 === 0 ? 'variant-a' : 'variant-b';
}

// ---------------------------------------------------------------------
// EXPERIMENTAL LOW-FI VIEW: VARIANT A (SINGLE-PAGE ACCORDION)
// ---------------------------------------------------------------------
const VariantAAccordion: React.FC<{ onComplete: () => void; recordStep: (step: string) => void }> = ({
  onComplete,
  recordStep,
}) => {
  const [openSection, setOpenSection] = useState<number>(1);

  return (
    <div style={{ maxWidth: 600, margin: '0 auto' }}>
      <h3>Struktur Low-Fi Varian A: Accordion Monolitik</h3>
      <WireframeBox
        id="accordion-sec-1"
        isInteractive
        onClick={() => {
          setOpenSection(1);
          recordStep('acc-sec-1');
        }}
      >
        <h4>[Section 1: Data Identitas Perusahaan]</h4>
        {openSection === 1 && (
          <>
            <WireframePlaceholderText lines={2} />
            <WireframeBox id="input-mock-1" height={40}>Input Block Identitas</WireframeBox>
          </>
        )}
      </WireframeBox>

      <WireframeBox
        id="accordion-sec-2"
        isInteractive
        onClick={() => {
          setOpenSection(2);
          recordStep('acc-sec-2');
        }}
      >
        <h4>[Section 2: Parameter Finansial Limit]</h4>
        {openSection === 2 && (
          <>
            <WireframePlaceholderText lines={3} />
            <WireframeBox id="input-mock-2" height={40}>Input Block Finansial</WireframeBox>
          </>
        )}
      </WireframeBox>

      <WireframeBox
        id="btn-complete-a"
        isInteractive
        onClick={() => {
          recordStep('complete');
          onComplete();
        }}
      >
        <strong>EKSEKUSI FINALISASI ORDER</strong>
      </WireframeBox>
    </div>
  );
};

// ---------------------------------------------------------------------
// EXPERIMENTAL LOW-FI VIEW: VARIANT B (STEPPER WIZARD)
// ---------------------------------------------------------------------
const VariantBStepper: React.FC<{ onComplete: () => void; recordStep: (step: string) => void }> = ({
  onComplete,
  recordStep,
}) => {
  const [step, setStep] = useState<number>(1);

  return (
    <div style={{ maxWidth: 600, margin: '0 auto' }}>
      <h3>Struktur Low-Fi Varian B: Multi-Step Sequential</h3>
      <WireframeBox id={`stepper-indicator-${step}`}>
        Indikator Progres Aktif: Tahap {step} dari 2
      </WireframeBox>

      {step === 1 && (
        <WireframeBox id="step-1-container">
          <h4>[Langkah 1: Identitas Perusahaan]</h4>
          <WireframePlaceholderText lines={3} />
          <WireframeBox id="step-1-input" height={40}>Input Field</WireframeBox>
          <WireframeBox
            id="btn-next-step"
            isInteractive
            onClick={() => {
              recordStep('step-2');
              setStep(2);
            }}
          >
            Lanjut ke Tahap 2 -&gt;
          </WireframeBox>
        </WireframeBox>
      )}

      {step === 2 && (
        <WireframeBox id="step-2-container">
          <h4>[Langkah 2: Parameter Finansial Limit]</h4>
          <WireframePlaceholderText lines={2} />
          <WireframeBox id="step-2-input" height={40}>Input Field</WireframeBox>
          <WireframeBox
            id="btn-complete-b"
            isInteractive
            onClick={() => {
              recordStep('complete');
              onComplete();
            }}
          >
            <strong>SELESAIKAN PROSES</strong>
          </WireframeBox>
        </WireframeBox>
      )}
    </div>
  );
};

// ---------------------------------------------------------------------
// HARNESS CONTAINER & TELEMETRY INGESTION ENGINE
// ---------------------------------------------------------------------
export const CheckoutExperimentHarness: React.FC<{ testSessionUserId: string }> = ({ testSessionUserId }) => {
  const variant = useMemo(() => hashUserVariant(testSessionUserId), [testSessionUserId]);
  
  // Metrik Navigasi (Lostness Metric Variables)
  const [visitedNodes, setVisitedNodes] = useState<string[]>([]);
  const [sessionCompleted, setSessionCompleted] = useState<boolean>(false);
  const [telemetryLogs, setTelemetryLogs] = useState<TelemetryPayload[]>([]);

  const optimalSteps = 2; // R (Minimum optimal steps: input-1 -> input-2 -> complete)

  const handleRecordStep = (stepNode: string) => {
    setVisitedNodes((prev) => [...prev, stepNode]);
  };

  const handleTelemetryDispatch = (event: TelemetryPayload) => {
    setTelemetryLogs((prev) => [...prev, event]);
    // Di lingkungan produksi: kirim via navigator.sendBeacon ke event ingestion bus
  };

  const computeLostness = (): number => {
    const N = visitedNodes.length; // Total kunjungan langkah
    const S = new Set(visitedNodes).size; // Total unique state/pages
    const R = optimalSteps;

    if (S === 0 || N === 0) return 0;
    const term1 = Math.pow(N / S - 1, 2);
    const term2 = Math.pow(S / R - 1, 2);
    return Math.sqrt(term1 + term2);
  };

  return (
    <WireframeProvider variantId={variant} onDispatchMetric={handleTelemetryDispatch}>
      <div style={{ borderBottom: '1px solid #999', paddingBottom: 16, marginBottom: 24 }}>
        <h2>Experimental Low-Fi Session Harness</h2>
        <p>User Identifier: <code>{testSessionUserId}</code> | Alokasi Varian: <strong>{variant.toUpperCase()}</strong></p>
      </div>

      {!sessionCompleted ? (
        variant === 'variant-a' ? (
          <VariantAAccordion
            recordStep={handleRecordStep}
            onComplete={() => setSessionCompleted(true)}
          />
        ) : (
          <VariantBStepper
            recordStep={handleRecordStep}
            onComplete={() => setSessionCompleted(true)}
          />
        )
      ) : (
        <WireframeBox id="evaluation-receipt">
          <h3>Eksperimen Berhasil Diselesaikan</h3>
          <p>Kalkulasi Lostness Score: <strong>{computeLostness().toFixed(4)}</strong></p>
          <p>Total Interaksi Terekam: {telemetryLogs.length} events</p>
          <pre style={{ textAlign: 'left', fontSize: 11, background: '#eee', padding: 8, width: '90%' }}>
            {JSON.stringify({ visitedNodes, telemetryLogs }, null, 2)}
          </pre>
        </WireframeBox>
      )}
    </WireframeProvider>
  );
};
