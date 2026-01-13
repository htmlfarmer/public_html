# OpenAI + Google Gemini PHP Interface (local)

Quick local interface to call both OpenAI Chat API and Google Gemini API from PHP.

**Google Gemini has a free tier** — no credit card required to start.

## Setup

1. Get API keys:
   - **OpenAI**: https://platform.openai.com/api-keys (requires paid account)
   - **Google Gemini (Free)**: https://aistudio.google.com/app/apikeys

2. Export the keys or create a `.env` file (copy from `.env.example`):
   ```bash
   export OPENAI_API_KEY="sk-..."
   export GOOGLE_API_KEY="your_google_key_here"
   ```

## Run locally

```bash
cd /home/asher/public_html/openai
php -S localhost:8000 -t /home/asher/public_html/openai
```

Open http://localhost:8000/index.php in your browser.

## Features

- Switch between OpenAI and Google Gemini in the UI
- Paste API keys directly into the form
- Session-based storage (no file writes)
- Show/hide key toggle for security

## Notes

- This is a minimal example; for production use an official SDK and secure key storage
- Google Gemini uses `gemini-pro` model (free, no quota issues)
- OpenAI uses `gpt-4o` (paid, requires valid billing)
