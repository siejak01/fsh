import streamlit as st
import pandas as pd
import requests
import altair as alt
from datetime import datetime

st.set_page_config(page_title="Franz-Senn-Hütte Dashboard", layout="wide")
st.title("FSH – Belegungsübersicht")

# ---------------------------
# CSV laden
# ---------------------------
@st.cache_data
def load_data():
    try:
        df = pd.read_csv("historie.csv")
        if df.empty:
            st.warning("historie.csv ist leer.")
            return pd.DataFrame()
        df["Abrufdatum"] = pd.to_datetime(df["Abrufdatum"])
        df["Buchungsdatum"] = pd.to_datetime(df["Buchungsdatum"])
        return df
    except FileNotFoundError:
        st.error("historie.csv wurde nicht gefunden.")
        return pd.DataFrame()

df = load_data()
if df.empty:
    st.stop()

# ---------------------------
# Nur aktuelle Abrufdaten
# ---------------------------
latest_date = df["Abrufdatum"].max()
latest_df = df[df["Abrufdatum"] == latest_date].copy()

# ---------------------------
# CLOSED-Tage rausfiltern
# ---------------------------
latest_df = latest_df[latest_df["Status"].str.upper() != "CLOSED"].copy()

# ---------------------------
# None / fehlende Freie Plätze rausfiltern
# ---------------------------
latest_df["FreiePlaetze"] = pd.to_numeric(latest_df["FreiePlaetze"], errors="coerce")
latest_df = latest_df[latest_df["FreiePlaetze"].notna()].copy()

# ---------------------------
# Auslastung berechnen
# ---------------------------
KAPAZITAET = 130  # Gesamtbetten der Hütte

latest_df["FixGebucht"] = KAPAZITAET - latest_df["Kapazität"]
latest_df["OnlineGebucht"] = latest_df["Kapazität"] - latest_df["FreiePlaetze"]

# ---------------------------
# Wetterdaten abrufen
# ---------------------------
@st.cache_data(ttl=3600)
def load_weather():
    lat = 47.085
    lon = 11.195
    weather_url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        "&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,weathercode"
        "&timezone=Europe/Vienna"
    )
    try:
        response = requests.get(weather_url)
        response.raise_for_status()
        daily = response.json()["daily"]
        weather_df = pd.DataFrame({
            "Datum": pd.to_datetime(daily["time"]),
            "Tmin °C": daily["temperature_2m_min"],
            "Tmax °C": daily["temperature_2m_max"],
            "Regen mm": daily["precipitation_sum"],
            "Wettercode": daily["weathercode"]
        })
        return weather_df
    except Exception as e:
        st.warning(f"Wetterdaten konnten nicht geladen werden: {e}")
        return pd.DataFrame()

weather_df = load_weather()

def weather_icon(code):
    if code == 0:
        return "☀️ Klar"
    elif code in [1,2,3]:
        return "🌤 Teilweise bewölkt"
    elif code in [45,48]:
        return "🌫 Nebel"
    elif code in [51,53,55]:
        return "🌦 Nieselregen"
    elif code in [61,63,65]:
        return "🌧 Regen"
    elif code in [71,73,75]:
        return "❄️ Schnee"
    elif code == 95:
        return "⛈ Gewitter"
    else:
        return "🌥 Unbekannt"

if not weather_df.empty:
    weather_df["Wetter"] = weather_df["Wettercode"].apply(weather_icon)

# ---------------------------
# Daten kombinieren
# ---------------------------
combined = latest_df.copy()
if not weather_df.empty:
    combined = combined.merge(weather_df, left_on="Buchungsdatum", right_on="Datum", how="left")

# ---------------------------
# Tabelle anzeigen
# ---------------------------
st.subheader(f"📅 Aktueller Stand vom {latest_date.date()}")
st.dataframe(
    combined[["Buchungsdatum","OnlineGebucht","FixGebucht","Wetter","Tmin °C","Tmax °C","Regen mm"]].sort_values("Buchungsdatum"),
    use_container_width=True
)

# ---------------------------
# Stacked Bar Chart: Aktuelle Auslastung
# ---------------------------
st.subheader("Aktuelle Auslastung")

stack_data = combined.melt(
    id_vars=["Buchungsdatum"],
    value_vars=["FixGebucht","OnlineGebucht"],  # Frei weggelassen
    var_name="Typ",
    value_name="Plaetze"
)

chart = alt.Chart(stack_data).mark_bar().encode(
    x=alt.X("Buchungsdatum:T", title="Datum"),
    y=alt.Y("Plaetze:Q", title="Belegte Betten"),
    color=alt.Color("Typ:N", scale=alt.Scale(
        domain=["OnlineGebucht","FixGebucht"],
        range=["#7EFCAE","#FF8279"]
    ))
)

st.altair_chart(chart, use_container_width=True)

# ---------------------------
# Historische Min/Max Belegung
# ---------------------------
st.subheader("Minimale und maximale Belegung")

# Alle gültigen historischen Tage
hist_df = df[df["FreiePlaetze"].notna() & (df["Status"].str.upper() != "CLOSED")].copy()
hist_df["Belegt"] = KAPAZITAET - hist_df["FreiePlaetze"]

# Min/Max pro Tag
minmax_df = hist_df.groupby("Buchungsdatum")["Belegt"].agg(["min","max"]).reset_index()

area = alt.Chart(minmax_df).mark_area(opacity=0.3, color="#FF2222B5").encode(
    x="Buchungsdatum:T",
    y="min(Belegt):Q",
    y2="max(Belegt):Q"
)

line_min = alt.Chart(minmax_df).mark_line(color="#A1362E").encode(
    x="Buchungsdatum:T",
    y="min(Belegt):Q"
)

line_max = alt.Chart(minmax_df).mark_line(color="#00FF37A6").encode(
    x="Buchungsdatum:T",
    y="max(Belegt):Q"
)

st.altair_chart(area + line_min + line_max, use_container_width=True)
