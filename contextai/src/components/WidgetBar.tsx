/**
 * WidgetBar — WhisperFlow-style floating pill that sits above the taskbar.
 *
 * Architecture:
 *   - The Tauri window is 480×500px, fully transparent.
 *   - Content is anchored to the bottom via flex + justify-end.
 *   - The pill starts compact (~48px tall) and expands UPWARD via CSS transitions.
 *   - No Rust-level window resizing — all visual expansion is CSS-only.
 *
 * States:
 *   IDLE    → Compact pill: space icon + "ContextAI" + status dot
 *   ACTIVE  → Full input bar: space selector + input + send (on hover/click)
 *   EXPANDED → Input bar + response panel above (after send)
 *
 * Features:
 *   - Space switcher dropdown (opens upward)
 *   - Auto-captures screen context
 *   - Streaming response with markdown rendering
 *   - Copy / Inject / New Chat / Dismiss
 *   - Esc to dismiss, Enter to send
 */

import { useState, useRef, useEffect, useCallback } from 'react';
import {
  Send, Square, Copy, Check, Zap, ArrowUpRight,
  ChevronDown, RotateCcw, X, Sparkles,
} from 'lucide-react';
import { useAppStore } from '../stores/appStore';
import { streamChat, captureScreenContext, generateTitle } from '../lib/api';
import { MarkdownRenderer } from './MarkdownRenderer';
import { toast } from './Toast';
import { isTauri } from '../lib/env';

type WidgetState = 'idle' | 'active' | 'expanded';

