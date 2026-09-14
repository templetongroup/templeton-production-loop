# Understand, Discover, and Design

Use this reference for a new product, unclear behavior, consequential architecture, or a request to be “grilled.” Skip it when the task is already sufficiently defined.

## One-decision discovery

1. Read the brief, current product, repository, TKS/project context, screenshots, and source-backed research first.
2. Separate known facts, reasonable assumptions, and decisions that only the operator can make.
3. Ask exactly one material decision at a time. Lead with a recommendation and explain the trade-off briefly.
4. Track decisions as they are made. Challenge contradictions or requests that would weaken the product instead of silently accepting them.
5. When enough is known, present a concise shared-understanding summary: users, job, essential workflow, scope, non-goals, constraints, success proof, and unresolved risks.
6. Do not implement until shared understanding is confirmed when the user explicitly requested a discovery phase. For ordinary clear requests, proceed without ceremony.

## Project start

For a project from scratch:

- confirm the product job and first usable vertical slice;
- choose the stack from requirements and the operator's environment, preferring established project/team conventions;
- establish repository, run command, test command, lint/typecheck/build command, environment-variable contract, and deployment boundary;
- create only the minimum structure required to run the slice;
- exercise the app before expanding breadth.

A GitHub issue is useful when the team needs a durable human-approved contract. It is not mandatory for local exploration or a clearly authorized direct build.

## Architecture decisions

For consequential design choices, record context, forces, two or three real options, recommendation, trade-offs, migration path, rollback, and proof. Prefer deep modules with small honest interfaces, dependency injection at real seams, reversible migrations, and behavioral tests through public contracts. Avoid speculative abstractions and broad rewrites.

## Prototypes

Prototype only to answer a named uncertainty. Keep it isolated, define the pass/fail signal first, run it, record the decision and limitations, and discard it unless the operator wants it retained. A prototype is not production until normal implementation and verification gates pass.
