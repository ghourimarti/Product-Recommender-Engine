"""
Anime Recommender — Streamlit frontend.
Communicates with the FastAPI backend via JWT-authenticated REST + SSE streaming.
"""
import os

import requests
import streamlit as st

API_BASE = os.getenv("API_BASE", "http://localhost:8000/v1")

st.set_page_config(
    page_title="Anime Recommender",
    layout="wide",
    page_icon="🎌",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Session state initialisation
# ---------------------------------------------------------------------------
for key, default in [
    ("token", None),
    ("username", ""),
    ("role", ""),
    ("session_cost_usd", 0.0),
    ("request_count", 0),
]:
    if key not in st.session_state:
        st.session_state[key] = default


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------
def _login(username: str, password: str) -> bool:
    try:
        r = requests.post(
            f"{API_BASE}/auth/token",
            json={"username": username, "password": password},
            timeout=10,
        )
        if r.status_code == 200:
            data = r.json()
            st.session_state.token = data["access_token"]
            st.session_state.username = username
            return True
        return False
    except requests.RequestException:
        return False


def _auth_header() -> dict:
    return {"Authorization": f"Bearer {st.session_state.token}"}


# ---------------------------------------------------------------------------
# Login gate
# ---------------------------------------------------------------------------
if not st.session_state.token:
    st.title("🎌 Anime Recommender")
    st.markdown("#### Sign in to get started")

    col, _ = st.columns([1, 2])
    with col:
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Sign in", use_container_width=True)
            if submitted:
                if _login(username, password):
                    st.rerun()
                else:
                    st.error("Invalid credentials.  Try **user / user123** or **admin / admin123**")

    st.caption("Demo credentials: `user / user123`  |  Admin: `admin / admin123`")
    st.stop()


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown(f"### Signed in as `{st.session_state.username}`")
    st.divider()

    st.metric("Session Cost", f"${st.session_state.session_cost_usd:.6f}")
    st.metric("Requests This Session", st.session_state.request_count)

    if st.button("Sign out", use_container_width=True):
        for key in ("token", "username", "role", "session_cost_usd", "request_count"):
            st.session_state[key] = None if key == "token" else (0.0 if "cost" in key else (0 if "count" in key else ""))
        st.rerun()

    st.divider()
    st.caption("**API endpoints**")
    st.caption(f"`POST {API_BASE}/recommend`")
    st.caption(f"`GET  {API_BASE}/admin/usage`")

    # Admin panel
    if st.session_state.username == "admin":
        st.divider()
        st.markdown("### Admin Panel")
        if st.button("Refresh Usage Stats", use_container_width=True):
            try:
                r = requests.get(f"{API_BASE}/admin/usage", headers=_auth_header(), timeout=5)
                if r.status_code == 200:
                    data = r.json()
                    st.json(data)
                else:
                    st.error(f"Error: {r.status_code}")
            except requests.RequestException as e:
                st.error(f"Connection error: {e}")


# ---------------------------------------------------------------------------
# Main UI
# ---------------------------------------------------------------------------
st.title("🎌 Anime Recommender")
st.markdown("Describe what you're in the mood for and get three tailored anime picks.")

query = st.text_input(
    "Your preferences",
    placeholder="e.g. dark psychological thriller with morally complex characters",
    max_chars=500,
    label_visibility="collapsed",
)

col_btn, col_note = st.columns([1, 4])
with col_btn:
    search_clicked = st.button("Get Recommendations", type="primary", use_container_width=True)
with col_note:
    st.caption("Responses stream in real time. Rate limit: 10 requests/min.")

if search_clicked and query.strip():
    placeholder = st.empty()
    cost_placeholder = st.empty()
    full_text = ""

    try:
        with requests.post(
            f"{API_BASE}/recommend",
            json={"query": query.strip()},
            headers=_auth_header(),
            stream=True,
            timeout=60,
        ) as response:
            if response.status_code == 422:
                detail = response.json().get("detail", "Query rejected by safety filter.")
                st.warning(f"Query blocked: {detail}")

            elif response.status_code == 401:
                st.error("Session expired. Please sign in again.")
                st.session_state.token = None
                st.rerun()

            elif response.status_code == 429:
                st.warning("Rate limit reached (10 req/min). Please wait a moment.")

            elif response.status_code == 200:
                st.session_state.request_count += 1
                st.markdown("### Recommendations")
                output_area = st.empty()

                for raw_line in response.iter_lines():
                    if not raw_line:
                        continue
                    line = raw_line if isinstance(raw_line, str) else raw_line.decode("utf-8")
                    if not line.startswith("data: "):
                        continue

                    chunk = line[6:]

                    if chunk == "[DONE]":
                        break
                    elif chunk.startswith("__cost__"):
                        cost = float(chunk.replace("__cost__", ""))
                        st.session_state.session_cost_usd += cost
                        cost_placeholder.caption(f"This request: ${cost:.6f} USD")
                    elif chunk.startswith("[ERROR]"):
                        st.error(chunk)
                        break
                    else:
                        full_text += chunk
                        output_area.markdown(full_text)
            else:
                st.error(f"Unexpected server error ({response.status_code}). Please try again.")

    except requests.ConnectionError:
        st.error("Cannot reach the backend. Is the server running?")
    except requests.Timeout:
        st.error("Request timed out. The server may be overloaded.")

elif search_clicked and not query.strip():
    st.warning("Please enter your anime preferences before searching.")
