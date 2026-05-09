import { useState, useEffect } from 'react';
import { MessageSquare, Trash2, Clock, Search, Download, FileJson, X } from 'lucide-react';
import { useAppStore } from '../stores/appStore';
import { searchConversations, exportConversation, type SearchResult } from '../lib/api';
import { toast } from './Toast';

export function HistoryView() {
  const conversations = useAppStore((s) => s.conversations);
  const spaces = useAppStore((s) => s.spaces);
  const activeConversationId = useAppStore((s) => s.activeConversationId);
  const loadConversation = useAppStore((s) => s.loadConversation);
  const deleteConversation = useAppStore((s) => s.deleteConversation);
  const backendReady = useAppStore((s) => s.backendReady);

  // Search state
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [isSearching, setIsSearching] = useState(false);

  // Debounced FTS search
  useEffect(() => {
    if (searchQuery.length < 2 || !backendReady) {
      setSearchResults([]);
      return;
    }
    setIsSearching(true);
    const timer = setTimeout(async () => {
      const results = await searchConversations(searchQuery);
      setSearchResults(results);
      setIsSearching(false);
    }, 300);
    return () => {
      clearTimeout(timer);
      setIsSearching(false);
    };
  }, [searchQuery, backendReady]);

  // Only show conversations with at least 1 message, sorted newest first
  const filledConversations = conversations
    .filter((c) => c.messages.length > 0)
    .sort((a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime());

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHrs = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHrs < 24) return `${diffHrs}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    return date.toLocaleDateString();
  };

  const handleExport = (e: React.MouseEvent, convoId: string, format: 'markdown' | 'json') => {
    e.stopPropagation();
    exportConversation(convoId, format);
    toast.success(`Exported as ${format === 'json' ? 'JSON' : 'Markdown'}`);
  };

  // Determine which list to render
  const isSearchActive = searchQuery.length >= 2;

  const renderConversationItem = (
    convo: { id: string; spaceId?: string; title: string; updatedAt?: string },
    preview?: string | null,
    messageCount?: number,
  ) => {
    const space = spaces.find((s) => s.id === (convo.spaceId || ''));
    const isActive = convo.id === activeConversationId;

    return (
      <div
        key={convo.id}
        className="history-item"
        role="listitem"
        style={{
          cursor: 'pointer',
          borderLeft: isActive ? '2px solid var(--accent)' : '2px solid transparent',
          background: isActive ? 'var(--accent-subtle)' : undefined,
        }}
        onClick={() => loadConversation(convo.id)}
        onKeyDown={(e) => { if (e.key === 'Enter') loadConversation(convo.id); }}
        tabIndex={0}
        aria-label={`Open conversation: ${convo.title}`}
      >
        <div style={{ fontSize: '18px', flexShrink: 0 }}>{space?.icon || '💬'}</div>
        <div className="history-item__content" style={{ flex: 1, minWidth: 0 }}>
          <div className="history-item__title">{convo.title}</div>
          {preview && (
            <div
              style={{
                fontSize: '11px', color: 'var(--text-muted)',
                overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
              }}
              dangerouslySetInnerHTML={
                preview.includes('<mark>') ? { __html: preview } : undefined
              }
            >
              {preview.includes('<mark>') ? undefined : preview}
            </div>
          )}
          <div className="history-item__time">
            <Clock size={10} style={{ marginRight: '3px' }} />
            {space?.name || 'Unknown'} · {convo.updatedAt ? formatDate(convo.updatedAt) : ''}
            {messageCount !== undefined ? ` · ${messageCount} msgs` : ''}
          </div>
        </div>
        <div style={{ display: 'flex', gap: '2px', flexShrink: 0 }}>
          <button
            className="title-bar__btn"
            onClick={(e) => handleExport(e, convo.id, 'markdown')}
            title="Export as Markdown"
            style={{ opacity: 0.4 }}
            aria-label="Export as Markdown"
          >
            <Download size={12} />
          </button>
          <button
            className="title-bar__btn"
            onClick={(e) => handleExport(e, convo.id, 'json')}
            title="Export as JSON"
            style={{ opacity: 0.4 }}
            aria-label="Export as JSON"
          >
            <FileJson size={12} />
          </button>
          <button
            className="title-bar__btn"
            onClick={(e) => {
              e.stopPropagation();
              deleteConversation(convo.id);
            }}
            title="Delete conversation"
            style={{ opacity: 0.4 }}
            aria-label="Delete conversation"
          >
            <Trash2 size={12} />
          </button>
        </div>
      </div>
    );
  };

  return (
    <div className="history-view" role="region" aria-label="Conversation history">
      <h2 className="spaces-header__title" style={{ marginBottom: '4px' }}>History</h2>

      {/* Search bar */}
      <div style={{ position: 'relative', marginBottom: '10px' }}>
        <div style={{
          display: 'flex', alignItems: 'center', gap: '6px',
          background: 'var(--surface-hover)', borderRadius: 'var(--radius-sm)',
          padding: '5px 8px', border: '1px solid var(--border)',
        }}>
          <Search size={13} style={{ color: 'var(--text-muted)', flexShrink: 0 }} />
          <input
            type="search"
            placeholder="Search conversations..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            aria-label="Search conversations"
            style={{
              background: 'none', border: 'none', outline: 'none',
              color: 'var(--text)', fontSize: '12px', width: '100%',
            }}
          />
          {searchQuery && (
            <button
              className="title-bar__btn"
              onClick={() => setSearchQuery('')}
              title="Clear search"
              style={{ flexShrink: 0 }}
              aria-label="Clear search"
            >
              <X size={12} />
            </button>
          )}
        </div>
      </div>

      {/* Results count */}
      <p style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '8px' }}>
        {isSearchActive
          ? isSearching
            ? 'Searching...'
            : `${searchResults.length} result${searchResults.length !== 1 ? 's' : ''} for "${searchQuery}"`
          : `${filledConversations.length} conversation${filledConversations.length !== 1 ? 's' : ''}`
        }
      </p>

      {/* Conversation list */}
      <div role="list" aria-label="Conversations">
        {isSearchActive ? (
          searchResults.length > 0 ? (
            searchResults.map((r) =>
              renderConversationItem(
                { id: r.id, spaceId: r.spaceId, title: r.title, updatedAt: r.updatedAt },
                r.matchPreview,
              ),
            )
          ) : !isSearching ? (
            <div className="chat-empty" style={{ paddingTop: '40px' }}>
              <div className="chat-empty__icon"><Search size={24} /></div>
              <div className="chat-empty__title">No results</div>
              <div className="chat-empty__subtitle">
                Try different search terms or check your spelling.
              </div>
            </div>
          ) : null
        ) : filledConversations.length === 0 ? (
          <div className="chat-empty" style={{ paddingTop: '40px' }}>
            <div className="chat-empty__icon"><MessageSquare size={24} /></div>
            <div className="chat-empty__title">No conversations yet</div>
            <div className="chat-empty__subtitle">
              Your chat history will appear here once you start chatting in any Space.
            </div>
          </div>
        ) : (
          filledConversations.map((convo) => {
            const lastUserMsg = [...convo.messages].reverse().find((m) => m.role === 'user');
            const preview = lastUserMsg?.content.replace(/\[Attached:.*?\]/g, '').trim().slice(0, 120) || '';
            return renderConversationItem(
              convo,
              preview,
              convo.messages.length,
            );
          })
        )}
      </div>
    </div>
  );
}
