# Multi-stage build for Spring Boot API Gateway
FROM eclipse-temurin:21-jdk-alpine AS builder

WORKDIR /workspace

# Cache Maven dependencies layer
COPY pom.xml .
RUN --mount=type=cache,target=/root/.m2 \
    mvn dependency:go-offline -q 2>/dev/null || true

COPY src ./src

RUN --mount=type=cache,target=/root/.m2 \
    mvn clean package -DskipTests -q && \
    mkdir -p target/extracted && \
    java -Djarmode=layertools -jar target/*.jar extract --destination target/extracted

# Runtime image — minimal JRE only
FROM eclipse-temurin:21-jre-alpine AS runtime

RUN addgroup -S payflow && adduser -S payflow -G payflow
WORKDIR /app
USER payflow

COPY --from=builder /workspace/target/extracted/dependencies/ ./
COPY --from=builder /workspace/target/extracted/spring-boot-loader/ ./
COPY --from=builder /workspace/target/extracted/snapshot-dependencies/ ./
COPY --from=builder /workspace/target/extracted/application/ ./

EXPOSE 8080

ENV JAVA_OPTS="-XX:MaxRAMPercentage=75 -XX:+UseG1GC -XX:+UseContainerSupport -Djava.security.egd=file:/dev/./urandom"

HEALTHCHECK --interval=30s --timeout=10s --start-period=45s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://localhost:8080/actuator/health || exit 1

ENTRYPOINT ["sh", "-c", "java $JAVA_OPTS org.springframework.boot.loader.launch.JarLauncher"]
