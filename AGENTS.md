# Agent engineering entrypoint

Read [the Product Passport](docs/product-passport/README.md), [CLAUDE.md](CLAUDE.md) and the code relevant to the task. The passport is a navigation aid; implementation, requirements and observed behavior determine correctness.

## DUNE paved path

Follow the [full DUNE Engineering handbook](https://github.com/ogfrench/agentic-coding-setup/blob/main/docs/dune.md) and optionally the [Agentic Workflow plugin](https://github.com/ogfrench/agentic-coding-setup/tree/main/plugins/agent-workflow). The link does not install a plugin or enable host permissions.

1. Identify the user outcome, canonical code owner, dependencies and relevant tests; verify any stale documentation against source.
2. Change the smallest correct path. Keep existing APIs, tests, security and configuration. Write regression coverage for a meaningful failure case.
3. Use the documented Python unittest pipeline and inspect index.html in a browser for rendering changes. Generated forecasts do not establish future results.
4. Reconcile affected passport entries after verification, or record `map unchanged` with a reason. In the PR, distinguish implemented, tested, blocked, merged, deployed and released, citing exact SHA and artifacts.

## Project-specific boundary

Preserve one canonical forecast model and the model/fixture provenance. Verify calculations from the source simulation rather than treating generated odds or static HTML as authoritative.

Respect current CI and release controls. Do not claim behavior, host acceptance or deployment from path validation alone.