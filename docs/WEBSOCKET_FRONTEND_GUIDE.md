# WebSocket Frontend Integration Guide

**Backend Endpoint:** `ws://localhost:8000/ws/chat?api_key={your_key}`  
**Protocol:** WebSocket with JSON messages  
**Última actualización:** 2026-08-02

---

## 🚀 Quick Start

### Connection

```typescript
const ws = new WebSocket(
  `ws://localhost:8000/ws/chat?api_key=sk_portfoli_a7nRq-5SYtNin6Y3YpZVVmW43imdpNPm`
);

ws.onopen = () => console.log('Connected');
ws.onmessage = (event) => handleMessage(JSON.parse(event.data));
ws.onerror = (error) => console.error('WebSocket error:', error);
ws.onclose = () => console.log('Disconnected');
```

### Send Message

```typescript
ws.send(JSON.stringify({
  message: 'Tell me about Nolan',
  session_id: 'optional-session-id',
  language: 'en'
}));
```

---

## 📨 Message Types

### Client → Server

```typescript
{
  message: string,        // Required: user message (1-4096 chars)
  session_id?: string,    // Optional: session identifier
  language?: 'en' | 'es'  // Optional: response language (default: 'en')
}
```

### Server → Client

#### 1. Connected
```json
{
  "type": "connected",
  "session_id": "7e00c968-6ad7-482f-8916-4662ed2f0ec4"
}
```
Sent immediately after connection. Save `session_id` for future messages.

#### 2. Content Chunk
```json
{
  "type": "content",
  "content": "Here's"
}
```
Streamed text chunks. Append to UI as received.

#### 3. Tool Call
```json
{
  "type": "tool_call",
  "name": "buscar_base_conocimiento_extensa",
  "args": {"documentos": ["stack-tecnologico"]}
}
```
AI is calling a tool. Show loading indicator.

#### 4. Tool Result
```json
{
  "type": "tool_result",
  "name": "buscar_base_conocimiento_extensa",
  "content": "{...}"
}
```
Tool execution completed. Continue showing loading.

#### 5. Done
```json
{
  "type": "done",
  "session_id": "7e00c968-6ad7-482f-8916-4662ed2f0ec4"
}
```
Message complete. Hide loading, finalize UI.

#### 6. Error
```json
{
  "type": "error",
  "message": "Rate limit exceeded",
  "retry_after_seconds": 30
}
```
Error occurred. Show error message to user.

---

## 💻 Complete React Example

```typescript
import { useEffect, useRef, useState } from 'react';

interface Message {
  role: 'user' | 'assistant';
  content: string;
}

function ChatComponent() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  
  const wsRef = useRef<WebSocket | null>(null);
  const currentMessageRef = useRef('');

  useEffect(() => {
    // Connect WebSocket
    const ws = new WebSocket(
      `ws://localhost:8000/ws/chat?api_key=sk_portfoli_a7nRq-5SYtNin6Y3YpZVVmW43imdpNPm`
    );

    ws.onopen = () => {
      console.log('WebSocket connected');
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      
      switch (data.type) {
        case 'connected':
          setSessionId(data.session_id);
          break;

        case 'content':
          currentMessageRef.current += data.content;
          // Update UI in real-time
          setMessages(prev => {
            const newMessages = [...prev];
            if (newMessages.length && newMessages[newMessages.length - 1].role === 'assistant') {
              // Update last message
              newMessages[newMessages.length - 1].content = currentMessageRef.current;
            } else {
              // Add new assistant message
              newMessages.push({
                role: 'assistant',
                content: currentMessageRef.current
              });
            }
            return newMessages;
          });
          break;

        case 'tool_call':
          console.log('Tool called:', data.name, data.args);
          setIsStreaming(true);
          break;

        case 'tool_result':
          console.log('Tool result:', data.name);
          break;

        case 'done':
          setIsStreaming(false);
          currentMessageRef.current = '';
          break;

        case 'error':
          console.error('Error:', data.message);
          alert(data.message);
          setIsStreaming(false);
          break;
      }
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };

    ws.onclose = () => {
      console.log('WebSocket disconnected');
    };

    wsRef.current = ws;

    return () => {
      ws.close();
    };
  }, []);

  const sendMessage = () => {
    if (!input.trim() || !wsRef.current || isStreaming) return;

    // Add user message to UI
    setMessages(prev => [...prev, { role: 'user', content: input }]);

    // Send to server
    wsRef.current.send(JSON.stringify({
      message: input,
      session_id: sessionId,
      language: 'en'
    }));

    setInput('');
    setIsStreaming(true);
    currentMessageRef.current = '';
  };

  return (
    <div>
      <div className="messages">
        {messages.map((msg, i) => (
          <div key={i} className={msg.role}>
            {msg.content}
          </div>
        ))}
        {isStreaming && <div className="loading">●</div>}
      </div>
      
      <input
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyPress={(e) => e.key === 'Enter' && sendMessage()}
        disabled={isStreaming}
      />
      <button onClick={sendMessage} disabled={isStreaming}>
        Send
      </button>
    </div>
  );
}
```

---

## 🎯 Vanilla JavaScript Example

```javascript
const API_KEY = 'sk_portfoli_a7nRq-5SYtNin6Y3YpZVVmW43imdpNPm';
let ws = null;
let sessionId = null;
let currentMessage = '';

