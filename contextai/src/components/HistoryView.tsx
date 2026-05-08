import { MessageSquare, Trash2, Clock } from 'lucide-react';
import { useAppStore } from '../stores/appStore';

export function HistoryView() {
  const conversations = useAppStore((s) => s.conversations);
  const spaces = useAppStore((s) => s.spaces);
  const activeConversationId = useAppStore((s) => s.activeConversationId);
  const loadConversation = useAppStore((s) => s.loadConversation);
  const deleteConversation = useAppStore((s) => s.deleteConversation);

  // Only show conversations with at least 1 message, sorted newest first
  const filledConversations = conversations
    .filter((c) => c.messages.length > 0)
    .sort((a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime());

  if (filledConversations.length === 0) {
    return (
      <div className="history-view">
        <div className="chat-empty" style={{ paddingTop: '60px' }}>
          <div className="chat-empty__icon">
            <MessageSquare size={24} />
          </div>
          <div className="chat-empty__title">No conversations yet</div>
          <div className="chat-empty__subtitle">
            Your chat history will appear here once you start chatting in any Space.
          </div>
        </div>
      </div>
    );
  }

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

  return (
    <div className="history-view">
      <h2 className="spaces-header__title" style={{ marginBottom: '4px' }}>History</h2>
      <p style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '12px' }}>
        {filledConversations.length} conversation{filledConversations.length !== 1 ? 's' : ''}
      </p>
      {filledConversations.map((convo) => {
        const space = spaces.find((s) => s.id === convo.spaceId);
        const isActive = convo.id === activeConversationId;
        const lastUserMsg = [...convo.messages].reverse().find((m) => m.role === 'user');
        const preview = lastUserMsg?.content.replace(/\[Attached:.*?\]/g, '').trim().slice(0, 120) || '';

        return (
          <div
            key={convo.id}
            className="history-item"
            style={{
              cursor: 'pointer',
              borderLeft: isActive ? '2px solid var(--accent)' : '2px solid transparent',
              background: isActive ? 'var(--accent-subtle)' : undefined,
            }}
            onClick={() => loadConversation(convo.id)}
          >
            <div style={{ fontSize: '18px', flexShrink: 0 }}>{space?.icon || '💬'}</div>
            <div className="history-item__content" style={{ flex: 1, minWidth: 0 }}>
              <div className="history-item__title">{convo.title}</div>
              {preview && (
                <div style={{
                  fontSize: '11px', color: 'var(--text-muted)',
                  overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                }}>
                  {preview}
                </div>
              )}
              <div className="history-item__time">
                <Clock size={10} style={{ marginRight: '3px' }} />
                {space?.name} · {formatDate(convo.updatedAt)} · {convo.messages.length} msgs
              </div>
            </div>
            <button
              className="title-bar__btn"
              onClick={(e) => {
                e.stopPropagation();
                deleteConversation(convo.id);
              }}
              title="Delete conversation"
              style={{ flexShrink: 0, opacity: 0.5 }}
            >
              <Trash2 size={13} />
            </button>
          </div>
        );
      })}
    </div>
  );
}
