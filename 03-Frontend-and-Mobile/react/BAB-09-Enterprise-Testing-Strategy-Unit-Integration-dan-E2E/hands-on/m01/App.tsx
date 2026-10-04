import React, { useState, useEffect } from 'react';

export const TransferForm: React.FC = () => {
  const [recipientId, setRecipientId] = useState('');
  const [amount, setAmount] = useState<number | ''>('');
  const [remainingLimit, setRemainingLimit] = useState<number | null>(null);
  const [status, setStatus] = useState<'idle' | 'submitting' | 'success' | 'error'>('idle');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [txId, setTxId] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;
    fetch('/api/v1/account/limits')
      .then((res) => res.json())
      .then((data) => {
        if (isMounted) setRemainingLimit(data.remainingLimit);
      })
      .catch(() => {
        if (isMounted) setErrorMessage('Gagal memuat limit harian');
      });

    return () => {
      isMounted = false;
    };
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!amount || Number(amount) <= 0 || !recipientId) return;

    setStatus('submitting');
    setErrorMessage(null);

    try {
      const res = await fetch('/api/v1/transfers', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ recipientId, amount: Number(amount) }),
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.message || 'Gagal memproses transaksi');
      }

      setTxId(data.transactionId);
      setStatus('success');
    } catch (err: unknown) {
      setStatus('error');
      if (err instanceof Error) {
        setErrorMessage(err.message);
      } else {
        setErrorMessage('Terjadi kesalahan internal');
      }
    }
  };

  if (status === 'success') {
    return (
      <div role="status" aria-label="Bukti Transfer">
        <h2>Transfer Berhasil!</h2>
        <p>ID Transaksi: {txId}</p>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} aria-label="Form Transfer Dana">
      <h2>Transfer Dana</h2>
      
      {remainingLimit !== null && (
        <p aria-live="polite">Sisa Limit Harian: Rp {remainingLimit.toLocaleString('id-ID')}</p>
      )}

      {errorMessage && (
        <div role="alert" style={{ color: 'red' }}>
          {errorMessage}
        </div>
      )}

      <div>
        <label htmlFor="recipient">Nomor Rekening Tujuan</label>
        <input
          id="recipient"
          type="text"
          value={recipientId}
          onChange={(e) => setRecipientId(e.target.value)}
          disabled={status === 'submitting'}
          required
        />
      </div>

      <div>
        <label htmlFor="amount">Jumlah Transfer</label>
        <input
          id="amount"
          type="number"
          value={amount}
          onChange={(e) => setAmount(e.target.value === '' ? '' : Number(e.target.value))}
          disabled={status === 'submitting'}
          required
        />
      </div>

      <button type="submit" disabled={status === 'submitting'}>
        {status === 'submitting' ? 'Memproses...' : 'Kirim Sekarang'}
      </button>
    </form>
  );
};
