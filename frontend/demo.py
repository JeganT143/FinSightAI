"""Minimal pure-Python client for the v2 SSE protocol.

The real frontend is the Next.js app in frontend/web (see DESIGN.md);
this exists so the backend can be demoed with nothing but Python:

    uv run streamlit run frontend/demo.py
"""

import json

import requests
import streamlit as st

st.set_page_config(page_title="FinSightAI (lite)", page_icon="📈", layout="wide")
st.title("FinSightAI — lite console")
st.caption("Minimal Streamlit client. The full experience is the Next.js console on :3000.")

col_input, col_button = st.columns([4, 1])
ticker = col_input.text_input("Ticker", placeholder="NVDA", max_chars=5).upper().strip()
run = col_button.button("Run research", use_container_width=True)

if run and ticker:
    if not ticker.isalpha():
        st.error("Tickers are 1-5 letters, e.g. NVDA.")
        st.stop()

    tape = st.status(f"Researching {ticker}...", expanded=True)
    report_slot = st.empty()

    try:
        with requests.post(
            "http://localhost:8000/api/research/stream",
            json={"ticker": ticker},
            stream=True,
            timeout=300,
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if not line.startswith(b"data: "):
                    continue
                try:
                    event = json.loads(line[6:])
                except json.JSONDecodeError:
                    continue

                etype = event.get("type")
                if etype == "phase":
                    tape.write(f"⏳ {event['message']}")
                elif etype == "grounding":
                    tape.write(f"📄 {event['detail']}")
                elif etype == "agent_completed":
                    usage = event["usage"]
                    score = event["data"].get("score", event["data"].get("overall_score"))
                    tape.write(
                        f"✅ {event['agent']} — score {score} · "
                        f"${usage['cost_usd']:.4f} · {usage['latency_ms'] / 1000:.1f}s"
                    )
                elif etype == "critic_verdict":
                    icon = "🛑" if event["blocks_publication"] else "🟢"
                    tape.write(
                        f"{icon} critic: {len(event['challenges'])} challenge(s) — "
                        f"{event['assessment']}"
                    )
                elif etype == "complete":
                    report = event["report"]
                    usage = event["usage_summary"]
                    tape.update(label="Research complete", state="complete", expanded=False)
                    with report_slot.container():
                        st.subheader(f"{report['ticker']} — {report['verdict']} "
                                     f"({report['overall_score']}/10)")
                        st.markdown(report["narrative_markdown"])
                        st.caption(
                            f"{event['revision_count']} revision(s) · "
                            f"${usage['cost_usd']:.4f} · {usage['latency_ms'] / 1000:.1f}s"
                        )
                elif etype == "error":
                    tape.update(label="Run failed", state="error")
                    st.error(event["message"])
                    break
    except requests.exceptions.ConnectionError:
        st.error("Backend unreachable — start it on :8000 first.")
elif run:
    st.warning("Enter a ticker first.")
