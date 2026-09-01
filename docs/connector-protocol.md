# Templeton Harness Connector Protocol v1

Templeton Production Loop has one workflow and one connector seam. Models are routing choices; harnesses are adapters at this seam. A new harness must not fork the workflow, labels, role contracts, evidence model, or human gates.

## Trust model

The deterministic Templeton broker remains trusted host software. A connector is also trusted host software, but the model or agent it launches is not. The broker supplies only a disposable, secret-filtered workspace and bounded prompt. The connector must enforce the declared session and tool policy before invoking the model.

Git, GitHub credentials, deployments, purchases, production systems, and merge authority remain outside every connector.

## Configuration

Pass a trusted regular JSON file with `--connector-config`:

```json
{
  "schema": "templeton.connector.v1",
  "id": "claude-code-local",
  "command": ["/absolute/path/to/templeton-claude-connector"],
  "roles": ["spec", "build", "review", "qa", "prove"]
}
```

Rules:

- keys are exact; unknown keys fail;
- `id` is a stable lowercase identifier;
- `command` is an argv array, never a shell string;
- the executable path is absolute and must resolve to an executable regular file;
- roles are a unique subset of `spec`, `build`, `review`, `qa`, and `prove`.

The config digest is recorded with runtime evidence.

## Preflight interface

Templeton runs:

```text
COMMAND preflight --role ROLE --workspace ABSOLUTE_PATH --json
```

The connector must inspect its effective runtime policy and return exactly:

```json
{
  "schema": "templeton.connector-preflight.v1",
  "id": "claude-code-local",
  "role": "build",
  "workspace": "/exact/staged/workspace",
  "workspace_access": "rw",
  "structured_output": true,
  "fresh_session": true,
  "isolation": "enforced",
  "network": "none",
  "credentials": "none",
  "verifier_image": null
}
```

Required workspace access:

| Role | Access |
|---|---|
| `spec` | `none` |
| `build` | `rw` |
| `review` | `ro` |
| `qa` | `ro` |
| `prove` | `rw` |

For `prove`, `verifier_image` must be an immutable `name@sha256:<64 lowercase hex>` image. It must be `null` for other roles.

Templeton fails closed if any field differs, if preflight writes to a report-only or one-shot workspace, or if the connector cannot prove its policy.

## Invocation interface

Templeton runs the connector inside the staged workspace:

```text
COMMAND invoke \
  --role ROLE \
  --workspace . \
  --message BOUNDED_PROMPT \
  --max-turns N \
  --timeout SECONDS \
  --json
```

Proof calls additionally receive:

```text
--phase strategy|worker
--model MODEL
[--provider PROVIDER]
[--profile PROFILE]
```

The connector must create a fresh model session for every invocation. It must not reuse hidden conversational state.

## Output contract

The connector writes the role-native Templeton result to stdout and diagnostics to stderr.

- `build`: one `templeton.result.v1` JSON object;
- `review` and `qa`: the existing normalized findings JSON contract;
- `spec`: one `templeton.spec.v1` JSON object;
- proof strategy: bounded plain text;
- proof worker: artifacts beneath the designated output directory; stdout is diagnostic only.

Do not wrap role output in provider-specific response envelopes. Normalizing provider or harness output is the connector’s responsibility.

## Capability levels

The same protocol can support different products without weakening claims:

- A text-only model may implement `spec` through a connector that receives no workspace.
- A read-only coding harness may implement `review` and `qa`.
- A sandboxed coding harness may implement `build`.
- A harness with exact one-shot workspace control and a pinned verifier image may implement `prove`.

Unsupported roles must be omitted from the config. Templeton refuses rather than silently degrading a requested role.

## Model portability

Claude, Gemini, GLM, Kimi, GPT, and local models are model routes, not workflow forks. A connector may use an API, CLI, or local inference server. It must preserve the same interface, evidence, isolation, and human authority rules.
