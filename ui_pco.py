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
                
                if not df_periods.empty and period_key in df_periods['key'].values:
                    st.warning(f"MCM Period for {selected_month} {selected_year} already exists.")
                else:
                    new_period = pd.DataFrame([{
                        "month_name": selected_month, 
                        "year": selected_year, 
                        "active": True, 
                        "key": period_key
                    }])
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
    
        # --- 3. Data Cleaning and Preparation ---
        amount_cols = [
            'total_amount_detected_overall_rs', 'total_amount_recovered_overall_rs',
            'revenue_involved_lakhs_rs', 'revenue_recovered_lakhs_rs'
        ]
        for col in amount_cols:
            if col in df_viz_data.columns:
                df_viz_data[col] = pd.to_numeric(df_viz_data[col], errors='coerce').fillna(0)
    
        df_viz_data['Detection in Lakhs'] = df_viz_data.get('total_amount_detected_overall_rs', 0) / 100000.0
        df_viz_data['Recovery in Lakhs'] = df_viz_data.get('total_amount_recovered_overall_rs', 0) / 100000.0
        
        df_viz_data['audit_group_number'] = pd.to_numeric(df_viz_data.get('audit_group_number'), errors='coerce').fillna(0).astype(int)
        df_viz_data['audit_circle_number'] = pd.to_numeric(df_viz_data.get('audit_circle_number'), errors='coerce').fillna(0).astype(int)
        df_viz_data['audit_group_number_str'] = df_viz_data['audit_group_number'].astype(str)
        df_viz_data['circle_number_str'] = df_viz_data['audit_circle_number'].astype(str)
        
        df_viz_data['category'] = df_viz_data.get('category', 'Unknown').fillna('Unknown')
        df_viz_data['trade_name'] = df_viz_data.get('trade_name', 'Unknown Trade Name').fillna('Unknown Trade Name')
        df_viz_data['status_of_para'] = df_viz_data.get('status_of_para', 'Unknown').fillna('Unknown')
    
        if 'dar_pdf_path' in df_viz_data.columns and df_viz_data['dar_pdf_path'].notna().any():
            df_unique_reports = df_viz_data.drop_duplicates(subset=['dar_pdf_path']).copy()
        else:
            st.warning("⚠️ 'dar_pdf_path' column not found. Report-level sums might be inflated.", icon=" ")
            df_unique_reports = df_viz_data.copy()
    
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
    
        # --- 6. Treemaps by Trade Name ---
        st.markdown("---")
        st.markdown("<h4>Analysis by Trade Name</h4>", unsafe_allow_html=True)
        
        df_treemap = df_unique_reports.dropna(subset=['category', 'trade_name']).copy()
        color_map = {
            'Large': '#3A86FF', 'Medium': '#3DCCC7',
            'Small': '#90E0EF', 'Unknown': '#CED4DA'
        }
    
        # Detection Treemap
        df_det_treemap = df_treemap[df_treemap['Detection in Lakhs'] > 0]
        if not df_det_treemap.empty:
            try:
                fig_tree_det = px.treemap(
                    df_det_treemap, 
                    path=[px.Constant("All Detections"), 'category', 'trade_name'],
                    values='Detection in Lakhs', 
                    color='category', 
                    color_discrete_map=color_map,
                    custom_data=['audit_group_number_str', 'trade_name']
                )
                
                # Update layout (without pathbar properties)
                fig_tree_det.update_layout(
                    title_text="<b>Detection by Trade Name</b>", 
                    title_x=0.5, 
                    margin=dict(t=50, l=25, r=25, b=25), 
                    paper_bgcolor='#F0F2F6',
                    font=dict(family="sans-serif", size=12)
                )
                
                # Update traces with pathbar styling and hover template
                fig_tree_det.update_traces(
                    marker_line_width=2, 
                    marker_line_color='white',
                    pathbar=dict(
                        textfont=dict(color='white', size=14),
                        bgcolor='rgba(0,0,0,0.8)',
                        bordercolor='white',
                        borderwidth=1
                    ),
                    hovertemplate="<b>%{customdata[1]}</b><br>Category: %{parent}<br>Detection: ₹%{value:,.2f} L<extra></extra>"
                )
                
                st.plotly_chart(fig_tree_det, use_container_width=True)
                
            except Exception as e:
                st.error(f"Could not generate detection treemap: {e}")
                # Fallback to simple bar chart if treemap fails
                st.write("Showing alternative visualization:")
                det_by_trade = df_det_treemap.groupby(['category', 'trade_name'])['Detection in Lakhs'].sum().reset_index()
                det_by_trade = det_by_trade.nlargest(15, 'Detection in Lakhs')
                if not det_by_trade.empty:
                    fig_fallback = px.bar(det_by_trade, x='trade_name', y='Detection in Lakhs', 
                                        color='category', color_discrete_map=color_map,
                                        title="Top 15 Trade Names by Detection")
                    fig_fallback.update_xaxes(tickangle=45)
                    st.plotly_chart(fig_fallback, use_container_width=True)
    
        # Recovery Treemap
        df_rec_treemap = df_treemap[df_treemap['Recovery in Lakhs'] > 0]
        if not df_rec_treemap.empty:
            try:
                fig_tree_rec = px.treemap(
                    df_rec_treemap, 
                    path=[px.Constant("All Recoveries"), 'category', 'trade_name'],
                    values='Recovery in Lakhs', 
                    color='category', 
                    color_discrete_map=color_map,
                    custom_data=['audit_group_number_str', 'trade_name']
                )
                
                # Update layout (without pathbar properties)
                fig_tree_rec.update_layout(
                    title_text="<b>Recovery by Trade Name</b>", 
                    title_x=0.5,
                    margin=dict(t=50, l=25, r=25, b=25), 
                    paper_bgcolor='#F0F2F6',
                    font=dict(family="sans-serif", size=12)
                )
                
                # Update traces with pathbar styling and hover template
                fig_tree_rec.update_traces(
                    marker_line_width=2, 
                    marker_line_color='white',
                    pathbar=dict(
                        textfont=dict(color='white', size=14),
                        bgcolor='rgba(0,0,0,0.8)',
                        bordercolor='white',
                        borderwidth=1
                    ),
                    hovertemplate="<b>%{customdata[1]}</b><br>Category: %{parent}<br>Recovery: ₹%{value:,.2f} L<extra></extra>"
                )
                
                st.plotly_chart(fig_tree_rec, use_container_width=True)
                
            except Exception as e:
                st.error(f"Could not generate recovery treemap: {e}")
                # Fallback to simple bar chart if treemap fails
                st.write("Showing alternative visualization:")
                rec_by_trade = df_rec_treemap.groupby(['category', 'trade_name'])['Recovery in Lakhs'].sum().reset_index()
                rec_by_trade = rec_by_trade.nlargest(15, 'Recovery in Lakhs')
                if not rec_by_trade.empty:
                    fig_fallback = px.bar(rec_by_trade, x='trade_name', y='Recovery in Lakhs', 
                                        color='category', color_discrete_map=color_map,
                                        title="Top 15 Trade Names by Recovery")
                    fig_fallback.update_xaxes(tickangle=45)
                    st.plotly_chart(fig_fallback, use_container_width=True)

    elif selected_tab == "Reports":
        pco_reports_dashboard(dbx)

    st.markdown("</div>", unsafe_allow_html=True)
    # # ========================== VISUALIZATIONS TAB ==========================
    # elif selected_tab == "Visualizations":
    #     st.markdown("<h3>Data Visualizations</h3>", unsafe_allow_html=True)
        
    #     df_periods = read_from_spreadsheet(dbx, MCM_PERIODS_INFO_PATH)
    #     if df_periods is None or df_periods.empty:
    #         st.info("No MCM periods exist to visualize.")
    #         return
            
    #     period_options = df_periods.apply(lambda row: f"{row['month_name']} {row['year']}", axis=1).tolist()
    #     selected_period = st.selectbox("Select MCM Period for Visualization", options=period_options, key="pco_viz_selectbox_final_v4")

    #     if not selected_period:
    #         return

    #     with st.spinner("Loading data for visualizations..."):
    #         df_viz_data = read_from_spreadsheet(dbx, MCM_DATA_PATH)
    #         if df_viz_data is None or df_viz_data.empty:
    #             st.info("No data available to visualize.")
    #             return
    #         df_viz_data = df_viz_data[df_viz_data['mcm_period'] == selected_period].copy()

    #     if df_viz_data.empty:
    #         st.info(f"No data to visualize for {selected_period}.")
    #         return

    #     # --- Data Cleaning and Preparation ---
    #     viz_amount_cols = ['total_amount_detected_overall_rs', 'total_amount_recovered_overall_rs', 'revenue_involved_lakhs_rs', 'revenue_recovered_lakhs_rs']
    #     for v_col in viz_amount_cols:
    #         if v_col in df_viz_data.columns:
    #             df_viz_data[v_col] = pd.to_numeric(df_viz_data[v_col], errors='coerce').fillna(0)
        
    #     if 'audit_group_number' in df_viz_data.columns:
    #         df_viz_data['audit_group_number'] = pd.to_numeric(df_viz_data['audit_group_number'], errors='coerce').fillna(0).astype(int)

    #     # --- De-duplicate data for aggregated charts to prevent inflated sums ---
    #     if 'dar_pdf_path' in df_viz_data.columns and df_viz_data['dar_pdf_path'].notna().any():
    #         df_unique_reports = df_viz_data.drop_duplicates(subset=['dar_pdf_path']).copy()
    #     else:
    #         st.warning("⚠️ 'dar_pdf_path' column not found. Chart sums might be inflated due to repeated values.", icon=" ")
    #         df_unique_reports = df_viz_data.copy()

    #     # --- Convert amounts to Lakhs on the de-duplicated data for clear visualization ---
    #     if 'total_amount_detected_overall_rs' in df_unique_reports.columns:
    #         df_unique_reports['Detection in Lakhs'] = df_unique_reports['total_amount_detected_overall_rs'] / 100000.0
    #     if 'total_amount_recovered_overall_rs' in df_unique_reports.columns:
    #         df_unique_reports['Recovery in Lakhs'] = df_unique_reports['total_amount_recovered_overall_rs'] / 100000.0

    #     # Prepare other columns for categorization and grouping
    #     for df in [df_viz_data, df_unique_reports]:
    #         if 'audit_group_number' in df.columns:
    #             df['audit_group_number'] = pd.to_numeric(df['audit_group_number'], errors='coerce').fillna(0).astype(int)
    #         else:
    #             df['audit_group_number'] = 0
    #         df['audit_group_number_str'] = df['audit_group_number'].astype(str)
            
    #         if 'audit_circle_number' in df.columns and df['audit_circle_number'].notna().any() and pd.to_numeric(df['audit_circle_number'], errors='coerce').notna().any():
    #             df['circle_number_for_plot'] = pd.to_numeric(df['audit_circle_number'], errors='coerce').fillna(0).astype(int)
    #         elif 'audit_group_number' in df.columns and not df['audit_group_number'].eq(0).all():
    #             df['circle_number_for_plot'] = ((df['audit_group_number'] - 1) // 3 + 1).astype(int)
    #         else:
    #             df['circle_number_for_plot'] = 0
    #         df['circle_number_str_plot'] = df['circle_number_for_plot'].astype(str)
            
    #         df['category'] = df.get('category', pd.Series(dtype='str')).fillna('Unknown')
    #         df['trade_name'] = df.get('trade_name', pd.Series(dtype='str')).fillna('Unknown Trade Name')
    #         df['status_of_para'] = df.get('status_of_para', pd.Series(dtype='str')).fillna('Unknown')

    #     # --- Monthly Performance Summary ---
    #     st.markdown("#### Monthly Performance Summary")
        
    #     # --- Calculations for Summary ---
    #     num_dars = df_unique_reports['dar_pdf_path'].nunique()
    #     total_detected = df_unique_reports['Detection in Lakhs'].sum()
    #     total_recovered = df_unique_reports['Recovery in Lakhs'].sum()

    #     dars_per_group = df_unique_reports[df_unique_reports['audit_group_number'] > 0].groupby('audit_group_number')['dar_pdf_path'].nunique()
        
    #     if not dars_per_group.empty:
    #         max_dars_count = dars_per_group.max()
    #         max_dars_group = dars_per_group.idxmax()
    #         max_group_str = f"AG {max_dars_group} ({max_dars_count} DARs)"
    #     else:
    #         max_group_str = "N/A"

    #     # Assuming total audit groups are from 1 to 30
    #     all_audit_groups = set(range(1, 31)) 
    #     submitted_groups = set(dars_per_group.index)
    #     zero_dar_groups = sorted(list(all_audit_groups - submitted_groups))
    #     zero_dar_groups_str = ", ".join(map(str, zero_dar_groups)) if zero_dar_groups else "None"

    #     # --- Display Summary ---
    #     col1, col2, col3 = st.columns(3)
    #     col1.metric(label="✅ No. of DARs Submitted", value=f"{num_dars}")
    #     col2.metric(label="💰 Total Revenue Involved", value=f"₹{total_detected:.2f} Lakhs")
    #     col3.metric(label="🏆 Total Revenue Recovered", value=f"₹{total_recovered:.2f} Lakhs")

    #     st.markdown(f"**Maximum DARs by:** `{max_group_str}`")
    #     st.markdown(f"**Audit Groups with Zero DARs:** `{zero_dar_groups_str}`")

    #     # --- Para Status Distribution (uses original full data) ---
    #     st.markdown("---")
    #     st.markdown("<h4>Para Status Distribution</h4>", unsafe_allow_html=True)
    #     if 'status_of_para' in df_viz_data.columns and df_viz_data['status_of_para'].nunique() > 1:
    #         viz_status_counts = df_viz_data['status_of_para'].value_counts().reset_index()
    #         viz_status_counts.columns = ['Status of para', 'Count']
    #         viz_fig_status_dist = px.bar(viz_status_counts, x='Status of para', y='Count', text_auto=True, title="Distribution of Para Statuses", labels={'Status of para': '<b>Status</b>', 'Count': 'Number of Paras'})
    #         viz_fig_status_dist.update_layout(xaxis_title_font_size=14, yaxis_title_font_size=14, xaxis_tickfont_size=12, yaxis_tickfont_size=12, xaxis_type='category')
    #         viz_fig_status_dist.update_traces(textposition='outside', marker_color='teal')
    #         st.plotly_chart(viz_fig_status_dist, use_container_width=True)
    #     else:
    #         st.info("Not enough data for 'Status of para' distribution chart.")

    #     # --- Group-wise Performance (uses de-duplicated data and shows in Lakhs) ---
    #     st.markdown("---")
    #     st.markdown("<h4>Group-wise Performance</h4>", unsafe_allow_html=True)
    #     if 'Detection in Lakhs' in df_unique_reports.columns and (df_unique_reports['audit_group_number'].nunique() > 1 or (df_unique_reports['audit_group_number'].nunique() == 1 and df_unique_reports['audit_group_number'].iloc[0] != 0)):
    #         viz_detection_data = df_unique_reports.groupby('audit_group_number_str')['Detection in Lakhs'].sum().reset_index().sort_values(by='Detection in Lakhs', ascending=False).nlargest(5, 'Detection in Lakhs')
    #         if not viz_detection_data.empty:
    #             st.write("**Top 5 Groups by Total Detection Amount (Lakhs Rs):**")
    #             fig_det_grp = px.bar(viz_detection_data, x='audit_group_number_str', y='Detection in Lakhs', text_auto='.2f', labels={'Detection in Lakhs': 'Total Detection (Lakhs Rs)', 'audit_group_number_str': '<b>Audit Group</b>'})
    #             fig_det_grp.update_layout(xaxis_title_font_size=14, yaxis_title_font_size=14, xaxis_tickfont_size=12, yaxis_tickfont_size=12, xaxis_type='category')
    #             fig_det_grp.update_traces(textposition='outside', marker_color='indianred')
    #             st.plotly_chart(fig_det_grp, use_container_width=True)
        
    #     if 'Recovery in Lakhs' in df_unique_reports.columns and (df_unique_reports['audit_group_number'].nunique() > 1 or (df_unique_reports['audit_group_number'].nunique() == 1 and df_unique_reports['audit_group_number'].iloc[0] != 0)):
    #         viz_recovery_data = df_unique_reports.groupby('audit_group_number_str')['Recovery in Lakhs'].sum().reset_index().sort_values(by='Recovery in Lakhs', ascending=False).nlargest(5, 'Recovery in Lakhs')
    #         if not viz_recovery_data.empty:
    #             st.write("**Top 5 Groups by Total Realisation Amount (Lakhs Rs):**")
    #             fig_rec_grp = px.bar(viz_recovery_data, x='audit_group_number_str', y='Recovery in Lakhs', text_auto='.2f', labels={'Recovery in Lakhs': 'Total Realisation (Lakhs Rs)', 'audit_group_number_str': '<b>Audit Group</b>'})
    #             fig_rec_grp.update_layout(xaxis_title_font_size=14, yaxis_title_font_size=14, xaxis_tickfont_size=12, yaxis_tickfont_size=12, xaxis_type='category')
    #             fig_rec_grp.update_traces(textposition='outside', marker_color='lightseagreen')
    #             st.plotly_chart(fig_rec_grp, use_container_width=True)

    #     # --- Circle-wise Performance (uses de-duplicated data and shows in Lakhs) ---
    #     st.markdown("---")
    #     st.markdown("<h4>Circle-wise Performance Metrics</h4>", unsafe_allow_html=True)
    #     if 'circle_number_str_plot' in df_unique_reports and (df_unique_reports['circle_number_for_plot'].nunique() > 1 or (df_unique_reports['circle_number_for_plot'].nunique() == 1 and df_unique_reports['circle_number_for_plot'].iloc[0] != 0)):
    #         if 'Recovery in Lakhs' in df_unique_reports.columns:
    #             recovery_per_circle_plot = df_unique_reports.groupby('circle_number_str_plot')['Recovery in Lakhs'].sum().reset_index().sort_values(by='Recovery in Lakhs', ascending=False)
    #             if not recovery_per_circle_plot.empty:
    #                 st.write("**Total Recovery Amount (Lakhs Rs) per Circle (Descending):**")
    #                 fig_rec_circle_plot = px.bar(recovery_per_circle_plot, x='circle_number_str_plot', y='Recovery in Lakhs', text_auto='.2f', labels={'Recovery in Lakhs': 'Total Recovery (Lakhs Rs)', 'circle_number_str_plot': '<b>Circle Number</b>'}, title="Circle-wise Total Recovery")
    #                 fig_rec_circle_plot.update_layout(xaxis_title_font_size=14, yaxis_title_font_size=14, xaxis_tickfont_size=12, yaxis_tickfont_size=12, xaxis_type='category')
    #                 fig_rec_circle_plot.update_traces(textposition='outside', marker_color='goldenrod')
    #                 st.plotly_chart(fig_rec_circle_plot, use_container_width=True)
            
    #         if 'Detection in Lakhs' in df_unique_reports.columns:
    #             # FIX: Define the dataframe before using it
    #             detection_per_circle_plot = df_unique_reports.groupby('circle_number_str_plot')['Detection in Lakhs'].sum().reset_index().sort_values(by='Detection in Lakhs', ascending=False)
    #             # FIX: Change the invalid syntax to a correct 'if' condition
    #             if not detection_per_circle_plot.empty:
    #                 st.write("**Total Detection Amount (Lakhs Rs) per Circle (Descending):**")
    #                 fig_det_circle_plot = px.bar(detection_per_circle_plot, x='circle_number_str_plot', y='Detection in Lakhs', text_auto='.2f', labels={'Detection in Lakhs': 'Total Detection (Lakhs Rs)', 'circle_number_str_plot': '<b>Circle Number</b>'}, title="Circle-wise Total Detection")
    #                 fig_det_circle_plot.update_layout(xaxis_title_font_size=14, yaxis_title_font_size=14, xaxis_tickfont_size=12, yaxis_tickfont_size=12, xaxis_type='category')
    #                 fig_det_circle_plot.update_traces(textposition='outside', marker_color='mediumseagreen')
    #                 st.plotly_chart(fig_det_circle_plot, use_container_width=True)

        # # --- Treemap Visualizations (uses de-duplicated data and shows in Lakhs) ---
        # st.markdown("---")
        # st.markdown("<h4>Detection and Recovery Treemaps by Trade Name</h4>", unsafe_allow_html=True)
        # if 'Detection in Lakhs' in df_unique_reports.columns:
        #     viz_df_detection_treemap = df_unique_reports[df_unique_reports['Detection in Lakhs'] > 0]
        #     if not viz_df_detection_treemap.empty:
        #         st.write("**Detection Amounts (Lakhs Rs) by Trade Name (Size: Amount, Color: Category)**")
        #         try:
        #             viz_fig_treemap_detection = px.treemap(viz_df_detection_treemap, path=[px.Constant("All Detections"), 'category', 'trade_name'], values='Detection in Lakhs', color='category', hover_name='trade_name', custom_data=['audit_group_number_str', 'trade_name'], color_discrete_map={'Large': 'rgba(230, 57, 70, 0.8)', 'Medium': 'rgba(241, 196, 15, 0.8)', 'Small': 'rgba(26, 188, 156, 0.8)', 'Unknown': 'rgba(149, 165, 166, 0.7)'})
        #             viz_fig_treemap_detection.update_layout(margin=dict(t=30, l=10, r=10, b=10))
        #             viz_fig_treemap_detection.data[0].textinfo = 'label+value'
        #             viz_fig_treemap_detection.update_traces(hovertemplate="<b>%{customdata[1]}</b><br>Category: %{parent}<br>Audit Group: %{customdata[0]}<br>Detection: %{value:,.2f} Lakhs Rs<extra></extra>")
        #             st.plotly_chart(viz_fig_treemap_detection, use_container_width=True)
        #         except Exception as e_viz_treemap_det:
        #             st.error(f"Could not generate detection treemap: {e_viz_treemap_det}")
        
        # if 'Recovery in Lakhs' in df_unique_reports.columns:
        #     viz_df_recovery_treemap = df_unique_reports[df_unique_reports['Recovery in Lakhs'] > 0]
        #     if not viz_df_recovery_treemap.empty:
        #         st.write("**Recovery Amounts (Lakhs Rs) by Trade Name (Size: Amount, Color: Category)**")
        #         try:
        #             viz_fig_treemap_recovery = px.treemap(viz_df_recovery_treemap, path=[px.Constant("All Recoveries"), 'category', 'trade_name'], values='Recovery in Lakhs', color='category', hover_name='trade_name', custom_data=['audit_group_number_str', 'trade_name'], color_discrete_map={'Large': 'rgba(230, 57, 70, 0.8)', 'Medium': 'rgba(241, 196, 15, 0.8)', 'Small': 'rgba(26, 188, 156, 0.8)', 'Unknown': 'rgba(149, 165, 166, 0.7)'})
        #             viz_fig_treemap_recovery.update_layout(margin=dict(t=30, l=10, r=10, b=10))
        #             viz_fig_treemap_recovery.data[0].textinfo = 'label+value'
        #             viz_fig_treemap_recovery.update_traces(hovertemplate="<b>%{customdata[1]}</b><br>Category: %{parent}<br>Audit Group: %{customdata[0]}<br>Recovery: %{value:,.2f} Lakhs Rs<extra></extra>")
        #             st.plotly_chart(viz_fig_treemap_recovery, use_container_width=True)
        #         except Exception as e_viz_treemap_rec:
        #             st.error(f"Could not generate recovery treemap: {e_viz_treemap_rec}")

        # # --- Para-wise Performance (uses original full data) ---
        # st.markdown("---")
        # st.markdown("<h4>Para-wise Performance</h4>", unsafe_allow_html=True)
        # if 'num_paras_to_show_pco' not in st.session_state:
        #     st.session_state.num_paras_to_show_pco = 5
        # viz_n_paras_input = st.text_input("Enter N for Top N Paras (e.g., 5):", value=str(st.session_state.num_paras_to_show_pco), key="pco_n_paras_input_final_v2")
        # viz_num_paras_show = st.session_state.num_paras_to_show_pco
        # try:
        #     viz_parsed_n = int(viz_n_paras_input)
        #     if viz_parsed_n < 1:
        #         viz_num_paras_show = 5
        #         st.warning("N must be positive. Showing Top 5.", icon="⚠️")
        #     elif viz_parsed_n > 50:
        #         viz_num_paras_show = 50
        #         st.warning("N capped at 50. Showing Top 50.", icon="⚠️")
        #     else:
        #         viz_num_paras_show = viz_parsed_n
        #     st.session_state.num_paras_to_show_pco = viz_num_paras_show
        # except ValueError:
        #     if viz_n_paras_input != str(st.session_state.num_paras_to_show_pco):
        #         st.warning(f"Invalid N ('{viz_n_paras_input}'). Using: {viz_num_paras_show}", icon="⚠️")
        
        # viz_df_paras_only = df_viz_data[df_viz_data['audit_para_number'].notna() & (~df_viz_data['audit_para_heading'].astype(str).isin(["N/A - Header Info Only (Add Paras Manually)", "Manual Entry Required", "Manual Entry - PDF Error", "Manual Entry - PDF Upload Failed"]))]
        # if 'revenue_involved_lakhs_rs' in viz_df_paras_only.columns:
        #     viz_top_det_paras = viz_df_paras_only.nlargest(viz_num_paras_show, 'revenue_involved_lakhs_rs')
        #     if not viz_top_det_paras.empty:
        #         st.write(f"**Top {viz_num_paras_show} Detection Paras (by Revenue Involved):**")
        #         viz_disp_cols_det = ['audit_group_number_str', 'trade_name', 'audit_para_number', 'audit_para_heading', 'revenue_involved_lakhs_rs', 'status_of_para']
        #         viz_existing_cols_det = [c for c in viz_disp_cols_det if c in viz_top_det_paras.columns]
        #         st.dataframe(viz_top_det_paras[viz_existing_cols_det].rename(columns={'audit_group_number_str': 'Audit Group'}), use_container_width=True)
        # if 'revenue_recovered_lakhs_rs' in viz_df_paras_only.columns:
        #     viz_top_rec_paras = viz_df_paras_only.nlargest(viz_num_paras_show, 'revenue_recovered_lakhs_rs')
        #     if not viz_top_rec_paras.empty:
        #         st.write(f"**Top {viz_num_paras_show} Realisation Paras (by Revenue Recovered):**")
        #         viz_disp_cols_rec = ['audit_group_number_str', 'trade_name', 'audit_para_number', 'audit_para_heading', 'revenue_recovered_lakhs_rs', 'status_of_para']
        #         viz_existing_cols_rec = [c for c in viz_disp_cols_rec if c in viz_top_rec_paras.columns]
        #         st.dataframe(viz_top_rec_paras[viz_existing_cols_rec].rename(columns={'audit_group_number_str': 'Audit Group'}), use_container_width=True)

    # ========================== REPORTS TAB ==========================
    elif selected_tab == "Reports":
        pco_reports_dashboard(dbx)

    st.markdown("</div>", unsafe_allow_html=True)
