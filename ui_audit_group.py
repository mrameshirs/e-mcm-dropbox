# ui_audit_group.py
import streamlit as st
import pandas as pd
import datetime
import math
from io import BytesIO
import time
from streamlit_option_menu import option_menu
import html

# --- Custom Module Imports for Dropbox Version ---
from dropbox_utils import (
    read_from_spreadsheet,
    update_spreadsheet_from_df,
    upload_file,
    get_shareable_link 
)
from dar_processor import preprocess_pdf_text, get_structured_data_with_gemini, get_structured_data_from_llm
from validation_utils import validate_data_for_sheet, VALID_CATEGORIES, VALID_PARA_STATUSES
from config import (
    USER_CREDENTIALS,
    MCM_PERIODS_INFO_PATH,
    MCM_DATA_PATH,
    DAR_PDFS_PATH
)
from models import ParsedDARReport

# --- Constants and Configuration ---
SHEET_DATA_COLUMNS_ORDER = [
    "mcm_period", "audit_group_number", "audit_circle_number", "gstin", "trade_name",
    "category", "total_amount_detected_overall_rs", "total_amount_recovered_overall_rs",
    "audit_para_number", "audit_para_heading", "revenue_involved_lakhs_rs",
    "revenue_recovered_lakhs_rs", "status_of_para", "dar_pdf_path", "record_created_date"
]

DISPLAY_COLUMN_ORDER_EDITOR = [
    "audit_group_number", "audit_circle_number", "gstin", "trade_name", "category",
    "total_amount_detected_overall_rs", "total_amount_recovered_overall_rs",
    "audit_para_number", "audit_para_heading", "revenue_involved_lakhs_rs",
    "revenue_recovered_lakhs_rs", "status_of_para"
]

# --- Helper Functions ---

def calculate_audit_circle(audit_group_number_val):
    """Calculates the audit circle based on the audit group number."""
    try:
        agn = int(audit_group_number_val)
        if 1 <= agn <= 30:
            return math.ceil(agn / 3.0)
        return None
    except (ValueError, TypeError, AttributeError):
        return None

@st.cache_data(ttl=120)
def get_active_mcm_periods(_dbx):
    """
    Reads MCM periods from Dropbox, converts to a dictionary,
    and returns only the active ones. Caches the result.
    """
    df_periods = read_from_spreadsheet(_dbx, MCM_PERIODS_INFO_PATH)
    if df_periods.empty:
        return {}
    
    if 'month_name' not in df_periods.columns or 'year' not in df_periods.columns:
        st.error("The 'mcm_periods_info.xlsx' file is missing 'month_name' or 'year' columns.")
        return {}

    df_periods['key'] = df_periods['month_name'].astype(str) + "_" + df_periods['year'].astype(str)
    df_periods.drop_duplicates(subset=['key'], keep='last', inplace=True)
    
    all_periods = df_periods.set_index('key').to_dict('index')
    active_periods = {k: v for k, v in all_periods.items() if v.get("active")}
    return active_periods

# --- Main Dashboard Function ---

def audit_group_dashboard(dbx):
    """Main function to render the Audit Group dashboard."""
    st.markdown(f"<div class='sub-header'>Audit Group {st.session_state.audit_group_no} Dashboard</div>", unsafe_allow_html=True)

    YOUR_GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", "")
    if not YOUR_GEMINI_API_KEY:
        st.error("Gemini API Key is not configured. Please contact the administrator.")
        st.stop()

    active_periods = get_active_mcm_periods(dbx)

    default_ag_states = {
        'ag_current_mcm_key': None, 'ag_current_uploaded_file_obj': None,
        'ag_current_uploaded_file_name': None, 'ag_editor_data': pd.DataFrame(columns=DISPLAY_COLUMN_ORDER_EDITOR),
        'ag_pdf_dropbox_path': None, 'ag_validation_errors': [],
        'ag_uploader_key_suffix': 0, 'ag_deletable_map': {}
    }
    for key, value in default_ag_states.items():
        if key not in st.session_state:
            st.session_state[key] = value

    with st.sidebar:
        try:
            st.image("logo.png", width=80)
        except Exception:
            st.sidebar.markdown("*(Logo)*")
        st.markdown(f"**User:** {st.session_state.username}<br>**Group No:** {st.session_state.audit_group_no}", unsafe_allow_html=True)
        if st.button("Logout", key="ag_logout", use_container_width=True):
            keys_to_clear = list(default_ag_states.keys()) + ['logged_in', 'username', 'role', 'audit_group_no']
            for k in keys_to_clear:
                if k in st.session_state: del st.session_state[k]
            st.rerun()
        st.markdown("---")
        if st.button("🚀 Smart Audit Tracker", key="launch_sat_ag"):
            st.session_state.app_mode = "smart_audit_tracker"
            st.rerun()
        st.markdown("---")

    selected_tab = option_menu(
        menu_title="e-MCM Menu",
        options=["Upload DAR for MCM", "View My Uploaded DARs", "Delete My DAR Entries"],
        icons=["cloud-upload-fill", "eye-fill", "trash2-fill"], menu_icon="person-workspace",
        default_index=0, orientation="horizontal",
        styles={
            "container": {"padding": "5px !important", "background-color": "#e9ecef"},
            "icon": {"color": "#28a745", "font-size": "20px"},
            "nav-link": {"font-size": "16px", "text-align": "center", "margin": "0px", "--hover-color": "#d4edda"},
            "nav-link-selected": {"background-color": "#28a745", "color": "white"},
        })

    st.markdown("<div class='card'>", unsafe_allow_html=True)

    if selected_tab == "Upload DAR for MCM":
        upload_dar_tab(dbx, active_periods, YOUR_GEMINI_API_KEY)
    elif selected_tab == "View My Uploaded DARs":
        view_uploads_tab(dbx)
    elif selected_tab == "Delete My DAR Entries":
        delete_entries_tab(dbx)

    st.markdown("</div>", unsafe_allow_html=True)


