# ui_audit_group.py
import streamlit as st
import pandas as pd
import datetime
import math
from io import BytesIO
import time
import json
from streamlit_option_menu import option_menu
import html

# --- Custom Module Imports for Dropbox Version ---
from dropbox_utils import (
    read_from_spreadsheet,
    update_spreadsheet_from_df,
    upload_file,
    get_shareable_link
)
from dar_processor import preprocess_pdf_text, get_structured_data_from_llm, get_para_classifications_from_llm
from validation_utils import validate_data_for_sheet, VALID_CATEGORIES, VALID_PARA_STATUSES
from config import (
    USER_CREDENTIALS,
    MCM_PERIODS_INFO_PATH,
    MCM_DATA_PATH,
    DAR_PDFS_PATH,
    TAXPAYER_CLASSIFICATION_OPTIONS,
    GST_RISK_PARAMETERS
)
from models import ParsedDARReport

# --- Constants and Configuration ---
SHEET_DATA_COLUMNS_ORDER = [
    "mcm_period", "audit_group_number", "audit_circle_number", "gstin", "trade_name",
    "category", "taxpayer_classification", "total_amount_detected_overall_rs",
    "total_amount_recovered_overall_rs", "audit_para_number", "audit_para_heading",
    "revenue_involved_rs", "revenue_recovered_rs", "status_of_para",
    "para_classification_code", "risk_flags_data", "dar_pdf_path", "record_created_date"
]

