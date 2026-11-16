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
- Send a pass to the collector their own way: WhatsApp, text or email (or the
  phone's share menu), choosing the QR pass link or today's six-digit code. It
  opens in the parent's own app with the message ready; ENTRACCESS UK sends
  nothing itself, and only notes which way it went.
- See the contacts the nursery added from their registration form, and remove
  any of them.
- Remove a collector instantly, or issue a new pass and code (the old ones stop at once).
- See every collection of their child, and every refusal.

**Room leaders**
- Scan the collector's pass with the phone camera (or a scanner), or enter
  their code against the child.
- See who the collector is, who authorised them and any note from the parent,
  and anyone the child must **never be released to**.
- **Release**, recording how they confirmed who the collector is (photo ID,
  known to them, or the parent's password), or **refuse** (with a reason).
- Both parents linked to the child are emailed straight away either way.

**Nursery managers**
- Today's releases, refusals and exceptions at the door.
- The full handover record, filterable by date and exportable to CSV.
- Children, parents, staff and who is linked to whom.
- **Nursery contacts**: the people parents named on the registration form,
  added one at a time or imported by CSV (Child, Contact name, Relationship,
  Phone, optional Password; all rows or none, and anyone already there is
  skipped). They become regular collectors, both parents are emailed the
  names, and the manager can send each one their pass.
- **Reports**: a KPI summary for up to a quarter, for all children or one:
  releases, refusals and why, checks the app refused and why, how identity was
  checked, collectors added and removed, passes sent, never-release changes,
  and how many days were reconciled against the register. Exportable to CSV.
- **Evidence pack**: one printable document (save it as PDF) for a period and
  one child or all, for an inspection or a safeguarding review: the summary,
  the never-release list, everyone who could collect, register disagreements
  and the full timeline. Its timeline also downloads as CSV, and each pack is
  logged.
- Remove any collector (for example for a court order or a safeguarding concern).
  Marking a child as left removes every collector for them.
- Keep each child's **never-release list** (court order, safeguarding, a
  parent's request), with a reference and a note. Adding someone removes them
  as a collector at once and stops a parent adding them again; room leaders
  see the list with every check for the child. Ending one keeps the record.
- **Reconcile** a day: import the sign-out register exported from the
  nursery's own system (CSV with the child's name and time signed out, and
  optionally who collected) and see, child by child, where it and the door
  disagree: signed out with no release at the door, released but not signed
  out, a different collector named, times over 15 minutes apart, a name that
  matches no child, or signed out twice. Exportable to CSV. Re-importing a day
  adds a new import; the latest is the one compared.

**ENTRACCESS UK (company portal)**
- Every nursery on one page: children, parents, room leaders, active
  collectors, collections and door exceptions over 30 days, and whether the
  geofence is on. Counts only: no child, parent or collector is ever named.
- Set up a nursery together with its first manager, who then adds everyone else.
- Suspend a nursery (nobody there can sign in, open sessions stop and its
  pass links stop working; nothing is deleted) and reactivate it.
- Operators are a separate kind of account, created from a shell with
  `python -m app.create_operator`, never over the API.

### The website, and three portals

The front page is the public website: how it works, the safeguards, pricing,
questions, a privacy page (`/privacy`) and an enquiry form whose enquiries land
in the company portal (and, if `SUPPORT_EMAIL` is set, in that mailbox). The
form is rate-limited and has a hidden field that traps bots.

**Sign in** leads to `/portals`, which offers the **Parent**, **Nursery** and **Company** portals. Each
goes to the same sign-in, and the account decides what opens: `/parent`,
`/admin` (managers) or `/door` (room leaders), and `/company`.

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
- **A name on the never-release list is refused at the door** even if a
  collector of that name somehow survives, and again at the moment of release.
  Names are compared ignoring case, accents, punctuation, word order and
  middle names, but never on a first name alone.
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
| Company (operator) | operator@demo.example.com |
| Manager | admin@demo.example.com    |
| Room leader | staff@demo.example.com |
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
npm run dev          # http://localhost:5180, proxies /api to :8000 (or $API_PROXY)
```

## Checks

```bash
cd backend && .venv/bin/ruff check app tests && .venv/bin/mypy app && .venv/bin/pytest
cd frontend && npm run typecheck && npm test && npm run build
```

## Production

Collector's domain is **entraccess-collector.co.uk**, and its mailbox is
**support@entraccess-collector.co.uk** (Zoho Mail UK). In production set
`APP_BASE_URL=https://entraccess-collector.co.uk`, `EMAIL_ENABLED=true`, the
Zoho SMTP values and `SUPPORT_EMAIL` shown in `.env.example`.

Set `ENVIRONMENT=production`, a `DATABASE_URL` for Postgres, and long random
`SECRET_KEY` and `PASS_SIGNING_KEY` values. The app refuses to start in
production with the development keys. Changing `PASS_SIGNING_KEY` invalidates
every pass and code in circulation.

Before any pilot with real children's data: complete a data protection impact
assessment, register with the ICO, and sign a pilot agreement with the setting.

## Maintenance jobs

Run these on the live service as a Render one-off job
(entraccess-collector-api → Jobs), or by hand in its Shell tab. Write a job's
command on one line with no quote marks: Render passes quotes through
literally, so a command such as `python -c "..."` runs nothing and still
reports success.

| Job | Command |
|---|---|
| Check the mail settings work | `python -m app.maintenance.send_test_email --to support@entraccess-collector.co.uk` |
| List what a test run left behind | `python -m app.maintenance.purge_test_accounts --domain collector-e2e.example.com` |
| Remove it | the same, with `--yes` on the end |
| Add a company-portal operator | `python -m app.create_operator --email you@entraccess-collector.co.uk --name "Your Name"` in the **Shell tab** (it asks for the password) |

`send_test_email` exits with an error when the message is refused or mail is
switched off, so a failed send shows as a failed job. `purge_test_accounts`
only accepts a reserved test domain (example.com and its subdomains, `.test`,
`.invalid`), removes a nursery only when every account in it is at that
domain, and stops if more than 20 accounts match.

## Layout

```
backend/   FastAPI, SQLAlchemy 2 (async), Alembic, Postgres or SQLite
  app/collection.py   the rules: authorise, revoke, reissue, check, decide, restrict
  app/reconcile.py    reading a register export and comparing it with the door
  app/names.py        when two written names are the same person
  app/passes.py       signed passes and daily codes
  app/routers/        auth, parent, door, admin, public pass page
frontend/  React, TypeScript, Vite, Tailwind
```
