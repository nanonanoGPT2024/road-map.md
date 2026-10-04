// File: src/test/scala/com/enterprise/settlement/SettlementRepositoryITSpec.scala
package com.enterprise.settlement

import munit.CatsEffectSuite
import com.dimafeng.testcontainers.munit.TestContainerForAll
import com.dimafeng.testcontainers.PostgreSQLContainer
import cats.effect.IO
import org.flywaydb.core.Flyway
import java.sql.DriverManager
import java.util.UUID

class SettlementRepositoryITSpec extends CatsEffectSuite with TestContainerForAll {

  override val containerDef: PostgreSQLContainer.Def = PostgreSQLContainer.Def(
    dockerImageName = "postgres:16-alpine"
  )

  def runMigrations(container: PostgreSQLContainer): Unit = {
    val flyway = Flyway.configure()
      .dataSource(container.jdbcUrl, container.username, container.password)
      .load()
    
    // Inisialisasi skema secara dinamis untuk integration testing
    val conn = DriverManager.getConnection(container.jdbcUrl, container.username, container.password)
    try {
      val stmt = conn.createStatement()
      stmt.execute(
        """
        CREATE TABLE IF NOT EXISTS settlements (
          id UUID PRIMARY KEY,
          account_id VARCHAR(64) NOT NULL,
          amount NUMERIC(18, 4) NOT NULL,
          status VARCHAR(32) NOT NULL
        );
        """
      )
    } finally {
      conn.close()
    }
  }

  test("Repository harus menyimpan dan membaca SettlementRecord secara deterministik dari database PostgreSQL") {
    withContainers { postgres =>
      runMigrations(postgres)
      
      val acquireConnection = IO.blocking(
        DriverManager.getConnection(postgres.jdbcUrl, postgres.username, postgres.password)
      )
      
      val repo = new SettlementRepository(acquireConnection)
      val recordId = UUID.randomUUID()
      val settlement = SettlementRecord(recordId, "ACC-GLOBAL-778", BigDecimal("45000.50"), "PENDING")

      for {
        _         <- repo.insert(settlement)
        retrieved <- repo.findById(recordId)
      } yield {
        assertEquals(retrieved, Some(settlement))
      }
    }
  }
}
