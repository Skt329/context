import { MessageSquare } from 'lucide-react';
import { useAppStore } from '../stores/appStore';

export function HistoryView() {
  const history = useAppStore((s) => s.history);
  const spaces = useAppStore((s) => s.spaces);

  if (history.length === 0) {
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

  return (
    <div className="history-view">
      <h2 className="spaces-header__title" style={{ marginBottom: '4px' }}>History</h2>
      {history.map((item) => {
        const space = spaces.find((s) => s.id === item.spaceId);
        return (
          <div key={item.id} className="history-item">
            <div style={{ fontSize: '18px' }}>{space?.icon || '💬'}</div>
            <div className="history-item__content">
              <div className="history-item__title">{item.title}</div>
              <div className="history-item__time">
                {space?.name} · {new Date(item.timestamp).toLocaleDateString()}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
