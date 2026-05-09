import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import {
  listConversations,
  getConversation,
  createConversation as apiCreateConversation,
  updateConversation as apiUpdateConversation,
  deleteConversation as apiDeleteConversation,
  listSpaces,
  getProviderConfigs,
} from '../lib/api';

// ─── Types ───────────────────────────────────────────────────

export type Tab = 'chat' | 'spaces' | 'history' | 'settings';

export interface Space {
  id: string;
  name: string;
  icon: string;
  description: string;
  fileCount: number;
  lastUsed: string | null;
  createdAt: string;
  textContext?: string;
}

export interface ChatAttachment {
  name: string;
  type: 'file' | 'image';
  size: number;
  dataUrl?: string; // Ephemeral: used for preview before upload, stripped on persist
  url?: string; // Persistent: backend-served URL after upload (/api/attachments/{filename})
  indexed?: boolean; // Whether the file was indexed into RAG
}

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  isStreaming?: boolean;
  attachments?: ChatAttachment[];
}

export interface Conversation {
  id: string;
  spaceId: string;
  title: string;
  messages: Message[];
  createdAt: string;
  updatedAt: string;
}

export interface ProviderConfig {
  id: string;
  name: string;
  enabled: boolean;
  apiKey: string;
  model: string;
  color: string;
  apiBase?: string;
  availableModels?: string[];
}

// ─── State Interface ─────────────────────────────────────────

interface AppState {
  // UI
  activeTab: Tab;
  setActiveTab: (tab: Tab) => void;

  // Spaces
  spaces: Space[];
  activeSpaceId: string;
  setActiveSpace: (id: string) => void;
  addSpace: (space: Space) => void;
  deleteSpace: (id: string) => void;
  updateSpaceTextContext: (id: string, textContext: string) => void;
  setSpaces: (spaces: Space[]) => void;

  // Conversations (per-space, backend-persistent)
  conversations: Conversation[];
  activeConversationId: string | null;
  setConversations: (convos: Conversation[]) => void;

  // Derived helpers
  getActiveConversation: () => Conversation | undefined;
  getSpaceConversations: (spaceId: string) => Conversation[];

  // Chat actions
  isGenerating: boolean;
  setIsGenerating: (v: boolean) => void;
  abortController: AbortController | null;
  setAbortController: (ctrl: AbortController | null) => void;
  addMessage: (msg: Message) => void;
  updateMessage: (id: string, content: string) => void;
  deleteMessage: (messageId: string) => void;
  regenerateLastResponse: () => void;
  stopGeneration: () => void;
  setConversationTitle: (convoId: string, title: string) => void;
  newChat: () => void;
  loadConversation: (conversationId: string) => void;
  deleteConversation: (conversationId: string) => void;

  // Settings — providers stay in Zustand for reactivity but are synced to backend
  providers: ProviderConfig[];
  toggleProvider: (id: string) => void;
  updateProviderKey: (id: string, key: string) => void;
  updateProviderModel: (id: string, model: string) => void;
  updateProviderApiBase: (id: string, apiBase: string) => void;
  setOllamaModels: (models: string[]) => void;
  setProviders: (providers: ProviderConfig[]) => void;

  // Context
  screenContext: string | null;
  setScreenContext: (ctx: string | null) => void;

  // Backend
  backendReady: boolean;
  setBackendReady: (v: boolean) => void;

  // Hydration
  hydrateFromBackend: () => Promise<void>;
  _hydrated: boolean;
}

// ─── Defaults ────────────────────────────────────────────────

const defaultProviders: ProviderConfig[] = [
  { id: 'ollama', name: 'Ollama (Local)', enabled: true, apiKey: '', model: '', color: '#ffffff', availableModels: [] },
  { id: 'openai', name: 'OpenAI', enabled: false, apiKey: '', model: 'gpt-4o', color: '#10a37f' },
  { id: 'anthropic', name: 'Anthropic', enabled: false, apiKey: '', model: 'claude-sonnet-4-5-20250514', color: '#d4a574' },
  { id: 'gemini', name: 'Google Gemini', enabled: false, apiKey: '', model: 'gemini-2.0-flash', color: '#4285f4' },
  { id: 'mistral', name: 'Mistral', enabled: false, apiKey: '', model: 'mistral-large-latest', color: '#ff7000' },
  { id: 'deepseek', name: 'DeepSeek', enabled: false, apiKey: '', model: 'deepseek-chat', color: '#0066ff' },
  { id: 'azure', name: 'Azure OpenAI', enabled: false, apiKey: '', model: 'gpt-4.1-mini', color: '#0078d4', apiBase: '' },
];

