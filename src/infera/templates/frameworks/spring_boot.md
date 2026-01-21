# Spring Boot (Cloud Run / ECS)

## Overview

Deploy Spring Boot applications on container platforms for enterprise-grade Java applications. Spring Boot's convention-over-configuration approach, extensive ecosystem, and production-ready features make it ideal for microservices and enterprise APIs. Supports native image compilation with GraalVM for faster startup.

## Detection Signals

Use this template when:
- `pom.xml` with spring-boot-starter dependency
- `build.gradle` with Spring Boot plugin
- `src/main/java/**/*Application.java` entry point
- `application.properties` or `application.yml`
- Enterprise Java application
- Microservices architecture
- Spring ecosystem (Security, Data, Cloud)

## Architecture

```
                    ┌─────────────────────────────────────────────────────────────────┐
                    │                    Container Platform                            │
                    │                                                                 │
    Internet ──────►│   ┌─────────────────────────────────────────────────────────┐   │
                    │   │                  Load Balancer                           │   │
                    │   │           (Cloud LB / ALB / Ingress)                     │   │
                    │   └─────────────────────────────────────────────────────────┘   │
                    │                            │                                    │
                    │                            ▼                                    │
                    │   ┌─────────────────────────────────────────────────────────┐   │
                    │   │              Container Service                           │   │
                    │   │           (Cloud Run / ECS Fargate)                      │   │
                    │   │                                                         │   │
                    │   │  ┌───────────┐ ┌───────────┐ ┌───────────┐             │   │
                    │   │  │  Spring   │ │  Spring   │ │  Spring   │             │   │
                    │   │  │   Boot    │ │   Boot    │ │   Boot    │             │   │
                    │   │  │           │ │           │ │           │             │   │
                    │   │  │  JVM or   │ │  JVM or   │ │  JVM or   │             │   │
                    │   │  │  Native   │ │  Native   │ │  Native   │             │   │
                    │   │  └───────────┘ └───────────┘ └───────────┘             │   │
                    │   │                                                         │   │
                    │   │  Auto-scaling: 2-20 instances based on CPU/requests    │   │
                    │   └─────────────────────────────────────────────────────────┘   │
                    │                            │                                    │
                    │          ┌─────────────────┼─────────────────┐                  │
                    │          ▼                 ▼                 ▼                  │
                    │   ┌───────────┐     ┌───────────┐     ┌───────────┐            │
                    │   │ PostgreSQL│     │   Redis   │     │  Storage  │            │
                    │   │ (Managed) │     │  (Cache)  │     │ (GCS/S3)  │            │
                    │   └───────────┘     └───────────┘     └───────────┘            │
                    │                                                                 │
                    │   Enterprise-grade • Auto-configuration • Production-ready     │
                    └─────────────────────────────────────────────────────────────────┘
```

## Resources

### GCP (Cloud Run)
| Resource | Purpose | Configuration |
|----------|---------|---------------|
| Cloud Run | Container hosting | 2 vCPU, 2GB RAM |
| Cloud SQL | PostgreSQL | db-custom-2-8192 |
| Memorystore | Redis | 1GB |
| Cloud Storage | File uploads | Regional |
| Secret Manager | Credentials | Auto-mount |

### AWS (ECS Fargate)
| Resource | Purpose | Configuration |
|----------|---------|---------------|
| ECS Fargate | Container hosting | 2 vCPU, 4GB |
| RDS Aurora | PostgreSQL | Serverless v2 |
| ElastiCache | Redis | cache.t3.small |
| S3 | File storage | Standard |
| Secrets Manager | Credentials | ECS integration |

## Configuration

