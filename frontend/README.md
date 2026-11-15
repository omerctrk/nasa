# ASTRA HEALTH frontend

The running interface retains the frontend branch's AHMS navigation, cosmic
styling, dashboard sections, and 3D anatomy model. Patient records load from
the FastAPI backend and central `AstraHealth` database.
The old simulation code is retained in source but is not loaded at runtime.
Missing measurements, assessments, and alarms are displayed as missing; no
browser-generated values are substituted.
The 3D model is a visual anatomy asset, not a patient measurement. Its region
labels use only stored readings. Radiation, cabin sensor, and similar values
stay empty until a database-backed source exists.

## Local run

From the repository root, start SQL Server and the API as described in
`backend/README.md`. Then run in `frontend/`:

```bash
npm ci
npm run dev
```

Open `http://127.0.0.1:5173/`. Vite proxies `/api/v1` and
`/ws/v1/notifications` to the API at `127.0.0.1:8000`, so the browser uses one
origin and needs no CORS exceptions. The local Vite server opens a seeded
astronaut session automatically; use the header buttons to switch to ground
control. It reads the seed passwords from the ignored repository-root `.env`
on the server side. Passwords are not bundled into the browser or committed.
The temporary access token lives in the browser tab's session storage.
This automatic session route exists only in the local Vite development server
bound to `127.0.0.1`; a production build still requires normal sign-in.

The live panel supports profile and measurement reads, daily check-ins,
weekly and cognitive history, physiological entry, analysis job status, alerts,
notifications, and Knowledge Card reads/creation for ground control. The analysis model and clinical threshold
rules are not configured yet. An analysis can therefore finish as
`insufficient_data` without producing a health result or alarm.

The old SANS and emergency screens are absent from the running app because the
current backend has no data contract for those views.
