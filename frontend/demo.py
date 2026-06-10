import streamlit as st
import requests
import json

# ─────────────────────────────────────────
# Page config
# ─────────────────────────────────────────
st.set_page_config(page_title="FinSightAI", page_icon="📈", layout="wide")

st.title("📈 FinSightAI")
st.caption("Multi-agent investment research platform")

# ─────────────────────────────────────────
# Input
# ─────────────────────────────────────────
col1, col2 = st.columns([3, 1])

with col1:
    ticker = (
        st.text_input("Stock Ticker", placeholder="e.g. NVDA, AAPL, MSFT", max_chars=5)
        .upper()
        .strip()
    )

with col2:
    st.write("")
    st.write("")
    run = st.button("🔍 Analyze", use_container_width=True)

# ─────────────────────────────────────────
# Pipeline execution
# ─────────────────────────────────────────
if run and ticker:

    if not ticker.isalpha():
        st.error("Invalid ticker. Use letters only e.g. NVDA")
        st.stop()

    # Activity feed — shows agent events in real time
    st.subheader("🤖 Agent Activity")
    activity = st.container()

    # Report placeholder — fills in when complete
    st.subheader("📋 Research Report")
    report_placeholder = st.empty()

    # Status tracking
    progress_bar = st.progress(0)
    status_text = st.empty()

    progress_steps = {
        "start": 5,
        "progress": 20,
        "fundamentals": 40,
        "risk": 50,
        "sentiment": 60,
        "critic": 80,
        "complete": 100,
    }

    try:
        with requests.post(
            "http://localhost:8000/api/research/stream",
            json={"ticker": ticker},
            stream=True,
            timeout=120,
        ) as response:

            response.raise_for_status()
            current_progress = 0

            for line in response.iter_lines():
                if not line:
                    continue

                # SSE lines start with "data: "
                if line.startswith(b"data: "):
                    raw = line[6:]  # strip "data: " prefix

                    try:
                        event = json.loads(raw)
                    except json.JSONDecodeError:
                        continue

                    event_type = event.get("type")

                    # Update progress bar
                    if event_type in progress_steps:
                        new_progress = progress_steps[event_type]
                        if new_progress > current_progress:
                            current_progress = new_progress
                            progress_bar.progress(current_progress)

                    # Render each event type differently
                    if event_type == "start":
                        status_text.info(f"🚀 {event['message']}")
                        with activity:
                            st.info(f"🚀 {event['message']}")

                    elif event_type == "progress":
                        status_text.info(f"⏳ {event['message']}")
                        with activity:
                            st.info(f"⏳ {event['message']}")

                    elif event_type == "fundamentals":
                        with activity:
                            with st.expander(
                                "📊 Fundamentals Agent — complete", expanded=False
                            ):
                                st.markdown(event["data"])

                    elif event_type == "risk":
                        with activity:
                            with st.expander(
                                "⚠️ Risk Agent — complete", expanded=False
                            ):
                                st.markdown(event["data"])

                    elif event_type == "sentiment":
                        with activity:
                            with st.expander(
                                "💬 Sentiment Agent — complete", expanded=False
                            ):
                                st.markdown(event["data"])

                    elif event_type == "critic":
                        challenges = event["challenges_found"]
                        blocks = event["blocks_publication"]
                        assessment = event["assessment"]

                        with activity:
                            if blocks:
                                st.warning(
                                    f"🔍 Critic found {challenges} challenges — "
                                    f"requesting revision\n\n_{assessment}_"
                                )
                            else:
                                st.success(
                                    f"✅ Critic approved — "
                                    f"{challenges} minor notes\n\n_{assessment}_"
                                )

                    elif event_type == "complete":
                        progress_bar.progress(100)
                        status_text.success("✅ Research complete")

                        # Render the final report
                        report_placeholder.markdown(event["report"])

                        # Show metadata
                        st.divider()
                        meta_col1, meta_col2, meta_col3 = st.columns(3)
                        with meta_col1:
                            st.metric("Ticker", event["ticker"])
                        with meta_col2:
                            st.metric(
                                "Report Revised",
                                "Yes" if event["was_revised"] else "No",
                            )
                        with meta_col3:
                            st.metric("Report ID", event["report_id"][:8] + "...")

                    elif event_type == "error":
                        st.error(f"❌ Pipeline error: {event['message']}")
                        break

    except requests.exceptions.ConnectionError:
        st.error(
            "Cannot connect to backend. Make sure the server is running on port 8000."
        )
    except requests.exceptions.Timeout:
        st.error("Request timed out. The pipeline took too long.")
    except Exception as e:
        st.error(f"Unexpected error: {str(e)}")

elif run and not ticker:
    st.warning("Please enter a ticker symbol.")
