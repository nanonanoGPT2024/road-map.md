use std::fs::File;
use std::io::{self, BufRead, BufReader, BufWriter, Write};
use std::path::Path;
use thiserror::Error;

// Domain Errors didefinisikan secara deklaratif dengan thiserror
#[derive(Error, Debug)]
pub enum IngestionError {
    #[error("I/O error fatal pada storage sistem: {0}")]
    FatalIo(#[from] io::Error),

    #[error("Gagal melakukan serialisasi metrik akhir: {0}")]
    SerializationFailed(String),
}

#[derive(Error, Debug)]
pub enum RecordError {
    #[error("Bidang transaksi tidak lengkap pada baris {line_no}: '{raw}'")]
    IncompleteFields { line_no: usize, raw: String },

    #[error("Format ID transaksi tidak valid '{val}' pada baris {line_no}")]
    InvalidTransactionId { line_no: usize, val: String },

    #[error("Nominal transaksi tidak valid pada baris {line_no}: {source}")]
    InvalidAmount {
        line_no: usize,
        #[source]
        source: std::num::ParseFloatError,
    },
}

#[derive(Debug, PartialEq)]
pub struct TransactionRecord {
    pub tx_id: u64,
    pub amount: f64,
    pub account_id: String,
}

#[derive(Default, Debug)]
pub struct IngestionMetrics {
    pub total_processed: usize,
    pub successful_records: usize,
    pub failed_records: usize,
    pub total_volume: f64,
}

pub struct TransactionIngestor;

impl TransactionIngestor {
    /// Melakukan parsing terhadap satu baris data
    fn parse_line(line_no: usize, raw: &str) -> Result<TransactionRecord, RecordError> {
        let fields: Vec<&str> = raw.split(',').map(str::trim).collect();

        if fields.len() != 3 {
            return Err(RecordError::IncompleteFields {
                line_no,
                raw: raw.to_string(),
            });
        }

        let tx_id = fields[0]
            .parse::<u64>()
            .map_err(|_| RecordError::InvalidTransactionId {
                line_no,
                val: fields[0].to_string(),
            })?;

        let amount = fields[1]
            .parse::<f64>()
            .map_err(|source| RecordError::InvalidAmount { line_no, source })?;

        let account_id = fields[2].to_string();

        Ok(TransactionRecord {
            tx_id,
            amount,
            account_id,
        })
    }

    /// Memproses berkas masukan secara streaming dan menulis laporan error audit
    pub fn process_stream<P1: AsRef<Path>, P2: AsRef<Path>>(
        input_path: P1,
        audit_error_path: P2,
    ) -> Result<IngestionMetrics, IngestionError> {
        let input_file = File::open(input_path)?;
        let mut reader = BufReader::with_capacity(128 * 1024, input_file); // Buffer 128KB

        let audit_file = File::create(audit_error_path)?;
        let mut audit_writer = BufWriter::with_capacity(64 * 1024, audit_file); // Buffer 64KB

        let mut metrics = IngestionMetrics::default();
        let mut line_buffer = String::new();
        let mut line_no = 0;

        loop {
            line_buffer.clear(); // Re-use alokasi memori heap String
            line_no += 1;

            let bytes_read = reader.read_line(&mut line_buffer)?;
            if bytes_read == 0 {
                break; // Akhir dari stream (EOF)
            }

            let trimmed = line_buffer.trim_end();
            if trimmed.is_empty() {
                continue;
            }

            metrics.total_processed += 1;

            match Self::parse_line(line_no, trimmed) {
                Ok(record) => {
                    metrics.successful_records += 1;
                    metrics.total_volume += record.amount;
                }
                Err(rec_err) => {
                    metrics.failed_records += 1;
                    // Tulis galat audit ke file disk secara berpenyangga
                    writeln!(audit_writer, "[WARN AUDIT] {}", rec_err)?;
                }
            }
        }

        // Pastikan seluruh sisa buffer ditulis ke media fisik
        audit_writer.flush()?;

        Ok(metrics)
    }
}
