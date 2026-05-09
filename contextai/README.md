# ContextAI

**Your personal AI command center for Windows.** A system-wide floating assistant with deep contextual awareness — upload documents, capture your screen, inject AI responses directly into any app, and build persistent memory. All powered locally on your machine.

![ContextAI](https://img.shields.io/badge/Status-Beta-blue) ![Platform](https://img.shields.io/badge/Platform-Windows-green) ![Tauri](https://img.shields.io/badge/Tauri-2.0-orange) ![License](https://img.shields.io/badge/License-MIT-purple)

---

## Highlights

- **System-wide floating widget** — WhisperFlow-style pill anchored above the taskbar, always one hotkey away
- **Text injection** — AI responses paste directly into Notepad, VS Code, browser fields, or any focused app
- **4-layer memory engine** — Global, space, procedural, and conversation-level memory
- **Multi-provider LLM** — OpenAI, Anthropic, Gemini, Mistral, DeepSeek, Azure, and local Ollama
- **RAG pipeline** — Hybrid vector + BM25 search with FlashRank reranking
- **Multi-modal** — Send images and files from the widget or main chat

---

## Features

### 🎯 Floating Widget (WhisperFlow Pattern)

The signature feature — a system-wide floating assistant that lives above your taskbar.

| Capability | Details |
|:-----------|:--------|
| **Always-on-top pill** | Compact emoji icon at bottom-center, expands on hover |
| **Hotkey** | `Ctrl+Shift+Space` toggles from anywhere |
| **Text injection** | One-click paste into the last focused app via `SetForegroundWindow` + `SendInput` |
| **Space switcher** | Compact icon → hover to expand name → dropdown with chat history per space |
| **File attachments** | 📎 button to attach images/files directly from the widget |
| **Streaming responses** | Real-time markdown rendering with copy/inject/new-chat actions |
| **Smart HWND tracking** | `SetWinEventHook(EVENT_SYSTEM_FOREGROUND)` continuously tracks the active window — inject always targets the right app |

**Widget States:**
```
IDLE     →  [ 🔮 ContextAI ✨ ● ]                 (compact pill)
ACTIVE   →  [ 🔮 ] [ Ask ContextAI...  ] [📎] [●] [→]  (on hover)
EXPANDED →  ┌─ Response (markdown) ─┐               (after send)
            ├─ Copy | Inject | New  ─┤
            └─ Input bar ────────────┘
```

### 🧠 4-Layer Memory Engine

| Layer | Scope | Purpose |
|:------|:------|:--------|
| **Global Memory** | All spaces | Persistent facts, preferences, and user info |
| **Space Memory** | Per workspace | Learned context specific to each project |
| **Procedural Memory** | Auto-evolving | Writing style, tone, expertise profile |
| **Conversation Memory** | Per session | Active chat context and thread continuity |

### 📄 RAG Pipeline

- **Hybrid Search** — ChromaDB vectors + BM25 keyword search with Reciprocal Rank Fusion
- **FlashRank Reranker** — State-of-the-art passage reranking for precision
- **Multi-format Ingestion** — PDF, DOCX, TXT, MD, CSV, PPTX, and code files
- **Per-Space Isolation** — Each workspace has its own document index

### 👁️ Vision & Screen Context

- **Multi-modal Chat** — Send images directly to vision-capable LLMs
- **Screen Capture** — UIA accessibility tree → clipboard → screenshot fallback chain
- **Clipboard Monitor** — Opt-in background clipboard tracking for active context
- **Widget Attachments** — Attach images/files from the floating widget

### 🔌 Multi-Provider LLM

| Provider | Models |
|:---------|:-------|
| OpenAI | GPT-4o, GPT-4.1, etc. |
| Anthropic | Claude Sonnet 4.5, etc. |
| Google Gemini | Gemini 2.0 Flash, etc. |
| Mistral | Mistral Large |
| DeepSeek | DeepSeek Chat |
| Azure OpenAI | GPT-4.1 Mini |
| Ollama | Auto-detected local models |

### 📁 Spaces & Templates

- **Workspaces** — Organize projects, research, and client work into isolated spaces
- **Templates** — Pre-configured spaces for Job Applications, Research, Client Work, Study, Coding, and Writing
- **Text Context** — Add persistent instructions per space for tailored AI behavior

### 💬 Chat Experience

- **Message actions** — Copy, edit, delete, regenerate on every message
- **Markdown rendering** — Code highlighting, tables, lists, and inline formatting
- **Conversation history** — Full history per space with search and export
- **Auto-titling** — AI-generated conversation titles
- **Streaming** — Real-time SSE response streaming with stop control

---

## Architecture

```
┌───────────────────────────────────────────────────┐
│                Tauri 2 Desktop App                 │
│                                                   │
│  ┌─────────────┐        ┌──────────────────────┐ │
│  │  React UI   │  HTTP   │  Python Sidecar      │ │
│  │  (Vite +    │ ←────→  │  (FastAPI + SSE)     │ │
│  │   Zustand)  │ :8742   │                      │ │
│  └──────┬──────┘        └──────────┬───────────┘ │
│         │                          │              │
│  ┌──────┴──────┐     ┌─────────────┴───────────┐ │
│  │  Widget     │     │    Backend Services      │ │
│  │  Window     │     │ ┌────────┐ ┌──────────┐  │ │
│  │  (480×500   │     │ │LiteLLM│ │   RAG    │  │ │
│  │   overlay)  │     │ │Router │ │ Pipeline │  │ │
│  └──────┬──────┘     │ └────────┘ └──────────┘  │ │
│         │            │ ┌────────┐ ┌──────────┐  │ │
│  ┌──────┴──────┐     │ │Memory │ │  Screen  │  │ │
│  │  Rust Core  │     │ │Engine │ │  Context │  │ │
│  │ • Win32 API │     │ └────────┘ └──────────┘  │ │
│  │ • Injection │     │ ┌──────────────────────┐ │ │
│  │ • Foreground│     │ │ Document Processor   │ │ │
│  │   Hook      │     │ │ (Chunk + Index)      │ │ │
│  └─────────────┘     │ └──────────────────────┘ │ │
│                      └──────────────────────────┘ │
└───────────────────────────────────────────────────┘
```

### Win32 Integration (Rust)

The Rust core provides enterprise-grade Windows integration:

| Component | Win32 API | Purpose |
|:----------|:----------|:--------|
| **Foreground Hook** | `SetWinEventHook(EVENT_SYSTEM_FOREGROUND)` | Continuously tracks the last non-widget foreground window |
| **Focus Switching** | `AttachThreadInput` + `SetForegroundWindow` | Reliably switches focus across processes |
| **Text Injection** | `SendInput` (Ctrl+V simulation) | Pastes clipboard content into any focused app |
| **Clipboard** | `OpenClipboard` + `SetClipboardData` | Sets clipboard text for injection |

**Data stored locally at** `~/.contextai/`

---

## Quick Start

### Prerequisites

- **Node.js** 18+
- **Python** 3.11+
- **Rust** (for Tauri 2 builds)
- **Ollama** (optional, for local LLMs)

### Development

```bash
# Clone
git clone https://github.com/your-username/contextai.git
cd contextai

# Frontend dependencies
npm install

# Backend virtual environment
cd backend
python -m venv .venv
.venv/Scripts/activate  # Windows
pip install -e ".[windows]"
cd ..

# Start everything (uses run.bat on Windows)
run.bat

# Or manually:
npm run dev                                           # Vite dev server on :1420
cd backend && python -m uvicorn app.main:app --port 8742 --reload  # Backend
```

### Build

```bash
npm run tauri build   # Produces installer in src-tauri/target/release
```

### Configuration

1. Open Settings (gear icon or tray → Open Manager)
2. Choose a provider: **OpenAI**, **Anthropic**, **Gemini**, **Ollama**, etc.
3. Enter your API key (or click "Detect Models" for Ollama)
4. Select a model and start chatting

### Hotkeys

| Shortcut | Action |
|:---------|:-------|
| `Ctrl+Shift+Space` | Toggle floating widget |
| `Enter` | Send message (widget or main chat) |
| `Esc` | Dismiss widget / close expanded state |

---

## API Endpoints

| Route | Method | Description |
|:------|:-------|:------------|
| `/api/health` | GET | Backend status |
| `/api/chat/stream` | POST | SSE streaming chat with context |
| `/api/spaces` | GET/POST | Space CRUD |
| `/api/spaces/{id}/instructions` | GET/PUT | Space instructions |
| `/api/files/{space}/upload` | POST | Upload + auto-index documents |
| `/api/conversations` | GET/POST | Conversation CRUD (filterable by space) |
| `/api/conversations/{id}` | GET/PUT/DELETE | Single conversation operations |
| `/api/attachments/upload` | POST | Upload chat attachments |
| `/api/attachments/{filename}` | GET | Serve uploaded attachments |
| `/api/settings/models` | GET | Available models |
| `/api/settings/providers` | GET/PUT | Provider configurations |
| `/api/memory/global` | GET/PUT | Global memory |
| `/api/memory/space/{id}` | GET/PUT | Space memory |
| `/api/memory/profile/{id}` | GET/PUT | User profile |
| `/api/memory/extract` | POST | Extract facts from conversation |
| `/api/context/capture` | POST | Screen context capture |
| `/api/context/preview` | GET | Preview available context |

---

## Tech Stack

| Layer | Technology |
|:------|:-----------|
| Desktop Shell | Tauri 2 (Rust + WebView2) |
| Win32 Integration | `windows` crate 0.58 (`SetWinEventHook`, `SendInput`, `AttachThreadInput`) |
| Frontend | React 18, TypeScript, Vite, Zustand |
| Styling | Vanilla CSS (glassmorphism, dark mode, micro-animations) |
| Backend | FastAPI, Uvicorn, Python 3.11+ |
| LLM Routing | LiteLLM (multi-provider) |
| Vector DB | ChromaDB |
| Search | BM25S + FlashRank reranker |
| Screen Capture | Windows UIA, MSS, pyperclip |
| Storage | Local filesystem (`~/.contextai/`) |

---

## Project Structure

```
contextai/
├── src/                        # React frontend
│   ├── components/
│   │   ├── WidgetBar.tsx       # Floating WhisperFlow widget
│   │   ├── ChatView.tsx        # Main chat interface
│   │   ├── SpacesView.tsx      # Space management
│   │   ├── HistoryView.tsx     # Conversation history
│   │   ├── SettingsView.tsx    # Provider configuration
│   │   ├── MessageActions.tsx  # Copy/edit/delete/regen per message
│   │   ├── MarkdownRenderer.tsx
│   │   ├── SpaceSwitcher.tsx
│   │   ├── TabNav.tsx
│   │   ├── TitleBar.tsx
│   │   └── Toast.tsx
│   ├── stores/
│   │   └── appStore.ts         # Zustand global state
│   ├── lib/
│   │   ├── api.ts              # Backend API client
│   │   └── env.ts              # Environment helpers
│   └── index.css               # Full design system
│
├── src-tauri/                  # Tauri / Rust core
│   ├── src/
│   │   └── lib.rs              # Win32 injection, foreground hook, commands
│   ├── tauri.conf.json         # Window configs (main + widget)
│   └── Cargo.toml              # Rust dependencies
│
├── backend/                    # Python sidecar
│   └── app/
│       ├── main.py             # FastAPI entrypoint
│       ├── routers/
│       │   ├── chat.py         # Streaming chat with RAG + memory
│       │   ├── conversations.py
│       │   ├── spaces.py
│       │   ├── files.py
│       │   ├── memory.py
│       │   ├── settings.py
│       │   ├── context.py
│       │   └── attachments.py
│       └── services/           # Business logic
│
├── widget.html                 # Widget window entry point
├── run.bat                     # One-click dev launcher (Windows)
└── package.json
```

---

## License

MIT
