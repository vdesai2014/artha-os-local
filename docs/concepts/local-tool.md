# local_tool

`local_tool` is the stable contract between the local filesystem and
everything that reads it: the frontend, the sync layer, and the agent
itself. Unlike the real-time layer (hacked for your robot) and the
frontend (hacked for your taste), **this layer stays mostly fixed**. The
schema *is* the product.

## Two halves

```
local_tool/
  store/   — CRUD over the local fs (projects, runs, manifests, episodes)
  sync/    — move entities between local and cloud (push/pull/clone)
```

Plus a FastAPI server (`local_tool/server/`) that exposes both as HTTP
under `/api/*`, and a few proxies (`/ws` → bridge, `/video/*` →
video_bridge) so the frontend only hits one host.

## Dual consumers

The HTTP API has two consumers with the same interface:

1. **The frontend** — renders projects/runs/datasets, lets the user edit
   READMEs, attach episodes to manifests, browse files.
2. **The agent** — when the user says *"link this manifest to the
   synthetic-data run"*, the agent calls
   `POST /api/runs/{id}/manifests` or `POST /api/manifests/{id}/runs`.
   Same endpoints, same semantics.

Anything the frontend can do, the agent can do.

Live reference: `http://localhost:8000/docs` (FastAPI OpenAPI UI).

## Why it's mostly fixed

The STORE schema (projects → runs, episodes ↔ manifests, provenance
chain) is what `sync` knows how to move, what the frontend knows how to
render, and what the agent knows how to reason over. Change the schema
and three things break at once.

If you think you need to change it, you almost certainly want to change
the cloud API first — or add a new field at the edges without touching
the graph shape.

## Where the agent reaches for what

| User asks for | Agent calls |
|---------------|-------------|
| "create a run", "rename this manifest", "mark episode reward=1", "attach these episodes" | STORE HTTP endpoints (`/api/projects/*`, `/api/runs/*`, `/api/manifests/*`, `/api/episodes/*`) |
| "push my project to cloud", "pull the latest data", "clone that public project" | CLI: `artha push`, `artha pull`, `artha clone` |
| Anything the CLI/HTTP surface doesn't cover | Raw cloud API or sync internals (see `concepts/cloud.md` and `concepts/sync.md`) |

## What lives where

- `catalog.py` — fcntl-locked `catalog.json` index of `entity_id → path`.
  Self-healing: stale entries trigger a rescan.
- `ids.py` — generate/validate `prefix_<32 hex>` IDs.
- `models.py` — pydantic models for every entity. Source of truth for
  the STORE schema.
- `paths.py` — where each entity lives under `workspace/`.
- `store/` — pure fs operations. No network.
- `sync/` — cloud integration. See `concepts/sync.md`.
- `server/` — FastAPI app. Routes are thin wrappers around `store/` and
  `sync/`; don't put logic here.

## Reference

One-liner per endpoint: `docs/reference/store-api.md`.
