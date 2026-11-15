# ASTRA HEALTH

ASTRA HEALTH is a decision support system that monitors astronaut health during
long-duration space missions. It collects physiological measurements, daily
self-reports and cognitive test results, compares each astronaut with their own
history, and explains any deviation in plain language using knowledge cards drawn
from NASA sources. It does not diagnose; it informs the astronaut and ground control
so that people can decide.

This document explains how to start the system, how to use it, and how to read its
output.

> All data in this repository is synthetic and for demonstration only. Thresholds
> and decision limits are demo values, not clinical reference ranges.

## Contents

1. [How it works](#1-how-it-works)
2. [Requirements](#2-requirements)
3. [Starting the system](#3-starting-the-system)
4. [Using the system](#4-using-the-system)
5. [Interpreting the results](#5-interpreting-the-results)
6. [Troubleshooting](#6-troubleshooting)
7. [Repository layout](#7-repository-layout)

## 1. How it works

```
measurements + daily check-ins + cognitive tests
                    |
                    v
   compare today with the astronaut's own previous days   (personal baseline)
   compare today with fixed safety limits                 (thresholds)
                    |
                    v
   select matching knowledge cards (76 cards from NASA reports and standards)
                    |
                    v
   local language model writes a short summary and card explanations
                    |
                    v
   result + recommendations -> astronaut panel, alert -> ground control
```

The decision (risk level, selected cards, recommendations) is made by deterministic
code. The language model only writes the explanation. If the model is unreachable,
the same decision is still produced and the alert is not lost.

| Part | Technology |
|---|---|
| Interface | React, TypeScript, Vite, Tailwind CSS, Recharts, three.js |
| API and worker | Python, FastAPI, SQLAlchemy, Alembic |
| Database | Microsoft SQL Server 2022 (Docker) |
| Language model | Qwen3 14B, run locally with Ollama (optional) |

## 2. Requirements

- **Docker Desktop**, running
- **Node.js 22 LTS or newer** (with npm)
- **Git**
- **Ollama** with the `qwen3:14b` model, only if you want AI-written explanations.
  Without it the system still works and falls back to rule-based summaries.

The one-click launcher is written for Windows. On macOS or Linux use the manual
steps in section 3.3.

## 3. Starting the system

### 3.1 Create the `.env` file (first time only)

Copy the template to the repository root and fill in the empty values:

```
copy backend\.env.example .env
```

| Variable | What to put |
|---|---|
| `MSSQL_SA_PASSWORD` | SQL Server admin password. At least 8 characters with upper case, lower case, digits or symbols |
| `ASTRA_APP_DB_PASSWORD` | Password for the limited account the API uses |
| `ASTRA_EVAL_DB_PASSWORD` | Password for the evaluation account |
| `JWT_SECRET` | A long random string. Generate one with `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `SEED_ASTRONAUT_PASSWORD` | Login password for the demo astronaut accounts |
| `SEED_GROUND_PASSWORD` | Login password for the demo ground control account |
| `LLM_BASE_URL` | Leave empty to run without the model. With Ollama on the same computer: `http://host.docker.internal:11434` |
| `LLM_MODEL` | `qwen3:14b` (default) |

`.env` is ignored by Git. Never commit it.

### 3.2 Optional: prepare the language model

```
ollama pull qwen3:14b
```

Make sure Ollama is running before you start the system, and that `LLM_BASE_URL`
is set in `.env`.

### 3.3 Start

**Windows:** double-click `baslat.cmd`.

It runs five steps and then opens the browser:

1. Starts the database and the API in Docker
2. Applies database migrations
3. Loads the dictionary, the mission and the demo accounts
4. Aligns the demo calendar so that mission day 74 is today, then loads the
   synthetic data for both astronauts
5. Starts the interface

When it finishes:

- Interface: http://127.0.0.1:5173/
- API documentation: http://127.0.0.1:8001/docs

The first start takes several minutes because Docker images are built and npm
packages are installed.

**macOS / Linux (manual):**

```bash
docker compose up -d api
docker compose run --rm migrate
docker compose run --rm seed
docker compose run --rm migrate python -m scripts.realign_demo --apply
docker compose run --rm seed python -m scripts.seed_physiological --apply
docker compose run --rm migrate python -m scripts.refresh_demo_profile --astronaut A009 --apply
docker compose run --rm seed python -m scripts.demo_data
docker compose run --rm seed python -m scripts.seed_physiological --astronaut A009 --apply
cd frontend && npm install && npm run dev
```

On Apple Silicon, uncomment the `platform: linux/amd64` line in
`docker-compose.yml` and enable Rosetta emulation in Docker Desktop.

### 3.4 Stop

Press `Ctrl+C` in the launcher window, then double-click `durdur.cmd`
(or run `docker compose stop`). Data is kept. To erase everything and start from
an empty database, run `docker compose down -v`.

## 4. Using the system

### 4.1 Accounts

The local interface signs in automatically as astronaut A007. No password has to
be typed during a local demo.

| Account | Role | Demo story |
|---|---|---|
| A007 (`astronaut@astra.local`) | Astronaut | Slow decline over the last 14 days: shorter sleep, lower mood, slower reactions; heart rate, blood pressure, glucose, temperature and cabin CO2 rise |
| A009 (`astronaut2@astra.local`) | Astronaut | Sudden event in the last 3 days: blood oxygen falls below the limit, heart rate and blood pressure drop; sleep, mood and cognition stay normal |
| `kule@astra.local` | Ground control | Sees the whole crew, acknowledges and closes alerts, manages knowledge cards |

**Switching accounts:** click the astronaut card at the bottom left of the sidebar
and pick another crew member. The page reloads with that person's data.

**Adding an account:** add a line to `backend/config/demo-accounts.json` and run
the launcher again. The new account appears in the list automatically. It will
have no measurements until data is entered or a profile is defined for it in
`backend/scripts/seed_behavioral.py` and `backend/scripts/seed_physiological.py`.

### 4.2 Pages

| Page | What you do there |
|---|---|
| Dashboard | See current vitals, the latest analysis result and any open alert. Start an analysis with **Analyze** |
| Body 3D | Rotate the anatomy model and click a body region to see the measurements linked to it |
| Tests | Take the reaction time (PVT) and mental rotation tests |
| Behavior | Fill in the daily check-in and the weekly questionnaire, and review their history |
| Reports | View measurement trends over time |
| Settings | Change language (Turkish / English), theme and sound |

### 4.3 A typical demo

1. Open the dashboard as A007 and press **Analyze**. Wait for the status to reach
   completed. With the model enabled this can take up to a few minutes.
2. Read the result card: level, summary, deviating measurements, recommendations.
3. Switch to A009 from the bottom-left crew list and press **Analyze** again.
4. Compare the two results. The findings, the cited cards and the wording differ
   because the underlying data differs.

## 5. Interpreting the results

### 5.1 Result levels

| Level | Meaning | What happens |
|---|---|---|
| **Normal** | Today's values agree with the astronaut's previous days and with the safety limits | No alert |
| **Watch** | At least one measurement deviates from the personal baseline or crosses a limit | A warning alert is created |
| **Review · escalate** | A strong deviation, a finding with no matching knowledge card, or a rule that always escalates (for example low blood oxygen) | A warning alert is created and the first recommendation is to notify the flight physician |
| **Insufficient data** | There is no measurement for today, or nothing to compare it with | No verdict is given. This is not the same as "normal" |

### 5.2 Two kinds of findings

**Personal baseline.** Today's value is compared with the average of the same
astronaut's earlier days. The distance is expressed as a z-score: how many
standard deviations today is from that person's usual value.

- |z| of 2.0 or more: deviation (watch)
- |z| of 3.0 or more: strong deviation (escalate)
- At least 14 earlier days are needed. With fewer, no verdict is given for that
  measurement.

Example: "heart rate today 88.6 BPM; average of the previous 73 days 73.7
(z = 4.13, high)" means the value is far above what is usual for this astronaut,
even if it would look acceptable for the general population.

**Safety thresholds.** Fixed limits that apply to everyone, defined in
`backend/config/thresholds.json`. Examples: blood oxygen below 95 %, eye pressure
above 21 mmHg, cabin CO2 above 4.0 mmHg.

A measurement can appear under both. The direction (high or low) is always taken
from the comparison with the astronaut's own history.

### 5.3 Parts of a result

| Part | Source | How to read it |
|---|---|---|
| Summary | Language model (or rule-based text if the model is off) | A short description of what changed today |
| Deviating measurements | Code | Today's value, the personal baseline, the z-score and any limit crossed |
| Explanations | Language model, based on the selected cards | Why the change may matter, with the source of each card |
| Recommendations | Approved text on the knowledge cards | Concrete actions. The model does not write or choose these |
| Unmatched findings | Code | Deviations for which no card exists. These always go to the flight physician |

Each explanation and recommendation lists the card it comes from, with the title
and link of the original NASA document.

### 5.4 Reading the vitals on the dashboard

- A value marked as out of range has crossed a configured threshold.
- If no threshold exists for a measurement its status is shown as unknown, not as
  normal.
- Values labelled synthetic come from the demo generator, not from a sensor.

### 5.5 Limits you should keep in mind

- The system is a decision support tool. It does not diagnose and does not replace
  a physician.
- Thresholds and z-score limits are demonstration values.
- Behavioral measurements have no fixed thresholds; they are judged only against
  the personal baseline.
- A language model can phrase things imperfectly. The numbers, the level and the
  recommendations do not come from the model, so they are not affected.
- Alerts are closed by ground control, not by the astronaut.

## 6. Troubleshooting

| Problem | What to do |
|---|---|
| `.env dosyası bulunamadı` | Create `.env` in the repository root (section 3.1) |
| Launcher stops at step 1 | Make sure Docker Desktop is running, then start again |
| Port 5173 is in use | Close the other program using it, or run `durdur.cmd` and start again |
| Interface shows "Backend bağlantısı kurulamadı" | The API is not up yet. Check `docker compose ps` and `docker compose logs api` |
| Analysis ends as insufficient data | Today has no measurements. Run the launcher again so the calendar is aligned to today |
| The summary looks generic and mentions no cards | The model was not reached and the rule-based fallback was used. Check that Ollama is running and `LLM_BASE_URL` is set, then restart the API |
| Only one astronaut in the crew list | Run the launcher again so the second account is created, and check that `SEED_GROUND_PASSWORD` is set in `.env` |
| Yellow warning "takvim hizalanmadı" | A record exists after mission day 74. The demo still opens with the existing calendar |

Useful commands:

```bash
docker compose ps                 # which services are running
docker compose logs -f api        # API and worker log
docker compose run --rm -e RUN_DB_TESTS=1 api pytest tests -q   # backend tests
```

## 7. Repository layout

| Path | Contents |
|---|---|
| `backend/` | API, analysis worker, database models, migrations, seed scripts, tests |
| `backend/config/` | Knowledge cards, thresholds, baseline policy, demo accounts |
| `frontend/` | Web interface |
| `LLM/` | Stand-alone copy of the card recommender and its scenario tests |
| `contracts/`, `docs/` | API contracts and design notes |
| `tests/e2e/` | End-to-end scenarios run in an isolated Docker stack |
| `transfer/` | Tools for moving the database content to another installation |
| `baslat.cmd`, `durdur.cmd` | One-click start and stop (Windows) |

More detail for developers is in `backend/README.md` and `frontend/README.md`.
