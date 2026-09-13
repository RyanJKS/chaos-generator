import streamlit as st

from generator import RunConfig, TrafficRunner

st.set_page_config(page_title="Chaos Generator", page_icon="🌪️")
st.title("Chaos Generator")
st.caption("Control the chaos. See how your system handles event traffic.")

if "runner" not in st.session_state:
    st.session_state.runner = TrafficRunner()
runner = st.session_state.runner


@st.fragment(run_every=1)
def controls() -> None:
    active = runner.is_running
    url = st.text_input(
        "Destination URL", placeholder="http://localhost:8000/events", disabled=active
    )
    rate = st.slider("Events/second", 1, 1000, 10, disabled=active)
    mode = st.selectbox("Streaming type", ["Real-time", "Batch", "Micro-batch"], disabled=active)
    interval = st.number_input(
        "Time between requests (seconds)",
        min_value=0.1,
        max_value=60.0,
        value=10.0 if mode == "Batch" else 1.0,
        step=0.1,
        key=f"interval_{mode}",
        disabled=active or mode == "Real-time",
    )
    if mode == "Real-time":
        st.caption(f"One JSON event per POST, every {1 / rate:.3f} seconds.")
    else:
        st.caption(
            f"One JSON array per POST, averaging {rate * interval:g} events per window. "
            "Batch defaults to 10 seconds; micro-batch defaults to 1 second."
        )
    start, stop = st.columns(2)
    if start.button("Start", disabled=active, type="primary", use_container_width=True):
        try:
            runner.start(RunConfig(url.strip(), rate, mode, interval))
        except ValueError as error:
            st.error(str(error))
        else:
            st.rerun()
    if stop.button("Stop", disabled=not active, use_container_width=True):
        runner.stop()
        st.rerun()

    stats = runner.snapshot()
    status = "Stopping…" if runner.stopping and runner.is_running else "Running"
    st.subheader(status if runner.is_running else "Stopped")
    events, sent, errors = st.columns(3)
    events.metric("Events delivered", stats["events"])
    sent.metric("Successful requests", stats["requests"])
    errors.metric("Failed requests", stats["errors"])
    st.caption(f"Last HTTP status: {stats['status'] or '—'}")
    if stats["error"]:
        st.error(stats["error"])
    st.caption("Best-effort rate. Stop before closing this tab. An in-flight request may finish.")


controls()
