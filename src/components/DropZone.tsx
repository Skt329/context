import { useState, useCallback, type DragEvent, type ReactNode } from 'react';
import { Upload } from 'lucide-react';

interface DropZoneProps {
  onFilesDropped: (files: File[]) => void;
  accept?: string[];
  maxSize?: number;
  children: ReactNode;
  className?: string;
}

/**
 * Wraps any container with drag-and-drop file upload.
 * Shows an overlay when dragging files over.
 */
export function DropZone({
  onFilesDropped,
  accept,
  maxSize = 50 * 1024 * 1024,
  children,
  className = '',
}: DropZoneProps) {
  const [isDragging, setIsDragging] = useState(false);

  const handleDragEnter = useCallback((e: DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  }, []);

  const handleDragOver = useCallback((e: DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  }, []);

  const handleDragLeave = useCallback((e: DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    // Only leave if we're exiting the drop zone entirely
    if (e.currentTarget === e.target) {
      setIsDragging(false);
    }
  }, []);

  const handleDrop = useCallback(
    (e: DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      setIsDragging(false);

      const files = Array.from(e.dataTransfer.files);
      const validFiles = files.filter((f) => {
        if (f.size > maxSize) return false;
        if (accept && accept.length > 0) {
          const ext = '.' + f.name.split('.').pop()?.toLowerCase();
          return accept.some((a) => a === ext || f.type.startsWith(a.replace('*', '')));
        }
        return true;
      });

      if (validFiles.length > 0) {
        onFilesDropped(validFiles);
      }
    },
    [onFilesDropped, maxSize, accept],
  );

  return (
    <div
      className={`drop-zone ${className}`}
      onDragEnter={handleDragEnter}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      style={{ position: 'relative' }}
    >
      {children}
      {isDragging && (
        <div
          className="drop-zone-overlay"
          style={{
            position: 'absolute',
            inset: 0,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '8px',
            background: 'rgba(var(--accent-rgb, 99, 102, 241), 0.12)',
            border: '2px dashed var(--accent)',
            borderRadius: 'var(--radius-md)',
            zIndex: 50,
            backdropFilter: 'blur(4px)',
            color: 'var(--accent)',
            fontSize: '13px',
            fontWeight: 500,
            pointerEvents: 'none',
          }}
        >
          <Upload size={24} />
          <span>Drop files here to upload</span>
        </div>
      )}
    </div>
  );
}
