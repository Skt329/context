/**
 * ContextAI Backend API Client
 * Connects the React frontend to the FastAPI backend on localhost:8742
 */

const BASE_URL = 'http://localhost:8742/api';

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
      }),
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
    onError(err instanceof Error ? err.message : 'Connection failed');
    onDone();
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
  update: { enabled?: boolean; api_key?: string; model?: string },
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

/** Capture screen context from the backend */
export async function captureContext(): Promise<{ method: string; text: string; length: number } | null> {
  try {
    const res = await fetch(`${BASE_URL}/context/capture`, { method: 'POST' });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
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
