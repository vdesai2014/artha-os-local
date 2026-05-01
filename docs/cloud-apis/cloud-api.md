# API Spec

Pure inputs/outputs for every endpoint. See [Data Model & API](data-model.md) for semantics.

**Auth shorthand:**

- `Bearer` — any authenticated user (Clerk JWT or PAT)
- `Owner` — must be the resource owner
- `Write` — owner or manifest member with role=writer
- `Read` — owner, member, or public
- `Webhook` — verified by signing secret, not user auth
- `Public` — no auth required

All authenticated endpoints accept `Authorization: Bearer <token>` where token is a Clerk JWT or PAT (`artha_...`).

---

## User

### GET /api/me

**Auth:** Bearer

**Response `200`:**
```json
{
  "id": "user_2x...",
  "username": "alice",
  "name": "Alice Chen",
  "email": "alice@stanford.edu",
  "image_url": "https://img.clerk.com/...",
  "bio": "Robotics PhD @ Stanford",
  "org": "Stanford ILIAD Lab",
  "created_at": "2026-03-20T10:00:00Z"
}
```

### PATCH /api/me

**Auth:** Bearer

**Request:**
```json
{
  "name?": "string",
  "image_url?": "string",
  "bio?": "string",
  "org?": "string"
}
```

Note: `email` is read-only and managed by Clerk.

**Response `200`:** Same shape as `GET /api/me`.

### GET /api/users/{username}

**Auth:** Public

**Path params:** `username` — user's username

Returns 404 if user has been deleted (`deleted_at IS NULL` filter).

**Response `200`:**
```json
{
  "username": "alice",
  "name": "Alice Chen",
  "image_url": "https://example.com/photo.jpg",
  "bio": "Robotics PhD @ Stanford",
  "org": "Stanford ILIAD Lab"
}
```

Note: `id` and `email` not exposed.

---

## Webhooks

### POST /api/webhooks/clerk

**Auth:** Webhook (Clerk signing secret)

**Events:** `user.created`, `user.deleted`

Body is Clerk's webhook payload format. Not called by clients.

### POST /api/webhooks/stripe

**Auth:** Webhook (Stripe signing secret)

**Events:** `checkout.session.completed`, `customer.subscription.updated`, `customer.subscription.deleted`, `invoice.payment_failed`

Body is Stripe's webhook payload format. Not called by clients.

---

## Auth Tokens

### POST /api/tokens

**Auth:** `kind: "root"` requires Clerk JWT (not mintable by PATs). `kind: "child"` requires Clerk JWT or root PAT. Child PATs cannot mint.

**Request (root):**
```json
{
  "kind": "root",
  "label": "my-laptop",
  "expires_in_days": 30
}
```

**Request (child):**
```json
{
  "kind": "child",
  "label": "gpu-worker-3",
  "expires_in_hours": 24
}
```

**Response `201`:**
```json
{
  "id": "tok_...",
  "token": "artha_k7x9m2...",
  "kind": "root",
  "label": "my-laptop",
  "expires_at": "2026-04-21T10:00:00Z"
}
```

Note: `token` returned **only on creation**.

### GET /api/tokens

**Auth:** Bearer

**Response `200`:**
```json
{
  "tokens": [
    {
      "id": "tok_...",
      "token_prefix": "artha_k",
      "kind": "root",
      "label": "my-laptop",
      "expires_at": "2026-04-21T10:00:00Z",
      "revoked_at": null,
      "last_used_at": "2026-03-22T08:00:00Z",
      "created_at": "2026-03-22T10:00:00Z"
    }
  ]
}
```

### DELETE /api/tokens/{id}

**Auth:** Bearer (must own the token)

**Path params:** `id` — token ID

**Response:** `204 No Content`

---

## Billing

### POST /api/billing/checkout

**Auth:** Bearer

**Request:**
```json
{
  "plan": "pro_250"
}
```

**Response `200`:**
```json
{
  "checkout_url": "https://checkout.stripe.com/..."
}
```

### GET /api/billing/status

**Auth:** Bearer

**Response `200`:**
```json
{
  "plan": "pro_250",
  "storage_bytes": 53687091200,
  "storage_limit_bytes": 268435456000,
  "storage_used_pct": 20.0,
  "subscription_status": "active",
  "current_period_end": "2026-04-20T00:00:00Z"
}
```

### POST /api/billing/portal

**Auth:** Bearer

**Response `200`:**
```json
{
  "portal_url": "https://billing.stripe.com/..."
}
```

---

## Project

### POST /api/projects

**Auth:** Bearer

