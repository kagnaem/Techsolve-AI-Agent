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

1. This project is stored in a GitHub repository. 
2. This repository is used in Streamlit Community Cloud's branch
3. Open AI key is stored in secretly in Streamlit Community Cloud 
4. app.py is deployed and tested.

## Data and responsible use

The assessment uses synthetic support-ticket data. Customer ID, customer name,
customer email, billing contact email, account manager and assigned-to columns
were removed from the public AI export. The application is intended for
aggregated operational analysis, and generated insights should be checked
against the governed Power BI measures.
