# NestJS Containers (Cloud Run / ECS)

## Overview

Deploy NestJS applications on container platforms for enterprise-grade APIs with dependency injection, modular architecture, and TypeScript support. NestJS's opinionated structure and decorators make it ideal for large-scale applications requiring maintainability and testability.

## Detection Signals

Use this template when:
- `nest-cli.json` exists
- `package.json` contains `@nestjs/core`
- `src/main.ts` with NestFactory
- `*.module.ts` files present
- Enterprise-scale API
- Dependency injection needed
- Modular architecture
- GraphQL or REST API

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
                    │   │  │  NestJS   │ │  NestJS   │ │  NestJS   │             │   │
                    │   │  │ Container │ │ Container │ │ Container │             │   │
                    │   │  │           │ │           │ │           │             │   │
                    │   │  │ Modules + │ │ Modules + │ │ Modules + │             │   │
                    │   │  │   DI      │ │   DI      │ │   DI      │             │   │
                    │   │  └───────────┘ └───────────┘ └───────────┘             │   │
                    │   │                                                         │   │
                    │   │  Auto-scaling: 2-20 instances based on CPU/requests    │   │
                    │   └─────────────────────────────────────────────────────────┘   │
                    │                            │                                    │
                    │          ┌─────────────────┼─────────────────┐                  │
                    │          ▼                 ▼                 ▼                  │
                    │   ┌───────────┐     ┌───────────┐     ┌───────────┐            │
                    │   │ PostgreSQL│     │   Redis   │     │  Storage  │            │
                    │   │ (Managed) │     │  (Cache + │     │ (GCS/S3)  │            │
                    │   │           │     │   Queue)  │     │           │            │
                    │   └───────────┘     └───────────┘     └───────────┘            │
                    │                                                                 │
                    │   Modular • Dependency Injection • OpenAPI • Production-ready  │
                    └─────────────────────────────────────────────────────────────────┘
```

## Resources

### GCP (Cloud Run)
| Resource | Purpose | Configuration |
|----------|---------|---------------|
| Cloud Run | Container hosting | 2 vCPU, 2GB RAM |
| Cloud SQL | PostgreSQL | db-f1-micro |
| Memorystore | Redis | 1GB |
| Cloud Storage | File uploads | Regional |
| Secret Manager | Credentials | Auto-mount |
| Pub/Sub | Message queue | Optional |

### AWS (ECS Fargate)
| Resource | Purpose | Configuration |
|----------|---------|---------------|
| ECS Fargate | Container hosting | 1 vCPU, 2GB |
| RDS Aurora | PostgreSQL | Serverless v2 |
| ElastiCache | Redis | cache.t3.micro |
| S3 | File storage | Standard |
| Secrets Manager | Credentials | ECS integration |
| SQS | Message queue | Optional |

## Configuration

### Project Structure
```
my-nestjs-app/
├── src/
│   ├── main.ts                    # Bootstrap
│   ├── app.module.ts              # Root module
│   ├── config/
│   │   ├── config.module.ts
│   │   └── configuration.ts
│   ├── common/
│   │   ├── decorators/
│   │   ├── filters/
│   │   ├── guards/
│   │   ├── interceptors/
│   │   └── pipes/
│   ├── users/
│   │   ├── users.module.ts
│   │   ├── users.controller.ts
│   │   ├── users.service.ts
│   │   ├── entities/
│   │   │   └── user.entity.ts
│   │   └── dto/
│   │       ├── create-user.dto.ts
│   │       └── update-user.dto.ts
│   ├── auth/
│   │   ├── auth.module.ts
│   │   ├── auth.controller.ts
│   │   ├── auth.service.ts
│   │   └── strategies/
│   │       └── jwt.strategy.ts
│   └── health/
│       ├── health.module.ts
│       └── health.controller.ts
├── test/
├── nest-cli.json
├── package.json
├── tsconfig.json
├── tsconfig.build.json
├── Dockerfile
└── docker-compose.yml
```

### Main Bootstrap
```typescript
// src/main.ts
import { NestFactory } from '@nestjs/core';
import { ValidationPipe, VersioningType } from '@nestjs/common';
import { SwaggerModule, DocumentBuilder } from '@nestjs/swagger';
import { ConfigService } from '@nestjs/config';
import helmet from 'helmet';
import compression from 'compression';
import { AppModule } from './app.module';
import { HttpExceptionFilter } from './common/filters/http-exception.filter';
import { TransformInterceptor } from './common/interceptors/transform.interceptor';
import { LoggingInterceptor } from './common/interceptors/logging.interceptor';

