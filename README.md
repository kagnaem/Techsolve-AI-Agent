# TechSolve Support Operations AI Agent

A Streamlit prototype that converts management questions into validated,
read-only DuckDB SQL and returns evidence-based insights from the prepared
TechSolve reporting data.

## Run locally

1. Create a local `.env` file from `.env.example`.
2. Add `OPENAI_API_KEY` and, optionally, `OPENAI_MODEL`.
3. Install the packages in `requirements.txt`.
4. Run:

```powershell
python -m streamlit run app.py
```

## Deploy on Streamlit Community Cloud

1. Store this project in a GitHub repository. A private repository is
   recommended for the assessment.
2. In Streamlit Community Cloud, select the repository, branch and `app.py`.
3. Open **Advanced settings > Secrets** and add:

```toml
OPENAI_API_KEY = "your-key-here"
OPENAI_MODEL = "gpt-5.6"
```

4. Deploy and test one of the suggested questions.

Never commit `.env` or `.streamlit/secrets.toml`. Both are excluded by
`.gitignore`.

## Data and responsible use

The assessment uses synthetic support-ticket data. Customer ID, customer name,
customer email, billing contact email, account manager and assigned-to columns
were removed from the public AI export. The application is intended for
aggregated operational analysis, and generated insights should be checked
against the governed Power BI measures.
