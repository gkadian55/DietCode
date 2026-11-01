import React, { useState } from 'react';
import { useDagStore, triggerBase64Download } from '../../store/useDagStore';
import { downloadZipClient } from '../../utils/zipBuilder';
import { 
  X, 
  Download, 
  FolderOpen, 
  FileCode, 
  FileText, 
  CheckCircle2, 
  Archive, 
  Sparkles, 
  ExternalLink,
  Layers
} from 'lucide-react';

export const ExportModal = () => {
  const { 
    isExportModalOpen, 
    setExportModalOpen, 
    exportResult, 
    goalInput,
    nodes
  } = useDagStore();

  const [downloaded, setDownloaded] = useState(false);

  if (!isExportModalOpen || !exportResult) return null;

  const files = exportResult.files || [];
  const executableFiles = files.filter(f => f.isExecutable);
  const isDesktop = Boolean(window.electronAPI?.openPath);

  const handleDownloadZip = () => {
    if (exportResult.zipBase64) {
      triggerBase64Download(
        exportResult.zipBase64, 
        `${exportResult.folderName || 'dietcode_codebase'}.zip`
      );
      setDownloaded(true);
      setTimeout(() => setDownloaded(false), 2500);
    } else {
      // In offline / client-fallback mode: build and download the real ZIP archive on the client!
      const filesToZip = (exportResult.files || []).map(f => ({
        name: f.path,
        content: f.content || `# ${f.task || f.path}\n# Category: ${f.category}\n`
      }));

      // Include dietcode-manifest.json
      const manifestJson = JSON.stringify(exportResult, null, 2);
      filesToZip.push({ name: 'dietcode-manifest.json', content: manifestJson });

      downloadZipClient(filesToZip, `${exportResult.folderName || 'dietcode_codebase'}.zip`);
      setDownloaded(true);
      setTimeout(() => setDownloaded(false), 2500);
    }
  };

  const handleOpenFolder = async () => {
    if (window.electronAPI?.openPath && exportResult.exportDirectory) {
      await window.electronAPI.openPath(exportResult.exportDirectory);
    }
  };

  return (
    <div className="modal-overlay" onClick={() => setExportModalOpen(false)}>
      <div className="modal-content export-modal-content" onClick={(e) => e.stopPropagation()}>
        {/* Modal Header */}
        <div className="modal-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
            <div className="export-icon-badge">
              <Archive size={17} color="#6366f1" />
            </div>
            <div>
              <div className="modal-title" style={{ fontSize: 16 }}>Export Project Codebase</div>
              <div style={{ fontSize: 11, color: '#94a3b8', marginTop: 1 }}>
                Extracted deliverables, architecture specs, and telemetry manifest
              </div>
            </div>
          </div>
          <button 
            className="window-btn" 
            onClick={() => setExportModalOpen(false)}
            title="Close"
          >
            <X size={15} />
          </button>
        </div>

        {/* Project Overview Card */}
        <div className="export-summary-card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <div style={{ flex: 1, paddingRight: 12 }}>
              <div style={{ fontSize: 10, textTransform: 'uppercase', color: '#94a3b8', fontWeight: 600 }}>
                Target Project Goal
              </div>
              <div style={{ fontSize: 13, fontWeight: 700, color: '#f1f5f9', marginTop: 3 }}>
                {goalInput}
              </div>
            </div>
            <div className="export-badge-status">
              <CheckCircle2 size={13} color="#10b981" />
              <span>{executableFiles.length} Code Files Extracted</span>
            </div>
          </div>

          <div className="export-meta-row">
            <div>
              <span className="export-meta-label">TOTAL DELIVERABLES:</span>{' '}
              <span className="export-meta-val">{files.length} Files</span>
            </div>
            <div>
              <span className="export-meta-label">TASKS BENCHMARKED:</span>{' '}
              <span className="export-meta-val">{nodes.length} Nodes</span>
            </div>
            <div>
              <span className="export-meta-label">FORMAT:</span>{' '}
              <span className="export-meta-val">Source Tree + ZIP</span>
            </div>
          </div>
        </div>

        {/* File Tree List */}
        <div className="export-file-section">
          <div className="export-section-label">
            <span>Generated File Hierarchy</span>
            <span style={{ fontSize: 10.5, color: '#64748b' }}>Ready for build & deploy</span>
          </div>

          <div className="export-file-list">
            {files.map((file, idx) => {
              const isDoc = file.path.endsWith('.md') || file.path.endsWith('.json');
              return (
                <div key={idx} className="export-file-row">
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    {isDoc ? (
                      <FileText size={14} color="#94a3b8" />
                    ) : (
                      <FileCode size={14} color="#10b981" />
                    )}
                    <span className="export-file-path">{file.path}</span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span className="export-file-cat">{file.category}</span>
                    <span className="export-file-size">{(file.size || 0).toLocaleString()} B</span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Local Directory Notice (If Available) */}
        {exportResult.exportDirectory && (
          <div className="export-directory-callout">
            <FolderOpen size={14} color="#6366f1" />
            <div style={{ flex: 1, overflow: 'hidden' }}>
              <div style={{ fontSize: 10, color: '#94a3b8', textTransform: 'uppercase' }}>
                Local Folder Path
              </div>
              <div className="export-path-text" title={exportResult.exportDirectory}>
                {exportResult.exportDirectory}
              </div>
            </div>
          </div>
        )}

        {/* Modal Footer Controls */}
        <div className="modal-footer" style={{ marginTop: 16 }}>
          {isDesktop && exportResult.exportDirectory && (
            <button 
              type="button" 
              className="btn btn-secondary"
              onClick={handleOpenFolder}
              title="Open folder directly in Windows Explorer"
            >
              <FolderOpen size={13} />
              Open Folder
            </button>
          )}

          <button 
            type="button" 
            className="btn btn-primary"
            onClick={handleDownloadZip}
          >
            {downloaded ? (
              <>
                <CheckCircle2 size={13} color="#fff" />
                <span>ZIP Downloaded!</span>
              </>
            ) : (
              <>
                <Download size={13} />
                <span>Download ZIP ({files.length} Files)</span>
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
};
