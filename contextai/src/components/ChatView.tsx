import { useState, useRef, useEffect } from 'react';
import { Send, Sparkles, FileText, Mail, BookOpen, X, Zap } from 'lucide-react';
import { useAppStore } from '../stores/appStore';

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

    // Auto-resize textarea back
    if (textareaRef.current) {
      textareaRef.current.style.height = '20px';
    }

    setIsGenerating(true);

    // Simulate AI response (will be replaced with actual FastAPI SSE call)
    const assistantMsg = {
      id: crypto.randomUUID(),
      role: 'assistant' as const,
      content: '',
      timestamp: new Date().toISOString(),
      isStreaming: true,
    };
    addMessage(assistantMsg);

    // Simulated streaming response
    const response = `I'm ContextAI, your personal context engine. I can see you're working in the "${activeSpace?.name}" space.${screenContext ? `\n\nI also have context from your current screen:\n"${screenContext.slice(0, 100)}..."` : ''}\n\nOnce the Python backend is connected, I'll use your uploaded documents and RAG pipeline to provide grounded, contextual responses. For now, the UI is fully functional — try switching spaces, configuring providers, or exploring the settings.`;
    
    let current = '';
    for (let i = 0; i < response.length; i++) {
      current += response[i];
      useAppStore.getState().updateMessage(assistantMsg.id, current);
      await new Promise((r) => setTimeout(r, 12));
    }

    setIsGenerating(false);
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
    { label: 'Cover Letter', icon: <FileText size={12} /> },
    { label: 'Cold Email', icon: <Mail size={12} /> },
    { label: 'Summarize', icon: <BookOpen size={12} /> },
    { label: 'Explain', icon: <Sparkles size={12} /> },
  ];

  return (
    <div className="chat-view">
      {screenContext && (
        <div className="context-bar">
          <Zap className="context-bar__icon" />
          <span className="context-bar__text">
            Screen context captured ({screenContext.length} chars)
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
              Press Ctrl+Shift+Space to toggle this widget anywhere.
            </div>
            <div className="chat-empty__actions">
              {quickActions.map((action) => (
                <button
                  key={action.label}
                  className="quick-action"
                  onClick={() => setInput(`Help me write a ${action.label.toLowerCase()}`)}
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
                  {msg.isStreaming && (
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
        <div className="chat-input-wrapper">
          <textarea
            ref={textareaRef}
            className="chat-input"
            placeholder={backendReady ? `Message ${activeSpace?.name}...` : 'Type a message...'}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            onInput={handleTextareaInput}
            rows={1}
          />
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