`id` optional — server validates format (`proj_<32 hex>`) and uniqueness (409 on collision). Omit for server-generated ID.

**Request:**
```json
{
  "id?": "proj_...",
  "name": "string",
  "description?": "string",
  "tags?": ["string"],
  "is_public?": false
}
```

**Response `201`:**
```json
{
  "id": "proj_...",
  "owner_user_id": "user_2x...",
  "name": "pi-zero-folding",
  "description": "Cloth folding with pi-zero policy",
  "tags": ["manipulation", "cloth"],
  "is_public": false,
  "files": {},
  "created_at": "2026-03-22T10:00:00Z",
  "updated_at": "2026-03-22T10:00:00Z"
}
```

### GET /api/projects

**Auth:** Public for `scope=public` (default), Bearer required for `scope=mine`

**Query params:**

| Param | Type | Description |
|-------|------|-------------|
| `scope` | `public` \| `mine` | Listing scope. Default `public`. |
| `tags` | string? | Comma-separated tag filter |
| `order` | `newest` \| `oldest` | Sort order. Default `newest`. |
| `limit` | int? | Max per page (default 20, max 100) |
| `cursor` | string? | Opaque pagination cursor |

**Response `200`:**
```json
{
  "projects": [
    {
      "id": "proj_...",
      "owner_user_id": "user_2x...",
      "name": "pi-zero-folding",
      "description": "Cloth folding with pi-zero policy",
      "tags": ["manipulation", "cloth"],
      "is_public": true,
      "created_at": "2026-03-22T10:00:00Z",
      "updated_at": "2026-03-22T10:00:00Z"
    }
  ],
  "next_cursor": "eyJpZCI6..."
}
```

Note: `files` omitted from list. `next_cursor` is `null` when no more results.

### GET /api/projects/{id}

**Auth:** Read (owner or public)

**Path params:** `id` — project ID

**Response `200`:** Full project object (same as create response).

### PATCH /api/projects/{id}

**Auth:** Owner

**Path params:** `id` — project ID

**Request:**
```json
{
  "name?": "string",
  "description?": "string",
  "type?": "teleop|eval|intervention|synthetic",
  "tags?": ["string"],
  "is_public?": true,
  "fps?": 30,
  "encoding?": {},
  "features?": {},
  "success_rate?": 0.75,
  "rated_episodes?": 20
}
```

**Response `200`:** Updated project object.

### DELETE /api/projects/{id}

**Auth:** Owner

**Path params:** `id` — project ID

**Response:** `204 No Content`

### POST /api/projects/{id}/files/upload

**Auth:** Owner

**Path params:** `id` — project ID

All paths are canonicalized server-side (see Path Canonicalization). Duplicate paths after normalization rejected with 400.

**Request:**
```json
{
  "files": {
    "<path>": {"blake3": "string", "size": 0}
  }
}
```

**Response `200`:**
```json
{
  "to_upload": {
    "<path>": {
      "url": "https://r2.cloudflarestorage.com/...",
      "content_length": 204800
    }
  },
  "to_download": {
    "<path>": {"blake3": "string", "size": 0, "updated_at": "string"}
  },
  "synced": ["<path>"],
  "storage_delta": 204800,
  "pending_upload_ids": ["uuid-string"]
}
```

### POST /api/projects/{id}/files/commit

**Auth:** Owner

**Path params:** `id` — project ID

**Request:**
```json
{
  "pending_upload_ids": ["uuid-string"]
}
```

**Response `200`:**
```json
{
  "files": {
    "<path>": {"blake3": "string", "size": 0, "r2_key": "string", "updated_at": "string"}
  },
  "storage_delta": 204800
}
```

### POST /api/projects/{id}/files/download

**Auth:** Read (owner or public)

**Path params:** `id` — project ID

Paths canonicalized server-side before lookup.

**Request:**
```json
{
  "paths": ["<path>"]
}
```

**Response `200`:**
```json
{
  "urls": {
    "<path>": "https://r2.cloudflarestorage.com/..."
  }
}
```

### POST /api/projects/{id}/files/delete

**Auth:** Owner

**Path params:** `id` — project ID

Explicitly delete files. Removes from `files` JSONB, deletes R2 objects, decrements `storage_bytes`. Missing paths silently ignored. Paths canonicalized server-side.

**Request:**
```json
{
  "paths": ["<path>"]
}
```

**Response `200`:**
```json
{
  "deleted": ["<path>"],
  "not_found": [],
  "storage_delta": -205800
}
```

---

## Run

### POST /api/projects/{project_id}/runs

**Auth:** Owner (of project)

