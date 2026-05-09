/**
 * SpaceSwitcher — dropdown in chat header for quick space switching.
 */

import { useState, useRef, useEffect } from 'react';
import { ChevronDown } from 'lucide-react';
import { useAppStore } from '../stores/appStore';

export function SpaceSwitcher() {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const spaces = useAppStore((s) => s.spaces);
  const activeSpaceId = useAppStore((s) => s.activeSpaceId);
  const setActiveSpace = useAppStore((s) => s.setActiveSpace);
  const newChat = useAppStore((s) => s.newChat);

  const activeSpace = spaces.find((s) => s.id === activeSpaceId);

  // Close on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    if (open) document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open]);

  const handleSelect = (spaceId: string) => {
    if (spaceId !== activeSpaceId) {
      setActiveSpace(spaceId);
      newChat(); // Start fresh chat in the new space
    }
    setOpen(false);
  };

  return (
    <div className="space-switcher" ref={ref}>
      <button
        className="space-switcher__trigger"
        onClick={() => setOpen(!open)}
      >
        <span className="space-switcher__icon">{activeSpace?.icon}</span>
        <span className="space-switcher__name">{activeSpace?.name}</span>
        <ChevronDown size={12} className={`space-switcher__chevron ${open ? 'space-switcher__chevron--open' : ''}`} />
      </button>

      {open && (
        <div className="space-switcher__dropdown">
          {spaces.map((space) => (
            <button
              key={space.id}
              className={`space-switcher__item ${space.id === activeSpaceId ? 'space-switcher__item--active' : ''}`}
              onClick={() => handleSelect(space.id)}
            >
              <span>{space.icon}</span>
              <span className="space-switcher__item-name">{space.name}</span>
              <span className="space-switcher__item-count">{space.fileCount} files</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
