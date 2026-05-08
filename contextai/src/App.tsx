import { useEffect } from 'react';
import './index.css';
import { TitleBar } from './components/TitleBar';
import { TabNav } from './components/TabNav';
import { ChatView } from './components/ChatView';
import { SpacesView } from './components/SpacesView';
import { HistoryView } from './components/HistoryView';
import { SettingsView } from './components/SettingsView';
import { useAppStore } from './stores/appStore';
import { checkHealth, fetchOllamaModels, updateProvider } from './lib/api';

function App() {
  const activeTab = useAppStore((s) => s.activeTab);
  const setBackendReady = useAppStore((s) => s.setBackendReady);
  const setOllamaModels = useAppStore((s) => s.setOllamaModels);

  // Poll backend health every 5 seconds & detect Ollama models on connect
  useEffect(() => {
    let alive = true;
    let ollamaDetected = false;

    const poll = async () => {
      while (alive) {
        const health = await checkHealth();
        const isReady = health?.status === 'ok';
        setBackendReady(isReady);

        // Detect Ollama models once backend is ready
        if (isReady && !ollamaDetected) {
          const result = await fetchOllamaModels();
          if (result.available && result.models.length > 0) {
            const modelNames = result.models.map((m) => m.name);
            setOllamaModels(modelNames);

            // Sync the first detected model to backend as default
            const firstModel = modelNames[0];
            await updateProvider('ollama', { enabled: true, model: firstModel });
            ollamaDetected = true;
          }
        }

        await new Promise((r) => setTimeout(r, 5000));
      }
    };

    poll();
    return () => { alive = false; };
  }, [setBackendReady, setOllamaModels]);

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
