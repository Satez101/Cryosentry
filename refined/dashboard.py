import sqlite3
import time
from datetime import datetime

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import config

st.set_page_config(page_title="CRYOSENTRY", page_icon="🧊", layout="wide")

TIER_COLORS = ["#22c55e", "#f59e0b", "#f97316", "#ef4444"]
DARK = dict(
    template="plotly_dark",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    margin=dict(l=10, r=10, t=30, b=10),
)

st.markdown(
    """
<style>
.big {font-size: 3.2rem; font-weight: 800; line-height: 1;}
.tier {font-size: 1.6rem; font-weight: 700; letter-spacing: .08em;}
.small {opacity: .7; font-size: .9rem;}
.block-container {padding-top: 1.2rem;}
</style>
""",
    unsafe_allow_html=True,
)

with st.sidebar:
    st.header("🧊 CRYOSENTRY")
    st.caption(config.SITE_NAME)
    minutes = st.select_slider(
        "Time window", options=[2, 5, 10, 30, 60, 240], value=10,
        format_func=lambda m: f"{m} min",
    )


def load(minutes):
    con = sqlite3.connect(f"file:{config.DB_PATH}?mode=ro", uri=True, timeout=5)
    since = time.time() - minutes * 60
    readings = pd.read_sql_query(
        "SELECT * FROM readings WHERE ts >= ? ORDER BY ts", con, params=(since,)
    )
    events = pd.read_sql_query("SELECT * FROM events ORDER BY ts DESC LIMIT 40", con)
    con.close()

    offset = -time.timezone if not time.daylight else -time.altzone
    for df in (readings, events):
        if not df.empty:
            df["time"] = pd.to_datetime(df["ts"], unit="s") + pd.Timedelta(seconds=offset)

    return readings, events


def gauge(risk, tier):
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=risk,
            number={"suffix": " / 100", "font": {"size": 40}},
            gauge={
                "axis": {"range": [0, 100]},
                "bar": {"color": TIER_COLORS[tier], "thickness": 0.3},
                "steps": [
                    {"range": [0, 25], "color": "rgba(34,197,94,.15)"},
                    {"range": [25, 50], "color": "rgba(245,158,11,.15)"},
                    {"range": [50, 75], "color": "rgba(249,115,22,.15)"},
                    {"range": [75, 100], "color": "rgba(239,68,68,.2)"},
                ],
            },
        )
    )
    fig.update_layout(height=250, **DARK)
    return fig


@st.fragment(run_every="2s")
def live():
    try:
        readings, events = load(minutes)
    except Exception as e:
        st.warning(f"Waiting for data. Start main.py first. ({e})")
        return

    if readings.empty:
        st.info("No readings in this window. Is main.py running?")
        return

    last = readings.iloc[-1]
    age = time.time() - last["ts"]
    online = age < config.HEARTBEAT_TIMEOUT_S

    analysed = readings.dropna(subset=["risk"])
    a = analysed.iloc[-1] if not analysed.empty else None
    tier = int(a["tier"]) if a is not None else 0
    risk = float(a["risk"]) if a is not None else 0.0

    h1, h2 = st.columns([3, 1])
    h1.markdown("## CRYOSENTRY · GLOF Early Detection")
    status = "🟢 ONLINE" if online else "🔴 SENSOR OFFLINE"
    h2.markdown(
        f"**{status}**  \n<span class='small'>updated {age:.0f} s ago</span>",
        unsafe_allow_html=True,
    )

    c1, c2, c3 = st.columns([1.3, 1, 1])
    c1.plotly_chart(gauge(risk, tier), use_container_width=True, key="gauge")
    c2.markdown(
        f"<div class='small'>RISK TIER</div>"
        f"<div class='tier' style='color:{TIER_COLORS[tier]}'>{config.TIER_NAMES[tier]}</div>",
        unsafe_allow_html=True,
    )

    ttb = a["ttb_min"] if a is not None else None
    if ttb is None or pd.isna(ttb):
        ttb_text, ttb_sub = "—", "water not rising"
    elif ttb == 0:
        ttb_text, ttb_sub = "BREACHED", "above danger level"
    else:
        ttb_text = f"{int(ttb)}:{int((ttb % 1) * 60):02d}"
        ttb_sub = "min:sec to danger level"

    c3.markdown(
        f"<div class='small'>ESTIMATED TIME TO BREACH</div>"
        f"<div class='big' style='color:{TIER_COLORS[tier]}'>{ttb_text}</div>"
        f"<div class='small'>{ttb_sub}</div>",
        unsafe_allow_html=True,
    )

    m = st.columns(5)
    m[0].metric("Water level", f"{last['level']:.1f} cm")
    m[1].metric("Rate of rise", f"{(a['rate'] if a is not None else 0):+.2f} cm/min")
    m[2].metric("Air temp", f"{last['air_temp']:.1f} °C")
    m[3].metric("Vibration", f"{last['vib']:.3f} g")
    m[4].metric(
        "Surge probability",
        f"{(a['surge_prob'] or 0) * 100:.0f}%" if a is not None else "—",
    )

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=readings["time"], y=readings["level"],
        name="Compensated level", line=dict(color="#38bdf8", width=3),
    ))
    fig.add_trace(go.Scatter(
        x=readings["time"], y=readings["raw_level"],
        name="Uncompensated", line=dict(color="#94a3b8", width=1, dash="dot"),
    ))
    fig.add_hline(
        y=config.DANGER_LEVEL_CM, line=dict(color="#ef4444", dash="dash"),
        annotation_text="DANGER LEVEL",
    )

    if a is not None and pd.notna(a["ttb_min"]) and a["ttb_min"] > 0:
        t_end = last["time"] + pd.Timedelta(minutes=float(a["ttb_min"]))
        fig.add_trace(go.Scatter(
            x=[last["time"], t_end], y=[last["level"], config.DANGER_LEVEL_CM],
            name="Forecast", line=dict(color="#f97316", dash="dot", width=2),
        ))

    fig.update_layout(
        height=330, title="Water level (cm)", yaxis_title="cm",
        legend=dict(orientation="h", y=-0.2), **DARK,
    )
    st.plotly_chart(fig, use_container_width=True, key="level")

    risk_fig = go.Figure()
    for lo, hi, idx in ((0, 25, 0), (25, 50, 1), (50, 75, 2), (75, 100, 3)):
        risk_fig.add_hrect(y0=lo, y1=hi, fillcolor=TIER_COLORS[idx], opacity=0.08, line_width=0)
    risk_fig.add_trace(go.Scatter(
        x=analysed["time"], y=analysed["risk"],
        name="Risk Index", line=dict(color="#e2e8f0", width=2),
    ))
    risk_fig.update_layout(
        height=250, title="GLOF Risk Index", yaxis=dict(range=[0, 100]), **DARK
    )
    st.plotly_chart(risk_fig, use_container_width=True, key="risk")

    st.subheader("Event log")
    if events.empty:
        st.caption("No events yet.")
    else:
        log = events[["time", "kind", "message"]].copy()
        log["time"] = log["time"].dt.strftime("%H:%M:%S")
        log["kind"] = log["kind"].replace({
            "REJECTED": "🛡️ REJECTED",
            "SENSOR_OFFLINE": "⚠️ SENSOR_OFFLINE",
            "TIER_CHANGE": "📈 TIER_CHANGE",
        })
        st.dataframe(log, hide_index=True, use_container_width=True, height=260)

    st.download_button(
        "Download data in this window (CSV)",
        readings.to_csv(index=False),
        file_name=f"cryosentry_{datetime.now():%Y%m%d_%H%M}.csv",
    )


live()