const DEFAULT_SPACE_ID = 'default';

const defaultSpaces: Space[] = [
  {
    id: DEFAULT_SPACE_ID,
    name: 'General',
    icon: '🌐',
    description: 'Default workspace for general tasks',
    fileCount: 0,
    lastUsed: new Date().toISOString(),
    createdAt: new Date().toISOString(),
  },
];

function createLocalConversation(spaceId: string): Conversation {
  const now = new Date().toISOString();
  return {
    id: crypto.randomUUID(),
    spaceId,
    title: 'New Chat',
    messages: [],
    createdAt: now,
    updatedAt: now,
  };
}

function deriveTitle(messages: Message[]): string {
  const firstUserMsg = messages.find((m) => m.role === 'user');
  if (!firstUserMsg) return 'New Chat';
  const text = firstUserMsg.content.replace(/\[Attached:.*?\]/g, '').trim();
  return text.slice(0, 80) || 'New Chat';
}


// ─── Debounced Backend Sync ──────────────────────────────────

const _syncTimers: Record<string, ReturnType<typeof setTimeout>> = {};

/**
 * Debounced write-through to backend. Called after every state mutation
 * that changes a conversation. Batches rapid updates (e.g., streaming tokens)
 * into a single API call.
 */
function debouncedSyncConversation(convoId: string, delayMs = 1500) {
  if (_syncTimers[convoId]) clearTimeout(_syncTimers[convoId]);
  _syncTimers[convoId] = setTimeout(() => {
    const state = useAppStore.getState();
    const convo = state.conversations.find((c) => c.id === convoId);
    if (!convo || !state.backendReady) return;

    // Strip transient fields before syncing
    const cleanMessages = convo.messages.map((m) => ({
      id: m.id,
      role: m.role,
      content: m.content,
      timestamp: m.timestamp,
      attachments: m.attachments?.map((a) => ({
        name: a.name,
        type: a.type,
        size: a.size,
        indexed: a.indexed,
        url: a.url, // Persist backend-served URL
        // dataUrl intentionally stripped — base64 is NOT persisted to backend
      })),
    }));

    apiUpdateConversation(convoId, {
      title: convo.title,
      messages: cleanMessages,
    }).catch((err) => {
      console.error(`Failed to sync conversation ${convoId}:`, err);
    });

    delete _syncTimers[convoId];
  }, delayMs);
}


// ─── Store ───────────────────────────────────────────────────

/**
 * Flush all pending debounced syncs immediately.
 * Called on beforeunload to prevent data loss when the app closes
 * during the debounce window.
 */
function flushAllPendingSyncs() {
  const pendingIds = Object.keys(_syncTimers);
  if (pendingIds.length === 0) return;

  for (const convoId of pendingIds) {
    clearTimeout(_syncTimers[convoId]);
    delete _syncTimers[convoId];

    const state = useAppStore.getState();
    const convo = state.conversations.find((c) => c.id === convoId);
    if (!convo || !state.backendReady) continue;

    const cleanMessages = convo.messages.map((m) => ({
      id: m.id,
      role: m.role,
      content: m.content,
      timestamp: m.timestamp,
      attachments: m.attachments?.map((a) => ({
        name: a.name,
        type: a.type,
        size: a.size,
        indexed: a.indexed,
        url: a.url,
      })),
    }));

    // Use sendBeacon for reliability during page unload
    const payload = JSON.stringify({ title: convo.title, messages: cleanMessages });
    const url = `http://127.0.0.1:8742/api/conversations/${convoId}`;
    const blob = new Blob([payload], { type: 'application/json' });
    navigator.sendBeacon(url, blob);
  }
}

// Register flush on page unload
if (typeof window !== 'undefined') {
  window.addEventListener('beforeunload', flushAllPendingSyncs);
}



