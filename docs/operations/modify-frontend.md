# Modifying the frontend

The frontend is React 19 + Vite. It's intended to be hacked — the
user's agent edits it regularly to surface new telemetry, add
controls, or swap out a page for project-specific UI. You don't have
to preserve a separation of concerns; edit whatever you need.

## Layout

```
frontend/
  index.html
  package.json
  tsconfig.json
  vite.config.ts
  src/
    main.tsx               # entry; mounts <RouterProvider>
    index.css              # global styles — all of them
    app/
      App.tsx              # shell wrapper around <Outlet />
      router.tsx           # all routes live here
      env.ts               # VITE_API_BASE etc.
    components/
      layout/              # AppShell, Sidebar
      ui/                  # Button, Modal, Breadcrumbs — shared primitives
    features/
      auth/                # minimal local auth helper
      controls/            # the controls page (neutral scaffold by default)
      datasets/            # dataset browser + parquet viewer
      projects/            # project + run detail, README editor, file tree
    lib/
      api.ts               # fetch wrapper for /api/*
      useBridge.ts         # the SHM/NATS hook surface
```

## The hook surface (`lib/useBridge.ts`)

Everything streams through one WebSocket to the bridge service. The
hooks:

```tsx
import { useTopic, useNatsSubject, usePublish, natsRequest } from '../../lib/useBridge'

// Stream a SHM struct at a requested rate
const data = useTopic<MyStructShape>('robot/actual', 'MyRobotState', 20)
// data is { values, timestamp, frame_id } | null

// Stream a NATS subject's payload
const evalStatus = useNatsSubject<EvalStatus>('eval.status')

// Fire-and-forget NATS publish
const publish = usePublish()
publish('sim.reset', {})
publish('commander.enable', {})

// NATS request/reply with a 2s timeout (used for, e.g., provenance.get)
const ctx = await natsRequest<RecordingContext>('provenance.get', {})
```

The bridge drops any `data` / `_pad` field or any array >1000 elements
from WebSocket payloads — camera frames go through `/video/<topic>`
instead, served by `video_bridge`. Just use `<img src="/video/<topic>" />`
in JSX.

## Adding a page

1. Create a file under `features/<feature>/pages/MyPage.tsx`. Write
   it as a plain React component using the hooks above.
2. Register it in `app/router.tsx`:
   ```tsx
   { path: 'my-page', element: <MyPage /> }
   ```
3. If it should appear in the sidebar, edit `components/layout/Sidebar.tsx`
   (there's a `navItems` array at the top).

## Dev loop

Two modes:

```bash
# Dev server with HMR — rebuilds on every save
cd frontend && npm run dev
# Open http://localhost:5173  (NOT 8000 — dev server has its own port)
```

```bash
# Production build, served by local_tool at :8000
cd frontend && npm run build
# Then restart local_tool if dist/ was absent when it started,
# otherwise just refresh the browser.
```

Use `npm run dev` while iterating; use `npm run build` + local_tool
when you want to confirm the prod bundle works.

## Project overlay convention

Demo projects (like grasp-pickup) may ship their own `ControlsPage.tsx`
at `workspace/<project>/frontend/ControlsPage.tsx`. The agent copies
this over `frontend/src/features/controls/pages/ControlsPage.tsx` at
onboarding time. See `docs/onboarding-steps.md` §8c.

The neutral scaffold is preserved at `docs/templates/ControlsPage.tsx`
— restore it when unmounting a project.

A future `artha apply-overlay <project>` CLI verb will automate this;
for now it's a manual `cp`.

## Styling

All styles live in one file: `src/index.css`. Class-based,
copper-accent theme. Add classes there rather than reaching for a
styling library. Shared primitives (button, modal, status-dot) have
stable class names; prefer reusing them.

## Proxies to remember

`local_tool` at `:8000` forwards:
- `GET /video/<topic>` → `http://127.0.0.1:9090/<topic>` (video_bridge MJPEG)
- `WS  /ws`            → `ws://127.0.0.1:8765/ws` (bridge)
- `GET /api/*`         → local_tool HTTP store
- everything else      → SPA (`frontend/dist/index.html`)

So from the browser, one origin (`localhost:8000`) covers everything.

## Common tasks

**Show a new SHM topic's values:**
1. Confirm the topic is published (check `services.yaml`, check
   `artha shm read` if CLI available).
2. `useTopic('<topic>', '<TypeName>', <rate_hz>)` in a component.
3. Render `data?.values`. Done.

**Trigger a NATS command on a button:**
```tsx
const publish = usePublish()
<button onClick={() => publish('my_service.reset', {})}>Reset</button>
```

**Display a camera feed:**
```tsx
<img src="/video/<topic>" alt="..." />
```
With status handling, see `features/controls/pages/ControlsPage.tsx`
for the `<CameraPanel>` pattern.

**Embed a time-series plot of joint positions over time:**
See `features/datasets/TimeSeriesPlot.tsx` for a uPlot-based example.

## Build output

`npm run build` produces `frontend/dist/` (gitignored). `local_tool`
detects this directory at startup and mounts it. If you build *after*
starting local_tool, restart local_tool for the SPA to appear.
