# 🚀 Core Coder V5 API Server

Your Python CLI agent is now available as a WebSocket/REST API for Next.js integration!

## 🎯 Quick Start

### 1. Start the API Server

```bash
# Make sure you're in the venv
.\venv\Scripts\Activate.ps1

# Start the API server
python api_server.py
```

The server will start on **http://localhost:8000**

### 2. Test WebSocket Connection

Open http://localhost:8000/docs to see the interactive API documentation.

### 3. Connect from Next.js

See `nextjs-example.tsx` for complete React hooks and components.

## 📡 API Endpoints

### WebSocket Chat
```
ws://localhost:8000/ws/chat
```

**Send to server:**
```json
{
  "message": "hello world",
  "session_id": "my-session"
}
```

**Receive from server:**
```json
{
  "type": "agent_response",
  "content": "Hello! How can I help?",
  "ansi": true
}
```

### Execute Commands (REST)
```
POST http://localhost:8000/api/command
```

**Request:**
```json
{
  "command": "cd",
  "args": ["langchain-agent-base/src"]
}
```

**Response:**
```json
{
  "result": "\u001b[32m✓ Changed directory\u001b[0m\n...",
  "success": true,
  "ansi": true,
  "cwd": "M:\\_tools\\cli_agent_exports\\core_coder_v5\\langchain-agent-base\\src"
}
```

### Get Status
```
GET http://localhost:8000/api/status
```

**Response:**
```json
{
  "name": "Core Coder V5",
  "provider": "ollama",
  "model": "qwen3:1.7b",
  "cwd": "/current/working/directory",
  "memory_enabled": true,
  "commands_available": 14
}
```

### List Commands
```
GET http://localhost:8000/api/commands
```

**Response:**
```json
{
  "commands": [
    {
      "name": "cd",
      "description": "Change current working directory",
      "usage": "//cd <path>"
    },
    {
      "name": "status",
      "description": "Show agent status and configuration",
      "usage": "//status"
    }
  ],
  "total": 14
}
```

### Autocomplete (Tab Completion)
```
POST http://localhost:8000/api/autocomplete
```

**Request:**
```json
{
  "text": "//cd lang",
  "cursor_position": 8
}
```

**Response:**
```json
{
  "suggestions": [
    "langchain-agent-base/",
    "langchain-agent-base/src/"
  ],
  "type": "path",
  "prefix": "lang"
}
```

**Works for:**
- Command completion: `//t` → `//tools`, `//status`
- Path completion: `//cd lang` → `langchain-agent-base/`
- File completion in any context

## 🎨 Rendering ANSI Colors in Next.js

All responses include ANSI color codes (like your CLI). You have options:

### Option 1: Convert ANSI to HTML

```bash
npm install ansi-to-html
```

```typescript
import AnsiToHtml from 'ansi-to-html';

const convert = new AnsiToHtml();
const html = convert.toHtml(response.result);

<div dangerouslySetInnerHTML={{ __html: html }} />
```

### Option 2: Use xterm.js (Full Terminal)

```bash
npm install xterm @xterm/addon-fit
```

```typescript
import { Terminal } from 'xterm';

const term = new Terminal();
term.write(response.result); // Handles ANSI automatically!
```

See `nextjs-example.tsx` for complete implementations.

## 🔧 Available Commands

All your CLI commands work via API:

- `//cd <path>` - Change directory
- `//status` - Show agent status
- `//tools` - List all tools
- `//config` - Show configuration
- `//memory status` - Check memory
- `//help` - Show help
- And all others from your CLI!

## 🌐 CORS Configuration

The server allows:
- `http://localhost:3000` (Next.js default)
- `http://localhost:3001`
- All origins in development

For production, edit `api_server.py` to restrict origins.

## 📦 Architecture

```
┌─────────────────────────────────────────┐
│          Next.js Frontend               │
│    (Your custom terminal UI)            │
└──────────────┬──────────────────────────┘
               │ WebSocket/HTTP
               │
┌──────────────▼──────────────────────────┐
│       FastAPI Server                    │
│    (api_server.py - Port 8000)          │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│      Python Agent (LangChain)           │
│   • Commands (//cd, //tools, etc)       │
│   • Tools (read_file, run_command)      │
│   • Chat with LLM                       │
└─────────────────────────────────────────┘
```

## 🎯 Message Types

### From Server → Client

| Type | Description | Fields |
|------|-------------|--------|
| `agent_typing` | Agent is processing | `agent_name` |
| `agent_response` | Chat response | `content`, `ansi` |
| `command_result` | Command output | `command`, `result`, `ansi`, `cwd` |
| `error` | Error occurred | `message` |

### From Client → Server

```json
{
  "message": "your message or //command",
  "session_id": "optional-session-id"
}
```

## 🔍 Testing with curl

### Test command execution:
```bash
curl -X POST http://localhost:8000/api/command \
  -H "Content-Type: application/json" \
  -d '{"command": "cd", "args": ["langchain-agent-base"]}'
```

### Test status:
```bash
curl http://localhost:8000/api/status
```

### Test WebSocket (using wscat):
```bash
npm install -g wscat
wscat -c ws://localhost:8000/ws/chat

> {"message": "hello", "session_id": "test"}
```

## 💡 Tips

1. **ANSI codes are preserved** - Your CLI colors work in Next.js
2. **Session IDs** - Use to maintain conversation history
3. **Commands work the same** - `//cd`, `//tools`, etc all work
4. **Real-time streaming** - WebSocket for live responses
5. **REST fallback** - Use `/api/command` if you prefer HTTP

## 🚀 Next Steps

1. ✅ Start API server: `python api_server.py`
2. ✅ Create Next.js app: `npx create-next-app@latest`
3. ✅ Copy `nextjs-example.tsx` to your Next.js project
4. ✅ Install: `npm install ansi-to-html` or `npm install xterm`
5. ✅ Connect and build your custom terminal UI!

Your CLI is now a headless agent that Next.js can control! 🎉