# import streamlit as st
# import datetime
# import time
# import pandas as pd
# import plotly.express as px
# from streamlit_option_menu import option_menu

# # Dropbox-based imports
# from dropbox_utils import read_from_spreadsheet, update_spreadsheet_from_df
# from config import MCM_PERIODS_INFO_PATH, MCM_DATA_PATH

# # Placeholders for other modules
# from ui_mcm_agenda import mcm_agenda_tab
# from ui_pco_reports import pco_reports_dashboard


# def pco_dashboard(dbx):
#     st.markdown("<div class='sub-header'>Planning & Coordination Officer Dashboard</div>", unsafe_allow_html=True)

#     with st.sidebar:
#         try:
#             st.image("logo.png", width=80)
#         except Exception:
#             st.sidebar.markdown("*(Logo)*")
#         st.markdown(f"**User:** {st.session_state.username}")
#         st.markdown(f"**Role:** {st.session_state.role}")
#         if st.button("Logout", key="pco_logout", use_container_width=True):
#             st.session_state.logged_in = False
#             st.rerun()
#         st.markdown("---")
#         if st.button("🚀 Smart Audit Tracker", key="launch_sat_pco"):
#             st.session_state.app_mode = "smart_audit_tracker"
#             st.rerun()
#         st.markdown("---")
        
