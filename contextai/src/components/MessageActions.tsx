/**
 * MessageActions — hover toolbar for chat messages.
 * Shows contextual actions: Copy, Delete, Regenerate (assistant-only), Edit (user-only).
 */

import { useState } from 'react';
import { Copy, Check, Trash2, RefreshCw, Pencil, ThumbsUp, ThumbsDown } from 'lucide-react';

interface Props {
  role: 'user' | 'assistant';
  content: string;
  isLast: boolean;
  isGenerating: boolean;
  onCopy: () => void;
  onDelete: () => void;
  onRegenerate?: () => void;
  onEdit?: () => void;
  onRate?: (rating: 'up' | 'down') => void;
}

export function MessageActions({
  role,
  content,
  isLast,
  isGenerating,
  onCopy,
  onDelete,
  onRegenerate,
  onEdit,
  onRate,
}: Props) {
  const [copied, setCopied] = useState(false);
  const [rated, setRated] = useState<'up' | 'down' | null>(null);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(content);
    setCopied(true);
    onCopy();
    setTimeout(() => setCopied(false), 2000);
  };

  const handleRate = (rating: 'up' | 'down') => {
    setRated(rating);
    onRate?.(rating);
  };

  return (
    <div className="message-actions">
      {/* Copy */}
      <button
        className="message-actions__btn"
        onClick={handleCopy}
        title="Copy message"
      >
        {copied ? <Check size={13} /> : <Copy size={13} />}
      </button>

      {/* Edit (user messages only) */}
      {role === 'user' && onEdit && (
        <button
          className="message-actions__btn"
          onClick={onEdit}
          title="Edit message"
          disabled={isGenerating}
        >
          <Pencil size={13} />
        </button>
      )}

      {/* Regenerate (last assistant message only) */}
      {role === 'assistant' && isLast && onRegenerate && (
        <button
          className="message-actions__btn"
          onClick={onRegenerate}
          title="Regenerate response"
          disabled={isGenerating}
        >
          <RefreshCw size={13} />
        </button>
      )}

      {/* Rate (assistant messages) */}
      {role === 'assistant' && onRate && (
        <>
          <button
            className={`message-actions__btn ${rated === 'up' ? 'message-actions__btn--active' : ''}`}
            onClick={() => handleRate('up')}
            title="Good response"
          >
            <ThumbsUp size={13} />
          </button>
          <button
            className={`message-actions__btn ${rated === 'down' ? 'message-actions__btn--active-bad' : ''}`}
            onClick={() => handleRate('down')}
            title="Bad response"
          >
            <ThumbsDown size={13} />
          </button>
        </>
      )}

      {/* Delete */}
      <button
        className="message-actions__btn message-actions__btn--danger"
        onClick={onDelete}
        title="Delete message"
        disabled={isGenerating}
      >
        <Trash2 size={13} />
      </button>
    </div>
  );
}
