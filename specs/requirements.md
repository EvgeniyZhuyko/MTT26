# LocalScript: A Local Agent System for Generating Lua Code

## Overview

Develop an autonomous agent system based on a local (lightweight) large language model (LLM) that generates and validates Lua code without sending any data to external services.

**Target audience:** generative AI engineers, backend developers, MLOps engineers, and DevOps/infrastructure engineers.

---

## Problem Statement

In many integration and security-sensitive environments, external AI services cannot be used for code generation. This introduces risks such as:

- data leakage  
- vendor lock-in  
- violations of infrastructure and compliance requirements  

At the same time:

- large models require expensive resources  
- they are not suitable for local deployment  

Therefore, there is a need for an agent-based system that:

- runs entirely on internal infrastructure  
- uses a lightweight local model  
- understands natural language requests  
- generates correct Lua code without sending data outside  

---

## Full Description

Participants must create an AI agent or agent system that:

- runs locally on a lightweight open-source LLM  
- accepts tasks in natural language  
- generates working Lua code  

The value of the solution is not limited to one-shot generation. A strong system should:

- ask clarifying questions  
- understand task context  
- validate generated code  
- iteratively improve results  

---

## Key Requirements

The solution must address all of the following:

- **Local execution only**  
- **No external LLM vendors at runtime**  
- **Clear generation and validation pipeline**  
- **Practical usability**  
- **Operation in a secure environment where data/code never leaves the company boundary**  

A strong solution would behave like:

1. User submits a task (Russian or English)  
2. System generates an initial Lua script  
3. System either:
   - validates it automatically  
   - asks clarifying questions  
   - performs corrective iterations  

Additional advantage:

- use of domain knowledge or task templates (if implemented locally and reproducibly)

---

## Technical Constraints

### Model & Runtime

- Must use a **lightweight model**
- Must run locally via :contentReference[oaicite:0]{index=0}
- GPU requirement:
  - **8 GB VRAM**
  - fully GPU execution (**no CPU offloading**)

### Fixed Evaluation Parameters

- `num_ctx = 4096`  
- `num_predict = 256`  
- `batch = 1`  
- `parallel = 1`  

### Memory Constraint

- Peak VRAM usage ≤ **8.0 GB**
- Measured via `nvidia-smi` by organizers

### Additional Notes

- Quantization is allowed  
- README must include:
  - exact `ollama pull <tag>`  
  - runtime parameters  

---

## Restrictions

- Must use **local open-source LLM**
- **Forbidden:**
  - :contentReference[oaicite:1]{index=1} APIs  
  - :contentReference[oaicite:2]{index=2} APIs  
  - any external AI services for generation or refinement  

---

## Recommended Stack

- Python  
- Open-source LLM  

---

## Functional Requirements

The system must:

- understand natural language tasks  
- generate Lua code  
- perform at least one iteration:
  - clarification OR
  - refinement  
- validate results using any verifiable method:
  - syntax checks  
  - tests  
  - static analysis  
  - rule-based validation  

---

## Reproducibility

All of the following must be provided:

- dependencies  
- models  
- setup steps  

So that the jury can reproduce the demo environment.

If used, the following must also be:

- local  
- included in the solution  
- documented  

Examples:

- knowledge base  
- retrieval system  
- template libraries  

---

## Evaluation Criteria

### 1. Code Quality & Correctness (0–50 points)

Evaluated on a hidden dataset:

- correctness vs task  
- syntactic validity  
- logical consistency  
- usability  

**Top score:** code requires little to no manual rewriting.

---

### 2. Agent Behavior & Iteration Quality (0–25 points)

Evaluates whether the system:

- asks clarifying questions  
- incorporates feedback  
- improves results iteratively  

**High score:** controlled workflow, not just a single model response.

---

### 3. Locality, Privacy & Reproducibility (0–25 points)

Evaluates whether:

- the system runs fully locally  
- no dependency on external AI services  
- deployment is reproducible  
- resource usage is reasonable  

---