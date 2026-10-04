package com.enterprise.persistence.fundamental;

import com.zaxxer.hikari.HikariConfig;
import com.zaxxer.hikari.HikariDataSource;

import javax.sql.DataSource;
import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.util.ArrayList;
import java.util.List;

public class HighPerformanceJdbcEngine {

    private final DataSource dataSource;

    public HighPerformanceJdbcEngine() {
        this.dataSource = initializePool();
    }

    private DataSource initializePool() {
        HikariConfig config = new HikariConfig();
        config.setJdbcUrl("jdbc:postgresql://localhost:5432/trade_db");
        config.setUsername("db_operator");
        config.setPassword("SuperSecureSecret123!");
        
        // Tuning Ukuran Pool Berdasarkan Kapasitas Core DB (cth: 4 Core DB)
        config.setMaximumPoolSize(9);
        config.setMinimumIdle(9); // Fixed pool size menghilangkan overhead dynamic allocation
        
        // Timeout & Leak Detection
        config.setConnectionTimeout(3000); // 3 detik
        config.setIdleTimeout(600000);
        config.setMaxLifetime(1800000); // 30 menit
        config.setLeakDetectionThreshold(5000); // Trigger warning jika connection ditahan > 5s
        
        // Performance Caching Flags untuk JDBC Driver
        config.addDataSourceProperty("cachePrepStmts", "true");
        config.addDataSourceProperty("prepStmtCacheSize", "250");
        config.addDataSourceProperty("prepStmtCacheSqlLimit", "2048");
        config.addDataSourceProperty("useServerPrepStmts", "true");

        return new HikariDataSource(config);
    }

    public record AuditLogRecord(long id, String source, String payload) {}

    public void executeHighThroughputBatch(List<AuditLogRecord> records) throws SQLException {
        final String sql = "INSERT INTO audit_logs (id, source, payload) VALUES (?, ?, ?)";

        try (Connection connection = dataSource.getConnection()) {
            // Nonaktifkan auto-commit untuk mengontrol batas transaksi secara eksplisit
            connection.setAutoCommit(false);

            try (PreparedStatement stmt = connection.prepareStatement(sql)) {
                int batchCounter = 0;
                final int BATCH_SIZE = 1000;

                for (AuditLogRecord record : records) {
                    stmt.setLong(1, record.id());
                    stmt.setString(2, record.source());
                    stmt.setString(3, record.payload());
                    stmt.addBatch();

                    batchCounter++;
                    if (batchCounter % BATCH_SIZE == 0) {
                        stmt.executeBatch();
                        stmt.clearBatch(); // Kosongkan memori buffer JDBC statement
                    }
                }

                // Eksekusi sisa query yang belum mencapai threshold batch
                if (batchCounter % BATCH_SIZE != 0) {
                    stmt.executeBatch();
                }

                connection.commit(); // Atomic commit ke disk storage
            } catch (SQLException ex) {
                connection.rollback();
                throw ex;
            } finally {
                connection.setAutoCommit(true);
            }
        }
    }

    public List<AuditLogRecord> streamMassiveResultSet(long minId) throws SQLException {
        final String sql = "SELECT id, source, payload FROM audit_logs WHERE id >= ?";
        List<AuditLogRecord> results = new ArrayList<>();

        try (Connection connection = dataSource.getConnection();
             PreparedStatement stmt = connection.prepareStatement(sql, 
                     ResultSet.TYPE_FORWARD_ONLY, 
                     ResultSet.CONCUR_READ_ONLY)) {

            // Mencegah JDBC memuat seluruh data ke JVM Heap sekaligus
            stmt.setFetchSize(500);
            stmt.setLong(1, minId);

            try (ResultSet rs = stmt.executeQuery()) {
                while (rs.next()) {
                    results.add(new AuditLogRecord(
                            rs.getLong("id"),
                            rs.getString("source"),
                            rs.getString("payload")
                    ));
                }
            }
        }
        return results;
    }
}
