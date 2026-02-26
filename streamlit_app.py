import altair as alt
import pandas as pd
import pydeck as pdk
import requests
import streamlit as st

st.set_page_config(page_title="FSH - AUSTRIA", layout="wide")
st.title("Belegungsübersicht Alpenvereinshütten")

HUT_COORDS = {
    "Franz Senn Hütte": {"lat": 47.085, "lon": 11.195, "fix_kapazitaet": 130},
    "Regensburger Hütte": {
        "lat": 47.054769090700326,
        "lon": 11.198342789601003,
        "fix_kapazitaet": 85,
    },
    "Starkenburger Hütte": {
        "lat": 47.126873249997395,
        "lon": 11.279589453978218,
        "fix_kapazitaet": 90,
    },
}


@st.cache_data
def load_data():
    try:
        df = pd.read_csv("historie.csv")
    except FileNotFoundError:
        st.error("historie.csv wurde nicht gefunden.")
        return pd.DataFrame()

    if df.empty:
        st.warning("historie.csv ist leer.")
        return pd.DataFrame()

    if "Huette" not in df.columns:
        df["Huette"] = "Franz Senn Hütte"

    df["Abrufdatum"] = pd.to_datetime(df["Abrufdatum"], dayfirst=True, errors="coerce")
    df["Buchungsdatum"] = pd.to_datetime(df["Buchungsdatum"], dayfirst=True, errors="coerce")
    df = df[df["Abrufdatum"].notna() & df["Buchungsdatum"].notna()].copy()
    return df


def weather_icon(code):
    if code == 0:
        return "☀️ Klar"
    if code in [1, 2, 3]:
        return "🌤 Teilweise bewölkt"
    if code in [45, 48]:
        return "🌫 Nebel"
    if code in [51, 53, 55]:
        return "🌦 Nieselregen"
    if code in [61, 63, 65]:
        return "🌧 Regen"
    if code in [71, 73, 75]:
        return "❄️ Schnee"
    if code == 95:
        return "⛈ Gewitter"
    return "🌥 Unbekannt"


@st.cache_data(ttl=3600)
def load_weather(lat: float, lon: float):
    weather_url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        "&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,weathercode"
        "&timezone=Europe/Vienna"
    )
    try:
        response = requests.get(weather_url, timeout=20)
        response.raise_for_status()
        daily = response.json()["daily"]
        weather_df = pd.DataFrame(
            {
                "Datum": pd.to_datetime(daily["time"]),
                "Tmin °C": daily["temperature_2m_min"],
                "Tmax °C": daily["temperature_2m_max"],
                "Regen mm": daily["precipitation_sum"],
                "Wettercode": daily["weathercode"],
            }
        )
        weather_df["Wetter"] = weather_df["Wettercode"].apply(weather_icon)
        return weather_df
    except Exception as e:
        st.warning(f"Wetterdaten konnten nicht geladen werden: {e}")
        return pd.DataFrame()


def get_map_data(df: pd.DataFrame) -> pd.DataFrame:
    today = pd.Timestamp.today().normalize()
    map_rows = []

    for hut, coords in HUT_COORDS.items():
        hut_df = df[(df["Huette"] == hut) & (df["Status"].str.upper() != "CLOSED")].copy()
        if hut_df.empty:
            free_beds_text = "keine Daten"
        else:
            hut_df["FreiePlaetze"] = pd.to_numeric(hut_df["FreiePlaetze"], errors="coerce")
            hut_df = hut_df[hut_df["FreiePlaetze"].notna()].copy()

            latest_snapshot = hut_df["Abrufdatum"].max()
            snapshot_df = hut_df[hut_df["Abrufdatum"] == latest_snapshot]

            today_match = snapshot_df[snapshot_df["Buchungsdatum"].dt.normalize() == today]
            if not today_match.empty:
                free_beds = int(today_match.iloc[0]["FreiePlaetze"])
                free_beds_text = f"{free_beds} frei heute"
            else:
                next_match = snapshot_df[snapshot_df["Buchungsdatum"] >= today].sort_values("Buchungsdatum")
                if next_match.empty:
                    free_beds_text = "keine aktuellen Daten"
                else:
                    free_beds = int(next_match.iloc[0]["FreiePlaetze"])
                    date_text = next_match.iloc[0]["Buchungsdatum"].strftime("%d.%m")
                    free_beds_text = f"{free_beds} frei ({date_text})"

        map_rows.append(
            {
                "Huette": hut,
                "lat": coords["lat"],
                "lon": coords["lon"],
                "label": f"{hut}\n{free_beds_text}",
            }
        )

    return pd.DataFrame(map_rows)


