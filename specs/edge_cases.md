## Dataset Strategy & Training Setup

### Single-Model, Multi-Role Approach

When using a **single base model** for three roles, you need **three separate datasets** to train adapters:

- Analyst (questioning / clarification)
- Generator (code writing)
- Critic (code validation)

---

## Lua Datasets

Public datasets for Lua:
- https://huggingface.co/datasets?search=lua

Example dataset loading:
```python
from datasets import load_dataset
ds = load_dataset("Roblox/luau_corpus")
```

---

## Synthetic Data Generation

Generate synthetic data using a **more powerful LLM**.

- Start with **200–500 high-quality examples per adapter**
- Focus on quality over quantity

---

## 1. Generator Dataset (Correct Lua Code)

Dataset: **pairs of task description → correct Lua code**

Example:
```json
{
  "instruction": "Write a Lua function to calculate factorial.",
  "output": "function factorial(n)\n  if n == 0 then return 1\n  else return n * factorial(n-1) end\nend"
}
```

---

## 2. Critic Dataset (Incorrect Code + Feedback)

Dataset file: `critic_data.jsonl`

Structure:
- **Input:** Lua code with typical mistakes  
- **Output:** constructive feedback  

Example:
```json
{
  "instruction": "Analyze this Lua code for errors:\n\nfunction test()\n  local x = 10\n  y = 20\n  return x + y\nend",
  "output": "The code contains a potential issue: variable 'y' is missing the 'local' keyword. This creates a global variable, which can lead to hard-to-debug errors. It is recommended to declare it as 'local y = 20'."
}
```

---

## 3. Analyst Dataset (Dialogue-Based Clarification)

### Step 1 — Generate Dialogues

Use a stronger model (e.g., GigaChat) to generate dialogues where:

- The task is initially vague  
- The assistant asks **3–5 clarifying questions**  
- The user provides answers  
- The assistant summarizes understanding  

### Example Prompt for Dialogue Generation

> Generate a dialogue between a programmer who wants to write a Lua script and an AI assistant.  
> Start with a vague request like "I need a script to process data".  
> The assistant should ask 3–5 specific clarifying questions (data source, format, processing steps, output).  
> The programmer provides clear answers.  
> At the end, the assistant confirms readiness to write code and summarizes key requirements.

---

### Step 2 — Convert to Training Format

Convert dialogues into **instruction–response format** for LoRA:

- **Instruction:** initial vague user request  
- **Output:** list of clarifying questions  

---

## Training Stack

### QLoRA + Unsloth

#### QLoRA

- Compresses base model (e.g., MultiPLCoder-1B) into **4-bit precision during training**
- Reduces VRAM usage:
  - from ~4–5 GB → ~1.1 GB  
- Enables training on:
  - free GPU (Tesla T4, 15 GB VRAM in Google Colab)

---

#### Unsloth

- Speeds up training **2–5×**
- Reduces memory usage by up to **80%**
- Optimizes internal training processes

---

## Training Plan: Three Specialists

The training process is identical across adapters — only datasets differ.

---

### 1. Analyst Adapter

**File:** `analyst_data.jsonl`  
**Goal:** learn to ask clarifying questions  

Dataset:
- vague task descriptions  
- model outputs 3–5 clarifying questions  

---

### 2. Generator Adapter

**File:** `generator_data.jsonl`  
**Goal:** generate Lua code  

Format:
```json
{
  "instruction": "Task description (RU/EN)",
  "output": "Valid Lua code"
}
```

---

### 3. Critic Adapter

**File:** `critic_data.jsonl`  
**Goal:** validate and analyze code  

Format:
```json
{
  "instruction": "Review this code",
  "output": "Error report (optionally structured as JSON)"
}
```

---

## Summary

- One base model → three LoRA adapters  
- Each adapter trained on **specialized dataset**  
- Synthetic data is essential (200–500 examples minimum)  
- Entire pipeline remains **local, reproducible, and privacy-safe**  
- Efficient training enabled by **QLoRA + Unsloth**