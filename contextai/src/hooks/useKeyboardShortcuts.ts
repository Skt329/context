/**
 * useKeyboardShortcuts — central keyboard shortcut handler.
 *
 * Shortcuts:
 *   Ctrl+N        — New chat
 *   Ctrl+1/2/3/4  — Switch tabs (Chat/Spaces/History/Settings)
 *   Ctrl+Shift+C  — Capture screen context
 *   Esc           — Clear screen context / close modals
 */

import { useEffect } from 'react';
import { useAppStore, type Tab } from '../stores/appStore';
import { captureScreenContext } from '../lib/api';

const TAB_MAP: Record<string, Tab> = {
  '1': 'chat',
  '2': 'spaces',
  '3': 'history',
  '4': 'settings',
};

export function useKeyboardShortcuts() {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const { ctrlKey, shiftKey, key } = e;

      // Ctrl+N — New chat
      if (ctrlKey && !shiftKey && key === 'n') {
        e.preventDefault();
        useAppStore.getState().newChat();
        useAppStore.getState().setActiveTab('chat');
        return;
      }

      // Ctrl+1/2/3/4 — Switch tabs
      if (ctrlKey && !shiftKey && TAB_MAP[key]) {
        e.preventDefault();
        useAppStore.getState().setActiveTab(TAB_MAP[key]);
        return;
      }

      // Ctrl+Shift+C — Capture screen context
      if (ctrlKey && shiftKey && key === 'C') {
        e.preventDefault();
        const state = useAppStore.getState();
        if (state.backendReady) {
          captureScreenContext().then((result) => {
            if (result && result.length > 0) {
              state.setScreenContext(result.text);
            }
          });
        }
        return;
      }

      // Esc — Clear screen context
      if (key === 'Escape') {
        const state = useAppStore.getState();
        if (state.screenContext) {
          state.setScreenContext(null);
        }
        return;
      }
    };

    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);
}
