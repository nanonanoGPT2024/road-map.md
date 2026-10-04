package com.enterprise.security.config;

import com.enterprise.security.converter.EnterpriseJwtAuthenticationConverter;
import com.enterprise.security.filter.DistributedTokenRevocationFilter;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.convert.converter.Converter;
import org.springframework.http.HttpMethod;
import org.springframework.security.authentication.AbstractAuthenticationToken;
import org.springframework.security.config.annotation.method.configuration.EnableMethodSecurity;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.config.annotation.web.configurers.AbstractHttpConfigurer;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.oauth2.jwt.JwtDecoder;
import org.springframework.security.oauth2.jwt.NimbusJwtDecoder;
import org.springframework.security.oauth2.server.resource.web.authentication.BearerTokenAuthenticationFilter;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.header.writers.ReferrerPolicyHeaderWriter;

import java.time.Duration;

@Configuration
@EnableWebSecurity
@EnableMethodSecurity(prePostEnabled = true, securedEnabled = true, jsr250Enabled = true)
public class SecurityConfiguration {

    private final DistributedTokenRevocationFilter revocationFilter;
    private final EnterpriseSecurityProperties securityProperties;

    public SecurityConfiguration(DistributedTokenRevocationFilter revocationFilter,
                                 EnterpriseSecurityProperties securityProperties) {
        this.revocationFilter = revocationFilter;
        this.securityProperties = securityProperties;
    }

    @Bean
    public SecurityFilterChain enterpriseSecurityFilterChain(
            HttpSecurity http,
            Converter<Jwt, ? extends AbstractAuthenticationToken> jwtAuthenticationConverter,
            JwtDecoder jwtDecoder) throws Exception {

        http
            // 1. Matikan proteksi CSRF karena arsitektur API sepenuhnya stateless menggunakan Bearer Tokens
            .csrf(AbstractHttpConfigurer::disable)

            // 2. Matikan manajemen state session pada kontainer servlet (Stateless API)
            .sessionManagement(session -> 
                session.sessionCreationPolicy(SessionCreationPolicy.STATELESS)
            )

            // 3. Konfigurasi Security Headers berstandar Enterprise
            .headers(headers -> headers
                .contentSecurityPolicy(csp -> csp.policyDirectives("default-src 'self'; frame-ancestors 'none';"))
                .frameOptions(frameOptions -> frameOptions.deny())
                .httpStrictTransportSecurity(hsts -> hsts
                    .includeSubDomains(true)
                    .maxAgeSeconds(31536000)
                    .preload(true)
                )
                .referrerPolicy(referrer -> 
                    referrer.policy(ReferrerPolicyHeaderWriter.ReferrerPolicy.STRICT_ORIGIN_WHEN_CROSS_ORIGIN)
                )
            )

            // 4. Konfigurasi Otorisasi Jalur HTTP (Request-Level Authorization)
            .authorizeHttpRequests(auth -> auth
                .requestMatchers(HttpMethod.GET, "/actuator/health", "/actuator/info").permitAll()
                .requestMatchers(HttpMethod.OPTIONS, "/**").permitAll()
                .requestMatchers("/api/v1/public/**").permitAll()
                .requestMatchers("/api/v1/admin/**").hasRole("ENTERPRISE_ADMIN")
                .anyRequest().authenticated()
            )

            // 5. Registrasi Filter Custom Pembatalan Token Terdistribusi sebelum Filter Autentikasi Inti
            .addFilterBefore(revocationFilter, BearerTokenAuthenticationFilter.class)

            // 6. Konfigurasi OAuth 2.0 Resource Server dengan Custom Converter
            .oauth2ResourceServer(oauth2 -> oauth2
                .jwt(jwt -> jwt
                    .decoder(jwtDecoder)
                    .jwtAuthenticationConverter(jwtAuthenticationConverter)
                )
            );

        return http.build();
    }

    @Bean
    public Converter<Jwt, ? extends AbstractAuthenticationToken> jwtAuthenticationConverter() {
        return new EnterpriseJwtAuthenticationConverter();
    }

    @Bean
    public JwtDecoder jwtDecoder() {
        NimbusJwtDecoder jwtDecoder = NimbusJwtDecoder
                .withJwkSetUri(securityProperties.getJwksUri())
                .build();

        // Validasi toleransi skew waktu kriptografis (maksimum 60 detik)
        jwtDecoder.setJwtValidator(
                EnterpriseJwtValidators.createDefaultWithIssuerAndSkew(
                        securityProperties.getIssuer(),
                        Duration.ofSeconds(60)
                )
        );

        return jwtDecoder;
    }
}