async function bootstrap() {
  const app = await NestFactory.create(AppModule, {
    logger: ['error', 'warn', 'log'],
  });

  const configService = app.get(ConfigService);

  // Security
  app.use(helmet());
  app.enableCors({
    origin: configService.get('CORS_ORIGINS')?.split(',') || '*',
    credentials: true,
  });

  // Compression
  app.use(compression());

  // Global prefix
  app.setGlobalPrefix('api');

  // API versioning
  app.enableVersioning({
    type: VersioningType.URI,
    defaultVersion: '1',
  });

  // Validation
  app.useGlobalPipes(
    new ValidationPipe({
      whitelist: true,
      forbidNonWhitelisted: true,
      transform: true,
      transformOptions: {
        enableImplicitConversion: true,
      },
    }),
  );

  // Global filters and interceptors
  app.useGlobalFilters(new HttpExceptionFilter());
  app.useGlobalInterceptors(
    new LoggingInterceptor(),
    new TransformInterceptor(),
  );

  // Swagger
  if (configService.get('NODE_ENV') !== 'production') {
    const config = new DocumentBuilder()
      .setTitle('My API')
      .setDescription('API Documentation')
      .setVersion('1.0')
      .addBearerAuth()
      .build();
    const document = SwaggerModule.createDocument(app, config);
    SwaggerModule.setup('docs', app, document);
  }

  // Graceful shutdown
  app.enableShutdownHooks();

  const port = configService.get('PORT') || 3000;
  await app.listen(port);

  console.log(`Application running on port ${port}`);
}

bootstrap();
```

### App Module
```typescript
// src/app.module.ts
import { Module } from '@nestjs/common';
import { ConfigModule, ConfigService } from '@nestjs/config';
import { TypeOrmModule } from '@nestjs/typeorm';
import { ThrottlerModule } from '@nestjs/throttler';
import { CacheModule } from '@nestjs/cache-manager';
import { BullModule } from '@nestjs/bull';
import { redisStore } from 'cache-manager-redis-yet';

import { UsersModule } from './users/users.module';
import { AuthModule } from './auth/auth.module';
import { HealthModule } from './health/health.module';
import configuration from './config/configuration';

@Module({
  imports: [
    // Configuration
    ConfigModule.forRoot({
      isGlobal: true,
      load: [configuration],
    }),

    // Database
    TypeOrmModule.forRootAsync({
      imports: [ConfigModule],
      useFactory: (configService: ConfigService) => ({
        type: 'postgres',
        url: configService.get('DATABASE_URL'),
        entities: [__dirname + '/**/*.entity{.ts,.js}'],
        synchronize: false,
        logging: configService.get('NODE_ENV') === 'development',
        ssl: configService.get('NODE_ENV') === 'production'
          ? { rejectUnauthorized: false }
          : false,
      }),
      inject: [ConfigService],
    }),

    // Cache
    CacheModule.registerAsync({
      isGlobal: true,
      imports: [ConfigModule],
      useFactory: async (configService: ConfigService) => ({
        store: await redisStore({
          url: configService.get('REDIS_URL'),
        }),
        ttl: 60 * 1000, // 1 minute
      }),
      inject: [ConfigService],
    }),

    // Rate limiting
    ThrottlerModule.forRoot([
      {
        ttl: 60000,
        limit: 100,
      },
    ]),

    // Queue
    BullModule.forRootAsync({
      imports: [ConfigModule],
      useFactory: (configService: ConfigService) => ({
        redis: configService.get('REDIS_URL'),
      }),
      inject: [ConfigService],
    }),

    // Feature modules
    UsersModule,
    AuthModule,
    HealthModule,
  ],
})
export class AppModule {}
```

### Configuration
```typescript
// src/config/configuration.ts
export default () => ({
  port: parseInt(process.env.PORT, 10) || 3000,
  nodeEnv: process.env.NODE_ENV || 'development',
  database: {
    url: process.env.DATABASE_URL,
  },
  redis: {
    url: process.env.REDIS_URL,
  },
  jwt: {
    secret: process.env.JWT_SECRET,
    expiresIn: process.env.JWT_EXPIRES_IN || '1d',
  },
  cors: {
    origins: process.env.CORS_ORIGINS?.split(',') || ['*'],
  },
});
```

### User Module
```typescript
// src/users/users.module.ts
import { Module } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';
import { UsersController } from './users.controller';
import { UsersService } from './users.service';
import { User } from './entities/user.entity';

