/**
 * ContextAI Backend API Client
 * Connects the React frontend to the FastAPI backend on localhost:8742
 */

const BASE_URL = 'http://127.0.0.1:8742/api';

/**
 * Fetch with automatic retry and exponential backoff.
 * Used for non-streaming API calls to handle transient failures.
 */
async function fetchWithRetry(
  url: string,
  options: RequestInit,
  retries = 3,
  backoffMs = 500,
): Promise<Response> {
  for (let attempt = 0; attempt < retries; attempt++) {
    try {
      const res = await fetch(url, options);
      if (res.ok || res.status < 500) return res;
      // Server error — retry
      if (attempt < retries - 1) {
        await new Promise((r) => setTimeout(r, backoffMs * (attempt + 1)));
      }
    } catch (error) {
      if (attempt === retries - 1) throw error;
      await new Promise((r) => setTimeout(r, backoffMs * (attempt + 1)));
    }
  }
  throw new Error(`Request failed after ${retries} retries: ${url}`);
}

/** Check if the backend is running */
export async function checkHealth(): Promise<{ status: string; version: string } | null> {
  try {
    const res = await fetch(`${BASE_URL}/health`, { signal: AbortSignal.timeout(2000) });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

/** Stream a chat response from the backend via SSE */
export async function streamChat(
  message: string,
  spaceId: string,
  screenContext: string | null,
  onChunk: (content: string) => void,
  onError: (error: string) => void,
  onDone: () => void,
  textContext?: string | null,
  images?: { data_url: string; name: string }[],
  history?: { role: string; content: string }[],
  signal?: AbortSignal,
): Promise<void> {
  try {
    const res = await fetch(`${BASE_URL}/chat/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message,
        space_id: spaceId,
        screen_context: screenContext,
        text_context: textContext || null,
        images: images && images.length > 0 ? images : null,
        history: history && history.length > 0 ? history : null,
      }),
      signal,
    });

    if (!res.ok) {
      onError(`Backend returned ${res.status}`);
      onDone();
      return;
    }

    const reader = res.body?.getReader();
    if (!reader) {
      onError('No response body');
      onDone();
      return;
    }

    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = line.slice(6).trim();
          if (data === '[DONE]') {
            onDone();
            return;
          }
          try {
            const parsed = JSON.parse(data);
            if (parsed.content) {
              onChunk(parsed.content);
            }
            if (parsed.error) {
              onError(parsed.error);
            }
          } catch {
            // Non-JSON data, skip
          }
        }
      }
    }
    onDone();
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') {
      onDone();
      return;
    }
    onError(err instanceof Error ? err.message : 'Connection failed');
    onDone();
  }
}

/** Generate an auto-title for a conversation using a fast LLM call */
export async function generateTitle(
  message: string,
): Promise<string | null> {
  try {
    const res = await fetch(`${BASE_URL}/chat/generate-title`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message }),
      signal: AbortSignal.timeout(8000),
    });
    if (!res.ok) return null;
    const data = await res.json();
    return data.title || null;
  } catch {
    return null;
  }
}

/** Rate a message for procedural memory */
export async function rateMessage(messageId: string, rating: number): Promise<boolean> {
  try {
    const res = await fetch(`${BASE_URL}/chat/rate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message_id: messageId, rating }),
    });
    return res.ok;
  } catch {
    return false;
  }
}

/** Sync provider configs to the backend */
export async function syncProviders(providers: Record<string, unknown>): Promise<boolean> {
  try {
    const res = await fetch(`${BASE_URL}/settings/providers/sync`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ providers }),
    });
    return res.ok;
  } catch {
    return false;
  }
}

