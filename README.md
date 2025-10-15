# Alcient (Local Demo)

A fast iteration playground for Alcient's storyboarding workflow. The app pairs a Flask backend with a Vite/React frontend to generate scripts, assemble scenes, pull stock media, and render short-form videos.

## Key Features
- **Prompt or manual scripting** – generate a storyboard with GPT-4o or paste your own script. Manual scripts are enriched through an LLM pass (`/api/scenes/enrich`) that returns scene keywords and future-facing image prompts before stock media is fetched.
- **Smart media selection** – enriched keywords (or a local fallback when the LLM is unavailable) drive `/api/media/suggest`, pulling relevant Pexels clips that can be swapped at any time.
- **Render controls** – start a render, then pause or stop it mid-flight from the preview panel. Cancels take effect immediately and free the queue.
- **Multi-aspect support** – landscape, portrait, and square layouts with per-scene previews.

## Prerequisites
- Python 3.10+
- Node.js 18+ and npm
- FFmpeg & FFprobe available on `PATH` (used by the renderer)
- API keys:
  - `OPENAI_API_KEY` for narration and storyboard generation
  - `PEXELS_API_KEY` for stock video lookup

## Environment Setup
Create a `.env` file in both `backend/` and `frontend/` (if needed) with the following entries:

```
OPENAI_API_KEY=sk-your-key
PEXELS_API_KEY=your-pexels-key
VITE_BACKEND=http://localhost:5000
```

The backend reads `OPENAI_API_KEY` and `PEXELS_API_KEY`; the frontend uses `VITE_BACKEND` to locate the API server.

## Run the Backend
```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py
```
The API listens on `http://localhost:5000` by default.

## Run the Frontend
```bash
cd frontend
npm install
npm run dev
```
Open `http://localhost:5173` in your browser to use the editor.

## Useful Commands
- `npm run build` (frontend) – production bundle
- `npm run lint` (frontend) – ESLint over the React codebase
- `python -m backend.tests.<module>` – run any backend smoke tests you add

## Workflow Tips
- Paste a script in **Enter script** mode and click **Apply script**. Scripts up to ~4 000 characters (~5 minutes of narration) are accepted; longer drafts should be trimmed before upload. After the LLM enrichment step, the app auto-suggests up to eight stock clips—watch the “Optimizing scene keywords…” and “Selecting stock clips…” notices in the storyboard header.
- Start a render from the storyboard. While it runs, the preview pane shows **Stop render** and **Pause render** controls. Use **Regenerate video** to resume after a pause or after edits.
- Replace clips inline using the scene card’s image icon. Suggestions come from the same `/api/media/suggest` endpoint, so keywords stay consistent.

Happy editing! Feel free to file issues or extend the demo with new render targets, audio models, or media providers.
