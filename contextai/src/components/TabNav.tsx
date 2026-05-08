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

  return (
    <nav className="tab-nav">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          className={`tab-nav__item ${activeTab === tab.id ? 'tab-nav__item--active' : ''}`}
          onClick={() => setActiveTab(tab.id)}
        >
          <span className="tab-nav__icon">{tab.icon}</span>
          {tab.label}
        </button>
      ))}
    </nav>
  );
}