export const useAppStore = create<AppState>()(
  persist(
    (set, get) => {
      // Create the initial conversation for the default space
      const initialConvo = createLocalConversation(DEFAULT_SPACE_ID);

      return {
        // ── UI ──
        activeTab: 'chat',
        setActiveTab: (tab) => set({ activeTab: tab }),

        // ── Spaces ──
        spaces: defaultSpaces,
        activeSpaceId: DEFAULT_SPACE_ID,
        setSpaces: (spaces) => set({ spaces }),

        setActiveSpace: (id) => {
          const state = get();
          if (state.activeSpaceId === id) return;

          // Find or create a conversation for the target space
          const spaceConvos = state.conversations.filter((c) => c.spaceId === id);
          const latestConvo = spaceConvos.sort(
            (a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime()
          )[0];

          if (latestConvo) {
            set({ activeSpaceId: id, activeConversationId: latestConvo.id });
          } else {
            // Auto-create a conversation for this space
            const newConvo = createLocalConversation(id);
            set({
              activeSpaceId: id,
              activeConversationId: newConvo.id,
              conversations: [...state.conversations, newConvo],
            });
            // Sync to backend
            if (state.backendReady) {
              apiCreateConversation(id, 'New Chat').then((remote) => {
                if (remote) {
                  // Update local ID to match backend
                  set((s) => ({
                    conversations: s.conversations.map((c) =>
                      c.id === newConvo.id ? { ...c, id: remote.id } : c
                    ),
                    activeConversationId: s.activeConversationId === newConvo.id ? remote.id : s.activeConversationId,
                  }));
                }
              });
            }
          }
        },

        addSpace: (space) => {
          const newConvo = createLocalConversation(space.id);
          set((s) => ({
            spaces: [...s.spaces, space],
            conversations: [...s.conversations, newConvo],
          }));
          // Backend sync for new conversation
          const currentState = get();
          if (currentState.backendReady) {
            apiCreateConversation(space.id, 'New Chat');
          }
        },

        deleteSpace: (id) => set((state) => {
          const remaining = state.spaces.filter((s) => s.id !== id);
          const newActiveSpace = state.activeSpaceId === id
            ? (remaining[0]?.id ?? DEFAULT_SPACE_ID)
            : state.activeSpaceId;

          // Remove all conversations belonging to the deleted space
          const filteredConvos = state.conversations.filter((c) => c.spaceId !== id);

          // Ensure there's an active conversation for the new active space
          let activeConvoId = state.activeConversationId;
          const deleted = !filteredConvos.find((c) => c.id === activeConvoId);
          if (deleted) {
            const fallback = filteredConvos.find((c) => c.spaceId === newActiveSpace);
            activeConvoId = fallback?.id ?? null;
          }

          return {
            spaces: remaining,
            activeSpaceId: newActiveSpace,
            conversations: filteredConvos,
            activeConversationId: activeConvoId,
          };
        }),

        updateSpaceTextContext: (id, textContext) => set((state) => ({
          spaces: state.spaces.map((s) => s.id === id ? { ...s, textContext } : s),
        })),

        // ── Conversations ──
        conversations: [initialConvo],
        activeConversationId: initialConvo.id,
        setConversations: (convos) => set({ conversations: convos }),

        getActiveConversation: () => {
          const state = get();
          return state.conversations.find((c) => c.id === state.activeConversationId);
        },

        getSpaceConversations: (spaceId) => {
          return get().conversations
            .filter((c) => c.spaceId === spaceId)
            .sort((a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime());
        },

        // ── Chat Actions ──
        isGenerating: false,
        setIsGenerating: (v) => set({ isGenerating: v }),
        abortController: null,
        setAbortController: (ctrl) => set({ abortController: ctrl }),

        stopGeneration: () => {
          const state = get();
          if (state.abortController) {
            state.abortController.abort();
            set({ abortController: null, isGenerating: false });
          }
        },

        addMessage: (msg) => {
          const state = get();
          const convoId = state.activeConversationId;
          if (!convoId) return;

          set((state) => ({
            conversations: state.conversations.map((c) => {
              if (c.id !== convoId) return c;
              const updatedMessages = [...c.messages, msg];
              return {
                ...c,
                messages: updatedMessages,
                title: deriveTitle(updatedMessages),
                updatedAt: new Date().toISOString(),
              };
            }),
          }));

          // Debounced write-through to backend
          debouncedSyncConversation(convoId);
        },

        updateMessage: (id, content) => {
          const state = get();
          const convoId = state.activeConversationId;
          if (!convoId) return;

          set((state) => ({
            conversations: state.conversations.map((c) => {
              if (c.id !== convoId) return c;
              return {
                ...c,
                messages: c.messages.map((m) =>
                  m.id === id ? { ...m, content, isStreaming: false } : m
                ),
                updatedAt: new Date().toISOString(),
              };
            }),
          }));

          // Debounced write-through — streaming will batch many updates
          debouncedSyncConversation(convoId, 2000);
        },

        deleteMessage: (messageId) => {
          const state = get();
          const convoId = state.activeConversationId;
          if (!convoId) return;

          set((state) => ({
            conversations: state.conversations.map((c) => {
              if (c.id !== convoId) return c;
              return {
                ...c,
                messages: c.messages.filter((m) => m.id !== messageId),
                updatedAt: new Date().toISOString(),
              };
            }),
          }));

          debouncedSyncConversation(convoId);
        },

        regenerateLastResponse: () => {
          const state = get();
          const convoId = state.activeConversationId;
          if (!convoId || state.isGenerating) return;

          const convo = state.conversations.find((c) => c.id === convoId);
          if (!convo || convo.messages.length < 2) return;

          // Remove the last assistant message
          const lastMsg = convo.messages[convo.messages.length - 1];
          if (lastMsg.role !== 'assistant') return;

          set((s) => ({
            conversations: s.conversations.map((c) => {
              if (c.id !== convoId) return c;
              return {
                ...c,
                messages: c.messages.filter((m) => m.id !== lastMsg.id),
                updatedAt: new Date().toISOString(),
              };
            }),
          }));
          // ChatView will detect the regenerate trigger via a callback
        },

        setConversationTitle: (convoId, title) => {
          set((state) => ({
            conversations: state.conversations.map((c) =>
              c.id === convoId ? { ...c, title, updatedAt: new Date().toISOString() } : c
            ),
          }));
          debouncedSyncConversation(convoId);
        },

        newChat: () => {
          const state = get();
          const spaceId = state.activeSpaceId;

          // If the current conversation is empty, just keep it
          const current = state.conversations.find((c) => c.id === state.activeConversationId);
          if (current && current.messages.length === 0) return;

          const newConvo = createLocalConversation(spaceId);
          set({
            conversations: [...state.conversations, newConvo],
            activeConversationId: newConvo.id,
          });

          // Create on backend
          if (state.backendReady) {
            apiCreateConversation(spaceId, 'New Chat').then((remote) => {
              if (remote) {
                set((s) => ({
                  conversations: s.conversations.map((c) =>
                    c.id === newConvo.id ? { ...c, id: remote.id } : c
                  ),
                  activeConversationId: s.activeConversationId === newConvo.id ? remote.id : s.activeConversationId,
                }));
              }
            });
          }
        },

        loadConversation: (conversationId) => {
          const state = get();
          const convo = state.conversations.find((c) => c.id === conversationId);
          if (!convo) {
            // Try loading from backend if not in local state
            if (state.backendReady) {
              getConversation(conversationId).then((remote) => {
                if (remote) {
                  set((s) => ({
                    conversations: [...s.conversations, remote as unknown as Conversation],
                    activeConversationId: conversationId,
                    activeSpaceId: remote.spaceId,
                    activeTab: 'chat',
                  }));
                }
              });
            }
            return;
          }

          set({
            activeConversationId: conversationId,
            activeSpaceId: convo.spaceId,
            activeTab: 'chat',
          });
        },

        deleteConversation: (conversationId) => {
          // Fire backend delete (non-blocking)
          const state = get();
          if (state.backendReady) {
            apiDeleteConversation(conversationId);
          }

          set((state) => {
            const filtered = state.conversations.filter((c) => c.id !== conversationId);
            let newActiveId = state.activeConversationId;

            if (state.activeConversationId === conversationId) {
              const sameSpace = filtered.filter((c) => c.spaceId === state.activeSpaceId);
              if (sameSpace.length > 0) {
                newActiveId = sameSpace.sort(
                  (a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime()
                )[0].id;
              } else {
                const newConvo = createLocalConversation(state.activeSpaceId);
                filtered.push(newConvo);
                newActiveId = newConvo.id;
              }
            }

            return {
              conversations: filtered,
              activeConversationId: newActiveId,
            };
          });
        },

        // ── Settings ──
        providers: defaultProviders,
        setProviders: (providers) => set({ providers }),
        toggleProvider: (id) => set((state) => ({
          providers: state.providers.map((p) => p.id === id ? { ...p, enabled: !p.enabled } : p),
        })),
        updateProviderKey: (id, key) => set((state) => ({
          providers: state.providers.map((p) => p.id === id ? { ...p, apiKey: key } : p),
        })),
        updateProviderModel: (id, model) => set((state) => ({
          providers: state.providers.map((p) => p.id === id ? { ...p, model } : p),
        })),
        updateProviderApiBase: (id, apiBase) => set((state) => ({
          providers: state.providers.map((p) => p.id === id ? { ...p, apiBase } : p),
        })),
        setOllamaModels: (models) => set((state) => ({
          providers: state.providers.map((p) => {
            if (p.id !== 'ollama') return p;
            const currentModelValid = models.includes(p.model);
            return {
              ...p,
              availableModels: models,
              model: currentModelValid ? p.model : (models[0] || ''),
            };
          }),
        })),

        // ── Context ──
        screenContext: null,
        setScreenContext: (ctx) => set({ screenContext: ctx }),

        // ── Backend ──
        backendReady: false,
        setBackendReady: (v) => set({ backendReady: v }),

        // ── Hydration from backend ──
        _hydrated: false,
        hydrateFromBackend: async () => {
          const state = get();
          if (state._hydrated) return;

          try {
            // 1. Hydrate spaces from backend
            const spacesResult = await listSpaces();
            if (spacesResult?.spaces && spacesResult.spaces.length > 0) {
              const hydrated: Space[] = spacesResult.spaces.map((s: any) => ({
                id: s.id,
                name: s.name,
                icon: s.icon || '📁',
                description: s.description || '',
                fileCount: s.file_count || 0,
                lastUsed: s.updated_at || null,
                createdAt: s.created_at || new Date().toISOString(),
                textContext: s.text_context,
              }));
              set({ spaces: hydrated });
            }

            // 2. Hydrate conversations from backend
            const convos = await listConversations();
            if (convos.length > 0) {
              // Load full messages for each conversation
              const fullConvos: Conversation[] = [];
              for (const summary of convos) {
                const full = await getConversation(summary.id);
                if (full) {
                  fullConvos.push({
                    id: full.id,
                    spaceId: full.spaceId,
                    title: full.title,
                    messages: (full.messages || []).map((m) => ({
                      id: m.id,
                      role: m.role as 'user' | 'assistant',
                      content: m.content,
                      timestamp: m.timestamp,
                      attachments: m.attachments as ChatAttachment[] | undefined,
                    })),
                    createdAt: full.createdAt,
                    updatedAt: full.updatedAt,
                  });
                }
              }

              if (fullConvos.length > 0) {
                const activeSpace = get().activeSpaceId;
                const spaceConvos = fullConvos.filter((c) => c.spaceId === activeSpace);
                const latest = spaceConvos.sort(
                  (a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime()
                )[0];

                set({
                  conversations: fullConvos,
                  activeConversationId: latest?.id || fullConvos[0].id,
                });
              }
            }
            // 3. Hydrate provider API keys from backend settings.json
            const backendProviders = await getProviderConfigs();
            if (backendProviders) {
              const currentProviders = get().providers;
              const mergedProviders = currentProviders.map((p) => {
                const backend = (backendProviders as Record<string, any>)[p.id];
                if (!backend) return p;
                return {
                  ...p,
                  enabled: backend.enabled ?? p.enabled,
                  apiKey: backend.has_key ? (p.apiKey || '••••••') : p.apiKey,
                  model: backend.model || p.model,
                  apiBase: backend.api_base || p.apiBase,
                };
              });
              set({ providers: mergedProviders });
            }
          } catch (err) {
            console.error('Failed to hydrate from backend:', err);
          }

          set({ _hydrated: true });
        },
      };
    },
    {
      name: 'contextai-store',
      // Only persist UI preferences — NOT data (that lives on backend)
      partialize: (state) => ({
        activeSpaceId: state.activeSpaceId,
        activeTab: state.activeTab,
        activeConversationId: state.activeConversationId,
        // Keep providers in localStorage for offline/fallback, but keys are
        // synced to backend on connect. This is acceptable since settings.json
        // is the canonical store.
        providers: state.providers,
      }),
      // Merge hydrated state with defaults for transient fields
      merge: (persisted: any, current) => ({
        ...current,
        ...(persisted as Partial<AppState>),
        // Always reset ephemeral state
        isGenerating: false,
        backendReady: false,
        screenContext: null,
        _hydrated: false,
        // Ensure conversations start empty — hydrated from backend
        conversations: current.conversations,
      }),
    },
  ),
);
