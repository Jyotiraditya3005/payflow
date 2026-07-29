package com.payflow.gateway.filter;

import lombok.extern.slf4j.Slf4j;
import org.springframework.cloud.gateway.filter.GlobalFilter;
import org.springframework.cloud.gateway.filter.GatewayFilterChain;
import org.springframework.core.Ordered;
import org.springframework.http.server.reactive.ServerHttpRequest;
import org.springframework.http.server.reactive.ServerHttpResponse;
import org.springframework.stereotype.Component;
import org.springframework.web.server.ServerWebExchange;
import reactor.core.publisher.Mono;

import java.time.Instant;
import java.util.UUID;

/**
 * Global filter that:
 * 1. Assigns a unique X-Request-ID to every request (or propagates existing)
 * 2. Logs request/response with timing for observability
 * 3. Adds timing headers to response
 */
@Slf4j
@Component
public class RequestLoggingFilter implements GlobalFilter, Ordered {

    @Override
    public Mono<Void> filter(ServerWebExchange exchange, GatewayFilterChain chain) {
        ServerHttpRequest request = exchange.getRequest();
        long startTime = System.currentTimeMillis();

        // Assign request ID for distributed tracing
        String requestId = request.getHeaders().getFirst("X-Request-ID");
        if (requestId == null || requestId.isBlank()) {
            requestId = UUID.randomUUID().toString();
        }
        final String finalRequestId = requestId;

        // Mutate request to include request ID downstream
        ServerHttpRequest mutatedRequest = request.mutate()
                .header("X-Request-ID", finalRequestId)
                .build();

        log.info("→ {} {} [{}]",
                request.getMethod(),
                request.getURI().getPath(),
                finalRequestId);

        return chain.filter(exchange.mutate().request(mutatedRequest).build())
                .then(Mono.fromRunnable(() -> {
                    ServerHttpResponse response = exchange.getResponse();
                    long duration = System.currentTimeMillis() - startTime;

                    // Add timing headers to response
                    response.getHeaders().add("X-Request-ID", finalRequestId);
                    response.getHeaders().add("X-Response-Time", duration + "ms");

                    log.info("← {} {} {} {}ms [{}]",
                            request.getMethod(),
                            request.getURI().getPath(),
                            response.getStatusCode() != null ? response.getStatusCode().value() : "?",
                            duration,
                            finalRequestId);
                }));
    }

    @Override
    public int getOrder() {
        return Ordered.HIGHEST_PRECEDENCE; // Run before all other filters
    }
}
