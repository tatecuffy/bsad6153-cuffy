# BSAD 6153 Project: Small Business Economic Data Assistant

**Student:** Tate Cuffy
**My decision:** Should a small business review its operating budget based on changing economic conditions?
**Website:** &lt;your domain, from Week 4&gt;

This repository is one complete AI system, built over eight weeks: a real API, synced on a schedule into a
PostgreSQL database, shown on a public website, with a chatbot and an agent that answer and act from your
own data. You build it with an AI coding agent, and you read and verify everything it writes.

---

## Setting up your computer (Week 1 Setup)

You need a **Windows 10/11 or macOS computer where you can install software**, Git, Python 3.12, and your AI
coding agent (Claude Code, Codex, Antigravity, or Copilot). Let your agent help with the installs, but read
every command before you approve it, and keep auto-approve off.

1. **Clone this repository** into a short folder path that isn't synced by OneDrive or Dropbox, for example
   `C:\dev\bsad6153` on Windows or `~/dev/bsad6153` on macOS.
2. **Create and activate a virtual environment** from the project folder:

   | | Windows (PowerShell) | macOS (Terminal) |
   |---|---|---|
   | Create | `py -3.12 -m venv .venv` | `python3.12 -m venv .venv` |
   | Activate | `.venv\Scripts\Activate.ps1` | `source .venv/bin/activate` |

   You'll see `(.venv)` at the start of your prompt when it's active. Activate it every time you open a new terminal.
3. **Install the packages:** `pip install -r requirements.txt`
4. **Create your secrets file:** copy `.env.example` to `.env`, and put a fake value on the `TEST_SECRET=` line.
5. **Check everything:** `python scripts/check_setup.py` should end with `Setup OK`.
6. **Try the website:** `streamlit run app/streamlit_app.py` opens it in your browser. Press Ctrl+C to stop it.

### Working with your AI agent

- **You approve every command.** Read it first, and if you don't understand it, ask the agent what it does.
- **Ask for a plan before code:** "Before writing anything, tell me your plan."
- **Never paste a real key into the chat,** and never ask the agent to print your `.env` file.
- **The agent never gets the owner database password or deploy tokens.** That's how agents delete databases.
- **Record what you directed, read, verified, and decided** in each pull request's AI review log.

---

## Project layout

| Folder | What goes there | When |
|---|---|---|
| `ingest/` | Fetch, load, and sync code | Weeks 1&ndash;3 |
| `db/` | `schema.sql`, `roles.sql`, `queries.sql` | Weeks 2&ndash;6 |
| `docs/` | Data dictionary, logs, reports (see `docs/README.md`) | Every week |
| `evals/` | Golden questions and evaluation runs | Weeks 3&ndash;7 |
| `app/` | Your website (Streamlit) | Weeks 4&ndash;6 |
| `examples/` | A reference tool-using chatbot loop | Week 5 |
| `scripts/` | Setup and database checks | Weeks 0&ndash;2 |
| `data/sample/` | A small sample of raw API data (large downloads go in `data/raw/`, which Git ignores) | Week 1 |

## Secrets: where each one lives

| Secret | On your computer | On Render (website) | In GitHub Actions (sync) |
|---|---|---|---|
| `DATABASE_URL` (owner) | `.env` | **never** | Actions secret |
| `APP_DATABASE_URL` (read-only) | `.env` | environment setting | if your checks need it |
| `AGENT_DATABASE_URL` | `.env` | environment setting | no |
| LLM key, `APP_PASSWORD` | `.env` | environment setting | no |
| Data API key | `.env` | no | Actions secret |

`.env.example` lists the names only. If a secret ever leaks, revoke or rotate it first, then tell the instructor.

---

## Deploying on Render (Week 4)

1. Claim your free domain through the GitHub Student Developer Pack.
2. In Render, choose **New &gt; Blueprint**, pick this repository, and enter each secret when asked.
   (`render.yaml` describes the service.) Or create a **Web Service** by hand with:
   - Build command: `pip install -r requirements.txt`
   - Start command: `streamlit run app/streamlit_app.py --server.port $PORT --server.address 0.0.0.0 --server.headless true`
   - Environment variables: `PYTHON_VERSION=3.12.4`, `APP_DATABASE_URL`, and later your LLM key and `APP_PASSWORD`
