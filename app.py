# app.py
import streamlit as st
import pandas as pd

# --- Custom Module Imports ---
from config import USER_CREDENTIALS, USER_ROLES, AUDIT_GROUP_NUMBERS
from css_styles import load_custom_css
from dropbox_utils import get_dropbox_client, log_activity # <-- Key imports
# Removed ui_login as login is handled here now
from ui_pco import pco_dashboard
from ui_audit_group import audit_group_dashboard
from ui_smart_audit_tracker import smart_audit_tracker_dashboard, audit_group_tracker_view

# Load custom CSS styles
load_custom_css()

# --- Session State Initialization ---
def initialize_session_state():
    """Initializes all required session state variables."""
    states = {
        'logged_in': False,
        'username': "",
        'role': "",
        'audit_group_no': None,
        'dbx': None,
        'app_mode': "e-mcm"
    }
    for key, value in states.items():
        if key not in st.session_state:
            st.session_state[key] = value

initialize_session_state()

# --- Main Application Logic ---
if not st.session_state.logged_in:
    st.title("e-MCM Application Login")
    
    # --- LOGIN FORM ---
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")

        if submitted:
            # Check credentials using the dictionaries from config.py
            if username in USER_CREDENTIALS and password == USER_CREDENTIALS[username]:
                # --- SUCCESSFUL LOGIN ---
                st.session_state.logged_in = True
                st.session_state.username = username
                st.session_state.role = USER_ROLES.get(username)
                st.session_state.audit_group_no = AUDIT_GROUP_NUMBERS.get(username)

                with st.spinner("Connecting and logging your session..."):
                    dbx = get_dropbox_client()
                    if dbx:
                        st.session_state.dbx = dbx
                        # --- CALL LOG_ACTIVITY HERE ---
                        log_activity(dbx, username, st.session_state.role)
                    else:
                        st.error("Failed to connect to Dropbox. Cannot log in.")
                        st.session_state.logged_in = False # Reset login status on failure
                
                # Rerun to show the dashboard
                st.rerun()
            else:
                st.error("Invalid username or password.")
else:
    # --- USER IS LOGGED IN, SHOW DASHBOARD ---
    dbx = st.session_state.dbx
    if dbx:
        # Route to the correct view based on app_mode and role
        if st.session_state.app_mode == "smart_audit_tracker":
            if st.session_state.role == "PCO":
                smart_audit_tracker_dashboard(dbx)
            elif st.session_state.role == "AuditGroup":
                audit_group_tracker_view(dbx)
        else:  # Default "e-mcm" mode
            if st.session_state.role == "PCO":
                pco_dashboard(dbx)
            elif st.session_state.role == "AuditGroup":
                audit_group_dashboard(dbx)
            else:
                st.error("Unknown user role. Please login again.")
                st.session_state.logged_in = False
                st.rerun()
    else:
        # This case handles if the page is reloaded after login and dbx client is lost
        st.warning("Connection to Dropbox lost. Please log out and back in.")
        if st.button("Logout"):
            # Clear session state on logout
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()
# # app.py
# import streamlit as st
# import pandas as pd
# from io import BytesIO

# # --- Custom Module Imports ---
# from config import (
#     DROPBOX_ROOT_PATH, DAR_PDFS_PATH, MCM_DATA_PATH,
#     LOG_SHEET_PATH, SMART_AUDIT_DATA_PATH, MCM_PERIODS_INFO_PATH,
#     OFFICE_ORDERS_PATH
# )
# from css_styles import load_custom_css
# from dropbox_utils import get_dropbox_client, create_folder, upload_file
# from ui_login import login_page
# from ui_pco import pco_dashboard
# from ui_audit_group import audit_group_dashboard
# from ui_smart_audit_tracker import smart_audit_tracker_dashboard, audit_group_tracker_view

# # Load custom CSS styles
# load_custom_css()

# # --- Session State Initialization ---
# def initialize_session_state():
#     """Initializes all required session state variables."""
#     states = {
#         'logged_in': False,
#         'username': "",
#         'role': "",
#         'audit_group_no': None,
#         'dbx': None,
#         'dropbox_initialized': False,
#         'app_mode': "e-mcm"
#     }
#     for key, value in states.items():
#         if key not in st.session_state:
#             st.session_state[key] = value

# initialize_session_state()

# # --- Main Application Logic ---
# if not st.session_state.logged_in:
#     login_page()
# else:
#     if not st.session_state.dbx:
#         with st.spinner("Connecting to Dropbox..."):
#             st.session_state.dbx = get_dropbox_client()
#             if st.session_state.dbx:
#                 st.rerun()

#     if st.session_state.dbx:
#         if not st.session_state.dropbox_initialized:
#             with st.spinner("Initializing Dropbox structure..."):
#                 dbx = st.session_state.dbx
#                 # Create all necessary folders
#                 for folder_path in [DROPBOX_ROOT_PATH, DAR_PDFS_PATH, OFFICE_ORDERS_PATH]:
#                     create_folder(dbx, folder_path)
                
#                 # Initialize centralized Excel files if they don't exist
#                 for path in [MCM_DATA_PATH, LOG_SHEET_PATH, SMART_AUDIT_DATA_PATH, MCM_PERIODS_INFO_PATH]:
#                     try:
#                         dbx.files_get_metadata(path)
#                     except Exception:
#                         # This is the corrected part
#                         output = BytesIO()
#                         pd.DataFrame().to_excel(output, index=False, engine='xlsxwriter')
#                         file_content = output.getvalue()
#                         upload_file(dbx, file_content, path)

#                 st.session_state.dropbox_initialized = True
#                 st.rerun()

#         if st.session_state.dropbox_initialized:
#             dbx = st.session_state.dbx
#             if st.session_state.app_mode == "smart_audit_tracker":
#                 if st.session_state.role == "PCO":
#                     smart_audit_tracker_dashboard(dbx)
#                 elif st.session_state.role == "AuditGroup":
#                     audit_group_tracker_view(dbx)
#             else:
#                 if st.session_state.role == "PCO":
#                     pco_dashboard(dbx)
#                 elif st.session_state.role == "AuditGroup":
#                     audit_group_dashboard(dbx)
#                 else:
#                     st.error("Unknown user role. Please login again.")
#                     st.session_state.logged_in = False
#                     st.rerun()

#     elif st.session_state.logged_in:
#         st.warning("Could not connect to Dropbox. Please check configuration and network.")
#         if st.button("Logout"):
#             st.session_state.logged_in = False
#             st.rerun()