function connect() {
  ws = new WebSocket(`ws://localhost:8000/ws/chat?api_key=${API_KEY}`);
  
  ws.onopen = () => {
    console.log('Connected');
    document.getElementById('status').textContent = '🟢 Connected';
  };
  
  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    
    switch (data.type) {
      case 'connected':
        sessionId = data.session_id;
        break;
        
      case 'content':
        currentMessage += data.content;
        updateLastMessage(currentMessage);
        break;
        
      case 'done':
        currentMessage = '';
        document.getElementById('send-btn').disabled = false;
        break;
        
      case 'error':
        alert(data.message);
        break;
    }
  };
  
  ws.onclose = () => {
    console.log('Disconnected');
    document.getElementById('status').textContent = '🔴 Disconnected';
  };
}

function sendMessage() {
  const input = document.getElementById('message-input');
  const message = input.value.trim();
  
  if (!message || !ws) return;
  
  addMessage('user', message);
  addMessage('assistant', ''); // Placeholder for streaming
  
  ws.send(JSON.stringify({
    message,
    session_id: sessionId,
    language: 'en'
  }));
  
  input.value = '';
  document.getElementById('send-btn').disabled = true;
}

function addMessage(role, content) {
  const messagesDiv = document.getElementById('messages');
  const msgDiv = document.createElement('div');
  msgDiv.className = `message ${role}`;
  msgDiv.textContent = content;
  messagesDiv.appendChild(msgDiv);
  messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

function updateLastMessage(content) {
  const messages = document.querySelectorAll('.message.assistant');
  if (messages.length) {
    messages[messages.length - 1].textContent = content;
  }
}

// Initialize
connect();
```

---

## ⚠️ Important Notes

### Rate Limiting
- Same limits as HTTP: 1000/hour, 100/minute per session
- Error message includes `retry_after_seconds`

### Connection Management
- WebSocket auto-reconnects on close (implement exponential backoff)
- Session persists across reconnections using `session_id`

### Session Handling
- Save `session_id` from `connected` message
- Include in all subsequent messages
- Omit `session_id` to start new conversation

### Error Handling
```typescript
ws.onerror = (error) => {
  console.error('WebSocket error:', error);
  // Attempt reconnect after 2s
  setTimeout(() => connect(), 2000);
};
```

---

## 🧪 Testing with wscat

Install:
```bash
npm install -g wscat
```

Test connection:
```bash
wscat -c "ws://localhost:8000/ws/chat?api_key=sk_portfoli_a7nRq-5SYtNin6Y3YpZVVmW43imdpNPm"

# Send message:
{"message":"Tell me about Nolan","language":"en"}
```

---

## 📊 Performance Benefits

✅ **Faster responses** - Streaming starts immediately  
✅ **Better UX** - Users see progress in real-time  
✅ **Lower latency** - Persistent connection eliminates HTTP overhead  
✅ **Token efficiency** - Session context maintained in memory  

---

## 🔄 Migration from HTTP

Keep both endpoints active:
- `/ws/chat` - New WebSocket endpoint
- `/api/v1/chat` - Legacy HTTP endpoint (still works)

Frontend can detect WebSocket support:
```typescript
const supportsWebSocket = 'WebSocket' in window;
if (supportsWebSocket) {
  // Use WebSocket
} else {
  // Fallback to HTTP
}
```

---

## 📞 Support

**GitHub:** https://github.com/NolanS-OMG/prototipo-agente  
**Email:** nolan1scott3@gmail.com

---

**Última actualización:** 2026-08-02 03:00 UTC
