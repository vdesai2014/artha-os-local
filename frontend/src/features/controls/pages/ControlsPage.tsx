import { useNatsSubject } from '../../../lib/useBridge'
import type { RecordingContext } from '../api'

/**
 * ControlsPage — neutral scaffold for robot controls & telemetry.
 *
 * This is where you wire up *your* robot's UI:
 *
 *   - Telemetry: read SHM topics via `useTopic(topic, TypeName, rate)` from
 *     `lib/useBridge.ts`. Matches a `ctypes.Structure` declared in
 *     `core/types.py`.
 *   - Video feeds: `<img src="/video/<topic>" />` (proxied to video_bridge;
 *     see `docs/concepts/cameras.md`).
 *   - Commands: `usePublish()` for fire-and-forget NATS, `natsRequest()` for
 *     request/reply. Subjects are your own convention — e.g. `sim.reset`,
 *     `commander.enable`, `mybot.foot_pedal`.
 *   - Recording context: `provenance.context` + the helpers in `./api.ts`.
 *
 * The agent may replace this file wholesale to fit the user's robot. The
 * sim-demo onboarding project ships its own variant that extends this with
 * joint telemetry, camera panels, and an eval button.
 */
export function ControlsPage() {
  const recordingContext = useNatsSubject<RecordingContext>('provenance.context')

  return (
    <div className="controls-page">
      <header className="controls-header">
        <p className="eyebrow">Controls</p>
        <h1>Robot telemetry &amp; control</h1>
        <p className="controls-subtitle">
          Stream joint state, camera feeds, and run commands from here.
          Edit <code>frontend/src/features/controls/pages/ControlsPage.tsx</code>.
        </p>
      </header>

      <section className="controls-placeholder">
        <h2>Telemetry</h2>
        <p>
          No topics wired up yet. Use <code>useTopic()</code> from
          <code> lib/useBridge.ts</code> to stream any SHM struct declared in
          <code> core/types.py</code>.
        </p>
      </section>

      <section className="controls-placeholder">
        <h2>Video</h2>
        <p>
          Camera feeds live at <code>/video/&lt;topic&gt;</code>, served by the
          Rust <code>video_bridge</code> service. Set
          <code> ipc.subscribes</code> on <code>video_bridge</code> in
          <code> services.yaml</code> to expose a topic here.
        </p>
      </section>

      <section className="controls-placeholder">
        <h2>Commands</h2>
        <p>
          Publish NATS from <code>usePublish()</code>. Convention:
          <code> &lt;service&gt;.&lt;verb&gt;</code>, e.g.
          <code> commander.enable</code>, <code>sim.reset</code>.
        </p>
      </section>

      <section className="controls-placeholder">
        <h2>Recording context</h2>
        {recordingContext ? (
          <pre className="controls-context">
            {JSON.stringify(recordingContext, null, 2)}
          </pre>
        ) : (
          <p>
            Waiting for <code>provenance.context</code> from the provenance
            service. See <code>docs/concepts/</code> for how provenance and the
            data recorder coordinate.
          </p>
        )}
      </section>
    </div>
  )
}
