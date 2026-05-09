# ContextAI

**Your personal AI command center for Windows.** A system-wide floating assistant with deep contextual awareness — upload documents, capture your screen, inject AI responses directly into any app, and build persistent memory. All powered locally on your machine.

![ContextAI](https://img.shields.io/badge/Status-Beta-blue) ![Platform](https://img.shields.io/badge/Platform-Windows-green) ![Tauri](https://img.shields.io/badge/Tauri-2.0-orange) ![License](https://img.shields.io/badge/License-MIT-purple) ![CI](https://img.shields.io/badge/CI-GitHub_Actions-brightgreen) ![Tests](https://img.shields.io/badge/Tests-45_Passing-success)

---

## Highlights

- **System-wide floating widget** — WhisperFlow-style pill anchored above the taskbar, always one hotkey away
- **Text injection** — AI responses paste directly into Notepad, VS Code, browser fields, or any focused app
- **4-layer memory engine** — Global, space, procedural, and conversation-level memory with auto-extraction
- **Multi-provider LLM** — OpenAI, Anthropic, Gemini, Mistral, DeepSeek, Azure, and local Ollama with automatic failover
- **Enterprise RAG pipeline** — Hybrid vector + BM25 search with HyDE expansion, FlashRank reranking, and numbered citations
- **Tool/function calling** — Built-in tools (calculator, time, memory) with a 3-round LLM execution loop
- **Full-text search** — FTS5-powered conversation search with highlighted match previews
- **Multi-modal** — Send images and files via drag-and-drop or file picker
- **Export** — Download any conversation as Markdown or JSON
- **WCAG AA accessible** — ARIA tablist/tabpanel, keyboard navigation, focus management

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
| **Drag & drop** | Drop files anywhere on the chat to attach them |
| **Streaming responses** | Real-time markdown rendering with copy/inject/new-chat actions |
| **Smart HWND tracking** | `SetWinEventHook(EVENT_SYSTEM_FOREGROUND)` continuously tracks the active window |

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

Memory is automatically extracted from conversations using pattern matching and LLM summarization. Rated messages feed back into procedural memory for continuous improvement.

### 📄 Enterprise RAG Pipeline

| Component | Technology | Purpose |
|:----------|:-----------|:--------|
| **Vector Search** | ChromaDB (cosine similarity) | Semantic document retrieval |
| **Keyword Search** | BM25S with persistent indexing | Exact term matching |
| **Fusion** | Reciprocal Rank Fusion (RRF) | Merges vector + keyword results |
| **Reranking** | FlashRank (ms-marco-MiniLM-L-12-v2) | State-of-the-art passage reranking |
| **HyDE** | Hypothetical Document Embeddings | Query expansion for better recall |
| **Citations** | Numbered `[N]` markers | Source attribution in every response |
| **Chunking** | Contextual chunking by document type | Semantic boundaries for code, prose, tables |
| **Token Budget** | tiktoken-based counting | Accurate context window management |

**Supported Formats:** PDF, DOCX, PPTX, CSV, TXT, Markdown, and 20+ code file types.

### 🔧 Tool / Function Calling

The LLM can invoke built-in tools during conversations:

| Tool | Description |
|:-----|:------------|
| `calculate` | Safe math evaluator (trig, log, sqrt, powers, etc.) |
| `get_current_time` | UTC + local time with timezone offset |
| `get_memory_summary` | Retrieves global + space memory for context |

Tools are executed in a **3-round loop**: the LLM decides whether to call tools, results are injected back, and the final response streams to the user. Tool definitions follow the OpenAI function-calling schema for LiteLLM compatibility.

### 🔍 Full-Text Search & Export

- **FTS5 Search** — SQLite full-text index with auto-sync triggers, debounced frontend, and highlighted match previews
- **Conversation Export** — Download any conversation as Markdown (with metadata) or raw JSON
- **Rebuild Index** — Admin endpoint to regenerate the FTS index from existing data

### 👁️ Vision & Screen Context

- **Multi-modal Chat** — Send images directly to vision-capable LLMs
- **Screen Capture** — UIA accessibility tree → clipboard → screenshot fallback chain
- **Clipboard Monitor** — Opt-in background clipboard tracking for active context
- **Drag & Drop** — Drop files directly onto the chat view with visual overlay feedback

### 🔌 Multi-Provider LLM with Failover

| Provider | Models |
|:---------|:-------|
| OpenAI | GPT-4o, GPT-4.1, etc. |
| Anthropic | Claude Sonnet 4.5, etc. |
| Google Gemini | Gemini 2.0 Flash, etc. |
| Mistral | Mistral Large |
| DeepSeek | DeepSeek Chat |
| Azure OpenAI | GPT-4.1 Mini |
| Ollama | Auto-detected local models |

**Automatic failover**: If the primary provider fails, the system tries the next enabled provider. Warnings are surfaced in the UI without interrupting the conversation.

### 📁 Spaces & Templates

- **Workspaces** — Organize projects, research, and client work into isolated spaces
- **Templates** — Pre-configured spaces for Job Applications, Research, Client Work, Study, Coding, and Writing
- **Text Context** — Add persistent instructions per space for tailored AI behavior

### 💬 Chat Experience

- **Message actions** — Copy, edit, delete, regenerate, and rate on every message
- **Markdown rendering** — Code highlighting, tables, lists, and inline formatting
- **Token usage** — Displays `↑prompt ↓completion Σtotal` tokens after each response
- **Source citations** — Collapsible section showing `[N]` references from RAG
- **Auto-titling** — AI-generated conversation titles
- **SSE streaming** — Real-time response streaming with 15s heartbeat, auto-reconnect (2 retries), and stop control
- **Drag & drop uploads** — Drop files anywhere on the chat for instant attachment

### ♿ Accessibility (WCAG AA)

- **TabNav** — `role="tablist"` with arrow key cycling and `aria-selected`
- **Content panels** — `role="tabpanel"` linked to tabs via `aria-labelledby`
- **History** — `role="list"` / `role="listitem"` with keyboard focus and labels
- **Messages** — `role="article"` with `aria-label` for screen readers
- **All controls** — Descriptive `aria-label`, `title`, and `tabIndex` attributes

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    Tauri 2 Desktop App                        │
│                                                              │
│  ┌──────────────┐         ┌────────────────────────────────┐│
│  │   React UI   │  HTTP    │     Python Sidecar (FastAPI)  ││
│  │  (Vite +     │ ←─────→  │                              ││
│  │   Zustand)   │ :8742    │  ┌──────┐  ┌───────────────┐ ││
│  └──────┬───────┘          │  │LiteLLM│ │   RAG Engine  │ ││
│         │                  │  │Router │ │ ChromaDB+BM25 │ ││
│  ┌──────┴───────┐          │  └──────┘  └───────────────┘ ││
│  │   Widget     │          │  ┌──────┐  ┌───────────────┐ ││
│  │   Window     │          │  │Memory│  │  Tool Engine  │ ││
│  │  (480×500)   │          │  │Engine│  │ (Function     │ ││
│  └──────┬───────┘          │  └──────┘  │  Calling)     │ ││
│         │                  │            └───────────────┘ ││
│  ┌──────┴───────┐          │  ┌──────────────────────────┐││
│  │  Rust Core   │          │  │   Infrastructure         │││
│  │ • Win32 API  │          │  │ • Task Queue (async)     │││
│  │ • Injection  │          │  │ • Correlation Middleware  │││
│  │ • Foreground │          │  │ • Error Reporting (SQLite)│││
│  │   Hook       │          │  │ • FTS5 Search Index       │││
│  └──────────────┘          │  └──────────────────────────┘││
│                            └────────────────────────────────┘│
└──────────────────────────────────────────────────────────────┘
```

### Win32 Integration (Rust)

| Component | Win32 API | Purpose |
|:----------|:----------|:--------|
| **Foreground Hook** | `SetWinEventHook(EVENT_SYSTEM_FOREGROUND)` | Continuously tracks the last non-widget foreground window |
| **Focus Switching** | `AttachThreadInput` + `SetForegroundWindow` | Reliably switches focus across processes |
| **Text Injection** | `SendInput` (Ctrl+V simulation) | Pastes clipboard content into any focused app |
| **Clipboard** | `OpenClipboard` + `SetClipboardData` | Sets clipboard text for injection |

### Observability

| Feature | Details |
|:--------|:--------|
| **Request Correlation** | Every request gets `X-Request-ID` (8-char UUID) + `X-Response-Time` headers |
| **Structured Logging** | Timestamped, leveled, namespaced log format |
| **Error Reporting** | Unhandled exceptions logged to `error_log` SQLite table with tracebacks |
| **Debug Endpoint** | `/api/debug/errors` returns recent errors for diagnostics |
| **Task Monitoring** | `/api/tasks` and `/api/tasks/{id}` for background job status |

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
pip install -e ".[windows,dev]"
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

### Run Tests

```bash
# Backend (45 tests)
cd backend
.venv/Scripts/python -m pytest tests/ -v

# Frontend type check
npx tsc --noEmit
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

### Core

| Route | Method | Description |
|:------|:-------|:------------|
| `/api/health` | GET | Backend status, version, pending tasks |
| `/api/chat/stream` | POST | SSE streaming chat with RAG, memory, and tool calling |
| `/api/chat/rate` | POST | Rate a message for procedural memory |
| `/api/chat/generate-title` | POST | AI-generated conversation title |

### Spaces & Files

| Route | Method | Description |
|:------|:-------|:------------|
| `/api/spaces` | GET/POST | Space CRUD |
| `/api/spaces/{id}/instructions` | GET/PUT | Space instructions |
| `/api/files/{space}/upload` | POST | Upload + async background indexing |
| `/api/files/{space}/files` | GET | List indexed files |
| `/api/files/{space}/reindex` | POST | Rebuild RAG index |

### Conversations

| Route | Method | Description |
|:------|:-------|:------------|
| `/api/conversations` | GET/POST | Conversation CRUD (filterable by space) |
| `/api/conversations/bulk` | POST | Bulk fetch by IDs (N+1 elimination) |
| `/api/conversations/search` | GET | FTS5 full-text search with snippets |
| `/api/conversations/{id}` | GET/PUT/DELETE | Single conversation operations |
| `/api/conversations/{id}/export` | GET | Export as Markdown or JSON |
| `/api/conversations/rebuild-fts` | POST | Rebuild FTS5 search index |

### Memory & Context

| Route | Method | Description |
|:------|:-------|:------------|
| `/api/memory/global` | GET/PUT | Global memory |
| `/api/memory/space/{id}` | GET/PUT | Space memory |
| `/api/memory/profile/{id}` | GET/PUT | User profile |
| `/api/memory/extract` | POST | Extract facts from conversation |
| `/api/context/capture` | POST | Screen context capture |
| `/api/context/preview` | GET | Preview available context |

### Infrastructure

| Route | Method | Description |
|:------|:-------|:------------|
| `/api/tasks` | GET | List background task statuses |
| `/api/tasks/{id}` | GET | Get specific task status |
| `/api/debug/errors` | GET | Recent unhandled errors |
| `/api/settings/providers` | GET/PUT | Provider configurations |
| `/api/settings/models` | GET | Available models |
| `/api/attachments/upload` | POST | Upload chat attachments |
| `/api/attachments/{filename}` | GET | Serve uploaded attachments |

---

## Tech Stack

| Layer | Technology |
|:------|:-----------|
| Desktop Shell | Tauri 2 (Rust + WebView2) |
| Win32 Integration | `windows` crate 0.58 (`SetWinEventHook`, `SendInput`, `AttachThreadInput`) |
| Frontend | React 18, TypeScript, Vite, Zustand |
| Styling | Vanilla CSS (glassmorphism, dark mode, micro-animations) |
| Backend | FastAPI, Uvicorn, Python 3.11+ |
| LLM Routing | LiteLLM (multi-provider, failover, tool calling) |
| Vector DB | ChromaDB (persistent, per-space) |
| Keyword Search | BM25S (persistent disk index) |
| Reranking | FlashRank (ms-marco-MiniLM-L-12-v2) |
| Full-Text Search | SQLite FTS5 with auto-sync triggers |
| Token Counting | tiktoken (exact GPT-compatible counting) |
| Screen Capture | Windows UIA, MSS, pyperclip |
| Storage | SQLite (WAL mode) + local filesystem (`~/.contextai/`) |
| CI/CD | GitHub Actions (pytest, tsc, ruff, eslint) |

---

## Project Structure

```
contextai/
├── src/                          # React frontend
│   ├── components/
│   │   ├── WidgetBar.tsx         # Floating WhisperFlow widget
│   │   ├── ChatView.tsx          # Main chat (token usage, citations, drag-drop)
│   │   ├── SpacesView.tsx        # Space management
│   │   ├── HistoryView.tsx       # History with FTS5 search + export buttons
│   │   ├── SettingsView.tsx      # Provider configuration
│   │   ├── MessageActions.tsx    # Copy/edit/delete/regen/rate per message
│   │   ├── MarkdownRenderer.tsx  # Syntax-highlighted markdown
│   │   ├── DropZone.tsx          # Drag-and-drop file upload overlay
│   │   ├── SpaceSwitcher.tsx     # Space context selector
│   │   ├── TabNav.tsx            # ARIA-compliant navigation tabs
│   │   ├── TitleBar.tsx          # Custom window title bar
│   │   └── Toast.tsx             # Notification system
│   ├── stores/
│   │   └── appStore.ts           # Zustand global state
│   ├── lib/
│   │   ├── api.ts                # Backend API client (SSE auto-reconnect, bulk fetch)
│   │   └── env.ts                # Environment helpers
│   └── index.css                 # Full design system
│
├── src-tauri/                    # Tauri / Rust core
│   ├── src/
│   │   └── lib.rs                # Win32 injection, foreground hook, commands
│   ├── tauri.conf.json           # Window configs (main + widget)
│   └── Cargo.toml                # Rust dependencies
│
├── backend/                      # Python sidecar
│   ├── app/
│   │   ├── main.py               # FastAPI entrypoint + lifecycle
│   │   ├── db.py                 # SQLite schema (WAL, FTS5, error_log)
│   │   ├── tasks.py              # Background async task queue
│   │   ├── middleware.py         # Correlation IDs + error reporting
│   │   ├── routers/
│   │   │   ├── chat.py           # Streaming chat (RAG + memory + tools)
│   │   │   ├── conversations.py  # CRUD, search, export, bulk fetch
│   │   │   ├── spaces.py         # Space management
│   │   │   ├── files.py          # Upload + async background indexing
│   │   │   ├── memory.py         # Memory CRUD + extraction
│   │   │   ├── settings.py       # Provider config + key masking
│   │   │   ├── context.py        # Screen context capture
│   │   │   └── attachments.py    # Image/file uploads
│   │   ├── services/
│   │   │   ├── rag_service.py    # Hybrid search (ChromaDB + BM25 + RRF + rerank)
│   │   │   ├── indexing.py       # Document indexing pipeline
│   │   │   ├── chunking.py       # Contextual chunking by doc type
│   │   │   ├── parser.py         # Multi-format document parsing
│   │   │   ├── memory_service.py # Memory extraction + summarization
│   │   │   ├── tools.py          # Built-in tool/function calling engine
│   │   │   └── screen_context.py # UIA + clipboard + screenshot
│   │   └── utils/
│   │       └── llm.py            # LLM completion helper
│   ├── tests/
│   │   ├── conftest.py           # Shared fixtures (temp DB, sample data)
│   │   ├── test_database.py      # Schema, CRUD, migration tests
│   │   ├── test_phase2.py        # Token counting, LLM resolver, RAG citations
│   │   └── test_phase3_4.py      # FTS5, task queue, tools, error log, middleware
│   └── pyproject.toml            # Python project config
│
├── .github/workflows/ci.yml     # CI pipeline (backend + frontend + lint)
├── widget.html                   # Widget window entry point
├── run.bat                       # One-click dev launcher (Windows)
└── package.json
```

---

## License

MIT
