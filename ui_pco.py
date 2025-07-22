import streamlit as st
import datetime
import time
import pandas as pd
import plotly.express as px
from streamlit_option_menu import option_menu

# Dropbox-based imports
from dropbox_utils import read_from_spreadsheet, update_spreadsheet_from_df
from config import MCM_PERIODS_INFO_PATH, MCM_DATA_PATH

# Import tab modules
from ui_mcm_agenda import mcm_agenda_tab
from ui_pco_reports import pco_reports_dashboard

def pco_dashboard(dbx):
    st.markdown("<div class='sub-header'>Planning & Coordination Officer Dashboard</div>", unsafe_allow_html=True)

    with st.sidebar:
        try:
            st.image("logo.png", width=80)
        except Exception:
            st.sidebar.markdown("*(Logo)*")
        
        st.markdown(f"**User:** {st.session_state.username}")
        st.markdown(f"**Role:** {st.session_state.role}")
        
        if st.button("Logout", key="pco_logout", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.username = ""
            st.session_state.role = ""
            # Clear session state keys
            keys_to_clear = ['period_to_delete', 'show_delete_confirm', 'num_paras_to_show_pco']
            for key in keys_to_clear:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()
        
        st.markdown("---")
        
        # Smart Audit Tracker Button with styling
        st.markdown("""
            <style>
            .stButton>button {
                background-image: linear-gradient(to right, #FF512F 0%, #DD2476  51%, #FF512F  100%);
                color: white;
                padding: 15px 30px;
                text-align: center;
                text-transform: uppercase;
                transition: 0.5s;
                background-size: 200% auto;
                border: none;
                border-radius: 10px;
                display: block;
                font-weight: bold;
                width: 100%;
            }
            .stButton>button:hover {
                background-position: right center;
                color: #fff;
                text-decoration: none;
            }
            </style>
        """, unsafe_allow_html=True)
        
        if st.button("🚀 Smart Audit Tracker", key="launch_sat_pco"):
            st.session_state.app_mode = "smart_audit_tracker"
            st.rerun()
        st.markdown("---")
    
    # Navigation menu
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
       # ========================== CREATE MCM PERIOD TAB ==========================
    if selected_tab == "Create MCM Period":
        st.markdown("<h3>Create New MCM Period</h3>", unsafe_allow_html=True)
        
        with st.form("create_period_form"):
            current_year = datetime.datetime.now().year
            years = list(range(current_year - 1, current_year + 3))
            months = ["January", "February", "March", "April", "May", "June", 
                      "July", "August", "September", "October", "November", "December"]
            
            col1, col2 = st.columns(2)
            selected_year = col1.selectbox("Select Year", options=years, index=years.index(current_year))
            selected_month = col2.selectbox("Select Month", options=months, index=datetime.datetime.now().month - 1)
            
            submitted = st.form_submit_button(f"Create MCM for {selected_month} {selected_year}", use_container_width=True)
            
            if submitted:
                df_periods = read_from_spreadsheet(dbx, MCM_PERIODS_INFO_PATH)
                if df_periods is None:
                    df_periods = pd.DataFrame()
                
                period_key = f"{selected_month}_{selected_year}"
                
                # --- FIX: Check if 'key' column exists before accessing it ---
                if not df_periods.empty and 'key' in df_periods.columns and period_key in df_periods['key'].values:
                    st.warning(f"MCM Period for {selected_month} {selected_year} already exists.")
                else:
                    new_period = pd.DataFrame([{
                        "month_name": selected_month, 
                        "year": selected_year, 
                        "active": True, 
                        "key": period_key,
                        "overall_remarks": "" 
                    }])

                    if 'overall_remarks' not in df_periods.columns and not df_periods.empty:
                        df_periods['overall_remarks'] = ""
                    
                    # Ensure all columns from the new period are in the old one before concat
                    for col in new_period.columns:
                        if col not in df_periods.columns:
                            df_periods[col] = pd.NA

                    updated_df = pd.concat([df_periods, new_period], ignore_index=True)
                    
                    if update_spreadsheet_from_df(dbx, updated_df, MCM_PERIODS_INFO_PATH):
                        st.success(f"Successfully created and activated MCM period for {selected_month} {selected_year}!")
                        st.balloons()
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("Failed to save the new MCM period to Dropbox.")
   

    # ========================== MANAGE MCM PERIODS TAB ==========================
    elif selected_tab == "Manage MCM Periods":
        st.markdown("<h3>Manage Existing MCM Periods</h3>", unsafe_allow_html=True)
        st.markdown("<h4 style='color: red;'>Please Note: Deleting records will delete all the DAR and Spreadsheet data uploaded for that month.</h4>", unsafe_allow_html=True)
        st.markdown("<h5 style='color: green;'>Only the months marked as 'Active' by Planning officer will be available in Audit group screen for uploading DARs.</h5>", unsafe_allow_html=True)
        st.info("You can activate/deactivate periods or delete them using the editor. Changes are saved automatically.", icon="ℹ️")
        
        df_periods_manage = read_from_spreadsheet(dbx, MCM_PERIODS_INFO_PATH)
        
        if df_periods_manage is None or df_periods_manage.empty:
            st.info("No MCM periods have been created yet.")
        else:
            edited_df = st.data_editor(
                df_periods_manage,
                column_config={
                    "month_name": st.column_config.TextColumn("Month", disabled=True),
                    "year": st.column_config.NumberColumn("Year", disabled=True),
                    "active": st.column_config.CheckboxColumn("Active?", default=False),
                    "key": None  # Hide the key column
                },
                use_container_width=True,
                hide_index=True,
                num_rows="dynamic",
                key="manage_periods_editor"
            )
            
            if not df_periods_manage.equals(edited_df):
                if update_spreadsheet_from_df(dbx, edited_df, MCM_PERIODS_INFO_PATH):
                    st.toast("Changes saved successfully!")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("Failed to save changes to Dropbox.")

        # Handle deletion with confirmation (similar to original Google version)
        if st.session_state.get('show_delete_confirm') and st.session_state.get('period_to_delete'):
            period_key_to_delete = st.session_state.period_to_delete
            with st.form(key=f"delete_confirm_form_{period_key_to_delete}"):
                st.warning(f"Are you sure you want to delete the MCM period: **{period_key_to_delete}**?")
                st.error("**Warning:** This will remove the period from tracking. Use cautiously.")
                
                pco_password_confirm = st.text_input("Enter your PCO password:", type="password")
                form_c1, form_c2 = st.columns(2)
                
                with form_c1:
                    submitted_delete = st.form_submit_button("Yes, Delete Record", use_container_width=True)
                with form_c2:
                    if st.form_submit_button("Cancel", type="secondary", use_container_width=True):
                        st.session_state.show_delete_confirm = False
                        st.session_state.period_to_delete = None
                        st.rerun()
                
                if submitted_delete:
                    # Here you would validate the password against your user credentials
                    # For now, we'll skip password validation as it depends on your config
                    if pco_password_confirm:  # Replace with actual password validation
                        # Remove the period from the dataframe
                        df_updated = df_periods_manage[df_periods_manage['key'] != period_key_to_delete]
                        if update_spreadsheet_from_df(dbx, df_updated, MCM_PERIODS_INFO_PATH):
                            st.success(f"MCM period {period_key_to_delete} deleted successfully.")
                        else:
                            st.error("Failed to delete the period.")
                        st.session_state.show_delete_confirm = False
                        st.session_state.period_to_delete = None
                        st.rerun()
                    else:
                        st.error("Please enter your password to confirm deletion.")

    # ========================== VIEW UPLOADED REPORTS TAB ==========================
    elif selected_tab == "View Uploaded Reports":
        st.markdown("<h3>View Uploaded Reports Summary</h3>", unsafe_allow_html=True)
        
        df_periods = read_from_spreadsheet(dbx, MCM_PERIODS_INFO_PATH)
        if df_periods is None or df_periods.empty:
            st.info("No MCM periods exist. Please create one first.")
            return

        period_options = df_periods.apply(lambda row: f"{row['month_name']} {row['year']}", axis=1).tolist()
        selected_period = st.selectbox("Select MCM Period to View", options=period_options)

        if not selected_period:
            return

        with st.spinner("Loading all report data..."):
            df_all_data = read_from_spreadsheet(dbx, MCM_DATA_PATH)

        if df_all_data is None or df_all_data.empty:
            st.info("No DARs have been submitted by any group yet.")
            return

        df_filtered = df_all_data[df_all_data['mcm_period'] == selected_period].copy()

        if df_filtered.empty:
            st.info(f"No data found for the period: {selected_period}")
            return

        # Summary section
        st.markdown("#### Summary of Uploads")
        df_filtered['audit_group_number'] = pd.to_numeric(df_filtered['audit_group_number'], errors='coerce')
        df_filtered['audit_circle_number'] = pd.to_numeric(df_filtered['audit_circle_number'], errors='coerce')
        
        # Table 1: DARs & Audit Paras per Group (FULL WIDTH)
        st.markdown("**DARs & Audit Paras Uploaded per Group:**")
        dars_per_group = df_filtered.groupby('audit_group_number')['dar_pdf_path'].nunique().reset_index(name='DARs Uploaded')
        paras_per_group = df_filtered.groupby('audit_group_number').size().reset_index(name='Audit Paras')
        
        # Merge the two dataframes
        group_summary = pd.merge(dars_per_group, paras_per_group, on='audit_group_number', how='outer').fillna(0)
        group_summary['DARs Uploaded'] = group_summary['DARs Uploaded'].astype(int)
        group_summary['Audit Paras'] = group_summary['Audit Paras'].astype(int)
        group_summary['audit_group_number'] = group_summary['audit_group_number'].astype(int)
        group_summary = group_summary.rename(columns={'audit_group_number': 'Audit Group Number'})
        
        st.dataframe(group_summary, use_container_width=True, hide_index=True)
        
        # Add spacing
        st.markdown("---")
        
        # Table 2: DARs & Audit Paras per Circle (FULL WIDTH)
        st.markdown("**DARs & Audit Paras Uploaded per Circle:**")
        if 'audit_circle_number' in df_filtered.columns:
            df_circle_data = df_filtered.dropna(subset=['audit_circle_number'])
            if not df_circle_data.empty:
                dars_per_circle = df_circle_data.groupby('audit_circle_number')['dar_pdf_path'].nunique().reset_index(name='DARs Uploaded')
                paras_per_circle = df_circle_data.groupby('audit_circle_number').size().reset_index(name='Audit Paras')
                
                # Merge the two dataframes
                circle_summary = pd.merge(dars_per_circle, paras_per_circle, on='audit_circle_number', how='outer').fillna(0)
                circle_summary['DARs Uploaded'] = circle_summary['DARs Uploaded'].astype(int)
                circle_summary['Audit Paras'] = circle_summary['Audit Paras'].astype(int)
                circle_summary['audit_circle_number'] = circle_summary['audit_circle_number'].astype(int)
                circle_summary = circle_summary.rename(columns={'audit_circle_number': 'Audit Circle Number'})
                
                st.dataframe(circle_summary, use_container_width=True, hide_index=True)
            else:
                st.info("No circle data available for this period")
        else:
            st.info("Circle information not available in the data")
        
        # Add spacing
        st.markdown("---")
        
        # Table 3: Para Status Summary (FULL WIDTH)
        st.markdown("**Para Status Summary:**")
        if 'status_of_para' in df_filtered.columns:
            status_summary = df_filtered['status_of_para'].value_counts().reset_index(name='Count')
            status_summary.columns = ['Status of Para', 'Count']
            st.dataframe(status_summary, use_container_width=True, hide_index=True)
        else:
            st.info("Para status information not available in the data")

        st.markdown("<hr>")
        st.markdown(f"#### Edit Detailed Data for {selected_period}")
        st.info("You can edit data below. Click 'Save Changes' to update the master file.", icon="✍️")

        edited_df = st.data_editor(
            df_filtered, 
            use_container_width=True, 
            hide_index=True, 
            num_rows="dynamic", 
            key=f"pco_editor_{selected_period}"
        )

        if st.button("Save Changes to Master File", type="primary"):
            with st.spinner("Saving changes to Dropbox..."):
                # Update the master dataframe with edited rows
                df_all_data.update(edited_df)
                if update_spreadsheet_from_df(dbx, df_all_data, MCM_DATA_PATH):
                    st.success("Changes saved successfully!")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("Failed to save changes.")

    # ========================== MCM AGENDA TAB ==========================
    elif selected_tab == "MCM Agenda":
        mcm_agenda_tab(dbx)
  
    # ========================== VISUALIZATIONS TAB ==========================
    elif selected_tab == "Visualizations":
        st.markdown("<h3>Data Visualizations</h3>", unsafe_allow_html=True)
        
        # --- 1. Load Prerequisite Data ---
        df_periods = read_from_spreadsheet(dbx, MCM_PERIODS_INFO_PATH)
        if df_periods is None or df_periods.empty:
            st.info("No MCM periods exist to visualize.")
            return
            
        period_options = df_periods.apply(lambda row: f"{row['month_name']} {row['year']}", axis=1).tolist()
        selected_period = st.selectbox("Select MCM Period for Visualization", options=period_options, key="pco_viz_selectbox_final_v4")
    
        if not selected_period:
            return
    
        # --- 2. Load and Filter Core Visualization Data ---
        with st.spinner("Loading data for visualizations..."):
            df_viz_data = read_from_spreadsheet(dbx, MCM_DATA_PATH)
            if df_viz_data is None or df_viz_data.empty:
                st.info("No data available to visualize.")
                return
            df_viz_data = df_viz_data[df_viz_data['mcm_period'] == selected_period].copy()
    
        if df_viz_data.empty:
            st.info(f"No data to visualize for {selected_period}.")
            return
    
        # --- Data Cleaning and Preparation (Consolidated) ---
        amount_cols = [
            'total_amount_detected_overall_rs', 'total_amount_recovered_overall_rs',
            'revenue_involved_rs', 'revenue_recovered_rs'
        ]
        for col in amount_cols:
            if col in df_viz_data.columns:
                df_viz_data[col] = pd.to_numeric(df_viz_data[col], errors='coerce').fillna(0)
    
        df_viz_data['Detection in Lakhs'] = df_viz_data.get('total_amount_detected_overall_rs', 0) / 100000.0
        df_viz_data['Recovery in Lakhs'] = df_viz_data.get('total_amount_recovered_overall_rs', 0) / 100000.0
        df_viz_data['Para Detection in Lakhs'] = df_viz_data.get('revenue_involved_rs', 0) / 100000.0
        df_viz_data['Para Recovery in Lakhs'] = df_viz_data.get('revenue_recovered_rs', 0) / 100000.0
        
        df_viz_data['audit_group_number'] = pd.to_numeric(df_viz_data.get('audit_group_number'), errors='coerce').fillna(0).astype(int)
        df_viz_data['audit_circle_number'] = pd.to_numeric(df_viz_data.get('audit_circle_number'), errors='coerce').fillna(0).astype(int)
        df_viz_data['audit_group_number_str'] = df_viz_data['audit_group_number'].astype(str)
        df_viz_data['circle_number_str'] = df_viz_data['audit_circle_number'].astype(str)
        
        df_viz_data['category'] = df_viz_data.get('category', 'Unknown').fillna('Unknown')
        df_viz_data['trade_name'] = df_viz_data.get('trade_name', 'Unknown Trade Name').fillna('Unknown Trade Name')
        df_viz_data['taxpayer_classification'] = df_viz_data.get('taxpayer_classification', 'Unknown').fillna('Unknown')
        df_viz_data['para_classification_code'] = df_viz_data.get('para_classification_code', 'UNCLASSIFIED').fillna('UNCLASSIFIED')

        # Unique reports for DAR-level analysis
        if 'dar_pdf_path' in df_viz_data.columns and df_viz_data['dar_pdf_path'].notna().any():
            df_unique_reports = df_viz_data.drop_duplicates(subset=['dar_pdf_path']).copy()
        else:
            df_unique_reports = df_viz_data.drop_duplicates(subset=['gstin']).copy()
    
    
        # --- 4. Monthly Performance Summary Metrics ---
        st.markdown("#### Monthly Performance Summary")
        num_dars = df_unique_reports['dar_pdf_path'].nunique()
        total_detected = df_unique_reports.get('Detection in Lakhs', 0).sum()
        total_recovered = df_unique_reports.get('Recovery in Lakhs', 0).sum()
        
        col1, col2, col3 = st.columns(3)
        col1.metric(label="✅ DARs Submitted", value=f"{num_dars}")
        col2.metric(label="💰 Revenue Involved", value=f"₹{total_detected:.2f} L")
        col3.metric(label="🏆 Revenue Recovered", value=f"₹{total_recovered:.2f} L")
    
        # --- 5. Group & Circle Performance Bar Charts ---
        st.markdown("---")
        st.markdown("<h4>Group & Circle Performance</h4>", unsafe_allow_html=True)
        
        def style_chart(fig, title_text, y_title, x_title):
            fig.update_layout(
                title_text=f"<b>{title_text}</b>", title_x=0.5,
                yaxis_title=f"<b>{y_title}</b>", xaxis_title=f"<b>{x_title}</b>",
                font=dict(family="sans-serif", color="#333"),
                paper_bgcolor='#F0F2F6', plot_bgcolor='#FFFFFF',
                xaxis_type='category',
                yaxis=dict(showgrid=True, gridcolor='#e5e5e5'),
                xaxis=dict(showgrid=False), height=400
            )
            fig.update_traces(marker_line=dict(width=1.5, color='#333'), textposition="outside", cliponaxis=False)
            return fig
    
        tab1, tab2 = st.tabs(["Detection Performance", "Recovery Performance"])
    
        with tab1:
            group_detection = df_unique_reports.groupby('audit_group_number_str')['Detection in Lakhs'].sum().nlargest(10).reset_index()
            if not group_detection.empty:
                fig_det_grp = px.bar(group_detection, x='audit_group_number_str', y='Detection in Lakhs', text_auto='.2f', color_discrete_sequence=px.colors.qualitative.Vivid)
                fig_det_grp = style_chart(fig_det_grp, "Top 10 Groups by Detection", "Amount (₹ Lakhs)", "Audit Group")
                st.plotly_chart(fig_det_grp, use_container_width=True)
    
            circle_detection = df_unique_reports.groupby('circle_number_str')['Detection in Lakhs'].sum().sort_values(ascending=False).reset_index()
            circle_detection = circle_detection[circle_detection['circle_number_str'] != '0']
            if not circle_detection.empty:
                fig_det_circle = px.bar(circle_detection, x='circle_number_str', y='Detection in Lakhs', text_auto='.2f', color_discrete_sequence=px.colors.qualitative.Pastel1)
                fig_det_circle = style_chart(fig_det_circle, "Circle-wise Detection", "Amount (₹ Lakhs)", "Audit Circle")
                st.plotly_chart(fig_det_circle, use_container_width=True)
    
        with tab2:
            group_recovery = df_unique_reports.groupby('audit_group_number_str')['Recovery in Lakhs'].sum().nlargest(10).reset_index()
            if not group_recovery.empty:
                fig_rec_grp = px.bar(group_recovery, x='audit_group_number_str', y='Recovery in Lakhs', text_auto='.2f', color_discrete_sequence=px.colors.qualitative.Set2)
                fig_rec_grp = style_chart(fig_rec_grp, "Top 10 Groups by Recovery", "Amount (₹ Lakhs)", "Audit Group")
                st.plotly_chart(fig_rec_grp, use_container_width=True)
    
            circle_recovery = df_unique_reports.groupby('circle_number_str')['Recovery in Lakhs'].sum().sort_values(ascending=False).reset_index()
            circle_recovery = circle_recovery[circle_recovery['circle_number_str'] != '0']
            if not circle_recovery.empty:
                fig_rec_circle = px.bar(circle_recovery, x='circle_number_str', y='Recovery in Lakhs', text_auto='.2f', color_discrete_sequence=px.colors.qualitative.G10)
                fig_rec_circle = style_chart(fig_rec_circle, "Circle-wise Recovery", "Amount (₹ Lakhs)", "Audit Circle")
                st.plotly_chart(fig_rec_circle, use_container_width=True)
              # --- Section 3: Taxpayer Classification Analysis (New) ---
        st.markdown("---")
        st.markdown("<h4>Taxpayer Classification Analysis</h4>", unsafe_allow_html=True)

        tc_tab1, tc_tab2 = st.tabs(["DARs by Classification", "Detection & Recovery by Classification"])

        with tc_tab1:
            if 'taxpayer_classification' in df_unique_reports.columns:
                class_counts = df_unique_reports['taxpayer_classification'].value_counts().reset_index()
                class_counts.columns = ['classification', 'count']
                
                fig_pie_dars = px.pie(class_counts, names='classification', values='count',
                                      title="Distribution of DARs by Taxpayer Classification",
                                      color_discrete_sequence=px.colors.sequential.Blues_r,
                                      labels={'classification': 'Taxpayer Classification', 'count': 'Number of DARs'})
                fig_pie_dars.update_traces(textposition='inside', textinfo='percent+label', pull=[0.05]*len(class_counts))
                fig_pie_dars.update_layout(legend_title="Classification", title_x=0.5)
                st.plotly_chart(fig_pie_dars, use_container_width=True)
            else:
                st.info("Taxpayer classification data not available for this period.")

        with tc_tab2:
            if 'taxpayer_classification' in df_unique_reports.columns:
                class_agg = df_unique_reports.groupby('taxpayer_classification').agg(
                    Total_Detection=('Detection in Lakhs', 'sum'),
                    Total_Recovery=('Recovery in Lakhs', 'sum')
                ).reset_index()

                col_det, col_rec = st.columns(2)
                with col_det:
                    fig_pie_det = px.pie(class_agg, names='taxpayer_classification', values='Total_Detection',
                                         title="Detection Amount by Taxpayer Classification",
                                         color_discrete_sequence=px.colors.sequential.Reds_r,
                                         labels={'taxpayer_classification': 'Classification', 'Total_Detection': 'Detection (₹ Lakhs)'})
                    fig_pie_det.update_traces(textposition='inside', textinfo='percent+label')
                    fig_pie_det.update_layout(legend_title="Classification", title_x=0.5)
                    st.plotly_chart(fig_pie_det, use_container_width=True)
                
                with col_rec:
                    fig_pie_rec = px.pie(class_agg, names='taxpayer_classification', values='Total_Recovery',
                                         title="Recovery Amount by Taxpayer Classification",
                                         color_discrete_sequence=px.colors.sequential.Purples_r,
                                         labels={'taxpayer_classification': 'Classification', 'Total_Recovery': 'Recovery (₹ Lakhs)'})
                    fig_pie_rec.update_traces(textposition='inside', textinfo='percent+label')
                    fig_pie_rec.update_layout(legend_title="Classification", title_x=0.5)
                    st.plotly_chart(fig_pie_rec, use_container_width=True)
            else:
                st.info("Taxpayer classification data not available for this period.")

        st.markdown("---")
        st.markdown("<h4>Nature of Compliance Analysis for Audit Paras</h4>", unsafe_allow_html=True)
        
        CLASSIFICATION_CODES_DESC = {
            'TP': 'TAX PAYMENT DEFAULTS', 'RC': 'REVERSE CHARGE MECHANISM',
            'IT': 'INPUT TAX CREDIT VIOLATIONS', 'IN': 'INTEREST LIABILITY DEFAULTS',
            'RF': 'RETURN FILING NON-COMPLIANCE', 'PD': 'PROCEDURAL & DOCUMENTATION',
            'CV': 'CLASSIFICATION & VALUATION', 'SS': 'SPECIAL SITUATIONS',
            'PG': 'PENALTY & GENERAL COMPLIANCE'
        }
        
        DETAILED_CLASSIFICATION_DESC = {
            'TP01': 'Output Tax Short Payment - GSTR Discrepancies', 'TP02': 'Output Tax on Other Income',
            'TP03': 'Output Tax on Asset Sales', 'TP04': 'Export & SEZ Related Issues',
            'TP05': 'Credit Note Adjustment Errors', 'TP06': 'Turnover Reconciliation Issues',
            'TP07': 'Scheme Migration Issues', 'TP08': 'Other Tax Payment Issues',
            'RC01': 'RCM on Transportation Services', 'RC02': 'RCM on Professional Services',
            'RC03': 'RCM on Administrative Services', 'RC04': 'RCM on Import of Services',
            'RC05': 'RCM Reconciliation Issues', 'RC06': 'RCM on Other Services', 'RC07': 'Other RCM Issues',
            'IT01': 'Blocked Credit Claims (Sec 17(5))', 'IT02': 'Ineligible ITC Claims (Sec 16)',
            'IT03': 'Excess ITC - GSTR Reconciliation', 'IT04': 'Supplier Registration Issues',
            'IT05': 'ITC Reversal - 180 Day Rule', 'IT06': 'ITC Reversal - Other Reasons',
            'IT07': 'Proportionate ITC Issues (Rule 42)', 'IT08': 'RCM ITC Mismatches',
            'IT09': 'Import IGST ITC Issues', 'IT10': 'Migration Related ITC Issues', 'IT11': 'Other ITC Issues',
            'IN01': 'Interest on Delayed Tax Payment', 'IN02': 'Interest on Delayed Filing',
            'IN03': 'Interest on ITC - 180 Day Rule', 'IN04': 'Interest on ITC Reversals',
            'IN05': 'Interest on Time of Supply Issues', 'IN06': 'Interest on Self-Assessment (DRC-03)',
            'IN07': 'Other Interest Issues', 'RF01': 'GSTR-1 Late Filing Fees', 'RF02': 'GSTR-3B Late Filing Fees',
            'RF03': 'GSTR-9 Late Filing Fees', 'RF04': 'GSTR-9C Late Filing Fees',
            'RF05': 'ITC-04 Non-Filing', 'RF06': 'General Return Filing Issues', 'RF07': 'Other Return Filing Issues',
            'PD01': 'Return Reconciliation Mismatches', 'PD02': 'Documentation Deficiencies',
            'PD03': 'Cash Payment Violations (Rule 86B)', 'PD04': 'Record Maintenance Issues', 'PD05': 'Other Procedural Issues',
            'CV01': 'Service Classification Errors', 'CV02': 'Rate Classification Errors',
            'CV03': 'Place of Supply Issues', 'CV04': 'Other Classification Issues',
            'SS01': 'Construction/Real Estate Issues', 'SS02': 'Job Work Related Issues',
            'SS03': 'Inter-Company Transaction Issues', 'SS04': 'Composition Scheme Issues', 'SS05': 'Other Special Situations',
            'PG01': 'Statutory Penalties (Sec 123)', 'PG02': 'Stock & Physical Verification Issues',
            'PG03': 'Compliance Monitoring Issues', 'PG04': 'Other Penalty Issues'
        }

        df_paras = df_viz_data[df_viz_data['para_classification_code'] != 'UNCLASSIFIED'].copy()
        if not df_paras.empty:
            df_paras['major_code'] = df_paras['para_classification_code'].str[:2]
        
            nc_tab1, nc_tab2, nc_tab3 = st.tabs(["Classification Code Summary", "Detection by Detailed Code", "Recovery by Detailed Code"])

            with nc_tab1:
                major_code_agg = df_paras.groupby('major_code').agg(
                    Para_Count=('major_code', 'count'),
                    Total_Detection=('Para Detection in Lakhs', 'sum'),
                    Total_Recovery=('Para Recovery in Lakhs', 'sum')
                ).reset_index()
                major_code_agg['description'] = major_code_agg['major_code'].map(CLASSIFICATION_CODES_DESC)

                fig_bar_paras = px.bar(major_code_agg, x='description', y='Para_Count', text_auto=True,
                                       title="Number of Audit Paras by Categorisation",
                                       labels={'description': 'Classification Code', 'Para_Count': 'Number of Paras'},
                                       color_discrete_sequence=['#1f77b4'])
                st.plotly_chart(fig_bar_paras, use_container_width=True)

                fig_bar_det = px.bar(major_code_agg, x='description', y='Total_Detection', text_auto='.2f',
                                     title="Detection Amount by Categorisation",
                                     labels={'description': 'Classification Code', 'Total_Detection': 'Detection (₹ Lakhs)'},
                                     color_discrete_sequence=['#ff7f0e'])
                st.plotly_chart(fig_bar_det, use_container_width=True)

                fig_bar_rec = px.bar(major_code_agg, x='description', y='Total_Recovery', text_auto='.2f',
                                     title="Recovery Amount by Categorisation",
                                     labels={'description': 'Classification Code', 'Total_Recovery': 'Recovery (₹ Lakhs)'},
                                     color_discrete_sequence=['#2ca02c'])
                st.plotly_chart(fig_bar_rec, use_container_width=True)

            with nc_tab2:
                st.markdown("<h5>Detection Analysis by Detailed Categorisation</h5>", unsafe_allow_html=True)
                unique_major_codes_det = df_paras[df_paras['Para Detection in Lakhs'] > 0]['major_code'].unique()
                for code in sorted(unique_major_codes_det):
                    df_filtered = df_paras[df_paras['major_code'] == code].copy()
                    df_agg = df_filtered.groupby('para_classification_code')['Para Detection in Lakhs'].sum().reset_index()
                    df_agg['description'] = df_agg['para_classification_code'].map(DETAILED_CLASSIFICATION_DESC)
                    
                    fig = px.bar(df_agg, x='para_classification_code', y='Para Detection in Lakhs',
                                 title=f"Detection for {code} - {CLASSIFICATION_CODES_DESC.get(code, '')}",
                                 labels={'para_classification_code': 'Detailed Code', 'Para Detection in Lakhs': 'Detection (₹ Lakhs)'},
                                 text_auto='.2f', hover_data=['description'])
                    fig.update_traces(hovertemplate='<b>%{x}</b>: %{customdata[0]}<br>Detection: %{y:,.2f} Lakhs<extra></extra>')
                    st.plotly_chart(fig, use_container_width=True)

            with nc_tab3:
                st.markdown("<h5>Recovery Analysis by Detailed Categorisation</h5>", unsafe_allow_html=True)
                unique_major_codes_rec = df_paras[df_paras['Para Recovery in Lakhs'] > 0]['major_code'].unique()
                for code in sorted(unique_major_codes_rec):
                    df_filtered = df_paras[df_paras['major_code'] == code].copy()
                    df_agg = df_filtered.groupby('para_classification_code')['Para Recovery in Lakhs'].sum().reset_index()
                    df_agg['description'] = df_agg['para_classification_code'].map(DETAILED_CLASSIFICATION_DESC)

                    fig = px.bar(df_agg, x='para_classification_code', y='Para Recovery in Lakhs',
                                 title=f"Recovery for {code} - {CLASSIFICATION_CODES_DESC.get(code, '')}",
                                 labels={'para_classification_code': 'Detailed Code', 'Para Recovery in Lakhs': 'Recovery (₹ Lakhs)'},
                                 text_auto='.2f', color_discrete_sequence=px.colors.qualitative.Plotly,
                                 hover_data=['description'])
                    fig.update_traces(hovertemplate='<b>%{x}</b>: %{customdata[0]}<br>Recovery: %{y:,.2f} Lakhs<extra></extra>')
                    st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No classified audit para data available for this period.")

        # --- 6. Treemaps by Trade Name ---
        st.markdown("---")
        st.markdown("<h4>Analysis by Trade Name</h4>", unsafe_allow_html=True)
        
        df_treemap = df_unique_reports.dropna(subset=['category', 'trade_name']).copy()
        
        # MODIFICATION: New light and modern color palette, avoiding red
        color_map = {
            'Large': '#3A86FF',    # Bright Blue
            'Medium': '#3DCCC7',   # Turquoise
            'Small': '#90E0EF',    # Light Blue/Cyan
            'Unknown': '#CED4DA'   # Light Grey
        }
    
        # Detection Treemap
        df_det_treemap = df_treemap[df_treemap['Detection in Lakhs'] > 0]
        if not df_det_treemap.empty:
            try:
                fig_tree_det = px.treemap(
                    df_det_treemap, path=[px.Constant("All Detections"), 'category', 'trade_name'],
                    values='Detection in Lakhs', color='category', color_discrete_map=color_map,
                    custom_data=['audit_group_number_str', 'trade_name']
                )
                fig_tree_det.update_layout(
                    title_text="<b>Detection by Trade Name</b>", title_x=0.5, 
                    margin=dict(t=50, l=25, r=25, b=25), paper_bgcolor='#F0F2F6',
                    font=dict(family="sans-serif")
                )
                # MODIFICATION: Add white borders for better separation and update hover text
                fig_tree_det.update_traces(
                    marker_line_width=2, marker_line_color='white',
                    hovertemplate="<b>%{customdata[1]}</b><br>Category: %{parent}<br>Detection: %{value:,.2f} L<extra></extra>"
                )
                st.plotly_chart(fig_tree_det, use_container_width=True)
            except Exception as e:
                st.error(f"Could not generate detection treemap: {e}")
    
        # Recovery Treemap
        df_rec_treemap = df_treemap[df_treemap['Recovery in Lakhs'] > 0]
        if not df_rec_treemap.empty:
            try:
                fig_tree_rec = px.treemap(
                    df_rec_treemap, path=[px.Constant("All Recoveries"), 'category', 'trade_name'],
                    values='Recovery in Lakhs', color='category', color_discrete_map=color_map,
                    custom_data=['audit_group_number_str', 'trade_name']
                )
                # MODIFICATION: Applied consistent styling to the recovery treemap
                fig_tree_rec.update_layout(
                    title_text="<b>Recovery by Trade Name</b>", title_x=0.5,
                    margin=dict(t=50, l=25, r=25, b=25), paper_bgcolor='#F0F2F6',
                    font=dict(family="sans-serif")
                )
                fig_tree_rec.update_traces(
                    marker_line_width=2, marker_line_color='white',
                    hovertemplate="<b>%{customdata[1]}</b><br>Category: %{parent}<br>Recovery: %{value:,.2f} L<extra></extra>"
                )
                st.plotly_chart(fig_tree_rec, use_container_width=True)
            except Exception as e:
                st.error(f"Could not generate recovery treemap: {e}")
        # --- Para-wise Performance (uses original full data) ---
        st.markdown("---")
        st.markdown("<h4>Para-wise Performance</h4>", unsafe_allow_html=True)
        if 'num_paras_to_show_pco' not in st.session_state:
            st.session_state.num_paras_to_show_pco = 5
        viz_n_paras_input = st.text_input("Enter N for Top N Paras (e.g., 5):", value=str(st.session_state.num_paras_to_show_pco), key="pco_n_paras_input_final_v2")
        viz_num_paras_show = st.session_state.num_paras_to_show_pco
        try:
            viz_parsed_n = int(viz_n_paras_input)
            if viz_parsed_n < 1:
                viz_num_paras_show = 5
                st.warning("N must be positive. Showing Top 5.", icon="⚠️")
            elif viz_parsed_n > 50:
                viz_num_paras_show = 50
                st.warning("N capped at 50. Showing Top 50.", icon="⚠️")
            else:
                viz_num_paras_show = viz_parsed_n
            st.session_state.num_paras_to_show_pco = viz_num_paras_show
        except ValueError:
            if viz_n_paras_input != str(st.session_state.num_paras_to_show_pco):
                st.warning(f"Invalid N ('{viz_n_paras_input}'). Using: {viz_num_paras_show}", icon="⚠️")
        
        viz_df_paras_only = df_viz_data[df_viz_data['audit_para_number'].notna() & (~df_viz_data['audit_para_heading'].astype(str).isin(["N/A - Header Info Only (Add Paras Manually)", "Manual Entry Required", "Manual Entry - PDF Error", "Manual Entry - PDF Upload Failed"]))]
        if 'revenue_involved_lakhs_rs' in viz_df_paras_only.columns:
            viz_top_det_paras = viz_df_paras_only.nlargest(viz_num_paras_show, 'revenue_involved_lakhs_rs')
            if not viz_top_det_paras.empty:
                st.write(f"**Top {viz_num_paras_show} Detection Paras (by Revenue Involved):**")
                viz_disp_cols_det = ['audit_group_number_str', 'trade_name', 'audit_para_number', 'audit_para_heading', 'revenue_involved_lakhs_rs', 'status_of_para']
                viz_existing_cols_det = [c for c in viz_disp_cols_det if c in viz_top_det_paras.columns]
                st.dataframe(viz_top_det_paras[viz_existing_cols_det].rename(columns={'audit_group_number_str': 'Audit Group'}), use_container_width=True)
        if 'revenue_recovered_lakhs_rs' in viz_df_paras_only.columns:
            viz_top_rec_paras = viz_df_paras_only.nlargest(viz_num_paras_show, 'revenue_recovered_lakhs_rs')
            if not viz_top_rec_paras.empty:
                st.write(f"**Top {viz_num_paras_show} Realisation Paras (by Revenue Recovered):**")
                viz_disp_cols_rec = ['audit_group_number_str', 'trade_name', 'audit_para_number', 'audit_para_heading', 'revenue_recovered_lakhs_rs', 'status_of_para']
                viz_existing_cols_rec = [c for c in viz_disp_cols_rec if c in viz_top_rec_paras.columns]
                st.dataframe(viz_top_rec_paras[viz_existing_cols_rec].rename(columns={'audit_group_number_str': 'Audit Group'}), use_container_width=True)

    elif selected_tab == "Reports":
        pco_reports_dashboard(dbx)

    st.markdown("</div>", unsafe_allow_html=True)
  