/** Update a single provider config */
export async function updateProvider(
  providerId: string,
  update: { enabled?: boolean; api_key?: string; model?: string; api_base?: string },
): Promise<boolean> {
  try {
    const res = await fetch(`${BASE_URL}/settings/providers/${providerId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(update),
    });
    return res.ok;
  } catch {
    return false;
  }
}

/** Test a provider connection */
export async function testProvider(providerId: string): Promise<{ status: string; message?: string }> {
  try {
    const res = await fetch(`${BASE_URL}/settings/providers/${providerId}/test`, {
      method: 'POST',
    });
    return await res.json();
  } catch {
    return { status: 'error', message: 'Backend not reachable' };
  }
}

/** Fetch installed Ollama models */
export interface OllamaModel {
  name: string;
  size: number;
  family: string;
  parameter_size: string;
  quantization: string;
}

export async function fetchOllamaModels(): Promise<{ available: boolean; models: OllamaModel[] }> {
  try {
    const res = await fetch(`${BASE_URL}/settings/ollama/models`);
    if (!res.ok) return { available: false, models: [] };
    return await res.json();
  } catch {
    return { available: false, models: [] };
  }
}

/** Check Ollama status */
export async function checkOllamaStatus(): Promise<{ running: boolean; model_count: number }> {
  try {
    const res = await fetch(`${BASE_URL}/settings/ollama/status`);
    if (!res.ok) return { running: false, model_count: 0 };
    return await res.json();
  } catch {
    return { running: false, model_count: 0 };
  }
}




/** List spaces from the backend */
export async function listSpaces(): Promise<{ spaces: any[] } | null> {
  try {
    const res = await fetch(`${BASE_URL}/spaces`);
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

/** Create a space on the backend */
export async function createSpace(name: string, icon: string, description: string): Promise<any | null> {
  try {
    const res = await fetch(`${BASE_URL}/spaces`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, icon, description }),
    });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

/** Update a space on the backend */
export async function updateSpace(
  spaceId: string,
  update: { name?: string; icon?: string; description?: string },
): Promise<boolean> {
  try {
    const res = await fetch(`${BASE_URL}/spaces/${spaceId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(update),
    });
    return res.ok;
  } catch {
    return false;
  }
}

/** Get the actual file count for a space from disk */
export async function getFileCount(spaceId: string): Promise<number> {
  try {
    const res = await fetch(`${BASE_URL}/spaces/${spaceId}/file-count`);
    if (!res.ok) return 0;
    const data = await res.json();
    return data.count || 0;
  } catch {
    return 0;
  }
}

