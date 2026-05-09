/**
 * Toast Notification System
 * Renders toast notifications in the bottom-right corner with auto-dismiss.
 */

import { create } from 'zustand';
import { Check, AlertTriangle, Info, X } from 'lucide-react';

// ─── Toast Store ─────────────────────────────────────────────

export type ToastType = 'success' | 'error' | 'info' | 'warning';

interface ToastItem {
  id: string;
  type: ToastType;
  message: string;
  duration: number; // ms
}

interface ToastStore {
  toasts: ToastItem[];
  addToast: (type: ToastType, message: string, duration?: number) => void;
  removeToast: (id: string) => void;
}

export const useToastStore = create<ToastStore>((set) => ({
  toasts: [],
  addToast: (type, message, duration = 3000) => {
    const id = crypto.randomUUID();
    set((s) => ({ toasts: [...s.toasts, { id, type, message, duration }] }));
    // Auto-remove
    setTimeout(() => {
      set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) }));
    }, duration);
  },
  removeToast: (id) => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
}));

// Convenience helpers
export const toast = {
  success: (msg: string) => useToastStore.getState().addToast('success', msg),
  error: (msg: string) => useToastStore.getState().addToast('error', msg, 5000),
  info: (msg: string) => useToastStore.getState().addToast('info', msg),
  warning: (msg: string) => useToastStore.getState().addToast('warning', msg, 4000),
};

// ─── Toast Component ─────────────────────────────────────────

const icons: Record<ToastType, React.ReactNode> = {
  success: <Check size={14} />,
  error: <AlertTriangle size={14} />,
  info: <Info size={14} />,
  warning: <AlertTriangle size={14} />,
};

function ToastItem({ item }: { item: ToastItem }) {
  const removeToast = useToastStore((s) => s.removeToast);

  return (
    <div className={`toast toast--${item.type}`}>
      <span className="toast__icon">{icons[item.type]}</span>
      <span className="toast__message">{item.message}</span>
      <button className="toast__close" onClick={() => removeToast(item.id)}>
        <X size={12} />
      </button>
    </div>
  );
}

export function ToastContainer() {
  const toasts = useToastStore((s) => s.toasts);

  if (toasts.length === 0) return null;

  return (
    <div className="toast-container">
      {toasts.map((t) => (
        <ToastItem key={t.id} item={t} />
      ))}
    </div>
  );
}
