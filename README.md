# StreamNotes fishing log

A Streamlit journal for North American freshwater catches, backed by a Flask API
and SQLite database. Users can register/sign in, save catches and locations,
view their fishing spots on a map, track species and see their trophy catches.

## Run locally

Install the requirements in your environment, then start both processes from
this directory in separate terminals:

```bash
python api_setup.py
```

```bash
streamlit run app.py
```

The API listens on `http://127.0.0.1:5001` and the database is created at
`instance/fishys.db`. Set `FISH_DATABASE_URL` to use another SQLAlchemy database
URL. Set `FISH_API_URL` in the Streamlit process when the API is hosted at a
different address (include the `/api` path).

Each user has private catches and locations. A catch at a new place creates a
location automatically; new places require latitude and longitude so they can
be shown on the map. A catch is marked as a river monster when its measured
length exceeds the selected species' threshold in `SPECIES_THRESHOLDS` in
`api_setup.py`.

The API creates account password hashes and issues revocable bearer tokens.
Keep the API and Streamlit app behind HTTPS and set an appropriate production
database URL before deploying.
