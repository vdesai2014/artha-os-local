import { Modal } from '../../../components/ui/Modal'

export function ManifestViewerModal({ manifestId, onClose }: { manifestId: string; onClose: () => void }) {
  return (
    <Modal title="Dataset Viewer" onClose={onClose}>
      <p className="project-detail-empty">Manifest viewer for `{manifestId}` will be enabled once local manifest/video/parquet APIs are in place.</p>
    </Modal>
  )
}
