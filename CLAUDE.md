# Frontier Radio API

Fork of `KIMB-technologies/Radio-API` for the Auna internet radios at the
Germany site.

## Layout

- `php/`, `utils/` — upstream application and container source
- `deploy/minipc-willich/` — production Compose stack and runbook

## Rules

- `origin` is `jttdev/frontier-radio-api`; `upstream` is the original project.
- Keep upstream-facing changes separable when practical so they can be
  proposed upstream or rebased cleanly.
- Production deploys from git: push locally, then pull and rebuild on
  `minipc-willich`. Do not copy source files directly to the host.
- Never commit deployment state under `deploy/*/data` or `deploy/*/media`.
- Validate both the legacy XML and newer Airable JSON endpoints after changes.
