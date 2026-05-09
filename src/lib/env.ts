/**
 * Environment detection utilities for ContextAI.
 * Differentiates between Tauri desktop and browser runtime.
 */

/**
 * Returns true if running inside a Tauri WebView (desktop app).
 * Returns false if running in a standard browser (dev mode).
 */
export function isTauri(): boolean {
  return typeof window !== 'undefined' && !!(window as any).__TAURI_INTERNALS__;
}
