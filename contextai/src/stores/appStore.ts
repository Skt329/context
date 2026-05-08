import { create } from 'zustand';
import { persist } from 'zustand/middleware';

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
  dataUrl?: string;
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

  // Conversations (per-space, persistent)
  conversations: Conversation[];
  activeConversationId: string | null;

  // Derived helpers
  getActiveConversation: () => Conversation | undefined;
  getSpaceConversations: (spaceId: string) => Conversation[];

  // Chat actions
  isGenerating: boolean;
  setIsGenerating: (v: boolean) => void;
  addMessage: (msg: Message) => void;
  updateMessage: (id: string, content: string) => void;
  newChat: () => void;
  loadConversation: (conversationId: string) => void;
  deleteConversation: (conversationId: string) => void;

  // Settings
  providers: ProviderConfig[];
  toggleProvider: (id: string) => void;
  updateProviderKey: (id: string, key: string) => void;
  updateProviderModel: (id: string, model: string) => void;
  updateProviderApiBase: (id: string, apiBase: string) => void;
  setOllamaModels: (models: string[]) => void;

  // Context
  screenContext: string | null;
  setScreenContext: (ctx: string | null) => void;

  // Backend
  backendReady: boolean;
  setBackendReady: (v: boolean) => void;
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

function createConversation(spaceId: string): Conversation {
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

// ─── Store ───────────────────────────────────────────────────

export const useAppStore = create<AppState>()(
  persist(
    (set, get) => {
      // Create the initial conversation for the default space
      const initialConvo = createConversation(DEFAULT_SPACE_ID);

      return {
        // ── UI ──
        activeTab: 'chat',
        setActiveTab: (tab) => set({ activeTab: tab }),

        // ── Spaces ──
        spaces: defaultSpaces,
        activeSpaceId: DEFAULT_SPACE_ID,

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
            const newConvo = createConversation(id);
            set({
              activeSpaceId: id,
              activeConversationId: newConvo.id,
              conversations: [...state.conversations, newConvo],
            });
          }
        },

        addSpace: (space) => {
          const newConvo = createConversation(space.id);
          set((state) => ({
            spaces: [...state.spaces, space],
            conversations: [...state.conversations, newConvo],
          }));
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

        addMessage: (msg) => set((state) => {
          const convoId = state.activeConversationId;
          if (!convoId) return state;

          return {
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
          };
        }),

        updateMessage: (id, content) => set((state) => {
          const convoId = state.activeConversationId;
          if (!convoId) return state;

          return {
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
          };
        }),

        newChat: () => {
          const state = get();
          const spaceId = state.activeSpaceId;

          // If the current conversation is empty, just keep it
          const current = state.conversations.find((c) => c.id === state.activeConversationId);
          if (current && current.messages.length === 0) return;

          const newConvo = createConversation(spaceId);
          set({
            conversations: [...state.conversations, newConvo],
            activeConversationId: newConvo.id,
          });
        },

        loadConversation: (conversationId) => {
          const state = get();
          const convo = state.conversations.find((c) => c.id === conversationId);
          if (!convo) return;

          set({
            activeConversationId: conversationId,
            activeSpaceId: convo.spaceId,
            activeTab: 'chat',
          });
        },

        deleteConversation: (conversationId) => set((state) => {
          const filtered = state.conversations.filter((c) => c.id !== conversationId);
          let newActiveId = state.activeConversationId;

          if (state.activeConversationId === conversationId) {
            // Switch to the latest conversation in the same space, or create new
            const sameSpace = filtered.filter((c) => c.spaceId === state.activeSpaceId);
            if (sameSpace.length > 0) {
              newActiveId = sameSpace.sort(
                (a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime()
              )[0].id;
            } else {
              const newConvo = createConversation(state.activeSpaceId);
              filtered.push(newConvo);
              newActiveId = newConvo.id;
            }
          }

          return {
            conversations: filtered,
            activeConversationId: newActiveId,
          };
        }),

        // ── Settings ──
        providers: defaultProviders,
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
      };
    },
    {
      name: 'contextai-store',
      // Persist everything except ephemeral state
      partialize: (state) => ({
        spaces: state.spaces,
        activeSpaceId: state.activeSpaceId,
        conversations: state.conversations.map((c) => ({
          ...c,
          // Strip streaming flags on save
          messages: c.messages.map((m) => ({ ...m, isStreaming: false })),
        })),
        activeConversationId: state.activeConversationId,
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
        activeTab: 'chat' as Tab,
      }),
    },
  ),
);