**Path params:** `project_id` — project ID

`id` optional — server validates format (`run_<32 hex>`) and uniqueness (409 on collision). Omit for server-generated ID.
`name` is trimmed server-side, must not be blank, and must be at most 160 characters.

If `parent_id` is provided, tree invariants are enforced: parent must be in the same project, no self-parenting, no cycles (400 on violation).

**Request:**
```json
{
  "id?": "run_...",
  "name": "string",
  "parent_id?": "string"
}
```

**Response `201`:**
```json
{
  "id": "run_...",
  "project_id": "proj_...",
  "parent_id": null,
  "name": "train-v1",
  "manifest_ids": [],
  "files": {},
  "created_at": "2026-03-22T10:00:00Z",
  "updated_at": "2026-03-22T10:00:00Z"
}
```

### GET /api/projects/{project_id}/runs

**Auth:** Read (owner or public)

**Path params:** `project_id` — project ID

**Query params:**

| Param | Type | Description |
|-------|------|-------------|
| `limit` | int? | Max per page (default 50, max 200) |
| `cursor` | string? | Opaque pagination cursor |

**Response `200`:**
```json
{
  "runs": [
    {
      "id": "run_...",
      "project_id": "proj_...",
      "parent_id": null,
      "name": "train-v1",
      "manifest_ids": ["mf_..."],
      "created_at": "2026-03-22T10:00:00Z",
      "updated_at": "2026-03-22T12:00:00Z"
    }
  ],
  "next_cursor": null
}
```

Note: `files` omitted from list. `manifest_ids` is included.

### GET /api/runs/{id}

**Auth:** Read (inherits from project)

**Path params:** `id` — run ID

**Response `200`:** Full run object (same as create response).

### PATCH /api/runs/{id}

**Auth:** Owner (of project)

**Path params:** `id` — run ID

If `parent_id` is changed, tree invariants are enforced: same project, no self-parenting, no cycles (400 on violation).

**Request:**
```json
{
  "name?": "string",
  "parent_id?": "string"
}
```

**Response `200`:** Updated run object.

### GET /api/runs/{id}/manifests

**Auth:** Read (inherits from project)

**Response `200`:**
```json
{
  "manifests": [
    {
      "id": "mf_...",
      "owner_user_id": "user_2x...",
      "owner_username": "alice",
      "name": "teleop-folding-v1",
      "description": "Teleoperated cloth folding demos",
      "type": "teleop",
      "tags": ["cloth", "folding"],
      "is_public": false,
      "fps": 30,
      "episode_count": 150,
      "created_at": "2026-03-22T10:00:00Z",
      "updated_at": "2026-03-22T10:00:00Z"
    }
  ]
}
```

### POST /api/runs/{id}/manifests

**Auth:** Write access to run project and manifest

**Request:**
```json
{
  "manifest_id": "mf_..."
}
```

**Response `201`:**
```json
{
  "run_id": "run_...",
  "manifest_id": "mf_..."
}
```

### DELETE /api/runs/{id}/manifests/{manifest_id}

**Auth:** Write access to run project and manifest

**Response:** `204 No Content`

### DELETE /api/runs/{id}

**Auth:** Owner (of project)

**Path params:** `id` — run ID

Deletes the run and its entire subtree (descendants, their files). Decrements storage for all files across the subtree. Clients should confirm with user if run has children.

**Response:** `204 No Content`

### POST /api/runs/{id}/files/upload

**Auth:** Owner (of project)

**Path params:** `id` — run ID

Same request/response as `POST /api/projects/{id}/files/upload`.

### POST /api/runs/{id}/files/commit

**Auth:** Owner (of project)

**Path params:** `id` — run ID

Same request/response as `POST /api/projects/{id}/files/commit`.

### POST /api/runs/{id}/files/download

**Auth:** Read (inherits from project)

**Path params:** `id` — run ID

Same request/response as `POST /api/projects/{id}/files/download`.

### POST /api/runs/{id}/files/delete

**Auth:** Owner (of project)

**Path params:** `id` — run ID

Same request/response as `POST /api/projects/{id}/files/delete`.

---

## Manifest

### POST /api/manifests

**Auth:** Bearer

`id` optional — server validates format (`mf_<32 hex>`) and uniqueness (409 on collision). Omit for server-generated ID.

**Request:**
```json
{
  "id?": "mf_...",
  "name": "string",
  "description?": "string",
  "type": "teleop|eval|intervention|synthetic",
  "tags?": ["string"],
  "is_public?": false,
  "fps": 30,
  "encoding?": {},
  "features?": {
    "<key>": {"dtype": "string", "shape": [0]}
  },
  "success_rate?": 0.75,
  "rated_episodes?": 20
}
```