### Project Structure
```
my-spring-app/
├── src/
│   ├── main/
│   │   ├── java/com/example/demo/
│   │   │   ├── DemoApplication.java
│   │   │   ├── config/
│   │   │   │   ├── SecurityConfig.java
│   │   │   │   └── WebConfig.java
│   │   │   ├── controller/
│   │   │   │   ├── UserController.java
│   │   │   │   └── HealthController.java
│   │   │   ├── service/
│   │   │   │   └── UserService.java
│   │   │   ├── repository/
│   │   │   │   └── UserRepository.java
│   │   │   ├── entity/
│   │   │   │   └── User.java
│   │   │   ├── dto/
│   │   │   │   ├── CreateUserDto.java
│   │   │   │   └── UserResponse.java
│   │   │   └── exception/
│   │   │       └── GlobalExceptionHandler.java
│   │   └── resources/
│   │       ├── application.yml
│   │       ├── application-prod.yml
│   │       └── db/migration/
│   │           └── V1__init.sql
│   └── test/
├── pom.xml
├── Dockerfile
└── docker-compose.yml
```

### pom.xml
```xml
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0
         https://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>

    <parent>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-parent</artifactId>
        <version>3.2.0</version>
    </parent>

    <groupId>com.example</groupId>
    <artifactId>demo</artifactId>
    <version>1.0.0</version>
    <packaging>jar</packaging>

    <properties>
        <java.version>21</java.version>
    </properties>

    <dependencies>
        <!-- Web -->
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-web</artifactId>
        </dependency>

        <!-- Validation -->
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-validation</artifactId>
        </dependency>

        <!-- Data JPA -->
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-data-jpa</artifactId>
        </dependency>

        <!-- PostgreSQL -->
        <dependency>
            <groupId>org.postgresql</groupId>
            <artifactId>postgresql</artifactId>
            <scope>runtime</scope>
        </dependency>

        <!-- Redis Cache -->
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-data-redis</artifactId>
        </dependency>

        <!-- Actuator -->
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-actuator</artifactId>
        </dependency>

        <!-- Security -->
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-security</artifactId>
        </dependency>

        <!-- OpenAPI -->
        <dependency>
            <groupId>org.springdoc</groupId>
            <artifactId>springdoc-openapi-starter-webmvc-ui</artifactId>
            <version>2.3.0</version>
        </dependency>

        <!-- Flyway -->
        <dependency>
            <groupId>org.flywaydb</groupId>
            <artifactId>flyway-core</artifactId>
        </dependency>

        <!-- Lombok -->
        <dependency>
            <groupId>org.projectlombok</groupId>
            <artifactId>lombok</artifactId>
            <optional>true</optional>
        </dependency>

        <!-- Test -->
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-test</artifactId>
            <scope>test</scope>
        </dependency>
    </dependencies>

    <build>
        <plugins>
            <plugin>
                <groupId>org.springframework.boot</groupId>
                <artifactId>spring-boot-maven-plugin</artifactId>
                <configuration>
                    <excludes>
                        <exclude>
                            <groupId>org.projectlombok</groupId>
                            <artifactId>lombok</artifactId>
                        </exclude>
                    </excludes>
                </configuration>
            </plugin>
        </plugins>
    </build>

    <!-- Native image support -->
    <profiles>
        <profile>
            <id>native</id>
            <build>
                <plugins>
                    <plugin>
                        <groupId>org.graalvm.buildtools</groupId>
                        <artifactId>native-maven-plugin</artifactId>
                    </plugin>
                </plugins>
            </build>
        </profile>
    </profiles>
</project>
```

### Application Properties
```yaml
# src/main/resources/application.yml
spring:
  application:
    name: demo-api

  profiles:
    active: ${SPRING_PROFILES_ACTIVE:dev}

  datasource:
    url: ${DATABASE_URL:jdbc:postgresql://localhost:5432/demo}
    username: ${DATABASE_USERNAME:demo}
    password: ${DATABASE_PASSWORD:demo}
    hikari:
      maximum-pool-size: 10
      minimum-idle: 5
      connection-timeout: 20000

  jpa:
    hibernate:
      ddl-auto: validate
    open-in-view: false
    properties:
      hibernate:
        format_sql: true
        jdbc:
          time_zone: UTC

  flyway:
    enabled: true
    locations: classpath:db/migration

  data:
    redis:
      host: ${REDIS_HOST:localhost}
      port: ${REDIS_PORT:6379}

  cache:
    type: redis
    redis:
      time-to-live: 3600000

server:
  port: ${PORT:8080}
  shutdown: graceful
  compression:
    enabled: true
    mime-types: application/json,text/html,text/plain

management:
  endpoints:
    web:
      exposure:
        include: health,info,metrics,prometheus
  endpoint:
    health:
      show-details: when_authorized
      probes:
        enabled: true

springdoc:
  api-docs:
    path: /api-docs
  swagger-ui:
    path: /swagger-ui

logging:
  level:
    root: INFO
    com.example.demo: DEBUG
  pattern:
    console: '{"timestamp":"%d{ISO8601}","level":"%p","logger":"%c","message":"%m"}%n'
```

