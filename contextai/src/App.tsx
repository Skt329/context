import './index.css';
import { TitleBar } from './components/TitleBar';
import { TabNav } from './components/TabNav';
import { ChatView } from './components/ChatView';
import { SpacesView } from './components/SpacesView';
import { HistoryView } from './components/HistoryView';
import { SettingsView } from './components/SettingsView';
import { useAppStore } from './stores/appStore';

function App() {
  const activeTab = useAppStore((s) => s.activeTab);

  const renderContent = () => {
    switch (activeTab) {
      case 'chat':
        return <ChatView />;
      case 'spaces':
        return <SpacesView />;
      case 'history':
        return <HistoryView />;
      case 'settings':
        return <SettingsView />;
    }
  };

  return (
    <div className="widget-shell">
      <TitleBar />
      <TabNav />
      <div className="content">
        {renderContent()}
      </div>
    </div>
  );
}

export default App;
