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

Deploy `gemini-worker.js` as a Cloudflare Worker or adapt the endpoint for
another server runtime. Configure the server variables `DASHBOARD_ORIGIN`
(the GitHub Pages origin), `GEMINI_MODEL` (a model enabled for your API
project), and secrets `GEMINI_API_KEY` and `ASSESSMENT_TOKEN`. Keep the
access token distinct from the Gemini API key. Use a random access token
and rate-limit requests at the host. Set the GitHub repository variable
`ASSESSMENT_ENDPOINT` to the HTTPS Worker URL and redeploy. The browser
accepts an access token in memory for the current tab session.

## IDX CLI

IDX CLI's Linux build can run on a GitHub-hosted Ubuntu runner without WSL
on the user's PC. To add a feed, choose the provider and command for the
required metric, pin the CLI version, validate the output schema, then
map it into the dashboard input. The Pages job currently uses Trading/Data
exports as its source.
