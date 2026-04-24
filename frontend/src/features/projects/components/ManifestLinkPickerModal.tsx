import { Modal } from '../../../components/ui/Modal'
import type { ManifestSummary } from '../types'

export function ManifestLinkPickerModal({
  manifests,
  onClose,
}: {
  manifests: ManifestSummary[]
  scope: 'all' | 'shared'
  onScopeChange: (scope: 'all' | 'shared') => void
  onSelect: (manifest: ManifestSummary) => void
  onClose: () => void
}) {
  return (
    <Modal title="Link Manifest" onClose={onClose}>
      {manifests.length === 0 ? (
        <p className="project-detail-empty">Manifest linking will be enabled once the local manifest API is wired.</p>
      ) : null}
    </Modal>
  )
}