#     selected_tab = option_menu(
#         menu_title=None,
#         options=["Create/Manage Periods", "View Uploaded Reports", "MCM Agenda", "Visualizations", "Reports"],
#         icons=["calendar-plus-fill", "eye-fill", "journal-richtext", "bar-chart-fill", "file-earmark-text-fill"],
#         menu_icon="gear-wide-connected",
#         default_index=0,
#         orientation="horizontal",
#         styles={
#             "container": {"padding": "5px !important", "background-color": "#e9ecef"},
#             "icon": {"color": "#007bff", "font-size": "20px"},
#             "nav-link": {"font-size": "16px", "text-align": "center", "margin": "0px", "--hover-color": "#d1e7fd"},
#             "nav-link-selected": {"background-color": "#007bff", "color": "white"},
#         })

#     st.markdown("<div class='card'>", unsafe_allow_html=True)

#     if selected_tab == "Create/Manage Periods":
#         manage_mcm_periods_tab(dbx)
#     elif selected_tab == "View Uploaded Reports":
#         view_uploaded_reports_tab(dbx)
#     elif selected_tab == "MCM Agenda":
#         mcm_agenda_tab(dbx)
#     elif selected_tab == "Visualizations":
#         visualizations_tab(dbx)
#     elif selected_tab == "Reports":
#         pco_reports_dashboard(dbx)

