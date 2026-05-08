import { useState, useRef, useEffect } from 'react';
import { Send, Sparkles, FileText, Mail, BookOpen, X, Zap, Wifi, WifiOff } from 'lucide-react';
import { useAppStore } from '../stores/appStore';
import { streamChat, captureContext } from '../lib/api';

export function ChatView() {
  const messages = useAppStore((s) => s.messages);
  const isGenerating = useAppStore((s) => s.isGenerating);
  const addMessage = useAppStore((s) => s.addMessage);
  const setIsGenerating = useAppStore((s) => s.setIsGenerating);
  const screenContext = useAppStore((s) => s.screenContext);
  const setScreenContext = useAppStore((s) => s.setScreenContext);
  const backendReady = useAppStore((s) => s.backendReady);
  const activeSpaceId = useAppStore((s) => s.activeSpaceId);
  const spaces = useAppStore((s) => s.spaces);
  const activeSpace = spaces.find((s) => s.id === activeSpaceId);

  const [input, setInput] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleCaptureContext = async () => {
    if (!backendReady) return;
    const result = await captureContext();
    if (result && result.length > 0) {
      setScreenContext(result.text);
    }
  };

  const handleSend = async () => {
    const text = input.trim();
    if (!text || isGenerating) return;

    const userMsg = {
      id: crypto.randomUUID(),
      role: 'user' as const,
      content: text,
      timestamp: new Date().toISOString(),
    };
    addMessage(userMsg);
    setInput('');

    if (textareaRef.current) {
      textareaRef.current.style.height = '20px';
    }

    setIsGenerating(true);

    const assistantMsg = {
      id: crypto.randomUUID(),
      role: 'assistant' as const,
      content: '',
      timestamp: new Date().toISOString(),
      isStreaming: true,
    };
    addMessage(assistantMsg);

    if (backendReady) {
      // Real backend streaming
      let accumulated = '';
      await streamChat(
        text,
        activeSpaceId || 'default',
        screenContext,
        (chunk) => {
          accumulated += chunk;
          useAppStore.getState().updateMessage(assistantMsg.id, accumulated);
        },
        (error) => {
          accumulated += `\n\n⚠️ Error: ${error}`;
          useAppStore.getState().updateMessage(assistantMsg.id, accumulated);
        },
        () => {
          setIsGenerating(false);
        },
      );
    } else {
      // Fallback: simulated response when backend is offline
      const response = `I'm ContextAI running in **offline mode** — the Python backend isn't connected yet.\n\n**To enable real AI responses:**\n1. Open a terminal in \`contextai/backend\`\n2. Run: \`.venv\\Scripts\\activate\`\n3. Run: \`python -m app.main\`\n4. The status indicator will turn green ✅\n\nOnce connected, I'll use **LiteLLM** to route to your configured provider (OpenAI, Anthropic, Gemini, etc.) with RAG context from your Space.`;

      let current = '';
      for (let i = 0; i < response.length; i++) {
        current += response[i];
        useAppStore.getState().updateMessage(assistantMsg.id, current);
        await new Promise((r) => setTimeout(r, 8));
      }
      setIsGenerating(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleTextareaInput = () => {
    if (textareaRef.current) {
      textareaRef.current.style.height = '20px';
      textareaRef.current.style.height = textareaRef.current.scrollHeight + 'px';
    }
  };

  const quickActions = [
    { label: 'Summarize this', icon: <BookOpen size={12} /> },
    { label: 'Draft email', icon: <Mail size={12} /> },
    { label: 'Explain code', icon: <FileText size={12} /> },
    { label: 'Quick answer', icon: <Sparkles size={12} /> },
  ];

  return (
    <div className="chat-view">
      {screenContext && (
        <div className="context-bar">
          <Zap className="context-bar__icon" />
          <span className="context-bar__text">
            Screen context active ({screenContext.length} chars)
          </span>
          <button className="context-bar__close" onClick={() => setScreenContext(null)}>
            <X size={12} />
          </button>
        </div>
      )}

      <div className="chat-messages">
        {messages.length === 0 ? (
          <div className="chat-empty">
            <div className="chat-empty__icon">
              <Sparkles size={24} />
            </div>
            <div className="chat-empty__title">
              {activeSpace?.icon} {activeSpace?.name}
            </div>
            <div className="chat-empty__subtitle">
              Ask anything using your uploaded documents as context.
              Press <strong>Ctrl+Shift+Space</strong> to toggle this widget.
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginTop: '4px' }}>
              <div className={`status-dot ${backendReady ? 'status-dot--connected' : 'status-dot--disconnected'}`} />
              <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                {backendReady ? 'Backend connected' : 'Backend offline — simulated mode'}
              </span>
            </div>
            <div className="chat-empty__actions">
              {quickActions.map((action) => (
                <button
                  key={action.label}
                  className="quick-action"
                  onClick={() => setInput(action.label)}
                >
                  {action.icon} {action.label}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <>
            {messages.map((msg) => (
              <div key={msg.id} className={`message message--${msg.role}`}>
                <div className="message__bubble">
                  {msg.content}
                  {msg.isStreaming && !msg.content && (
                    <span className="loading-dots">
                      <span></span><span></span><span></span>
                    </span>
                  )}
                </div>
                <span className="message__meta">
                  {new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </span>
              </div>
            ))}
            <div ref={messagesEndRef} />
          </>
        )}
      </div>

      <div className="chat-input-area">
        {!backendReady && (
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            padding: '4px 8px',
            marginBottom: '6px',
            fontSize: '10px',
            color: 'var(--warning)',
            background: 'rgba(251, 191, 36, 0.08)',
            borderRadius: 'var(--radius-sm)',
          }}>
            <WifiOff size={10} />
            Backend offline — responses are simulated
          </div>
        )}
        <div className="chat-input-wrapper">
          <textarea
            ref={textareaRef}
            className="chat-input"
            placeholder={backendReady ? `Message ${activeSpace?.name}...` : 'Type a message (simulated)...'}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            onInput={handleTextareaInput}
            rows={1}
          />
          {backendReady && (
            <button
              className="title-bar__btn"
              onClick={handleCaptureContext}
              title="Capture screen context"
              style={{ flexShrink: 0 }}
            >
              <Zap size={14} />
            </button>
          )}
          <button
            className="chat-send-btn"
            onClick={handleSend}
            disabled={!input.trim() || isGenerating}
          >
            <Send size={16} />
          </button>
        </div>
      </div>
    </div>
  );
}