@Module({
  imports: [TypeOrmModule.forFeature([User])],
  controllers: [UsersController],
  providers: [UsersService],
  exports: [UsersService],
})
export class UsersModule {}
```

### User Entity
```typescript
// src/users/entities/user.entity.ts
import {
  Entity,
  PrimaryGeneratedColumn,
  Column,
  CreateDateColumn,
  UpdateDateColumn,
  Index,
} from 'typeorm';
import { Exclude } from 'class-transformer';

@Entity('users')
export class User {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Index({ unique: true })
  @Column()
  email: string;

  @Column()
  name: string;

  @Exclude()
  @Column()
  password: string;

  @Column({ default: true })
  isActive: boolean;

  @CreateDateColumn()
  createdAt: Date;

  @UpdateDateColumn()
  updatedAt: Date;
}
```

### User DTOs
```typescript
// src/users/dto/create-user.dto.ts
import { ApiProperty } from '@nestjs/swagger';
import { IsEmail, IsString, MinLength, MaxLength } from 'class-validator';

export class CreateUserDto {
  @ApiProperty({ example: 'user@example.com' })
  @IsEmail()
  email: string;

  @ApiProperty({ example: 'John Doe' })
  @IsString()
  @MinLength(2)
  @MaxLength(100)
  name: string;

  @ApiProperty({ example: 'password123' })
  @IsString()
  @MinLength(8)
  password: string;
}

// src/users/dto/update-user.dto.ts
import { PartialType } from '@nestjs/swagger';
import { CreateUserDto } from './create-user.dto';

export class UpdateUserDto extends PartialType(CreateUserDto) {}
```

### User Controller
```typescript
// src/users/users.controller.ts
import {
  Controller,
  Get,
  Post,
  Body,
  Patch,
  Param,
  Delete,
  Query,
  UseGuards,
  ParseUUIDPipe,
  HttpStatus,
} from '@nestjs/common';
import {
  ApiTags,
  ApiOperation,
  ApiResponse,
  ApiBearerAuth,
  ApiQuery,
} from '@nestjs/swagger';
import { UsersService } from './users.service';
import { CreateUserDto } from './dto/create-user.dto';
import { UpdateUserDto } from './dto/update-user.dto';
import { JwtAuthGuard } from '../auth/guards/jwt-auth.guard';
import { PaginationDto } from '../common/dto/pagination.dto';

@ApiTags('users')
@Controller('users')
export class UsersController {
  constructor(private readonly usersService: UsersService) {}

  @Post()
  @ApiOperation({ summary: 'Create user' })
  @ApiResponse({ status: HttpStatus.CREATED, description: 'User created' })
  create(@Body() createUserDto: CreateUserDto) {
    return this.usersService.create(createUserDto);
  }

  @Get()
  @UseGuards(JwtAuthGuard)
  @ApiBearerAuth()
  @ApiOperation({ summary: 'List all users' })
  @ApiQuery({ name: 'page', required: false, type: Number })
  @ApiQuery({ name: 'limit', required: false, type: Number })
  findAll(@Query() query: PaginationDto) {
    return this.usersService.findAll(query);
  }

  @Get(':id')
  @UseGuards(JwtAuthGuard)
  @ApiBearerAuth()
  @ApiOperation({ summary: 'Get user by ID' })
  @ApiResponse({ status: HttpStatus.OK, description: 'User found' })
  @ApiResponse({ status: HttpStatus.NOT_FOUND, description: 'User not found' })
  findOne(@Param('id', ParseUUIDPipe) id: string) {
    return this.usersService.findOne(id);
  }

  @Patch(':id')
  @UseGuards(JwtAuthGuard)
  @ApiBearerAuth()
  @ApiOperation({ summary: 'Update user' })
  update(
    @Param('id', ParseUUIDPipe) id: string,
    @Body() updateUserDto: UpdateUserDto,
  ) {
    return this.usersService.update(id, updateUserDto);
  }

