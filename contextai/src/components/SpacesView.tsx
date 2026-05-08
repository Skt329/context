import { useState } from 'react';
import { Plus, Trash2 } from 'lucide-react';
import { useAppStore, type Space } from '../stores/appStore';

const SPACE_EMOJIS = ['📁', '💼', '🔬', '📚', '✍️', '💡', '🎯', '🏢', '🛠️', '🎨', '📊', '🌐'];

export function SpacesView() {
  const spaces = useAppStore((s) => s.spaces);
  const activeSpaceId = useAppStore((s) => s.activeSpaceId);
  const setActiveSpace = useAppStore((s) => s.setActiveSpace);
  const addSpace = useAppStore((s) => s.addSpace);
  const deleteSpace = useAppStore((s) => s.deleteSpace);
  const setActiveTab = useAppStore((s) => s.setActiveTab);

  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState('');
  const [newIcon, setNewIcon] = useState('📁');
  const [newDesc, setNewDesc] = useState('');

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
    setActiveTab('chat');
  };

  const handleDelete = (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    if (spaces.length <= 1) return;
    deleteSpace(id);
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
          <div
            key={space.id}
            className={`space-card ${activeSpaceId === space.id ? 'space-card--active' : ''}`}
            onClick={() => {
              setActiveSpace(space.id);
              setActiveTab('chat');
            }}
          >
            <div className="space-card__icon">{space.icon}</div>
            <div className="space-card__info">
              <div className="space-card__name">{space.name}</div>
              <div className="space-card__meta">
                {space.fileCount} files · {space.description || 'No description'}
              </div>
            </div>
            {activeSpaceId === space.id && (
              <span className="space-card__badge">Active</span>
            )}
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
        ))}
      </div>

      {showCreate && (
        <div className="modal-overlay" onClick={() => setShowCreate(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h3 className="modal__title">Create Space</h3>
            
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <div>
                <label className="settings-section__title" style={{ marginBottom: '6px', display: 'block' }}>
                  Icon
                </label>
                <div className="emoji-grid">
                  {SPACE_EMOJIS.map((emoji) => (
                    <button
                      key={emoji}
                      className={`emoji-btn ${newIcon === emoji ? 'emoji-btn--selected' : ''}`}
                      onClick={() => setNewIcon(emoji)}
                    >
                      {emoji}
                    </button>
                  ))}
                </div>
              </div>
              
              <div>
                <label className="settings-section__title" style={{ marginBottom: '6px', display: 'block' }}>
                  Name
                </label>
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
                <label className="settings-section__title" style={{ marginBottom: '6px', display: 'block' }}>
                  Description
                </label>
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
              <button className="btn-primary" onClick={handleCreate} disabled={!newName.trim()}>
                Create Space
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
