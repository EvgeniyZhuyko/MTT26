# MWS Octapi Integration Platform: Unifying Complex Branch Organizations with Event Mesh

> Source: [habr.com/ru/companies/ru_mts/articles/941266](https://habr.com/ru/companies/ru_mts/articles/941266)
> Author: Alexander Bardash, CTO at MWS Octapi
> Based on a talk at HighLoad++

## Introduction

MWS Octapi is an integration platform that provides all possible methods of interaction between systems within a company's ecosystem. It uses an Event Mesh approach — a technology that enables real-time data processing while ensuring security, performance, and manageability.

---

## Octapi Architecture: Two Worlds — Design-Time and Run-Time

The architecture is divided into several zones, viewed top to bottom.

### Preparation Phase: Design-Time

In design-time mode (the development phase), all integration processes are prepared. This is the initial phase where the foundations for the system are formed: from the API First approach (integration starts with API creation) to delivering data into isolated perimeters (separate zones where data is processed securely).

At this stage, clients and users interact through an **API server**. This is not just an API — it is a full-fledged layer upon which the GUI (graphical user interface) is built.

### GUI as DiscoveryPortal

The GUI is a unified integration catalog, called **DiscoveryPortal** on the architecture diagram. All integrations within the ecosystem are collected here. They can be located:

- At the **federated level** — publicly available integrations;
- In **isolation** — for example, in an On-Prem environment (local systems).

An **AI-powered search engine** is used to find the needed integrations. It analyzes specifications (i.e., integration descriptions) and helps quickly find the right solutions.

DiscoveryPortal also includes:

- **Permission Engine** — an access rights management system;
- **Low-code UI** — an interface with minimal code for simplified configuration.

### Control Plane: Information Delivery Zone

The next block is the **Control Plane** — the control layer responsible for information delivery. It implements coordinated processes:

- **Government Deploy** — system deployment in accordance with regulations;
- Data preparation;
- Data transmission into an **isolated perimeter** — a separated zone.

### Data Plane: Isolated Integrations

The final zone is the **Data Plane** — where data lives. Various isolated integrations run here, interacting with each other: OpenAPI, GraphQL, Service Mesh, Event Mesh, Low Code, and other technologies.

This zone also contains:

- **Traffic account module** (network traffic management);
- **Observability** (system monitoring);
- **DevOps tools** (development and management automation);
- **Internet access**;
- **Security components**: WAF (web traffic filtering), anti-bot (protection against automated attacks), anti-DDoS (protection against distributed attacks).

---

## What is Event Mesh

Integrations vary by abstraction level, maturity, and implementation. One place may use modern APIs, another — a 15-year-old IBM bus, a third — an asynchronous Kafka queue. The landscape can be very heterogeneous, and teams need to interact within it.

The key challenge is to give teams the ability to integrate quickly and easily. Of course, you could write a microservice for each integration, but that requires resources and leads to shifting responsibility. To avoid this, Event Mesh was introduced — a universal layer capable of working with any data sources and consumers.

### Business Scenarios

Event Mesh is a solution for unifying complex branch organizations:

- Minimizing systems' impact on each other;
- Data exchange between different subsidiaries and branches with completely different tech stacks and data formats;
- Asynchronous and event-driven interactions with validation capabilities, DLQ formation, and data transformation.

---

## How Event Mesh Works

There are four main steps:

**Step 1. Receiving Data.**
Data is received from various sources — RabbitMQ, Kafka, databases, Microsoft or IBM queues. Already at this stage, data can be split into streams by JSON schema or AsyncAPI specification, validated, formed into multiple streams, and separated by capability.

**Step 2. Conversion to a Standard Format.**
Data is sent to a tool that converts it into a unified, understandable format — for example, JSON or XML. This is important so that all data looks the same and is ready for further processing.

**Step 3. Sending to Kafka.**
After conversion, data is sent to an intermediate buffer — Kafka. This is a temporary "staging area" where data waits to be received by the needed services or systems. Data in Kafka is divided into isolated streams — for example, by type or region. These streams include **DLQ (Dead Letter Queue)** — a "bunker" for incorrect or unprocessed data so it doesn't get lost. Kafka ensures reliable delivery even if issues arise during the process.

**Step 4. Filtering and Transformation.**
At this stage, the consumer applies filtering — for example, selecting only data with a specific attribute (e.g., region). Transformation is also applied here, such as converting data to the required format. The result is filtered data — only the needed information, filtered by the specified criteria.

### Technical Perspective

The system starts working from a **manifest** — an instruction file describing data flow parameters: where to get data, how to process it, where to send it. The manifest is sent to the Event Mesh platform.

After receiving the manifest, the platform launches a configured **adapter** — a specialized module implementing data processing logic (filtering, transformation, routing to the right destination).

**Rate limits** allow solving several important tasks, including managing the "noisy neighbor" problem. If other services mistakenly send unnecessary traffic, limits are configured to prevent system overload.

All data processing logic is recorded in the manifest, making integrations easy to configure and verify.

### User Journey

1. **Manifest Formation.** The client enters the Discovery Portal (data flow management platform) and creates a manifest through the UI — an "instruction" describing what data to collect, how to process it, and where to send it. Example: "Collect data from System A, filter by region, and send to System B."

2. **Manifest Conversion.** The manifest is sent to the **Provisioner** — a tool that converts it into a technical manifest understandable by **Apache Flink** (the data processing system). The manifest is now ready to launch.

3. **Storage and Management in GitLab.** The manifest is saved in GitLab — a shared "warehouse" for files where instructions can be stored and managed. All data in GitLab is isolated for protection against accidental access.

4. **Delivery to Kubernetes via ArgoCD.** The manifest then goes to **ArgoCD** — a system that automatically delivers files (in this case, the manifest) to **Kubernetes** — the platform for running applications. Important: Kubernetes is in a separate network perimeter (Data Plane) to prevent data leaks.

### Why Two Network Perimeters?

- **Control Plane** — the "control zone" where settings and management live;
- **Data Plane** — the "working zone" where data is processed.

Personal data or banking information cannot be in the "working zone" without checks — that's too dangerous. Interaction occurs through GitLab.

Before the manifest reaches Kubernetes, it passes through a **pipeline** — a chain of checks:

- **Security validation** — information security specialists verify compliance;
- **Pentests** — vulnerability testing;
- **SAST scanning** — code analysis for errors;
- **Manual approval** — final review by responsible personnel.

Only after all these checks does the manifest reach Kubernetes and launch the integration in the Data Plane.

### Access Exists, Control is Strict

Access to Git exists, but integration does not activate automatically. All steps require mandatory validation to eliminate errors and threats.

---

## Connection Security in Event Mesh

### Authorization and Authentication

Event Mesh supports modern authentication methods:

- **OAuth 2.0** — for managing access to resources;
- **SASL** — for secure interaction between services;
- **mTLS (mutual TLS)** — for encryption and identity verification of parties.

This ensures data protection at all stages of transmission.

### Secret and Certificate Storage

Secrets (passwords, keys) and certificates are stored in **HashiCorp Vault** — a centralized vault where data is protected from unauthorized access. The **Secrets manager** delivers these secrets to Kubernetes, ensuring secure and automated distribution.

### Rotation and Reissuance

Secrets are **rotated** (reset) regularly to minimize leak risks. Certificates are **reissued** to avoid expiration or vulnerabilities. This guarantees data protection even when keys change or certificates become outdated.

### Automatic Updates by the Platform Core

The Octapi platform core (the main part of the system) **re-reads secrets and certificates** on every startup or on integration failure. For example, if a server changes a password or a breach occurs (e.g., a data leak), the core automatically updates secrets without requiring manual intervention.

### No Local Storage — Security Only

All data is stored in Vault and delivered to Kubernetes, not locally. This eliminates the risks of secret leaks and complies with security requirements.

---

## Routing

The platform supports **Content-Based Routing (CBR)** — routing by message content. Streams can be split by JSON or XML schemas, allowing data to be distributed on the fly across different streams.

Real-world case: One team couldn't read messages from Kafka, another could only put messages there. In three minutes, a manifest was composed, the needed messages were pulled from Kafka, filtered by metadata, and delivered via REST. What hadn't worked for months was running in minutes.

---

## Scalability and Performance

The platform runs on Kubernetes and scales linearly and horizontally. New nodes (virtual machines or containers) can be added as load grows, rather than increasing resources on a single node.

Using Apache Flink, there are known cases of processing up to **1 billion messages per second** in real scenarios. However, the team settled on **300,000 RPS** (requests per second) — sufficient for most tasks.

### Horizontal Scaling of Components

- **Task Manager** — the main Flink component responsible for data processing. It scales horizontally, distributing load across multiple nodes. It ensures fast inter-component communication, minimizing latency and improving performance when processing large data volumes.

- **GSLB (Global Server Load Balancing)** — provides load balancing between data centers, distributing traffic and avoiding overloading individual nodes.

- **Rate limit** — works in a distributed manner, not tied to a single node. This improves fault tolerance and allows the system to adapt to load fluctuations.

- **Apache Flink enhancements** — include reinforced security settings (e.g., encryption, authentication) and validators that check data before processing. These changes ensure system resilience and protection against anomalies (such as incorrect data or attacks).

All components — Task Manager, GSLB, rate limit, Flink — work **automatically** without user intervention, enabling large-scale scenarios (e.g., processing millions of messages per second) without manual resource management.

---

## Generating Manifests with an AI Assistant

To simplify manifest generation, an **AI assistant** was built. It can assemble a data flow for a task: receive messages from Kafka, transform to XML, send JSON via REST. The assistant clarifies details itself: bootstrap server, authorization, etc. Even if the client doesn't know the terms — that's fine. The assistant will guide them.

It leads the user, suggests a schema, shows the interface. A business analyst can say: "I want to receive balances and send them to the product" — the AI will find the appropriate APIs, understand what's needed (even if the word "balance" isn't explicitly stated), and suggest the right flow. The delivery point and attribute are selected — done!

The AI assistant provides links to documentation, loads current data, generates manifest examples, and supports dialogue to help those unfamiliar with technical terms.

The system works with **AsyncAPI specifications**, processes keywords, and analyzes information.

The team is moving toward the assistant being able to "communicate" with other agents, loading current data and providing not just documentation, but ready-made examples. In the future, inter-agent interaction is planned to automate even more integration creation processes.

---

## What's Next

Development of the platform continues. The goal is to make it accessible not only to system engineers but also to **business analysts**. Pilot deployments of AI assistants already show that the hypotheses work and users are satisfied.

Coming up:
- Expanding AI capabilities;
- More automation;
- UI improvements;
- New use cases.

All so that integrations are done **in minutes, not months**.
