# Implementation Brief | Small Business Economic Data Assistant

**Funding decision.** Approve a dashboard-first pilot. Release up to $20 in prepaid LLM credit after verifying read-only access and spending controls. Continue AI only if it saves time over the dashboard and produces verifiable answers.

## 1. Current decision workflow

Weekly, I decide whether economic changes warrant reviewing a small business's operating budget. I find reliable figures on World Bank data pages, compare recent U.S. inflation, unemployment, and GDP growth, check available years, and flag expense, staffing, or revenue assumptions. Before proposing changes, I would check actual expenses, sales, and cash flow. Finding reliable data, judging relevance, and interpreting national trends for the business take time.

**Timed baseline.** Oct. 23 inflation/expense review, **20 min**. Oct. 31 inflation, unemployment, and GDP growth, **10 min each**, plus a **12-min** combined review. All five entries recorded **4/5** confidence. [Milestone 1 log](baseline_log.md)

## 2. Three options

| Option | Benefits | Costs and risks |
| --- | --- | --- |
| No new technology | Familiar sources and direct judgment. | $0 in new services. Manual lookup takes time and can mix reporting years. |
| PostgreSQL dashboard | SQL handles latest values, trends, comparisons, and missing-year flags. | Build and maintain views. Cold starts, outages, or stale data can hinder reviews. |
| LLM chatbot or agent | Adds plain-language follow-ups and cited briefings about which assumptions to check. SQL supplies the figures. | Adds token spend, latency, evaluation, and oversight. The model can invent figures or overstate implications. |

The verified Supabase snapshot has 960 annual observations across 20 countries and three indicators, including ten NULLs. Five SQL analyses were verified. Sync code, a scheduled workflow, and the Streamlit freshness banner exist. Dashboard views and integrated AI are pending. [SQL findings](query_findings.md) · [Sync status](sync_tests.md)

## 3. Value hypotheses and measurement

- **Dashboard:** Reduce median single-indicator review time from **10 to ≤6 min**, using the three Oct. 31 checks.
- **LLM:** Reduce median combined review time from **12 to ≤8 min** and beat dashboard-only time on matched tasks. Usable outputs must match SQL on values, years, and gaps, with correct citations.

In Milestone 4, time each real review from lookup to a checked decision or briefing, including waits and verification. Log date, task, features, time, usefulness, gaps, and confidence. Compare medians and sample sizes by task and mode. Start with dashboard-only reviews and repeat matched tasks when AI is available. The combined baseline has one entry. [Usage log](usage_log.md)

## 4. Monthly cost estimate and spending limit

**Provisional USD estimates.** One low-traffic Render web service ($0), one Supabase Free project ($0), three daily GitHub Actions syncs on standard Linux runners within quota ($0), and public World Bank API access ($0 budgeted). [Render](https://render.com/docs/free) · [Supabase](https://supabase.com/pricing) · [GitHub](https://docs.github.com/en/billing/concepts/product-billing/github-actions) · [World Bank](https://datahelpdesk.worldbank.org/knowledgebase/articles/889392)

At 100 AI interactions/month with 4,000 input and 1,000 output tokens per interaction across all calls, Claude Haiku 4.5 at $1 input and $5 output per million tokens yields **$0.90/month**. Estimated service total is **$0 for the dashboard and $0.90 with AI**, excluding labor. Published rates were checked. Verify rates and plan eligibility before activation. [Claude pricing](https://platform.claude.com/docs/en/about-claude/pricing)

**Hard $20 prepaid LLM API cap.** Disable auto-reload, require sign-in, bound tool calls and tokens, and reserve maximum request cost before each call. If credit is insufficient, unknown, or exhausted, stop model calls, show a notice, and keep SQL views available. [Prepaid billing](https://support.anthropic.com/en/articles/8977456-how-do-i-pay-for-my-api-usage)

## 5. Risks and prohibited AI actions

Stale, revised, or missing national data and unsupported conclusions can mislead managers, affecting employees' hours and supplier orders. Show sources, observation years, gaps, and last successful sync. Managers check firm records privately and retain decision authority. Source data are public aggregates, but prompts or logs could expose names, payroll, invoices, or credentials. Send only public results and sanitized questions. Keep raw prompts and secrets out of logs. Prohibit AI from changing records or budgets, making financial or staffing decisions, placing orders, sending messages, or disclosing private data.

## 6. Implementation Scorecard

| Official factor | Rating | Project evidence |
| --- | --- | --- |
| Real user and workflow | Green | My weekly budget-review decision has five timed baseline entries. |
| Data access | Green | World Bank retrieval and the Supabase load were verified. |
| Data understanding | Green | The data dictionary and SQL findings document definitions, coverage, and NULLs. |
| Freshness and monitoring | Yellow | Sync logging and a freshness banner exist, with live scheduled runs unverified. |
| Grounding | Yellow | Five verified SQL analyses can supply evidence, with chatbot citations untested. |
| Bounded autonomy | Yellow | Sign-in code and reader migrations exist, with live permissions and AI limits unverified. |
| Evaluation | Red | Golden questions and assistant evaluation results are pending. |
| Measured value and cost | Yellow | Timed baselines and provisional costs exist, with pilot usage unmeasured. |
| Adoption | Red | First-time task completion and willingness to reuse are untested. |
| Governance and accountability | Yellow | Human approval and data-handling rules are defined, with enforcement untested. |

**Two weakest factors.** **Evaluation:** Build 15 golden questions, verify expected answers against SQL, and test accuracy and missing-data handling. **Adoption:** Conduct a first-time user test, record task completion and feedback, and evaluate willingness to reuse the tool.
