import { useEffect, useRef } from 'react';
import './index.css';
import { TitleBar } from './components/TitleBar';
import { TabNav } from './components/TabNav';
import { ChatView } from './components/ChatView';
import { SpacesView } from './components/SpacesView';
import { HistoryView } from './components/HistoryView';
import { SettingsView } from './components/SettingsView';
import { ToastContainer } from './components/Toast';
import { ErrorBoundary } from './components/ErrorBoundary';
import { useAppStore } from './stores/appStore';
import { checkHealth, fetchOllamaModels, updateProvider } from './lib/api';
import { useKeyboardShortcuts } from './hooks/useKeyboardShortcuts';

function App() {
  const activeTab = useAppStore((s) => s.activeTab);
  const setBackendReady = useAppStore((s) => s.setBackendReady);
  const setOllamaModels = useAppStore((s) => s.setOllamaModels);
  const hydrateFromBackend = useAppStore((s) => s.hydrateFromBackend);

  // Global keyboard shortcuts
  useKeyboardShortcuts();

  // Guard against StrictMode double-mount (Mi2)
  const pollRef = useRef(false);

  useEffect(() => {
    if (pollRef.current) return; // Prevent double-poll in StrictMode
    pollRef.current = true;

    let alive = true;
    let ollamaDetected = false;
    let wasReady = false;
    let hydrated = false;

    const poll = async () => {
      while (alive) {
        const health = await checkHealth();
        const isReady = health?.status === 'ok';

        // Only update Zustand when value changes to avoid re-render spam
        if (isReady !== wasReady) {
          setBackendReady(isReady);
          wasReady = isReady;
        }

        // Hydrate state from backend on first successful connection
        if (isReady && !hydrated) {
          hydrated = true;
          await hydrateFromBackend();
        }

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

        // Poll fast (5s) when disconnected, slow (30s) when connected
        await new Promise((r) => setTimeout(r, isReady ? 30000 : 5000));
      }
    };

    poll();
    return () => { alive = false; };
  }, [setBackendReady, setOllamaModels, hydrateFromBackend]);

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
        <ErrorBoundary>
          {renderContent()}
        </ErrorBoundary>
      </div>
      <ToastContainer />
    </div>
  );
}

export default App;

