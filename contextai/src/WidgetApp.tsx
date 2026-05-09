/**
 * WidgetApp — Root component for the floating widget window.
 * Runs its own backend health polling, and positions itself
 * above the taskbar on mount.
 */

import { useEffect, useRef } from 'react';
import './index.css';
import { WidgetBar } from './components/WidgetBar';
import { ToastContainer } from './components/Toast';
import { useAppStore } from './stores/appStore';
import { checkHealth, fetchOllamaModels, updateProvider } from './lib/api';
import { isTauri } from './lib/env';

export function WidgetApp() {
  const setBackendReady = useAppStore((s) => s.setBackendReady);
  const setOllamaModels = useAppStore((s) => s.setOllamaModels);
  const hydrateFromBackend = useAppStore((s) => s.hydrateFromBackend);
  const pollRef = useRef(false);

  // Position widget above taskbar on mount
  useEffect(() => {
    const positionWidget = async () => {
      if (!isTauri()) return;
      try {
        const { invoke } = await import('@tauri-apps/api/core');
        await invoke('position_widget_bottom');
      } catch {}
    };
    positionWidget();
  }, []);

  // Backend health polling (identical to App.tsx)
  useEffect(() => {
    if (pollRef.current) return;
    pollRef.current = true;

    let alive = true;
    let ollamaDetected = false;
    let wasReady = false;
    let hydrated = false;

    const poll = async () => {
      while (alive) {
        const health = await checkHealth();
        const isReady = health?.status === 'ok';

        if (isReady !== wasReady) {
          setBackendReady(isReady);
          wasReady = isReady;
        }

        if (isReady && !hydrated) {
          hydrated = true;
          await hydrateFromBackend();
        }

        if (isReady && !ollamaDetected) {
          const result = await fetchOllamaModels();
          if (result.available && result.models.length > 0) {
            const modelNames = result.models.map((m) => m.name);
            setOllamaModels(modelNames);
            await updateProvider('ollama', { enabled: true, model: modelNames[0] });
            ollamaDetected = true;
          }
        }

        await new Promise((r) => setTimeout(r, isReady ? 30000 : 3000));
      }
    };

    poll();
    return () => { alive = false; };
  }, [setBackendReady, setOllamaModels, hydrateFromBackend]);

  return (
    <div className="widget-root">
      <WidgetBar />
      <ToastContainer />
    </div>
  );
}