#     st.markdown("</div>", unsafe_allow_html=True)

# def manage_mcm_periods_tab(dbx):
#     """A combined tab for creating, activating/deactivating, and managing MCM periods."""
#     st.markdown("<h3>Create New MCM Period</h3>", unsafe_allow_html=True)
    
#     with st.form("create_period_form"):
#         current_year = datetime.datetime.now().year
#         years = list(range(current_year - 1, current_year + 3))
#         months = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
        
#         col1, col2 = st.columns(2)
#         selected_year = col1.selectbox("Select Year", options=years, index=years.index(current_year))
#         selected_month = col2.selectbox("Select Month", options=months, index=datetime.datetime.now().month - 1)
        
#         submitted = st.form_submit_button(f"Create MCM for {selected_month} {selected_year}", use_container_width=True)
        
#         if submitted:
#             df_periods = read_from_spreadsheet(dbx, MCM_PERIODS_INFO_PATH)
#             period_key = f"{selected_month}_{selected_year}"
            
#             if not df_periods.empty and period_key in df_periods['key'].values:
#                 st.warning(f"MCM Period for {selected_month} {selected_year} already exists.")
#             else:
#                 new_period = pd.DataFrame([{"month_name": selected_month, "year": selected_year, "active": True, "key": period_key}])
#                 updated_df = pd.concat([df_periods, new_period], ignore_index=True)
                