DISPLAY_COLUMN_ORDER_EDITOR = [
    "audit_group_number", "audit_circle_number", "gstin", "trade_name", "category",
    "total_amount_detected_overall_rs", "total_amount_recovered_overall_rs",
    "audit_para_number", "audit_para_heading", "revenue_involved_rs",
    "revenue_recovered_rs", "status_of_para"
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

def reset_ag_states():
    """Resets all session state variables for the audit group upload tab."""
    # FIXED: Don't clear uploaded file references to prevent Extract button from disappearing
    # st.session_state.ag_current_uploaded_file_obj = None  # REMOVED
    # st.session_state.ag_current_uploaded_file_name = None  # REMOVED
    
    st.session_state.ag_editor_data = pd.DataFrame(columns=DISPLAY_COLUMN_ORDER_EDITOR)
    st.session_state.ag_pdf_dropbox_path = None
    st.session_state.ag_validation_errors = []
    st.session_state.ag_risk_flags_data = []
    st.session_state.ag_raw_taxpayer_classification = None

    # FIX: Delete keyed widget states instead of reassigning to prevent StreamlitAPIException
    for key in ['ag_taxpayer_classification', 'ag_no_risk_flags', 'new_risk_flag_select']:
        if key in st.session_state:
            del st.session_state[key]

def reset_file_states():
    """Separate function to reset file-related states when needed."""
    st.session_state.ag_current_uploaded_file_obj = None
    st.session_state.ag_current_uploaded_file_name = None
    reset_ag_states()

# --- Main Dashboard Function ---

def audit_group_dashboard(dbx):
    st.markdown(f"<div class='sub-header'>Audit Group {st.session_state.audit_group_no} Dashboard</div>", unsafe_allow_html=True)

    YOUR_GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", "")
    if not YOUR_GEMINI_API_KEY:
        st.error("Gemini API Key is not configured. Please contact the administrator.")
        st.stop()

    active_periods = get_active_mcm_periods(dbx)

    # Initialize non-widget states
    default_ag_states = {
        'ag_current_mcm_key': None, 'ag_current_uploaded_file_obj': None,
        'ag_current_uploaded_file_name': None, 'ag_editor_data': pd.DataFrame(columns=DISPLAY_COLUMN_ORDER_EDITOR),
        'ag_pdf_dropbox_path': None, 'ag_validation_errors': [],
        'ag_uploader_key_suffix': 0, 'ag_deletable_map': {},
        'ag_risk_flags_data': [], 'ag_raw_taxpayer_classification': None
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
            keys_to_clear = list(st.session_state.keys())
            for k in keys_to_clear:
                del st.session_state[k]
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
    st.markdown("<h3>Upload DAR PDF for MCM Period</h3>", unsafe_allow_html=True)
    if not active_periods:
        st.warning("No active MCM periods available.")
        return
    
    period_options_disp_map = {k: f"{v.get('month_name')} {v.get('year')}" for k, v in sorted(active_periods.items(), key=lambda x: x[0], reverse=True)}
    period_select_map_rev = {v: k for k, v in period_options_disp_map.items()}
    selected_period_str = st.selectbox(
        "Select Active MCM Period", options=list(period_select_map_rev.keys()),
        key=f"ag_mcm_sel_uploader_{st.session_state.ag_uploader_key_suffix}"
    )
    if not selected_period_str: 
        return
    
    new_mcm_key = period_select_map_rev[selected_period_str]
    if st.session_state.ag_current_mcm_key != new_mcm_key:
        st.session_state.ag_current_mcm_key = new_mcm_key
        reset_file_states()  # Use separate function to reset file states when period changes
        st.session_state.ag_uploader_key_suffix += 1
        st.rerun()

    mcm_info_current = active_periods[st.session_state.ag_current_mcm_key]
    st.info(f"Uploading for: {mcm_info_current['month_name']} {mcm_info_current['year']}")
    
    uploaded_file = st.file_uploader(
        "Choose DAR PDF", type="pdf",
        key=f"ag_uploader_main_{st.session_state.ag_current_mcm_key}_{st.session_state.ag_uploader_key_suffix}"
    )
    
    # FIXED: Only update file references, don't reset all states
    if uploaded_file and st.session_state.ag_current_uploaded_file_name != uploaded_file.name:
        st.session_state.ag_current_uploaded_file_obj = uploaded_file
        st.session_state.ag_current_uploaded_file_name = uploaded_file.name
        # Only clear data-related states, not file states
        st.session_state.ag_editor_data = pd.DataFrame(columns=DISPLAY_COLUMN_ORDER_EDITOR)
        st.session_state.ag_pdf_dropbox_path = None
        st.session_state.ag_validation_errors = []
        st.session_state.ag_risk_flags_data = []
        st.session_state.ag_raw_taxpayer_classification = None
        # Clear widget states
        for key in ['ag_taxpayer_classification', 'ag_no_risk_flags', 'new_risk_flag_select']:
            if key in st.session_state:
                del st.session_state[key]
        st.rerun()

    # FIXED: Extract button now appears when file is uploaded
    if st.session_state.ag_current_uploaded_file_obj and st.button("Extract Data", use_container_width=True, type="primary"):
        progress_bar = st.progress(0, text="Starting process...")
        
        pdf_bytes = st.session_state.ag_current_uploaded_file_obj.getvalue()

        progress_bar.progress(10, text="▶️ Stage 1/4: Uploading PDF to Dropbox...")
        dar_filename_on_dropbox = f"AG{st.session_state.audit_group_no}_{st.session_state.ag_current_uploaded_file_name}"
        pdf_dropbox_path = f"{DAR_PDFS_PATH}/{dar_filename_on_dropbox}"
        if not upload_file(dbx, pdf_bytes, pdf_dropbox_path):
            st.error("❌ Failed: Could not upload PDF to Dropbox.")
            st.stop()
        st.session_state.ag_pdf_dropbox_path = pdf_dropbox_path

        progress_bar.progress(25, text="▶️ Stage 2/4: Pre-processing PDF content...")
        preprocessed_text = preprocess_pdf_text(BytesIO(pdf_bytes))
        if preprocessed_text.startswith("Error"):
            st.error(f"❌ Failed: {preprocessed_text}")
            st.stop()
        
        progress_bar.progress(50, text="▶️ Stage 3/4: Extracting with AI (it may take less than 2 min.. pls wait)")
        parsed_data = get_structured_data_from_llm(preprocessed_text)
        if parsed_data.parsing_errors:
            st.warning(f"AI Parsing Issues: {parsed_data.parsing_errors}")
        
        progress_bar.progress(75, text="▶️ Stage 4/4: Formatting data for review...")
        header_dict = parsed_data.header.model_dump() if parsed_data.header else {}
        st.session_state.ag_raw_taxpayer_classification = header_dict.get("taxpayer_classification")
        extracted_risk_flags = header_dict.get("risk_flags") or []
        st.session_state.ag_risk_flags_data = [{"risk_flag": flag, "paras": []} for flag in extracted_risk_flags]
        
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
            st.error("AI failed to extract key information.")
        
        df_extracted = pd.DataFrame(temp_list_for_df)
        for col in DISPLAY_COLUMN_ORDER_EDITOR:
            if col not in df_extracted.columns: 
                df_extracted[col] = None
        st.session_state.ag_editor_data = df_extracted[DISPLAY_COLUMN_ORDER_EDITOR]
        
        progress_bar.empty()
        st.success("✅ Extraction complete. Data is ready for review below.")
        time.sleep(1)
        st.rerun()

    if not st.session_state.ag_editor_data.empty:
        st.markdown("<h4>Review and Edit Extracted Data:</h4>", unsafe_allow_html=True)
        
        st.selectbox(
            "Taxpayer Classification",
            options=[None] + TAXPAYER_CLASSIFICATION_OPTIONS,
            index=(TAXPAYER_CLASSIFICATION_OPTIONS.index(st.session_state.ag_raw_taxpayer_classification) + 1) if st.session_state.ag_raw_taxpayer_classification in TAXPAYER_CLASSIFICATION_OPTIONS else 0,
            key='ag_taxpayer_classification'
        )

        if st.session_state.ag_raw_taxpayer_classification:
            st.caption(f"AI Extracted Value: {st.session_state.ag_raw_taxpayer_classification}")

        col_conf = { 
            "audit_group_number": st.column_config.NumberColumn("Group No.", disabled=True), 
            "audit_circle_number": st.column_config.NumberColumn("Circle No.", disabled=True),
            "gstin": st.column_config.TextColumn("GSTIN", width="medium"), 
            "trade_name": st.column_config.TextColumn("Trade Name", width="large"),
            "category": st.column_config.SelectboxColumn("Category", options=[None] + VALID_CATEGORIES, width="small"),
            "total_amount_detected_overall_rs": st.column_config.NumberColumn("Total Detect (₹)", format="%.2f"),
            "total_amount_recovered_overall_rs": st.column_config.NumberColumn("Total Recover (₹)", format="%.2f"),
            "audit_para_number": st.column_config.NumberColumn("Para No.", format="%d", width="small"),
            "audit_para_heading": st.column_config.TextColumn("Para Heading", width="xlarge"),
            "revenue_involved_rs": st.column_config.NumberColumn("Revenue Involved (₹)", format="%.2f"),
            "revenue_recovered_rs": st.column_config.NumberColumn("Revenue Recovered (₹)", format="%.2f"),
            "status_of_para": st.column_config.SelectboxColumn("Para Status", options=[None] + VALID_PARA_STATUSES, width="medium") 
        }
        editor_key = f"data_editor_{st.session_state.ag_current_mcm_key}_{st.session_state.ag_current_uploaded_file_name or 'no_file'}"
        edited_df = st.data_editor(st.session_state.ag_editor_data, column_config=col_conf, num_rows="dynamic", key=editor_key,
                                   use_container_width=True, hide_index=True, height=min(len(st.session_state.ag_editor_data) * 45 + 70, 450))

        st.markdown("<hr>", unsafe_allow_html=True)
        st.markdown("<h4>Manage Risk Flags:</h4>", unsafe_allow_html=True)
        st.checkbox("No risk flags available for this Taxpayer", key='ag_no_risk_flags')

        if not st.session_state.get('ag_no_risk_flags', False):
            valid_para_numbers = pd.to_numeric(pd.DataFrame(edited_df)['audit_para_number'], errors='coerce').dropna().astype(int).unique().tolist()
            
            risk_container = st.container()
            with risk_container:
                for i, risk_item in enumerate(st.session_state.ag_risk_flags_data):
                    cols = st.columns([2, 5, 4, 1])
                    with cols[0]: 
                        st.text(risk_item['risk_flag'])
                    with cols[1]: 
                        st.caption(GST_RISK_PARAMETERS.get(risk_item['risk_flag'], "Unknown Description"))
                    with cols[2]:
                        selected_paras = st.multiselect( 
                            "Link to Para(s)", options=valid_para_numbers, default=risk_item['paras'], 
                            key=f"risk_{i}_paras", label_visibility="collapsed"
                        )
                        st.session_state.ag_risk_flags_data[i]['paras'] = selected_paras
                    with cols[3]:
                        if st.button("🗑️", key=f"del_risk_{i}", help="Remove this risk flag"):
                            st.session_state.ag_risk_flags_data.pop(i)
                            st.rerun()

                st.markdown("---")
                add_cols = st.columns([3, 1])
                with add_cols[0]: 
                    new_risk_flag = st.selectbox("Add new risk flag:", options=[""] + list(GST_RISK_PARAMETERS.keys()), key="new_risk_flag_select")
                with add_cols[1]:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("Add Flag", use_container_width=True):
                        if new_risk_flag and not any(d['risk_flag'] == new_risk_flag for d in st.session_state.ag_risk_flags_data):
                            st.session_state.ag_risk_flags_data.append({"risk_flag": new_risk_flag, "paras": []})
                            st.rerun()
                        elif not new_risk_flag: 
                            st.warning("Please select a risk flag to add.")
                        else: 
                            st.warning(f"Risk flag '{new_risk_flag}' is already in the list.")

        st.markdown("<hr>", unsafe_allow_html=True)
        if st.button("Submit to MCM Sheet", use_container_width=True, type="primary"):
            submit_status_area = st.empty()
            submit_status_area.info("▶️ Step 1/5: Cleaning and validating data...")
            df_to_submit = pd.DataFrame(edited_df).dropna(how='all').reset_index(drop=True)
            
            if df_to_submit.empty:
                submit_status_area.error("❌ Submission Failed: No data found in the editor.")
                return

            # FIX: Automatically fill disabled/required fields for all rows
            df_to_submit['audit_group_number'] = st.session_state.audit_group_no
            df_to_submit['audit_circle_number'] = calculate_audit_circle(st.session_state.audit_group_no)
            df_to_submit['taxpayer_classification'] = st.session_state.ag_taxpayer_classification

            validation_errors = validate_data_for_sheet(df_to_submit, st.session_state.ag_risk_flags_data, st.session_state.get('ag_no_risk_flags', False))
            if validation_errors:
                submit_status_area.empty()
                st.error("Validation Failed! Please correct the following errors:")
                for err in validation_errors: 
                    st.warning(f"- {err}")
                return

            submit_status_area.info("✅ Step 1/5: Validation successful. \n\n▶️ Step 2/5: Classifying audit paras with AI...")
            headings_to_classify = df_to_submit[df_to_submit['audit_para_number'].notna()]['audit_para_heading'].tolist()
            if headings_to_classify:
                classifications, class_error = get_para_classifications_from_llm(headings_to_classify)
                if class_error:
                    st.error(f"AI Classification Failed: {class_error}")
                    if not classifications: 
                        st.stop()
                    st.warning("Classification was partial. Proceeding with available data.")
                
                para_rows = df_to_submit['audit_para_number'].notna()
                df_to_submit.loc[para_rows, 'para_classification_code'] = classifications[:len(df_to_submit[para_rows])]

            submit_status_area.info("✅ Step 2/5: AI classification complete. \n\n▶️ Step 3/5: Reading master data file...")
            master_df = read_from_spreadsheet(dbx, MCM_DATA_PATH)
            
            submit_status_area.info("✅ Step 3/5: Master file read. \n\n▶️ Step 4/5: Preparing final data...")
            df_to_submit['mcm_period'] = selected_period_str
            df_to_submit['dar_pdf_path'] = st.session_state.ag_pdf_dropbox_path
            df_to_submit['record_created_date'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            risk_json = json.dumps(st.session_state.ag_risk_flags_data) if not st.session_state.get('ag_no_risk_flags', False) else None
            df_to_submit['risk_flags_data'] = pd.Series([risk_json] + [None] * (len(df_to_submit) - 1))

            for col in SHEET_DATA_COLUMNS_ORDER:
                if col not in master_df.columns: 
                    master_df[col] = pd.NA
                if col not in df_to_submit.columns: 
                    df_to_submit[col] = pd.NA

            submit_status_area.info("✅ Step 4/5: Data prepared. \n\n▶️ Step 5/5: Saving updated data to Dropbox...")
            final_df = pd.concat([master_df, df_to_submit[SHEET_DATA_COLUMNS_ORDER]], ignore_index=True)
            if update_spreadsheet_from_df(dbx, final_df, MCM_DATA_PATH):
                submit_status_area.success("✅ Submission complete! Data saved successfully.")
                st.balloons()
                time.sleep(2)
                reset_file_states()  # Reset everything after successful submission
                st.session_state.ag_uploader_key_suffix += 1
                st.rerun()
            else:
                st.error("❌ Step 5/5 Failed: Could not save updated data to Dropbox.")


def view_uploads_tab(dbx):
    """Renders the 'View My Uploaded DARs' tab using Streamlit's native st.dataframe."""
    st.markdown("<h3>My Uploaded DARs</h3>", unsafe_allow_html=True)
    
    all_periods = read_from_spreadsheet(dbx, MCM_PERIODS_INFO_PATH)
    if all_periods.empty:
        st.warning("Could not load period information.")
        return
        
    period_options_map = {f"{row['month_name']} {row['year']}": f"{row['month_name']} {row['year']}" for _, row in all_periods.iterrows()}
    selected_period = st.selectbox("Select MCM Period to Manage", options=list(period_options_map.keys()))
    if not selected_period: 
        return
        
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
                        st.error("Incorrect password.")} {row['year']}" for _, row in all_periods.iterrows()}
    selected_period = st.selectbox("Select MCM Period to View", options=list(period_options_map.keys()))

    if not selected_period: 
        return

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
            my_uploads['pdf_url'] = my_uploads['dar_pdf_path'].apply(
                lambda path: get_link(dbx, path) if pd.notna(path) else None
            )
        
        cols_to_show = [
            "gstin", "trade_name", "taxpayer_classification", "audit_para_number", "audit_para_heading",
            "para_classification_code", "status_of_para", "revenue_involved_rs",
            "revenue_recovered_rs", "record_created_date", "pdf_url"
        ]
        
        df_to_display = my_uploads[[col for col in cols_to_show if col in my_uploads.columns]].copy()

        st.dataframe(
            df_to_display,
            column_config={
                "gstin": st.column_config.TextColumn("GSTIN", width="medium"),
                "trade_name": st.column_config.TextColumn("Trade Name", width="large"),
                "taxpayer_classification": st.column_config.TextColumn("Taxpayer Class"),
                "audit_para_number": st.column_config.NumberColumn("Para No.", format="%d"),
                "audit_para_heading": st.column_config.TextColumn("Para Heading", width="xlarge"),
                "para_classification_code": st.column_config.TextColumn("Para Class Code"),
                "status_of_para": st.column_config.TextColumn("Status"),
                "revenue_involved_rs": st.column_config.NumberColumn("Revenue Involved (₹)", format="%.2f"),
                "revenue_recovered_rs": st.column_config.NumberColumn("Revenue Recovered (₹)", format="%.2f"),
                "record_created_date": st.column_config.DatetimeColumn("Created Date", format="YYYY-MM-DD HH:mm:ss"),
                "pdf_url": st.column_config.LinkColumn(
                    "View PDF",
                    help="Click to view the uploaded DAR PDF",
                    display_text="📄 View PDF"
                )
            },
            hide_index=True,
            use_container_width=True
        )

        risk_data_json = my_uploads['risk_flags_data'].dropna().iloc[0] if 'risk_flags_data' in my_uploads.columns and not my_uploads['risk_flags_data'].dropna().empty else None
        if risk_data_json:
            with st.expander("View Associated Risk Flags"):
                try:
                    risk_data_list = json.loads(risk_data_json)
                    if risk_data_list:
                        for risk_item in risk_data_list:
                            st.markdown(f"**{risk_item['risk_flag']}**: {GST_RISK_PARAMETERS.get(risk_item['risk_flag'])}")
                            st.caption(f"Linked to Para(s): {', '.join(map(str, risk_item['paras'])) if risk_item['paras'] else 'None'}")
                    else:
                        st.info("No risk flags were recorded for this entry.")
                except json.JSONDecodeError:
                    st.warning("Could not parse the stored risk flag data.")


def delete_entries_tab(dbx):
    """Renders the 'Delete My DAR Entries' tab with fixed logic."""
    st.markdown("<h3>Delete My Uploaded DAR Entries</h3>", unsafe_allow_html=True)
    st.error("⚠️ **Warning:** This action is permanent and cannot be undone.")
    
    all_periods = read_from_spreadsheet(dbx, MCM_PERIODS_INFO_PATH)
    if all_periods.empty:
        st.warning("Could not load period information.")
        return
        
    period_options_map = {f"{row['month_name']} {row['year']}": f"{row['month_name'
# import streamlit as st
# import pandas as pd
# import datetime
# import math
# from io import BytesIO
# import time
# import json
# from streamlit_option_menu import option_menu
# import html

# # --- Custom Module Imports for Dropbox Version ---
# from dropbox_utils import (
#     read_from_spreadsheet,
#     update_spreadsheet_from_df,
#     upload_file,
#     get_shareable_link
# )
# from dar_processor import preprocess_pdf_text, get_structured_data_from_llm, get_para_classifications_from_llm
# from validation_utils import validate_data_for_sheet, VALID_CATEGORIES, VALID_PARA_STATUSES
# from config import (
#     USER_CREDENTIALS,
#     MCM_PERIODS_INFO_PATH,
#     MCM_DATA_PATH,
#     DAR_PDFS_PATH,
#     TAXPAYER_CLASSIFICATION_OPTIONS,
#     GST_RISK_PARAMETERS
# )
# from models import ParsedDARReport

# # --- Constants and Configuration ---
# SHEET_DATA_COLUMNS_ORDER = [
#     "mcm_period", "audit_group_number", "audit_circle_number", "gstin", "trade_name",
#     "category", "taxpayer_classification", "total_amount_detected_overall_rs",
#     "total_amount_recovered_overall_rs", "audit_para_number", "audit_para_heading",
#     "revenue_involved_rs", "revenue_recovered_rs", "status_of_para",
#     "para_classification_code", "risk_flags_data", "dar_pdf_path", "record_created_date"
# ]

# DISPLAY_COLUMN_ORDER_EDITOR = [
#     "audit_group_number", "audit_circle_number", "gstin", "trade_name", "category",
#     "total_amount_detected_overall_rs", "total_amount_recovered_overall_rs",
#     "audit_para_number", "audit_para_heading", "revenue_involved_rs",
#     "revenue_recovered_rs", "status_of_para"
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

# def reset_ag_states():
#     """Resets all session state variables for the audit group upload tab."""
#     st.session_state.ag_current_uploaded_file_obj = None
#     st.session_state.ag_current_uploaded_file_name = None
#     st.session_state.ag_editor_data = pd.DataFrame(columns=DISPLAY_COLUMN_ORDER_EDITOR)
#     st.session_state.ag_pdf_dropbox_path = None
#     st.session_state.ag_validation_errors = []
#     st.session_state.ag_taxpayer_classification = None
#     st.session_state.ag_risk_flags_data = []
#     st.session_state.ag_no_risk_flags = False
#     st.session_state.ag_raw_taxpayer_classification = None # ADDED

# # --- Main Dashboard Function ---

# def audit_group_dashboard(dbx):
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
#         'ag_uploader_key_suffix': 0, 'ag_deletable_map': {},
#         'ag_taxpayer_classification': None, 'ag_risk_flags_data': [], 'ag_no_risk_flags': False,
#         'ag_raw_taxpayer_classification': None # ADDED
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
#         view_uploads_tab(dbx)
#     elif selected_tab == "Delete My DAR Entries":
#         delete_entries_tab(dbx)

#     st.markdown("</div>", unsafe_allow_html=True)

# def upload_dar_tab(dbx, active_periods, api_key):
#     st.markdown("<h3>Upload DAR PDF for MCM Period</h3>", unsafe_allow_html=True)
#     if not active_periods:
#         st.warning("No active MCM periods available.")
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
#         reset_ag_states()
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
#         reset_ag_states()
#         st.rerun()

#     if st.session_state.ag_current_uploaded_file_obj and st.button("Extract Data", use_container_width=True):
#         progress_bar = st.progress(0)
#         status_text = st.empty()
        
#         pdf_bytes = st.session_state.ag_current_uploaded_file_obj.getvalue()

#         status_text.info("▶️ Stage 1/4: Uploading PDF to Dropbox...")
#         dar_filename_on_dropbox = f"AG{st.session_state.audit_group_no}_{st.session_state.ag_current_uploaded_file_name}"
#         pdf_dropbox_path = f"{DAR_PDFS_PATH}/{dar_filename_on_dropbox}"
#         if not upload_file(dbx, pdf_bytes, pdf_dropbox_path):
#             st.error("❌ Failed: Could not upload PDF to Dropbox.")
#             st.stop()
#         st.session_state.ag_pdf_dropbox_path = pdf_dropbox_path
#         progress_bar.progress(25)

#         status_text.info("▶️ Stage 2/4: Pre-processing PDF content...")
#         preprocessed_text = preprocess_pdf_text(BytesIO(pdf_bytes))
#         if preprocessed_text.startswith("Error"):
#             st.error(f"❌ Failed: {preprocessed_text}")
#             st.stop()
#         progress_bar.progress(50)
        
#         status_text.info("▶️ Stage 3/4: Extracting with AI (it may take less than 2 min.. pls wait)")
#         parsed_data = get_structured_data_from_llm(preprocessed_text)
#         if parsed_data.parsing_errors:
#             st.warning(f"AI Parsing Issues: {parsed_data.parsing_errors}")
#         progress_bar.progress(75)
        
#         status_text.info("▶️ Stage 4/4: Formatting data for review...")
#         header_dict = parsed_data.header.model_dump() if parsed_data.header else {}
#         st.session_state.ag_raw_taxpayer_classification = header_dict.get("taxpayer_classification")
#         st.session_state.ag_taxpayer_classification = st.session_state.ag_raw_taxpayer_classification
#         extracted_risk_flags = header_dict.get("risk_flags") or []
#         st.session_state.ag_risk_flags_data = [{"risk_flag": flag, "paras": []} for flag in extracted_risk_flags]
        
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
#             st.error("AI failed to extract key information.")
        
#         df_extracted = pd.DataFrame(temp_list_for_df)
#         for col in DISPLAY_COLUMN_ORDER_EDITOR:
#             if col not in df_extracted.columns: df_extracted[col] = None
#         st.session_state.ag_editor_data = df_extracted[DISPLAY_COLUMN_ORDER_EDITOR]
#         progress_bar.progress(100)
#         status_text.empty()
#         progress_bar.empty()
        
#         st.success("✅ Extraction complete. Data is ready for review below.")
#         time.sleep(1)
#         st.rerun()

#     if not st.session_state.ag_editor_data.empty:
#         st.markdown("<h4>Review and Edit Extracted Data:</h4>", unsafe_allow_html=True)
        
#         st.selectbox(
#             "Taxpayer Classification",
#             options=[None] + TAXPAYER_CLASSIFICATION_OPTIONS,
#             index=(TAXPAYER_CLASSIFICATION_OPTIONS.index(st.session_state.ag_raw_taxpayer_classification) + 1) if st.session_state.ag_raw_taxpayer_classification in TAXPAYER_CLASSIFICATION_OPTIONS else 0,
#             key='ag_taxpayer_classification'
#         )

#         if st.session_state.ag_raw_taxpayer_classification:
#             st.caption(f"AI Extracted Value: {st.session_state.ag_raw_taxpayer_classification}")

#         col_conf = { "audit_group_number": st.column_config.NumberColumn("Group No.", disabled=True), "audit_circle_number": st.column_config.NumberColumn("Circle No.", disabled=True),
#                      "gstin": st.column_config.TextColumn("GSTIN", width="medium"), "trade_name": st.column_config.TextColumn("Trade Name", width="large"),
#                      "category": st.column_config.SelectboxColumn("Category", options=[None] + VALID_CATEGORIES, width="small"),
#                      "total_amount_detected_overall_rs": st.column_config.NumberColumn("Total Detect (₹)", format="%.2f"),
#                      "total_amount_recovered_overall_rs": st.column_config.NumberColumn("Total Recover (₹)", format="%.2f"),
#                      "audit_para_number": st.column_config.NumberColumn("Para No.", format="%d", width="small"),
#                      "audit_para_heading": st.column_config.TextColumn("Para Heading", width="xlarge"),
#                      "revenue_involved_rs": st.column_config.NumberColumn("Revenue Involved (₹)", format="%.2f"),
#                      "revenue_recovered_rs": st.column_config.NumberColumn("Revenue Recovered (₹)", format="%.2f"),
#                      "status_of_para": st.column_config.SelectboxColumn("Para Status", options=[None] + VALID_PARA_STATUSES, width="medium") }
#         editor_key = f"data_editor_{st.session_state.ag_current_mcm_key}_{st.session_state.ag_current_uploaded_file_name or 'no_file'}"
#         edited_df = st.data_editor(st.session_state.ag_editor_data, column_config=col_conf, num_rows="dynamic", key=editor_key,
#                                    use_container_width=True, hide_index=True, height=min(len(st.session_state.ag_editor_data) * 45 + 70, 450))

#         st.markdown("<hr>", unsafe_allow_html=True)
#         st.markdown("<h4>Manage Risk Flags:</h4>", unsafe_allow_html=True)
#         st.checkbox("No risk flags available for this Taxpayer", key='ag_no_risk_flags')

#         if not st.session_state.ag_no_risk_flags:
#             valid_para_numbers = pd.to_numeric(pd.DataFrame(edited_df)['audit_para_number'], errors='coerce').dropna().astype(int).unique().tolist()
            
#             risk_container = st.container()
#             with risk_container:
#                 for i, risk_item in enumerate(st.session_state.ag_risk_flags_data):
#                     cols = st.columns([2, 5, 4, 1])
#                     with cols[0]: st.text(risk_item['risk_flag'])
#                     with cols[1]: st.caption(GST_RISK_PARAMETERS.get(risk_item['risk_flag'], "Unknown Description"))
#                     with cols[2]:
#                         selected_paras = st.multiselect( "Link to Para(s)", options=valid_para_numbers, default=risk_item['paras'], key=f"risk_{i}_paras", label_visibility="collapsed")
#                         st.session_state.ag_risk_flags_data[i]['paras'] = selected_paras
#                     with cols[3]:
#                         if st.button("🗑️", key=f"del_risk_{i}", help="Remove this risk flag"):
#                             st.session_state.ag_risk_flags_data.pop(i)
#                             st.rerun()

#                 st.markdown("---")
#                 add_cols = st.columns([3, 1])
#                 with add_cols[0]: new_risk_flag = st.selectbox("Add new risk flag:", options=[""] + list(GST_RISK_PARAMETERS.keys()), key="new_risk_flag_select")
#                 with add_cols[1]:
#                     st.markdown("<br>", unsafe_allow_html=True)
#                     if st.button("Add Flag", use_container_width=True):
#                         if new_risk_flag and not any(d['risk_flag'] == new_risk_flag for d in st.session_state.ag_risk_flags_data):
#                             st.session_state.ag_risk_flags_data.append({"risk_flag": new_risk_flag, "paras": []})
#                             st.rerun()
#                         elif not new_risk_flag: st.warning("Please select a risk flag to add.")
#                         else: st.warning(f"Risk flag '{new_risk_flag}' is already in the list.")

#         st.markdown("<hr>", unsafe_allow_html=True)
#         if st.button("Submit to MCM Sheet", use_container_width=True, type="primary"):
#             submit_status_area = st.empty()
#             submit_status_area.info("▶️ Step 1/5: Cleaning and validating data...")
#             df_to_submit = pd.DataFrame(edited_df).dropna(how='all').reset_index(drop=True)
#             if df_to_submit.empty:
#                 submit_status_area.error("❌ Submission Failed: No data found in the editor.")
#                 return

#             # FIX: Automatically fill disabled fields for all rows, including manually added ones
#             df_to_submit['audit_group_number'] = st.session_state.audit_group_no
#             df_to_submit['audit_circle_number'] = calculate_audit_circle(st.session_state.audit_group_no)
#             df_to_submit['taxpayer_classification'] = st.session_state.ag_taxpayer_classification

#             validation_errors = validate_data_for_sheet(df_to_submit, st.session_state.ag_risk_flags_data, st.session_state.ag_no_risk_flags)
#             if validation_errors:
#                 submit_status_area.empty()
#                 st.error("Validation Failed! Please correct the following errors:")
#                 for err in validation_errors: st.warning(f"- {err}")
#                 return

#             submit_status_area.info("✅ Step 1/5: Validation successful. \n\n▶️ Step 2/5: Classifying audit paras with AI...")
#             headings_to_classify = df_to_submit[df_to_submit['audit_para_number'].notna()]['audit_para_heading'].tolist()
#             if headings_to_classify:
#                 classifications, class_error = get_para_classifications_from_llm(headings_to_classify)
#                 if class_error:
#                     st.error(f"AI Classification Failed: {class_error}")
#                     if not classifications: st.stop()
#                     st.warning("Classification was partial. Proceeding with available data.")
                
#                 para_rows = df_to_submit['audit_para_number'].notna()
#                 df_to_submit.loc[para_rows, 'para_classification_code'] = classifications[:len(df_to_submit[para_rows])]

#             submit_status_area.info("✅ Step 2/5: AI classification complete. \n\n▶️ Step 3/5: Reading master data file...")
#             master_df = read_from_spreadsheet(dbx, MCM_DATA_PATH)
            
#             submit_status_area.info("✅ Step 3/5: Master file read. \n\n▶️ Step 4/5: Preparing final data...")
#             df_to_submit['mcm_period'] = selected_period_str
#             df_to_submit['dar_pdf_path'] = st.session_state.ag_pdf_dropbox_path
#             df_to_submit['record_created_date'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

#             risk_json = json.dumps(st.session_state.ag_risk_flags_data) if not st.session_state.ag_no_risk_flags else None
#             df_to_submit['risk_flags_data'] = pd.Series([risk_json] + [None] * (len(df_to_submit) - 1))

#             for col in SHEET_DATA_COLUMNS_ORDER:
#                 if col not in master_df.columns: master_df[col] = pd.NA
#                 if col not in df_to_submit.columns: df_to_submit[col] = pd.NA

#             submit_status_area.info("✅ Step 4/5: Data prepared. \n\n▶️ Step 5/5: Saving updated data to Dropbox...")
#             final_df = pd.concat([master_df, df_to_submit[SHEET_DATA_COLUMNS_ORDER]], ignore_index=True)
#             if update_spreadsheet_from_df(dbx, final_df, MCM_DATA_PATH):
#                 submit_status_area.success("✅ Submission complete! Data saved successfully.")
#                 st.balloons()
#                 time.sleep(2)
#                 reset_ag_states()
#                 st.session_state.ag_uploader_key_suffix += 1
#                 st.rerun()
#             else:
#                 st.error("❌ Step 5/5 Failed: Could not save updated data to Dropbox.")

# # def upload_dar_tab(dbx, active_periods, api_key):
# #     st.markdown("<h3>Upload DAR PDF for MCM Period</h3>", unsafe_allow_html=True)
# #     if not active_periods:
# #         st.warning("No active MCM periods available.")
# #         return
# #     period_options_disp_map = {k: f"{v.get('month_name')} {v.get('year')}" for k, v in sorted(active_periods.items(), key=lambda x: x[0], reverse=True)}
# #     period_select_map_rev = {v: k for k, v in period_options_disp_map.items()}
# #     selected_period_str = st.selectbox(
# #         "Select Active MCM Period", options=list(period_select_map_rev.keys()),
# #         key=f"ag_mcm_sel_uploader_{st.session_state.ag_uploader_key_suffix}"
# #     )
# #     if not selected_period_str: return
# #     new_mcm_key = period_select_map_rev[selected_period_str]
# #     if st.session_state.ag_current_mcm_key != new_mcm_key:
# #         st.session_state.ag_current_mcm_key = new_mcm_key
# #         reset_ag_states()
# #         st.session_state.ag_uploader_key_suffix += 1; st.rerun()

# #     mcm_info_current = active_periods[st.session_state.ag_current_mcm_key]
# #     st.info(f"Uploading for: {mcm_info_current['month_name']} {mcm_info_current['year']}")
# #     uploaded_file = st.file_uploader(
# #         "Choose DAR PDF", type="pdf",
# #         key=f"ag_uploader_main_{st.session_state.ag_current_mcm_key}_{st.session_state.ag_uploader_key_suffix}"
# #     )
# #     if uploaded_file and st.session_state.ag_current_uploaded_file_name != uploaded_file.name:
# #         st.session_state.ag_current_uploaded_file_obj = uploaded_file
# #         st.session_state.ag_current_uploaded_file_name = uploaded_file.name
# #         reset_ag_states()
# #         st.rerun()

# #     if st.session_state.ag_current_uploaded_file_obj and st.button("Extract Data", use_container_width=True):
# #         # CHANGED: Show spinner with custom message during processing
# #         with st.spinner("Extracting with AI (it may take less than 2 min.. pls wait)"):
# #             pdf_bytes = st.session_state.ag_current_uploaded_file_obj.getvalue()
            
# #             # Step 1: Upload
# #             dar_filename_on_dropbox = f"AG{st.session_state.audit_group_no}_{st.session_state.ag_current_uploaded_file_name}"
# #             pdf_dropbox_path = f"{DAR_PDFS_PATH}/{dar_filename_on_dropbox}"
# #             if not upload_file(dbx, pdf_bytes, pdf_dropbox_path):
# #                 st.error("❌ Failed: Could not upload PDF to Dropbox.")
# #                 st.stop()
# #             st.session_state.ag_pdf_dropbox_path = pdf_dropbox_path
            
# #             # Step 2: Pre-process
# #             preprocessed_text = preprocess_pdf_text(BytesIO(pdf_bytes))
# #             if preprocessed_text.startswith("Error"):
# #                 st.error(f"❌ Failed: {preprocessed_text}")
# #                 st.stop()
            
# #             # Step 3: Extract with AI
# #             parsed_data = get_structured_data_from_llm(preprocessed_text)
# #             if parsed_data.parsing_errors:
# #                 st.warning(f"AI Parsing Issues: {parsed_data.parsing_errors}")
            
# #             # Step 4: Format data
# #             header_dict = parsed_data.header.model_dump() if parsed_data.header else {}
# #             # ADDED: Store the raw extracted value
# #             st.session_state.ag_raw_taxpayer_classification = header_dict.get("taxpayer_classification")
# #             st.session_state.ag_taxpayer_classification = st.session_state.ag_raw_taxpayer_classification

# #             extracted_risk_flags = header_dict.get("risk_flags") or []
# #             st.session_state.ag_risk_flags_data = [{"risk_flag": flag, "paras": []} for flag in extracted_risk_flags]

# #             base_info = {"audit_group_number": st.session_state.audit_group_no, "audit_circle_number": calculate_audit_circle(st.session_state.audit_group_no),
# #                          "gstin": header_dict.get("gstin"), "trade_name": header_dict.get("trade_name"), "category": header_dict.get("category"),
# #                          "total_amount_detected_overall_rs": header_dict.get("total_amount_detected_overall_rs"),
# #                          "total_amount_recovered_overall_rs": header_dict.get("total_amount_recovered_overall_rs")}
# #             temp_list_for_df = []
# #             if parsed_data.audit_paras:
# #                 for para_obj in parsed_data.audit_paras:
# #                     temp_list_for_df.append({**base_info, **para_obj.model_dump()})
# #             elif base_info.get("trade_name"):
# #                 temp_list_for_df.append({**base_info, "audit_para_heading": "N/A - Header Info Only"})
# #             else:
# #                 temp_list_for_df.append({**base_info, "audit_para_heading": "Manual Entry Required"})
# #                 st.error("AI failed to extract key information.")
            
# #             df_extracted = pd.DataFrame(temp_list_for_df)
# #             for col in DISPLAY_COLUMN_ORDER_EDITOR:
# #                 if col not in df_extracted.columns: df_extracted[col] = None
# #             st.session_state.ag_editor_data = df_extracted[DISPLAY_COLUMN_ORDER_EDITOR]
        
# #         st.success("✅ Extraction complete. Data is ready for review below.")
# #         time.sleep(2)
# #         st.rerun()

# #     if not st.session_state.ag_editor_data.empty:
# #         st.markdown("<h4>Review and Edit Extracted Data:</h4>", unsafe_allow_html=True)
        
# #         # --- Taxpayer Classification Dropdown ---
# #         st.selectbox(
# #             "Taxpayer Classification",
# #             options=[None] + TAXPAYER_CLASSIFICATION_OPTIONS,
# #             index=(TAXPAYER_CLASSIFICATION_OPTIONS.index(st.session_state.ag_raw_taxpayer_classification) + 1) if st.session_state.ag_raw_taxpayer_classification in TAXPAYER_CLASSIFICATION_OPTIONS else 0,
# #             key='ag_taxpayer_classification'
# #         )

# #         # ADDED: Display the raw AI extracted value
# #         if st.session_state.ag_raw_taxpayer_classification:
# #             st.caption(f"AI Extracted Value: {st.session_state.ag_raw_taxpayer_classification}")

# #         col_conf = { "audit_group_number": st.column_config.NumberColumn("Group No.", disabled=True), "audit_circle_number": st.column_config.NumberColumn("Circle No.", disabled=True),
# #                      "gstin": st.column_config.TextColumn("GSTIN", width="medium"), "trade_name": st.column_config.TextColumn("Trade Name", width="large"),
# #                      "category": st.column_config.SelectboxColumn("Category", options=[None] + VALID_CATEGORIES, width="small"),
# #                      "total_amount_detected_overall_rs": st.column_config.NumberColumn("Total Detect (₹)", format="%.2f"),
# #                      "total_amount_recovered_overall_rs": st.column_config.NumberColumn("Total Recover (₹)", format="%.2f"),
# #                      "audit_para_number": st.column_config.NumberColumn("Para No.", format="%d", width="small"),
# #                      "audit_para_heading": st.column_config.TextColumn("Para Heading", width="xlarge"),
# #                      "revenue_involved_rs": st.column_config.NumberColumn("Revenue Involved (₹)", format="%.2f"),
# #                      "revenue_recovered_rs": st.column_config.NumberColumn("Revenue Recovered (₹)", format="%.2f"),
# #                      "status_of_para": st.column_config.SelectboxColumn("Para Status", options=[None] + VALID_PARA_STATUSES, width="medium") }
# #         editor_key = f"data_editor_{st.session_state.ag_current_mcm_key}_{st.session_state.ag_current_uploaded_file_name or 'no_file'}"
# #         edited_df = st.data_editor(st.session_state.ag_editor_data, column_config=col_conf, num_rows="dynamic", key=editor_key,
# #                                    use_container_width=True, hide_index=True, height=min(len(st.session_state.ag_editor_data) * 45 + 70, 450))

# #         st.markdown("<hr>", unsafe_allow_html=True)
# #         st.markdown("<h4>Manage Risk Flags:</h4>", unsafe_allow_html=True)
# #         st.checkbox("No risk flags available for this Taxpayer", key='ag_no_risk_flags')

# #         if not st.session_state.ag_no_risk_flags:
# #             valid_para_numbers = pd.to_numeric(pd.DataFrame(edited_df)['audit_para_number'], errors='coerce').dropna().astype(int).unique().tolist()
            
# #             risk_container = st.container()
# #             with risk_container:
# #                 for i, risk_item in enumerate(st.session_state.ag_risk_flags_data):
# #                     cols = st.columns([2, 5, 4, 1])
# #                     with cols[0]:
# #                         st.text(risk_item['risk_flag'])
# #                     with cols[1]:
# #                         st.caption(GST_RISK_PARAMETERS.get(risk_item['risk_flag'], "Unknown Description"))
# #                     with cols[2]:
# #                         selected_paras = st.multiselect(
# #                             "Link to Para(s)", options=valid_para_numbers, default=risk_item['paras'],
# #                             key=f"risk_{i}_paras", label_visibility="collapsed"
# #                         )
# #                         st.session_state.ag_risk_flags_data[i]['paras'] = selected_paras
# #                     with cols[3]:
# #                         if st.button("🗑️", key=f"del_risk_{i}", help="Remove this risk flag"):
# #                             st.session_state.ag_risk_flags_data.pop(i)
# #                             st.rerun()

# #                 st.markdown("---")
# #                 add_cols = st.columns([3, 1])
# #                 with add_cols[0]:
# #                     new_risk_flag = st.selectbox("Add new risk flag:", options=[""] + list(GST_RISK_PARAMETERS.keys()), key="new_risk_flag_select")
# #                 with add_cols[1]:
# #                     st.markdown("<br>", unsafe_allow_html=True)
# #                     if st.button("Add Flag", use_container_width=True):
# #                         if new_risk_flag and not any(d['risk_flag'] == new_risk_flag for d in st.session_state.ag_risk_flags_data):
# #                             st.session_state.ag_risk_flags_data.append({"risk_flag": new_risk_flag, "paras": []})
# #                             st.rerun()
# #                         elif not new_risk_flag:
# #                             st.warning("Please select a risk flag to add.")
# #                         else:
# #                             st.warning(f"Risk flag '{new_risk_flag}' is already in the list.")

# #         # ADDED: The missing submit button and its logic
# #         st.markdown("<hr>", unsafe_allow_html=True)
# #         if st.button("Submit to MCM Sheet", use_container_width=True, type="primary"):
# #             submit_status_area = st.empty()
# #             submit_status_area.info("▶️ Step 1/5: Cleaning and validating data...")
# #             df_to_submit = pd.DataFrame(edited_df).dropna(how='all').reset_index(drop=True)
# #             if df_to_submit.empty:
# #                 submit_status_area.error("❌ Submission Failed: No data found in the editor.")
# #                 return

# #             df_to_submit['taxpayer_classification'] = st.session_state.ag_taxpayer_classification

# #             validation_errors = validate_data_for_sheet(df_to_submit, st.session_state.ag_risk_flags_data, st.session_state.ag_no_risk_flags)
# #             if validation_errors:
# #                 submit_status_area.empty()
# #                 st.error("Validation Failed! Please correct the following errors:")
# #                 for err in validation_errors: st.warning(f"- {err}")
# #                 return

# #             submit_status_area.info("✅ Step 1/5: Validation successful. \n\n▶️ Step 2/5: Classifying audit paras with AI...")
# #             headings_to_classify = df_to_submit[df_to_submit['audit_para_number'].notna()]['audit_para_heading'].tolist()
# #             classifications, class_error = get_para_classifications_from_llm(headings_to_classify)
# #             if class_error:
# #                 st.error(f"AI Classification Failed: {class_error}")
# #                 if not classifications: # Stop if it completely failed
# #                     st.stop()
# #                 st.warning("Classification was partial. Proceeding with available data.")
            
# #             para_rows = df_to_submit['audit_para_number'].notna()
# #             df_to_submit.loc[para_rows, 'para_classification_code'] = classifications[:len(df_to_submit[para_rows])]

# #             submit_status_area.info("✅ Step 2/5: AI classification complete. \n\n▶️ Step 3/5: Reading master data file...")
# #             master_df = read_from_spreadsheet(dbx, MCM_DATA_PATH)
            
# #             submit_status_area.info("✅ Step 3/5: Master file read. \n\n▶️ Step 4/5: Preparing final data...")
# #             df_to_submit['mcm_period'] = selected_period_str
# #             df_to_submit['dar_pdf_path'] = st.session_state.ag_pdf_dropbox_path
# #             df_to_submit['record_created_date'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# #             risk_json = json.dumps(st.session_state.ag_risk_flags_data) if not st.session_state.ag_no_risk_flags else None
# #             df_to_submit['risk_flags_data'] = pd.Series([risk_json] + [None] * (len(df_to_submit) - 1))

# #             for col in SHEET_DATA_COLUMNS_ORDER:
# #                 if col not in master_df.columns: master_df[col] = pd.NA
# #                 if col not in df_to_submit.columns: df_to_submit[col] = pd.NA

# #             submit_status_area.info("✅ Step 4/5: Data prepared. \n\n▶️ Step 5/5: Saving updated data to Dropbox...")
# #             final_df = pd.concat([master_df, df_to_submit[SHEET_DATA_COLUMNS_ORDER]], ignore_index=True)
# #             if update_spreadsheet_from_df(dbx, final_df, MCM_DATA_PATH):
# #                 submit_status_area.success("✅ Submission complete! Data saved successfully.")
# #                 st.balloons()
# #                 time.sleep(2)
# #                 reset_ag_states()
# #                 st.session_state.ag_uploader_key_suffix += 1
# #                 st.rerun()
# #             else:
# #                 st.error("❌ Step 5/5 Failed: Could not save updated data to Dropbox.")


# def view_uploads_tab(dbx):
#     """Renders the 'View My Uploaded DARs' tab using Streamlit's native st.dataframe."""
#     st.markdown("<h3>My Uploaded DARs</h3>", unsafe_allow_html=True)
    
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
#             my_uploads['pdf_url'] = my_uploads['dar_pdf_path'].apply(
#                 lambda path: get_link(dbx, path) if pd.notna(path) else None
#             )
        
#         cols_to_show = [
#             "gstin", "trade_name", "taxpayer_classification", "audit_para_number", "audit_para_heading",
#             "para_classification_code", "status_of_para", "revenue_involved_rs",
#             "revenue_recovered_rs", "record_created_date", "pdf_url"
#         ]
        
#         df_to_display = my_uploads[[col for col in cols_to_show if col in my_uploads.columns]].copy()

#         st.dataframe(
#             df_to_display,
#             column_config={
#                 "gstin": st.column_config.TextColumn("GSTIN", width="medium"),
#                 "trade_name": st.column_config.TextColumn("Trade Name", width="large"),
#                 "taxpayer_classification": st.column_config.TextColumn("Taxpayer Class"),
#                 "audit_para_number": st.column_config.NumberColumn("Para No.", format="%d"),
#                 "audit_para_heading": st.column_config.TextColumn("Para Heading", width="xlarge"),
#                 "para_classification_code": st.column_config.TextColumn("Para Class Code"),
#                 "status_of_para": st.column_config.TextColumn("Status"),
#                 "revenue_involved_rs": st.column_config.NumberColumn("Revenue Involved (₹)", format="%.2f"),
#                 "revenue_recovered_rs": st.column_config.NumberColumn("Revenue Recovered (₹)", format="%.2f"),
#                 "record_created_date": st.column_config.DatetimeColumn("Created Date", format="YYYY-MM-DD HH:mm:ss"),
#                 "pdf_url": st.column_config.LinkColumn(
#                     "View PDF",
#                     help="Click to view the uploaded DAR PDF",
#                     display_text="📄 View PDF"
#                 )
#             },
#             hide_index=True,
#             use_container_width=True
#         )

#         # Display Risk Flags in an expander
#         risk_data_json = my_uploads['risk_flags_data'].dropna().iloc[0] if 'risk_flags_data' in my_uploads.columns and not my_uploads['risk_flags_data'].dropna().empty else None
#         if risk_data_json:
#             with st.expander("View Associated Risk Flags"):
#                 try:
#                     risk_data_list = json.loads(risk_data_json)
#                     if risk_data_list:
#                         for risk_item in risk_data_list:
#                             st.markdown(f"**{risk_item['risk_flag']}**: {GST_RISK_PARAMETERS.get(risk_item['risk_flag'])}")
#                             st.caption(f"Linked to Para(s): {', '.join(map(str, risk_item['paras'])) if risk_item['paras'] else 'None'}")
#                     else:
#                         st.info("No risk flags were recorded for this entry.")
#                 except json.JSONDecodeError:
#                     st.warning("Could not parse the stored risk flag data.")


# def delete_entries_tab(dbx):
#     """Renders the 'Delete My DAR Entries' tab with fixed logic."""
#     st.markdown("<h3>Delete My Uploaded DAR Entries</h3>", unsafe_allow_html=True)
#     st.error("⚠️ **Warning:** This action is permanent and cannot be undone.")
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
#                         st.error("Incorrect password.")# # ui_audit_group.py
# # import streamlit as st
# # import pandas as pd
# # import datetime
# # import math
# # from io import BytesIO
# # import time
# # import json
# # from streamlit_option_menu import option_menu
# # import html

# # # --- Custom Module Imports for Dropbox Version ---
# # from dropbox_utils import (
# #     read_from_spreadsheet,
# #     update_spreadsheet_from_df,
# #     upload_file,
# #     get_shareable_link
# # )
# # from dar_processor import preprocess_pdf_text, get_structured_data_from_llm, get_para_classifications_from_llm
# # from validation_utils import validate_data_for_sheet, VALID_CATEGORIES, VALID_PARA_STATUSES
# # from config import (
# #     USER_CREDENTIALS,
# #     MCM_PERIODS_INFO_PATH,
# #     MCM_DATA_PATH,
# #     DAR_PDFS_PATH,
# #     TAXPAYER_CLASSIFICATION_OPTIONS,
# #     GST_RISK_PARAMETERS
# # )
# # from models import ParsedDARReport

# # # --- Constants and Configuration ---
# # SHEET_DATA_COLUMNS_ORDER = [
# #     "mcm_period", "audit_group_number", "audit_circle_number", "gstin", "trade_name",
# #     "category", "taxpayer_classification", "total_amount_detected_overall_rs",
# #     "total_amount_recovered_overall_rs", "audit_para_number", "audit_para_heading",
# #     "revenue_involved_rs", "revenue_recovered_rs", "status_of_para",
# #     "para_classification_code", "risk_flags_data", "dar_pdf_path", "record_created_date"
# # ]

# # DISPLAY_COLUMN_ORDER_EDITOR = [
# #     "audit_group_number", "audit_circle_number", "gstin", "trade_name", "category",
# #     "total_amount_detected_overall_rs", "total_amount_recovered_overall_rs",
# #     "audit_para_number", "audit_para_heading", "revenue_involved_rs",
# #     "revenue_recovered_rs", "status_of_para"
# # ]

# # # --- Helper Functions ---

# # def calculate_audit_circle(audit_group_number_val):
# #     """Calculates the audit circle based on the audit group number."""
# #     try:
# #         agn = int(audit_group_number_val)
# #         if 1 <= agn <= 30:
# #             return math.ceil(agn / 3.0)
# #         return None
# #     except (ValueError, TypeError, AttributeError):
# #         return None

# # @st.cache_data(ttl=120)
# # def get_active_mcm_periods(_dbx):
# #     """
# #     Reads MCM periods from Dropbox, converts to a dictionary,
# #     and returns only the active ones. Caches the result.
# #     """
# #     df_periods = read_from_spreadsheet(_dbx, MCM_PERIODS_INFO_PATH)
# #     if df_periods.empty:
# #         return {}

# #     if 'month_name' not in df_periods.columns or 'year' not in df_periods.columns:
# #         st.error("The 'mcm_periods_info.xlsx' file is missing 'month_name' or 'year' columns.")
# #         return {}

# #     df_periods['key'] = df_periods['month_name'].astype(str) + "_" + df_periods['year'].astype(str)
# #     df_periods.drop_duplicates(subset=['key'], keep='last', inplace=True)

# #     all_periods = df_periods.set_index('key').to_dict('index')
# #     active_periods = {k: v for k, v in all_periods.items() if v.get("active")}
# #     return active_periods

# # def reset_ag_states():
# #     """Resets all session state variables for the audit group upload tab."""
# #     st.session_state.ag_current_uploaded_file_obj = None
# #     st.session_state.ag_current_uploaded_file_name = None
# #     st.session_state.ag_editor_data = pd.DataFrame(columns=DISPLAY_COLUMN_ORDER_EDITOR)
# #     st.session_state.ag_pdf_dropbox_path = None
# #     st.session_state.ag_validation_errors = []
# #     st.session_state.ag_taxpayer_classification = None
# #     st.session_state.ag_risk_flags_data = []
# #     st.session_state.ag_no_risk_flags = False


# # # --- Main Dashboard Function ---

# # def audit_group_dashboard(dbx):
# #     st.markdown(f"<div class='sub-header'>Audit Group {st.session_state.audit_group_no} Dashboard</div>", unsafe_allow_html=True)

# #     YOUR_GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", "")
# #     if not YOUR_GEMINI_API_KEY:
# #         st.error("Gemini API Key is not configured. Please contact the administrator.")
# #         st.stop()

# #     active_periods = get_active_mcm_periods(dbx)

# #     default_ag_states = {
# #         'ag_current_mcm_key': None, 'ag_current_uploaded_file_obj': None,
# #         'ag_current_uploaded_file_name': None, 'ag_editor_data': pd.DataFrame(columns=DISPLAY_COLUMN_ORDER_EDITOR),
# #         'ag_pdf_dropbox_path': None, 'ag_validation_errors': [],
# #         'ag_uploader_key_suffix': 0, 'ag_deletable_map': {},
# #         'ag_taxpayer_classification': None, 'ag_risk_flags_data': [], 'ag_no_risk_flags': False
# #     }
# #     for key, value in default_ag_states.items():
# #         if key not in st.session_state:
# #             st.session_state[key] = value

# #     with st.sidebar:
# #         try:
# #             st.image("logo.png", width=80)
# #         except Exception:
# #             st.sidebar.markdown("*(Logo)*")
# #         st.markdown(f"**User:** {st.session_state.username}<br>**Group No:** {st.session_state.audit_group_no}", unsafe_allow_html=True)
# #         if st.button("Logout", key="ag_logout", use_container_width=True):
# #             keys_to_clear = list(default_ag_states.keys()) + ['logged_in', 'username', 'role', 'audit_group_no']
# #             for k in keys_to_clear:
# #                 if k in st.session_state: del st.session_state[k]
# #             st.rerun()
# #         st.markdown("---")
# #         if st.button("🚀 Smart Audit Tracker", key="launch_sat_ag"):
# #             st.session_state.app_mode = "smart_audit_tracker"
# #             st.rerun()
# #         st.markdown("---")

# #     selected_tab = option_menu(
# #         menu_title="e-MCM Menu",
# #         options=["Upload DAR for MCM", "View My Uploaded DARs", "Delete My DAR Entries"],
# #         icons=["cloud-upload-fill", "eye-fill", "trash2-fill"], menu_icon="person-workspace",
# #         default_index=0, orientation="horizontal",
# #         styles={
# #             "container": {"padding": "5px !important", "background-color": "#e9ecef"},
# #             "icon": {"color": "#28a745", "font-size": "20px"},
# #             "nav-link": {"font-size": "16px", "text-align": "center", "margin": "0px", "--hover-color": "#d4edda"},
# #             "nav-link-selected": {"background-color": "#28a745", "color": "white"},
# #         })

# #     st.markdown("<div class='card'>", unsafe_allow_html=True)

# #     if selected_tab == "Upload DAR for MCM":
# #         upload_dar_tab(dbx, active_periods, YOUR_GEMINI_API_KEY)
# #     elif selected_tab == "View My Uploaded DARs":
# #         view_uploads_tab(dbx)
# #     elif selected_tab == "Delete My DAR Entries":
# #         delete_entries_tab(dbx)

# #     st.markdown("</div>", unsafe_allow_html=True)


# # def upload_dar_tab(dbx, active_periods, api_key):
# #     st.markdown("<h3>Upload DAR PDF for MCM Period</h3>", unsafe_allow_html=True)
# #     if not active_periods:
# #         st.warning("No active MCM periods available.")
# #         return
# #     period_options_disp_map = {k: f"{v.get('month_name')} {v.get('year')}" for k, v in sorted(active_periods.items(), key=lambda x: x[0], reverse=True)}
# #     period_select_map_rev = {v: k for k, v in period_options_disp_map.items()}
# #     selected_period_str = st.selectbox(
# #         "Select Active MCM Period", options=list(period_select_map_rev.keys()),
# #         key=f"ag_mcm_sel_uploader_{st.session_state.ag_uploader_key_suffix}"
# #     )
# #     if not selected_period_str: return
# #     new_mcm_key = period_select_map_rev[selected_period_str]
# #     if st.session_state.ag_current_mcm_key != new_mcm_key:
# #         st.session_state.ag_current_mcm_key = new_mcm_key
# #         reset_ag_states()
# #         st.session_state.ag_uploader_key_suffix += 1; st.rerun()

# #     mcm_info_current = active_periods[st.session_state.ag_current_mcm_key]
# #     st.info(f"Uploading for: {mcm_info_current['month_name']} {mcm_info_current['year']}")
# #     uploaded_file = st.file_uploader(
# #         "Choose DAR PDF", type="pdf",
# #         key=f"ag_uploader_main_{st.session_state.ag_current_mcm_key}_{st.session_state.ag_uploader_key_suffix}"
# #     )
# #     if uploaded_file and st.session_state.ag_current_uploaded_file_name != uploaded_file.name:
# #         st.session_state.ag_current_uploaded_file_obj = uploaded_file
# #         st.session_state.ag_current_uploaded_file_name = uploaded_file.name
# #         reset_ag_states()
# #         st.rerun()

# #     if st.session_state.ag_current_uploaded_file_obj and st.button("Extract Data", use_container_width=True):
# #         status_area = st.empty()
# #         pdf_bytes = st.session_state.ag_current_uploaded_file_obj.getvalue()
# #         status_area.info("▶️ Step 1/4: Uploading PDF to Dropbox...")
# #         dar_filename_on_dropbox = f"AG{st.session_state.audit_group_no}_{st.session_state.ag_current_uploaded_file_name}"
# #         pdf_dropbox_path = f"{DAR_PDFS_PATH}/{dar_filename_on_dropbox}"
# #         if not upload_file(dbx, pdf_bytes, pdf_dropbox_path):
# #             status_area.error("❌ Step 1/4 Failed: Could not upload PDF to Dropbox.")
# #             st.stop()
# #         st.session_state.ag_pdf_dropbox_path = pdf_dropbox_path
# #         status_area.info("✅ Step 1/4: PDF uploaded. \n\n▶️ Step 2/4: Pre-processing PDF...")
# #         preprocessed_text = preprocess_pdf_text(BytesIO(pdf_bytes))
# #         if preprocessed_text.startswith("Error"):
# #             status_area.error(f"❌ Step 2/4 Failed: {preprocessed_text}")
# #             st.stop()
# #         status_area.info("✅ Step 2/4: PDF pre-processed. \n\n▶️ Step 3/4: Extracting data with AI...")
# #         parsed_data = get_structured_data_from_llm(preprocessed_text)
# #         if parsed_data.parsing_errors:
# #             st.warning(f"AI Parsing Issues: {parsed_data.parsing_errors}")
# #         status_area.info("✅ Step 3/4: AI data extraction complete. \n\n▶️ Step 4/4: Formatting data for review...")
# #         header_dict = parsed_data.header.model_dump() if parsed_data.header else {}
# #         st.session_state.ag_taxpayer_classification = header_dict.get("taxpayer_classification")
# #         extracted_risk_flags = header_dict.get("risk_flags") or []
# #         st.session_state.ag_risk_flags_data = [{"risk_flag": flag, "paras": []} for flag in extracted_risk_flags]

# #         base_info = {"audit_group_number": st.session_state.audit_group_no, "audit_circle_number": calculate_audit_circle(st.session_state.audit_group_no),
# #                      "gstin": header_dict.get("gstin"), "trade_name": header_dict.get("trade_name"), "category": header_dict.get("category"),
# #                      "total_amount_detected_overall_rs": header_dict.get("total_amount_detected_overall_rs"),
# #                      "total_amount_recovered_overall_rs": header_dict.get("total_amount_recovered_overall_rs")}
# #         temp_list_for_df = []
# #         if parsed_data.audit_paras:
# #             for para_obj in parsed_data.audit_paras:
# #                 temp_list_for_df.append({**base_info, **para_obj.model_dump()})
# #         elif base_info.get("trade_name"):
# #             temp_list_for_df.append({**base_info, "audit_para_heading": "N/A - Header Info Only"})
# #         else:
# #             temp_list_for_df.append({**base_info, "audit_para_heading": "Manual Entry Required"})
# #             st.error("AI failed to extract key information.")
# #         df_extracted = pd.DataFrame(temp_list_for_df)
# #         for col in DISPLAY_COLUMN_ORDER_EDITOR:
# #             if col not in df_extracted.columns: df_extracted[col] = None
# #         st.session_state.ag_editor_data = df_extracted[DISPLAY_COLUMN_ORDER_EDITOR]
# #         status_area.success("✅ Step 4/4: Formatting complete. Data is ready for review below.")
# #         time.sleep(2)
# #         st.rerun()

# #     if not st.session_state.ag_editor_data.empty:
# #         st.markdown("<h4>Review and Edit Extracted Data:</h4>", unsafe_allow_html=True)

# #         # --- Taxpayer Classification Dropdown ---
# #         st.selectbox(
# #             "Taxpayer Classification",
# #             options=[None] + TAXPAYER_CLASSIFICATION_OPTIONS,
# #             index=(TAXPAYER_CLASSIFICATION_OPTIONS.index(st.session_state.ag_taxpayer_classification) + 1) if st.session_state.ag_taxpayer_classification in TAXPAYER_CLASSIFICATION_OPTIONS else 0,
# #             key='ag_taxpayer_classification'
# #         )

# #         col_conf = { "audit_group_number": st.column_config.NumberColumn("Group No.", disabled=True), "audit_circle_number": st.column_config.NumberColumn("Circle No.", disabled=True),
# #                      "gstin": st.column_config.TextColumn("GSTIN", width="medium"), "trade_name": st.column_config.TextColumn("Trade Name", width="large"),
# #                      "category": st.column_config.SelectboxColumn("Category", options=[None] + VALID_CATEGORIES, width="small"),
# #                      "total_amount_detected_overall_rs": st.column_config.NumberColumn("Total Detect (₹)", format="%.2f"),
# #                      "total_amount_recovered_overall_rs": st.column_config.NumberColumn("Total Recover (₹)", format="%.2f"),
# #                      "audit_para_number": st.column_config.NumberColumn("Para No.", format="%d", width="small"),
# #                      "audit_para_heading": st.column_config.TextColumn("Para Heading", width="xlarge"),
# #                      "revenue_involved_rs": st.column_config.NumberColumn("Revenue Involved (₹)", format="%.2f"),
# #                      "revenue_recovered_rs": st.column_config.NumberColumn("Revenue Recovered (₹)", format="%.2f"),
# #                      "status_of_para": st.column_config.SelectboxColumn("Para Status", options=[None] + VALID_PARA_STATUSES, width="medium") }
# #         editor_key = f"data_editor_{st.session_state.ag_current_mcm_key}_{st.session_state.ag_current_uploaded_file_name or 'no_file'}"
# #         edited_df = st.data_editor(st.session_state.ag_editor_data, column_config=col_conf, num_rows="dynamic", key=editor_key,
# #                                    use_container_width=True, hide_index=True, height=min(len(st.session_state.ag_editor_data) * 45 + 70, 450))

# #         st.markdown("<hr>", unsafe_allow_html=True)
# #         st.markdown("<h4>Manage Risk Flags:</h4>", unsafe_allow_html=True)
# #         st.checkbox("No risk flags available for this Taxpayer", key='ag_no_risk_flags')

# #         if not st.session_state.ag_no_risk_flags:
# #             # CORRECTED LINE:
# #             valid_para_numbers = pd.to_numeric(pd.DataFrame(edited_df)['audit_para_number'], errors='coerce').dropna().astype(int).unique().tolist()
            
# #             risk_container = st.container()
# #             with risk_container:
# #                 for i, risk_item in enumerate(st.session_state.ag_risk_flags_data):
# #                     cols = st.columns([2, 5, 4, 1])
# #                     with cols[0]:
# #                         st.text(risk_item['risk_flag'])
# #                     with cols[1]:
# #                         st.caption(GST_RISK_PARAMETERS.get(risk_item['risk_flag'], "Unknown Description"))
# #                     with cols[2]:
# #                         selected_paras = st.multiselect(
# #                             "Link to Para(s)", options=valid_para_numbers, default=risk_item['paras'],
# #                             key=f"risk_{i}_paras", label_visibility="collapsed"
# #                         )
# #                         st.session_state.ag_risk_flags_data[i]['paras'] = selected_paras
# #                     with cols[3]:
# #                         if st.button("🗑️", key=f"del_risk_{i}", help="Remove this risk flag"):
# #                             st.session_state.ag_risk_flags_data.pop(i)
# #                             st.rerun()

# #                 st.markdown("---")
# #                 add_cols = st.columns([3, 1])
# #                 with add_cols[0]:
# #                     new_risk_flag = st.selectbox("Add new risk flag:", options=[""] + list(GST_RISK_PARAMETERS.keys()), key="new_risk_flag_select")
# #                 with add_cols[1]:
# #                     st.markdown("<br>", unsafe_allow_html=True)
# #                     if st.button("Add Flag", use_container_width=True):
# #                         if new_risk_flag and not any(d['risk_flag'] == new_risk_flag for d in st.session_state.ag_risk_flags_data):
# #                             st.session_state.ag_risk_flags_data.append({"risk_flag": new_risk_flag, "paras": []})
# #                             st.rerun()
# #                         elif not new_risk_flag:
# #                             st.warning("Please select a risk flag to add.")
# #                         else:
# #                             st.warning(f"Risk flag '{new_risk_flag}' is already in the list.")

# # def view_uploads_tab(dbx):
# #     """Renders the 'View My Uploaded DARs' tab using Streamlit's native st.dataframe."""
# #     st.markdown("<h3>My Uploaded DARs</h3>", unsafe_allow_html=True)
    
# #     all_periods = read_from_spreadsheet(dbx, MCM_PERIODS_INFO_PATH)
# #     if all_periods.empty:
# #         st.warning("Could not load period information.")
# #         return
        
# #     period_options_map = {f"{row['month_name']} {row['year']}": f"{row['month_name']} {row['year']}" for _, row in all_periods.iterrows()}
# #     selected_period = st.selectbox("Select MCM Period to View", options=list(period_options_map.keys()))

# #     if not selected_period: return

# #     with st.spinner("Loading your uploaded reports..."):
# #         df_all_data = read_from_spreadsheet(dbx, MCM_DATA_PATH)
# #         if df_all_data.empty:
# #             st.info("No reports have been submitted for any period yet.")
# #             return

# #         df_all_data['audit_group_number'] = pd.to_numeric(df_all_data['audit_group_number'], errors='coerce')
# #         my_uploads = df_all_data[(df_all_data['audit_group_number'] == st.session_state.audit_group_no) & (df_all_data['mcm_period'] == selected_period)].copy()

# #         if my_uploads.empty:
# #             st.info(f"You have not submitted any reports for {selected_period}.")
# #             return
        
# #         st.markdown(f"<h4>Your Uploads for {selected_period}:</h4>", unsafe_allow_html=True)
        
# #         @st.cache_data(ttl=600)
# #         def get_link(_dbx, path):
# #             return get_shareable_link(_dbx, path)

# #         if 'dar_pdf_path' in my_uploads.columns:
# #             my_uploads['pdf_url'] = my_uploads['dar_pdf_path'].apply(
# #                 lambda path: get_link(dbx, path) if pd.notna(path) else None
# #             )
        
# #         cols_to_show = [
# #             "gstin", "trade_name", "taxpayer_classification", "audit_para_number", "audit_para_heading",
# #             "para_classification_code", "status_of_para", "revenue_involved_rs",
# #             "revenue_recovered_rs", "record_created_date", "pdf_url"
# #         ]
        
# #         df_to_display = my_uploads[[col for col in cols_to_show if col in my_uploads.columns]].copy()

# #         st.dataframe(
# #             df_to_display,
# #             column_config={
# #                 "gstin": st.column_config.TextColumn("GSTIN", width="medium"),
# #                 "trade_name": st.column_config.TextColumn("Trade Name", width="large"),
# #                 "taxpayer_classification": st.column_config.TextColumn("Taxpayer Class"),
# #                 "audit_para_number": st.column_config.NumberColumn("Para No.", format="%d"),
# #                 "audit_para_heading": st.column_config.TextColumn("Para Heading", width="xlarge"),
# #                 "para_classification_code": st.column_config.TextColumn("Para Class Code"),
# #                 "status_of_para": st.column_config.TextColumn("Status"),
# #                 "revenue_involved_rs": st.column_config.NumberColumn("Revenue Involved (₹)", format="%.2f"),
# #                 "revenue_recovered_rs": st.column_config.NumberColumn("Revenue Recovered (₹)", format="%.2f"),
# #                 "record_created_date": st.column_config.DatetimeColumn("Created Date", format="YYYY-MM-DD HH:mm:ss"),
# #                 "pdf_url": st.column_config.LinkColumn(
# #                     "View PDF",
# #                     help="Click to view the uploaded DAR PDF",
# #                     display_text="📄 View PDF"
# #                 )
# #             },
# #             hide_index=True,
# #             use_container_width=True
# #         )

# #         # Display Risk Flags in an expander
# #         risk_data_json = my_uploads['risk_flags_data'].dropna().iloc[0] if 'risk_flags_data' in my_uploads.columns and not my_uploads['risk_flags_data'].dropna().empty else None
# #         if risk_data_json:
# #             with st.expander("View Associated Risk Flags"):
# #                 try:
# #                     risk_data_list = json.loads(risk_data_json)
# #                     if risk_data_list:
# #                         for risk_item in risk_data_list:
# #                             st.markdown(f"**{risk_item['risk_flag']}**: {GST_RISK_PARAMETERS.get(risk_item['risk_flag'])}")
# #                             st.caption(f"Linked to Para(s): {', '.join(map(str, risk_item['paras'])) if risk_item['paras'] else 'None'}")
# #                     else:
# #                         st.info("No risk flags were recorded for this entry.")
# #                 except json.JSONDecodeError:
# #                     st.warning("Could not parse the stored risk flag data.")


# # def delete_entries_tab(dbx):
# #     """Renders the 'Delete My DAR Entries' tab with fixed logic."""
# #     st.markdown("<h3>Delete My Uploaded DAR Entries</h3>", unsafe_allow_html=True)
# #     st.error("⚠️ **Warning:** This action is permanent and cannot be undone.")
# #     all_periods = read_from_spreadsheet(dbx, MCM_PERIODS_INFO_PATH)
# #     if all_periods.empty:
# #         st.warning("Could not load period information.")
# #         return
# #     period_options_map = {f"{row['month_name']} {row['year']}": f"{row['month_name']} {row['year']}" for _, row in all_periods.iterrows()}
# #     selected_period = st.selectbox("Select MCM Period to Manage", options=list(period_options_map.keys()))
# #     if not selected_period: return
# #     master_df = read_from_spreadsheet(dbx, MCM_DATA_PATH)
# #     if master_df.empty:
# #         st.info("Master data file is empty. Nothing to delete.")
# #         return
# #     master_df['original_index'] = master_df.index
# #     master_df['audit_group_number'] = pd.to_numeric(master_df['audit_group_number'], errors='coerce')
# #     my_entries = master_df[(master_df['audit_group_number'] == st.session_state.audit_group_no) & (master_df['mcm_period'] == selected_period)].copy()
# #     if my_entries.empty:
# #         st.info(f"You have no entries in {selected_period} to delete.")
# #         return
# #     my_entries['delete_label'] = (
# #         "TN: " + my_entries['trade_name'].astype(str).str.slice(0, 25) + "... | " +
# #         "Para: " + my_entries['audit_para_number'].astype(str) + " | " +
# #         "Date: " + my_entries['record_created_date'].astype(str)
# #     )
# #     deletable_map = my_entries.set_index('delete_label')['original_index'].to_dict()
# #     options = ["--Select an entry--"] + list(deletable_map.keys())
# #     selected_label = st.selectbox("Select Entry to Delete:", options=options)
# #     if selected_label != "--Select an entry--":
# #         index_to_delete = deletable_map.get(selected_label)
# #         if index_to_delete is not None:
# #             details = master_df.loc[index_to_delete]
# #             st.warning(f"Confirm Deletion: **{details['trade_name']}**, Para: **{details['audit_para_number']}**")
# #             with st.form(key=f"delete_form_{index_to_delete}"):
# #                 password = st.text_input("Enter your password to confirm:", type="password")
# #                 if st.form_submit_button("Yes, Delete This Entry", type="primary"):
# #                     if password == USER_CREDENTIALS.get(st.session_state.username):
# #                         with st.spinner("Deleting entry..."):
# #                             df_after_delete = master_df.drop(index=index_to_delete).drop(columns=['original_index'])
# #                             if update_spreadsheet_from_df(dbx, df_after_delete, MCM_DATA_PATH):
# #                                 st.success("Entry deleted successfully!")
# #                                 time.sleep(1)
# #                                 st.rerun()
# #                             else:
# #                                 st.error("Failed to update the data file on Dropbox.")
# #                     else:
# #                         st.error("Incorrect password.")
# #                         # # ui_audit_group.py
# # # import streamlit as st
# # # import pandas as pd
# # # import datetime
# # # import math
# # # from io import BytesIO
# # # import time
# # # from streamlit_option_menu import option_menu
# # # import html

# # # # --- Custom Module Imports for Dropbox Version ---
# # # from dropbox_utils import (
# # #     read_from_spreadsheet,
# # #     update_spreadsheet_from_df,
# # #     upload_file,
# # #     get_shareable_link 
# # # )
# # # from dar_processor import preprocess_pdf_text, get_structured_data_with_gemini, get_structured_data_from_llm
# # # from validation_utils import validate_data_for_sheet, VALID_CATEGORIES, VALID_PARA_STATUSES
# # # from config import (
# # #     USER_CREDENTIALS,
# # #     MCM_PERIODS_INFO_PATH,
# # #     MCM_DATA_PATH,
# # #     DAR_PDFS_PATH
# # # )
# # # from models import ParsedDARReport

# # # # --- Constants and Configuration ---
# # # SHEET_DATA_COLUMNS_ORDER = [
# # #     "mcm_period", "audit_group_number", "audit_circle_number", "gstin", "trade_name",
# # #     "category", "total_amount_detected_overall_rs", "total_amount_recovered_overall_rs",
# # #     "audit_para_number", "audit_para_heading", "revenue_involved_lakhs_rs",
# # #     "revenue_recovered_lakhs_rs", "status_of_para", "dar_pdf_path", "record_created_date"
# # # ]

# # # DISPLAY_COLUMN_ORDER_EDITOR = [
# # #     "audit_group_number", "audit_circle_number", "gstin", "trade_name", "category",
# # #     "total_amount_detected_overall_rs", "total_amount_recovered_overall_rs",
# # #     "audit_para_number", "audit_para_heading", "revenue_involved_lakhs_rs",
# # #     "revenue_recovered_lakhs_rs", "status_of_para"
# # # ]

# # # # --- Helper Functions ---

# # # def calculate_audit_circle(audit_group_number_val):
# # #     """Calculates the audit circle based on the audit group number."""
# # #     try:
# # #         agn = int(audit_group_number_val)
# # #         if 1 <= agn <= 30:
# # #             return math.ceil(agn / 3.0)
# # #         return None
# # #     except (ValueError, TypeError, AttributeError):
# # #         return None

# # # @st.cache_data(ttl=120)
# # # def get_active_mcm_periods(_dbx):
# # #     """
# # #     Reads MCM periods from Dropbox, converts to a dictionary,
# # #     and returns only the active ones. Caches the result.
# # #     """
# # #     df_periods = read_from_spreadsheet(_dbx, MCM_PERIODS_INFO_PATH)
# # #     if df_periods.empty:
# # #         return {}
    
# # #     if 'month_name' not in df_periods.columns or 'year' not in df_periods.columns:
# # #         st.error("The 'mcm_periods_info.xlsx' file is missing 'month_name' or 'year' columns.")
# # #         return {}

# # #     df_periods['key'] = df_periods['month_name'].astype(str) + "_" + df_periods['year'].astype(str)
# # #     df_periods.drop_duplicates(subset=['key'], keep='last', inplace=True)
    
# # #     all_periods = df_periods.set_index('key').to_dict('index')
# # #     active_periods = {k: v for k, v in all_periods.items() if v.get("active")}
# # #     return active_periods

# # # # --- Main Dashboard Function ---

# # # def audit_group_dashboard(dbx):
# # #     st.markdown(f"<div class='sub-header'>Audit Group {st.session_state.audit_group_no} Dashboard</div>", unsafe_allow_html=True)

# # #     YOUR_GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", "")
# # #     if not YOUR_GEMINI_API_KEY:
# # #         st.error("Gemini API Key is not configured. Please contact the administrator.")
# # #         st.stop()

# # #     active_periods = get_active_mcm_periods(dbx)

# # #     default_ag_states = {
# # #         'ag_current_mcm_key': None, 'ag_current_uploaded_file_obj': None,
# # #         'ag_current_uploaded_file_name': None, 'ag_editor_data': pd.DataFrame(columns=DISPLAY_COLUMN_ORDER_EDITOR),
# # #         'ag_pdf_dropbox_path': None, 'ag_validation_errors': [],
# # #         'ag_uploader_key_suffix': 0, 'ag_deletable_map': {}
# # #     }
# # #     for key, value in default_ag_states.items():
# # #         if key not in st.session_state:
# # #             st.session_state[key] = value

# # #     with st.sidebar:
# # #         try:
# # #             st.image("logo.png", width=80)
# # #         except Exception:
# # #             st.sidebar.markdown("*(Logo)*")
# # #         st.markdown(f"**User:** {st.session_state.username}<br>**Group No:** {st.session_state.audit_group_no}", unsafe_allow_html=True)
# # #         if st.button("Logout", key="ag_logout", use_container_width=True):
# # #             keys_to_clear = list(default_ag_states.keys()) + ['logged_in', 'username', 'role', 'audit_group_no']
# # #             for k in keys_to_clear:
# # #                 if k in st.session_state: del st.session_state[k]
# # #             st.rerun()
# # #         st.markdown("---")
# # #         if st.button("🚀 Smart Audit Tracker", key="launch_sat_ag"):
# # #             st.session_state.app_mode = "smart_audit_tracker"
# # #             st.rerun()
# # #         st.markdown("---")

# # #     selected_tab = option_menu(
# # #         menu_title="e-MCM Menu",
# # #         options=["Upload DAR for MCM", "View My Uploaded DARs", "Delete My DAR Entries"],
# # #         icons=["cloud-upload-fill", "eye-fill", "trash2-fill"], menu_icon="person-workspace",
# # #         default_index=0, orientation="horizontal",
# # #         styles={
# # #             "container": {"padding": "5px !important", "background-color": "#e9ecef"},
# # #             "icon": {"color": "#28a745", "font-size": "20px"},
# # #             "nav-link": {"font-size": "16px", "text-align": "center", "margin": "0px", "--hover-color": "#d4edda"},
# # #             "nav-link-selected": {"background-color": "#28a745", "color": "white"},
# # #         })

# # #     st.markdown("<div class='card'>", unsafe_allow_html=True)

# # #     if selected_tab == "Upload DAR for MCM":
# # #         upload_dar_tab(dbx, active_periods, YOUR_GEMINI_API_KEY)
# # #     elif selected_tab == "View My Uploaded DARs":
# # #         view_uploads_tab(dbx)
# # #     elif selected_tab == "Delete My DAR Entries":
# # #         delete_entries_tab(dbx)

# # #     st.markdown("</div>", unsafe_allow_html=True)


# # # def upload_dar_tab(dbx, active_periods, api_key):
# # #     # This function remains unchanged
# # #     st.markdown("<h3>Upload DAR PDF for MCM Period</h3>", unsafe_allow_html=True)
# # #     if not active_periods:
# # #         st.warning("No active MCM periods available.")
# # #         return
# # #     period_options_disp_map = {k: f"{v.get('month_name')} {v.get('year')}" for k, v in sorted(active_periods.items(), key=lambda x: x[0], reverse=True)}
# # #     period_select_map_rev = {v: k for k, v in period_options_disp_map.items()}
# # #     selected_period_str = st.selectbox(
# # #         "Select Active MCM Period", options=list(period_select_map_rev.keys()),
# # #         key=f"ag_mcm_sel_uploader_{st.session_state.ag_uploader_key_suffix}"
# # #     )
# # #     if not selected_period_str: return
# # #     new_mcm_key = period_select_map_rev[selected_period_str]
# # #     if st.session_state.ag_current_mcm_key != new_mcm_key:
# # #         st.session_state.ag_current_mcm_key = new_mcm_key
# # #         st.session_state.ag_current_uploaded_file_obj = None; st.session_state.ag_current_uploaded_file_name = None
# # #         st.session_state.ag_editor_data = pd.DataFrame(columns=DISPLAY_COLUMN_ORDER_EDITOR)
# # #         st.session_state.ag_pdf_dropbox_path = None; st.session_state.ag_validation_errors = []
# # #         st.session_state.ag_uploader_key_suffix += 1; st.rerun()
# # #     mcm_info_current = active_periods[st.session_state.ag_current_mcm_key]
# # #     st.info(f"Uploading for: {mcm_info_current['month_name']} {mcm_info_current['year']}")
# # #     uploaded_file = st.file_uploader(
# # #         "Choose DAR PDF", type="pdf",
# # #         key=f"ag_uploader_main_{st.session_state.ag_current_mcm_key}_{st.session_state.ag_uploader_key_suffix}"
# # #     )
# # #     if uploaded_file and st.session_state.ag_current_uploaded_file_name != uploaded_file.name:
# # #         st.session_state.ag_current_uploaded_file_obj = uploaded_file
# # #         st.session_state.ag_current_uploaded_file_name = uploaded_file.name
# # #         st.session_state.ag_editor_data = pd.DataFrame(columns=DISPLAY_COLUMN_ORDER_EDITOR)
# # #         st.session_state.ag_pdf_dropbox_path = None; st.session_state.ag_validation_errors = []
# # #         st.rerun()
# # #     if st.session_state.ag_current_uploaded_file_obj and st.button("Extract Data", use_container_width=True):
# # #         status_area = st.empty()
# # #         pdf_bytes = st.session_state.ag_current_uploaded_file_obj.getvalue()
# # #         status_area.info("▶️ Step 1/4: Uploading PDF to Dropbox...")
# # #         dar_filename_on_dropbox = f"AG{st.session_state.audit_group_no}_{st.session_state.ag_current_uploaded_file_name}"
# # #         pdf_dropbox_path = f"{DAR_PDFS_PATH}/{dar_filename_on_dropbox}"
# # #         if not upload_file(dbx, pdf_bytes, pdf_dropbox_path):
# # #             status_area.error("❌ Step 1/4 Failed: Could not upload PDF to Dropbox.")
# # #             st.stop()
# # #         st.session_state.ag_pdf_dropbox_path = pdf_dropbox_path
# # #         status_area.info("✅ Step 1/4: PDF uploaded. \n\n▶️ Step 2/4: Pre-processing PDF...")
# # #         preprocessed_text = preprocess_pdf_text(BytesIO(pdf_bytes))
# # #         if preprocessed_text.startswith("Error"):
# # #             status_area.error(f"❌ Step 2/4 Failed: {preprocessed_text}")
# # #             st.stop()
# # #         status_area.info("✅ Step 2/4: PDF pre-processed. \n\n▶️ Step 3/4: Extracting data with AI...")
# # #         parsed_data = get_structured_data_from_llm(preprocessed_text)
# # #         if parsed_data.parsing_errors:
# # #             st.warning(f"AI Parsing Issues: {parsed_data.parsing_errors}")
# # #         status_area.info("✅ Step 3/4: AI data extraction complete. \n\n▶️ Step 4/4: Formatting data for review...")
# # #         header_dict = parsed_data.header.model_dump() if parsed_data.header else {}
# # #         base_info = {"audit_group_number": st.session_state.audit_group_no, "audit_circle_number": calculate_audit_circle(st.session_state.audit_group_no),
# # #                      "gstin": header_dict.get("gstin"), "trade_name": header_dict.get("trade_name"), "category": header_dict.get("category"),
# # #                      "total_amount_detected_overall_rs": header_dict.get("total_amount_detected_overall_rs"),
# # #                      "total_amount_recovered_overall_rs": header_dict.get("total_amount_recovered_overall_rs")}
# # #         temp_list_for_df = []
# # #         if parsed_data.audit_paras:
# # #             for para_obj in parsed_data.audit_paras:
# # #                 temp_list_for_df.append({**base_info, **para_obj.model_dump()})
# # #         elif base_info.get("trade_name"):
# # #             temp_list_for_df.append({**base_info, "audit_para_heading": "N/A - Header Info Only"})
# # #         else:
# # #             temp_list_for_df.append({**base_info, "audit_para_heading": "Manual Entry Required"})
# # #             st.error("AI failed to extract key information.")
# # #         df_extracted = pd.DataFrame(temp_list_for_df)
# # #         for col in DISPLAY_COLUMN_ORDER_EDITOR:
# # #             if col not in df_extracted.columns: df_extracted[col] = None
# # #         st.session_state.ag_editor_data = df_extracted[DISPLAY_COLUMN_ORDER_EDITOR]
# # #         status_area.success("✅ Step 4/4: Formatting complete. Data is ready for review below.")
# # #         time.sleep(2)
# # #         st.rerun()
# # #     if not st.session_state.ag_editor_data.empty:
# # #         st.markdown("<h4>Review and Edit Extracted Data:</h4>", unsafe_allow_html=True)
# # #         col_conf = { "audit_group_number": st.column_config.NumberColumn("Group No.", disabled=True), "audit_circle_number": st.column_config.NumberColumn("Circle No.", disabled=True),
# # #                      "gstin": st.column_config.TextColumn("GSTIN", width="medium"), "trade_name": st.column_config.TextColumn("Trade Name", width="large"),
# # #                      "category": st.column_config.SelectboxColumn("Category", options=[None] + VALID_CATEGORIES, width="small"),
# # #                      "total_amount_detected_overall_rs": st.column_config.NumberColumn("Total Detect (₹)", format="%.2f"),
# # #                      "total_amount_recovered_overall_rs": st.column_config.NumberColumn("Total Recover (₹)", format="%.2f"),
# # #                      "audit_para_number": st.column_config.NumberColumn("Para No.", format="%d", width="small"),
# # #                      "audit_para_heading": st.column_config.TextColumn("Para Heading", width="xlarge"),
# # #                      "revenue_involved_lakhs_rs": st.column_config.NumberColumn("Rev. Involved (₹)", format="%.2f"),
# # #                      "revenue_recovered_lakhs_rs": st.column_config.NumberColumn("Rev. Recovered (₹)", format="%.2f"),
# # #                      "status_of_para": st.column_config.SelectboxColumn("Para Status", options=[None] + VALID_PARA_STATUSES, width="medium") }
# # #         editor_key = f"data_editor_{st.session_state.ag_current_mcm_key}_{st.session_state.ag_current_uploaded_file_name or 'no_file'}"
# # #         edited_df = st.data_editor(st.session_state.ag_editor_data, column_config=col_conf, num_rows="dynamic", key=editor_key,
# # #                                    use_container_width=True, hide_index=True, height=min(len(st.session_state.ag_editor_data) * 45 + 70, 450))
# # #         if st.button("Submit to MCM Sheet", use_container_width=True):
# # #             submit_status_area = st.empty()
# # #             submit_status_area.info("▶️ Step 1/4: Cleaning and validating data...")
# # #             df_to_submit = pd.DataFrame(edited_df).dropna(how='all').reset_index(drop=True)
# # #             if df_to_submit.empty:
# # #                 submit_status_area.error("❌ Submission Failed: No data found in the editor.")
# # #                 return
# # #             validation_errors = validate_data_for_sheet(df_to_submit)
# # #             if validation_errors:
# # #                 submit_status_area.empty()
# # #                 st.error("Validation Failed! Please correct the following errors:")
# # #                 for err in validation_errors: st.warning(f"- {err}")
# # #                 return
# # #             submit_status_area.info("✅ Step 1/4: Validation successful. \n\n▶️ Step 2/4: Reading master data file...")
# # #             master_df = read_from_spreadsheet(dbx, MCM_DATA_PATH)
# # #             submit_status_area.info("✅ Step 2/4: Master file read. \n\n▶️ Step 3/4: Preparing final data...")
# # #             df_to_submit['mcm_period'] = selected_period_str
# # #             df_to_submit['dar_pdf_path'] = st.session_state.ag_pdf_dropbox_path
# # #             df_to_submit['record_created_date'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
# # #             for col in SHEET_DATA_COLUMNS_ORDER:
# # #                 if col not in master_df.columns: master_df[col] = pd.NA
# # #                 if col not in df_to_submit.columns: df_to_submit[col] = pd.NA
# # #             submit_status_area.info("✅ Step 3/4: Data prepared. \n\n▶️ Step 4/4: Saving updated data to Dropbox...")
# # #             final_df = pd.concat([master_df, df_to_submit[SHEET_DATA_COLUMNS_ORDER]], ignore_index=True)
# # #             if update_spreadsheet_from_df(dbx, final_df, MCM_DATA_PATH):
# # #                 submit_status_area.success("✅ Submission complete! Data saved successfully.")
# # #                 st.balloons()
# # #                 time.sleep(2)
# # #                 st.session_state.ag_current_uploaded_file_obj = None; st.session_state.ag_current_uploaded_file_name = None
# # #                 st.session_state.ag_editor_data = pd.DataFrame(columns=DISPLAY_COLUMN_ORDER_EDITOR)
# # #                 st.session_state.ag_pdf_dropbox_path = None; st.session_state.ag_validation_errors = []
# # #                 st.session_state.ag_uploader_key_suffix += 1; st.rerun()
# # #             else:
# # #                 st.error("❌ Step 4/4 Failed: Could not save updated data to Dropbox.")

# # # def view_uploads_tab(dbx):
# # #     """Renders the 'View My Uploaded DARs' tab using Streamlit's native st.dataframe."""
# # #     st.markdown("<h3>My Uploaded DARs</h3>", unsafe_allow_html=True)
    
# # #     all_periods = read_from_spreadsheet(dbx, MCM_PERIODS_INFO_PATH)
# # #     if all_periods.empty:
# # #         st.warning("Could not load period information.")
# # #         return
        
# # #     period_options_map = {f"{row['month_name']} {row['year']}": f"{row['month_name']} {row['year']}" for _, row in all_periods.iterrows()}
# # #     selected_period = st.selectbox("Select MCM Period to View", options=list(period_options_map.keys()))

# # #     if not selected_period: return

# # #     with st.spinner("Loading your uploaded reports..."):
# # #         df_all_data = read_from_spreadsheet(dbx, MCM_DATA_PATH)
# # #         if df_all_data.empty:
# # #             st.info("No reports have been submitted for any period yet.")
# # #             return

# # #         df_all_data['audit_group_number'] = pd.to_numeric(df_all_data['audit_group_number'], errors='coerce')
# # #         my_uploads = df_all_data[(df_all_data['audit_group_number'] == st.session_state.audit_group_no) & (df_all_data['mcm_period'] == selected_period)].copy()

# # #         if my_uploads.empty:
# # #             st.info(f"You have not submitted any reports for {selected_period}.")
# # #             return
        
# # #         st.markdown(f"<h4>Your Uploads for {selected_period}:</h4>", unsafe_allow_html=True)
        
# # #         @st.cache_data(ttl=600)
# # #         def get_link(_dbx, path):
# # #             return get_shareable_link(_dbx, path)

# # #         if 'dar_pdf_path' in my_uploads.columns:
# # #             my_uploads['pdf_url'] = my_uploads['dar_pdf_path'].apply(
# # #                 lambda path: get_link(dbx, path) if pd.notna(path) else None
# # #             )
        
# # #         cols_to_show = [
# # #             "gstin", "trade_name", "audit_para_number", "audit_para_heading", 
# # #             "status_of_para", "revenue_involved_lakhs_rs", "revenue_recovered_lakhs_rs", 
# # #             "record_created_date", "pdf_url"
# # #         ]
        
# # #         df_to_display = my_uploads[[col for col in cols_to_show if col in my_uploads.columns]].copy()

# # #         st.dataframe(
# # #             df_to_display,
# # #             column_config={
# # #                 "gstin": st.column_config.TextColumn("GSTIN", width="medium"),
# # #                 "trade_name": st.column_config.TextColumn("Trade Name", width="large"),
# # #                 "audit_para_number": st.column_config.NumberColumn("Para No.", format="%d"),
# # #                 "audit_para_heading": st.column_config.TextColumn("Para Heading", width="xlarge"),
# # #                 "status_of_para": st.column_config.TextColumn("Status"),
# # #                 "revenue_involved_lakhs_rs": st.column_config.NumberColumn("Revenue Involved (₹)", format="%.2f"),
# # #                 "revenue_recovered_lakhs_rs": st.column_config.NumberColumn("Revenue Recovered (₹)", format="%.2f"),
# # #                 "record_created_date": st.column_config.DatetimeColumn("Created Date", format="YYYY-MM-DD HH:mm:ss"),
# # #                 "pdf_url": st.column_config.LinkColumn(
# # #                     "View PDF",
# # #                     help="Click to view the uploaded DAR PDF",
# # #                     display_text="📄 View PDF"
# # #                 )
# # #             },
# # #             hide_index=True,
# # #             use_container_width=True
# # #         )


# # # def delete_entries_tab(dbx):
# # #     """Renders the 'Delete My DAR Entries' tab with fixed logic."""
# # #     # This function remains unchanged
# # #     st.markdown("<h3>Delete My Uploaded DAR Entries</h3>", unsafe_allow_html=True)
# # #     st.error("⚠️ **Warning:** This action is permanent and cannot be undone.")
# # #     all_periods = read_from_spreadsheet(dbx, MCM_PERIODS_INFO_PATH)
# # #     if all_periods.empty:
# # #         st.warning("Could not load period information.")
# # #         return
# # #     period_options_map = {f"{row['month_name']} {row['year']}": f"{row['month_name']} {row['year']}" for _, row in all_periods.iterrows()}
# # #     selected_period = st.selectbox("Select MCM Period to Manage", options=list(period_options_map.keys()))
# # #     if not selected_period: return
# # #     master_df = read_from_spreadsheet(dbx, MCM_DATA_PATH)
# # #     if master_df.empty:
# # #         st.info("Master data file is empty. Nothing to delete.")
# # #         return
# # #     master_df['original_index'] = master_df.index
# # #     master_df['audit_group_number'] = pd.to_numeric(master_df['audit_group_number'], errors='coerce')
# # #     my_entries = master_df[(master_df['audit_group_number'] == st.session_state.audit_group_no) & (master_df['mcm_period'] == selected_period)].copy()
# # #     if my_entries.empty:
# # #         st.info(f"You have no entries in {selected_period} to delete.")
# # #         return
# # #     my_entries['delete_label'] = (
# # #         "TN: " + my_entries['trade_name'].astype(str).str.slice(0, 25) + "... | " +
# # #         "Para: " + my_entries['audit_para_number'].astype(str) + " | " +
# # #         "Date: " + my_entries['record_created_date'].astype(str)
# # #     )
# # #     deletable_map = my_entries.set_index('delete_label')['original_index'].to_dict()
# # #     options = ["--Select an entry--"] + list(deletable_map.keys())
# # #     selected_label = st.selectbox("Select Entry to Delete:", options=options)
# # #     if selected_label != "--Select an entry--":
# # #         index_to_delete = deletable_map.get(selected_label)
# # #         if index_to_delete is not None:
# # #             details = master_df.loc[index_to_delete]
# # #             st.warning(f"Confirm Deletion: **{details['trade_name']}**, Para: **{details['audit_para_number']}**")
# # #             with st.form(key=f"delete_form_{index_to_delete}"):
# # #                 password = st.text_input("Enter your password to confirm:", type="password")
# # #                 if st.form_submit_button("Yes, Delete This Entry", type="primary"):
# # #                     if password == USER_CREDENTIALS.get(st.session_state.username):
# # #                         with st.spinner("Deleting entry..."):
# # #                             df_after_delete = master_df.drop(index=index_to_delete).drop(columns=['original_index'])
# # #                             if update_spreadsheet_from_df(dbx, df_after_delete, MCM_DATA_PATH):
# # #                                 st.success("Entry deleted successfully!")
# # #                                 time.sleep(1)
# # #                                 st.rerun()
# # #                             else:
# # #                                 st.error("Failed to update the data file on Dropbox.")
# # #                     else:
# # #                         st.error("Incorrect password.")
