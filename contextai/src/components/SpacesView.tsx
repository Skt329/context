import { useState, useRef, useCallback, useEffect } from 'react';
import { Plus, Trash2, Upload, FileText, RefreshCw, MessageSquare, ChevronDown, ChevronRight, Save, Type } from 'lucide-react';
import { useAppStore, type Space } from '../stores/appStore';
import { uploadFile, listFiles } from '../lib/api';

const SPACE_EMOJIS = ['📁', '💼', '🔬', '📚', '✍️', '💡', '🎯', '🏢', '🛠️', '🎨', '📊', '🌐'];

interface SpaceFile {
  name: string;
  size: number;
  modified: number;
}

export function SpacesView() {
  const spaces = useAppStore((s) => s.spaces);
  const activeSpaceId = useAppStore((s) => s.activeSpaceId);
  const setActiveSpace = useAppStore((s) => s.setActiveSpace);
  const addSpace = useAppStore((s) => s.addSpace);
  const deleteSpace = useAppStore((s) => s.deleteSpace);
  const setActiveTab = useAppStore((s) => s.setActiveTab);
  const updateSpaceTextContext = useAppStore((s) => s.updateSpaceTextContext);

  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState('');
  const [newIcon, setNewIcon] = useState('📁');
  const [newDesc, setNewDesc] = useState('');

  // File management state
  const [expandedSpace, setExpandedSpace] = useState<string | null>(null);
  const [spaceFiles, setSpaceFiles] = useState<Record<string, SpaceFile[]>>({});
  const [uploading, setUploading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Text context editing
  const [editingTextContext, setEditingTextContext] = useState<string | null>(null);
  const [textContextDraft, setTextContextDraft] = useState('');

  const handleCreate = () => {
    if (!newName.trim()) return;
    const space: Space = {
      id: crypto.randomUUID(),
      name: newName.trim(),
      icon: newIcon,
      description: newDesc.trim(),
      fileCount: 0,
      lastUsed: null,
      createdAt: new Date().toISOString(),
    };
    addSpace(space);
    setActiveSpace(space.id);
    setShowCreate(false);
    setNewName('');
    setNewDesc('');
    setNewIcon('📁');
  };

  const handleDelete = (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    if (spaces.length <= 1) return;
    deleteSpace(id);
    if (expandedSpace === id) setExpandedSpace(null);
  };

  const loadFiles = useCallback(async (spaceId: string) => {
    const result = await listFiles(spaceId);
    if (result) {
      setSpaceFiles((prev) => ({ ...prev, [spaceId]: result.files }));
    }
  }, []);

  const toggleExpand = (spaceId: string) => {
    if (expandedSpace === spaceId) {
      setExpandedSpace(null);
      setEditingTextContext(null);
    } else {
      setExpandedSpace(spaceId);
      setActiveSpace(spaceId);
      loadFiles(spaceId);
      setEditingTextContext(null);
    }
  };

  const handleFileUpload = async (spaceId: string, files: FileList | null) => {
    if (!files || files.length === 0) return;
    setUploading(true);
    setUploadStatus(null);

    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      setUploadStatus(`Uploading ${file.name}...`);
      const result = await uploadFile(spaceId, file);
      if (result) {
        const indexing = result.indexing;
        if (indexing?.status === 'indexed') {
          setUploadStatus(`✓ ${file.name} — ${indexing.chunks_created} chunks indexed`);
        }
      } else {
        setUploadStatus(`✗ Failed to upload ${file.name}`);
      }
    }

    await loadFiles(spaceId);
    setUploading(false);
    setTimeout(() => setUploadStatus(null), 4000);
  };

  const handleDrop = useCallback(
    (e: React.DragEvent, spaceId: string) => {
      e.preventDefault();
      e.stopPropagation();
      setDragOver(null);
      handleFileUpload(spaceId, e.dataTransfer.files);
    },
    [],
  );

  const handleDragOver = (e: React.DragEvent, spaceId: string) => {
    e.preventDefault();
    e.stopPropagation();
    setDragOver(spaceId);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(null);
  };

  const startEditingTextContext = (spaceId: string) => {
    const space = spaces.find((s) => s.id === spaceId);
    setEditingTextContext(spaceId);
    setTextContextDraft(space?.textContext || '');
  };

  const saveTextContext = (spaceId: string) => {
    updateSpaceTextContext(spaceId, textContextDraft);
    setEditingTextContext(null);
    // TODO: Sync to backend
  };

  const handleGoToChat = (e: React.MouseEvent, spaceId: string) => {
    e.stopPropagation();
    setActiveSpace(spaceId);
    setActiveTab('chat');
  };

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  return (
    <>
      <div className="spaces-view">
        <div className="spaces-header">
          <h2 className="spaces-header__title">Spaces</h2>
          <button className="btn-primary" onClick={() => setShowCreate(true)}>
            <Plus size={14} /> New Space
          </button>
        </div>

        {spaces.map((space) => (
          <div key={space.id}>
            {/* Space card — clicking expands, NOT navigates */}
            <div
              className={`space-card ${activeSpaceId === space.id ? 'space-card--active' : ''} ${expandedSpace === space.id ? 'space-card--expanded' : ''} ${dragOver === space.id ? 'space-card--dragover' : ''}`}
              onClick={() => toggleExpand(space.id)}
              onDrop={(e) => handleDrop(e, space.id)}
              onDragOver={(e) => handleDragOver(e, space.id)}
              onDragLeave={handleDragLeave}
            >
              <div className="space-card__icon">{space.icon}</div>
              <div className="space-card__info">
                <div className="space-card__name">{space.name}</div>
                <div className="space-card__meta">
                  {space.fileCount} files
                  {space.textContext ? ' · 📝 Context set' : ''}
                  {space.description ? ` · ${space.description}` : ''}
                </div>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                {activeSpaceId === space.id && (
                  <span className="space-card__badge">Active</span>
                )}
                {/* Go to Chat button */}
                <button
                  className="title-bar__btn"
                  onClick={(e) => handleGoToChat(e, space.id)}
                  title="Open Chat"
                >
                  <MessageSquare size={14} />
                </button>
                <button className="title-bar__btn" title={expandedSpace === space.id ? 'Collapse' : 'Expand'}>
                  {expandedSpace === space.id ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                </button>
                {spaces.length > 1 && (
                  <button
                    className="title-bar__btn"
                    onClick={(e) => handleDelete(e, space.id)}
                    title="Delete space"
                  >
                    <Trash2 size={14} />
                  </button>
                )}
              </div>
            </div>

            {/* Expanded management panel */}
            {expandedSpace === space.id && (
              <div className="space-files" onClick={(e) => e.stopPropagation()}>
                {/* ── Text Context Section ─────────────────────── */}
                <div className="space-section">
                  <div
                    className="space-section__header"
                    onClick={() => editingTextContext === space.id ? setEditingTextContext(null) : startEditingTextContext(space.id)}
                  >
                    <Type size={14} style={{ opacity: 0.6 }} />
                    <span className="space-section__label">Space Context</span>
                    <span style={{ fontSize: '10px', color: 'var(--text-muted)', marginLeft: 'auto' }}>
                      {space.textContext ? `${space.textContext.length} chars` : 'Not set'}
                    </span>
                  </div>

                  {editingTextContext === space.id ? (
                    <div className="space-context-edit">
                      <textarea
                        className="space-context-textarea"
                        placeholder="Add persistent text context for this space...&#10;&#10;Example: &quot;I am a senior developer applying to FAANG companies. My stack is Python, Go, and Kubernetes. Prefer concise, technical tone.&quot;"
                        value={textContextDraft}
                        onChange={(e) => setTextContextDraft(e.target.value)}
                        rows={4}
                        autoFocus
                      />
                      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '6px' }}>
                        <button className="btn-ghost btn-sm" onClick={() => setEditingTextContext(null)}>Cancel</button>
                        <button className="btn-primary btn-sm" onClick={() => saveTextContext(space.id)}>
                          <Save size={12} /> Save
                        </button>
                      </div>
                    </div>
                  ) : space.textContext ? (
                    <div
                      className="space-context-preview"
                      onClick={() => startEditingTextContext(space.id)}
                    >
                      {space.textContext.slice(0, 150)}{space.textContext.length > 150 ? '...' : ''}
                    </div>
                  ) : null}
                </div>

                {/* ── File Upload Section ──────────────────────── */}
                <div className="space-section">
                  <div className="space-section__header">
                    <FileText size={14} style={{ opacity: 0.6 }} />
                    <span className="space-section__label">Documents</span>
                    <span style={{ fontSize: '10px', color: 'var(--text-muted)', marginLeft: 'auto' }}>
                      {(spaceFiles[space.id] || []).length} files
                    </span>
                  </div>

                  <div
                    className={`upload-zone ${dragOver === space.id ? 'upload-zone--active' : ''}`}
                    onClick={() => fileInputRef.current?.click()}
                  >
                    <Upload size={18} style={{ opacity: 0.6 }} />
                    <span style={{ fontSize: '12px', opacity: 0.7 }}>
                      Drop files or click to upload
                    </span>
                    <span style={{ fontSize: '10px', opacity: 0.4 }}>
                      PDF, DOCX, TXT, MD, CSV, PPTX, Code
                    </span>
                    <input
                      ref={fileInputRef}
                      type="file"
                      multiple
                      accept=".pdf,.docx,.txt,.md,.csv,.pptx,.py,.js,.ts,.json,.yaml,.yml,.html,.xml"
                      style={{ display: 'none' }}
                      onChange={(e) => handleFileUpload(space.id, e.target.files)}
                    />
                  </div>

                  {uploadStatus && (
                    <div className="upload-status">
                      {uploading && <RefreshCw size={12} className="spin" />}
                      <span>{uploadStatus}</span>
                    </div>
                  )}

                  {(spaceFiles[space.id] || []).length > 0 ? (
                    <div className="file-list">
                      {spaceFiles[space.id].map((file) => (
                        <div key={file.name} className="file-item">
                          <FileText size={14} style={{ opacity: 0.5, flexShrink: 0 }} />
                          <span className="file-item__name">{file.name}</span>
                          <span className="file-item__size">{formatFileSize(file.size)}</span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div style={{ fontSize: '12px', opacity: 0.4, textAlign: 'center', padding: '6px' }}>
                      No files uploaded yet
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        ))}
      </div>

      {showCreate && (
        <div className="modal-overlay" onClick={() => setShowCreate(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h3 className="modal__title">Create Space</h3>
            
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <div>
                <label className="settings-section__title" style={{ marginBottom: '6px', display: 'block' }}>Icon</label>
                <div className="emoji-grid">
                  {SPACE_EMOJIS.map((emoji) => (
                    <button
                      key={emoji}
                      className={`emoji-btn ${newIcon === emoji ? 'emoji-btn--selected' : ''}`}
                      onClick={() => setNewIcon(emoji)}
                    >{emoji}</button>
                  ))}
                </div>
              </div>
              <div>
                <label className="settings-section__title" style={{ marginBottom: '6px', display: 'block' }}>Name</label>
                <input
                  className="input-field"
                  placeholder="e.g., Job Applications"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  autoFocus
                  onKeyDown={(e) => e.key === 'Enter' && handleCreate()}
                />
              </div>
              <div>
                <label className="settings-section__title" style={{ marginBottom: '6px', display: 'block' }}>Description</label>
                <input
                  className="input-field"
                  placeholder="What is this space for?"
                  value={newDesc}
                  onChange={(e) => setNewDesc(e.target.value)}
                />
              </div>
            </div>

            <div className="modal__actions">
              <button className="btn-ghost" onClick={() => setShowCreate(false)}>Cancel</button>
              <button className="btn-primary" onClick={handleCreate} disabled={!newName.trim()}>Create Space</button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
