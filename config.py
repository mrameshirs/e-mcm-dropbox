# # config.py
import streamlit as st

# --- Dropbox Configuration ---
DROPBOX_APP_KEY = st.secrets.get("dropbox_app_key", "")
DROPBOX_APP_SECRET = st.secrets.get("dropbox_app_secret", "")
#DROPBOX_API_TOKEN = st.secrets.get("dropbox_api_token", "")
# NEW: Use the refresh token
DROPBOX_REFRESH_TOKEN = st.secrets.get("dropbox_refresh_token", "")
# --- Centralized Folders and Files ---
DROPBOX_ROOT_PATH = "/e-MCM_App"
DAR_PDFS_PATH = f"{DROPBOX_ROOT_PATH}/DAR_PDFs"
OFFICE_ORDERS_PATH = f"{DROPBOX_ROOT_PATH}/Office_Orders" # Path for allocation/reallocation orders
MCM_DATA_PATH = f"{DROPBOX_ROOT_PATH}/mcm_dar_data.xlsx"
LOG_SHEET_PATH = f"{DROPBOX_ROOT_PATH}/log_sheet.xlsx"
SMART_AUDIT_DATA_PATH = f"{DROPBOX_ROOT_PATH}/smart_audit_data.xlsx"
MCM_PERIODS_INFO_PATH = f"{DROPBOX_ROOT_PATH}/mcm_periods_info.xlsx"


# --- User Credentials ---
USER_CREDENTIALS = {
    "planning_officer": "pco_password",
    **{f"audit_group{i}": f"ag{i}_audit" for i in range(1, 31)}
}
USER_ROLES = {
    "planning_officer": "PCO",
    **{f"audit_group{i}": "AuditGroup" for i in range(1, 31)}
}
AUDIT_GROUP_NUMBERS = {
    f"audit_group{i}": i for i in range(1, 31)
}
