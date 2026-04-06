# VII Two — Feature Gap vs DecisionsAI

## LLM Providers
| Provider | DecisionsAI | VII | Priority |
|----------|------------|-----|----------|
| Ollama (local) | Yes | No | HIGH — free, private |
| OpenAI/GPT | Yes | No | MED |
| Anthropic/Claude | Yes | Yes | Done |
| Google Gemini | Yes | No | LOW |
| Groq | Yes | No | LOW |
| OpenRouter | Yes | No | MED — access to all models |
| KiloCode | Yes | No | LOW |

## TTS (Voice Output)
| Engine | DecisionsAI | VII | Priority |
|--------|------------|-----|----------|
| Kokoro (local) | Yes | Yes | Done |
| ElevenLabs (cloud) | Yes | No | HIGH — premium voice quality |
| OpenAI TTS | Yes | No | MED |
| Coqui (local) | Yes | No | LOW |

## STT (Voice Input)
| Engine | DecisionsAI | VII | Priority |
|--------|------------|-----|----------|
| Whisper.cpp (local) | Yes | Yes | Done |
| Vosk (local) | Yes | No | LOW |
| OpenAI Whisper (cloud) | Yes | No | MED |
| AssemblyAI | Yes | No | LOW |

## Voice Modes
| Mode | DecisionsAI | VII | Priority |
|------|------------|-----|----------|
| Push-to-talk (click) | Yes | Yes | Done |
| Hands-free (VAD) | Yes | Yes | Done |
| Dictation mode | Yes | No | HIGH — type what you say |
| Record macro | Yes | No | MED |

## Computer Control
| Action | DecisionsAI | VII | Priority |
|--------|------------|-----|----------|
| Open/close apps | Yes | Yes | Done |
| Type text | Yes | Yes | Done |
| Key combos | Yes | Yes | Done |
| Click at coords | Yes | Yes | Done |
| Scroll | Yes | No | HIGH |
| Read clipboard | Yes | Yes | Done |
| Screenshot | Yes | Yes | Done |
| Mouse movement | Yes | No | MED |
| Window management | Yes | Partial | MED |
| Volume control | Yes | Yes | Done |

## Settings UI
| Setting | DecisionsAI | VII | Priority |
|---------|------------|-----|----------|
| General settings page | Yes | No | HIGH |
| LLM model selection | Yes | No | HIGH |
| TTS voice selection | Yes | No | HIGH |
| Audio input/output device | Yes | No | HIGH |
| Playback speed | Yes | No | MED |
| Sphere/orb size | Yes | Partial (skin) | Done |
| Skin/avatar selection | Yes | Yes | Done |
| API key management | Yes | No | HIGH |
| Third-party integrations | Yes | No | MED |
| Advanced settings | Yes | No | LOW |
| Activity log viewer | Yes | No | MED |

## Web UI Pages
| Page | DecisionsAI | VII | Priority |
|------|------------|-----|----------|
| Settings panel | Yes | No | HIGH |
| Chat history | Yes | No | HIGH |
| Actions editor | Yes | No | MED |
| Snippets manager | Yes | No | MED |
| Projects panel | Yes | No | LOW |
| Kanban board | Yes | No | LOW |
| Step Runner (workflows) | Yes | No | LOW |
| API docs | Yes | No | LOW |

## Right-Click Menu
| Item | DecisionsAI | VII | Priority |
|------|------------|-----|----------|
| Listen toggle | Yes | No | HIGH |
| Hands-free toggle | Yes | Yes | Done |
| Dictation mode | Yes | No | HIGH |
| Record macro | Yes | No | MED |
| New chat | Yes | No | HIGH |
| Chat history | Yes | No | HIGH |
| Actions | Yes | No | MED |
| Snippets | Yes | No | MED |
| Change skin | Yes | Yes | Done |
| Preferences | Yes | No | HIGH |
| Restart | Yes | No | MED |

## Integrations
| Integration | DecisionsAI | VII | Priority |
|-------------|------------|-----|----------|
| Telegram remote | Yes | Partial (URL) | HIGH |
| Trello | Yes | No | LOW |
| Google (OAuth) | Yes | No | MED |

## Other
| Feature | DecisionsAI | VII | Priority |
|---------|------------|-----|----------|
| One-line installer | Yes | No | HIGH |
| Cross-platform | Yes | No (Mac only) | MED |
| Echo cancellation | Yes | No | HIGH |
| Conversation history DB | Yes | No | HIGH |
| File drop support | Yes | No | MED |
| Vision (screenshot analysis) | Yes | No | HIGH |
| 7 avatar skins | Yes | 3 skin configs | MED |

## Summary — HIGH Priority Items to Build Next
1. Settings web UI (model selection, voice, API keys, audio device)
2. Dictation mode (type what you say — basic VII Zero feature)
3. Chat history with persistence
4. Conversation DB (SQLite)
5. Vision/screenshot analysis
6. Echo cancellation
7. Ollama support (local, free LLM)
8. ElevenLabs TTS option
9. One-line installer
10. Proper right-click menu (listen, dictation, new chat, preferences)