#                 if update_spreadsheet_from_df(dbx, updated_df, MCM_PERIODS_INFO_PATH):
#                     st.success(f"Successfully created and activated MCM period for {selected_month} {selected_year}!")
#                     st.balloons()
#                     time.sleep(1)
#                     st.rerun()
#                 else:
#                     st.error("Failed to save the new MCM period to Dropbox.")

#     st.markdown("<hr>")
#     st.markdown("<h3>Manage Existing MCM Periods</h3>", unsafe_allow_html=True)
#     st.info("You can activate/deactivate periods or delete them using the editor. Changes are saved automatically.", icon="ℹ️")
    
#     df_periods_manage = read_from_spreadsheet(dbx, MCM_PERIODS_INFO_PATH)
    
#     if df_periods_manage.empty:
#         st.info("No MCM periods have been created yet.")
#         return

#     edited_df = st.data_editor(
#         df_periods_manage,
#         column_config={
#             "month_name": st.column_config.TextColumn("Month", disabled=True),
#             "year": st.column_config.NumberColumn("Year", disabled=True),
#             "active": st.column_config.CheckboxColumn("Active?", default=False),
#             "key": None
#         },
#         use_container_width=True,
#         hide_index=True,
#         num_rows="dynamic",
#         key="manage_periods_editor"
#     )
    
