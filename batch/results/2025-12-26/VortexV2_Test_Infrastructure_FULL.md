# VortexV2 Test Infrastructure Analysis & Redesign

## Executive Summary

Your current state of 27% coverage with critical security gaps (0/36 input validation, 0/24 database transactions) indicates fundamental infrastructure issues, not just missing tests. This analysis provides a complete redesign to reach 80% coverage.

---

## 1. Root Cause Analysis

### Current Infrastructure Failures

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    CURRENT STATE DIAGNOSIS                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Coverage: 27% ──┬── Security Tests: 44/77 (57%)                           │
│                  ├── Input Validation: 0/36 (0%) ← CRITICAL                │
│                  ├── DB Transactions: 0/24 (0%) ← CRITICAL                 │
│                  └── JWT Edge Cases: Unknown                                │
│                                                                              │
│  Root Causes Identified:                                                     │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ 1. Missing test database isolation (transactions fail)              │   │
│  │ 2. No input validation test fixtures exist                          │   │
│  │ 3. JWT mocking incomplete - edge cases untestable                   │   │
│  │ 4. Rate limiting has no time-manipulation capability                │   │
│  │ 5. No security-specific test utilities                              │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Test Infrastructure Redesign

### 2.1 Core Architecture

```typescript
// tests/infrastructure/core/TestOrchestrator.ts

import { Container } from 'inversify';
import { DataSource, QueryRunner } from 'typeorm';

/**
 * Central test orchestration system for VortexV2
 * Handles lifecycle, isolation, and resource management
 */
export class TestOrchestrator {
  private static instance: TestOrchestrator;
  private container: Container;
  private dataSource: DataSource;
  private activeTransactions: Map<string, QueryRunner> = new Map();
  
  private constructor() {}
  
  static getInstance(): TestOrchestrator {
    if (!TestOrchestrator.instance) {
      TestOrchestrator.instance = new TestOrchestrator();
    }
    return TestOrchestrator.instance;
  }

  async initialize(): Promise<void> {
    // Initialize test container with all mocks
    this.container = await this.buildTestContainer();
    
    // Initialize test database
    this.dataSource = await this.initializeTestDatabase();
    
    // Warm up connection pool
    await this.warmupConnections();
    
    // Initialize test utilities
    await this.initializeTestUtilities();
  }

  private async buildTestContainer(): Promise<Container> {
    const container = new Container({ defaultScope: 'Singleton' });
    
    // Core services with test implementations
    container.bind<IAuthService>('AuthService')
      .to(MockableAuthService);
    container.bind<IRateLimiter>('RateLimiter')
      .to(ControllableRateLimiter);
    container.bind<IValidator>('Validator')
      .to(InstrumentedValidator);
    container.bind<ICacheService>('CacheService')
      .to(InMemoryCache);
    container.bind<IEventBus>('EventBus')
      .to(SynchronousEventBus);
    
    return container;
  }

  private async initializeTestDatabase(): Promise<DataSource> {
    const dataSource = new DataSource({
      type: 'postgres',
      host: process.env.TEST_DB_HOST || 'localhost',
      port: parseInt(process.env.TEST_DB_PORT || '5433'),
      username: process.env.TEST_DB_USER || 'vortex_test',
      password: process.env.TEST_DB_PASS || 'test_password',
      database: process.env.TEST_DB_NAME || 'vortex_test',
      entities: ['src/**/*.entity.ts'],
      synchronize: true,
      dropSchema: true, // Fresh schema each run
      logging: process.env.TEST_DB_LOGGING === 'true',
      extra: {
        max: 10, // Limited pool for tests
        idleTimeoutMillis: 10000,
      },
    });

    await dataSource.initialize();
    return dataSource;
  }

  /**
   * Creates isolated transaction context for a test
   * Automatically rolls back after test completion
   */
  async createIsolatedContext(testId: string): Promise<TestContext> {
    const queryRunner = this.dataSource.createQueryRunner();
    await queryRunner.connect();
    await queryRunner.startTransaction();
    
    this.activeTransactions.set(testId, queryRunner);
    
    return new TestContext(
      testId,
      queryRunner,
      this.container.createChild(),
      this
    );
  }

  async releaseContext(testId: string): Promise<void> {
    const queryRunner = this.activeTransactions.get(testId);
    if (queryRunner) {
      await queryRunner.rollbackTransaction();
      await queryRunner.release();
      this.activeTransactions.delete(testId);
    }
  }

  async shutdown(): Promise<void> {
    // Rollback all active transactions
    for (const [testId, queryRunner] of this.activeTransactions) {
      await queryRunner.rollbackTransaction();
      await queryRunner.release();
    }
    this.activeTransactions.clear();
    
    // Close database connection
    if (this.dataSource?.isInitialized) {
      await this.dataSource.destroy();
    }
  }
}

/**
 * Test context providing isolated environment for each test
 */
export class TestContext {
  constructor(
    public readonly testId: string,
    public readonly queryRunner: QueryRunner,
    public readonly container: Container,
    private readonly orchestrator: TestOrchestrator
  ) {}

  get manager() {
    return this.queryRunner.manager;
  }

  resolve<T>(serviceId: string): T {
    return this.container.get<T>(serviceId);
  }

  async cleanup(): Promise<void> {
    await this.orchestrator.releaseContext(this.testId);
  }
}
```

