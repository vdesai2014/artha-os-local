import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { Button } from '../../../components/ui/Button'
import { Breadcrumbs } from '../../../components/ui/Breadcrumbs'
import { useAuth, useUser } from '../../auth/localAuth'
import { FilesPanel } from '../components/FilesPanel'
import { ManifestLinkPickerModal } from '../components/ManifestLinkPickerModal'
import { MarkdownReadmeEditor } from '../components/MarkdownReadmeEditor'
import { ManifestViewerModal } from '../components/ManifestViewerModal'
import { downloadRunFiles, getProject, getRun, getRunReadme, listManifests, listRunFiles, listRuns, updateRun } from '../api'
import { saveRunReadme } from '../runReadmeSync'
import type { FileListEntry, ManifestSummary, ProjectDetail, RunDetail, RunLink, RunSummary } from '../types'

function formatDate(value: string) {
  return new Date(value).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}

function classifyLinkBucket(link: RunLink) {
  return ['input_data', 'input_model', 'input_code'].includes(link.type) ? 'inputs' : 'outputs'
}

function LinkCard({
  link,
  canRemove,
  onClick,
  onRemove,
}: {
  link: RunLink
  canRemove: boolean
  onClick?: (link: RunLink) => void
  onRemove?: (link: RunLink) => void
}) {
  return (
    <div className="run-link-card">
      <div className="run-link-card-head">
        <button type="button" className="run-link-card-main" onClick={() => onClick?.(link)}>
          <div className="run-link-card-top">
            <span>{link.type.replace(/_/g, ' ')}</span>
            <code>{link.target_type}</code>
          </div>
          <strong>{link.label || link.target_id}</strong>
          <span>{link.target_id}</span>
          {link.path ? <small>{link.path}</small> : null}
        </button>
        {canRemove ? (
          <button
            type="button"
            className="run-link-remove"
            aria-label="Remove link"
            onClick={() => onRemove?.(link)}
          >
            ×
          </button>
        ) : null}
      </div>
    </div>
  )
}

function RunLinksPanel({
  title,
  links,
  canAdd,
  canRemove,
  onAdd,
  onLinkClick,
  onRemoveLink,
}: {
  title: string
  links: RunLink[]
  canAdd: boolean
  canRemove: boolean
  onAdd: () => void
  onLinkClick: (link: RunLink) => void
  onRemoveLink: (link: RunLink) => void
}) {
  return (
    <section className="run-detail-card run-links-panel">
      <div className="run-detail-card-header">
        <span>{title}</span>
        <span className="run-detail-card-header-actions">
          <span>{links.length}</span>
          {canAdd ? (
            <button type="button" className="project-inline-action" onClick={onAdd}>
              + link
            </button>
          ) : null}
        </span>
      </div>
      {links.length === 0 ? (
        <p className="project-detail-empty">No {title.toLowerCase()} linked yet.</p>
      ) : (
        <div className="run-links-grid">
          {links.map((link, index) => (
            <LinkCard
              key={`${link.target_id}-${index}`}
              link={link}
              canRemove={canRemove}
              onClick={onLinkClick}
              onRemove={onRemoveLink}
            />
          ))}
        </div>
      )}
    </section>
  )
}