def render_map(df: pd.DataFrame):
    st.subheader("🗺️ Hüttenkarte")
    map_df = get_map_data(df)

    view_state = pdk.ViewState(
        latitude=map_df["lat"].mean(),
        longitude=map_df["lon"].mean(),
        zoom=9.2,
        pitch=0,
    )

    scatter = pdk.Layer(
        "ScatterplotLayer",
        data=map_df,
        get_position="[lon, lat]",
        get_fill_color="[255, 99, 71, 220]",
        get_line_color="[255, 255, 255, 255]",
        line_width_min_pixels=1,
        stroked=True,
        pickable=True,
        get_radius=300,
    )

    text = pdk.Layer(
        "TextLayer",
        data=map_df,
        get_position="[lon, lat]",
        get_text="label",
        get_size=14,
        get_color="[20, 20, 20, 255]",
        get_alignment_baseline="top",
        get_pixel_offset="[0, 20]",
    )

    st.pydeck_chart(
        pdk.Deck(
            layers=[scatter, text],
            initial_view_state=view_state,
            tooltip={"text": "{Huette}\n{label}"},
            map_style="mapbox://styles/mapbox/light-v9",
        ),
        use_container_width=True,
    )


df = load_data()
if df.empty:
    st.stop()

render_map(df)

selected_hut = st.selectbox("Hütte auswählen", sorted(df["Huette"].dropna().unique()))

hut_df = df[df["Huette"] == selected_hut].copy()
latest_date = hut_df["Abrufdatum"].max()
latest_df = hut_df[hut_df["Abrufdatum"] == latest_date].copy()
latest_df = latest_df[latest_df["Status"].str.upper() != "CLOSED"].copy()
latest_df["FreiePlaetze"] = pd.to_numeric(latest_df["FreiePlaetze"], errors="coerce")
latest_df["Kapazität"] = pd.to_numeric(latest_df["Kapazität"], errors="coerce")
latest_df = latest_df[latest_df["FreiePlaetze"].notna()].copy()

fix_kapazitaet = HUT_COORDS.get(selected_hut, {}).get("fix_kapazitaet")
if fix_kapazitaet is None:
    fix_kapazitaet = int(latest_df["Kapazität"].max()) if not latest_df.empty else 0

latest_df["FixGebucht"] = (fix_kapazitaet - latest_df["Kapazität"]).clip(lower=0)
latest_df["OnlineGebucht"] = latest_df["Kapazität"] - latest_df["FreiePlaetze"]

coords = HUT_COORDS.get(selected_hut, {})
weather_df = load_weather(coords.get("lat", 47.085), coords.get("lon", 11.195))

combined = latest_df.copy()
if not weather_df.empty:
    combined = combined.merge(weather_df, left_on="Buchungsdatum", right_on="Datum", how="left")
else:
    for col in ["Wetter", "Tmin °C", "Tmax °C", "Regen mm"]:
        combined[col] = pd.NA

st.subheader(f"📅 {selected_hut} – aktueller Stand vom {latest_date.date()}")
st.dataframe(
    combined[
        [
            "Buchungsdatum",
            "OnlineGebucht",
            "FixGebucht",
            "Wetter",
            "Tmin °C",
            "Tmax °C",
            "Regen mm",
        ]
    ].sort_values("Buchungsdatum"),
    use_container_width=True,
)

st.subheader("Aktuelle Auslastung")
stack_data = combined.melt(
    id_vars=["Buchungsdatum"],
    value_vars=["FixGebucht", "OnlineGebucht"],
    var_name="Typ",
    value_name="Plaetze",
)

chart = alt.Chart(stack_data).mark_bar().encode(
    x=alt.X("Buchungsdatum:T", title="Datum"),
    y=alt.Y("Plaetze:Q", title="Belegte Betten"),
    color=alt.Color(
        "Typ:N",
        scale=alt.Scale(domain=["OnlineGebucht", "FixGebucht"], range=["#7EFCAE", "#FF8279"]),
    ),
)
st.altair_chart(chart, use_container_width=True)

st.subheader("Historische minimale und maximale Belegung")
hist_df = hut_df.copy()
hist_df = hist_df[hist_df["Status"].str.upper() != "CLOSED"]
hist_df["FreiePlaetze"] = pd.to_numeric(hist_df["FreiePlaetze"], errors="coerce")
hist_df = hist_df[hist_df["FreiePlaetze"].notna()]
hist_df["Belegt"] = fix_kapazitaet - hist_df["FreiePlaetze"]

minmax_df = (
    hist_df.groupby("Buchungsdatum")["Belegt"].agg(MinBelegt="min", MaxBelegt="max").reset_index()
)
minmax_df["Range"] = minmax_df["MaxBelegt"] - minmax_df["MinBelegt"]

bar_data = minmax_df.melt(
    id_vars=["Buchungsdatum"],
    value_vars=["MinBelegt", "Range"],
    var_name="Typ",
    value_name="Wert",
)

chart = alt.Chart(bar_data).mark_bar().encode(
    x=alt.X("Buchungsdatum:T", title="Datum"),
    y=alt.Y("Wert:Q", title="Belegte Betten"),
    color=alt.Color(
        "Typ:N",
        scale=alt.Scale(domain=["MinBelegt", "Range"], range=["#B0BEC5", "#FF5722"]),
    ),
)
st.altair_chart(chart, use_container_width=True)
