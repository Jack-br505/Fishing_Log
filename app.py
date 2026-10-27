import base64
from html import escape
import os
from datetime import date, time

import folium
import requests
import streamlit as st


API_URL = os.environ.get("FISH_API_URL", "http://127.0.0.1:5001/api").rstrip("/")

st.set_page_config(
    page_title="Stream Notes — fishing log",
    page_icon="🎣",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=DM+Sans:wght@400;500;600;700&family=Playfair+Display:wght@600;700&display=swap');
    :root { --ink:#192a25; --muted:#75817b; --paper:#f5f6f1; --green:#245c47; }
    html, body, [class*="css"] { font-family:'DM Sans',sans-serif; color:var(--ink); }
    .stApp { background:var(--paper); }
    [data-testid="stSidebar"] { background:#e9eee7; border-right:1px solid #dfe5dd; }
    [data-testid="stSidebar"] > div:first-child { padding-top:2rem; }
    h1,h2,h3 { color:var(--ink); }
    h1 { font-family:'Playfair Display',serif; letter-spacing:-.04em; font-size:2.65rem; }
    .eyebrow { color:#718078; font:500 .72rem 'DM Mono',monospace; text-transform:uppercase; letter-spacing:.14em; }
    .hero-note { color:#718078; font-size:1.04rem; margin-top:-.6rem; }
    .metric-card { background:#fff; border:1px solid #e4e9e2; border-radius:14px; padding:1.15rem 1.3rem; min-height:116px; }
    .metric-label { color:#75817b; font:500 .72rem 'DM Mono',monospace; letter-spacing:.1em; text-transform:uppercase; }
    .metric-value { font:600 2rem 'Playfair Display',serif; margin-top:.4rem; }
    div[data-testid="stForm"] { background:#fff; border:1px solid #e4e9e2; border-radius:14px; padding:1.2rem; }
    .catch-card { background:#fff; border:1px solid #e4e9e2; border-radius:14px; padding:1.1rem 1.3rem; margin-bottom:.8rem; }
    .catch-title { font:600 1.15rem 'Playfair Display',serif; }
    .catch-meta { color:#75817b; font-size:.88rem; margin-top:.35rem; }
    div.stButton > button[kind="primary"], div[data-testid="stFormSubmitButton"] button { background:#245c47; border-color:#245c47; }
    </style>
    """,
    unsafe_allow_html=True,
)


def api_request(path, method="GET", payload=None, authenticated=True):
    headers = {}
    token = st.session_state.get("token")
    if authenticated and token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        response = requests.request(
            method,
            f"{API_URL}{path}",
            json=payload,
            headers=headers,
            timeout=10,
        )
    except requests.RequestException as error:
        raise RuntimeError(
            "Can't reach the fishing log API. Start it with `python api_setup.py`."
        ) from error
    try:
        body = response.json()
    except ValueError:
        body = {}
    if not response.ok:
        raise RuntimeError(body.get("error", "The request could not be completed."))
    return body


def call_api(path, method="GET", payload=None, authenticated=True):
    try:
        return api_request(path, method, payload, authenticated=authenticated)
    except RuntimeError as error:
        st.error(str(error))
        return None


def metric(label, value):
    st.markdown(
        f'<div class="metric-card"><div class="metric-label">{label}</div>'
        f'<div class="metric-value">{value}</div></div>',
        unsafe_allow_html=True,
    )


def page_header(kicker, title, description):
    st.markdown(f'<div class="eyebrow">{kicker}</div>', unsafe_allow_html=True)
    st.title(title)
    st.markdown(f'<p class="hero-note">{description}</p>', unsafe_allow_html=True)
    st.write("")


def login_page():
    left, right = st.columns([1.1, 0.9], gap="large")
    with left:
        st.markdown('<div class="eyebrow">YOUR EXPERIENCE, NOTED</div>', unsafe_allow_html=True)
        st.title("A Way to Note Every Cast")
        st.markdown(
            '<p class="hero-note">Keep every catch, honey hole, and details in one place.</p>',
            unsafe_allow_html=True,
        )
        st.image(
            "https://images.unsplash.com/photo-1786788684933-89146e442418?q=80&w=1548&auto=format&fit=crop&ixlib=rb-4.1.0&ixid=NHwxMjA3fDA%3D",
            width="stretch",
        )
        st.caption("A personal journal for freshwater anglers.")
    with right:
        st.write("")
        st.write("")
        st.markdown('<div class="eyebrow">WELCOME TO STREAM NOTES</div>', unsafe_allow_html=True)
        st.header("Sign in")
        login_tab, register_tab = st.tabs(["Sign in", "Create account"])
        with login_tab:
            with st.form("login_form"):
                username = st.text_input("Username")
                password = st.text_input("Password", type="password")
                submitted = st.form_submit_button("Sign in", type="primary", width="stretch")
            if submitted:
                try:
                    result = api_request(
                        "/login",
                        "POST",
                        {"username": username, "password": password},
                        authenticated=False,
                    )
                    st.session_state.token = result["token"]
                    st.session_state.username = result["username"]
                    st.rerun()
                except RuntimeError as error:
                    st.error(str(error))
        with register_tab:
            with st.form("register_form"):
                new_username = st.text_input("Username", key="register_username")
                email = st.text_input("Email (optional)", key="register_email")
                new_password = st.text_input("Password (8+ characters)", type="password", key="register_password")
                confirm = st.text_input("Confirm password", type="password", key="register_confirm")
                submitted = st.form_submit_button("Create account", type="primary", width="stretch")
            if submitted:
                if new_password != confirm:
                    st.error("Those passwords don't match.")
                else:
                    try:
                        api_request(
                            "/register",
                            "POST",
                            {"username": new_username, "email": email, "password": new_password},
                            authenticated=False,
                        )
                        st.success("Account created. Sign in to start your log.")
                    except RuntimeError as error:
                        st.error(str(error))


def catch_tile(item):
    badge = "  ·  RIVER MONSTER" if item["monster"] else ""
    species = escape(item["species"])
    details = " · ".join(
        [
            f'{escape(item["date"])} at {escape(item["time"])}',
            escape(item["location"]),
            f'{escape(str(item["length_inches"] or "—"))} in',
            f'{escape(str(item["weight_lbs"] or "—"))} lb',
            escape(item["gear"] or "Gear not noted"),
        ]
    )
    st.markdown(
        f'<div class="catch-card"><div class="catch-title">{species}{escape(badge)}</div>'
        f'<div class="catch-meta">{details}</div></div>',
        unsafe_allow_html=True,
    )
    if item.get("picture"):
        image_bytes = base64.b64decode(item["picture"].partition(",")[2])
        st.image(image_bytes, width=320)


def catches_page():
    page_header("Your Logbook", "Your catches", "A field record of every fish and the water it came from.")
    locations = call_api("/locations")
    catches = call_api("/catches")
    species_catalog = call_api("/species", authenticated=False)
    if locations is None or catches is None or species_catalog is None:
        return
    species_options = [item["name"] for item in species_catalog]
    total_col, species_col, monster_col = st.columns(3)
    summary = call_api("/summary")
    if summary is None:
        return
    with total_col:
        metric("Total catches", summary["total_catches"])
    with species_col:
        metric("Species", summary["species_count"])
    with monster_col:
        metric("River monsters", summary["monster_count"])
    st.write("")
    log_tab, overview_tab = st.tabs(["＋  Log a catch", "Catch overview"])
    with log_tab:
        location_names = ["＋ Add a new location"] + [item["name"] for item in locations]
        selected_location = st.selectbox("Location", location_names)
        with st.form("catch_form", clear_on_submit=True):
            st.subheader("Add a catch")
            first, second = st.columns(2)
            with first:
                species = st.selectbox("Species", species_options)
                selected_threshold = next(
                    item["monster_threshold_inches"]
                    for item in species_catalog
                    if item["name"] == species
                )
                st.caption(f"River monster status starts over {selected_threshold} inches.")
                catch_date = st.date_input("Date", value=date.today())
                length = st.number_input("Length (inches)", min_value=0.0, step=0.5, value=None, placeholder="Optional")
            with second:
                catch_time = st.time_input("Time", value=time(12, 0))
                gear = st.text_input("Gear used", placeholder="Optional e.g. spinning rod, fly rod, etc.")
                lure = st.text_input("Lure or bait", placeholder="Optional e.g. spinner, worm, etc.")
                weight = st.number_input("Weight (lbs)", min_value=0.0, step=0.1, value=None, placeholder="Optional")
                picture = st.file_uploader("Fish photo", type=["jpg", "jpeg", "png", "webp"])
            location_name, latitude, longitude = "", None, None
            if selected_location == "＋ Add a new location":
                st.markdown("**New location details**")
                name_col, lat_col, lon_col = st.columns(3)
                location_name = name_col.text_input("Location name")
                latitude = lat_col.number_input("Latitude", label = "North/South", min_value=-90.0, max_value=90.0, value=42.0, format="%.6f")
                longitude = lon_col.number_input("Longitude", label = "East/West", min_value=-180.0, max_value=180.0, value=-84.0, format="%.6f")
            submitted = st.form_submit_button("Save catch", type="primary")
        if submitted:
            photo_data = None
            if picture is not None:
                if picture.size > 4 * 1024 * 1024:
                    st.error("Please choose an image smaller than 4 MB.")
                    return
                photo_data = (
                    f"data:{picture.type};base64,"
                    + base64.b64encode(picture.getvalue()).decode("ascii")
                )
            payload = {
                "species": species,
                "date": catch_date.isoformat(),
                "time": catch_time.isoformat(timespec="minutes"),
                "gear": gear,
                "lure": lure,
                "length_inches": length or None,
                "weight_lbs": weight or None,
                "picture": photo_data,
            }
            if selected_location == "＋ Add a new location":
                payload.update(
                    {"location_name": location_name, "latitude": latitude, "longitude": longitude}
                )
            else:
                payload["location_id"] = next(
                    item["id"] for item in locations if item["name"] == selected_location
                )
            result = call_api("/catches", "POST", payload)
            if result is not None:
                if result["monster"]:
                    st.success(f"River monster! Your {result['species']} crossed its size threshold.")
                else:
                    st.success(f"{result['species']} added to your log.")
                st.rerun()
    with overview_tab:
        if catches:
            for item in catches:
                catch_tile(item)
        else:
            st.info("Your log is ready for its first catch.")


def locations_page():
    page_header("Honey Holes", "Your locations", "Map the places you fish and the whats in them")
    locations = call_api("/locations")
    if locations is None:
        return
    form_col, summary_col = st.columns([0.85, 1.15], gap="large")
    with form_col:
        st.subheader("Add a location")
        with st.form("location_form", clear_on_submit=True):
            name = st.text_input("Location name", placeholder="e.g. Pine River bend")
            lat_col, lon_col = st.columns(2)
            latitude = lat_col.number_input("Latitude", min_value=-90.0, max_value=90.0, value=42.0, format="%.6f")
            longitude = lon_col.number_input("Longitude", min_value=-180.0, max_value=180.0, value=-84.0, format="%.6f")
            submitted = st.form_submit_button("Save location", type="primary")
        if submitted:
            result = call_api(
                "/locations",
                "POST",
                {"name": name, "latitude": latitude, "longitude": longitude},
            )
            if result is not None:
                st.success(f"{name} added to your locations.")
                st.rerun()
        st.write("")
        if locations:
            for location in locations:
                species = ", ".join(location["species"]) or "No catches yet"
                st.markdown(
                    f'**{location["name"]}**  \n{location["num_caught"]} fish · {species}'
                )
                st.caption(f'{location["latitude"]:.5f}, {location["longitude"]:.5f}')
        else:
            st.info("Locations you add or use in a catch will appear here.")
    with summary_col:
        st.subheader("Fishing map")
        if locations:
            center = [
                sum(item["latitude"] for item in locations) / len(locations),
                sum(item["longitude"] for item in locations) / len(locations),
            ]
            fishing_map = folium.Map(location=center, zoom_start=6, control_scale=True)
            for location in locations:
                location_name = escape(location["name"])
                species_list = escape(", ".join(location["species"]) or "No species logged")
                folium.Marker(
                    [location["latitude"], location["longitude"]],
                    tooltip=location_name,
                    popup=(
                        f'<b>{location_name}</b><br>'
                        f'{location["num_caught"]} fish<br>'
                        f'{species_list}'
                    ),
                    icon=folium.Icon(color="darkgreen", icon="map-marker", prefix="fa"),
                ).add_to(fishing_map)
            st.components.v1.html(fishing_map.get_root().render(), height=520, scrolling=False)
        else:
            st.markdown(
                '<div class="metric-card">Add a location to place your first pin on the map.</div>',
                unsafe_allow_html=True,
            )


def monsters_page():
    page_header("Your Trophy Case", "River monsters", "The catches that cleared their species' size threshold.")
    catches = call_api("/catches")
    if catches is None:
        return
    monsters = [item for item in catches if item["monster"]]
    st.markdown(f'<div class="eyebrow">{len(monsters)} QUALIFYING CATCH{"ES" if len(monsters) != 1 else ""}</div>', unsafe_allow_html=True)
    st.write("")
    if monsters:
        for item in monsters:
            catch_tile(item)
    else:
        st.info("No river monsters yet. Keep your line in the water.")


def species_page():
    page_header("YOUR FRESHWATER MILESTONES", "Species", "See the variety in your freshwater fishing story.")
    summary = call_api("/summary")
    if summary is None:
        return
    left, right = st.columns([0.65, 1.35], gap="large")
    with left:
        metric("Species caught", summary["species_count"])
        st.write("")
        metric("Total fish", summary["total_catches"])
    with right:
        st.subheader("Species tally")
        if summary["species"]:
            st.bar_chart(
                {item["name"]: item["count"] for item in summary["species"]},
                color="#3d7a5d",
                horizontal=True,
            )
            st.dataframe(
                summary["species"],
                column_config={
                    "name": st.column_config.TextColumn("Species"),
                    "count": st.column_config.NumberColumn("Fish caught", format="%d"),
                },
                hide_index=True,
                width="stretch",
            )
        else:
            st.info("Your species tally will build as you log catches.")


if not st.session_state.get("token"):
    login_page()
else:
    with st.sidebar:
        st.markdown('<div class="eyebrow">FIELDNOTES</div>', unsafe_allow_html=True)
        st.markdown(f"### 🎣 {st.session_state.get('username', 'Angler')}")
        st.caption("Your freshwater journal")
        st.divider()
        page = st.radio(
            "Navigate",
            ["Catches", "Locations", "River monsters", "Species"],
            label_visibility="collapsed",
        )
        st.divider()
        if st.button("Sign out", width="stretch"):
            try:
                api_request("/logout", "POST")
            except RuntimeError as error:
                st.error(f"Signed out locally; the API session could not be revoked: {error}")
            st.session_state.pop("token", None)
            st.session_state.pop("username", None)
            st.rerun()
    if page == "Catches":
        catches_page()
    elif page == "Locations":
        locations_page()
    elif page == "River monsters":
        monsters_page()
    else:
        species_page()
