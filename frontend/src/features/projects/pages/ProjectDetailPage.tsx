import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { Button } from '../../../components/ui/Button'
import { Breadcrumbs } from '../../../components/ui/Breadcrumbs'
import { useAuth, useUser } from '../../auth/localAuth'
import { FilesPanel } from '../components/FilesPanel'
import { MarkdownReadmeEditor } from '../components/MarkdownReadmeEditor'
import { RunsPanel } from '../components/RunsPanel'
import { downloadProjectFiles, getProject, listProjectFiles, listRuns, syncProject } from '../api'
import { saveProjectReadme } from '../readmeSync'
import type { FileListEntry, ProjectDetail, ProjectSyncResult, RunSummary } from '../types'

function formatDate(value: string) {
  return new Date(value).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}

export function ProjectDetailPage({ workspace }: { workspace: boolean }) {
  const { projectId } = useParams()
  const { getToken } = useAuth()
  const { user } = useUser()
  const [project, setProject] = useState<ProjectDetail | null>(null)
  const [files, setFiles] = useState<Record<string, FileListEntry>>({})
  const [runs, setRuns] = useState<RunSummary[]>([])
  const [readme, setReadme] = useState('')
  const [savedReadme, setSavedReadme] = useState('')
  const [readmeState, setReadmeState] = useState<'idle' | 'loading' | 'ready' | 'missing' | 'error'>('idle')
  const [saveState, setSaveState] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle')
  const [saveError, setSaveError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [copiedProjectId, setCopiedProjectId] = useState(false)
  const [syncing, setSyncing] = useState(false)
  const [syncError, setSyncError] = useState<string | null>(null)
  const [syncResult, setSyncResult] = useState<ProjectSyncResult | null>(null)

  const loadProjectPage = useCallback(async () => {
    if (!projectId) {
      setError('Missing project id.')
      setLoading(false)
      return
    }

    setLoading(true)
    setError(null)

    try {
      const currentProjectId = projectId
      const [projectResponse, filesResponse, runsResponse] = await Promise.all([
        getProject(currentProjectId, getToken),
        listProjectFiles(currentProjectId, getToken),
        listRuns(currentProjectId, getToken),
      ])

      setProject(projectResponse)
      setFiles(filesResponse.files)
      setRuns(runsResponse.runs)

      if (projectResponse.has_readme) {
        setReadmeState('loading')
        const download = await downloadProjectFiles(currentProjectId, ['README.md'], getToken)
        const url = download.urls['README.md']

        if (!url) {
          setReadme('')
          setSavedReadme('')
          setReadmeState('missing')
          return
        }

        const response = await fetch(url)
        const text = await response.text()

        setReadme(text)
        setSavedReadme(text)
        setReadmeState('ready')
      } else {
        setReadme('')
        setSavedReadme('')
        setReadmeState('missing')
      }

      setSaveState('idle')
      setSaveError(null)
    } catch (loadError) {
      setError((loadError as Error).message || 'Failed to load project.')
      setReadmeState('error')
    } finally {
      setLoading(false)
    }
  }, [projectId, getToken])

  useEffect(() => {
    void loadProjectPage()
  }, [loadProjectPage])

  const isOwner = project?.owner_user_id === user?.id
  const readmeDirty = useMemo(() => readme !== savedReadme, [readme, savedReadme])
  const readmeStatusLabel = useMemo(() => {
    if (saveState === 'saving') return 'saving…'
    if (readmeDirty) return 'unsaved changes'
    return ''
  }, [saveState, readmeDirty])

  async function handleCopyProjectId() {
    if (!project) return
    try {
      await navigator.clipboard.writeText(project.id)
      setCopiedProjectId(true)
      window.setTimeout(() => setCopiedProjectId(false), 1200)
    } catch {
      setCopiedProjectId(false)
    }
  }

  async function handleSaveReadme() {
    if (!project || !isOwner || !readmeDirty) return
    setSaveState('saving')
    setSaveError(null)
    try {
      await saveProjectReadme(project.id, readme, getToken)
      setProject((current) => {
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

  async function handleSyncProject() {
    if (!project || syncing) return
    setSyncing(true)
    setSyncError(null)
    try {
      const result = await syncProject(project.id, getToken)
      setSyncResult(result)
    } catch (syncProjectError) {
      setSyncError((syncProjectError as Error).message || 'Failed to sync project.')
      setSyncResult(null)
    } finally {
      setSyncing(false)
    }
  }

  if (loading) {
    return <section className="projects-empty-state">Loading project…</section>
  }

  if (error || !project) {
    return (
      <section className="project-detail-page">
        <div className="project-detail-shell">
          <div className="projects-status projects-status-error">{error || 'Project not found.'}</div>
          <Link to={workspace ? '/workspace/projects' : '/projects'} className="project-detail-backlink">
            Back to projects
          </Link>
        </div>
      </section>
    )
  }

  return (
    <section className="project-detail-page">
      <div className="project-detail-shell">
        <Breadcrumbs crumbs={[
          { label: 'Projects', href: workspace ? '/workspace/projects' : '/projects' },
          { label: project.name },
        ]} />

        <header className="project-hero">
          <p className="project-hero-copy">{project.description || 'No short project description yet.'}</p>

          <div className="project-hero-meta">
            <div className="project-hero-meta-left">
              {workspace ? null : <span>@{project.owner_username}</span>}
              <span className="project-id-meta">
                <span>{project.id}</span>
                <button type="button" className="project-meta-copy" onClick={handleCopyProjectId} aria-label="Copy project id">
                  <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
                    <rect x="5" y="5" width="8" height="8" />
                    <path d="M3 11V3h8" />
                  </svg>
                </button>
                {copiedProjectId ? <span className="project-meta-copy-state">copied</span> : null}
              </span>
            </div>
            <div className="project-hero-meta-right">
              <span>{project.is_public ? 'Public' : 'Private'}</span>
              <span>{runs.length} runs</span>
              <span>{project.file_count} files</span>
              <span>updated {formatDate(project.updated_at)}</span>
            </div>
          </div>

          <div className="project-hero-tags">
            {project.tags.length > 0 ? (
              project.tags.map((tag) => <span key={tag} className="project-tag">{tag}</span>)
            ) : (
              <span className="project-tag project-tag-muted">untagged</span>
            )}
          </div>

          <div className="project-sync-row">
            <Button type="button" variant="secondary" onClick={() => void handleSyncProject()} disabled={syncing}>
              {syncing ? (
                <span className="button-spinner-wrap">
                  <span className="button-spinner" aria-hidden="true" />
                  <span>Syncing Project…</span>
                </span>
              ) : 'Sync Project'}
            </Button>
            {syncError ? <div className="projects-status projects-status-error">{syncError}</div> : null}
            {syncResult ? (
              <div className="projects-status">
                Synced to {syncResult.cloud_api_base}. Created {syncResult.created.runs} runs, {syncResult.created.manifests} manifests, {syncResult.created.episodes} episodes. Uploaded {syncResult.uploaded.project_files + syncResult.uploaded.run_files + syncResult.uploaded.episode_files} files.
              </div>
            ) : null}
          </div>
        </header>

        <RunsPanel projectId={project.id} runs={runs} isOwner={isOwner} onRunsChanged={loadProjectPage} workspace={workspace} />

        <FilesPanel
          entityName={project.name}
          files={files}
          fetchDownloadUrls={(paths, getToken) => downloadProjectFiles(project.id, paths, getToken)}
        />

        <section className="project-readme-panel">
          <MarkdownReadmeEditor
            value={readme}
            editable={Boolean(isOwner)}
            placeholder="README.md will appear here once uploaded."
            onChange={setReadme}
          />

          {saveError ? <div className="projects-status projects-status-error">{saveError}</div> : null}

          <div className="project-readme-footer">
            {isOwner ? (
              <div className="project-readme-actions">
                <Button type="button" variant="primary" onClick={() => void handleSaveReadme()} disabled={!readmeDirty || saveState === 'saving'}>
                  {saveState === 'saving' ? 'Saving…' : 'Save'}
                </Button>
                <Button type="button" variant="ghost" onClick={() => setReadme(savedReadme)} disabled={!readmeDirty || saveState === 'saving'}>
                  Revert
                </Button>
              </div>
            ) : <div />}
            <div className="project-readme-status">
              {readmeStatusLabel ? <span>{readmeStatusLabel}</span> : null}
              {saveState === 'saved' ? <span>saved</span> : null}
            </div>
          </div>
        </section>
      </div>
    </section>
  )
}
