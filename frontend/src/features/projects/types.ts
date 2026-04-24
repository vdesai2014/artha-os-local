export type ProjectScope = 'public' | 'mine'
export type ProjectOrder = 'newest' | 'oldest'

export interface FileListEntry {
  size: number
  updated_at: string
  is_readme?: boolean
}

export interface ProjectSummary {
  id: string
  owner_user_id: string
  owner_username: string
  name: string
  description: string | null
  tags: string[]
  is_public: boolean
  created_at: string
  updated_at: string
}

export interface ProjectDetail extends ProjectSummary {
  has_readme: boolean
  file_count: number
}

export interface RunSummary {
  id: string
  project_id: string
  parent_id: string | null
  name: string
  created_at: string
  updated_at: string
}

export interface RunLink {
  type: string
  target_type: string
  target_id: string
  path?: string | null
  label?: string | null
}

export interface RunDetail extends RunSummary {
  links: RunLink[]
  has_readme: boolean
  file_count: number
}

export interface RunListResponse {
  runs: RunSummary[]
  next_cursor: string | null
}

export interface DownloadFilesResponse {
  urls: Record<string, string>
}

export interface FileListResponse {
  files: Record<string, FileListEntry>
}

export interface ProjectListResponse {
  projects: ProjectSummary[]
  next_cursor: string | null
  total_count: number
}

export interface ProjectSyncResult {
  project_id: string
  cloud_api_base: string
  created: {
    projects: number
    runs: number
    manifests: number
    episodes: number
  }
  patched: {
    projects: number
    runs: number
    manifests: number
    run_links: number
  }
  uploaded: {
    project_files: number
    run_files: number
    episode_files: number
  }
  warnings: string[]
}

export interface ProjectMutationInput {
  name: string
  description?: string | null
  tags?: string[]
  is_public?: boolean
}

export interface RunMutationInput {
  name: string
  parent_id?: string | null
}

export interface RunPatchInput {
  name?: string
  parent_id?: string | null
  links?: RunLink[]
}

export interface ManifestSummary {
  id: string
  owner_user_id: string
  owner_username: string
  name: string
  description: string | null
  type: string
  tags: string[]
  is_public: boolean
  fps: number | null
  episode_count: number
  created_at: string
  updated_at: string
}

export interface ManifestListResponse {
  manifests: ManifestSummary[]
  next_cursor: string | null
  total_count: number
}