### Production Properties
```yaml
# src/main/resources/application-prod.yml
spring:
  jpa:
    show-sql: false

  datasource:
    hikari:
      maximum-pool-size: 20

logging:
  level:
    root: WARN
    com.example.demo: INFO

management:
  endpoints:
    web:
      exposure:
        include: health,prometheus
```

### Main Application
```java
// src/main/java/com/example/demo/DemoApplication.java
package com.example.demo;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.cache.annotation.EnableCaching;

@SpringBootApplication
@EnableCaching
public class DemoApplication {
    public static void main(String[] args) {
        SpringApplication.run(DemoApplication.class, args);
    }
}
```

### User Entity
```java
// src/main/java/com/example/demo/entity/User.java
package com.example.demo.entity;

import jakarta.persistence.*;
import lombok.Data;
import lombok.NoArgsConstructor;
import lombok.AllArgsConstructor;
import org.hibernate.annotations.CreationTimestamp;
import org.hibernate.annotations.UpdateTimestamp;

import java.time.LocalDateTime;
import java.util.UUID;

@Entity
@Table(name = "users")
@Data
@NoArgsConstructor
@AllArgsConstructor
public class User {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    private UUID id;

    @Column(unique = true, nullable = false)
    private String email;

    @Column(nullable = false)
    private String name;

    @Column(nullable = false)
    private String password;

    @Column(name = "is_active")
    private boolean active = true;

    @CreationTimestamp
    @Column(name = "created_at", updatable = false)
    private LocalDateTime createdAt;

    @UpdateTimestamp
    @Column(name = "updated_at")
    private LocalDateTime updatedAt;
}
```

### User Repository
```java
// src/main/java/com/example/demo/repository/UserRepository.java
package com.example.demo.repository;

import com.example.demo.entity.User;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.Optional;
import java.util.UUID;

@Repository
public interface UserRepository extends JpaRepository<User, UUID> {
    Optional<User> findByEmail(String email);
    boolean existsByEmail(String email);
    Page<User> findByActiveTrue(Pageable pageable);
}
```

### User Service
```java
// src/main/java/com/example/demo/service/UserService.java
package com.example.demo.service;

import com.example.demo.dto.CreateUserDto;
import com.example.demo.dto.UserResponse;
import com.example.demo.entity.User;
import com.example.demo.exception.ResourceNotFoundException;
import com.example.demo.exception.ConflictException;
import com.example.demo.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.cache.annotation.CacheEvict;
import org.springframework.cache.annotation.Cacheable;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.UUID;

@Service
@RequiredArgsConstructor
public class UserService {

    private final UserRepository userRepository;
    private final PasswordEncoder passwordEncoder;

    @Transactional(readOnly = true)
    public Page<UserResponse> findAll(Pageable pageable) {
        return userRepository.findByActiveTrue(pageable)
                .map(UserResponse::fromEntity);
    }

    @Transactional(readOnly = true)
    @Cacheable(value = "users", key = "#id")
    public UserResponse findById(UUID id) {
        return userRepository.findById(id)
                .map(UserResponse::fromEntity)
                .orElseThrow(() -> new ResourceNotFoundException("User not found: " + id));
    }

    @Transactional
    public UserResponse create(CreateUserDto dto) {
        if (userRepository.existsByEmail(dto.getEmail())) {
            throw new ConflictException("Email already exists: " + dto.getEmail());
        }

        User user = new User();
        user.setEmail(dto.getEmail());
        user.setName(dto.getName());
        user.setPassword(passwordEncoder.encode(dto.getPassword()));

        return UserResponse.fromEntity(userRepository.save(user));
    }

    @Transactional
    @CacheEvict(value = "users", key = "#id")
    public UserResponse update(UUID id, CreateUserDto dto) {
        User user = userRepository.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("User not found: " + id));

        user.setName(dto.getName());
        if (dto.getPassword() != null && !dto.getPassword().isEmpty()) {
            user.setPassword(passwordEncoder.encode(dto.getPassword()));
        }

        return UserResponse.fromEntity(userRepository.save(user));
    }

    @Transactional
    @CacheEvict(value = "users", key = "#id")
    public void delete(UUID id) {
        if (!userRepository.existsById(id)) {
            throw new ResourceNotFoundException("User not found: " + id);
        }
        userRepository.deleteById(id);
    }
}
```

