# ASTRA HEALTH frontend

The `frontend` branch UI is included here. The default screen is the live FastAPI
client. It shows only records returned by the central `AstraHealth` database.
The older simulation UI is available only with `VITE_USE_MOCK=true`.

## Local run

From the repository root, start SQL Server and the API as described in
`backend/README.md`. Then run in `frontend/`:

```bash
npm ci
npm run dev
```

Open `http://127.0.0.1:5173/`. Vite proxies `/api/v1` and
`/ws/v1/notifications` to the API at `127.0.0.1:8000`, so the browser uses one
origin and needs no CORS exceptions. Sign in with the existing seeded astronaut
or ground-control account. No passwords are stored in the repository; the access
token lives in the browser tab's session storage and is removed on sign-out.

The live panel supports profile and measurement reads, daily check-ins,
physiological entry, analysis job status, alerts, notifications, and Knowledge
Card reads/creation for ground control. The analysis model and clinical threshold
rules are not configured yet. An analysis can therefore finish as
`insufficient_data` without producing a health result or alarm.

Use `VITE_USE_MOCK=true npm run dev` only for the original visual simulation.
Its SANS and emergency screens are demo content and are not backed by this API.