export function WidgetBar() {
  const [widgetState, setWidgetState] = useState<WidgetState>('idle');
  const [input, setInput] = useState('');
  const [response, setResponse] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [copied, setCopied] = useState(false);
  const [contextInfo, setContextInfo] = useState<string | null>(null);
  const [spaceSelectorOpen, setSpaceSelectorOpen] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const spaceSelectorRef = useRef<HTMLDivElement>(null);
  const idleTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Store
  const activeSpaceId = useAppStore((s) => s.activeSpaceId);
  const spaces = useAppStore((s) => s.spaces);
  const backendReady = useAppStore((s) => s.backendReady);
  const addMessage = useAppStore((s) => s.addMessage);
  const activeConversationId = useAppStore((s) => s.activeConversationId);
  const setConversationTitle = useAppStore((s) => s.setConversationTitle);
  const newChat = useAppStore((s) => s.newChat);
  const setActiveSpace = useAppStore((s) => s.setActiveSpace);
  const activeSpace = spaces.find((s) => s.id === activeSpaceId);

  // Auto-capture screen context once backend is ready
  useEffect(() => {
    if (backendReady) {
      captureScreenContext().then((result) => {
        if (result?.text?.length) {
          setContextInfo(`${result.text.length} chars`);
          useAppStore.getState().setScreenContext(result.text);
        }
      }).catch(() => {});
    }
  }, [backendReady]);

  // Focus input when transitioning to active
  useEffect(() => {
    if (widgetState === 'active') {
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  }, [widgetState]);

  // Esc to dismiss
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        if (spaceSelectorOpen) {
          setSpaceSelectorOpen(false);
        } else if (widgetState === 'expanded' || widgetState === 'active') {
          if (!isStreaming) {
            resetToIdle();
          }
        } else {
          hideWidget();
        }
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [spaceSelectorOpen, widgetState, isStreaming]);

  // Close space selector on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (spaceSelectorRef.current && !spaceSelectorRef.current.contains(e.target as Node)) {
        setSpaceSelectorOpen(false);
      }
    };
    if (spaceSelectorOpen) document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [spaceSelectorOpen]);

  // Return to idle after mouse leaves (only when in 'active' state, no input)
  const handleMouseEnter = useCallback(() => {
    if (idleTimerRef.current) {
      clearTimeout(idleTimerRef.current);
      idleTimerRef.current = null;
    }
    if (widgetState === 'idle') {
      setWidgetState('active');
    }
  }, [widgetState]);

  const handleMouseLeave = useCallback(() => {
    // Only return to idle if no input, no response, and not streaming
    if (widgetState === 'active' && !input.trim() && !response && !isStreaming) {
      idleTimerRef.current = setTimeout(() => {
        setWidgetState('idle');
      }, 800);
    }
  }, [widgetState, input, response, isStreaming]);

  const resetToIdle = () => {
    setWidgetState('idle');
    setResponse('');
    setInput('');
    setIsStreaming(false);
    setSpaceSelectorOpen(false);
  };

  const hideWidget = async () => {
    if (!isTauri()) return;
    try {
      const { invoke } = await import('@tauri-apps/api/core');
      await invoke('hide_widget');
    } catch {}
    resetToIdle();
    setContextInfo(null);
  };

  const handleSend = async () => {
    const text = input.trim();
    if (!text || isStreaming || !backendReady) return;

    setWidgetState('expanded');
    setResponse('');
    setIsStreaming(true);
    setInput('');

    if (!activeConversationId) {
      newChat();
    }

    const userMsg = {
      id: crypto.randomUUID(),
      role: 'user' as const,
      content: text,
      timestamp: new Date().toISOString(),
    };
    addMessage(userMsg);

    const abortCtrl = new AbortController();
    abortRef.current = abortCtrl;

    const screenCtx = useAppStore.getState().screenContext;
    let accumulated = '';

    const assistantMsg = {
      id: crypto.randomUUID(),
      role: 'assistant' as const,
      content: '',
      timestamp: new Date().toISOString(),
      isStreaming: true,
    };
    addMessage(assistantMsg);

    await streamChat(
      text,
      activeSpaceId || 'default',
      screenCtx,
      (chunk) => {
        accumulated += chunk;
        setResponse(accumulated);
        useAppStore.getState().updateMessage(assistantMsg.id, accumulated);
      },
      (error) => {
        accumulated += `\n⚠️ ${error}`;
        setResponse(accumulated);
        useAppStore.getState().updateMessage(assistantMsg.id, accumulated);
      },
      () => {
        setIsStreaming(false);
        abortRef.current = null;
      },
      activeSpace?.textContext,
      undefined,
      undefined,
      abortCtrl.signal,
    );

    // Auto-title
    const convoId = useAppStore.getState().activeConversationId;
    if (convoId) {
      const title = await generateTitle(text);
      if (title) setConversationTitle(convoId, title);
    }
  };

  const handleStop = () => {
    abortRef.current?.abort();
    setIsStreaming(false);
    abortRef.current = null;
  };

  const handleCopy = async () => {
    await navigator.clipboard.writeText(response);
    setCopied(true);
    toast.success('Copied');
    setTimeout(() => setCopied(false), 2000);
  };

  const handleInject = async () => {
    if (!isTauri() || !response) return;
    try {
      const { invoke } = await import('@tauri-apps/api/core');
      const result = await invoke<string>('inject_text', { text: response });
      console.log('[inject result]', result);
      if (result?.startsWith('HWND=0')) {
        toast.info('Copied to clipboard — press Ctrl+V');
      } else {
        toast.success('Injected!');
      }
    } catch (e) {
      console.error('[inject error]', e);
      toast.error('Injection failed');
    }
    // Don't reset — widget stays visible so user can re-inject or dismiss
  };

  const handleNewChat = () => {
    newChat();
    setWidgetState('active');
    setResponse('');
    setInput('');
    setTimeout(() => inputRef.current?.focus(), 100);
  };

  const handleSpaceSelect = (spaceId: string) => {
    if (spaceId !== activeSpaceId) {
      setActiveSpace(spaceId);
      newChat();
    }
    setSpaceSelectorOpen(false);
    inputRef.current?.focus();
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handlePillClick = () => {
    if (widgetState === 'idle') {
      setWidgetState('active');
    }
  };

  return (
    <div
      className={`wgt ${widgetState !== 'idle' ? 'wgt--active' : ''}`}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
    >
      {/* ── Response panel (shown when expanded, grows upward) ── */}
      {widgetState === 'expanded' && (
        <div className="wgt__response">
          {response ? (
            <div className="wgt__response-content">
              <MarkdownRenderer content={response} />
            </div>
          ) : (
            <div className="wgt__loading">
              <div className="wgt__loading-dots"><span /><span /><span /></div>
              <span className="wgt__loading-label">Thinking...</span>
            </div>
          )}
        </div>
      )}

      {/* ── Action bar (shown after response, between response and input) ── */}
      {widgetState === 'expanded' && !isStreaming && response && (
        <div className="wgt__actions">
          <button className="wgt__action" onClick={handleCopy} title="Copy">
            {copied ? <Check size={12} /> : <Copy size={12} />}
            <span>{copied ? 'Copied' : 'Copy'}</span>
          </button>
          <button className="wgt__action wgt__action--inject" onClick={handleInject} title="Inject into active app">
            <ArrowUpRight size={12} />
            <span>Inject</span>
          </button>
          <button className="wgt__action" onClick={handleNewChat} title="New chat">
            <RotateCcw size={12} />
            <span>New</span>
          </button>
          <div className="wgt__action-spacer" />
          <button className="wgt__action wgt__action--close" onClick={resetToIdle} title="Close">
            <X size={12} />
          </button>
        </div>
      )}

      {/* ── Input bar / Pill ── */}
      <div
        className={`wgt__bar ${widgetState === 'idle' ? 'wgt__bar--pill' : 'wgt__bar--full'}`}
        onClick={handlePillClick}
      >
        {/* Space selector */}
        <div className="wgt__space" ref={spaceSelectorRef}>
          <button
            className="wgt__space-btn"
            onClick={(e) => {
              e.stopPropagation();
              if (widgetState !== 'idle') setSpaceSelectorOpen(!spaceSelectorOpen);
            }}
            title={activeSpace?.name || 'Default'}
          >
            <span className="wgt__space-emoji">{activeSpace?.icon || '🔮'}</span>
            {widgetState !== 'idle' && (
              <>
                <span className="wgt__space-name">{activeSpace?.name || 'Default'}</span>
                <ChevronDown
                  size={10}
                  className={`wgt__space-chev ${spaceSelectorOpen ? 'wgt__space-chev--open' : ''}`}
                />
              </>
            )}
          </button>

          {spaceSelectorOpen && spaces.length > 0 && (
            <div className="wgt__space-drop">
              {spaces.map((space) => (
                <button
                  key={space.id}
                  className={`wgt__space-opt ${space.id === activeSpaceId ? 'wgt__space-opt--active' : ''}`}
                  onClick={(e) => {
                    e.stopPropagation();
                    handleSpaceSelect(space.id);
                  }}
                >
                  <span>{space.icon}</span>
                  <span className="wgt__space-opt-name">{space.name}</span>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Input field (hidden in idle, shown in active/expanded) */}
        {widgetState !== 'idle' ? (
          <>
            <input
              ref={inputRef}
              className="wgt__input"
              type="text"
              placeholder={
                backendReady
                  ? `Ask ${activeSpace?.name || 'ContextAI'}...`
                  : 'Connecting...'
              }
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={isStreaming || !backendReady}
            />

            {contextInfo && (
              <span className="wgt__ctx">
                <Zap size={9} /> {contextInfo}
              </span>
            )}

            {/* Status dot */}
            <div
              className={`wgt__status ${backendReady ? 'wgt__status--on' : 'wgt__status--off'}`}
              title={backendReady ? 'Connected' : 'Connecting...'}
            />

            {isStreaming ? (
              <button className="wgt__send wgt__send--stop" onClick={handleStop} title="Stop">
                <Square size={11} />
              </button>
            ) : (
              <button
                className="wgt__send"
                onClick={handleSend}
                disabled={!input.trim() || !backendReady}
                title="Send (Enter)"
              >
                <Send size={11} />
              </button>
            )}
          </>
        ) : (
          /* Idle pill content */
          <>
            <span className="wgt__pill-label">
              {activeSpace?.name || 'ContextAI'}
            </span>
            <Sparkles size={11} className="wgt__pill-sparkle" />
            <div
              className={`wgt__status ${backendReady ? 'wgt__status--on' : 'wgt__status--off'}`}
            />
          </>
        )}
      </div>
    </div>
  );
}
