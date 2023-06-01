import streamlit as st
from unitunes.streamlit.Unitunes import pm

# List services
st.header("Services")
# for service in pm.services:
#     st.write(service)
tabs = st.tabs(pm.services)
for tab, service in zip(tabs, pm.services):
    with tab:
        st.write(service)
