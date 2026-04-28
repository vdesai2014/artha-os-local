import { useMemo, useRef, useState } from 'react'

import { useNatsSubject, usePublish, useTopic } from '../../../lib/useBridge'
import type { RecordingContext } from '../api'

type RobStrideValues = {
  position: number[]
  velocity: number[]
  torque: number[]
  temperature: number[]
  enabled: number[]
}

type CameraPanelProps = {
  title: string
  src: string
}

type EvalStatus = {
  state?: string
  message?: string
  reason?: string | null
  run_id?: string | null
  episode?: {
    episode_id?: string
    manifest_name?: string
    manifest_id?: string
    length?: number
  } | null
}

type ProvenanceHeartbeat = {
  stats?: {
    context?: RecordingContext
  }
}

function CameraPanel({ title, src }: CameraPanelProps) {
  const imgRef = useRef<HTMLImageElement>(null)
  const [status, setStatus] = useState<'connecting' | 'live' | 'error'>('connecting')

  return (
    <div className="robot-tab-feed sim-camera-panel">
      <div className="feed-header">
        <p className="eyebrow">{title}</p>
        <span className={`status-dot status-dot-${status === 'live' ? 'green' : status === 'connecting' ? 'copper' : 'dim'}`} />
      </div>
      <div className="feed-viewport">
        <img
          ref={imgRef}
          src={src}
          alt={title}
          className="feed-img"
          onLoad={() => setStatus('live')}
          onError={() => setStatus('error')}
        />
        {status === 'connecting' && <div className="feed-overlay">Connecting...</div>}
        {status === 'error' && (
          <div className="feed-overlay">
            <span>No feed</span>
            <button
              className="button button-ghost"
              style={{ marginTop: 12, fontSize: 10 }}
              onClick={() => {
                setStatus('connecting')
                if (imgRef.current) {
                  imgRef.current.src = ''
                  imgRef.current.src = src
                }
              }}
            >
              Retry
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

// Block spawn range must match the training grid (vec_env.py in the act-ppo
// run): x ∈ [1.15, 1.55], y ∈ [-0.55, -0.22], z = BLOCK_Z_INIT (0.009).
// Sampling outside this region = out-of-distribution for the policy = erratic
// behavior.
function randomBlockPos() {
  const x = 1.15 + Math.random() * 0.40
  const y = -0.55 + Math.random() * 0.33
  const z = 0.009
  return [Number(x.toFixed(3)), Number(y.toFixed(3)), z]
}

export function ControlsPage() {
  const publish = usePublish()
  const data = useTopic<RobStrideValues>('sim_robot/actual', 'RobStrideState', 20)
  const evalStatus = useNatsSubject<EvalStatus>('eval.status')
  const provenanceHeartbeat = useNatsSubject<ProvenanceHeartbeat>('service.provenance.heartbeat')
  const recordingContext = provenanceHeartbeat?.stats?.context
  const [gravityEnabled, setGravityEnabled] = useState(true)
  const [lastSpawn, setLastSpawn] = useState<number[] | null>(null)

  const rows = useMemo(() => {
    const values = data?.values
    if (!values) return []
    return values.position.map((position, index) => ({
      index,
      position,
      velocity: values.velocity[index] ?? 0,
      torque: values.torque[index] ?? 0,
      enabled: values.enabled[index] ?? 0,
    }))
  }, [data])

  const evalState = (evalStatus?.state ?? 'idle').toLowerCase()
  const evalActive = evalState === 'preparing' || evalState === 'running'
  const evalTagClass = evalActive ? 'teleop-mode-tag teleop-mode-active' : 'teleop-mode-tag'

  const manifestLine = recordingContext?.manifest_name
    ? `${recordingContext.manifest_name}${recordingContext.manifest_type ? ` · ${recordingContext.manifest_type}` : ''}`
    : 'no manifest'
  const policyLine = recordingContext?.policy_name
    ? `${recordingContext.policy_name}${recordingContext.source_checkpoint ? ` · ${recordingContext.source_checkpoint}` : ''}`
    : 'no policy'
  const lastEpisodeLine = evalStatus?.episode?.episode_id
    ? `last ${evalStatus.episode.episode_id.slice(0, 10)}${evalStatus.episode.length ? ` · ${evalStatus.episode.length}f` : ''}`
    : 'last —'

  return (
    <div className="sim-controls-page">
      <header className="sim-controls-header">
        <div className="sim-controls-header-col">
          <div className="sim-controls-header-row">
            <p className="eyebrow">Sim Runtime</p>
            <span className={`teleop-mode-tag ${data ? 'teleop-mode-active' : ''}`}>
              {data ? 'LIVE' : 'WAITING'}
            </span>
          </div>
          <div className="sim-controls-header-meta">sim_robot/actual · 20 Hz</div>
          <div className="sim-controls-header-meta">
            {lastSpawn ? `last block [${lastSpawn.join(', ')}]` : 'no block spawned yet'}
          </div>
        </div>
        <div className="sim-controls-header-col sim-controls-header-col-right">
          <div className="sim-controls-header-row">
            <p className="eyebrow">Eval</p>
            <span className={evalTagClass} data-tour="eval-state">{evalState.toUpperCase()}</span>
          </div>
          <div className="sim-controls-header-meta" title={manifestLine} data-tour="manifest-name">{manifestLine}</div>
          <div className="sim-controls-header-meta" title={policyLine}>
            {policyLine}
            <span className="sim-controls-header-separator">·</span>
            {lastEpisodeLine}
          </div>
          {evalStatus?.message ? (
            <div className="sim-controls-header-message" title={evalStatus.message}>
              {evalStatus.message}
            </div>
          ) : null}
        </div>
      </header>

      <div className="sim-controls-cameras">
        <CameraPanel title="Overhead" src="/video/camera/overhead_ui" />
        <CameraPanel title="Gripper" src="/video/camera/gripper_ui" />
      </div>

      <div className="sim-joint-strip">
        {rows.length > 0 ? rows.map((row) => (
          <div key={row.index} className="sim-joint-cell">
            <div className="sim-joint-cell-head">
              <span className="eyebrow">J{row.index + 1}</span>
              <span className={`status-dot status-dot-${row.enabled ? 'green' : 'dim'}`} />
            </div>
            <div className="sim-joint-cell-values">
              <span>pos {row.position.toFixed(3)}</span>
              <span>vel {row.velocity.toFixed(3)}</span>
              <span>trq {row.torque.toFixed(3)}</span>
            </div>
          </div>
        )) : (
          <div className="sim-joint-cell-waiting">
            Waiting for telemetry from sim_robot/actual.
          </div>
        )}
      </div>

      <footer className="sim-controls-footer">
        <div className="sim-controls-group">
          <span className="sim-controls-group-label">World</span>
          <button className="joint-btn joint-btn-zero" onClick={() => publish('sim.reset', {})}>
            Reset
          </button>
          <button
            className="joint-btn joint-btn-enable"
            onClick={() => {
              const pos = randomBlockPos()
              setLastSpawn(pos)
              publish('sim.spawn_block', { pos })
            }}
          >
            Random Block
          </button>
          <button
            className="joint-btn joint-btn-disable"
            onClick={() => publish('sim.remove_block', {})}
          >
            Remove Block
          </button>
          <button
            className="joint-btn joint-btn-enable"
            onClick={() => {
              const next = !gravityEnabled
              setGravityEnabled(next)
              publish('sim.set_gravity', { enabled: next })
            }}
          >
            Gravity {gravityEnabled ? 'on' : 'off'}
          </button>
        </div>
        <div className="sim-controls-group">
          <span className="sim-controls-group-label">Policy</span>
          <button
            data-tour="start-eval"
            className={evalActive ? 'joint-btn joint-btn-disable' : 'joint-btn joint-btn-enable'}
            onClick={() => publish(evalActive ? 'eval.cancel' : 'eval.start', {})}
            title="Start or cancel one eval episode via the managed demo runner"
          >
            {evalActive ? 'Cancel Eval' : 'Start Eval'}
          </button>
          <button
            className="joint-btn joint-btn-zero"
            onClick={() => publish('sim.resume_commands', {})}
            title="Re-enable SHM command ingestion after a sim.set_qpos"
          >
            Resume SHM
          </button>
        </div>
      </footer>
    </div>
  )
}