  @Delete(':id')
  @UseGuards(JwtAuthGuard)
  @ApiBearerAuth()
  @ApiOperation({ summary: 'Delete user' })
  @ApiResponse({ status: HttpStatus.NO_CONTENT })
  remove(@Param('id', ParseUUIDPipe) id: string) {
    return this.usersService.remove(id);
  }
}
```

### User Service
```typescript
// src/users/users.service.ts
import {
  Injectable,
  NotFoundException,
  ConflictException,
} from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository } from 'typeorm';
import * as bcrypt from 'bcrypt';
import { User } from './entities/user.entity';
import { CreateUserDto } from './dto/create-user.dto';
import { UpdateUserDto } from './dto/update-user.dto';
import { PaginationDto } from '../common/dto/pagination.dto';

@Injectable()
export class UsersService {
  constructor(
    @InjectRepository(User)
    private readonly usersRepository: Repository<User>,
  ) {}

  async create(createUserDto: CreateUserDto): Promise<User> {
    const existing = await this.usersRepository.findOne({
      where: { email: createUserDto.email },
    });

    if (existing) {
      throw new ConflictException('Email already exists');
    }

    const hashedPassword = await bcrypt.hash(createUserDto.password, 10);

    const user = this.usersRepository.create({
      ...createUserDto,
      password: hashedPassword,
    });

    return this.usersRepository.save(user);
  }

  async findAll(query: PaginationDto) {
    const { page = 1, limit = 20 } = query;
    const skip = (page - 1) * limit;

    const [users, total] = await this.usersRepository.findAndCount({
      skip,
      take: limit,
      order: { createdAt: 'DESC' },
    });

    return {
      data: users,
      meta: {
        total,
        page,
        limit,
        totalPages: Math.ceil(total / limit),
      },
    };
  }

  async findOne(id: string): Promise<User> {
    const user = await this.usersRepository.findOne({ where: { id } });

    if (!user) {
      throw new NotFoundException('User not found');
    }

    return user;
  }

  async findByEmail(email: string): Promise<User | null> {
    return this.usersRepository.findOne({ where: { email } });
  }

  async update(id: string, updateUserDto: UpdateUserDto): Promise<User> {
    const user = await this.findOne(id);

    if (updateUserDto.password) {
      updateUserDto.password = await bcrypt.hash(updateUserDto.password, 10);
    }

    Object.assign(user, updateUserDto);
    return this.usersRepository.save(user);
  }

  async remove(id: string): Promise<void> {
    const result = await this.usersRepository.delete(id);

    if (result.affected === 0) {
      throw new NotFoundException('User not found');
    }
  }
}
```

### Health Module
```typescript
// src/health/health.module.ts
import { Module } from '@nestjs/common';
import { TerminusModule } from '@nestjs/terminus';
import { HealthController } from './health.controller';

@Module({
  imports: [TerminusModule],
  controllers: [HealthController],
})
export class HealthModule {}

// src/health/health.controller.ts
import { Controller, Get } from '@nestjs/common';
import {
  HealthCheck,
  HealthCheckService,
  TypeOrmHealthIndicator,
  MemoryHealthIndicator,
  DiskHealthIndicator,
} from '@nestjs/terminus';
import { ApiTags, ApiOperation } from '@nestjs/swagger';

@ApiTags('health')
@Controller('health')
export class HealthController {
  constructor(
    private health: HealthCheckService,
    private db: TypeOrmHealthIndicator,
    private memory: MemoryHealthIndicator,
    private disk: DiskHealthIndicator,
  ) {}

  @Get()
  @HealthCheck()
  @ApiOperation({ summary: 'Health check' })
  check() {
    return this.health.check([
      () => this.db.pingCheck('database'),
      () => this.memory.checkHeap('memory_heap', 200 * 1024 * 1024),
      () =>
        this.disk.checkStorage('disk', { thresholdPercent: 0.9, path: '/' }),
    ]);
  }
}
```

### Dockerfile
```dockerfile
# Build stage
FROM node:20-alpine AS builder

WORKDIR /app

# Install dependencies
COPY package*.json ./
RUN npm ci