### 2.2 Base Test Classes

```typescript
// tests/infrastructure/base/BaseIntegrationTest.ts

import { TestOrchestrator, TestContext } from '../core/TestOrchestrator';
import { v4 as uuidv4 } from 'uuid';

/**
 * Base class for all integration tests
 * Provides automatic transaction isolation and cleanup
 */
export abstract class BaseIntegrationTest {
  protected ctx: TestContext;
  protected testId: string;
  
  private static orchestrator: TestOrchestrator;

  static async globalSetup(): Promise<void> {
    BaseIntegrationTest.orchestrator = TestOrchestrator.getInstance();
    await BaseIntegrationTest.orchestrator.initialize();
  }

  static async globalTeardown(): Promise<void> {
    await BaseIntegrationTest.orchestrator.shutdown();
  }

  async beforeEach(): Promise<void> {
    this.testId = uuidv4();
    this.ctx = await BaseIntegrationTest.orchestrator.createIsolatedContext(
      this.testId
    );
    await this.setupTestData();
  }

  async afterEach(): Promise<void> {
    await this.ctx.cleanup();
  }

  /**
   * Override to set up test-specific data
   */
  protected async setupTestData(): Promise<void> {}

  /**
   * Helper to get repository with transaction context
   */
  protected getRepository<T>(entity: new () => T) {
    return this.ctx.manager.getRepository(entity);
  }
}

// tests/infrastructure/base/BaseSecurityTest.ts

import { BaseIntegrationTest } from './BaseIntegrationTest';
import { SecurityTestUtilities } from '../security/SecurityTestUtilities';

/**
 * Base class for security-focused tests
 * Includes additional security testing utilities
 */
export abstract class BaseSecurityTest extends BaseIntegrationTest {
  protected security: SecurityTestUtilities;

  async beforeEach(): Promise<void> {
    await super.beforeEach();
    this.security = new SecurityTestUtilities(this.ctx);
  }

  /**
   * Asserts that an action is properly unauthorized
   */
  protected async assertUnauthorized(
    action: () => Promise<any>,
    expectedCode: string = 'UNAUTHORIZED'
  ): Promise<void> {
    await expect(action()).rejects.toMatchObject({
      code: expectedCode,
      status: 401,
    });
  }

  /**
   * Asserts that an action is properly forbidden
   */
  protected async assertForbidden(
    action: () => Promise<any>,
    expectedCode: string = 'FORBIDDEN'
  ): Promise<void> {
    await expect(action()).rejects.toMatchObject({
      code: expectedCode,
      status: 403,
    });
  }

  /**
   * Tests that rate limiting is properly applied
   */
  protected async assertRateLimited(
    action: () => Promise<any>,
    limit: number
  ): Promise<void> {
    // Execute up to limit
    for (let i = 0; i < limit; i++) {
      await action();
    }
    
    // Next should be rate limited
    await expect(action()).rejects.toMatchObject({
      code: 'RATE_LIMITED',
      status: 429,
    });
  }
}
```

### 2.3 Database Transaction Testing Infrastructure

