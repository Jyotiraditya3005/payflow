package com.payflow.gateway.routes;

import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import reactor.core.publisher.Mono;

import java.time.Instant;
import java.util.Map;

/**
 * Circuit breaker fallback endpoints.
 * Called when a downstream service is unavailable.
 */
@Slf4j
@RestController
@RequestMapping("/fallback")
public class FallbackController {

    @GetMapping
    @PostMapping
    public Mono<ResponseEntity<Map<String, Object>>> globalFallback() {
        log.warn("Circuit breaker triggered — global fallback");
        return Mono.just(ResponseEntity
                .status(HttpStatus.SERVICE_UNAVAILABLE)
                .body(Map.of(
                        "error_code", "SERVICE_UNAVAILABLE",
                        "message", "Service temporarily unavailable. Please retry in a moment.",
                        "timestamp", Instant.now().toString(),
                        "retry_after", 10
                )));
    }

    @GetMapping("/payment")
    @PostMapping("/payment")
    public Mono<ResponseEntity<Map<String, Object>>> paymentFallback() {
        log.warn("Circuit breaker triggered — payment service fallback");
        return Mono.just(ResponseEntity
                .status(HttpStatus.SERVICE_UNAVAILABLE)
                .body(Map.of(
                        "error_code", "PAYMENT_SERVICE_UNAVAILABLE",
                        "message", "Payment processing is temporarily unavailable. Your request has NOT been processed. Please retry.",
                        "timestamp", Instant.now().toString(),
                        "retry_after", 15,
                        "support", "payments@payflow.io"
                )));
    }

    @GetMapping("/auth")
    @PostMapping("/auth")
    public Mono<ResponseEntity<Map<String, Object>>> authFallback() {
        log.warn("Circuit breaker triggered — auth service fallback");
        return Mono.just(ResponseEntity
                .status(HttpStatus.SERVICE_UNAVAILABLE)
                .body(Map.of(
                        "error_code", "AUTH_SERVICE_UNAVAILABLE",
                        "message", "Authentication service is temporarily unavailable.",
                        "timestamp", Instant.now().toString()
                )));
    }

    @GetMapping("/health")
    public Mono<ResponseEntity<Map<String, Object>>> healthFallback() {
        return Mono.just(ResponseEntity
                .status(HttpStatus.OK)
                .body(Map.of(
                        "status", "degraded",
                        "gateway", "healthy",
                        "downstream", "unavailable",
                        "timestamp", Instant.now().toString()
                )));
    }
}