export function RunDetailPage({ workspace }: { workspace: boolean }) {
  const { projectId, runId } = useParams()
  const { getToken } = useAuth()
  const { user } = useUser()

  const [project, setProject] = useState<ProjectDetail | null>(null)
  const [run, setRun] = useState<RunDetail | null>(null)
  const [files, setFiles] = useState<Record<string, FileListEntry>>({})
  const [runs, setRuns] = useState<RunSummary[]>([])
  const [manifests, setManifests] = useState<ManifestSummary[]>([])
  const [manifestPickerScope, setManifestPickerScope] = useState<'all' | 'shared'>('all')
  const [readme, setReadme] = useState('')
  const [savedReadme, setSavedReadme] = useState('')
  const [readmeRevision, setReadmeRevision] = useState(0)
  const [readmeState, setReadmeState] = useState<'idle' | 'loading' | 'ready' | 'missing' | 'error'>('idle')
  const [saveState, setSaveState] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle')
  const [saveError, setSaveError] = useState<string | null>(null)
  const [linkingBucket, setLinkingBucket] = useState<'inputs' | 'outputs' | null>(null)
  const [selectedManifestId, setSelectedManifestId] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const loadRunPage = useCallback(async () => {
    if (!projectId || !runId) {
      setError('Missing run or project id.')
      setLoading(false)
      return
    }

    setLoading(true)
    setError(null)

    try {
      const [projectResponse, runResponse, filesResponse, runsResponse] = await Promise.all([
        getProject(projectId, getToken),
        getRun(runId, getToken),
        listRunFiles(runId, getToken),
        listRuns(projectId, getToken),
      ])

      setProject(projectResponse)
      setRun(runResponse)
      setFiles(filesResponse.files)
      setRuns(runsResponse.runs)

      if (runResponse.has_readme) {
        setReadmeState('loading')
        const response = await getRunReadme(runId)
        const text = response.content
        setReadme(text)
        setSavedReadme(text)
        setReadmeRevision((revision) => revision + 1)
        setReadmeState('ready')
      } else {
        setReadme('')
        setSavedReadme('')
        setReadmeRevision((revision) => revision + 1)
        setReadmeState('missing')
      }

      setSaveState('idle')
      setSaveError(null)
    } catch (loadError) {
      setError((loadError as Error).message || 'Failed to load run.')
      setReadmeState('error')
    } finally {
      setLoading(false)
    }
  }, [projectId, runId, getToken])

  useEffect(() => {
    void loadRunPage()
  }, [loadRunPage])

  useEffect(() => {
    setLinkingBucket(null)
    setSelectedManifestId(null)
  }, [projectId, runId])

  useEffect(() => {
    let cancelled = false

    async function loadManifestList() {
      try {
        const response = await listManifests(getToken, { scope: manifestPickerScope })
        if (!cancelled) {
          setManifests(response.manifests)
        }
      } catch {
        if (!cancelled) {
          setManifests([])
        }
      }
    }

    void loadManifestList()
    return () => {
      cancelled = true
    }
  }, [getToken, manifestPickerScope])

  const isOwner = project?.owner_user_id === user?.id
  const readmeDirty = useMemo(() => readme !== savedReadme, [readme, savedReadme])
  const parentRun = useMemo(() => runs.find((entry) => entry.id === run?.parent_id) ?? null, [runs, run?.parent_id])
  const childRuns = useMemo(() => runs.filter((entry) => entry.parent_id === run?.id), [runs, run?.id])
  const inputLinks = useMemo(() => (run?.links ?? []).filter((link) => classifyLinkBucket(link) === 'inputs'), [run?.links])
  const outputLinks = useMemo(() => (run?.links ?? []).filter((link) => classifyLinkBucket(link) === 'outputs'), [run?.links])

  async function handleAddManifestLink(manifest: ManifestSummary) {
    if (!run || !linkingBucket) return
    const nextType = linkingBucket === 'inputs' ? 'input_data' : 'output_data'
    const duplicate = run.links.some((link) => link.target_type === 'manifest' && link.target_id === manifest.id && link.type === nextType)
    if (duplicate) {
      setLinkingBucket(null)
      return
    }

    const nextLinks = [
      ...run.links,
      {
        type: nextType,
        target_type: 'manifest',
        target_id: manifest.id,
        label: manifest.name,
      },
    ]

    await updateRun(run.id, { links: nextLinks }, getToken)
    setRun((current) => (current ? { ...current, links: nextLinks } : current))
    setLinkingBucket(null)
  }

  async function handleRemoveLink(target: RunLink) {
    if (!run) return
    const nextLinks = run.links.filter((link) => !(
      link.type === target.type
      && link.target_type === target.target_type
      && link.target_id === target.target_id
      && (link.path ?? null) === (target.path ?? null)
      && (link.label ?? null) === (target.label ?? null)
    ))
    await updateRun(run.id, { links: nextLinks }, getToken)
    setRun((current) => (current ? { ...current, links: nextLinks } : current))
  }

  function handleLinkClick(link: RunLink) {
    if (link.target_type === 'manifest') {
      setSelectedManifestId(link.target_id)
    }
  }

  async function handleSaveReadme() {
    if (!run || !isOwner || !readmeDirty) return
    setSaveState('saving')
    setSaveError(null)
    try {
      await saveRunReadme(run.id, readme, getToken)
      setRun((current) => {
        if (!current) return current
        return {
          ...current,
          has_readme: true,
          file_count: current.has_readme ? current.file_count : current.file_count + 1,
        }
      })
      setFiles((current) => ({
        ...current,
        'README.md': {
          size: new TextEncoder().encode(readme).length,
          updated_at: new Date().toISOString(),
          is_readme: true,
        },
      }))
      setSavedReadme(readme)
      setReadmeState('ready')
      setSaveState('saved')
      window.setTimeout(() => {
        setSaveState((current) => (current === 'saved' ? 'idle' : current))
      }, 1800)
    } catch (saveReadmeError) {
      setSaveState('error')
      setSaveError((saveReadmeError as Error).message || 'Failed to save README.md.')
    }
  }

  if (loading) {
    return <section className="projects-empty-state">Loading run…</section>
  }

  if (error || !project || !run) {
    return (
      <section className="project-detail-page">
        <div className="project-detail-shell">
          <div className="projects-status projects-status-error">{error || 'Run not found.'}</div>
          <Link to={workspace ? `/workspace/projects/${projectId}` : `/projects/${projectId}`} className="project-detail-backlink">
            Back to project
          </Link>
        </div>
      </section>
    )
  }

  return (
    <section className="run-detail-page">
      <div className="run-detail-shell">
        <Breadcrumbs crumbs={[
          { label: 'Projects', href: workspace ? '/workspace/projects' : '/projects' },
          { label: project.name, href: workspace ? `/workspace/projects/${project.id}` : `/projects/${project.id}` },
          { label: run.name },
        ]} />

        <header className="run-hero">
          <div className="run-hero-main">
            <p className="eyebrow">Run</p>
            <h1>{run.name}</h1>
          </div>
          <div className="run-hero-meta">
            <span>{run.id}</span>
            <span>created {formatDate(run.created_at)}</span>
            <span>updated {formatDate(run.updated_at)}</span>
            <span>{run.file_count} files</span>
          </div>
          <div className="run-hero-relations">
            <span>{parentRun ? `parent ${parentRun.name}` : 'top level'}</span>
            <span>{childRuns.length} children</span>
          </div>
        </header>

        <div className="run-detail-grid">
          <section className="run-detail-card run-editor-card">
            <MarkdownReadmeEditor
              key={`${run.id}:${readmeRevision}`}
              value={readme}
              editable={Boolean(isOwner)}
              placeholder="README.md will appear here once uploaded."
              onChange={setReadme}
            />

            {saveError ? <div className="projects-status projects-status-error">{saveError}</div> : null}

            <div className="project-readme-footer">
              {isOwner ? (
                <div className="project-readme-actions">
                  <Button
                    type="button"
                    variant="primary"
                    onClick={() => void handleSaveReadme()}
                    disabled={!readmeDirty || saveState === 'saving'}
                  >
                    {saveState === 'saving' ? 'Saving…' : 'Save'}
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    onClick={() => setReadme(savedReadme)}
                    disabled={!readmeDirty || saveState === 'saving'}
                  >
                    Revert
                  </Button>
                </div>
              ) : <div />}
              <div className="project-readme-status">
                {saveState === 'saving' ? <span>saving…</span> : null}
                {readmeDirty ? <span>unsaved changes</span> : null}
                {saveState === 'saved' ? <span>saved</span> : null}
              </div>
            </div>
          </section>

          <div className="run-detail-sidebar">
            <section className="run-detail-card">
              <FilesPanel
                entityName={run.name}
                files={files}
                fetchDownloadUrls={(paths, tokenGetter) => downloadRunFiles(run.id, paths, tokenGetter)}
              />
            </section>

            <RunLinksPanel
              title="Inputs"
              links={inputLinks}
              canAdd={Boolean(isOwner)}
              canRemove={Boolean(isOwner)}
              onAdd={() => setLinkingBucket('inputs')}
              onLinkClick={handleLinkClick}
              onRemoveLink={(link) => void handleRemoveLink(link)}
            />

            <RunLinksPanel
              title="Outputs"
              links={outputLinks}
              canAdd={Boolean(isOwner)}
              canRemove={Boolean(isOwner)}
              onAdd={() => setLinkingBucket('outputs')}
              onLinkClick={handleLinkClick}
              onRemoveLink={(link) => void handleRemoveLink(link)}
            />
          </div>
        </div>

        {linkingBucket ? (
          <ManifestLinkPickerModal
            manifests={manifests}
            scope={manifestPickerScope}
            onScopeChange={setManifestPickerScope}
            onSelect={(manifest) => void handleAddManifestLink(manifest)}
            onClose={() => setLinkingBucket(null)}
          />
        ) : null}

        {selectedManifestId ? (
          <ManifestViewerModal
            manifestId={selectedManifestId}
            onClose={() => setSelectedManifestId(null)}
          />
        ) : null}
      </div>
    </section>
  )
}
