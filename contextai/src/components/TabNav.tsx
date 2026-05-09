import { MessageSquare, Layers, Clock, Settings } from 'lucide-react';
import { useAppStore, type Tab } from '../stores/appStore';

const tabs: { id: Tab; label: string; icon: React.ReactNode }[] = [
  { id: 'chat', label: 'Chat', icon: <MessageSquare size={18} /> },
  { id: 'spaces', label: 'Spaces', icon: <Layers size={18} /> },
  { id: 'history', label: 'History', icon: <Clock size={18} /> },
  { id: 'settings', label: 'Settings', icon: <Settings size={18} /> },
];

export function TabNav() {
  const activeTab = useAppStore((s) => s.activeTab);
  const setActiveTab = useAppStore((s) => s.setActiveTab);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    const currentIndex = tabs.findIndex((t) => t.id === activeTab);
    if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
      e.preventDefault();
      const next = tabs[(currentIndex + 1) % tabs.length];
      setActiveTab(next.id);
    } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
      e.preventDefault();
      const prev = tabs[(currentIndex - 1 + tabs.length) % tabs.length];
      setActiveTab(prev.id);
    }
  };

  return (
    <nav className="tab-nav" role="tablist" aria-label="Main navigation">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          className={`tab-nav__item ${activeTab === tab.id ? 'tab-nav__item--active' : ''}`}
          onClick={() => setActiveTab(tab.id)}
          onKeyDown={handleKeyDown}
          role="tab"
          aria-selected={activeTab === tab.id}
          aria-controls={`panel-${tab.id}`}
          tabIndex={activeTab === tab.id ? 0 : -1}
          id={`tab-${tab.id}`}
        >
          <span className="tab-nav__icon">{tab.icon}</span>
          {tab.label}
        </button>
      ))}
    </nav>
  );
}