**Response `201`:**
```json
{
  "id": "mf_...",
  "owner_user_id": "user_2x...",
  "name": "teleop-folding-v1",
  "description": "Teleoperated cloth folding demos",
  "type": "teleop",
  "tags": ["cloth", "folding"],
  "is_public": false,
  "fps": 30,
  "encoding": {"video_codec": "h264"},
  "features": {
    "observation.images.overhead": {"dtype": "video", "shape": [480, 640, 3]}
  },
  "run_ids": [],
  "success_rate": 0.75,
  "rated_episodes": 20,
  "episode_count": 0,
  "created_at": "2026-03-22T10:00:00Z",
  "updated_at": "2026-03-22T10:00:00Z"
}
```

### GET /api/manifests

**Auth:** Public only for `scope=public` or when unauthenticated. Bearer required for `scope=all` (default), `mine`, and `shared`.

**Query params:**

| Param | Type | Description |
|-------|------|-------------|
| `scope` | `all` \| `mine` \| `shared` \| `public` | Listing scope. Default `all`. |
| `owner` | string? | Filter by username |
| `is_public` | bool? | Filter by public flag |
| `tags` | string? | Comma-separated tag filter |
| `type` | string? | Filter by manifest type |
| `limit` | int? | Max per page (default 20, max 100) |
| `cursor` | string? | Opaque pagination cursor |

Scope semantics:
- `all`: owned + shared-with-me + public (auth required)
- `mine`: owned only (auth required)
- `shared`: member but not owner (auth required)
- `public`: public manifests only

**Response `200`:**
```json
{
  "manifests": [
    {
      "id": "mf_...",
      "owner_user_id": "user_2x...",
      "owner_username": "alice",
      "name": "teleop-folding-v1",
      "description": "Teleoperated cloth folding demos",
      "type": "teleop",
      "tags": ["cloth", "folding"],
      "is_public": true,
      "fps": 30,
      "run_ids": ["run_..."],
      "success_rate": 0.75,
      "rated_episodes": 20,
      "episode_count": 150,
      "created_at": "2026-03-22T10:00:00Z",
      "updated_at": "2026-03-22T10:00:00Z"
    }
  ],
  "next_cursor": null
}
```

Note: `features` and `encoding` omitted from list. `run_ids` is included.

### GET /api/manifests/{id}

**Auth:** Read (owner, member, or public)

**Path params:** `id` — manifest ID

**Response `200`:** Full manifest object. Includes `members` array if caller is the owner or an existing manifest member; public non-members do not receive the member roster.

### PATCH /api/manifests/{id}

**Auth:** Owner

**Path params:** `id` — manifest ID

**Request:**
```json
{
  "name?": "string",
  "description?": "string",
  "tags?": ["string"],
  "is_public?": true
}
```

**Response `200`:** Updated manifest object.

### DELETE /api/manifests/{id}

**Auth:** Owner

**Path params:** `id` — manifest ID

**Response:** `204 No Content`

### GET /api/manifests/{id}/runs

**Auth:** Read (owner, member, or public)

**Response `200`:**
```json
{
  "runs": [
    {
      "id": "run_...",
      "project_id": "proj_...",
      "parent_id": null,
      "name": "train-v1",
      "created_at": "2026-03-22T10:00:00Z",
      "updated_at": "2026-03-22T12:00:00Z"
    }
  ]
}
```

### POST /api/manifests/{id}/runs

**Auth:** Write access to manifest and run project

**Request:**
```json
{
  "run_id": "run_..."
}
```

**Response `201`:**
```json
{
  "run_id": "run_...",
  "manifest_id": "mf_..."
}
```

### DELETE /api/manifests/{id}/runs/{run_id}

**Auth:** Write access to manifest and run project

**Response:** `204 No Content`

### POST /api/manifests/{id}/members

**Auth:** Owner

**Path params:** `id` — manifest ID

**Request:**
```json
{
  "user_id": "user_2y...",
  "role": "reader|writer"
}
```

**Response `200`:**
```json
{
  "manifest_id": "mf_...",
  "user_id": "user_2y...",
  "role": "writer",
  "added_at": "2026-03-22T10:00:00Z"
}
```

### DELETE /api/manifests/{id}/members/{user_id}

**Auth:** Owner

**Path params:** `id` — manifest ID, `user_id` — member to remove

**Response:** `204 No Content`

### POST /api/manifests/{id}/episodes/add