# Copy source and build
COPY . .
RUN npm run build

# Production stage
FROM node:20-alpine

WORKDIR /app

# Create non-root user
RUN addgroup -g 1001 nodejs && adduser -S -u 1001 nestjs

# Install production dependencies
COPY package*.json ./
RUN npm ci --only=production && npm cache clean --force

# Copy built application
COPY --from=builder /app/dist ./dist

# Set ownership
RUN chown -R nestjs:nodejs /app
USER nestjs

EXPOSE 3000
ENV PORT=3000

CMD ["node", "dist/main.js"]
```

## Deployment Commands

### GCP Cloud Run
```bash
# Build and push
gcloud builds submit --tag gcr.io/${PROJECT_ID}/nestjs-api

# Deploy
gcloud run deploy nestjs-api \
  --image gcr.io/${PROJECT_ID}/nestjs-api \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 2 \
  --min-instances 2 \
  --max-instances 20 \
  --set-env-vars "NODE_ENV=production" \
  --set-secrets "DATABASE_URL=database-url:latest,JWT_SECRET=jwt-secret:latest"

# Run migrations
gcloud run jobs execute migrate \
  --image gcr.io/${PROJECT_ID}/nestjs-api \
  -- npm run migration:run
```

### AWS ECS
```bash
# Build and push to ECR
aws ecr get-login-password | docker login --username AWS --password-stdin ${ACCOUNT}.dkr.ecr.${REGION}.amazonaws.com

docker build -t nestjs-api .
docker tag nestjs-api:latest ${ACCOUNT}.dkr.ecr.${REGION}.amazonaws.com/nestjs-api:latest
docker push ${ACCOUNT}.dkr.ecr.${REGION}.amazonaws.com/nestjs-api:latest

# Update ECS service
aws ecs update-service --cluster main --service nestjs-api --force-new-deployment
```

## Cost Breakdown

### GCP Cloud Run
| Component | Monthly Cost |
|-----------|--------------|
| Cloud Run (2 min instances) | ~$50 |
| Cloud SQL | ~$25 |
| Memorystore | ~$35 |
| **Total** | **~$110** |

### AWS ECS Fargate
| Component | Monthly Cost |
|-----------|--------------|
| ECS Fargate (2 tasks) | ~$60 |
| RDS Aurora Serverless | ~$30 |
| ElastiCache | ~$15 |
| **Total** | **~$105** |

## Best Practices

1. **Use modules for organization** - Group related functionality
2. **Dependency injection** - Let NestJS manage dependencies
3. **DTO validation** - Use class-validator decorators
4. **OpenAPI documentation** - Auto-generate with Swagger
5. **Global exception filter** - Consistent error responses
6. **Health checks with Terminus** - Production-ready health endpoints
7. **Config service** - Centralized configuration
8. **TypeORM migrations** - Version-controlled schema changes

## Common Mistakes

1. **Circular dependencies** - Use forwardRef() carefully
2. **Missing validation pipe** - Always enable globally
3. **Sync TypeORM operations** - Use async/await properly
4. **No exception filters** - Unhandled errors expose internals
5. **Hardcoded config** - Use ConfigService
6. **Missing health checks** - Required for container platforms
7. **No rate limiting** - Use ThrottlerModule
8. **Large response payloads** - Use serialization interceptors

## Example Configuration

```yaml
# infera.yaml
project_name: my-nestjs-api
provider: gcp

framework:
  name: nestjs
  version: "10"

deployment:
  type: container
  runtime: nodejs-20

  resources:
    cpu: 2
    memory: 2Gi

  scaling:
    min_instances: 2
    max_instances: 20
    target_cpu: 70

  health_check:
    path: /api/v1/health
    interval: 30s

database:
  type: postgresql
  version: "15"
  tier: db-f1-micro

cache:
  type: redis
  size: 1gb

env_vars:
  NODE_ENV: production

secrets:
  - DATABASE_URL
  - JWT_SECRET
  - REDIS_URL
```

## Sources

- [NestJS Documentation](https://docs.nestjs.com/)
- [TypeORM Documentation](https://typeorm.io/)
- [Cloud Run Node.js](https://cloud.google.com/run/docs/quickstarts/build-and-deploy/nodejs)
- [NestJS Terminus](https://docs.nestjs.com/recipes/terminus)
