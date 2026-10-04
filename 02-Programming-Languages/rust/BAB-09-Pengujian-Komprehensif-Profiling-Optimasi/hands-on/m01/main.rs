use std::fmt;

#[derive(Debug, PartialEq, Eq, Clone, Copy)]
pub enum EngineError {
    MalformedPayload,
    CapacityExceeded,
    CalculationOverflow,
}

impl fmt::Display for EngineError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            EngineError::MalformedPayload => write!(f, "Format log tidak valid"),
            EngineError::CapacityExceeded => write!(f, "Kapasitas array internal terlampaui"),
            EngineError::CalculationOverflow => write!(f, "Integer overflow pada agregasi nilai"),
        }
    }
}

impl std::error::Error for EngineError {}

/// Struktur data padat berorientasi cache (Ukuran pas 16 byte, cache-line aligned friendly)
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
#[repr(C)]
pub struct TransactionRecord {
    pub transaction_id: u32,
    pub symbol_id: u16,
    pub flag: u8,
    pub _reserved: u8, // Alinyemen manual eksplisit
    pub net_value: i64,
}

/// Zero-Allocation Parser: Mem-parsing string ASCII byte secara in-place tanpa alokasi Heap
#[inline(always)]
pub fn parse_log_line_zero_alloc(raw_line: &str) -> Result<TransactionRecord, EngineError> {
    let bytes = raw_line.as_bytes();
    let mut fields = [0usize; 4]; // Menyimpan indeks pemisah koma
    let mut field_idx = 0;

    let mut i = 0;
    while i < bytes.len() {
        if bytes[i] == b',' {
            if field_idx >= fields.len() {
                return Err(EngineError::MalformedPayload);
            }
            fields[field_idx] = i;
            field_idx += 1;
        }
        i += 1;
    }

    // Format yang valid harus memiliki tepat 3 pemisah koma: ID,SymbolID,Flag,NetValue
    if field_idx != 3 {
        return Err(EngineError::MalformedPayload);
    }

    let id_bytes = &bytes[0..fields[0]];
    let symbol_bytes = &bytes[fields[0] + 1..fields[1]];
    let flag_bytes = &bytes[fields[1] + 1..fields[2]];
    let net_val_bytes = &bytes[fields[2] + 1..];

    let transaction_id = parse_u32_fast(id_bytes)?;
    let symbol_id = parse_u16_fast(symbol_bytes)?;
    let flag = parse_u8_fast(flag_bytes)?;
    let net_value = parse_i64_fast(net_val_bytes)?;

    Ok(TransactionRecord {
        transaction_id,
        symbol_id,
        flag,
        _reserved: 0,
        net_value,
    })
}

// Parser konversi ASCII integer kencang tanpa overhead abstraksi format library umum
#[inline(always)]
fn parse_u32_fast(bytes: &[u8]) -> Result<u32, EngineError> {
    if bytes.is_empty() {
        return Err(EngineError::MalformedPayload);
    }
    let mut acc: u32 = 0;
    for &b in bytes {
        if !b.is_ascii_digit() {
            return Err(EngineError::MalformedPayload);
        }
        acc = acc
            .checked_mul(10)
            .and_then(|v| v.checked_add((b - b'0') as u32))
            .ok_or(EngineError::CalculationOverflow)?;
    }
    Ok(acc)
}

#[inline(always)]
fn parse_u16_fast(bytes: &[u8]) -> Result<u16, EngineError> {
    parse_u32_fast(bytes).and_then(|v| {
        if v <= u16::MAX as u32 {
            Ok(v as u16)
        } else {
            Err(EngineError::CalculationOverflow)
        }
    })
}

#[inline(always)]
fn parse_u8_fast(bytes: &[u8]) -> Result<u8, EngineError> {
    parse_u32_fast(bytes).and_then(|v| {
        if v <= u8::MAX as u32 {
            Ok(v as u8)
        } else {
            Err(EngineError::CalculationOverflow)
        }
    })
}

#[inline(always)]
fn parse_i64_fast(bytes: &[u8]) -> Result<i64, EngineError> {
    if bytes.is_empty() {
        return Err(EngineError::MalformedPayload);
    }
    let (is_negative, slice) = match bytes[0] {
        b'-' => (true, &bytes[1..]),
        b'+' => (false, &bytes[1..]),
        _ => (false, bytes),
    };

    if slice.is_empty() {
        return Err(EngineError::MalformedPayload);
    }

    let mut acc: i64 = 0;
    for &b in slice {
        if !b.is_ascii_digit() {
            return Err(EngineError::MalformedPayload);
        }
        let digit = (b - b'0') as i64;
        acc = acc
            .checked_mul(10)
            .and_then(|v| v.checked_add(digit))
            .ok_or(EngineError::CalculationOverflow)?;
    }

    if is_negative {
        acc = acc.checked_neg().ok_or(EngineError::CalculationOverflow)?;
    }

    Ok(acc)
}

/// Pemrosesan batch tanpa alokasi heap: Buffer keluaran dialokasikan di awal (Caller-Provided)
pub fn process_batch_zero_alloc(
    lines: &[&str],
    out_records: &mut [TransactionRecord],
) -> Result<usize, EngineError> {
    if out_records.len() < lines.len() {
        return Err(EngineError::CapacityExceeded);
    }

    let mut count = 0;
    for &line in lines {
        let rec = parse_log_line_zero_alloc(line)?;
        // Penulisan contiguous memory secara sequential (Cache write friendly)
        out_records[count] = rec;
        count += 1;
    }

    Ok(count)
}
