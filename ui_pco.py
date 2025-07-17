# ui_pco.py
import streamlit as st
import datetime
import time
import pandas as pd
import plotly.express as px
from streamlit_option_menu import option_menu
import math

from dropbox_utils import read_from_spreadsheet, update_spreadsheet_from_df
from config import MCM_PERIODS_INFO_PATH, MCM_DATA_PATH
from ui_mcm_agenda import mcm_agenda_tab
from ui_pco_reports import pco_reports_dashboard

def pco_dashboard(dbx):
    st.markdown("<div class='sub-header'>Planning & Coordination Officer Dashboard</div>", unsafe_allow_html=True)
    mcm_periods = read_from_spreadsheet(dbx, MCM_PERIODS_INFO_PATH)

    with st.sidebar:
        try:
            st.image("logo.png", width=80)
        except Exception as e:
            st.sidebar.warning(f"Could not load logo.png: {e}")
            st.sidebar.markdown("*(Logo)*")

        st.markdown(f"**User:** {st.session_state.username}")
        st.markdown(f"**Role:** {st.session_state.role}")
        if st.button("Logout", key="pco_logout_full_final_v2", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.username = ""
            st.session_state.role = ""
            st.rerun()
        st.markdown("---")
        if st.button("🚀 Smart Audit Tracker", key="launch_sat_pco"):
            st.session_state.app_mode = "smart_audit_tracker"
            st.rerun()
        st.markdown("---")

    selected_tab = option_menu(
        menu_title=None,
        options=["Create MCM Period", "Manage MCM Periods", "View Uploaded Reports", "MCM Agenda", "Visualizations", "Reports"],
        icons=["calendar-plus-fill", "sliders", "eye-fill", "journal-richtext", "bar-chart-fill", "file-earmark-text-fill"],
        menu_icon="gear-wide-connected",
        default_index=0,
        orientation="horizontal",
        styles={
            "container": {"padding": "5px !important", "background-color": "#e9ecef"},
            "icon": {"color": "#007bff", "font-size": "20px"},
            "nav-link": {"font-size": "16px", "text-align": "center", "margin": "0px", "--hover-color": "#d1e7fd"},
            "nav-link-selected": {"background-color": "#007bff", "color": "white"},
        })

    st.markdown("<div class='card'>", unsafe_allow_html=True)

    if selected_tab == "Create MCM Period":
        st.markdown("<h3>Create New MCM Period</h3>", unsafe_allow_html=True)
        current_year = datetime.datetime.now().year
        years = list(range(current_year - 1, current_year + 3))
        months = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
        
        col1, col2 = st.columns(2)
        with col1:
            selected_year = st.selectbox("Select Year", options=years, index=years.index(current_year))
        with col2:
            selected_month_name = st.selectbox("Select Month", options=months, index=datetime.datetime.now().month - 1)
        
        if st.button(f"Create MCM for {selected_month_name} {selected_year}", use_container_width=True):
            new_period = pd.DataFrame([{"year": selected_year, "month_name": selected_month_name, "active": True}])
            updated_periods = pd.concat([mcm_periods, new_period], ignore_index=True)
            if update_spreadsheet_from_df(dbx, updated_periods, MCM_PERIODS_INFO_PATH):
                st.success("MCM Period created successfully.")
                st.rerun()
            else:
                st.error("Failed to create MCM Period.")

    elif selected_tab == "Manage MCM Periods":
        st.markdown("<h3>Manage Existing MCM Periods</h3>", unsafe_allow_html=True)
        if not mcm_periods.empty:
            edited_df = st.data_editor(mcm_periods, use_container_width=True, hide_index=True, num_rows="dynamic")
            if st.button("Save Changes", use_container_width=True):
                if update_spreadsheet_from_df(dbx, edited_df, MCM_PERIODS_INFO_PATH):
                    st.success("Changes saved successfully.")
                    st.rerun()
                else:
                    st.error("Failed to save changes.")
        else:
            st.info("No MCM periods to manage.")

    elif selected_tab == "View Uploaded Reports":
        st.markdown("<h3>View Uploaded Reports Summary</h3>", unsafe_allow_html=True)
        df_reports = read_from_spreadsheet(dbx, MCM_DATA_PATH)
        if not df_reports.empty:
            st.dataframe(df_reports, use_container_width=True)
        else:
            st.info("No reports have been uploaded yet.")

    elif selected_tab == "MCM Agenda":
        mcm_agenda_tab(dbx, mcm_periods)

    elif selected_tab == "Visualizations":
        st.markdown("<h3>Data Visualizations</h3>", unsafe_allow_html=True)
        df_reports = read_from_spreadsheet(dbx, MCM_DATA_PATH)
        if not df_reports.empty:
            # Example visualization
            st.markdown("<h4>Detections vs. Recoveries</h4>", unsafe_allow_html=True)
            fig = px.scatter(df_reports, x="total_amount_detected_overall_rs", y="total_amount_recovered_overall_rs",
                             hover_data=['trade_name'])
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No data to visualize.")
            
    elif selected_tab == "Reports":
        pco_reports_dashboard(dbx)

    st.markdown("</div>", unsafe_allow_html=True)
