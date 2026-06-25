# Hermes Agent — Autonomous Business Development Agent

Multi-agent BD platform with **PostgreSQL** for CRM, long-term memory, and follow-up automation. Exposed via MCP for Cursor and Claude Desktop.

## Features

- **Company research** — Research agent profiles target companies
- **Decision-maker discovery** — Finds economic buyers and influencers
- **Personalized proposals** — Proposal agent generates tailored outreach
- **CRM integration** — PostgreSQL-backed CRM (companies, contacts, proposals, activities)
- **Follow-up automation** — Schedules and processes due follow-ups
- **Multi-agent architecture** — Orchestrator-workers pipeline
- **Long-term memory** — PostgreSQL full-text search over agent memories

## Quick start

### 1. PostgreSQL (local pgAdmin — no Docker)

Use the **same PostgreSQL server** you already use in pgAdmin (where you see `BSCS`, `jobs_crowler`, etc.).

Create the database if it does not exist (pgAdmin → Query Tool, or terminal):

```sql
CREATE DATABASE hermes_bd;
```

pgAdmin connection (match your existing server):

| Field | Typical value |
|-------|----------------|
| Host | `localhost` |
| Port | `5433` (your local server — check pgAdmin server properties) |
| User | `postgres` |
| Database | `hermes_bd` |

### 2. Install dependencies

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure environment

```bash
cp .env.example .env
```

Set `DATABASE_URL` to your **pgAdmin** server (port, password):

```
postgresql+psycopg://postgres:YOUR_PASSWORD@localhost:5433/hermes_bd
```

### 4. Initialize schema

```bash
python scripts/init_db.py
```

### 5. Run MCP server

```bash
python main.py
```

Reload MCP in Cursor (`.cursor/mcp.json` is preconfigured).

### 6. Run the web frontend

**Terminal 1 — API backend:**

```bash
python run_api.py
```

**Terminal 2 — React UI:**

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173** in your browser.

The dashboard lets you run BD pipelines, browse companies, search memory, and manage follow-ups.

## MCP tools

### Harmis persona

| Tool | Description |
|------|-------------|
| `harmis_act` | Harmis performs an action |
| `harmis_status` | Harmis state |

### Business Development Agent

| Tool | Description |
|------|-------------|
| `bd_run_pipeline` | Full pipeline: research → discovery → proposal → CRM → follow-up |
| `bd_research_company` | Research and save company profile |
| `bd_discover_contacts` | Find decision-makers for a company |
| `bd_generate_proposal` | Generate personalized proposal |
| `bd_recall_memory` | Search long-term agent memory |
| `bd_list_companies` | List CRM companies |
| `bd_process_follow_ups` | Process due follow-ups |
| `cv_screen` | Screen a CV against a job description |

### CV Screening

Paste **job description** + **CV text** → get a **score out of 100** and a one-line reason.

## Example prompts

- *"Run bd_run_pipeline for Acme Corp in fintech, domain acme.com"*
- *"Research Stripe and save to CRM"*
- *"Recall memory about Acme Corp"*
- *"Process due follow-ups"*

## Architecture

```
Orchestrator
 ├── ResearchAgent      → company profile
 ├── DiscoveryAgent     → decision-makers
 ├── ProposalAgent      → personalized proposal
 ├── FollowUpAgent      → scheduled follow-up
 └── PostgresCRM        → persist to PostgreSQL
MemoryStore              → long-term FTS memory
```

## LLM

Set `OPENAI_API_KEY` in `.env` for GPT-powered research and proposals. Without it, the agents use heuristic templates (still fully functional).

Default model is `gpt-4o-mini`. Override with `OPENAI_MODEL` (e.g. `gpt-4o`).

## PostgreSQL schema

Tables: `companies`, `contacts`, `proposals`, `follow_ups`, `activities`, `memory_entries`

Default in `hermes/config.py` is port 5433 — override via `.env` `DATABASE_URL`.
