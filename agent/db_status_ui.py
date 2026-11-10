"""A small database-status block for a Streamlit sidebar. The check (a trivial query per database) is cached for five minutes, so opening a page keeps both Aura instances active without
hammering them. Failures are shown with the reason and the fix; the page itself is never blocked."""
import streamlit as st

from agent.neo4j_health import check_all


@st.cache_data(ttl=300, show_spinner=False)
def _status() -> list:
    return check_all()


def render_sidebar_status() -> None:
    with st.sidebar:
        st.markdown("#### Databases")
        for r in _status():
            st.markdown(f"{'✅' if r['ok'] else '❌'} **{r['name']}** — {r['summary']}")
            if not r["ok"]:
                st.caption(r["hint"])
        if st.button("Re-check databases", key="recheck_dbs"):
            _status.clear()
            st.rerun()
