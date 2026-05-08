import { Minus, X, Pin, PinOff } from 'lucide-react';
import { useState } from 'react';
import { useAppStore } from '../stores/appStore';
import { isTauri } from '../lib/env';

export function TitleBar() {
  const [pinned, setPinned] = useState(true);
  const activeSpaceId = useAppStore((s) => s.activeSpaceId);
  const spaces = useAppStore((s) => s.spaces);
  const activeSpace = spaces.find((s) => s.id === activeSpaceId);

  const handleMinimize = async () => {
    if (!isTauri()) return;
    const { getCurrentWindow } = await import('@tauri-apps/api/window');
    const win = getCurrentWindow();
    await win.minimize();
  };

  const handleClose = async () => {
    if (!isTauri()) return;
    const { getCurrentWindow } = await import('@tauri-apps/api/window');
    const win = getCurrentWindow();
    await win.hide();
  };

  const handlePin = async () => {
    if (!isTauri()) return;
    const { getCurrentWindow } = await import('@tauri-apps/api/window');
    const win = getCurrentWindow();
    const next = !pinned;
    await win.setAlwaysOnTop(next);
    setPinned(next);
  };

  return (
    <div className="title-bar">
      <div className="title-bar__left">
        <div className="title-bar__logo">C</div>
        <span className="title-bar__title">ContextAI</span>
        {activeSpace && (
          <span className="title-bar__space">
            {activeSpace.icon} {activeSpace.name}
          </span>
        )}
      </div>
      <div className="title-bar__actions">
        {isTauri() && (
          <>
            <button className="title-bar__btn" onClick={handlePin} title={pinned ? 'Unpin' : 'Pin on top'}>
              {pinned ? <PinOff size={14} /> : <Pin size={14} />}
            </button>
            <button className="title-bar__btn" onClick={handleMinimize}>
              <Minus size={14} />
            </button>
            <button className="title-bar__btn title-bar__btn--close" onClick={handleClose}>
              <X size={14} />
            </button>
          </>
        )}
      </div>
    </div>
  );
}
