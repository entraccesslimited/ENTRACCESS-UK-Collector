# ENTRACCESS UK Collector

**Authorised child collection for UK nurseries. Every handover authorised, checked and logged.**

Parents authorise who may collect their child. Staff check that authorisation at
the door. The nursery keeps a clear, uneditable record of every handover.

It works alongside the nursery management system a setting already uses. It
does not replace registers, learning journals or staff judgement.

## What it does

**Parents**
- Authorise a **one-off** collector (one collection, then the pass stops) or a
  **regular** collector (any day in a window, with a new code each day).
- Share a pass with the collector: a link that shows a QR code, plus a six-digit
  code for a collector without a phone.
- Remove a collector instantly, or issue a new pass and code (the old ones stop at once).
- See every collection of their child, and every refusal.

**Door staff**
- Scan the collector's pass with the phone camera (or a scanner), or enter
  their code against the child.
- See who the collector is, who authorised them and any note from the parent,
  then **release** or **refuse** (with a reason).
- Both parents linked to the child are emailed straight away either way.

**Nursery managers**
- Today's releases, refusals and exceptions at the door.
- The full handover record, filterable by date and exportable to CSV.
- Children, parents, staff and who is linked to whom.
- Remove any collector (for example for a court order or a safeguarding concern).
  Marking a child as left removes every collector for them.

## How it keeps children safe

- **Nothing secret is stored.** A pass (`CP1.<payload>.<signature>`) is signed
  with a key derived for each nursery alone, so one nursery's pass never works at
  another. It names an authorisation and a version, and carries no name, child or
  date. Whether it is still good is always decided by the database at the door.
- **Codes are checked against one child, never the whole nursery,** and code
  entry for a child pauses after 5 wrong tries in 15 minutes.
- **A release is re-checked at the moment it happens.** A collector removed
  while standing at the door is not released.
- **One-off passes cannot be reused.** The pass stops when the child is released.
- **Every check is recorded, whatever its answer,** and handovers are
  append-only. Names are copied into the record, so it reads the same after a
  collector is removed or a member of staff leaves.
- **No photos of children, no biometrics.** Only what is needed to authorise a
  collection is held.
- Sessions are HttpOnly, SameSite=Strict cookies; changes require a request
  header a cross-site form cannot send; sign-in is rate-limited; CSV exports are
  protected against spreadsheet formula injection.

## Run it

You need Docker.

```bash
docker compose up --build
docker compose exec api python -m app.seed
```

Open <http://localhost:8090> and sign in with any demo account (password
`demo-password-123`, demo data only):

| Role    | Email                     |
| ------- | ------------------------- |
| Manager | admin@demo.example.com    |
| Staff   | staff@demo.example.com    |
| Parent  | parent@demo.example.com   |

Emails sent in development land in Mailpit at <http://localhost:8026>.

### Share it over Tailscale (not only localhost)

```bash
TS_SOCKET=~/.tailscale/ts.sock scripts/tailnet.sh   # TS_SOCKET only if tailscaled runs with a custom socket
docker compose --env-file .env.tailnet -f docker-compose.yml -f docker-compose.tailnet.yml exec api python -m app.seed
```

Runs a separate `staging` stack (real random keys in the gitignored
`.env.tailnet`, Secure cookies) and publishes it with Tailscale Funnel at
`https://<machine>.<tailnet>.ts.net:10000`. Shared pass links use that address,
so a collector can open theirs on their own phone. `scripts/tailnet.sh stop`
takes it down. It is reachable only while this machine is on: for demos and
pilots, never real children's data.

### Without Docker

```bash
cd backend
python3.12 -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/alembic upgrade head
.venv/bin/python -m app.seed
.venv/bin/uvicorn app.main:app --port 8000

cd ../frontend
npm install
npm run dev          # http://localhost:5180, proxies /api to :8000
```

## Checks

```bash
cd backend && .venv/bin/ruff check app tests && .venv/bin/mypy app && .venv/bin/pytest
cd frontend && npm run typecheck && npm test && npm run build
```

## Production

Set `ENVIRONMENT=production`, a `DATABASE_URL` for Postgres, and long random
`SECRET_KEY` and `PASS_SIGNING_KEY` values. The app refuses to start in
production with the development keys. Changing `PASS_SIGNING_KEY` invalidates
every pass and code in circulation.

Before any pilot with real children's data: complete a data protection impact
assessment, register with the ICO, and sign a pilot agreement with the setting.

## Layout

```
backend/   FastAPI, SQLAlchemy 2 (async), Alembic, Postgres or SQLite
  app/collection.py   the rules: authorise, revoke, reissue, check, decide
  app/passes.py       signed passes and daily codes
  app/routers/        auth, parent, door, admin, public pass page
frontend/  React, TypeScript, Vite, Tailwind
```
