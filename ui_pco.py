# ui_pco.py
import streamlit as st
import datetime
import time
import pandas as pd
import plotly.express as px
from streamlit_option_menu import option_menu

from dropbox_utils import read_from_spreadsheet, update_spreadsheet_from_df
from config import MCM_PERIODS_INFO_PATH, MCM_DATA_PATH
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
                        st.success(f"Successfully created MCM period for {selected_month} {selected_year}!")
                        st.balloons()
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("Failed to save the new MCM period.")

    elif selected_tab == "Manage MCM Periods":
        st.markdown("<h3>Manage Existing MCM Periods</h3>", unsafe_allow_html=True)
        st.info("You can activate/deactivate periods using the editor below.", icon="ℹ️")
        
        df_periods = read_from_spreadsheet(dbx, MCM_PERIODS_INFO_PATH)
        
        if df_periods is None or df_periods.empty:
            st.info("No MCM periods have been created yet.")
        else:
            edited_df = st.data_editor(
                df_periods,
                column_config={
                    "month_name": st.column_config.TextColumn("Month", disabled=True),
                    "year": st.column_config.NumberColumn("Year", disabled=True),
                    "active": st.column_config.CheckboxColumn("Active?", default=False),
                    "key": None
                },
                use_container_width=True,
                hide_index=True,
                num_rows="dynamic",
                key="manage_periods_editor"
            )
            
            if not df_periods.equals(edited_df):
                if update_spreadsheet_from_df(dbx, edited_df, MCM_PERIODS_INFO_PATH):
                    st.toast("Changes saved successfully!")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("Failed to save changes.")

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

        df_all_data = read_from_spreadsheet(dbx, MCM_DATA_PATH)
        if df_all_data is None or df_all_data.empty:
            st.info("No data available yet.")
            return

        df_filtered = df_all_data[df_all_data['mcm_period'] == selected_period].copy()
        if df_filtered.empty:
            st.info(f"No data found for {selected_period}.")
            return

        st.markdown("#### Summary of Uploads")
        df_filtered['audit_group_number'] = pd.to_numeric(df_filtered['audit_group_number'], errors='coerce')
        
        st.markdown("**DARs & Audit Paras Uploaded per Group:**")
        dars_per_group = df_filtered.groupby('audit_group_number')['dar_pdf_path'].nunique().reset_index(name='DARs Uploaded')
        paras_per_group = df_filtered.groupby('audit_group_number').size().reset_index(name='Audit Paras')
        group_summary = pd.merge(dars_per_group, paras_per_group, on='audit_group_number', how='outer').fillna(0)
        group_summary['DARs Uploaded'] = group_summary['DARs Uploaded'].astype(int)
        group_summary['Audit Paras'] = group_summary['Audit Paras'].astype(int)
        group_summary = group_summary.rename(columns={'audit_group_number': 'Audit Group Number'})
        st.dataframe(group_summary, use_container_width=True, hide_index=True)
        
        st.markdown("---")
        
        if 'status_of_para' in df_filtered.columns:
            st.markdown("**Para Status Summary:**")
            status_summary = df_filtered['status_of_para'].value_counts().reset_index(name='Count')
            status_summary.columns = ['Status of Para', 'Count']
            st.dataframe(status_summary, use_container_width=True, hide_index=True)

        st.markdown("---")
        st.markdown("#### Edit Detailed Data")
        edited_df = st.data_editor(df_filtered, use_container_width=True, hide_index=True, num_rows="dynamic")

        if st.button("Save Changes", type="primary"):
            df_all_data.update(edited_df)
            if update_spreadsheet_from_df(dbx, df_all_data, MCM_DATA_PATH):
                st.success("Changes saved!")
                st.rerun()
            else:
                st.error("Failed to save changes.")

    elif selected_tab == "MCM Agenda":
        mcm_agenda_tab(dbx)

    elif selected_tab == "Visualizations":
        st.markdown("<h3>Data Visualizations</h3>", unsafe_allow_html=True)
        
        df_periods = read_from_spreadsheet(dbx, MCM_PERIODS_INFO_PATH)
        if df_periods is None or df_periods.empty:
            st.info("No MCM periods exist.")
            return
            
        period_options = df_periods.apply(lambda row: f"{row['month_name']} {row['year']}", axis=1).tolist()
        selected_period = st.selectbox("Select MCM Period for Visualization", options=period_options)

        if not selected_period:
            return

        df_viz = read_from_spreadsheet(dbx, MCM_DATA_PATH)
        if df_viz is None or df_viz.empty:
            st.info("No data available.")
            return
            
        df_viz = df_viz[df_viz['mcm_period'] == selected_period].copy()
        if df_viz.empty:
            st.info(f"No data for {selected_period}.")
            return

        amount_cols = ['total_amount_detected_overall_rs', 'total_amount_recovered_overall_rs', 
                      'revenue_involved_lakhs_rs', 'revenue_recovered_lakhs_rs']
        for col in amount_cols:
            if col in df_viz.columns:
                df_viz[col] = pd.to_numeric(df_viz[col], errors='coerce').fillna(0)
        
        df_viz['audit_group_number'] = pd.to_numeric(df_viz['audit_group_number'], errors='coerce').fillna(0).astype(int)
        
        df_unique = df_viz.drop_duplicates(subset=['dar_pdf_path']).copy()
        df_unique['Detection in Lakhs'] = df_unique['total_amount_detected_overall_rs'] / 100000.0
        df_unique['Recovery in Lakhs'] = df_unique['total_amount_recovered_overall_rs'] / 100000.0

        st.markdown("#### Performance Summary")
        col1, col2, col3 = st.columns(3)
        col1.metric("DARs Submitted", df_unique['dar_pdf_path'].nunique())
        col2.metric("Total Detection", f"₹{df_unique['Detection in Lakhs'].sum():.2f} L")
        col3.metric("Total Recovery", f"₹{df_unique['Recovery in Lakhs'].sum():.2f} L")

        if 'status_of_para' in df_viz.columns:
            st.markdown("#### Para Status Distribution")
            status_counts = df_viz['status_of_para'].value_counts().reset_index()
            status_counts.columns = ['Status', 'Count']
            fig = px.bar(status_counts, x='Status', y='Count', title="Para Status Distribution")
            st.plotly_chart(fig, use_container_width=True)

        st.markdown("#### Top Groups by Detection")
        if df_unique['audit_group_number'].nunique() > 1:
            group_perf = df_unique.groupby('audit_group_number')['Detection in Lakhs'].sum().reset_index()
            group_perf = group_perf.sort_values('Detection in Lakhs', ascending=False).head(10)
            if not group_perf.empty:
                fig_group = px.bar(group_perf, x='audit_group_number', y='Detection in Lakhs', 
                                 title="Top Groups by Detection")
                st.plotly_chart(fig_group, use_container_width=True)

        st.markdown("#### Top Paras")
        n_paras = st.number_input("Number of paras to show:", min_value=1, max_value=50, value=5)
        
        df_paras = df_viz[df_viz['audit_para_number'].notna()]
        if 'revenue_involved_lakhs_rs' in df_paras.columns:
            top_paras = df_paras.nlargest(n_paras, 'revenue_involved_lakhs_rs')
            cols = ['audit_group_number', 'trade_name', 'audit_para_heading', 'revenue_involved_lakhs_rs']
            existing = [c for c in cols if c in top_paras.columns]
            st.dataframe(top_paras[existing], use_container_width=True)

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