#     if not df_periods_manage.equals(edited_df):
#         if update_spreadsheet_from_df(dbx, edited_df, MCM_PERIODS_INFO_PATH):
#             st.toast("Changes saved successfully!")
#             time.sleep(1)
#             st.rerun()
#         else:
#             st.error("Failed to save changes to Dropbox.")

# def view_uploaded_reports_tab(dbx):
#     """Tab for viewing summaries and editing all submitted data."""
#     st.markdown("<h3>View Uploaded Reports</h3>", unsafe_allow_html=True)
    
#     df_periods = read_from_spreadsheet(dbx, MCM_PERIODS_INFO_PATH)
#     if df_periods.empty:
#         st.info("No MCM periods exist. Please create one first.")
#         return

#     period_options = df_periods.apply(lambda row: f"{row['month_name']} {row['year']}", axis=1).tolist()
#     selected_period = st.selectbox("Select MCM Period to View", options=period_options)

#     if not selected_period: return

#     with st.spinner("Loading all report data..."):
#         df_all_data = read_from_spreadsheet(dbx, MCM_DATA_PATH)

#     if df_all_data.empty:
#         st.info("No DARs have been submitted by any group yet.")
#         return

#     df_filtered = df_all_data[df_all_data['mcm_period'] == selected_period].copy()

