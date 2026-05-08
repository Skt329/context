import { create } from 'zustand';

export type Tab = 'chat' | 'spaces' | 'history' | 'settings';

export interface Space {
  id: string;
  name: string;
  icon: string;
  description: string;
  fileCount: number;
  lastUsed: string | null;
  createdAt: string;
}

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  isStreaming?: boolean;
}

export interface ProviderConfig {
  id: string;
  name: string;
  enabled: boolean;
  apiKey: string;
  model: string;
  color: string;
}

export interface HistoryItem {
  id: string;
  spaceId: string;
  spaceName: string;
  title: string;
  preview: string;
  timestamp: string;
}

interface AppState {
  // UI State
  activeTab: Tab;
  setActiveTab: (tab: Tab) => void;
  
  // Spaces
  spaces: Space[];
  activeSpaceId: string | null;
  setActiveSpace: (id: string) => void;
  addSpace: (space: Space) => void;
  deleteSpace: (id: string) => void;
  
  // Chat
  messages: Message[];
  isGenerating: boolean;
  addMessage: (msg: Message) => void;
  updateMessage: (id: string, content: string) => void;
  clearMessages: () => void;
  setIsGenerating: (v: boolean) => void;
  
  // Settings
  providers: ProviderConfig[];
  toggleProvider: (id: string) => void;
  updateProviderKey: (id: string, key: string) => void;
  
  // History
  history: HistoryItem[];

  // Context
  screenContext: string | null;
  setScreenContext: (ctx: string | null) => void;

  // Backend
  backendReady: boolean;
  setBackendReady: (v: boolean) => void;
}

const defaultProviders: ProviderConfig[] = [
  { id: 'openai', name: 'OpenAI', enabled: false, apiKey: '', model: 'gpt-4o', color: '#10a37f' },
  { id: 'anthropic', name: 'Anthropic', enabled: false, apiKey: '', model: 'claude-sonnet-4-5-20250514', color: '#d4a574' },
  { id: 'gemini', name: 'Google Gemini', enabled: false, apiKey: '', model: 'gemini-2.0-flash', color: '#4285f4' },
  { id: 'mistral', name: 'Mistral', enabled: false, apiKey: '', model: 'mistral-large-latest', color: '#ff7000' },
  { id: 'deepseek', name: 'DeepSeek', enabled: false, apiKey: '', model: 'deepseek-chat', color: '#0066ff' },
  { id: 'azure', name: 'Azure OpenAI', enabled: false, apiKey: '', model: 'gpt-4o', color: '#0078d4' },
  { id: 'ollama', name: 'Ollama (Local)', enabled: false, apiKey: '', model: 'llama3', color: '#ffffff' },
];

const defaultSpaces: Space[] = [
  {
    id: 'default',
    name: 'General',
    icon: '🌐',
    description: 'Default workspace for general tasks',
    fileCount: 0,
    lastUsed: new Date().toISOString(),
    createdAt: new Date().toISOString(),
  },
];

export const useAppStore = create<AppState>((set) => ({
  activeTab: 'chat',
  setActiveTab: (tab) => set({ activeTab: tab }),
  
  spaces: defaultSpaces,
  activeSpaceId: 'default',
  setActiveSpace: (id) => set({ activeSpaceId: id }),
  addSpace: (space) => set((state) => ({ spaces: [...state.spaces, space] })),
  deleteSpace: (id) => set((state) => ({
    spaces: state.spaces.filter((s) => s.id !== id),
    activeSpaceId: state.activeSpaceId === id ? (state.spaces[0]?.id ?? null) : state.activeSpaceId,
  })),
  
  messages: [],
  isGenerating: false,
  addMessage: (msg) => set((state) => ({ messages: [...state.messages, msg] })),
  updateMessage: (id, content) => set((state) => ({
    messages: state.messages.map((m) => m.id === id ? { ...m, content, isStreaming: false } : m),
  })),
  clearMessages: () => set({ messages: [] }),
  setIsGenerating: (v) => set({ isGenerating: v }),
  
  providers: defaultProviders,
  toggleProvider: (id) => set((state) => ({
    providers: state.providers.map((p) => p.id === id ? { ...p, enabled: !p.enabled } : p),
  })),
  updateProviderKey: (id, key) => set((state) => ({
    providers: state.providers.map((p) => p.id === id ? { ...p, apiKey: key } : p),
  })),
  
  history: [],
  
  screenContext: null,
  setScreenContext: (ctx) => set({ screenContext: ctx }),
  
  backendReady: false,
  setBackendReady: (v) => set({ backendReady: v }),
}));
