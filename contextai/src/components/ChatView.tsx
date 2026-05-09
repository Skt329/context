import { useState, useRef, useEffect } from 'react';
import { Send, Sparkles, FileText, Mail, BookOpen, X, Zap, WifiOff, PlusCircle, Paperclip, Image } from 'lucide-react';
import { useAppStore, type ChatAttachment } from '../stores/appStore';
import { streamChat, captureScreenContext, uploadFile, extractMemoryFromChat, uploadAttachment, attachmentUrl } from '../lib/api';
import { MarkdownRenderer } from './MarkdownRenderer';

export function ChatView() {
  const activeConversationId = useAppStore((s) => s.activeConversationId);
  const conversations = useAppStore((s) => s.conversations);
  const isGenerating = useAppStore((s) => s.isGenerating);
  const addMessage = useAppStore((s) => s.addMessage);
  const setIsGenerating = useAppStore((s) => s.setIsGenerating);
  const screenContext = useAppStore((s) => s.screenContext);
  const setScreenContext = useAppStore((s) => s.setScreenContext);
  const backendReady = useAppStore((s) => s.backendReady);
  const activeSpaceId = useAppStore((s) => s.activeSpaceId);
  const spaces = useAppStore((s) => s.spaces);
  const newChat = useAppStore((s) => s.newChat);

  const handleNewChat = async () => {
    // Extract memory from the ending conversation before creating a new one
    if (activeConvo && activeConvo.messages.length > 2 && backendReady && activeSpaceId) {
      const chatMsgs = activeConvo.messages.map((m) => ({ role: m.role, content: m.content }));
      extractMemoryFromChat(chatMsgs, activeSpaceId).catch(() => {});
    }
    newChat();
  };

  const activeSpace = spaces.find((s) => s.id === activeSpaceId);
  const activeConvo = conversations.find((c) => c.id === activeConversationId);
  const messages = activeConvo?.messages ?? [];

  const [input, setInput] = useState('');
  const [attachments, setAttachments] = useState<ChatAttachment[]>([]);
  const [uploadingFiles, setUploadingFiles] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const imageInputRef = useRef<HTMLInputElement>(null);

  // File objects stored separately (not serializable)
  const pendingFilesRef = useRef<Map<string, File>>(new Map());

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Reset input when switching conversations
  useEffect(() => {
    setInput('');
    setAttachments([]);
    pendingFilesRef.current.clear();
  }, [activeConversationId]);

  const handleCaptureContext = async () => {
    if (!backendReady) return;
    const result = await captureScreenContext();
    if (result && result.length > 0) {
      setScreenContext(result.text);
    }
  };

  const handleAttachFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files) return;

    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      const attachId = crypto.randomUUID();
      const isImage = file.type.startsWith('image/');

      const attachment: ChatAttachment = {
        name: file.name,
        type: isImage ? 'image' : 'file',
        size: file.size,
      };

      // Store the actual File object for upload
      pendingFilesRef.current.set(attachId, file);

      if (isImage) {
        const reader = new FileReader();
        reader.onload = () => {
          attachment.dataUrl = reader.result as string;
          setAttachments((prev) => [...prev]); // Trigger re-render
        };
        reader.readAsDataURL(file);
      }

      setAttachments((prev) => [...prev, { ...attachment, name: `${attachId}::${file.name}` }]);
    }
    e.target.value = '';
  };

  const removeAttachment = (index: number) => {
    const att = attachments[index];
    const attachId = att.name.split('::')[0];
    pendingFilesRef.current.delete(attachId);
    setAttachments((prev) => prev.filter((_, i) => i !== index));
  };

  const getDisplayName = (name: string) => {
    const parts = name.split('::');
    return parts.length > 1 ? parts[1] : name;
  };

  const handleSend = async () => {
    const text = input.trim();
    if ((!text && attachments.length === 0) || isGenerating) return;

    // 1. Upload attached files to the active space for indexing
    const processedAttachments: ChatAttachment[] = [];
    // Keep original base64 data for the LLM vision call (not stored in conversation)
    const imageDataUrls = new Map<string, string>();
    if (attachments.length > 0 && backendReady) {
      setUploadingFiles(true);
      for (const att of attachments) {
        const attachId = att.name.split('::')[0];
        const displayName = getDisplayName(att.name);
        const file = pendingFilesRef.current.get(attachId);

        if (file && att.type === 'file') {
          // Upload document files to the space for RAG indexing
          const result = await uploadFile(activeSpaceId, file);
          processedAttachments.push({
            name: displayName,
            type: att.type,
            size: att.size,
            indexed: result?.indexing?.status === 'indexed',
          });
        } else if (att.type === 'image' && att.dataUrl) {
          // Preserve original base64 for the LLM call
          imageDataUrls.set(displayName, att.dataUrl);
          // Upload image to backend attachment storage — replaces base64 with URL
          const uploaded = await uploadAttachment(att.dataUrl, displayName);
          if (uploaded) {
            processedAttachments.push({
              name: displayName,
              type: att.type,
              size: uploaded.size,
              url: uploaded.url,
              // dataUrl intentionally omitted — no longer stored in conversation JSON
            });
          } else {
            // Fallback: keep dataUrl if upload failed (offline etc.)
            processedAttachments.push({
              name: displayName,
              type: att.type,
              size: att.size,
              dataUrl: att.dataUrl,
            });
          }
        } else {
          processedAttachments.push({
            name: displayName,
            type: att.type,
            size: att.size,
            dataUrl: att.dataUrl,
          });
        }
      }
      setUploadingFiles(false);
    }

    // 2. Build message content
    let messageContent = text;
    if (processedAttachments.length > 0) {
      const attachInfo = processedAttachments
        .map((a) => `[Attached: ${a.name}${a.indexed ? ' ✓ indexed' : ''}]`)
        .join(' ');
      messageContent = messageContent ? `${messageContent}\n\n${attachInfo}` : attachInfo;
    }

    const userMsg = {
      id: crypto.randomUUID(),
      role: 'user' as const,
      content: messageContent,
      timestamp: new Date().toISOString(),
      attachments: processedAttachments.length > 0 ? processedAttachments : undefined,
    };
    addMessage(userMsg);
    setInput('');
    setAttachments([]);
    pendingFilesRef.current.clear();

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
      // Build image payload for multi-modal LLM vision.
      // Use the original base64 dataUrl (kept in memory, NOT persisted),
      // because the LLM API requires data: URIs, not HTTP URLs.
      const imagePayload = processedAttachments
        .filter((a) => a.type === 'image' && (imageDataUrls.has(a.name) || a.dataUrl))
        .map((a) => ({
          data_url: imageDataUrls.get(a.name) || a.dataUrl!,
          name: a.name,
        }));

      // Build conversation history from all prior messages (exclude current)
      const conversationHistory = messages.map((m) => ({
        role: m.role,
        content: typeof m.content === 'string' ? m.content : '',
      }));

      let accumulated = '';
      await streamChat(
        messageContent,
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
        activeSpace?.textContext,
        imagePayload,
        conversationHistory,
      );
    } else {
      const response = `I'm ContextAI running in **offline mode** — the Python backend isn't connected yet.\n\n**To enable real AI responses:**\n1. Open a terminal in \`contextai/backend\`\n2. Run: \`.venv\\\\Scripts\\\\activate\`\n3. Run: \`python -m app.main\`\n4. The status indicator will turn green ✅`;

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
    {
      label: 'Summarize this',
      icon: <BookOpen size={12} />,
      prompt: screenContext
        ? 'Summarize the following screen context concisely:'
        : 'Summarize the uploaded documents in this space.',
    },
    {
      label: 'Draft email',
      icon: <Mail size={12} />,
      prompt: 'Draft a professional email based on the current context. Keep it concise and actionable.',
    },
    {
      label: 'Explain code',
      icon: <FileText size={12} />,
      prompt: screenContext
        ? 'Explain the code on my screen. Focus on what it does and any potential issues.'
        : 'Explain the code in the uploaded files. Focus on architecture and key decisions.',
    },
    {
      label: 'Quick answer',
      icon: <Sparkles size={12} />,
      prompt: 'Give me a quick, direct answer based on the available context.',
    },
    {
      label: 'Cover letter',
      icon: <FileText size={12} />,
      prompt: 'Write a tailored cover letter based on my profile and the job description in the current context. Match my writing style.',
    },
    {
      label: 'Cold email',
      icon: <Mail size={12} />,
      prompt: 'Draft a personalized cold outreach email based on the current context. Be concise and professional.',
    },
  ];

  return (
    <div className="chat-view">
      {/* Chat header */}
      <div className="chat-header">
        <div className="chat-header__space">
          <span className="chat-header__icon">{activeSpace?.icon}</span>
          <span className="chat-header__name">{activeSpace?.name}</span>
        </div>
        <button
          className="btn-ghost btn-sm"
          onClick={handleNewChat}
          disabled={messages.length === 0}
          title="New Chat"
        >
          <PlusCircle size={15} />
          <span>New Chat</span>
        </button>
      </div>

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
            <div className="chat-empty__icon"><Sparkles size={24} /></div>
            <div className="chat-empty__title">{activeSpace?.icon} {activeSpace?.name}</div>
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
                <button key={action.label} className="quick-action" onClick={() => setInput(action.prompt)}>
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
                  {msg.attachments?.filter((a) => a.type === 'image' && (a.dataUrl || a.url)).map((a, i) => (
                    <img key={i} src={a.url ? attachmentUrl(a.url) : a.dataUrl} alt={a.name} className="message__attachment-img" />
                  ))}
                  {msg.attachments?.filter((a) => a.type === 'file').map((a, i) => (
                    <div key={i} className="message__attachment-chip">
                      <FileText size={12} /> {a.name}
                      {a.indexed && <span style={{ color: 'var(--success)', marginLeft: '4px' }}>✓</span>}
                    </div>
                  ))}
                  {msg.role === 'assistant' ? (
                    <MarkdownRenderer content={msg.content} />
                  ) : (
                    msg.content
                  )}
                  {msg.isStreaming && !msg.content && (
                    <span className="loading-dots"><span></span><span></span><span></span></span>
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

      {/* Attachment preview strip */}
      {attachments.length > 0 && (
        <div className="attachment-strip">
          {attachments.map((att, i) => (
            <div key={i} className="attachment-chip">
              {att.type === 'image' && att.dataUrl ? (
                <img src={att.dataUrl} alt={getDisplayName(att.name)} className="attachment-chip__thumb" />
              ) : (
                <FileText size={12} />
              )}
              <span className="attachment-chip__name">{getDisplayName(att.name)}</span>
              <button className="attachment-chip__remove" onClick={() => removeAttachment(i)}>
                <X size={10} />
              </button>
            </div>
          ))}
        </div>
      )}

      <div className="chat-input-area">
        {!backendReady && (
          <div style={{
            display: 'flex', alignItems: 'center', gap: '6px',
            padding: '4px 8px', marginBottom: '6px', fontSize: '10px',
            color: 'var(--warning)', background: 'rgba(251, 191, 36, 0.08)',
            borderRadius: 'var(--radius-sm)',
          }}>
            <WifiOff size={10} /> Backend offline — responses are simulated
          </div>
        )}
        {uploadingFiles && (
          <div style={{
            display: 'flex', alignItems: 'center', gap: '6px',
            padding: '4px 8px', marginBottom: '6px', fontSize: '10px',
            color: 'var(--text-accent)', background: 'var(--accent-subtle)',
            borderRadius: 'var(--radius-sm)',
          }}>
            Indexing attached files...
          </div>
        )}
        <div className="chat-input-wrapper">
          <button
            className="title-bar__btn"
            onClick={() => fileInputRef.current?.click()}
            title="Attach file"
            style={{ flexShrink: 0 }}
          >
            <Paperclip size={14} />
          </button>
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept=".pdf,.docx,.txt,.md,.csv,.pptx,.py,.js,.ts,.json,.yaml,.yml,.html,.xml"
            style={{ display: 'none' }}
            onChange={handleAttachFile}
          />
          <button
            className="title-bar__btn"
            onClick={() => imageInputRef.current?.click()}
            title="Attach image"
            style={{ flexShrink: 0 }}
          >
            <Image size={14} />
          </button>
          <input
            ref={imageInputRef}
            type="file"
            multiple
            accept="image/*"
            style={{ display: 'none' }}
            onChange={handleAttachFile}
          />

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
            disabled={(!input.trim() && attachments.length === 0) || isGenerating || uploadingFiles}
          >
            <Send size={16} />
          </button>
        </div>
      </div>
    </div>
  );
}