### User Controller
```java
// src/main/java/com/example/demo/controller/UserController.java
package com.example.demo.controller;

import com.example.demo.dto.CreateUserDto;
import com.example.demo.dto.UserResponse;
import com.example.demo.service.UserService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.*;

import java.util.UUID;

@RestController
@RequestMapping("/api/v1/users")
@RequiredArgsConstructor
@Tag(name = "Users", description = "User management API")
public class UserController {

    private final UserService userService;

    @GetMapping
    @Operation(summary = "List all users")
    public Page<UserResponse> list(Pageable pageable) {
        return userService.findAll(pageable);
    }

    @GetMapping("/{id}")
    @Operation(summary = "Get user by ID")
    public UserResponse get(@PathVariable UUID id) {
        return userService.findById(id);
    }

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    @Operation(summary = "Create user")
    public UserResponse create(@Valid @RequestBody CreateUserDto dto) {
        return userService.create(dto);
    }

    @PutMapping("/{id}")
    @Operation(summary = "Update user")
    public UserResponse update(@PathVariable UUID id, @Valid @RequestBody CreateUserDto dto) {
        return userService.update(id, dto);
    }

    @DeleteMapping("/{id}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    @Operation(summary = "Delete user")
    public void delete(@PathVariable UUID id) {
        userService.delete(id);
    }
}
```

### Global Exception Handler
```java
// src/main/java/com/example/demo/exception/GlobalExceptionHandler.java
package com.example.demo.exception;

import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.http.ProblemDetail;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

import java.time.Instant;

@RestControllerAdvice
@Slf4j
public class GlobalExceptionHandler {

    @ExceptionHandler(ResourceNotFoundException.class)
    public ProblemDetail handleNotFound(ResourceNotFoundException e) {
        ProblemDetail problem = ProblemDetail.forStatusAndDetail(
                HttpStatus.NOT_FOUND, e.getMessage());
        problem.setProperty("timestamp", Instant.now());
        return problem;
    }

    @ExceptionHandler(ConflictException.class)
    public ProblemDetail handleConflict(ConflictException e) {
        ProblemDetail problem = ProblemDetail.forStatusAndDetail(
                HttpStatus.CONFLICT, e.getMessage());
        problem.setProperty("timestamp", Instant.now());
        return problem;
    }

    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ProblemDetail handleValidation(MethodArgumentNotValidException e) {
        ProblemDetail problem = ProblemDetail.forStatusAndDetail(
                HttpStatus.BAD_REQUEST, "Validation failed");
        problem.setProperty("timestamp", Instant.now());
        problem.setProperty("errors", e.getBindingResult().getFieldErrors().stream()
                .map(f -> f.getField() + ": " + f.getDefaultMessage())
                .toList());
        return problem;
    }

    @ExceptionHandler(Exception.class)
    public ProblemDetail handleGeneric(Exception e) {
        log.error("Unhandled exception", e);
        ProblemDetail problem = ProblemDetail.forStatusAndDetail(
                HttpStatus.INTERNAL_SERVER_ERROR, "Internal server error");
        problem.setProperty("timestamp", Instant.now());
        return problem;
    }
}
```

