# Cloud

## What it is

`artha.bot` is a thin data + collaboration layer — **not compute**. It covers:

- Users, auth tokens (Clerk JWT or PATs), billing
- **Projects** — owner-scoped, hold code + file blobs
- **Runs** — a tree under a project (`parent_id`), each with its own files
- **Manifests** — collections of episodes with members + roles, independent
  of project ownership
- **Episodes** — user-owned data blobs, attachable to 0..N manifests

There is deliberately **no per-endpoint CLI wrapper**. Two reasons: the API
evolves independently of the OS, and the agent is already fluent in HTTP.
The agent interacts with the cloud via one of:

- **The sync tool** (`local_tool` push / pull / clone; CLI coming) — for
  the 90% cases: moving an entity between local and cloud
- **Raw HTTP in Python** from the CLI — for the long tail; creds live in
  `.artha/credentials.json`

## Resource graph

```
User
 ├── Project (owner-scoped)
 │    └── Run (tree via parent_id)
 │         └── files
 ├── Episode (user-owned, standalone blob)
 │    └── attached to 0..N Manifests via junction
 └── Manifest (owner + members with reader/writer roles)
      └── episode list
```

Projects/runs own their files directly. Episodes are *standalone* — they
exist independent of any manifest and can be attached to many manifests.
Manifest *membership* (who can read/write) is separate from project
ownership, which is what makes multi-robot data collection work: one
manifest, many contributors.

## Primary use cases

1. **Multi-robot data collection.** Each robot or instance pushes episodes
   to a shared manifest. Manifest writer-members let a team contribute
   without transferring ownership of individual episodes.

2. **Cloud GPU training.** Pull manifest episodes onto a rented GPU (RunPod
   or similar), train, then create a child run under your project and
   upload weights + training logs back. Locally, the agent loads the new
   checkpoint by editing `services.yaml` (see `concepts/supervisor.md`).

3. **Browse + clone public work.** Find a public project whose approach
   looks useful, clone it into the local workspace with fresh IDs, let
   the agent wire it up for your hardware. (Templates — a future curated
   layer of cloneable popular algorithms/models — will sit on top of this
   same primitive.)

## Invariants the agent must know up front

- **Auth:** Clerk JWT or PAT (`artha_...`). Read from
  `.artha/credentials.json` rather than asking the user.
- **Two-phase file upload:** `POST .../files/upload` returns presigned R2
  URLs + `pending_upload_ids`. `PUT` each file to its R2 URL. Then
  `POST .../files/commit` with the IDs. Orphaned uploads count against
  `reserved_bytes` until they're committed or expire.
- **IDs are `<prefix>_<32 hex>`:** `proj_`, `run_`, `mf_`, `ep_`, `tok_`.
  Client may supply (server validates format + uniqueness) or omit for
  server-generated.
- **Paths are canonicalized server-side.** `foo/./bar` and `foo/bar`
  collide; 400 on post-normalization duplicates.
- **`source_run_id` on a manifest is singular.** Cloud does not model
  multi-source manifests. Keep local in step.
- **PATCH is narrow.** Most resource fields are set at creation and
  immutable (manifest `type`, `fps`, `encoding`, `features`,
  `source_run_id`; project/run identity). Name/description/tags/is_public
  are patchable.

## Clone is client-side

There is no `/clone` endpoint. Cloning a project reads it + its runs via
GET, mints fresh local IDs, and creates entities in the local store. The
sync tool does this end-to-end. Clone plans are structural: `/api/sync/plan`
returns `required_id_remaps`, but does not mint concrete IDs. Agents should
use `artha clone` and capture the returned `id_remaps` before rewriting
`services.yaml` paths that reference old IDs. Only bypass the CLI for
intentional API integrations that need the same lower-level boundary.

## Full spec

- Canonical reference in repo: [`cloud-apis/cloud-api.md`](../cloud-apis/cloud-api.md)
- Live (coming): `artha.bot/api-spec.md`

For anything not covered by this concept doc, read the spec. Don't
paraphrase it here — it rots.
