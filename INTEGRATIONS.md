# Data IHSG integrations

## IDX daily statistics

GitHub Actions runs at 00.00 WIB. With the OneDrive credentials configured,
it reads files named `ds_YYMMDD.pdf` under Trading/Data. A manual run can
publish a report sooner. Prices and net flow come from the PDF text. The
report’s rounded Today participation is read from its stacked bar when the
chart passes the layout and color checks. The TSV format is a fallback.
Missing input values remain gaps. The initial historical series comes from
the workbook, with missing closing prices preserved as gaps.

## Gemini

1. Open [Google AI Studio API Keys](https://aistudio.google.com/apikey),
   revoke the old key if it was shared, and create a replacement.
2. In [Cloudflare Workers & Pages](https://dash.cloudflare.com/), choose
   **Create application**, create a Worker, and deploy it.
3. Open the Worker editor, replace the example code with
   [gemini-worker.js](./gemini-worker.js), then deploy the new version.
4. In the Worker's **Settings → Variables and Secrets**, add these entries.

   | Name | Type | Value |
   | --- | --- | --- |
   | `DASHBOARD_ORIGIN` | Text | `https://amedenthusiast.github.io` |
   | `GEMINI_MODEL` | Text | `gemini-3.1-flash-lite`, if enabled in your project |
   | `GEMINI_API_KEY` | Secret | Your replacement AI Studio key |
   | `ASSESSMENT_TOKEN` | Secret | A separate long random access token |

5. Copy your Worker's HTTPS URL. In GitHub, go to **Settings → Secrets and
   variables → Actions → Variables → New repository variable**. Set
   `ASSESSMENT_ENDPOINT` to the Worker URL. Run **Data IHSG Pages** from
   the GitHub Actions page and wait for deployment to succeed.
6. Open Screener or Stock Detail, click **AI Assessment**, and enter the
   `ASSESSMENT_TOKEN` from step 4. The dashboard sends the displayed
   assessment context to your Worker, which calls Gemini. The token is
   held in browser memory for this tab. Keep the Gemini API key in Cloudflare.

## IDX CLI

On Windows, download the repository ZIP from **Code → Download ZIP**.
Extract it and double-click `start-idx-gui.cmd`. The launcher requires
Python 3 with Tkinter on Windows, and runs the existing IDX CLI installed
in the default WSL distro in the background. Once installed, you can use
the form without writing or running any WSL commands yourself. On Linux
or macOS with IDX CLI on PATH and Tkinter installed, run `python3 idx_gui.py`.

Enter a ticker, choose **Quote**, **History**, or **Ownership**, then select
**Ambil data**. For your first ownership query, click **Sinkron KSEI ≥1%**
to download the maintained register. Use **Simpan hasil** to export CSV or
JSON on your device. The app displays results locally. Pages continues to
use Trading/Data for its own dataset.
