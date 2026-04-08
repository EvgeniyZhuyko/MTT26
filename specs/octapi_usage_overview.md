# Enabler for AI Agents — MWS OCTAPI Integration Platform

Author: Alexander Bardash (CTO MWS Octapi)  
Source: Habr / MTS  
Date: July 30, 2025  

---

## Introduction

This is about building an engineering foundation for AI agents that:
- automate processes,
- make decisions,
- become part of real products (not just prototypes).

The core idea is a unified integration landscape for both business systems and models.

---

## Why Integration Breaks

A typical scenario:
1. A microservice is quickly built around an API.
2. Everything works.
3. Over time:
   - contract changes → failure,
   - infrastructure changes → failure,
   - no centralized control → chaos.

Each department solves the problem independently:
- their own APIs,
- their own DevOps,
- their own costs.

### Solution

A centralized platform is introduced — **Octapi**:
- single integration entry point,
- governance,
- reusability,
- risk reduction.

---

## Octapi Architecture

The system is divided into two layers:

### 1. Control Plane (design)
- integration design

### 2. Data Plane (runtime)
- integration execution

---

### Single Entry Point

All interactions go through an API server:
- web
- mobile clients
- CLI
- CI/CD pipelines

---

### Core Components

- Discovery portal (RBAC, ABAC, search, low-code UI)
- Workflow Engine (aligned with business processes)
- GitOps-based delivery
- Isolated zones (no direct access)

---

### Data Plane Capabilities

- Async API
- OpenAPI
- Event Mesh
- Service Mesh
- Low-code integrations

---

## Composite Integrations

Real-world scenarios include:
- multiple APIs
- data transformation (JSON ↔ XML)
- Kafka + DB + REST
- unified pipelines

This requires orchestration, not simple point-to-point connections.

---

## Low-Code Approach

Problem:
- simple tools → too limited
- universal tools → too complex

### Solution

A custom low-code tool:
- engine: **Temporal**
- architecture:
  - primitives
  - connectors
  - workers
- deployment: Kubernetes

Temporal:
- executes pipelines only
- contains no business logic
- easily replaceable

---

## Unified Descriptions (W2LCODE)

Any format → unified JSON:
- GUI
- diagrams
- code
- LLM input

→ transformed via adapters into executable format

---

## Ways to Build Integrations

### 1. JSON (developers)
- fast
- direct
- no GUI required

### 2. Diagrams (architects)
- abstract level

### 3. GUI (analysts)
- visual blocks

### 4. AI (chat-based)

#### AI Schema Builder
- dialog with a model
- clarification questions
- pipeline construction

Example:
> Kafka → XML → REST JSON

Result:
- ready integration in 5–30 minutes
- no coding required

---

## AI Integration Builder

Next level:

- user describes a business task
- system:
  - searches APIs, documentation, Confluence
  - understands semantics (semantic search)
  - suggests ready integrations

Example:
- query: "balance"
- system finds:
  - getBalance
  - financeAttribute
  - etc.

The user does not need to know:
- REST / Kafka
- schemas
- infrastructure

→ everything is abstracted by the platform

---

## Why Low-Code Matters

### Effects

- faster time-to-market
- fewer roles and handoffs
- direct business involvement

---

## Operations

Foundation — Temporal:
- monitoring
- state management
- GUI

Additionally:
- custom observability tools

---

## Metrics

- delivery acceleration: **+36%**
- load:
  - baseline: 300k RPS
  - potential: up to 1M TPS
- reliability:
  - 99.95% – 99.99%
- architecture:
  - multi-DC
  - cloud-native
  - HA / DR

---

## Limitations

Low-code is not suitable when:
- highly complex custom logic
- extreme load (~10M TPS)
- easier to build a dedicated service

However:
> ~95% of integrations are covered by the platform

---

## Q&A

### ❓ Can the result be poor?
Yes — if requirements are poor.  
But low-code helps surface issues faster.

---

### ❓ How are environments structured?

Pipeline stages:
- DevProd
- TestProd
- UATProd
- LoadProd
- ProdProd

Includes:
- access control
- policies
- production safety mechanisms

---

### ❓ How is high throughput achieved?

- Kubernetes
- horizontal scaling
- each block = pod

Additionally:
- rate limiting
- retries
- contract constraints

---

### ❓ Integration reusability

Each integration:
- is a reusable "building block"
- includes:
  - endpoints
  - authorization
  - tokens

→ published and reused

---

## Conclusion

Octapi is:
- a unified integration platform
- a foundation for AI agents
- a tool that:
  - reduces integration complexity
  - accelerates development
  - shifts control closer to business