def upload_dar_tab(dbx, active_periods, api_key):
    # This function remains unchanged from the previous correct version
    st.markdown("<h3>Upload DAR PDF for MCM Period</h3>", unsafe_allow_html=True)
    if not active_periods:
        st.warning("No active MCM periods available. Please contact the Planning Officer.")
        return
    period_options_disp_map = {k: f"{v.get('month_name')} {v.get('year')}" for k, v in sorted(active_periods.items(), key=lambda x: x[0], reverse=True)}
    period_select_map_rev = {v: k for k, v in period_options_disp_map.items()}
    selected_period_str = st.selectbox(
        "Select Active MCM Period", options=list(period_select_map_rev.keys()),
        key=f"ag_mcm_sel_uploader_{st.session_state.ag_uploader_key_suffix}"
    )
    if not selected_period_str: return
    new_mcm_key = period_select_map_rev[selected_period_str]
    if st.session_state.ag_current_mcm_key != new_mcm_key:
        st.session_state.ag_current_mcm_key = new_mcm_key
        st.session_state.ag_current_uploaded_file_obj = None; st.session_state.ag_current_uploaded_file_name = None
        st.session_state.ag_editor_data = pd.DataFrame(columns=DISPLAY_COLUMN_ORDER_EDITOR)
        st.session_state.ag_pdf_dropbox_path = None; st.session_state.ag_validation_errors = []
        st.session_state.ag_uploader_key_suffix += 1; st.rerun()
    mcm_info_current = active_periods[st.session_state.ag_current_mcm_key]
    st.info(f"Uploading for: {mcm_info_current['month_name']} {mcm_info_current['year']}")
    uploaded_file = st.file_uploader(
        "Choose DAR PDF", type="pdf",
        key=f"ag_uploader_main_{st.session_state.ag_current_mcm_key}_{st.session_state.ag_uploader_key_suffix}"
    )
    if uploaded_file and st.session_state.ag_current_uploaded_file_name != uploaded_file.name:
        st.session_state.ag_current_uploaded_file_obj = uploaded_file
        st.session_state.ag_current_uploaded_file_name = uploaded_file.name
        st.session_state.ag_editor_data = pd.DataFrame(columns=DISPLAY_COLUMN_ORDER_EDITOR)
        st.session_state.ag_pdf_dropbox_path = None; st.session_state.ag_validation_errors = []
        st.rerun()
    if st.session_state.ag_current_uploaded_file_obj and st.button("Extract Data", use_container_width=True):
        status_area = st.empty()
        pdf_bytes = st.session_state.ag_current_uploaded_file_obj.getvalue()
        status_area.info("▶️ Step 1/4: Uploading PDF to Dropbox...")
        dar_filename_on_dropbox = f"AG{st.session_state.audit_group_no}_{st.session_state.ag_current_uploaded_file_name}"
        pdf_dropbox_path = f"{DAR_PDFS_PATH}/{dar_filename_on_dropbox}"
        if not upload_file(dbx, pdf_bytes, pdf_dropbox_path):
            status_area.error("❌ Step 1/4 Failed: Could not upload PDF to Dropbox. Please try again.")
            st.stop()
        st.session_state.ag_pdf_dropbox_path = pdf_dropbox_path
        status_area.info("✅ Step 1/4: PDF uploaded successfully. \n\n▶️ Step 2/4: Pre-processing PDF content...")
        preprocessed_text = preprocess_pdf_text(BytesIO(pdf_bytes))
        if preprocessed_text.startswith("Error"):
            status_area.error(f"❌ Step 2/4 Failed: {preprocessed_text}")
            st.stop()
        status_area.info("✅ Step 2/4: PDF pre-processed. \n\n▶️ Step 3/4: Extracting data with AI (this may take a moment)...")
        parsed_data = get_structured_data_from_llm(preprocessed_text)
        if parsed_data.parsing_errors:
            st.warning(f"AI Parsing Issues: {parsed_data.parsing_errors}")
        status_area.info("✅ Step 3/4: AI data extraction complete. \n\n▶️ Step 4/4: Formatting data for review...")
        header_dict = parsed_data.header.model_dump() if parsed_data.header else {}
        base_info = {"audit_group_number": st.session_state.audit_group_no, "audit_circle_number": calculate_audit_circle(st.session_state.audit_group_no),
                     "gstin": header_dict.get("gstin"), "trade_name": header_dict.get("trade_name"), "category": header_dict.get("category"),
                     "total_amount_detected_overall_rs": header_dict.get("total_amount_detected_overall_rs"),
                     "total_amount_recovered_overall_rs": header_dict.get("total_amount_recovered_overall_rs")}
        temp_list_for_df = []
        if parsed_data.audit_paras:
            for para_obj in parsed_data.audit_paras:
                temp_list_for_df.append({**base_info, **para_obj.model_dump()})
        elif base_info.get("trade_name"):
            temp_list_for_df.append({**base_info, "audit_para_heading": "N/A - Header Info Only"})
        else:
            temp_list_for_df.append({**base_info, "audit_para_heading": "Manual Entry Required"})
            st.error("AI failed to extract key information. A manual entry template is provided.")
        df_extracted = pd.DataFrame(temp_list_for_df)
        for col in DISPLAY_COLUMN_ORDER_EDITOR:
            if col not in df_extracted.columns: df_extracted[col] = None
        st.session_state.ag_editor_data = df_extracted[DISPLAY_COLUMN_ORDER_EDITOR]
        status_area.success("✅ Step 4/4: Formatting complete. Data is ready for review below.")
        time.sleep(2)
        st.rerun()
    if not st.session_state.ag_editor_data.empty:
        st.markdown("<h4>Review and Edit Extracted Data:</h4>", unsafe_allow_html=True)
        col_conf = { "audit_group_number": st.column_config.NumberColumn("Group No.", disabled=True), "audit_circle_number": st.column_config.NumberColumn("Circle No.", disabled=True),
                     "gstin": st.column_config.TextColumn("GSTIN", width="medium"), "trade_name": st.column_config.TextColumn("Trade Name", width="large"),
                     "category": st.column_config.SelectboxColumn("Category", options=[None] + VALID_CATEGORIES, width="small"),
                     "total_amount_detected_overall_rs": st.column_config.NumberColumn("Total Detect (₹)", format="%.2f"),
                     "total_amount_recovered_overall_rs": st.column_config.NumberColumn("Total Recover (₹)", format="%.2f"),
                     "audit_para_number": st.column_config.NumberColumn("Para No.", format="%d", width="small"),
                     "audit_para_heading": st.column_config.TextColumn("Para Heading", width="xlarge"),
                     "revenue_involved_lakhs_rs": st.column_config.NumberColumn("Rev. Involved (₹)", format="%.2f"),
                     "revenue_recovered_lakhs_rs": st.column_config.NumberColumn("Rev. Recovered (₹)", format="%.2f"),
                     "status_of_para": st.column_config.SelectboxColumn("Para Status", options=[None] + VALID_PARA_STATUSES, width="medium") }
        editor_key = f"data_editor_{st.session_state.ag_current_mcm_key}_{st.session_state.ag_current_uploaded_file_name or 'no_file'}"
        edited_df = st.data_editor(st.session_state.ag_editor_data, column_config=col_conf, num_rows="dynamic", key=editor_key,
                                   use_container_width=True, hide_index=True, height=min(len(st.session_state.ag_editor_data) * 45 + 70, 450))
        if st.button("Submit to MCM Sheet", use_container_width=True):
            submit_status_area = st.empty()
            submit_status_area.info("▶️ Step 1/4: Cleaning and validating data...")
            df_to_submit = pd.DataFrame(edited_df).dropna(how='all').reset_index(drop=True)
            if df_to_submit.empty:
                submit_status_area.error("❌ Submission Failed: No data found in the editor.")
                return
            validation_errors = validate_data_for_sheet(df_to_submit)
            if validation_errors:
                submit_status_area.empty()
                st.error("Validation Failed! Please correct the following errors:")
                for err in validation_errors: st.warning(f"- {err}")
                return
            submit_status_area.info("✅ Step 1/4: Validation successful. \n\n▶️ Step 2/4: Reading master data file from Dropbox...")
            master_df = read_from_spreadsheet(dbx, MCM_DATA_PATH)
            submit_status_area.info("✅ Step 2/4: Master file read. \n\n▶️ Step 3/4: Preparing final data for submission...")
            df_to_submit['mcm_period'] = selected_period_str
            df_to_submit['dar_pdf_path'] = st.session_state.ag_pdf_dropbox_path
            df_to_submit['record_created_date'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            for col in SHEET_DATA_COLUMNS_ORDER:
                if col not in master_df.columns: master_df[col] = pd.NA
                if col not in df_to_submit.columns: df_to_submit[col] = pd.NA
            submit_status_area.info("✅ Step 3/4: Data prepared. \n\n▶️ Step 4/4: Saving updated data back to Dropbox...")
            final_df = pd.concat([master_df, df_to_submit[SHEET_DATA_COLUMNS_ORDER]], ignore_index=True)
            if update_spreadsheet_from_df(dbx, final_df, MCM_DATA_PATH):
                submit_status_area.success("✅ Submission complete! Data saved successfully.")
                st.balloons()
                time.sleep(2)
                st.session_state.ag_current_uploaded_file_obj = None
                st.session_state.ag_current_uploaded_file_name = None
                st.session_state.ag_editor_data = pd.DataFrame(columns=DISPLAY_COLUMN_ORDER_EDITOR)
                st.session_state.ag_pdf_dropbox_path = None
                st.session_state.ag_validation_errors = []
                st.session_state.ag_uploader_key_suffix += 1
                st.rerun()
            else:
                submit_status_area.error("❌ Step 4/4 Failed: Could not save the updated data to Dropbox.")

def view_uploads_tab(dbx):
    """Renders the 'View My Uploaded DARs' tab with a robust, styled table."""
    st.markdown("<h3>My Uploaded DARs</h3>", unsafe_allow_html=True)
    
    all_periods = read_from_spreadsheet(dbx, MCM_PERIODS_INFO_PATH)
    if all_periods.empty:
        st.warning("Could not load period information.")
        return
        
    period_options_map = {f"{row['month_name']} {row['year']}": f"{row['month_name']} {row['year']}" for _, row in all_periods.iterrows()}
    selected_period = st.selectbox("Select MCM Period to View", options=list(period_options_map.keys()))

    if not selected_period: return

    with st.spinner("Loading your uploaded reports..."):
        df_all_data = read_from_spreadsheet(dbx, MCM_DATA_PATH)
        if df_all_data.empty:
            st.info("No reports have been submitted for any period yet.")
            return

        df_all_data['audit_group_number'] = pd.to_numeric(df_all_data['audit_group_number'], errors='coerce')
        my_uploads = df_all_data[(df_all_data['audit_group_number'] == st.session_state.audit_group_no) & (df_all_data['mcm_period'] == selected_period)].copy()

        if my_uploads.empty:
            st.info(f"You have not submitted any reports for {selected_period}.")
            return
        
        st.markdown(f"<h4>Your Uploads for {selected_period}:</h4>", unsafe_allow_html=True)
        
        @st.cache_data(ttl=600)
        def get_link(_dbx, path):
            return get_shareable_link(_dbx, path)

        if 'dar_pdf_path' in my_uploads.columns:
            my_uploads['View PDF'] = my_uploads['dar_pdf_path'].apply(
                lambda path: f'<a href="{get_link(dbx, path)}" target="_blank" style="text-decoration:none; color:#1E88E5; font-weight:bold;">📄 View PDF</a>' if pd.notna(path) else "No Link"
            )

        display_cols = ["gstin", "trade_name", "audit_para_number", "audit_para_heading", "status_of_para",
                        "revenue_involved_lakhs_rs", "revenue_recovered_lakhs_rs", "record_created_date", "View PDF"]
        
        cols_to_show = [col for col in display_cols if col in my_uploads.columns]
        
        # --- NEW: Use Pandas Styler for robust HTML and formatting ---
        df_to_display = my_uploads[cols_to_show].copy()

        format_dict = {
            'revenue_involved_lakhs_rs': '₹ {:,.2f}',
            'revenue_recovered_lakhs_rs': '₹ {:,.2f}',
            'audit_para_number': '{:.0f}'
        }
        
        styler = df_to_display.style.format(formatter=format_dict, na_rep="N/A")
        styler = styler.hide(axis="index")
        styler = styler.set_table_attributes('class="view-table"')
        
        numeric_cols = ['revenue_involved_lakhs_rs', 'revenue_recovered_lakhs_rs']
        styler = styler.set_properties(subset=numeric_cols, **{'text-align': 'right'})
        
        text_cols = ['gstin', 'trade_name', 'audit_para_heading', 'status_of_para']
        styler = styler.set_properties(subset=text_cols, **{'text-align': 'left'})

        table_html = styler.to_html(escape=False)
        
        # --- Inject more forceful CSS to ensure styles are applied ---
        table_css = """
        <style>
            .view-table {
                width: 100%;
                border-collapse: collapse;
                margin: 25px 0;
                font-size: 0.9em;
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                box-shadow: 0 4px 15px rgba(0, 0, 0, 0.05);
                border-radius: 10px;
                overflow: hidden;
            }
            .view-table thead tr {
                background-color: #16a085 !important;
                color: #ffffff !important;
                text-align: left;
                font-weight: bold;
            }
            .view-table th, .view-table td {
                padding: 12px 15px !important;
                text-align: left;
            }
            .view-table tbody tr {
                border-bottom: 1px solid #dddddd;
            }
            .view-table tbody tr:nth-of-type(even) {
                background-color: #f3f3f3 !important;
            }
            .view-table tbody tr:nth-of-type(odd) {
                background-color: #ffffff !important;
            }
            .view-table tbody tr:last-of-type {
                border-bottom: 2px solid #16a085 !important;
            }
            .view-table tbody tr:hover {
                background-color: #d4edda !important;
                cursor: pointer;
            }
        </style>
        """
        st.markdown(table_css + table_html, unsafe_allow_html=True)


def delete_entries_tab(dbx):
    """Renders the 'Delete My DAR Entries' tab with fixed logic."""
    # This function remains unchanged from the previous correct version
    st.markdown("<h3>Delete My Uploaded DAR Entries</h3>", unsafe_allow_html=True)
    st.error("⚠️ **Warning:** This action is permanent and cannot be undone.")
    all_periods = read_from_spreadsheet(dbx, MCM_PERIODS_INFO_PATH)
    if all_periods.empty:
        st.warning("Could not load period information.")
        return
    period_options_map = {f"{row['month_name']} {row['year']}": f"{row['month_name']} {row['year']}" for _, row in all_periods.iterrows()}
    selected_period = st.selectbox("Select MCM Period to Manage", options=list(period_options_map.keys()))
    if not selected_period: return
    master_df = read_from_spreadsheet(dbx, MCM_DATA_PATH)
    if master_df.empty:
        st.info("Master data file is empty. Nothing to delete.")
        return
    master_df['original_index'] = master_df.index
    master_df['audit_group_number'] = pd.to_numeric(master_df['audit_group_number'], errors='coerce')
    my_entries = master_df[(master_df['audit_group_number'] == st.session_state.audit_group_no) & (master_df['mcm_period'] == selected_period)].copy()
    if my_entries.empty:
        st.info(f"You have no entries in {selected_period} to delete.")
        return
    my_entries['delete_label'] = (
        "TN: " + my_entries['trade_name'].astype(str).str.slice(0, 25) + "... | " +
        "Para: " + my_entries['audit_para_number'].astype(str) + " | " +
        "Date: " + my_entries['record_created_date'].astype(str)
    )
    deletable_map = my_entries.set_index('delete_label')['original_index'].to_dict()
    options = ["--Select an entry--"] + list(deletable_map.keys())
    selected_label = st.selectbox("Select Entry to Delete:", options=options)
    if selected_label != "--Select an entry--":
        index_to_delete = deletable_map.get(selected_label)
        if index_to_delete is not None:
            details = master_df.loc[index_to_delete]
            st.warning(f"Confirm Deletion: **{details['trade_name']}**, Para: **{details['audit_para_number']}**")
            with st.form(key=f"delete_form_{index_to_delete}"):
                password = st.text_input("Enter your password to confirm:", type="password")
                if st.form_submit_button("Yes, Delete This Entry", type="primary"):
                    if password == USER_CREDENTIALS.get(st.session_state.username):
                        with st.spinner("Deleting entry..."):
                            df_after_delete = master_df.drop(index=index_to_delete).drop(columns=['original_index'])
                            if update_spreadsheet_from_df(dbx, df_after_delete, MCM_DATA_PATH):
                                st.success("Entry deleted successfully!")
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.error("Failed to update the data file on Dropbox.")
                    else:
                        st.error("Incorrect password.")
# import streamlit as st
# import pandas as pd
# import datetime
# import math
# from io import BytesIO
# import time
# from streamlit_option_menu import option_menu
# import html

# # --- Custom Module Imports for Dropbox Version ---
# from dropbox_utils import (
#     read_from_spreadsheet,
#     update_spreadsheet_from_df,
#     upload_file,
#     get_shareable_link 
# )
# from dar_processor import preprocess_pdf_text, get_structured_data_with_gemini, get_structured_data_from_llm
# from validation_utils import validate_data_for_sheet, VALID_CATEGORIES, VALID_PARA_STATUSES
# from config import (
#     USER_CREDENTIALS,
#     MCM_PERIODS_INFO_PATH,
#     MCM_DATA_PATH,
#     DAR_PDFS_PATH
# )
# from models import ParsedDARReport

# # --- Constants and Configuration ---
# SHEET_DATA_COLUMNS_ORDER = [
#     "mcm_period", "audit_group_number", "audit_circle_number", "gstin", "trade_name",
#     "category", "total_amount_detected_overall_rs", "total_amount_recovered_overall_rs",
#     "audit_para_number", "audit_para_heading", "revenue_involved_lakhs_rs",
#     "revenue_recovered_lakhs_rs", "status_of_para", "dar_pdf_path", "record_created_date"
# ]

# DISPLAY_COLUMN_ORDER_EDITOR = [
#     "audit_group_number", "audit_circle_number", "gstin", "trade_name", "category",
#     "total_amount_detected_overall_rs", "total_amount_recovered_overall_rs",
#     "audit_para_number", "audit_para_heading", "revenue_involved_lakhs_rs",
#     "revenue_recovered_lakhs_rs", "status_of_para"
# ]

# # --- Helper Functions ---

# def calculate_audit_circle(audit_group_number_val):
#     """Calculates the audit circle based on the audit group number."""
#     try:
#         agn = int(audit_group_number_val)
#         if 1 <= agn <= 30:
#             return math.ceil(agn / 3.0)
#         return None
#     except (ValueError, TypeError, AttributeError):
#         return None

# @st.cache_data(ttl=120)
# def get_active_mcm_periods(_dbx):
#     """
#     Reads MCM periods from Dropbox, converts to a dictionary,
#     and returns only the active ones. Caches the result.
#     """
#     df_periods = read_from_spreadsheet(_dbx, MCM_PERIODS_INFO_PATH)
#     if df_periods.empty:
#         return {}
    
#     if 'month_name' not in df_periods.columns or 'year' not in df_periods.columns:
#         st.error("The 'mcm_periods_info.xlsx' file is missing 'month_name' or 'year' columns.")
#         return {}

#     df_periods['key'] = df_periods['month_name'].astype(str) + "_" + df_periods['year'].astype(str)
#     df_periods.drop_duplicates(subset=['key'], keep='last', inplace=True)
    
#     all_periods = df_periods.set_index('key').to_dict('index')
#     active_periods = {k: v for k, v in all_periods.items() if v.get("active")}
#     return active_periods

# # --- Main Dashboard Function ---

# def audit_group_dashboard(dbx):
#     """Main function to render the Audit Group dashboard."""
#     st.markdown(f"<div class='sub-header'>Audit Group {st.session_state.audit_group_no} Dashboard</div>", unsafe_allow_html=True)

#     YOUR_GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", "")
#     if not YOUR_GEMINI_API_KEY:
#         st.error("Gemini API Key is not configured. Please contact the administrator.")
#         st.stop()

#     active_periods = get_active_mcm_periods(dbx)

#     default_ag_states = {
#         'ag_current_mcm_key': None, 'ag_current_uploaded_file_obj': None,
#         'ag_current_uploaded_file_name': None, 'ag_editor_data': pd.DataFrame(columns=DISPLAY_COLUMN_ORDER_EDITOR),
#         'ag_pdf_dropbox_path': None, 'ag_validation_errors': [],
#         'ag_uploader_key_suffix': 0, 'ag_deletable_map': {}
#     }
#     for key, value in default_ag_states.items():
#         if key not in st.session_state:
#             st.session_state[key] = value

#     with st.sidebar:
#         try:
#             st.image("logo.png", width=80)
#         except Exception:
#             st.sidebar.markdown("*(Logo)*")
#         st.markdown(f"**User:** {st.session_state.username}<br>**Group No:** {st.session_state.audit_group_no}", unsafe_allow_html=True)
#         if st.button("Logout", key="ag_logout", use_container_width=True):
#             keys_to_clear = list(default_ag_states.keys()) + ['logged_in', 'username', 'role', 'audit_group_no']
#             for k in keys_to_clear:
#                 if k in st.session_state: del st.session_state[k]
#             st.rerun()
#         st.markdown("---")
#         if st.button("🚀 Smart Audit Tracker", key="launch_sat_ag"):
#             st.session_state.app_mode = "smart_audit_tracker"
#             st.rerun()
#         st.markdown("---")

#     selected_tab = option_menu(
#         menu_title="e-MCM Menu",
#         options=["Upload DAR for MCM", "View My Uploaded DARs", "Delete My DAR Entries"],
#         icons=["cloud-upload-fill", "eye-fill", "trash2-fill"], menu_icon="person-workspace",
#         default_index=0, orientation="horizontal",
#         styles={
#             "container": {"padding": "5px !important", "background-color": "#e9ecef"},
#             "icon": {"color": "#28a745", "font-size": "20px"},
#             "nav-link": {"font-size": "16px", "text-align": "center", "margin": "0px", "--hover-color": "#d4edda"},
#             "nav-link-selected": {"background-color": "#28a745", "color": "white"},
#         })

#     st.markdown("<div class='card'>", unsafe_allow_html=True)

#     if selected_tab == "Upload DAR for MCM":
#         upload_dar_tab(dbx, active_periods, YOUR_GEMINI_API_KEY)
#     elif selected_tab == "View My Uploaded DARs":
#         view_uploads_tab(dbx, active_periods)
#     elif selected_tab == "Delete My DAR Entries":
#         delete_entries_tab(dbx, active_periods)

#     st.markdown("</div>", unsafe_allow_html=True)


# def upload_dar_tab(dbx, active_periods, api_key):
#     """Renders the 'Upload DAR' tab with step-by-step status updates."""
#     st.markdown("<h3>Upload DAR PDF for MCM Period</h3>", unsafe_allow_html=True)
#     if not active_periods:
#         st.warning("No active MCM periods available. Please contact the Planning Officer.")
#         return

#     period_options_disp_map = {k: f"{v.get('month_name')} {v.get('year')}" for k, v in sorted(active_periods.items(), key=lambda x: x[0], reverse=True)}
#     period_select_map_rev = {v: k for k, v in period_options_disp_map.items()}

#     selected_period_str = st.selectbox(
#         "Select Active MCM Period", options=list(period_select_map_rev.keys()),
#         key=f"ag_mcm_sel_uploader_{st.session_state.ag_uploader_key_suffix}"
#     )

#     if not selected_period_str: return

#     new_mcm_key = period_select_map_rev[selected_period_str]
#     if st.session_state.ag_current_mcm_key != new_mcm_key:
#         st.session_state.ag_current_mcm_key = new_mcm_key
#         st.session_state.ag_current_uploaded_file_obj = None; st.session_state.ag_current_uploaded_file_name = None
#         st.session_state.ag_editor_data = pd.DataFrame(columns=DISPLAY_COLUMN_ORDER_EDITOR)
#         st.session_state.ag_pdf_dropbox_path = None; st.session_state.ag_validation_errors = []
#         st.session_state.ag_uploader_key_suffix += 1; st.rerun()

#     mcm_info_current = active_periods[st.session_state.ag_current_mcm_key]
#     st.info(f"Uploading for: {mcm_info_current['month_name']} {mcm_info_current['year']}")

#     uploaded_file = st.file_uploader(
#         "Choose DAR PDF", type="pdf",
#         key=f"ag_uploader_main_{st.session_state.ag_current_mcm_key}_{st.session_state.ag_uploader_key_suffix}"
#     )

#     if uploaded_file and st.session_state.ag_current_uploaded_file_name != uploaded_file.name:
#         st.session_state.ag_current_uploaded_file_obj = uploaded_file
#         st.session_state.ag_current_uploaded_file_name = uploaded_file.name
#         st.session_state.ag_editor_data = pd.DataFrame(columns=DISPLAY_COLUMN_ORDER_EDITOR)
#         st.session_state.ag_pdf_dropbox_path = None; st.session_state.ag_validation_errors = []
#         st.rerun()

#     if st.session_state.ag_current_uploaded_file_obj and st.button("Extract Data", use_container_width=True):
#         status_area = st.empty()
        
#         pdf_bytes = st.session_state.ag_current_uploaded_file_obj.getvalue()
        
#         status_area.info("▶️ Step 1/4: Uploading PDF to Dropbox...")
#         dar_filename_on_dropbox = f"AG{st.session_state.audit_group_no}_{st.session_state.ag_current_uploaded_file_name}"
#         pdf_dropbox_path = f"{DAR_PDFS_PATH}/{dar_filename_on_dropbox}"
#         if not upload_file(dbx, pdf_bytes, pdf_dropbox_path):
#             status_area.error("❌ Step 1/4 Failed: Could not upload PDF to Dropbox. Please try again.")
#             st.stop()
#         st.session_state.ag_pdf_dropbox_path = pdf_dropbox_path
#         status_area.info("✅ Step 1/4: PDF uploaded successfully. \n\n▶️ Step 2/4: Pre-processing PDF content...")
        
#         preprocessed_text = preprocess_pdf_text(BytesIO(pdf_bytes))
#         if preprocessed_text.startswith("Error"):
#             status_area.error(f"❌ Step 2/4 Failed: {preprocessed_text}")
#             st.stop()
        
#         status_area.info("✅ Step 2/4: PDF pre-processed. \n\n▶️ Step 3/4: Extracting data with AI (this may take a moment)...")
        
#         parsed_data = get_structured_data_from_llm(preprocessed_text)
#         if parsed_data.parsing_errors:
#             st.warning(f"AI Parsing Issues: {parsed_data.parsing_errors}")
#         status_area.info("✅ Step 3/4: AI data extraction complete. \n\n▶️ Step 4/4: Formatting data for review...")

#         header_dict = parsed_data.header.model_dump() if parsed_data.header else {}
#         base_info = {"audit_group_number": st.session_state.audit_group_no, "audit_circle_number": calculate_audit_circle(st.session_state.audit_group_no),
#                      "gstin": header_dict.get("gstin"), "trade_name": header_dict.get("trade_name"), "category": header_dict.get("category"),
#                      "total_amount_detected_overall_rs": header_dict.get("total_amount_detected_overall_rs"),
#                      "total_amount_recovered_overall_rs": header_dict.get("total_amount_recovered_overall_rs")}
#         temp_list_for_df = []
#         if parsed_data.audit_paras:
#             for para_obj in parsed_data.audit_paras:
#                 temp_list_for_df.append({**base_info, **para_obj.model_dump()})
#         elif base_info.get("trade_name"):
#             temp_list_for_df.append({**base_info, "audit_para_heading": "N/A - Header Info Only"})
#         else:
#             temp_list_for_df.append({**base_info, "audit_para_heading": "Manual Entry Required"})
#             st.error("AI failed to extract key information. A manual entry template is provided.")
        
#         df_extracted = pd.DataFrame(temp_list_for_df)
#         for col in DISPLAY_COLUMN_ORDER_EDITOR:
#             if col not in df_extracted.columns: df_extracted[col] = None
#         st.session_state.ag_editor_data = df_extracted[DISPLAY_COLUMN_ORDER_EDITOR]
        
#         status_area.success("✅ Step 4/4: Formatting complete. Data is ready for review below.")
#         time.sleep(2)
#         st.rerun()

#     if not st.session_state.ag_editor_data.empty:
#         st.markdown("<h4>Review and Edit Extracted Data:</h4>", unsafe_allow_html=True)
#         col_conf = { "audit_group_number": st.column_config.NumberColumn("Group No.", disabled=True), "audit_circle_number": st.column_config.NumberColumn("Circle No.", disabled=True),
#                      "gstin": st.column_config.TextColumn("GSTIN", width="medium"), "trade_name": st.column_config.TextColumn("Trade Name", width="large"),
#                      "category": st.column_config.SelectboxColumn("Category", options=[None] + VALID_CATEGORIES, width="small"),
#                      "total_amount_detected_overall_rs": st.column_config.NumberColumn("Total Detect (₹)", format="%.2f"),
#                      "total_amount_recovered_overall_rs": st.column_config.NumberColumn("Total Recover (₹)", format="%.2f"),
#                      "audit_para_number": st.column_config.NumberColumn("Para No.", format="%d", width="small"),
#                      "audit_para_heading": st.column_config.TextColumn("Para Heading", width="xlarge"),
#                      "revenue_involved_lakhs_rs": st.column_config.NumberColumn("Rev. Involved (₹)", format="%.2f"),
#                      "revenue_recovered_lakhs_rs": st.column_config.NumberColumn("Rev. Recovered (₹)", format="%.2f"),
#                      "status_of_para": st.column_config.SelectboxColumn("Para Status", options=[None] + VALID_PARA_STATUSES, width="medium") }
        
#         editor_key = f"data_editor_{st.session_state.ag_current_mcm_key}_{st.session_state.ag_current_uploaded_file_name or 'no_file'}"
#         edited_df = st.data_editor(st.session_state.ag_editor_data, column_config=col_conf, num_rows="dynamic", key=editor_key,
#                                    use_container_width=True, hide_index=True, height=min(len(st.session_state.ag_editor_data) * 45 + 70, 450))

#         if st.button("Submit to MCM Sheet", use_container_width=True):
#             submit_status_area = st.empty()
#             submit_status_area.info("▶️ Step 1/4: Cleaning and validating data...")
            
#             df_to_submit = pd.DataFrame(edited_df).dropna(how='all').reset_index(drop=True)
#             if df_to_submit.empty:
#                 submit_status_area.error("❌ Submission Failed: No data found in the editor.")
#                 return
            
#             validation_errors = validate_data_for_sheet(df_to_submit)
#             if validation_errors:
#                 submit_status_area.empty()
#                 st.error("Validation Failed! Please correct the following errors:")
#                 for err in validation_errors: st.warning(f"- {err}")
#                 return
            
#             submit_status_area.info("✅ Step 1/4: Validation successful. \n\n▶️ Step 2/4: Reading master data file from Dropbox...")
#             master_df = read_from_spreadsheet(dbx, MCM_DATA_PATH)
            
#             submit_status_area.info("✅ Step 2/4: Master file read. \n\n▶️ Step 3/4: Preparing final data for submission...")
#             df_to_submit['mcm_period'] = selected_period_str
#             df_to_submit['dar_pdf_path'] = st.session_state.ag_pdf_dropbox_path
#             df_to_submit['record_created_date'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

#             for col in SHEET_DATA_COLUMNS_ORDER:
#                 if col not in master_df.columns: master_df[col] = pd.NA
#                 if col not in df_to_submit.columns: df_to_submit[col] = pd.NA
            
#             submit_status_area.info("✅ Step 3/4: Data prepared. \n\n▶️ Step 4/4: Saving updated data back to Dropbox...")
#             final_df = pd.concat([master_df, df_to_submit[SHEET_DATA_COLUMNS_ORDER]], ignore_index=True)
            
#             if update_spreadsheet_from_df(dbx, final_df, MCM_DATA_PATH):
#                 submit_status_area.success("✅ Submission complete! Data saved successfully.")
#                 st.balloons()
#                 time.sleep(2)
#                 st.session_state.ag_current_uploaded_file_obj = None
#                 st.session_state.ag_current_uploaded_file_name = None
#                 st.session_state.ag_editor_data = pd.DataFrame(columns=DISPLAY_COLUMN_ORDER_EDITOR)
#                 st.session_state.ag_pdf_dropbox_path = None
#                 st.session_state.ag_validation_errors = []
#                 st.session_state.ag_uploader_key_suffix += 1
#                 st.rerun()
#             else:
#                 submit_status_area.error("❌ Step 4/4 Failed: Could not save the updated data to Dropbox.")

# def view_uploads_tab(dbx, active_periods):
#     """Renders the 'View My Uploaded DARs' tab with a colorful, modern table."""
#     st.markdown("<h3>My Uploaded DARs</h3>", unsafe_allow_html=True)
#     if not active_periods:
#         st.info("No active MCM periods exist to view reports from.")
#         return

#     all_periods = read_from_spreadsheet(dbx, MCM_PERIODS_INFO_PATH)
#     if all_periods.empty:
#         st.warning("Could not load period information.")
#         return
        
#     period_options_map = {f"{row['month_name']} {row['year']}": f"{row['month_name']} {row['year']}" for _, row in all_periods.iterrows()}
#     selected_period = st.selectbox("Select MCM Period to View", options=list(period_options_map.keys()))

#     if not selected_period: return

#     with st.spinner("Loading your uploaded reports..."):
#         df_all_data = read_from_spreadsheet(dbx, MCM_DATA_PATH)
#         if df_all_data.empty:
#             st.info("No reports have been submitted for any period yet.")
#             return

#         df_all_data['audit_group_number'] = pd.to_numeric(df_all_data['audit_group_number'], errors='coerce')
#         my_uploads = df_all_data[(df_all_data['audit_group_number'] == st.session_state.audit_group_no) & (df_all_data['mcm_period'] == selected_period)].copy()

#         if my_uploads.empty:
#             st.info(f"You have not submitted any reports for {selected_period}.")
#             return
        
#         st.markdown(f"<h4>Your Uploads for {selected_period}:</h4>", unsafe_allow_html=True)
        
#         @st.cache_data(ttl=600)
#         def get_link(_dbx, path):
#             return get_shareable_link(_dbx, path)

#         if 'dar_pdf_path' in my_uploads.columns:
#             my_uploads['View PDF'] = my_uploads['dar_pdf_path'].apply(
#                 lambda path: f'<a href="{get_link(dbx, path)}" target="_blank" style="text-decoration:none; color:#1E88E5; font-weight:bold;">📄 View PDF</a>' if pd.notna(path) else "No Link"
#             )

#         display_cols = ["gstin", "trade_name", "audit_para_number", "audit_para_heading", "status_of_para",
#                         "revenue_involved_lakhs_rs", "revenue_recovered_lakhs_rs", "record_created_date", "View PDF"]
        
#         cols_to_show = [col for col in display_cols if col in my_uploads.columns]
        
#         # --- NEW: Inject CSS for a colorful table ---
#         table_css = """
#         <style>
#             .view-table {
#                 width: 100%;
#                 border-collapse: collapse;
#                 margin: 25px 0;
#                 font-size: 0.9em;
#                 font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
#                 box-shadow: 0 4px 15px rgba(0, 0, 0, 0.05);
#                 border-radius: 10px;
#                 overflow: hidden;
#             }
#             .view-table thead tr {
#                 background-color: #007bff;
#                 color: #ffffff;
#                 text-align: left;
#                 font-weight: bold;
#             }
#             .view-table th, .view-table td {
#                 padding: 12px 15px;
#                 text-align: left;
#             }
#             .view-table tbody tr {
#                 border-bottom: 1px solid #dddddd;
#             }
#             .view-table tbody tr:nth-of-type(even) {
#                 background-color: #f3f3f3;
#             }
#             .view-table tbody tr:last-of-type {
#                 border-bottom: 2px solid #007bff;
#             }
#             .view-table tbody tr:hover {
#                 background-color: #e0eaff;
#                 cursor: pointer;
#             }
#         </style>
#         """
#         table_html = my_uploads[cols_to_show].to_html(escape=False, index=False, classes='view-table', border=0)
#         st.markdown(table_css + table_html, unsafe_allow_html=True)


# def delete_entries_tab(dbx, active_periods):
#     """Renders the 'Delete My DAR Entries' tab with fixed logic."""
#     st.markdown("<h3>Delete My Uploaded DAR Entries</h3>", unsafe_allow_html=True)
#     st.error("⚠️ **Warning:** This action is permanent and cannot be undone.")

#     if not active_periods:
#         st.info("No active MCM periods exist to delete reports from.")
#         return

#     all_periods = read_from_spreadsheet(dbx, MCM_PERIODS_INFO_PATH)
#     if all_periods.empty:
#         st.warning("Could not load period information.")
#         return
        
#     period_options_map = {f"{row['month_name']} {row['year']}": f"{row['month_name']} {row['year']}" for _, row in all_periods.iterrows()}
#     selected_period = st.selectbox("Select MCM Period to Manage", options=list(period_options_map.keys()))

#     if not selected_period: return

#     master_df = read_from_spreadsheet(dbx, MCM_DATA_PATH)
#     if master_df.empty:
#         st.info("Master data file is empty. Nothing to delete.")
#         return
    
#     master_df['original_index'] = master_df.index
#     master_df['audit_group_number'] = pd.to_numeric(master_df['audit_group_number'], errors='coerce')
#     my_entries = master_df[(master_df['audit_group_number'] == st.session_state.audit_group_no) & (master_df['mcm_period'] == selected_period)].copy()

#     if my_entries.empty:
#         st.info(f"You have no entries in {selected_period} to delete.")
#         return

#     my_entries['delete_label'] = (
#         "TN: " + my_entries['trade_name'].astype(str).str.slice(0, 25) + "... | " +
#         "Para: " + my_entries['audit_para_number'].astype(str) + " | " +
#         "Date: " + my_entries['record_created_date'].astype(str)
#     )
#     deletable_map = my_entries.set_index('delete_label')['original_index'].to_dict()

#     options = ["--Select an entry--"] + list(deletable_map.keys())
#     selected_label = st.selectbox("Select Entry to Delete:", options=options)

#     if selected_label != "--Select an entry--":
#         index_to_delete = deletable_map.get(selected_label)
        
#         if index_to_delete is not None:
#             details = master_df.loc[index_to_delete]
#             st.warning(f"Confirm Deletion: **{details['trade_name']}**, Para: **{details['audit_para_number']}**")
            
#             with st.form(key=f"delete_form_{index_to_delete}"):
#                 password = st.text_input("Enter your password to confirm:", type="password")
#                 if st.form_submit_button("Yes, Delete This Entry", type="primary"):
#                     if password == USER_CREDENTIALS.get(st.session_state.username):
#                         with st.spinner("Deleting entry..."):
#                             df_after_delete = master_df.drop(index=index_to_delete).drop(columns=['original_index'])
#                             if update_spreadsheet_from_df(dbx, df_after_delete, MCM_DATA_PATH):
#                                 st.success("Entry deleted successfully!")
#                                 time.sleep(1)
#                                 st.rerun()
#                             else:
#                                 st.error("Failed to update the data file on Dropbox.")
#                     else:
#                         st.error("Incorrect password.")
# import pandas as pd
# import datetime
# import math
# from io import BytesIO
# import time
# from streamlit_option_menu import option_menu

# # --- Custom Module Imports for Dropbox Version ---
# from dropbox_utils import (
#     read_from_spreadsheet,
#     update_spreadsheet_from_df,
#     upload_file
# )
# from dar_processor import preprocess_pdf_text, get_structured_data_with_gemini,get_structured_data_from_llm
# from validation_utils import validate_data_for_sheet, VALID_CATEGORIES, VALID_PARA_STATUSES
# from config import (
#     USER_CREDENTIALS,
#     MCM_PERIODS_INFO_PATH,
#     MCM_DATA_PATH,
#     DAR_PDFS_PATH
# )
# from models import ParsedDARReport

# # --- Constants and Configuration ---
# SHEET_DATA_COLUMNS_ORDER = [
#     "mcm_period", "audit_group_number", "audit_circle_number", "gstin", "trade_name",
#     "category", "total_amount_detected_overall_rs", "total_amount_recovered_overall_rs",
#     "audit_para_number", "audit_para_heading", "revenue_involved_lakhs_rs",
#     "revenue_recovered_lakhs_rs", "status_of_para", "dar_pdf_path", "record_created_date"
# ]

# DISPLAY_COLUMN_ORDER_EDITOR = [
#     "audit_group_number", "audit_circle_number", "gstin", "trade_name", "category",
#     "total_amount_detected_overall_rs", "total_amount_recovered_overall_rs",
#     "audit_para_number", "audit_para_heading", "revenue_involved_lakhs_rs",
#     "revenue_recovered_lakhs_rs", "status_of_para"
# ]

# # --- Helper Functions ---

# def calculate_audit_circle(audit_group_number_val):
#     """Calculates the audit circle based on the audit group number."""
#     try:
#         agn = int(audit_group_number_val)
#         if 1 <= agn <= 30:
#             return math.ceil(agn / 3.0)
#         return None
#     except (ValueError, TypeError, AttributeError):
#         return None

# def get_active_mcm_periods(dbx):
#     """
#     Reads MCM periods from Dropbox, converts to a dictionary,
#     and returns only the active ones.
#     """
#     df_periods = read_from_spreadsheet(dbx, MCM_PERIODS_INFO_PATH)
#     if df_periods.empty:
#         return {}
    
#     # Ensure 'month_name' and 'year' columns exist before proceeding
#     if 'month_name' not in df_periods.columns or 'year' not in df_periods.columns:
#         st.error("The 'mcm_periods_info.xlsx' file is missing 'month_name' or 'year' columns.")
#         return {}

#     df_periods['key'] = df_periods['month_name'].astype(str) + "_" + df_periods['year'].astype(str)
    
#     # --- FIX ---
#     # NEW: Drop duplicate periods, keeping the last one.
#     df_periods.drop_duplicates(subset=['key'], keep='last', inplace=True)
#     # --- END FIX ---
    
#     all_periods = df_periods.set_index('key').to_dict('index')
#     active_periods = {k: v for k, v in all_periods.items() if v.get("active")}
#     return active_periods

# # --- Main Dashboard Function ---

# def audit_group_dashboard(dbx):
#     """Main function to render the Audit Group dashboard."""
#     st.markdown(f"<div class='sub-header'>Audit Group {st.session_state.audit_group_no} Dashboard</div>", unsafe_allow_html=True)

#     YOUR_GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", "")
#     if not YOUR_GEMINI_API_KEY:
#         st.error("Gemini API Key is not configured. Please contact the administrator.")
#         st.stop()

#     active_periods = get_active_mcm_periods(dbx)

#     default_ag_states = {
#         'ag_current_mcm_key': None, 'ag_current_uploaded_file_obj': None,
#         'ag_current_uploaded_file_name': None, 'ag_editor_data': pd.DataFrame(columns=DISPLAY_COLUMN_ORDER_EDITOR),
#         'ag_pdf_dropbox_path': None, 'ag_validation_errors': [],
#         'ag_uploader_key_suffix': 0, 'ag_deletable_map': {}
#     }
#     for key, value in default_ag_states.items():
#         if key not in st.session_state:
#             st.session_state[key] = value

#     with st.sidebar:
#         try:
#             st.image("logo.png", width=80)
#         except Exception:
#             st.sidebar.markdown("*(Logo)*")
#         st.markdown(f"**User:** {st.session_state.username}<br>**Group No:** {st.session_state.audit_group_no}", unsafe_allow_html=True)
#         if st.button("Logout", key="ag_logout", use_container_width=True):
#             keys_to_clear = list(default_ag_states.keys()) + ['logged_in', 'username', 'role', 'audit_group_no']
#             for k in keys_to_clear:
#                 if k in st.session_state: del st.session_state[k]
#             st.rerun()
#         st.markdown("---")
#         if st.button("🚀 Smart Audit Tracker", key="launch_sat_ag"):
#             st.session_state.app_mode = "smart_audit_tracker"
#             st.rerun()
#         st.markdown("---")

#     selected_tab = option_menu(
#         menu_title="e-MCM Menu",
#         options=["Upload DAR for MCM", "View My Uploaded DARs", "Delete My DAR Entries"],
#         icons=["cloud-upload-fill", "eye-fill", "trash2-fill"], menu_icon="person-workspace",
#         default_index=0, orientation="horizontal",
#         styles={
#             "container": {"padding": "5px !important", "background-color": "#e9ecef"},
#             "icon": {"color": "#28a745", "font-size": "20px"},
#             "nav-link": {"font-size": "16px", "text-align": "center", "margin": "0px", "--hover-color": "#d4edda"},
#             "nav-link-selected": {"background-color": "#28a745", "color": "white"},
#         })

#     st.markdown("<div class='card'>", unsafe_allow_html=True)

#     if selected_tab == "Upload DAR for MCM":
#         upload_dar_tab(dbx, active_periods, YOUR_GEMINI_API_KEY)
#     elif selected_tab == "View My Uploaded DARs":
#         view_uploads_tab(dbx, active_periods)
#     elif selected_tab == "Delete My DAR Entries":
#         delete_entries_tab(dbx, active_periods)

#     st.markdown("</div>", unsafe_allow_html=True)


# def upload_dar_tab(dbx, active_periods, api_key):
#     """Renders the 'Upload DAR' tab with step-by-step status updates."""
#     st.markdown("<h3>Upload DAR PDF for MCM Period</h3>", unsafe_allow_html=True)
#     if not active_periods:
#         st.warning("No active MCM periods available. Please contact the Planning Officer.")
#         return

#     period_options_disp_map = {k: f"{v.get('month_name')} {v.get('year')}" for k, v in sorted(active_periods.items(), key=lambda x: x[0], reverse=True)}
#     period_select_map_rev = {v: k for k, v in period_options_disp_map.items()}

#     selected_period_str = st.selectbox(
#         "Select Active MCM Period", options=list(period_select_map_rev.keys()),
#         key=f"ag_mcm_sel_uploader_{st.session_state.ag_uploader_key_suffix}"
#     )

#     if not selected_period_str: return

#     new_mcm_key = period_select_map_rev[selected_period_str]
#     if st.session_state.ag_current_mcm_key != new_mcm_key:
#         st.session_state.ag_current_mcm_key = new_mcm_key
#         st.session_state.ag_current_uploaded_file_obj = None; st.session_state.ag_current_uploaded_file_name = None
#         st.session_state.ag_editor_data = pd.DataFrame(columns=DISPLAY_COLUMN_ORDER_EDITOR)
#         st.session_state.ag_pdf_dropbox_path = None; st.session_state.ag_validation_errors = []
#         st.session_state.ag_uploader_key_suffix += 1; st.rerun()

#     mcm_info_current = active_periods[st.session_state.ag_current_mcm_key]
#     st.info(f"Uploading for: {mcm_info_current['month_name']} {mcm_info_current['year']}")

#     uploaded_file = st.file_uploader(
#         "Choose DAR PDF", type="pdf",
#         key=f"ag_uploader_main_{st.session_state.ag_current_mcm_key}_{st.session_state.ag_uploader_key_suffix}"
#     )

#     if uploaded_file and st.session_state.ag_current_uploaded_file_name != uploaded_file.name:
#         st.session_state.ag_current_uploaded_file_obj = uploaded_file
#         st.session_state.ag_current_uploaded_file_name = uploaded_file.name
#         st.session_state.ag_editor_data = pd.DataFrame(columns=DISPLAY_COLUMN_ORDER_EDITOR)
#         st.session_state.ag_pdf_dropbox_path = None; st.session_state.ag_validation_errors = []
#         st.rerun()

#     if st.session_state.ag_current_uploaded_file_obj and st.button("Extract Data", use_container_width=True):
#         status_area = st.empty()
        
#         pdf_bytes = st.session_state.ag_current_uploaded_file_obj.getvalue()
        
#         status_area.info("▶️ Step 1/4: Uploading PDF to Dropbox...")
#         dar_filename_on_dropbox = f"AG{st.session_state.audit_group_no}_{st.session_state.ag_current_uploaded_file_name}"
#         pdf_dropbox_path = f"{DAR_PDFS_PATH}/{dar_filename_on_dropbox}"
#         if not upload_file(dbx, pdf_bytes, pdf_dropbox_path):
#             status_area.error("❌ Step 1/4 Failed: Could not upload PDF to Dropbox. Please try again.")
#             st.stop()
#         st.session_state.ag_pdf_dropbox_path = pdf_dropbox_path
#         status_area.info("✅ Step 1/4: PDF uploaded successfully. \n\n▶️ Step 2/4: Pre-processing PDF content...")
        
#         preprocessed_text = preprocess_pdf_text(BytesIO(pdf_bytes))
#         if preprocessed_text.startswith("Error"):
#             status_area.error(f"❌ Step 2/4 Failed: {preprocessed_text}")
#             st.stop()
#         # status_area.info("✅ Step 2/4: PDF pre-processed. \n\n▶️ Step 3/4: Extracting data with Gemini AI (this may take a moment)...")
        
#         # parsed_data = get_structured_data_with_gemini(api_key, preprocessed_text)
#         # Updated the status message
#         status_area.info("✅ Step 2/4: PDF pre-processed. \n\n▶️ Step 3/4: Extracting data with Deepseek (this may take a moment)...")
        
#         # Updated the function call
#         parsed_data = get_structured_data_from_llm(preprocessed_text)
#         if parsed_data.parsing_errors:
#             st.warning(f"AI Parsing Issues: {parsed_data.parsing_errors}")
#         status_area.info("✅ Step 3/4: AI data extraction complete. \n\n▶️ Step 4/4: Formatting data for review...")

#         header_dict = parsed_data.header.model_dump() if parsed_data.header else {}
#         base_info = {"audit_group_number": st.session_state.audit_group_no, "audit_circle_number": calculate_audit_circle(st.session_state.audit_group_no),
#                      "gstin": header_dict.get("gstin"), "trade_name": header_dict.get("trade_name"), "category": header_dict.get("category"),
#                      "total_amount_detected_overall_rs": header_dict.get("total_amount_detected_overall_rs"),
#                      "total_amount_recovered_overall_rs": header_dict.get("total_amount_recovered_overall_rs")}
#         temp_list_for_df = []
#         if parsed_data.audit_paras:
#             for para_obj in parsed_data.audit_paras:
#                 temp_list_for_df.append({**base_info, **para_obj.model_dump()})
#         elif base_info.get("trade_name"):
#             temp_list_for_df.append({**base_info, "audit_para_heading": "N/A - Header Info Only"})
#         else:
#             temp_list_for_df.append({**base_info, "audit_para_heading": "Manual Entry Required"})
#             st.error("AI failed to extract key information. A manual entry template is provided.")
        
#         df_extracted = pd.DataFrame(temp_list_for_df)
#         for col in DISPLAY_COLUMN_ORDER_EDITOR:
#             if col not in df_extracted.columns: df_extracted[col] = None
#         st.session_state.ag_editor_data = df_extracted[DISPLAY_COLUMN_ORDER_EDITOR]
        
#         status_area.success("✅ Step 4/4: Formatting complete. Data is ready for review below.")
#         time.sleep(2)
#         st.rerun()

#     if not st.session_state.ag_editor_data.empty:
#         st.markdown("<h4>Review and Edit Extracted Data:</h4>", unsafe_allow_html=True)
#         col_conf = { "audit_group_number": st.column_config.NumberColumn("Group No.", disabled=True), "audit_circle_number": st.column_config.NumberColumn("Circle No.", disabled=True),
#                      "gstin": st.column_config.TextColumn("GSTIN", width="medium"), "trade_name": st.column_config.TextColumn("Trade Name", width="large"),
#                      "category": st.column_config.SelectboxColumn("Category", options=[None] + VALID_CATEGORIES, width="small"),
#                      "total_amount_detected_overall_rs": st.column_config.NumberColumn("Total Detect (₹)", format="%.2f"),
#                      "total_amount_recovered_overall_rs": st.column_config.NumberColumn("Total Recover (₹)", format="%.2f"),
#                      "audit_para_number": st.column_config.NumberColumn("Para No.", format="%d", width="small"),
#                      "audit_para_heading": st.column_config.TextColumn("Para Heading", width="xlarge"),
#                      "revenue_involved_lakhs_rs": st.column_config.NumberColumn("Rev. Involved (Lakhs)", format="%.2f"),
#                      "revenue_recovered_lakhs_rs": st.column_config.NumberColumn("Rev. Recovered (Lakhs)", format="%.2f"),
#                      "status_of_para": st.column_config.SelectboxColumn("Para Status", options=[None] + VALID_PARA_STATUSES, width="medium") }
        
#         editor_key = f"data_editor_{st.session_state.ag_current_mcm_key}_{st.session_state.ag_current_uploaded_file_name or 'no_file'}"
#         edited_df = st.data_editor(st.session_state.ag_editor_data, column_config=col_conf, num_rows="dynamic", key=editor_key,
#                                    use_container_width=True, hide_index=True, height=min(len(st.session_state.ag_editor_data) * 45 + 70, 450))

#         if st.button("Submit to MCM Sheet", use_container_width=True):
#             submit_status_area = st.empty()
#             submit_status_area.info("▶️ Step 1/4: Cleaning and validating data...")
            
#             df_to_submit = pd.DataFrame(edited_df).dropna(how='all').reset_index(drop=True)
#             if df_to_submit.empty:
#                 submit_status_area.error("❌ Submission Failed: No data found in the editor.")
#                 return
            
#             validation_errors = validate_data_for_sheet(df_to_submit)
#             if validation_errors:
#                 submit_status_area.empty()
#                 st.error("Validation Failed! Please correct the following errors:")
#                 for err in validation_errors: st.warning(f"- {err}")
#                 return
            
#             submit_status_area.info("✅ Step 1/4: Validation successful. \n\n▶️ Step 2/4: Reading master data file from Dropbox...")
#             master_df = read_from_spreadsheet(dbx, MCM_DATA_PATH)
#             if master_df is None:
#                 submit_status_area.error("❌ Step 2/4 Failed: Could not read master data file. Submission aborted.")
#                 return

#             submit_status_area.info("✅ Step 2/4: Master file read. \n\n▶️ Step 3/4: Preparing final data for submission...")
#             df_to_submit['mcm_period'] = selected_period_str
#             df_to_submit['dar_pdf_path'] = st.session_state.ag_pdf_dropbox_path
#             df_to_submit['record_created_date'] = datetime.datetime.now(datetime.timezone.utc).astimezone(datetime.timezone(datetime.timedelta(hours=5, minutes=30))).strftime("%Y-%m-%d %H:%M:%S")

#             for col in SHEET_DATA_COLUMNS_ORDER:
#                 if col not in master_df.columns: master_df[col] = None
#                 if col not in df_to_submit.columns: df_to_submit[col] = None
            
#             submit_status_area.info("✅ Step 3/4: Data prepared. \n\n▶️ Step 4/4: Saving updated data back to Dropbox...")
#             final_df = pd.concat([master_df, df_to_submit[SHEET_DATA_COLUMNS_ORDER]], ignore_index=True)
            
#             if update_spreadsheet_from_df(dbx, final_df, MCM_DATA_PATH):
#                 submit_status_area.success("✅ Submission complete! Data saved successfully.")
#                 st.balloons()
#                 time.sleep(2)
#                 st.session_state.ag_current_uploaded_file_obj = None; st.session_state.ag_current_uploaded_file_name = None
#                 st.session_state.ag_editor_data = pd.DataFrame(columns=DISPLAY_COLUMN_ORDER_EDITOR)
#                 st.session_state.ag_pdf_dropbox_path = None; st.session_state.ag_validation_errors = []
#                 st.session_state.ag_uploader_key_suffix += 1; st.rerun()
#             else:
#                 submit_status_area.error("❌ Step 4/4 Failed: Could not save the updated data to Dropbox.")

# def view_uploads_tab(dbx, all_periods):
#     """Renders the 'View My Uploaded DARs' tab."""
#     st.markdown("<h3>My Uploaded DARs</h3>", unsafe_allow_html=True)
#     if not all_periods:
#         st.info("No MCM periods exist to view reports from.")
#         return

#     period_options_map = {f"{p.get('month_name')} {p.get('year')}": f"{p.get('month_name')} {p.get('year')}" for _, p in all_periods.items()}
#     selected_period = st.selectbox("Select MCM Period to View", options=list(period_options_map.keys()))

#     if not selected_period: return

#     with st.spinner("Loading your uploaded reports..."):
#         df_all_data = read_from_spreadsheet(dbx, MCM_DATA_PATH)
#         if df_all_data.empty:
#             st.info("No reports have been submitted for any period yet.")
#             return

#         df_all_data['audit_group_number'] = pd.to_numeric(df_all_data['audit_group_number'], errors='coerce')
#         my_uploads = df_all_data[(df_all_data['audit_group_number'] == st.session_state.audit_group_no) & (df_all_data['mcm_period'] == selected_period)]

#         if my_uploads.empty:
#             st.info(f"You have not submitted any reports for {selected_period}.")
#             return
        
#         st.markdown(f"<h4>Your Uploads for {selected_period}:</h4>", unsafe_allow_html=True)
#         display_cols = ["gstin", "trade_name", "audit_para_number", "audit_para_heading", "status_of_para",
#                         "revenue_involved_lakhs_rs", "revenue_recovered_lakhs_rs", "record_created_date", "dar_pdf_path"]
#         cols_to_show = [col for col in display_cols if col in my_uploads.columns]
#         st.dataframe(my_uploads[cols_to_show], use_container_width=True, hide_index=True)

# def delete_entries_tab(dbx, all_periods):
#     """Renders the 'Delete My DAR Entries' tab."""
#     st.markdown("<h3>Delete My Uploaded DAR Entries</h3>", unsafe_allow_html=True)
#     st.error("⚠️ **Warning:** This action is permanent and cannot be undone.")

#     if not all_periods:
#         st.info("No MCM periods exist to delete reports from.")
#         return

#     period_options_map = {f"{p.get('month_name')} {p.get('year')}": f"{p.get('month_name')} {p.get('year')}" for _, p in all_periods.items()}
#     selected_period = st.selectbox("Select MCM Period to Manage", options=list(period_options_map.keys()))

#     if not selected_period: return

#     master_df = read_from_spreadsheet(dbx, MCM_DATA_PATH)
#     if master_df.empty:
#         st.info("Master data file is empty. Nothing to delete.")
#         return
        
#     master_df['audit_group_number'] = pd.to_numeric(master_df['audit_group_number'], errors='coerce')
#     my_entries = master_df[(master_df['audit_group_number'] == st.session_state.audit_group_no) & (master_df['mcm_period'] == selected_period)].copy()

#     if my_entries.empty:
#         st.info(f"You have no entries in {selected_period} to delete.")
#         return

#     my_entries['delete_label'] = ("TN: " + my_entries['trade_name'].str.slice(0, 20) + " | " + "Para: " + my_entries['audit_para_number'].astype(str) + " | " + "Date: " + my_entries['record_created_date'].astype(str))
#     st.session_state.ag_deletable_map = my_entries.set_index('delete_label').index.to_series().to_dict()

#     selected_label = st.selectbox("Select Entry to Delete:", options=["--Select an entry--"] + my_entries['delete_label'].tolist())

#     if selected_label != "--Select an entry--":
#         index_to_delete = st.session_state.ag_deletable_map.get(selected_label)
#         if index_to_delete is not None:
#             details = master_df.loc[index_to_delete]
#             st.warning(f"Confirm Deletion: **{details['trade_name']}**, Para: **{details['audit_para_number']}**")
            
#             with st.form(key=f"delete_form_{index_to_delete}"):
#                 password = st.text_input("Enter your password to confirm:", type="password")
#                 if st.form_submit_button("Yes, Delete This Entry", type="primary"):
#                     if password == USER_CREDENTIALS.get(st.session_state.username):
#                         with st.spinner("Deleting entry..."):
#                             df_after_delete = master_df.drop(index=index_to_delete)
#                             if update_spreadsheet_from_df(dbx, df_after_delete, MCM_DATA_PATH):
#                                 st.success("Entry deleted successfully!")
#                                 time.sleep(1); st.rerun()
#                             else:
#                                 st.error("Failed to update the data file on Dropbox.")
#                     else:
#                         st.error("Incorrect password.")
