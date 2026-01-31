/**
 * Next.js WebSocket Client Example
 * ================================
 * 
 * How to connect your Next.js frontend to the Python agent API.
 * 
 * Installation:
 * npm install ansi-to-html  // For rendering ANSI colors
 * 
 * Or use xterm.js:
 * npm install xterm @xterm/addon-fit
 */

import { useEffect, useRef, useState } from 'react';
import AnsiToHtml from 'ansi-to-html';

// Initialize ANSI converter
const ansiConverter = new AnsiToHtml({
  fg: '#f8f8f2',
  bg: '#282a36',
  newline: true,
  colors: {
    0: '#282a36',  // black
    1: '#ff5555',  // red
    2: '#50fa7b',  // green
    3: '#f1fa8c',  // yellow
    4: '#bd93f9',  // blue
    5: '#ff79c6',  // magenta
    6: '#8be9fd',  // cyan
    7: '#f8f8f2',  // white
  }
});

export function useAgentWebSocket() {
  const [connected, setConnected] = useState(false);
  const [messages, setMessages] = useState<string[]>([]);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    // Connect to Python agent WebSocket
    const ws = new WebSocket('ws://localhost:8000/ws/chat');

    ws.onopen = () => {
      console.log('✅ Connected to agent');
      setConnected(true);
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);

      switch (data.type) {
        case 'agent_typing':
          console.log('Agent is typing...');
          break;

        case 'agent_response':
          // Got agent response with ANSI codes
          const html = ansiConverter.toHtml(data.content);
          setMessages((prev) => [...prev, html]);
          break;

        case 'command_result':
          // Got command result (like //cd, //status)
          const resultHtml = ansiConverter.toHtml(data.result);
          setMessages((prev) => [...prev, resultHtml]);
          break;

        case 'error':
          console.error('Agent error:', data.message);
          break;
      }
    };

    ws.onclose = () => {
      console.log('❌ Disconnected from agent');
      setConnected(false);
    };

    wsRef.current = ws;

    return () => {
      ws.close();
    };
  }, []);

  const sendMessage = (message: string, sessionId?: string) => {
    if (wsRef.current && connected) {
      wsRef.current.send(
        JSON.stringify({
          message,
          session_id: sessionId || 'default',
        })
      );
    }
  };

  return { connected, messages, sendMessage };
}

// ============================================
// Example Component
// ============================================

export default function AgentTerminal() {
  const { connected, messages, sendMessage } = useAgentWebSocket();
  const [input, setInput] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (input.trim()) {
      sendMessage(input);
      setInput('');
    }
  };

  return (
    <div className="flex flex-col h-screen bg-gray-900 text-white font-mono">
      {/* Connection Status */}
      <div className="p-2 bg-gray-800 border-b border-gray-700">
        <span className={connected ? 'text-green-400' : 'text-red-400'}>
          {connected ? '● Connected' : '○ Disconnected'}
        </span>
      </div>

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-2">
        {messages.map((msg, i) => (
          <div
            key={i}
            dangerouslySetInnerHTML={{ __html: msg }}
            className="whitespace-pre-wrap"
          />
        ))}
      </div>

      {/* Input Area */}
      <form onSubmit={handleSubmit} className="p-4 bg-gray-800 border-t border-gray-700">
        <div className="flex gap-2">
          <span className="text-cyan-400">You:</span>
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Type your message or //command..."
            className="flex-1 bg-transparent outline-none text-white"
            disabled={!connected}
          />
        </div>
      </form>
    </div>
  );
}

// ============================================
// Alternative: Using xterm.js (More Authentic)
// ============================================

/*
import { Terminal } from 'xterm';
import { FitAddon } from '@xterm/addon-fit';
import 'xterm/css/xterm.css';

export function XTermAgent() {
  const terminalRef = useRef<HTMLDivElement>(null);
  const xtermRef = useRef<Terminal>();
  const wsRef = useRef<WebSocket>();

  useEffect(() => {
    if (!terminalRef.current) return;

    // Create terminal
    const term = new Terminal({
      theme: {
        background: '#282a36',
        foreground: '#f8f8f2',
        cursor: '#f8f8f2',
        // Dracula theme colors
      },
      fontSize: 14,
      fontFamily: 'Consolas, monospace',
    });

    const fitAddon = new FitAddon();
    term.loadAddon(fitAddon);
    term.open(terminalRef.current);
    fitAddon.fit();

    xtermRef.current = term;

    // Connect to WebSocket
    const ws = new WebSocket('ws://localhost:8000/ws/chat');
    
    ws.onopen = () => {
      term.writeln('✅ Connected to agent');
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      
      if (data.type === 'agent_response' || data.type === 'command_result') {
        // Write directly to terminal (handles ANSI automatically!)
        term.write(data.content || data.result);
        term.writeln('');
      }
    };

    wsRef.current = ws;

    // Handle user input
    term.onData((data) => {
      if (data === '\r') {
        // Enter key - send to agent
        const line = getCurrentLine();
        ws.send(JSON.stringify({ message: line }));
        term.writeln('');
      } else {
        term.write(data);
      }
    });

    return () => {
      term.dispose();
      ws.close();
    };
  }, []);

  return <div ref={terminalRef} className="h-full w-full" />;
}
*/