3. Under **Settings &gt; Custom Domains**, add your domain, then add the DNS records Render shows you at your
   registrar. Ask your agent to explain each record before you add it. HTTPS turns on automatically.
4. Free services sleep when idle and take about a minute to wake. Say so on your site.

---

## Troubleshooting

- **`pip install` fails with "No such file or directory" on Windows:** the folder path is too long. Move the
  project to a short path such as `C:\dev\bsad6153` and recreate `.venv`.
- **PowerShell says running scripts is disabled when you activate:** use Command Prompt instead and run
  `.venv\Scripts\activate.bat`, or ask the instructor. Don't change system security settings without asking.
- **`python` opens the Microsoft Store or isn't found:** use `py -3.12` on Windows or `python3.12` on macOS.
- **The database check can't connect:** use Supabase's Session pooler string, check the password, and check
  that your Supabase project isn't paused.

---

## Project proposal (Week 1)

My Small Business Economic Data Assistant will help answer: should a small
business review its operating budget based on changing economic conditions?
The primary source is the [World Bank Indicators API v2](https://datahelpdesk.worldbank.org/knowledgebase/articles/889392).
The project retrieves annual consumer-price inflation, modeled unemployment,
and GDP growth for 20 countries, requesting 2010–2026 where available. Country
and indicator metadata provide definitions and context. International data
support comparisons; they do not measure a particular firm's expenses.

My [baseline log](docs/baseline_log.md) describes a weekly decision workflow.
On October 23, 2026, I spent 20 minutes reviewing information about inflation
and its possible effects on supplies, transportation, utilities, and other
expenses. I wanted to know which expenses had risen most, how costs compared
with previous months, and whether revenue covered increases. I recommended
reviewing the budget but wanted actual business expenses before proposing
changes. Finding reliable, relevant information and connecting it to operating
expenses were documented difficulties.

The backup is the [BLS Public Data API](https://www.bls.gov/developers/api_FAQs.htm),
using U.S. CPI, unemployment, and potentially earnings data. Its narrower scope
would support U.S. price and labor analysis rather than replace this international
dataset or GDP coverage. BLS requests must be batched by series and year ranges;
its [documented signatures](https://www.bls.gov/developers/api_signature_v2.htm)
do not provide World Bank-style page/per_page pagination. This fallback is
proposed, not implemented.

A future agent could prepare a budget-review briefing when newly retrieved
values change, citing years, sources, missing values, and possible revisions.
It would request human review rather than adjust budgets or financial records.

Risks include delayed or revised data, missing observations, API outages, and
misinterpreting national averages. Annual data cannot provide real-time weekly
economic alerts. Timestamped snapshots, completeness checks, and source
citations help expose these limits. Published licensing and attribution
requirements must be respected, including exceptions for future indicators.
Success would mean reducing information-gathering time while keeping budget
decisions grounded in evidence and actual business costs.

## How to run this project

<!-- Keep this current: how to run the sync, the website, and the evaluations. -->

### Milestone 1 — World Bank Indicators API v2

The current ingestion source is World Development Indicators, using annual
consumer-price inflation, modeled unemployment, and real GDP growth for 20
countries from 2010 through 2026 where available. These indicators provide broad
economic context for deciding whether to review a small-business operating
budget; actual business expenses are still needed before recommending changes.

Run `.venv\Scripts\python.exe ingest/fetch.py` from the repository root.
No API credentials are needed. See [ingestion instructions](ingest/README.md)
for tests, outputs, pagination, retries, and important functions, and the
[data dictionary](docs/data_dictionary.md) for definitions and limitations.
Raw downloads stay in ignored `data/raw/`; a small authentic sample is saved in
`data/sample/world_bank_sample.json`. Database loading and scheduled sync are
later milestones.

## Credits

The World Bank: World Development Indicators: IMF; ILO/ILOSTAT; national
statistical organizations/central banks; OECD; World Bank estimates.
The selected indicators are labeled CC BY 4.0. See the
[license](https://datacatalog.worldbank.org/public-licenses) and
[dataset terms](https://www.worldbank.org/ext/en/legal/terms-conditions/datasets).
Retrieval dates are recorded with the data. The local sample is a subset
with original API field values preserved. No provider endorsement is implied.

<!-- Your data API's required attribution, plus any open-source code or samples you used. -->
