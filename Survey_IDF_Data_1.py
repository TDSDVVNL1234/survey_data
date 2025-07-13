import streamlit as st

if 'google_service_account' not in st.secrets:
    st.error("Google credentials not found! Check your secrets configuration")
else:
    st.success("Credentials loaded successfully")
    # st.write(st.secrets.google_service_account)  # Debug (remove in production)