#     if df_filtered.empty:
#         st.info(f"No data found for the period: {selected_period}")
#         return

#     st.markdown("#### Summary of Uploads")
#     df_filtered['audit_group_number'] = pd.to_numeric(df_filtered['audit_group_number'], errors='coerce')
#     dars_per_group = df_filtered.groupby('audit_group_number')['dar_pdf_path'].nunique().reset_index(name='DARs Uploaded')
#     paras_per_group = df_filtered.groupby('audit_group_number').size().reset_index(name='Total Para Entries')
    
#     col1, col2 = st.columns(2)
#     with col1:
#         st.write("**DARs Uploaded per Group:**")
#         st.dataframe(dars_per_group, use_container_width=True)
#     with col2:
#         st.write("**Para Entries per Group:**")
#         st.dataframe(paras_per_group, use_container_width=True)

#     st.markdown("<hr>")
#     st.markdown(f"#### Edit Detailed Data for {selected_period}")
#     st.info("You can edit data below. Click 'Save Changes' to update the master file.", icon="✍️")

#     edited_df = st.data_editor(df_filtered, use_container_width=True, hide_index=True, num_rows="dynamic", key=f"pco_editor_{selected_period}")

#     if st.button("Save Changes to Master File", type="primary"):
#         with st.spinner("Saving changes to Dropbox..."):
#             df_all_data.update(edited_df)
#             if update_spreadsheet_from_df(dbx, df_all_data, MCM_DATA_PATH):
#                 st.success("Changes saved successfully!")
#                 time.sleep(1); st.rerun()
#             else:
#                 st.error("Failed to save changes.")

# def visualizations_tab(dbx):
#     """Tab for displaying various data visualizations with restored functionality."""
#     st.markdown("<h3>Data Visualizations</h3>", unsafe_allow_html=True)
    
