# local_tool HTTP API reference

Live OpenAPI UI: `http://localhost:8000/docs` (FastAPI-generated). This
file is a grep-friendly index — design intent lives in
`concepts/local-tool.md` and `concepts/sync.md`.

## Health

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/health` | service liveness ping |

## Projects

| Method | Path | Purpose |
|--------|------|---------|
| GET    | `/api/projects` | list local projects (filter by `tags`, `order`, `limit`, `cursor`) |
| POST   | `/api/projects` | create a project (server or client-supplied id) |
| GET    | `/api/projects/{id}` | fetch project detail |
| PATCH  | `/api/projects/{id}` | edit name/description/tags/is_public |
| DELETE | `/api/projects/{id}` | delete project + all descendants |
| GET    | `/api/projects/{id}/files` | list project-level files |
| POST   | `/api/projects/{id}/files/download` | resolve download URLs for given paths |
| GET    | `/api/projects/{id}/files/content?path=…` | stream one file |
| GET    | `/api/projects/{id}/readme` | fetch README.md contents |
| PUT    | `/api/projects/{id}/readme` | replace README.md |
| POST   | `/api/projects/{id}/sync` | push project to cloud |
| POST   | `/api/projects/{id}/pull` | pull project from cloud |

## Runs

| Method | Path | Purpose |
|--------|------|---------|
| POST   | `/api/projects/{project_id}/runs` | create a run under a project |
| GET    | `/api/projects/{project_id}/runs` | list runs (full tree, flat) |
| GET    | `/api/runs/{id}` | fetch run detail |
| PATCH  | `/api/runs/{id}` | edit name / parent_id |
| GET    | `/api/runs/{id}/manifests` | list manifests linked to a run |
| POST   | `/api/runs/{id}/manifests` | link a manifest to a run |
| DELETE | `/api/runs/{id}/manifests/{manifest_id}` | unlink a manifest from a run |
| DELETE | `/api/runs/{id}` | delete run + descendants |
| GET    | `/api/runs/{id}/files` | list run-level files |
| POST   | `/api/runs/{id}/files/download` | resolve download URLs for given paths |
| GET    | `/api/runs/{id}/files/content?path=…` | stream one file |
| GET    | `/api/runs/{id}/readme` | fetch README.md |
| PUT    | `/api/runs/{id}/readme` | replace README.md |
| POST   | `/api/runs/{id}/sync` | push run (+ project skeleton + ancestors) |
| POST   | `/api/runs/{id}/pull` | pull run from cloud |

## Manifests

| Method | Path | Purpose |
|--------|------|---------|
| POST   | `/api/manifests` | create a manifest |
| GET    | `/api/manifests` | list manifests (filter by `type`, `tags`, `is_public`) |
| GET    | `/api/manifests/{id}` | fetch manifest detail |
| PATCH  | `/api/manifests/{id}` | edit mutable fields |
| DELETE | `/api/manifests/{id}` | delete manifest (episodes stay) |
| GET    | `/api/manifests/{id}/runs` | list runs linked to a manifest |
| POST   | `/api/manifests/{id}/runs` | link a run to a manifest |
| DELETE | `/api/manifests/{id}/runs/{run_id}` | unlink a run from a manifest |
| POST   | `/api/manifests/{id}/episodes/add` | attach episodes to manifest |
| POST   | `/api/manifests/{id}/episodes/remove` | detach episodes |
| GET    | `/api/manifests/{id}/episodes` | list episodes in manifest |
| POST   | `/api/manifests/{id}/episodes/batch-get` | fetch episode detail + file URLs |
| POST   | `/api/manifests/{id}/sync` | push manifest + its episode payloads |
| POST   | `/api/manifests/{id}/pull` | pull manifest + episodes |

## Episodes

| Method | Path | Purpose |
|--------|------|---------|
| PATCH  | `/api/episodes/{id}` | edit `reward`, `task`, `task_description` (triggers manifest rollup recompute) |
| GET    | `/api/episodes/{id}/files/content?path=…` | stream an episode file |

## Sync (generic)

| Method | Path | Purpose |
|--------|------|---------|
| POST   | `/api/sync/plan` | build a `SyncPlan` without side effects (`required_id_remaps`, not concrete clone IDs) |
| POST   | `/api/sync/execute` | execute the plan (push/pull/clone for project/run/manifest) |
| POST   | `/api/sync/jobs` | start a background sync job and write `.artha/run/sync/<job_id>.json` progress |
| GET    | `/api/sync/jobs` | list recent sync progress files |
| GET    | `/api/sync/jobs/{job_id}` | read one sync progress file |

Body fields: `operation` (`push`/`pull`/`clone`), `entity_type`
(`project`/`run`/`manifest`), `entity_id`, `include_manifests?`,
`include_descendants?`, `cloud_api_base?`, `bearer_token?`. Blocking
`/api/sync/execute` also accepts `progress: true` to write a progress file.

Sync is additive. These endpoints create/update/copy/upload planned
records and files; they do not prune files missing from the source side.
Use explicit delete endpoints for destructive cleanup.

## Proxies (not STORE API)

| Path | Upstream |
|------|----------|
| `WS /ws` | bridge (`ws://127.0.0.1:8765/ws`) |
| `GET /video/{path}` | video_bridge (`http://127.0.0.1:9090/{path}`) |
| `GET /{path}` | SPA fallback — serves `frontend/dist/` |

See `concepts/bridge.md` and `concepts/cameras.md` for the upstreams.