### Dockerfile
```dockerfile
# Build stage
FROM eclipse-temurin:21-jdk-alpine AS builder

WORKDIR /app

# Copy Maven wrapper and pom
COPY mvnw .
COPY .mvn .mvn
COPY pom.xml .

# Download dependencies
RUN ./mvnw dependency:go-offline -B

# Copy source and build
COPY src src
RUN ./mvnw package -DskipTests

# Extract layers for better caching
RUN java -Djarmode=layertools -jar target/*.jar extract

# Runtime stage
FROM eclipse-temurin:21-jre-alpine

WORKDIR /app

# Create non-root user
RUN addgroup -g 1001 spring && adduser -S -u 1001 spring

# Copy layers
COPY --from=builder /app/dependencies/ ./
COPY --from=builder /app/spring-boot-loader/ ./
COPY --from=builder /app/snapshot-dependencies/ ./
COPY --from=builder /app/application/ ./

USER spring

EXPOSE 8080

ENTRYPOINT ["java", "org.springframework.boot.loader.launch.JarLauncher"]
```

### Dockerfile (Native Image)
```dockerfile
# Build native image
FROM ghcr.io/graalvm/native-image-community:21 AS builder

WORKDIR /app

COPY mvnw .
COPY .mvn .mvn
COPY pom.xml .
COPY src src

RUN ./mvnw -Pnative native:compile -DskipTests

# Runtime
FROM debian:bookworm-slim

WORKDIR /app

RUN addgroup --gid 1001 spring && adduser --uid 1001 --gid 1001 spring
COPY --from=builder /app/target/demo app

USER spring

EXPOSE 8080

ENTRYPOINT ["./app"]
```

## Deployment Commands

### GCP Cloud Run
```bash
# Build with Cloud Build
gcloud builds submit --tag gcr.io/${PROJECT_ID}/spring-api

# Deploy
gcloud run deploy spring-api \
  --image gcr.io/${PROJECT_ID}/spring-api \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 2 \
  --min-instances 2 \
  --set-env-vars "SPRING_PROFILES_ACTIVE=prod" \
  --set-secrets "DATABASE_URL=database-url:latest"

# View logs
gcloud logging read "resource.type=cloud_run_revision" --limit 100
```

## Cost Breakdown

| Component | Monthly Cost |
|-----------|--------------|
| Cloud Run (2 min instances) | ~$60 |
| Cloud SQL (2 vCPU, 8GB) | ~$100 |
| Memorystore Redis | ~$35 |
| **Total** | **~$195** |

## Best Practices

1. **Use layered Dockerfile** - Faster builds with layer caching
2. **Enable actuator endpoints** - Health, metrics, info
3. **Use profiles** - Separate dev/prod configuration
4. **Flyway for migrations** - Version-controlled schema
5. **Connection pooling** - Configure HikariCP properly
6. **Graceful shutdown** - Handle SIGTERM signals
7. **Structured logging** - JSON format for cloud
8. **Consider native images** - Faster startup with GraalVM

## Common Mistakes

1. **JVM not tuned** - Set memory limits appropriately
2. **No connection pooling** - Exhausts database connections
3. **Missing health checks** - Actuator not exposed
4. **Slow startup** - Consider native image for serverless
5. **No caching** - Use Spring Cache with Redis
6. **Blocking operations** - Use WebFlux for reactive
7. **Debug logging in prod** - Performance impact
8. **Open-in-view enabled** - Lazy loading issues

## Example Configuration

```yaml
# infera.yaml
project_name: my-spring-api
provider: gcp

framework:
  name: spring-boot
  version: "3.2"
  java_version: "21"

deployment:
  type: container
  native_image: false  # Set true for faster startup

  resources:
    cpu: 2
    memory: 2Gi

  scaling:
    min_instances: 2
    max_instances: 20
    target_cpu: 70

  health_check:
    path: /actuator/health
    interval: 30s

database:
  type: postgresql
  version: "15"
  tier: db-custom-2-8192

cache:
  type: redis
  size: 1gb

env_vars:
  SPRING_PROFILES_ACTIVE: prod

secrets:
  - DATABASE_URL
  - REDIS_HOST
```

## Sources

- [Spring Boot Documentation](https://docs.spring.io/spring-boot/docs/current/reference/html/)
- [Spring Cloud GCP](https://spring.io/projects/spring-cloud-gcp)
- [GraalVM Native Image](https://www.graalvm.org/native-image/)
- [Cloud Run Java](https://cloud.google.com/run/docs/quickstarts/build-and-deploy/java)