/** Upload a file to a space */
export async function uploadFile(spaceId: string, file: File): Promise<any | null> {
  try {
    const formData = new FormData();
    formData.append('file', file);
    const res = await fetch(`${BASE_URL}/files/${spaceId}/upload`, {
      method: 'POST',
      body: formData,
    });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

/** List files in a space */
export async function listFiles(spaceId: string): Promise<{ files: any[] } | null> {
  try {
    const res = await fetch(`${BASE_URL}/files/${spaceId}/files`);
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}


// ─── Memory API ──────────────────────────────────────────────

/** Get global memory content */
export async function getGlobalMemory(): Promise<{ content: string } | null> {
  try {
    const res = await fetch(`${BASE_URL}/memory/global`);
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

/** Update global memory content */
export async function setGlobalMemory(content: string): Promise<boolean> {
  try {
    const res = await fetch(`${BASE_URL}/memory/global`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content }),
    });
    return res.ok;
  } catch {
    return false;
  }
}

/** Get space-specific memory */
export async function getSpaceMemory(spaceId: string): Promise<{ content: string } | null> {
  try {
    const res = await fetch(`${BASE_URL}/memory/space/${spaceId}`);
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

/** Update space memory */
export async function setSpaceMemory(spaceId: string, content: string): Promise<boolean> {
  try {
    const res = await fetch(`${BASE_URL}/memory/space/${spaceId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content }),
    });
    return res.ok;
  } catch {
    return false;
  }
}

/** Get user profile (procedural memory) for a space */
export async function getUserProfile(spaceId: string): Promise<{ content: string } | null> {
  try {
    const res = await fetch(`${BASE_URL}/memory/profile/${spaceId}`);
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

/** Extract facts from a conversation and save to memory */
export async function extractMemoryFromChat(
  messages: { role: string; content: string }[],
  spaceId: string,
): Promise<{ facts_extracted: number } | null> {
  try {
    const res = await fetch(`${BASE_URL}/memory/extract`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ messages, space_id: spaceId }),
    });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}


// ─── Screen Context API ──────────────────────────────────────

/** Capture screen context (UIA / clipboard / screenshot) */
export async function captureScreenContext(): Promise<{
  method: string;
  text: string;
  length: number;
  window_title: string;
} | null> {
  try {
    const res = await fetch(`${BASE_URL}/context/capture`, { method: 'POST' });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

/** Get a preview of available screen context */
export async function previewScreenContext(): Promise<{
  available: boolean;
  method?: string;
  preview?: string;
  length?: number;
} | null> {
  try {
    const res = await fetch(`${BASE_URL}/context/preview`);
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}


// ─── Conversations API ───────────────────────────────────────

export interface ConversationSummary {
  id: string;
  spaceId: string;
  title: string;
  messageCount: number;
  createdAt: string;
  updatedAt: string;
  lastMessage: string | null;
}

export interface ConversationFull {
  id: string;
  spaceId: string;
  title: string;
  messages: {
    id: string;
    role: string;
    content: string;
    timestamp: string;
    attachments?: { type: string; name: string; dataUrl?: string; url?: string }[];
  }[];
  createdAt: string;
  updatedAt: string;
}

/** List conversations (optionally filtered by space) */
export async function listConversations(spaceId?: string): Promise<ConversationSummary[]> {
  try {
    const url = spaceId
      ? `${BASE_URL}/conversations?space_id=${encodeURIComponent(spaceId)}`
      : `${BASE_URL}/conversations`;
    const res = await fetch(url);
    if (!res.ok) return [];
    const data = await res.json();
    return data.conversations || [];
  } catch {
    return [];
  }
}

/** Get a single conversation with full messages */
export async function getConversation(convoId: string): Promise<ConversationFull | null> {
  try {
    const res = await fetch(`${BASE_URL}/conversations/${convoId}`);
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

/** Create a new conversation */
export async function createConversation(
  spaceId: string,
  title: string = 'New Chat',
): Promise<ConversationFull | null> {
  try {
    const res = await fetch(`${BASE_URL}/conversations`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ space_id: spaceId, title }),
    });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

/** Update a conversation (title and/or messages) */
export async function updateConversation(
  convoId: string,
  update: {
    title?: string;
    messages?: { id: string; role: string; content: string; timestamp: string; attachments?: unknown[] }[];
  },
): Promise<boolean> {
  try {
    const res = await fetch(`${BASE_URL}/conversations/${convoId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(update),
    });
    return res.ok;
  } catch {
    return false;
  }
}

/** Delete a conversation */
export async function deleteConversation(convoId: string): Promise<boolean> {
  try {
    const res = await fetch(`${BASE_URL}/conversations/${convoId}`, {
      method: 'DELETE',
    });
    return res.ok;
  } catch {
    return false;
  }
}


// ─── Provider Configs from Backend ───────────────────────────

/** Get all provider configurations from backend settings */
export async function getProviderConfigs(): Promise<Record<string, unknown> | null> {
  try {
    const res = await fetch(`${BASE_URL}/settings/providers`);
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}


// ─── Attachments API ─────────────────────────────────────────

export interface AttachmentResult {
  id: string;
  filename: string;
  url: string; // relative: /api/attachments/{filename}
  mime_type: string;
  size: number;
  original_name?: string;
}

/** Upload a single base64 image attachment to backend storage */
export async function uploadAttachment(
  dataUrl: string,
  name?: string,
): Promise<AttachmentResult | null> {
  try {
    const res = await fetch(`${BASE_URL}/attachments/upload`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ data_url: dataUrl, name: name || null }),
    });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

/** Upload multiple base64 image attachments in one request */
export async function uploadAttachmentsBatch(
  items: { data_url: string; name?: string }[],
): Promise<AttachmentResult[]> {
  try {
    const res = await fetch(`${BASE_URL}/attachments/upload/batch`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(items.map((i) => ({ data_url: i.data_url, name: i.name || null }))),
    });
    if (!res.ok) return [];
    const data = await res.json();
    return data.attachments || [];
  } catch {
    return [];
  }
}

/** Convert a relative attachment path to a full backend URL */
export function attachmentUrl(relativeUrl: string): string {
  if (relativeUrl.startsWith('http')) return relativeUrl;
  if (relativeUrl.startsWith('data:')) return relativeUrl;
  // relativeUrl is like "/api/attachments/{filename}"
  return `http://127.0.0.1:8742${relativeUrl}`;
}