**Auth:** Write on destination manifest. Per-episode: caller must own the episode OR episode must be in `source_manifest_id` (requires read access to source).

**Path params:** `id` — destination manifest ID

**Request:**
```json
{
  "episode_ids": ["ep_...", "ep_..."],
  "source_manifest_id?": "mf_..."
}
```

**Response `200`:**
```json
{
  "added": 3,
  "already_linked": 0
}
```

**Errors:** Per-episode messages, e.g. `"Episode ep_xyz: not owned by you and not found in source manifest mf_abc"`

### POST /api/manifests/{id}/episodes/remove

**Auth:** Write (owner or writer member)

**Path params:** `id` — manifest ID

**Request:**
```json
{
  "episode_ids": ["ep_..."]
}
```

**Response `200`:**
```json
{
  "removed": 1
}
```

### GET /api/manifests/{id}/episodes

**Auth:** Read (owner, member, or public)

**Path params:** `id` — manifest ID

**Query params:** `task?`, `limit?` (default 20, max 100), `cursor?`

**Response `200`:**
```json
{
  "episodes": [
    {
      "id": "ep_...",
      "length": 500,
      "task": "fold_cloth",
      "task_description": "Fold a cloth in half",
      "features": {},
      "size_bytes": 2099200,
      "created_at": "2026-03-22T10:00:00Z"
    }
  ],
  "next_cursor": null
}
```

### POST /api/manifests/{id}/episodes/batch-get

**Auth:** Read (owner, member, or public)

**Path params:** `id` — manifest ID

**Request:**
```json
{
  "episode_ids": ["ep_...", "ep_..."]
}
```

**Response `200`:**
```json
{
  "episodes": [
    {
      "id": "ep_...",
      "length": 500,
      "task": "fold_cloth",
      "features": {},
      "files": {
        "<filename>": {
          "url": "https://r2.cloudflarestorage.com/...",
          "size": 2048000
        }
      }
    }
  ]
}
```

---

## Episode

### GET /api/episodes

**Auth:** Bearer (returns only own episodes)

**Query params:** `manifest_id?` (filter by manifest; `none` = unattached episodes), `task?`, `limit?` (default 20, max 100), `cursor?`

**Response `200`:**
```json
{
  "episodes": [
    {
      "id": "ep_...",
      "length": 500,
      "task": "fold_cloth",
      "task_description": "Fold a cloth in half",
      "features": {},
      "size_bytes": 2099200,
      "manifest_ids": ["mf_...", "mf_..."],
      "created_at": "2026-03-22T10:00:00Z"
    }
  ],
  "next_cursor": null
}
```

### POST /api/episodes/upload

**Auth:** Bearer

Episode `id` is client-provided. Server validates format (`ep_<32 hex>`) — 400 on malformed, existing episodes with matching ID + blake3 are returned as `existing`.

**Request:**
```json
{
  "episodes": [
    {
      "id": "ep_...",
      "length": 500,
      "task?": "string",
      "task_description?": "string",
      "features?": {
        "<key>": {"dtype": "string", "shape": [0]}
      },
      "files": {
        "<filename>": {"blake3": "string", "size": 0}
      }
    }
  ]
}
```

**Response `200`:**
```json
{
  "new": {
    "ep_...": {
      "files": {
        "<filename>": {
          "url": "https://r2.cloudflarestorage.com/...",
          "content_length": 2048000
        }
      },
      "pending_upload_ids": ["pending_..."]
    }
  },
  "existing": ["ep_other..."],
  "errors": {},
  "storage_delta": 2099200
}
```

### POST /api/episodes/commit

**Auth:** Bearer

**Request:**
```json
{
  "pending_upload_ids": ["uuid-string"]
}
```

**Response `200`:**
```json
{
  "committed": ["ep_..."],
  "storage_delta": 2099200
}
```

### POST /api/episodes/batch-get

**Auth:** Bearer (returns only episodes where `uploaded_by_user_id = caller`)

**Request:**
```json
{
  "episode_ids": ["ep_...", "ep_..."]
}
```

**Response `200`:** Same shape as `POST /api/manifests/{id}/episodes/batch-get`.

### DELETE /api/episodes/{id}

**Auth:** Bearer (must own the episode: `uploaded_by_user_id = caller`)

**Path params:** `id` — episode ID

Deletes an episode. Removes from all manifests (junction rows), deletes R2 files. Committed episodes decrement `storage_bytes`; uncommitted episodes release `reserved_bytes` via pending uploads. Works on committed and uncommitted episodes.

**Response:** `204 No Content`
