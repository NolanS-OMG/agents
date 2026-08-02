# WebSocket Implementation Plan

## Arquitectura

```
Frontend (WebSocket Client)
    ↓
FastAPI WebSocket endpoint (/ws/chat)
    ↓
LLM Provider (streaming mode)
    ↓
Real-time chunks → Frontend
```

## Backend Changes

### 1. WebSocket Route
**Nuevo archivo:** `src/app/api/routes/websocket.py`

```python
from fastapi import WebSocket, WebSocketDisconnect
from src.app.services.agent_router import AgentRouter

@router.websocket("/ws/chat")
async def websocket_chat(
    websocket: WebSocket,
    api_key: str = Query(...),
):
    await websocket.accept()
    
    # Auth via query param
    # Load tenant context
    # Keep connection alive
    
    try:
        while True:
            data = await websocket.receive_json()
            # {"message": "...", "session_id": "..."}
            
            # Stream LLM response
            async for chunk in agent.run_stream(data["message"]):
                await websocket.send_json({
                    "type": "chunk",
                    "content": chunk
                })
            
            await websocket.send_json({"type": "done"})
    except WebSocketDisconnect:
        pass
```

### 2. LLM Provider Streaming
**Modificar:** `src/app/services/llm/openai_compatible.py`

Agregar método `stream()`:

```python
async def stream(
    self,
    messages: list[dict],
    tools: list[dict] | None = None,
) -> AsyncGenerator[str, None]:
    payload = {..., "stream": True}
    
    async with self._client.stream("POST", url, json=payload) as response:
        async for line in response.aiter_lines():
            if line.startswith("data: "):
                chunk = json.loads(line[6:])
                if chunk["choices"][0]["delta"].get("content"):
                    yield chunk["choices"][0]["delta"]["content"]
```

### 3. Agent Router Streaming
**Modificar:** `src/app/services/agent_router.py`

```python
async def run_stream(
    self,
    user_message: str,
    history: list[Message],
) -> AsyncGenerator[str, None]:
    messages = self._build_messages(user_message, history)
    
    async for chunk in self.llm.stream(messages, tools):
        yield chunk
```

## Frontend Changes

### WebSocket Client (TypeScript)

```typescript
class ChatWebSocket {
  private ws: WebSocket;
  private sessionId: string;

  connect(apiKey: string) {
    this.ws = new WebSocket(
      `ws://localhost:8000/ws/chat?api_key=${apiKey}`
    );

    this.ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      
      if (data.type === 'chunk') {
        this.onChunk(data.content);
      } else if (data.type === 'done') {
        this.onComplete();
      }
    };
  }

  sendMessage(message: string) {
    this.ws.send(JSON.stringify({
      message,
      session_id: this.sessionId,
    }));
  }

  onChunk(content: string) {
    // Append to UI
  }

  onComplete() {
    // Finalize message
  }
}
```

## Benefits

✅ **Real-time streaming** - Texto aparece mientras se genera  
✅ **Mejor UX** - Usuario ve progreso inmediato  
✅ **Ahorro tokens** - Conexión persistente reutiliza contexto  
✅ **Interacciones fluidas** - Bi-directional communication  

## Implementation Steps

1. Agregar WebSocket route con auth
2. Implementar streaming en LLM provider
3. Adaptar AgentRouter para streaming
4. Actualizar frontend para usar WS
5. Mantener backward compatibility con POST /chat

## Tool Calling con Streaming

**Opción 1:** Pausar stream, ejecutar tool, resumir
**Opción 2:** Enviar evento especial `{"type": "tool_call", "name": "..."}`

## Session Management

- Mantener sesión en memoria durante conexión WS
- Persistir a Redis solo al desconectar
- Reducir queries a BD

## Next Steps

¿Quieres que implemente esto ahora?
