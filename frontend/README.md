# ASTRA HEALTH frontend

The `frontend` branch's original simulation UI is the default landing page.
It is labeled as a simulation because its readings are generated in the browser.
Use the visible **Canlı backend verilerini aç** link or `/?view=live` for the
FastAPI client, which shows only records from the central `AstraHealth` database.

## Local run

From the repository root, start SQL Server and the API as described in
`backend/README.md`. Then run in `frontend/`:

```bash
npm ci
npm run dev
```

Open `http://127.0.0.1:5173/` for the original interface, then use its live-data
link for the connected panel. Vite proxies `/api/v1` and
`/ws/v1/notifications` to the API at `127.0.0.1:8000`, so the browser uses one
origin and needs no CORS exceptions. The local Vite server opens a seeded
astronaut session automatically; use the header buttons to switch to ground
control. It reads the seed passwords from the ignored repository-root `.env`
on the server side. Passwords are not bundled into the browser or committed.
The temporary access token lives in the browser tab's session storage.
This automatic session route exists only in the local Vite development server
bound to `127.0.0.1`; a production build still requires normal sign-in.

The live panel supports profile and measurement reads, daily check-ins,
physiological entry, analysis job status, alerts, notifications, and Knowledge
Card reads/creation for ground control. The analysis model and clinical threshold
rules are not configured yet. An analysis can therefore finish as
`insufficient_data` without producing a health result or alarm.

The original visual simulation's SANS and emergency screens are demo content
and are not backed by this API.
