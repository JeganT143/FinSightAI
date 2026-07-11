# FinSightAI — web console

The Next.js frontend. **Read [DESIGN.md](../../DESIGN.md) first** — every visual
decision (surfaces, tokens, type, motion, streaming state machine) is specified
there, and the implementation follows it.

```bash
npm install
npm run dev     # http://localhost:3000 (backend expected on :8000)
```

Environment:

- `NEXT_PUBLIC_API_URL` — backend URL for the browser (default `http://localhost:8000`)
- `BACKEND_URL` — backend URL for server components (compose sets `http://backend:8000`)