```typescript
// tests/infrastructure/database/TransactionTestHarness.ts

import { QueryRunner, EntityManager } from 'typeorm';
import { TestContext } from '../core/TestOrchestrator';

/**
 * Transaction testing utilities for complex scenarios
 */
export class TransactionTestHarness {
  constructor(private ctx: TestContext) {}

  /**
   * Tests that a service properly handles transaction rollback
   */
  async testRollbackBehavior<T>(
    setup: (manager: EntityManager) => Promise<void>,
    action: (manager: EntityManager) => Promise<T>,
    verify: (manager: EntityManager) => Promise<void>
  ): Promise<void> {
    // Setup test data
    await setup(this.ctx.manager);
    
    // Create nested transaction for the action
    const nestedRunner = this.ctx.manager.connection.createQueryRunner();
    await nestedRunner.connect();
    await nestedRunner.startTransaction();
    
    try {
      // Execute action that should fail
      await action(nestedRunner.manager);
      throw new Error('Expected action to throw');
    } catch (error) {
      // Rollback nested transaction
      await nestedRunner.rollbackTransaction();
    } finally {
      await nestedRunner.release();
    }
    
    // Verify rollback occurred correctly
    await verify(this.ctx.manager);
  }

  /**
   * Tests concurrent transaction handling
   */
  async testConcurrentAccess<T>(
    setup: (manager: EntityManager) => Promise<T>,
    concurrentActions: Array<(entity: T, manager: EntityManager) => Promise<void>>,
    expectedBehavior: 'all-succeed' | 'one-succeeds' | 'optimistic-lock-error'
  ): Promise<void> {
    const entity = await setup(this.ctx.manager);
    
    const runners = await Promise.all(
      concurrentActions.map(async () => {
        const runner = this.ctx.manager.connection.createQueryRunner();
        await runner.connect();
        await runner.startTransaction('SERIALIZABLE');
        return runner;
      })
    );

    try {
      const results = await Promise.allSettled(
        runners.map((runner, idx) => 
          concurrentActions[idx](entity, runner.manager)
        )
      );

      switch (expectedBehavior) {
        case 'all-succeed':
          results.forEach(r => expect(r.status).toBe('fulfilled'));
          break;
        case 'one-succeeds':
          const succeeded = results.filter(r => r.status === 'fulfilled');
          expect(succeeded).toHaveLength(1);
          break;
        case 'optimistic-lock-error':
          const failed = results.filter(r => r.status === 'rejected');
          expect(failed.length).toBeGreaterThan(0);
          expect((failed[0] as PromiseRejectedResult).reason.message)
            .toContain('optimistic lock');
          break;
      }
    } finally {
      await Promise.all(runners.map(async r => {
        await r.rollbackTransaction();
        await r.release();
      }));
    }
  }

  /**
   * Tests deadlock detection and resolution
   */
  async testDeadlockHandling(): Promise<void> {
    // Create two entities that will be accessed in opposite order
    const repo = this.ctx.manager.getRepository(TestEntity);
    const entityA = await repo.save({ name: 'A', value: 0 });
    const entityB = await repo.save({ name: 'B', value: 0 });

    const runner1 = this.ctx.manager.connection.createQueryRunner();
    const runner2 = this.ctx.manager.connection.createQueryRunner();
    
    await runner1.connect();
    await runner2.connect();
    await runner1.startTransaction();
    await runner2.startTransaction();

    try {
      // Transaction 1: Lock A, then try to lock B
      // Transaction 2: Lock B, then try to lock A
      const promise1 = (async () => {
        await runner1.manager.findOne(TestEntity, { 
          where: { id: entityA.id }, 
          lock: { mode: 'pessimistic_write' } 
        });
        await new Promise(r => setTimeout(r, 100));
        await runner1.manager.findOne(TestEntity, { 
          where: { id: entityB.id }, 
          lock: { mode: 'pessimistic_write' } 
        });
      })();

      const promise2 = (async () => {
        await runner2.manager.findOne(TestEntity, { 
          where: { id: entityB.id }, 
          lock: { mode: 'pessimistic_write' } 
        });
        await new Promise(r => setTimeout(r, 100));
        await runner2.manager.findOne(TestEntity, { 
          where: { id: entityA.id }, 
          lock: { mode: 'pessimistic_write' } 
        });
      })();

      const results = await Promise.allSettled([promise1, promise2]);
      
      // At least one should fail with deadlock
      const failures = results.filter(r => r.status === 'rejected');
      expect(failures.length).toBeGreaterThan(0);
      
    } finally {
      await runner1.rollbackTransaction();
      await runner2.rollbackTransaction();
      await runner1.release();
      await runner2.release();
    }
  }
}
```

---

## 3. Fixture System Improvements

### 3.1 Fixture Factory System

```typescript
// tests/fixtures/core/FixtureFactory.ts

import { EntityManager } from 'typeorm';
import { faker } from '@faker-js/faker';

/**
 * Type-safe fixture factory with builder pattern
 */
export abstract class 