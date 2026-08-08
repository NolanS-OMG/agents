# Tecnicas para reducir latencia percibida en voz

> Contexto: Pipeline actual STT → LLM → TTS tarda ~7-9s end-to-end.
> El usuario percibe silencio muerto durante ese tiempo.

---

## 1. Sonidos de espera (typing/hold)

**Que es:** Reproducir un loop de audio suave (tecleo, musica ambient, tono de espera) mientras se procesa la respuesta.

**Impacto:** Medio. Reduce la percepcion de espera. El silencio muerto hace que 3s se sientan como 10s.

**Dificultad:** Baja. Es un archivo de audio en loop que se detiene cuando llega la respuesta.

**Quien lo hace:** Intercom, Drift, chatbots bancarios por telefono, IVRs modernos.

**Implementacion:**
- Reproducir audio pregrabado (loop de ~2s) en un thread separado
- Detener cuando el primer byte de respuesta TTS esta listo
- En WebSocket de Twilio: enviar chunks de audio de "hold" mientras se procesa

---

## 2. Muletillas y fillers ("un momento...")

**Que es:** Reproducir frases cortas pregrabadas o sintetizadas que simulan que el agente "piensa", como lo haria un humano.

**Impacto:** Alto. Es la diferencia entre un bot y una conversacion real. Los humanos naturalmente dicen "este...", "a ver...", "dejame ver..." mientras piensan.

**Dificultad:** Baja-Media.

**Quien lo hace:** Bland AI, Retell AI, Vapi, ElevenLabs Conversational AI, Google Duplex.

**Dos approaches:**

### A) Fillers estaticos (facil)
- Banco de audios pregrabados: "Un momento...", "Dejame revisar...", "Claro, ya busco..."
- Se disparan cuando se detecta que la respuesta va a tardar:
  - Tool call (buscar_base_conocimiento → "Dejame buscar eso...")
  - Primera respuesta del LLM tarda >2s
- Audio pregrabado + TTS one-shot para variedad

### B) Fillers dinamicos (medio)
- El LLM genera una primera frase corta rapido ("Claro, deja busco eso")
- Se sintetiza esa frase en streaming mientras el resto sigue generando
- Requiere split del output del LLM en "primer chunk" + "respuesta completa"
- Mas natural pero mas complejo de orquestar

**Implementacion practica (approach A):**
```python
# Detectar si hay tool call en la respuesta
if result.tool_used:
    # Reproducir filler antes de la respuesta final
    play_filler("dejame_revisar.wav")
```

---

## 3. Streaming TTS (text-to-speech por chunks)

**Que es:** En vez de esperar la respuesta completa del LLM para sintetizarla, generar audio por oracion/chunk conforme llegan tokens del LLM.

**Impacto:** Muy alto. Reduce latencia de ~7s (LLM completo + TTS completo) a ~1-2s (primer chunk LLM + primer chunk TTS).

**Dificultad:** Media-Alta.

**Quien lo hace:** Vapi, ElevenLabs, Cartesia, PlayHT, Retell AI, LiveKit Agents.

**Como funciona:**
```
Sin streaming:
  [------ LLM 1.5s ------][------ TTS 5s ------] = 6.5s hasta primer sonido

Con streaming:
  [LLM chunk 1 0.3s][TTS 0.5s] ← primer sonido a 0.8s
  [LLM chunk 2...][TTS chunk 2...]
  [LLM chunk 3...][TTS chunk 3...]
```

**Requisitos:**
- LLM con streaming habilitado (OpenRouter lo soporta via SSE)
- TTS que acepte texto incremental o latencia baja por request
- Buffer inteligente: acumular tokens hasta tener oracion/clause completa antes de enviar a TTS
- Manejo de interrupciones (barge-in): si el usuario habla, cancelar TTS en curso

**Modelos de TTS con baja latencia para streaming:**
- `microsoft/mai-voice-2-flash` — optimizado para low-latency
- Cartesia (no en OpenRouter) — <100ms time-to-first-byte
- ElevenLabs Turbo v2.5 — streaming nativo

**OpenRouter soporta esto?**
- LLM streaming: Si (`stream: true` en chat/completions)
- TTS: No tiene streaming nativo, pero con requests rapidos por oracion se puede simular
- Para streaming real de TTS se necesita un provider dedicado (ElevenLabs, Cartesia, Deepgram)

---

## 4. STT streaming (transcripcion en tiempo real)

**Que es:** Transcribir mientras el usuario habla, no despues.

**Impacto:** Bajo para nuestro caso. Ya usamos VAD (Voice Activity Detection) para detectar fin de turno, asi que el STT empieza inmediatamente despues. El ahorro seria minimo (~200ms).

**Dificultad:** Alta. Requiere WebSocket a un STT que soporte streaming (Deepgram, Google Cloud Speech).

**Quien lo hace:** Google Cloud Speech-to-Text, Deepgram, AssemblyAI (real-time).

**Cuando vale la pena:** Solo si la transcripcion batch es el bottleneck (>2s). En nuestro caso Qwen ASR tarda ~1.9s, que es aceptable.

---

## Resumen y prioridades

| # | Tecnica | Latencia percibida | Esfuerzo | ROI |
|---|---------|-------------------|----------|-----|
| 1 | Fillers estaticos | 7s → 2s percibidos | 2-3h | Altisimo |
| 2 | Sonido de espera | 7s → 4s percibidos | 1h | Alto |
| 3 | TTS streaming | 7s → 1.5s reales | 2-3 dias | Muy alto pero costoso |
| 4 | STT streaming | -200ms | 1-2 dias | Bajo |

**Recomendacion:** Implementar (1) y (2) primero — son 3-4 horas de trabajo y transforman la experiencia. (3) es el siguiente paso si se busca calidad de produccion tipo Bland/Vapi.

---

## Arquitectura propuesta con fillers

```
Usuario habla → VAD detecta fin → STT (1.9s)
                                    ↓
                              [reproducir filler si >1s]
                                    ↓
                              LLM genera (1.3s)
                                    ↓
                              [cortar filler]
                                    ↓
                              TTS sintetiza → reproduce
```

Con streaming futuro:
```
Usuario habla → VAD → STT (1.9s)
                        ↓
                  [filler: "Un momento..."]
                        ↓
                  LLM stream chunk 1 (0.3s) → TTS chunk 1 (0.3s) → reproduce
                  LLM stream chunk 2 → TTS chunk 2 → reproduce (seamless)
```
