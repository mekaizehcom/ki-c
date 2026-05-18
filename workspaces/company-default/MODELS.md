# MODELS.md

## default-fast

Zweck:
Schnelle, einfache Aufgaben.

Provider:
- openai/gpt-4o-mini
- anthropic/claude-haiku
- deepseek/deepseek-chat

---

## default-balanced

Zweck:
Normale Firmenarbeit (Zusammenfassungen, Dokumentanalyse, Assistenz).

Provider:
- openai/gpt-4.1
- anthropic/claude-sonnet
- deepseek/deepseek-chat

---

## strong-reasoning

Zweck:
Komplexe Aufgaben (Serveranalyse, Architektur, Sicherheitsbewertung).

Provider:
- anthropic/claude-sonnet
- openai/gpt-4.1
- deepseek/deepseek-reasoner

---

## code-premium

Zweck:
Code- und Architekturanalyse.

Provider:
- anthropic/claude-sonnet
- deepseek/deepseek-reasoner

---

## local-private

Zweck:
Sensible Daten und lokale Verarbeitung.

Endpoint:
- http://model-node-1.internal:11434
- http://model-node-2.internal:8000

Provider:
- ollama/qwen
- ollama/llama
- vllm/mistral
