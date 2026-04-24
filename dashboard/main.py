import streamlit as st
import requests  # type: ignore[import-untyped]
import pandas as pd
import plotly.express as px
import time
from datetime import datetime
import os

st.set_page_config(
    page_title="Auction Analytics Dashboard", page_icon="📈", layout="wide"
)

st.title("📊 Real-Time Auction Analytics")
st.markdown(f"**Last updated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# Use environment variable (set in docker-compose.yml)
API_URL = os.getenv("API_URL", "http://api:8000")
# Auto-refresh every 5 seconds
if "last_refresh" not in st.session_state:
    st.session_state.last_refresh = time.time()

# Sidebar controls
st.sidebar.header("Controls")
refresh_rate = st.sidebar.slider("Refresh interval (seconds)", 5, 30, 5)
auto_refresh = st.sidebar.checkbox("Auto-refresh", value=True)

if auto_refresh and (time.time() - st.session_state.last_refresh > refresh_rate):
    st.rerun()

# ====================== Fetch Data ======================


@st.cache_data(ttl=5)
def fetch_data(endpoint: str):
    try:
        response = requests.get(f"{API_URL}{endpoint}", timeout=10)
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"API error {response.status_code}: {response.text}")
            return None
    except Exception as e:
        st.error(f"Failed to connect to API: {e}")
        return None


# Fetch data
funnel = fetch_data("/api/funnel")
top_items = fetch_data("/api/top-items?limit=10")
revenue = fetch_data("/api/revenue?hours=24")
stats = fetch_data("/api/stats")
recent = fetch_data("/api/recent-events?limit=15")

# ====================== Layout ======================

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Total Views", f"{stats['views']:,}" if stats else "—")
with col2:
    st.metric("Total Bids", f"{stats['bids']:,}" if stats else "—")
with col3:
    st.metric("Total Purchases", f"{stats['purchases']:,}" if stats else "—")
with col4:
    st.metric(
        "Overall Conversion", f"{funnel['view_to_bid_rate']:.1f}%" if funnel else "—"
    )

# Row 2: Funnel & Top Items
col_a, col_b = st.columns([1, 1])

with col_a:
    st.subheader("Conversion Funnel")
    if funnel:
        funnel_data = pd.DataFrame(
            {
                "Stage": ["Views", "Bids", "Purchases"],
                "Count": [
                    funnel["total_views"],
                    funnel["total_bids"],
                    funnel["total_purchases"],
                ],
            }
        )
        fig_funnel = px.bar(
            funnel_data,
            x="Stage",
            y="Count",
            text="Count",
            color="Stage",
            color_discrete_sequence=["#636EFA", "#EF553B", "#00CC96"],
        )
        st.plotly_chart(fig_funnel, use_container_width=True)

with col_b:
    st.subheader("Top 10 Items by Bids")
    if (
        top_items
        and len(top_items) > 0
        and isinstance(top_items[0], dict)
        and "error" not in top_items[0]
    ):
        df_top = pd.DataFrame(top_items)
        fig_top = px.bar(
            df_top,
            x="item_id",
            y="bid_count",
            text="bid_count",
            title="Top Items by Bid Count",
        )
        st.plotly_chart(fig_top, use_container_width=True)
    else:
        st.info("No bid data yet — keep the producer running")

# Row 3: Revenue Trend
st.subheader("Revenue Trend (Last 24 Hours)")
if revenue:
    df_rev = pd.DataFrame(revenue)
    if not df_rev.empty:
        fig_rev = px.line(
            df_rev, x="hour", y="revenue", markers=True, title="Hourly Revenue"
        )
        st.plotly_chart(fig_rev, use_container_width=True)

# Row 4: Recent Events
st.subheader("Recent Events")
if recent:
    df_recent = pd.DataFrame(recent)
    if not df_recent.empty:
        st.dataframe(df_recent, use_container_width=True, hide_index=True)

# Footer
st.caption("Real-Time Auction Analytics Pipeline • Phase 5 Dashboard")
