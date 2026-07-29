package com.payflow.gateway.filter;

import io.jsonwebtoken.Claims;
import io.jsonwebtoken.JwtException;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.cloud.gateway.filter.GatewayFilter;
import org.springframework.cloud.gateway.filter.factory.AbstractGatewayFilterFactory;
import org.springframework.core.io.buffer.DataBuffer;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.server.reactive.ServerHttpRequest;
import org.springframework.http.server.reactive.ServerHttpResponse;
import org.springframework.stereotype.Component;
import org.springframework.web.server.ServerWebExchange;
import reactor.core.publisher.Mono;

import javax.crypto.SecretKey;
import java.nio.charset.StandardCharsets;
import java.util.List;

/**
 * JWT Authentication Filter
 *
 * Validates Bearer tokens on every request before routing to downstream services.
 * Extracts user claims and forwards them as request headers so services
 * don't need to re-validate.
 *
 * Public paths (login, register, health) bypass this filter.
 */
@Slf4j
@Component
public class AuthenticationFilter extends AbstractGatewayFilterFactory<AuthenticationFilter.Config> {

    @Value("${payflow.jwt.secret}")
    private String jwtSecret;

    @Value("${payflow.gateway.public-paths}")
    private List<String> publicPaths;

    public AuthenticationFilter() {
        super(Config.class);
    }

    @Override
    public GatewayFilter apply(Config config) {
        return (exchange, chain) -> {
            ServerHttpRequest request = exchange.getRequest();
            String path = request.getURI().getPath();

            // Skip auth for public paths
            if (isPublicPath(path)) {
                return chain.filter(exchange);
            }

            // Extract Authorization header
            String authHeader = request.getHeaders().getFirst(HttpHeaders.AUTHORIZATION);
            if (authHeader == null || !authHeader.startsWith("Bearer ")) {
                return unauthorizedResponse(exchange, "Missing or invalid Authorization header");
            }

            String token = authHeader.substring(7);

            try {
                Claims claims = validateToken(token);

                // Forward user context to downstream services via headers
                ServerHttpRequest mutatedRequest = request.mutate()
                        .header("X-User-ID", claims.getSubject())
                        .header("X-User-Role", claims.get("role", String.class))
                        .header("X-Merchant-ID", claims.get("merchant_id", String.class) != null
                                ? claims.get("merchant_id", String.class) : "")
                        .header("X-Token-Expiry", String.valueOf(claims.getExpiration().getTime()))
                        .build();

                log.debug("Auth OK: userId={} role={} path={}",
                        claims.getSubject(), claims.get("role"), path);

                return chain.filter(exchange.mutate().request(mutatedRequest).build());

            } catch (JwtException e) {
                log.warn("JWT validation failed: {} for path {}", e.getMessage(), path);
                return unauthorizedResponse(exchange, "Invalid or expired token: " + e.getMessage());
            }
        };
    }

    private Claims validateToken(String token) {
        SecretKey key = Keys.hmacShaKeyFor(jwtSecret.getBytes(StandardCharsets.UTF_8));
        return Jwts.parser()
                .verifyWith(key)
                .build()
                .parseSignedClaims(token)
                .getPayload();
    }

    private boolean isPublicPath(String path) {
        return publicPaths.stream().anyMatch(p -> {
            if (p.endsWith("/**")) {
                return path.startsWith(p.substring(0, p.length() - 3));
            }
            return path.equals(p);
        });
    }

    private Mono<Void> unauthorizedResponse(ServerWebExchange exchange, String message) {
        ServerHttpResponse response = exchange.getResponse();
        response.setStatusCode(HttpStatus.UNAUTHORIZED);
        response.getHeaders().setContentType(MediaType.APPLICATION_JSON);

        String body = String.format(
                "{\"error_code\":\"UNAUTHORIZED\",\"message\":\"%s\"}", message
        );
        DataBuffer buffer = response.bufferFactory()
                .wrap(body.getBytes(StandardCharsets.UTF_8));

        return response.writeWith(Mono.just(buffer));
    }

    public static class Config {
        // Config class required by AbstractGatewayFilterFactory
    }
}
