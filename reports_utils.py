# reports_utils.py
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

from dropbox_utils import read_from_spreadsheet
from config import LOG_SHEET_PATH

# These are the expected column names in the log sheet.
LOG_SHEET_COLUMNS = ['Timestamp', 'Username', 'Role']

@st.cache_data(ttl=300)
def get_log_data(_dbx):
    """
    Reads and caches data from the log spreadsheet on Dropbox.
    The _dbx argument is prefixed with an underscore to indicate it's
    used for caching purposes and shouldn't be hashed by Streamlit's caching mechanism.
    """
    df = read_from_spreadsheet(_dbx, LOG_SHEET_PATH)
    
    if df.empty or not all(col in df.columns for col in LOG_SHEET_COLUMNS):
         return pd.DataFrame(columns=LOG_SHEET_COLUMNS)
         
    return df

def generate_login_report(df_logs, days):
    """Processes the log DataFrame to generate the login activity report."""
    if df_logs.empty:
        return pd.DataFrame()

    # Ensure timestamp column is in datetime format
    df_logs['Timestamp'] = pd.to_datetime(df_logs['Timestamp'], errors='coerce')
    df_logs.dropna(subset=['Timestamp'], inplace=True)

    # Filter logs for the selected time period
    cutoff_date = datetime.now() - timedelta(days=days)
    filtered_logs = df_logs[df_logs['Timestamp'] >= cutoff_date]

    if filtered_logs.empty:
        return pd.DataFrame()

    # Count logins and sort the results
    login_counts = filtered_logs.groupby(['Username', 'Role']).size().reset_index(name='Login Count')
    report = login_counts.sort_values(by='Login Count', ascending=False).reset_index(drop=True)
    
    return report