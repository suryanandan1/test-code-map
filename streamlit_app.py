import os

import requests
import streamlit as st

API_URL = os.getenv("MAPPING_API_URL", "http://localhost:8000/map-test")

st.title("Test Description Mapper")
test_description = st.text_input("Test Description")
code_type = st.selectbox("Code Type", ["local", "loinc"])

if st.button("Search"):
    if not test_description.strip():
        st.warning("Please enter a test description.")
        st.stop()

    try:
        response = requests.post(
            API_URL,
            json={"test_description": test_description, "code_type": code_type},
            timeout=30,
        )
    except requests.RequestException:
        st.error(f"Could not reach the mapping API at {API_URL}. Is it running?")
        st.stop()

    if response.status_code == 200:
        data = response.json()
        st.success("Match Found")
        st.write("Matched Test:", data["matched_test"])
        st.write("Code:", data["code"])
        st.write("Score:", data["match_score"])
    elif response.status_code == 404:
        st.error(response.json()["detail"])
    else:
        st.error(f"API error {response.status_code}: {response.text}")
