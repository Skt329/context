# ContextAI

**Personal AI assistant with deep contextual awareness.** Upload documents, capture your screen, and build persistent memory — all locally on your machine.

![ContextAI](https://img.shields.io/badge/Status-Beta-blue) ![Platform](https://img.shields.io/badge/Platform-Windows-green) ![License](https://img.shields.io/badge/License-MIT-purple)

---

## Features

### 🧠 4-Layer Memory Engine
- **Global Memory** — Persistent facts shared across all spaces
- **Space Memory** — Per-workspace learned preferences and context
- **Procedural Memory** — Auto-evolving user profile (writing style, tone, expertise)
- **Conversation Memory** — Session-level context within active chats

### 📄 RAG Pipeline
- **Hybrid Search** — ChromaDB vectors + BM25 keyword search with RRF fusion
- **FlashRank Reranker** — State-of-the-art passage reranking for precision
- **Multi-format Ingestion** — PDF, DOCX, TXT, MD, CSV, PPTX, code files
- **Per-Space Isolation** — Each workspace has its own document index

### 👁️ Vision & Screen Context
- **Multi-modal Chat** — Send images directly to vision-capable LLMs
- **Screen Capture** — UIA accessibility tree → clipboard → screenshot fallback
- **Clipboard Monitor** — Opt-in background clipboard tracking for active context

### 🔌 Multi-Provider LLM
- **LiteLLM Router** — Works with OpenAI, Anthropic, Google Gemini, and Ollama
- **Auto-detection** — Discovers locally installed Ollama models
- **Streaming** — Real-time SSE response streaming

### 📁 Spaces & Templates
- **Workspaces** — Organize projects, research, and client work into isolated spaces
- **Templates** — Pre-configured spaces for Job Applications, Research, Client Work, Study, Coding, and Writing
- **Text Context** — Add persistent instructions per space for tailored AI behavior

### ⚡ Quick Actions
- Summarize documents or screen content
- Draft emails and cover letters
- Explain code
- Write cold outreach emails

---

## Architecture

```
┌──────────────────────────────────────────┐
│             Tauri 2 Desktop App           │
│  ┌────────────┐     ┌──────────────────┐ │
│  │ React UI   │ ←→  │ Python Sidecar   │ │
│  │ (Vite)     │     │ (FastAPI + SSE)  │ │
│  └────────────┘     └──────────────────┘ │
│                           │               │
│  ┌─────────────────────────┴────────────┐│
│  │          Backend Services             ││
│  │ ┌──────────┐ ┌──────────┐ ┌────────┐ ││
│  │ │ LiteLLM  │ │ RAG      │ │ Memory │ ││
│  │ │ Router   │ │ Pipeline │ │ Engine │ ││
│  │ └──────────┘ └──────────┘ └────────┘ ││
│  │ ┌──────────┐ ┌──────────────────────┐││
│  │ │ Screen   │ │ Document Processor   │││
│  │ │ Context  │ │ (Chunk + Index)      │││
│  │ └──────────┘ └──────────────────────┘││
│  └──────────────────────────────────────┘│
└──────────────────────────────────────────┘
```

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

# Start development
npm run dev              # Vite dev server on :1420
cd backend && python -m uvicorn app.main:app --port 8742 --reload
```

### Configuration

1. Open Settings (gear icon)
2. Choose a provider: **OpenAI**, **Anthropic**, **Gemini**, or **Ollama**
3. Enter your API key (or click "Detect Models" for Ollama)
4. Select a model and start chatting

---

## API Endpoints

| Route | Method | Description |
|:------|:-------|:------------|
| `/api/health` | GET | Backend status |
| `/api/chat/stream` | POST | SSE streaming chat |
| `/api/spaces` | GET/POST | Space CRUD |
| `/api/files/{space}/upload` | POST | Upload + auto-index documents |
| `/api/settings/models` | GET | Available models |
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
| Desktop | Tauri 2 (Rust) |
| Frontend | React 18, Vite, Zustand |
| Backend | FastAPI, Uvicorn |
| LLM | LiteLLM (multi-provider) |
| Vectors | ChromaDB |
| Search | BM25S + FlashRank |
| Screen | Windows UIA, MSS, pyperclip |
| Storage | Local filesystem (~/.contextai) |

---

## Project Structure

```
contextai/
├── src/                    # React frontend
│   ├── components/         # UI components
│   ├── stores/             # Zustand state
│   ├── lib/                # API client
│   └── index.css           # Design system
├── backend/                # Python sidecar
│   └── app/
│       ├── routers/        # API endpoints
│       └── services/       # Business logic
├── src-tauri/              # Tauri config
└── package.json
```

---

## License

MIT
