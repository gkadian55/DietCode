import React, { useEffect, useState } from 'react';
import { Clock3, FolderOpen, History, Save, X } from 'lucide-react';
import { useDagStore } from '../../store/useDagStore';

const formatDate = (value) => new Date(value).toLocaleString();

export const ProjectsModal = () => {
  const {
    isProjectsModalOpen,
    setProjectsModalOpen,
    currentProjectId,
    savedProjects,
    refreshSavedProjects,
    saveCurrentProject,
    createProject,
    loadProject,
    loadProjectHistory,
    restoreDagSnapshot,
    projectPersistenceStatus,
    projectPersistenceError
  } = useDagStore();
  const [projectName, setProjectName] = useState('');
  const [historyProjectId, setHistoryProjectId] = useState(null);
  const [historyItems, setHistoryItems] = useState([]);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!isProjectsModalOpen) return;
    refreshSavedProjects();
    const currentProject = savedProjects.find((project) => project.id === currentProjectId);
    setProjectName(currentProject?.name || '');
    setHistoryProjectId(null);
    setHistoryItems([]);
  }, [isProjectsModalOpen]);

  if (!isProjectsModalOpen) return null;

  const handleSaveCurrent = async () => {
    setBusy(true);
    await saveCurrentProject(projectName);
    setBusy(false);
  };

  const handleSaveAsNew = async () => {
    if (!projectName.trim()) return;
    setBusy(true);
    const projectId = await createProject(projectName.trim());
    if (projectId) setProjectName('');
    setBusy(false);
  };

  const handleOpenProject = async (projectId) => {
    setBusy(true);
    const opened = await loadProject(projectId);
    setBusy(false);
    if (opened) setProjectsModalOpen(false);
  };

  const handleToggleHistory = async (projectId) => {
    if (historyProjectId === projectId) {
      setHistoryProjectId(null);
      setHistoryItems([]);
      return;
    }
    setHistoryProjectId(projectId);
    setHistoryItems(await loadProjectHistory(projectId));
  };

  const handleRestore = async (snapshotId) => {
    setBusy(true);
    const restored = await restoreDagSnapshot(snapshotId);
    setBusy(false);
    if (restored) setProjectsModalOpen(false);
  };

  return (
    <div className="modal-overlay" role="presentation" onClick={() => setProjectsModalOpen(false)}>
      <div
        className="modal-content projects-modal-content"
        role="dialog"
        aria-modal="true"
        aria-labelledby="projects-modal-title"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="modal-header">
          <div className="modal-title" id="projects-modal-title">
            <FolderOpen size={16} />
            Local projects
          </div>
          <button className="window-btn" onClick={() => setProjectsModalOpen(false)} title="Close">
            <X size={16} />
          </button>
        </div>

        <div className="projects-modal-body">
          <p className="projects-storage-note">
            Projects and run snapshots are stored locally in this app on this device.
          </p>

          <div className="projects-save-row">
            <input
              className="form-input"
              value={projectName}
              onChange={(event) => setProjectName(event.target.value)}
              placeholder="Project name"
              maxLength={100}
              aria-label="Project name"
            />
            <button type="button" className="btn btn-primary btn-sm" onClick={handleSaveCurrent} disabled={busy}>
              <Save size={13} />
              Save current
            </button>
            <button type="button" className="btn btn-secondary btn-sm" onClick={handleSaveAsNew} disabled={busy || !projectName.trim()}>
              Save as new
            </button>
          </div>

          <div className="projects-save-status" role="status">
            {projectPersistenceError || (
              projectPersistenceStatus === 'saving'
                ? 'Saving locally...'
                : projectPersistenceStatus === 'saved'
                  ? 'Saved on this device'
                  : ''
            )}
          </div>

          <div className="projects-list">
            {savedProjects.length === 0 ? (
              <div className="projects-empty-state">No saved projects yet.</div>
            ) : savedProjects.map((project) => (
              <div className="project-list-item" key={project.id}>
                <div className="project-list-main">
                  <div className="project-list-title">
                    {project.name}
                    {project.id === currentProjectId && <span className="project-current-badge">CURRENT</span>}
                  </div>
                  <div className="project-list-meta">
                    <Clock3 size={11} />
                    Updated {formatDate(project.updatedAt)}
                    <span>{project.nodes?.length || 0} tasks</span>
                  </div>
                </div>
                <div className="project-list-actions">
                  <button type="button" className="btn btn-secondary btn-sm" onClick={() => handleOpenProject(project.id)} disabled={busy}>
                    Open
                  </button>
                  <button
                    type="button"
                    className="window-btn"
                    onClick={() => handleToggleHistory(project.id)}
                    title="View saved DAG snapshots"
                    aria-label={`View history for ${project.name}`}
                  >
                    <History size={14} />
                  </button>
                </div>
                {historyProjectId === project.id && (
                  <div className="project-history-list">
                    {historyItems.length === 0 ? (
                      <span>No execution snapshots yet.</span>
                    ) : historyItems.map((snapshot) => (
                      <div className="project-history-item" key={snapshot.id}>
                        <div>
                          <span>{formatDate(snapshot.createdAt)}</span>
                          <small>
                            {snapshot.taskIds?.length || snapshot.nodes?.length || 0} tasks
                            {snapshot.run ? ` · ${snapshot.run.status}` : ''}
                          </small>
                        </div>
                        <button
                          type="button"
                          className="btn btn-secondary btn-sm"
                          onClick={() => handleRestore(snapshot.id)}
                          disabled={busy}
                        >
                          Restore DAG
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
