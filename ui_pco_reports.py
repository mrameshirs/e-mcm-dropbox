# ui_pco_reports.py
import streamlit as st
import pandas as pd
from reports_utils import get_log_data, generate_login_report

def pco_reports_dashboard(dbx):
    """
    Displays the reports dashboard for the PCO.
    """
    st.markdown("<h3>Application Reports</h3>", unsafe_allow_html=True)

    st.markdown("<h4>User Login Activity</h4>", unsafe_allow_html=True)
    
    log_df = get_log_data(dbx)

    if log_df.empty:
        st.info("No login activity has been recorded yet.")
        return

    days_to_report = st.selectbox(
        "Select Time Period for Login Report",
        options=[7, 30, 90],
        format_func=lambda x: f"Last {x} Days"
    )

    if days_to_report:
        report_df = generate_login_report(log_df, days_to_report)
        if not report_df.empty:
            st.dataframe(report_df, use_container_width=True)
        else:
            st.info(f"No login activity in the last {days_to_report} days.")