#     df_periods = read_from_spreadsheet(dbx, MCM_PERIODS_INFO_PATH)
#     if df_periods.empty:
#         st.info("No MCM periods exist to visualize.")
#         return
        
#     period_options = df_periods.apply(lambda row: f"{row['month_name']} {row['year']}", axis=1).tolist()
#     selected_period = st.selectbox("Select MCM Period for Visualization", options=period_options)

#     if not selected_period: return

#     with st.spinner("Loading data for visualizations..."):
#         df_viz = read_from_spreadsheet(dbx, MCM_DATA_PATH)
#         if df_viz.empty:
#             st.info("No data available to visualize."); return
#         df_viz = df_viz[df_viz['mcm_period'] == selected_period].copy()

#     if df_viz.empty:
#         st.info(f"No data to visualize for {selected_period}.")
#         return

#     # --- Data Cleaning and Preparation ---
#     amount_cols = ['total_amount_detected_overall_rs', 'total_amount_recovered_overall_rs', 'revenue_involved_lakhs_rs', 'revenue_recovered_lakhs_rs']
#     for col in amount_cols:
#         df_viz[col] = pd.to_numeric(df_viz[col], errors='coerce').fillna(0)
    
#     df_viz['audit_group_number'] = pd.to_numeric(df_viz['audit_group_number'], errors='coerce').fillna(0).astype(int)
#     df_viz['audit_circle_number'] = pd.to_numeric(df_viz['audit_circle_number'], errors='coerce').fillna(0).astype(int)
    
#     df_unique_dars = df_viz.drop_duplicates(subset=['dar_pdf_path']).copy()
#     df_unique_dars['Detection in Lakhs'] = df_unique_dars['total_amount_detected_overall_rs'] / 100000.0
#     df_unique_dars['Recovery in Lakhs'] = df_unique_dars['total_amount_recovered_overall_rs'] / 100000.0

#     # --- Summary Metrics ---
#     st.markdown("#### Monthly Performance Summary")
#     total_detected = df_unique_dars['Detection in Lakhs'].sum()
#     total_recovered = df_unique_dars['Recovery in Lakhs'].sum()
#     dars_per_group = df_unique_dars[df_unique_dars['audit_group_number'] > 0].groupby('audit_group_number')['dar_pdf_path'].nunique()

#     max_group_str = "N/A"
#     if not dars_per_group.empty:
#         max_dars_group = dars_per_group.idxmax()
#         max_group_str = f"AG {max_dars_group} ({dars_per_group.max()} DARs)"

#     all_audit_groups = set(range(1, 31))
#     submitted_groups = set(dars_per_group.index)
#     zero_dar_groups_str = ", ".join(map(str, sorted(list(all_audit_groups - submitted_groups)))) or "None"

#     col1, col2, col3 = st.columns(3)
#     col1.metric(label="✅ DARs Submitted", value=df_unique_dars['dar_pdf_path'].nunique())
#     col2.metric(label="💰 Total Detection", value=f"₹{total_detected:.2f} L")
#     col3.metric(label="🏆 Total Recovery", value=f"₹{total_recovered:.2f} L")
#     st.markdown(f"**Maximum DARs by:** `{max_group_str}`")
#     st.markdown(f"**Groups with Zero DARs:** `{zero_dar_groups_str}`")
#     st.markdown("---")

#     # --- Charts ---
#     st.markdown("<h4>Group & Circle Performance</h4>", unsafe_allow_html=True)
#     c1, c2 = st.columns(2)
#     with c1:
#         group_perf = df_unique_dars.groupby('audit_group_number')['Detection in Lakhs'].sum().nlargest(10).reset_index()
#         fig_group_det = px.bar(group_perf, x='audit_group_number', y='Detection in Lakhs', text_auto='.2f', title="Top 10 Groups by Detection")
#         st.plotly_chart(fig_group_det, use_container_width=True)
#     with c2:
#         circle_perf = df_unique_dars.groupby('audit_circle_number')['Detection in Lakhs'].sum().reset_index()
#         fig_circle_det = px.bar(circle_perf, x='audit_circle_number', y='Detection in Lakhs', text_auto='.2f', title="Detection by Circle")
#         st.plotly_chart(fig_circle_det, use_container_width=True)

#     st.markdown("---")
#     st.markdown("<h4>Para-wise Analysis</h4>", unsafe_allow_html=True)
    
#     # Treemap
#     st.write("**Detection Amounts by Trade Name (Size: Amount, Color: Category)**")
#     fig_treemap = px.treemap(df_unique_dars, path=[px.Constant("All"), 'category', 'trade_name'], values='Detection in Lakhs', color='category')
#     st.plotly_chart(fig_treemap, use_container_width=True)

#     # Top N Paras
#     st.write("**Top N Paras by Revenue Involved**")
#     n_paras = st.number_input("Select number of paras to show:", min_value=1, max_value=50, value=5, key="top_n_paras")
#     df_top_paras = df_viz.nlargest(n_paras, 'revenue_involved_lakhs_rs')
#     st.dataframe(df_top_paras[['audit_group_number', 'trade_name', 'audit_para_heading', 'revenue_involved_lakhs_rs']], use_container_width=True)
