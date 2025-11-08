
# PPS Village Sampling App (WFP Somali Region AO)

A Streamlit app to run **PPS village selection** and draw **household samples** with **reserves**, **rebalancing**, and **reproducible Sample IDs**.

## Features
- PPS per kebele (MOS = total HHs in village) → select up to 2 villages.
- Main sample per selected village: **15 Eligible + 15 Non‑eligible** (or **30 + 30** if only one village).
- Reserves per selected village per group: **4** (two-village case) or **8** (one-village case). No overlap with main.
- Rebalancing (main only) between the two selected villages for the **same group**.
- Reproducible with a fixed seed (default `20251031`).
- Exports a 5‑sheet Excel and an optional **field-team printable workbook**.
- **In‑app validator** and a CLI validator under `tests/`.

## Run locally
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

## Demo mode
Inside the app, click **🧪 Demo mode** to run using the bundled `data/sample_input.xlsx`.

## Deploy on Streamlit Cloud
1. Push this folder to a public GitHub repo.
2. On https://share.streamlit.io → **New app** → point to `app.py`.
3. Deploy.

## Tests / Validation
```bash
pip install pandas openpyxl
python tests/validate_output.py produced_output.xlsx tests/expected_output.xlsx
```

## Data expectations
At minimum, your input file should include: **Kebele**, **Village**, and preferably **Eligibility** (values `Eligible` or others → treated as `Non-eligible`). Additional columns (IDs, names, phone) are preserved in outputs.

## License
MIT (adapt as needed)
