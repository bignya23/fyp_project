# Multi-Agent Coordination Rules & Boundary Protocols

This repository operates on a specialized multi-agent workflow. AI agents and human teammates must strictly adhere to domain ownership boundaries to avoid merge conflicts and breaking cross-module contracts.

---

## 1. Agent Roles & Module Ownership

| Agent Name | Role | Primary Ownership | Secondary / Read-Only Access |
| :--- | :--- | :--- | :--- |
| **`@sim-agent`** | Optical Physics & Frame Generator | `/transmitter_sim/`<br>`/shared/protocol.json` (co-owner) | `/shared/samples/` |
| **`@cv-demod-agent`** | 4-Stage Computer Vision Demodulator | `/receiver_demod/` | `/shared/` (read-only) |
| **`@benchmark-agent`**| Evaluation, BER, & Documentation | `/benchmarks/`<br>`/docs/` | `/transmitter_sim/`<br>`/receiver_demod/` (read-only execution) |
| **`@coordinator-agent`**| System Architect & Contract Enforcer | Root Tracking Files (`PROJECT_STATUS.md`, `TASKS.md`, `ARCHITECTURE.md`, `HANDOFF_LOG.md`) | Repository-wide oversight |

---

## 2. Strict Rules of Engagement

1. **Check Before You Act:**
   - Always read `PROJECT_STATUS.md` and `ARCHITECTURE.md` before executing any task.
   - Inspect `TASKS.md` and claim an item by marking it `[IN PROGRESS]` with your agent handle.

2. **Stay Within Your Boundary:**
   - `@sim-agent` MUST NEVER edit files inside `/receiver_demod/` or `/benchmarks/`.
   - `@cv-demod-agent` MUST NEVER modify synthetic generation physics inside `/transmitter_sim/`.
   - Any proposed change to `/shared/protocol.json` requires explicit sign-off from `@coordinator-agent`.

3. **Log Every Handoff:**
   - After completing code generation, testing, or modifications, append an entry to `HANDOFF_LOG.md`.
   - Update `PROJECT_STATUS.md` with current verification status and mark the item `[DONE]` in `TASKS.md`.

4. **Zero-Broken-Window Policy:**
   - Never commit code that breaks test framing or violates the image format contract specified in `ARCHITECTURE.md`.
