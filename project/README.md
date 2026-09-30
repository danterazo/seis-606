# Homelab Dashboard & Inventory Tracker

## Running the App
From the repository root, install the project dependencies and start Streamlit
in mock mode. Streamlit prints a local URL in the terminal; open it in a browser to access the app.

```bash
poetry install
HOMELAB_STATUS_SOURCE=mock poetry run streamlit run project/app.py
```

The [MVP quickstart guide](specs/001-homelab-inventory-dashboard/quickstart.md)
contains more information.