// ============================================
// REST API Alternative (No WebSocket)
// ============================================

export async function executeCommand(command: string, args: string[] = []) {
  const response = await fetch('http://localhost:8000/api/command', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ command, args }),
  });

  const data = await response.json();
  
  if (data.ansi) {
    // Convert ANSI to HTML
    return {
      ...data,
      resultHtml: ansiConverter.toHtml(data.result),
    };
  }

  return data;
}

// Usage:
// const result = await executeCommand('cd', ['langchain-agent-base/src']);
// console.log(result.resultHtml); // Rendered HTML with colors

// ============================================
// Tab Autocomplete Hook
// ============================================

export function useAutocomplete(apiUrl = 'http://localhost:8000') {
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);

  const getSuggestions = async (text: string, cursorPosition?: number) => {
    setLoading(true);
    try {
      const response = await fetch(`${apiUrl}/api/autocomplete`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          text,
          cursor_position: cursorPosition ?? text.length,
        }),
      });

      const data = await response.json();
      setSuggestions(data.suggestions || []);
      return data;
    } catch (error) {
      console.error('Autocomplete error:', error);
      setSuggestions([]);
      return { suggestions: [] };
    } finally {
      setLoading(false);
    }
  };

  const clearSuggestions = () => setSuggestions([]);

  return { suggestions, loading, getSuggestions, clearSuggestions };
}

// ============================================
// Autocomplete Input Component
// ============================================

export function AutocompleteInput({
  onSubmit,
  placeholder = 'Type your message...',
}: {
  onSubmit: (text: string) => void;
  placeholder?: string;
}) {
  const [input, setInput] = useState('');
  const [selectedIndex, setSelectedIndex] = useState(0);
  const { suggestions, getSuggestions, clearSuggestions } = useAutocomplete();
  const inputRef = useRef<HTMLInputElement>(null);

  // Debounced autocomplete
  useEffect(() => {
    const timer = setTimeout(() => {
      if (input) {
        getSuggestions(input, inputRef.current?.selectionStart || input.length);
      } else {
        clearSuggestions();
      }
    }, 200); // Wait 200ms after user stops typing

    return () => clearTimeout(timer);
  }, [input]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (suggestions.length > 0) {
      // Tab or Right Arrow - accept suggestion
      if (e.key === 'Tab' || e.key === 'ArrowRight') {
        e.preventDefault();
        acceptSuggestion(suggestions[selectedIndex]);
        return;
      }

      // Arrow Down - next suggestion
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setSelectedIndex((prev) => (prev + 1) % suggestions.length);
        return;
      }

      // Arrow Up - previous suggestion
      if (e.key === 'ArrowUp') {
        e.preventDefault();
        setSelectedIndex((prev) => (prev - 1 + suggestions.length) % suggestions.length);
        return;
      }

      // Escape - clear suggestions
      if (e.key === 'Escape') {
        clearSuggestions();
        return;
      }
    }

    // Enter - submit
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const acceptSuggestion = (suggestion: string) => {
    setInput(suggestion);
    clearSuggestions();
    inputRef.current?.focus();
  };

  const handleSubmit = () => {
    if (input.trim()) {
      onSubmit(input);
      setInput('');
      clearSuggestions();
    }
  };

  return (
    <div className="relative">
      {/* Input */}
      <input
        ref={inputRef}
        type="text"
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        className="w-full bg-gray-800 text-white px-4 py-2 outline-none font-mono"
      />

      {/* Autocomplete Dropdown */}
      {suggestions.length > 0 && (
        <div className="absolute bottom-full left-0 right-0 mb-1 bg-gray-800 border border-gray-600 rounded max-h-48 overflow-y-auto">
          {suggestions.map((suggestion, index) => (
            <div
              key={index}
              onClick={() => acceptSuggestion(suggestion)}
              className={`px-4 py-2 cursor-pointer font-mono text-sm ${
                index === selectedIndex
                  ? 'bg-blue-600 text-white'
                  : 'text-gray-300 hover:bg-gray-700'
              }`}
            >
              {suggestion}
            </div>
          ))}
        </div>
      )}

      {/* Preview (inline suggestion) */}
      {suggestions.length > 0 && (
        <div className="absolute left-0 top-0 px-4 py-2 pointer-events-none font-mono">
          <span className="invisible">{input}</span>
          <span className="text-gray-500">
            {suggestions[selectedIndex].slice(input.length)}
          </span>
        </div>
      )}
    </div>
  );
}

// ============================================
// Complete Terminal with Autocomplete
// ============================================

export function TerminalWithAutocomplete() {
  const { connected, messages, sendMessage } = useAgentWebSocket();

  return (
    <div className="flex flex-col h-screen bg-gray-900">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 font-mono text-sm">
        {messages.map((msg, i) => (
          <div
            key={i}
            dangerouslySetInnerHTML={{ __html: msg }}
            className="whitespace-pre-wrap"
          />
        ))}
      </div>

      {/* Input with Autocomplete */}
      <div className="border-t border-gray-700 p-4">
        <div className="flex gap-2 items-center">
          <span className="text-cyan-400 font-mono">You:</span>
          <AutocompleteInput
            onSubmit={sendMessage}
            placeholder="Type your message or //command... (Tab to autocomplete)"
          />
        </div>
      </div>
    </div>
  );
}
