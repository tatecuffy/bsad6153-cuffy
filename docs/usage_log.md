# Usage Log (Weeks 4&ndash;8)

Every time you use your own website for your real decision, add a row, using the same columns as
your baseline log plus two more. Time yourself again so you can compare with your baseline.

| Date | What I was deciding | What I used on the site (views / chatbot / agent) | Time (min) | Did it help? Why or why not? | What I wished I knew | Confidence (1&ndash;5) |
|---|---|---|---|---|---|---|
|  |  |  |  |  |  |  |
| November 23, 2026 | How did average annual consumer-price inflation in Argentina and the United States compare from 2018 through 2024? | Read-only database check and Question 2 in `db/queries.sql` | Approximately 8, including troubleshooting | Yes. I retrieved the seven-year comparison: Argentina averaged 86.29% and the United States averaged 3.61%. | I wanted an easier way to retrieve the comparison without troubleshooting Python or running a technical command. | 4/5 |

**Notes on anything that went wrong, or that I didn't trust:**

The first attempt, `python scripts/check_db.py --app`, failed because `psycopg` was unavailable in the Python environment I was using. I reran the check with the virtual environment's Python executable. The read-only connection returned counts of 20 countries, 3 indicators, 960 observations, and 10 sync runs. I then ran Question 2 to retrieve the inflation comparison. A simple website or interface would make this information easier for nontechnical users to access.

**Comparison with the October 31 baseline**

In my [baseline log](baseline_log.md), I spent 10 minutes reviewing U.S. inflation to decide whether a small business should revisit its operating expenses. I rated my confidence 4/5. The November 23 comparison took approximately 8 minutes, including troubleshooting, and I rated my confidence 4/5 again. The tasks differed, so this test does not establish that the assistant is faster.
