# Architecture docs

- [`agent-runtime.md`](agent-runtime.md) — the durable, committed reference for the Agent Runtime: core concepts, the concrete slice-1 design (interfaces, module layout), and a table of what's implemented vs. future work.
- [`decisions.md`](decisions.md) — a short log of specific calls made while building the first slice, and why, for anything not obvious from reading the code.
- [`multi-agent.md`](multi-agent.md) — design-only reference for how multi-agent support would extend the Agent Runtime; no code exists yet.
- [`setup-and-diagnostics.md`](setup-and-diagnostics.md) — the durable reference for `woven setup`/`woven doctor` (`src/woven/setup/`, `src/woven/diagnostics/`).
- [`user-settings.md`](user-settings.md) — the durable reference for the persisted settings/secrets subsystem (`src/woven/settings/`).

See also `../architecture.md`, the original high-level conceptual overview (Agent Runtime, Modes, Workflows, Context, Memory, Events, etc.) that predates and motivates the documents in this folder.
