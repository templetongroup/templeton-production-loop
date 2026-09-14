# Project Discovery Stage

This is an internal report-only stage of `templeton-build`, not a standalone skill.

Use it when the operator explicitly asks to be grilled, requests discovery before implementation, or when a new product has unresolved decisions that materially change scope, architecture, cost, risk, or irreversible work.

1. Research retrievable facts from the trusted brief, project context, repository, and approved sources before asking.
2. Ask exactly one material decision at a time, with the recommended answer first and concise trade-offs.
3. Maintain a decision ledger and resolve dependencies in order.
4. Present a proposed `PROJECT-SEED.md` containing users, job, essential workflows, scope, non-goals, constraints, architecture assumptions, success proof, deployment boundary, and unresolved risks.
5. Require explicit operator confirmation of shared understanding before handing the seed to setup or implementation.

This stage does not scaffold, edit source, mutate GitHub, apply `loop:agent-ready`, deploy, or silently enter implementation. A broader operator request to build may continue only after the discovery result is explicitly confirmed; that continuation is a new internal stage with its own permissions and proof.
