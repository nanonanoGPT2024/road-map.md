package com.enterprise.multitenant.autoconfigure;

import com.enterprise.multitenant.datasource.DynamicTenantRoutingDataSource;
import com.zaxxer.hikari.HikariDataSource;
import io.micrometer.observation.ObservationRegistry;
import org.springframework.boot.autoconfigure.AutoConfiguration;
import org.springframework.boot.autoconfigure.condition.ConditionalOnClass;
import org.springframework.boot.autoconfigure.condition.ConditionalOnMissingBean;
import org.springframework.boot.autoconfigure.jdbc.DataSourceAutoConfiguration;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Primary;

import javax.sql.DataSource;
import java.util.HashMap;
import java.util.Map;

@ConfigurationProperties(prefix = "enterprise.multitenant")
record MultiTenantProperties(
    String defaultTenantId,
    Map<String, String> urls,
    String commonUsername,
    String commonPassword
) {
    public MultiTenantProperties {
        if (urls == null) urls = new HashMap<>();
        if (defaultTenantId == null) defaultTenantId = "master";
    }
}

@AutoConfiguration(before = DataSourceAutoConfiguration.class)
@ConditionalOnClass({DynamicTenantRoutingDataSource.class, HikariDataSource.class})
@EnableConfigurationProperties(MultiTenantProperties.class)
public class DynamicMultiTenantAutoConfiguration {

    @Bean
    @Primary
    @ConditionalOnMissingBean
    public DataSource dynamicRoutingDataSource(
            MultiTenantProperties properties,
            ObservationRegistry observationRegistry) {

        // Instansiasi DataSource Default (Master Data Source)
        HikariDataSource defaultSource = new HikariDataSource();
        defaultSource.setPoolName("TenantPool-Master");
        defaultSource.setJdbcUrl(properties.urls().getOrDefault("master", "jdbc:h2:mem:masterdb"));
        defaultSource.setUsername(properties.commonUsername());
        defaultSource.setPassword(properties.commonPassword());

        DynamicTenantRoutingDataSource routingDataSource = new DynamicTenantRoutingDataSource(defaultSource);

        // Pre-populate DataSources yang didefinisikan di environment
        properties.urls().forEach((tenantId, url) -> {
            if (!"master".equalsIgnoreCase(tenantId)) {
                HikariDataSource ds = new HikariDataSource();
                ds.setPoolName("TenantPool-" + tenantId);
                ds.setJdbcUrl(url);
                ds.setUsername(properties.commonUsername());
                ds.setPassword(properties.commonPassword());
                routingDataSource.addTenantDataSource(tenantId, ds);
            }
        });

        return routingDataSource;
    }
}
