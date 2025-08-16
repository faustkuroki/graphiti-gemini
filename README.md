# Graphiti + Gemini (Dokploy)

Рабочий пример API-сайдкара на FastAPI с Graphiti и Google Gemini.

## Быстрый старт

1) Создай `.env` на основе `.env.example`
2) Запусти стек через Dokploy (или Docker Compose):
   - В Dokploy: импортируй `dokploy.yaml`, задай переменные окружения из `.env`
   - В Docker Compose: `docker compose -f dokploy.yaml up -d --build`

3) Проверка:
   - Health: `curl -s http://localhost:8000/healthz`
   - LLM: `curl -s "http://localhost:8000/ask?question=Привет"`
   - Embed: `curl -s "http://localhost:8000/embed?text=Проверка"`
   - Rerank: `curl -s "http://localhost:8000/rerank?query=экзамен&documents=текст1||текст2"`

### Замечания по доке

- Graphiti по умолчанию использует OpenAI — в этом примере мы **явно** передаём Gemini-клиенты, поэтому `OPENAI_API_KEY` не нужен.  
- Установка экстрой Gemini: `pip install "graphiti-core[google-genai]"`.  
- Требования: Python ≥ 3.10, Neo4j 5.26+.  
- Отключить телеметрию: `GRAPHITI_TELEMETRY_ENABLED=false`.  
См. официальную документацию и README.
