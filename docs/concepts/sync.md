# sync

`local_tool/sync/` moves entities between the local store and the cloud.
Three operations: **push**, **pull**, **clone**. That's the whole
surface.

Agents should normally use the CLI (`artha push`, `artha pull`,
`artha clone`). This doc explains the backing sync engine and HTTP API
for debugging or advanced integrations.

## Not git

It is tempting to reach for git analogies. Resist them.

| git | sync |
|-----|------|
| history | no history — the cloud is the latest state |
| branches, merges | neither |
| tracks code changes | tracks *entities* (projects, runs, manifests, episodes) |
| optimizes for diffs | optimizes for fast iteration + provenance |

The point is **provenance**, not versioning. The local manifest tracks
which runs contributed its episodes; a run tracks which manifest it
trained on. The cloud stores the edges so any machine can answer: *which
dataset trained this checkpoint?* That's what we pay for, not a commit
graph.

## The three operations

### push

Upload local entity + its children to the cloud. Additive only; does
not delete remote content.

- **Project push:** project + all runs; manifests opt-in via
  `include_manifests=True`.
- **Run push:** run + project skeleton + ancestor-chain. Descendants
  opt-in via `include_descendants=True`; linked manifests opt-in via
  `include_manifests=True`.
- **Manifest push:** manifest + its episode payloads.

IDs are preserved. The pusher is the owner.

`.arthaignore` applies — patterns filter project/run file uploads, not
episode payloads.

### pull

Download cloud entity into the local store. IDs are preserved; the
puller owns a local mirror of the same thing. Calling pull twice
updates in place.

- **Project pull:** project + runs; manifests opt-in via
  `include_manifests=True`.
- **Run pull:** run + project skeleton + ancestor-chain. Descendants
  opt-in via `include_descendants=True`; linked manifests opt-in via
  `include_manifests=True`.
- **Manifest pull:** manifest + its episodes. Pull also stores the
  manifest's linked `run_ids`, but does not pull those run records/files.
  If a linked run is not present locally, the viewer shows the linked ID
  and reports that local run metadata is unavailable.

### clone

Copy a cloud project (typically someone else's public one) into the
local store **with fresh local IDs**. Now you own it; you can modify
and push back to *your* project. No cloud-side operation exists — this
is entirely client-side: fetch, remap IDs, create locally.

Only projects clone, for now. Covered scope: project + all runs +
project/run files. Not episodes or manifests.

## id_remaps

Clone mints new IDs at execution time. A clone plan is structural: it
reports which source IDs require remapping, but does not reserve or mint
the concrete target IDs.

Normal agent workflow:

```bash
artha clone <public_project_id> --output /tmp/clone-result.json
python3 -c "import json; print(json.load(open('/tmp/clone-result.json'))['id_remaps'])"
```

Internal/API flow:

```python
plan = plan_sync(ctx, operation="clone", entity_type="project", entity_id=<public_project_id>)
plan.required_id_remaps       # {"projects": ["proj_..."], "runs": ["run_..."]}
plan.id_remaps                # {}
result = execute_sync_plan(ctx, plan, config)
old_to_new = result.plan.id_remaps
```

`SyncResult.to_dict()` surfaces execution's authoritative `id_remaps`.
Only bypass the CLI if you are intentionally building an API client or
debugging the sync boundary.

**Rewrite `services.yaml` after clone.** The old cloud IDs still appear
in paths and env vars (`workspace/<name>__<short_id>/…`,
`SOURCE_PROJECT_ID: proj_<hex>`). Loop the remap, `text.replace` both
the full ID and its 8-char short form, write back. Without this, the
supervisor launches services pointed at nonexistent directories.

Clone is not idempotent — rerunning creates a second local project.
`rm -rf workspace/<name>__*` before retrying a failed clone.

## Additive Semantics

Sync is intentionally additive. `push`, `pull`, and `clone` create,
patch, copy, or upload records/files that are in the resolved plan; they
do not delete anything that is merely absent from the other side.

This means:

- Pushing a local project with fewer files than the cloud copy does not
  prune remote files.
- Pulling from cloud does not delete local-only files.
- Cloning always creates a fresh local project with fresh IDs.
- Removing obsolete cloud assets, such as spare checkpoints, requires an
  explicit cloud file-delete API call.

Agents should treat sync as a monotonic transfer primitive, not a
bidirectional mirror.

## Run ↔ manifest associations

Local and cloud both model run-manifest links as a simple bidirectional
association:

- Local runs store `manifest_ids`.
- Local manifests store `run_ids`.
- Cloud stores the pair in `run_manifests`.

The association is explicit metadata. Sync only follows run → manifest
edges when `include_manifests=True`; otherwise project/run push/pull
stays project/run-only. Manifest pull is manifest-centric, so it always
pulls episodes and also preserves the manifest's `run_ids` for display.

Episode provenance remains separate: `source_project_id`,
`source_run_id`, `source_checkpoint`, `policy_name`, `collection_mode`,
and `reward` live on the episode.

## The phases

Planning and execution are split:

```python
plan   = plan_sync(ctx, operation=..., entity_type=..., entity_id=...)
config = resolve_cloud_sync_config(...)
result = execute_sync_plan(ctx, plan, config)
```

- `plan_sync` resolves scope, reads remote/local state, builds
  metadata, file, and association actions. No mutation.
- `execute_sync_plan` applies the actions in order: metadata, files,
  then associations. Remote run-manifest changes go through the cloud
  association endpoints; local changes go through the store APIs.

Convenience wrappers (`sync_project_to_cloud`,
`pull_project_from_cloud`, etc.) compose plan+execute for the common
cases. CLI commands use these boundaries; call the Python functions
directly only when debugging or building another integration.

## Credentials

`resolve_cloud_sync_config` reads (in priority):

1. `cloud_api_base` / `bearer_token` args
2. `ARTHA_CLOUD_API_BASE` / `ARTHA_CLOUD_TOKEN` env vars
3. `.artha/credentials.json` (file mode 600)
4. Default base `https://artha.bot`

Pull works without a token for public content; push requires one.
