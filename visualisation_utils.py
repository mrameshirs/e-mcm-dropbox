# visualization_utils.py
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
import json
from dropbox_utils import read_from_spreadsheet
from config import MCM_DATA_PATH

# def get_visualization_data(dbx, selected_period):
#     """
#     COMPREHENSIVE helper function that extracts ALL visualization data and charts 
#     from the Visualizations tab in ui_pco.py. This function preserves EVERY chart,
#     analysis, and feature from the original implementation.
    
#     Returns vital_stats dict and list of plotly charts with all analysis features.
#     """
#     try:
#         # --- 1. Load and Filter Core Visualization Data (EXACT REPLICA) ---
#         df_viz_data = read_from_spreadsheet(dbx, MCM_DATA_PATH)
#         if df_viz_data is None or df_viz_data.empty:
#             return None, None
            
#         df_viz_data = df_viz_data[df_viz_data['mcm_period'] == selected_period].copy()
        
#         if df_viz_data.empty:
#             return None, None
        
#         # --- 2. Data Cleaning and Preparation (CONSOLIDATED - EXACT REPLICA) ---
#         amount_cols = [
#             'total_amount_detected_overall_rs', 'total_amount_recovered_overall_rs',
#             'revenue_involved_rs', 'revenue_recovered_rs', 'revenue_involved_lakhs_rs', 'revenue_recovered_lakhs_rs'
#         ]
#         for col in amount_cols:
#             if col in df_viz_data.columns:
#                 df_viz_data[col] = pd.to_numeric(df_viz_data[col], errors='coerce').fillna(0)
        
#         df_viz_data['Detection in Lakhs'] = df_viz_data.get('total_amount_detected_overall_rs', 0) / 100000.0
#         df_viz_data['Recovery in Lakhs'] = df_viz_data.get('total_amount_recovered_overall_rs', 0) / 100000.0
#         df_viz_data['Para Detection in Lakhs'] = df_viz_data.get('revenue_involved_rs', 0) / 100000.0
#         df_viz_data['Para Recovery in Lakhs'] = df_viz_data.get('revenue_recovered_rs', 0) / 100000.0
        
#         df_viz_data['audit_group_number'] = pd.to_numeric(df_viz_data.get('audit_group_number'), errors='coerce').fillna(0).astype(int)
#         df_viz_data['audit_circle_number'] = pd.to_numeric(df_viz_data.get('audit_circle_number'), errors='coerce').fillna(0).astype(int)
#         df_viz_data['audit_group_number_str'] = df_viz_data['audit_group_number'].astype(str)
#         df_viz_data['circle_number_str'] = df_viz_data['audit_circle_number'].astype(str)
        
#         df_viz_data['category'] = df_viz_data.get('category', 'Unknown').fillna('Unknown')
#         df_viz_data['trade_name'] = df_viz_data.get('trade_name', 'Unknown Trade Name').fillna('Unknown Trade Name')
#         df_viz_data['taxpayer_classification'] = df_viz_data.get('taxpayer_classification', 'Unknown').fillna('Unknown')
#         df_viz_data['para_classification_code'] = df_viz_data.get('para_classification_code', 'UNCLASSIFIED').fillna('UNCLASSIFIED')

#         # Unique reports for DAR-level analysis (EXACT REPLICA)
#         if 'dar_pdf_path' in df_viz_data.columns and df_viz_data['dar_pdf_path'].notna().any():
#             df_unique_reports = df_viz_data.drop_duplicates(subset=['dar_pdf_path']).copy()
#         else:
#             df_unique_reports = df_viz_data.drop_duplicates(subset=['gstin']).copy()
        
#         # --- 3. Monthly Performance Summary Metrics (EXACT REPLICA) ---
#         num_dars = df_unique_reports['dar_pdf_path'].nunique()
#         total_detected = df_unique_reports.get('Detection in Lakhs', 0).sum()
#         total_recovered = df_unique_reports.get('Recovery in Lakhs', 0).sum()
        
#         vital_stats = {
#             'num_dars': num_dars,
#             'total_detected': total_detected,
#             'total_recovered': total_recovered
#         }
        
#         # --- 4. Prepare Performance Summary Table Data (EXACT REPLICA) ---
#         categories_order = ['Large', 'Medium', 'Small']
#         dar_summary = df_unique_reports.groupby('category').agg(
#             dars_submitted=('dar_pdf_path', 'nunique'),
#             total_detected=('Detection in Lakhs', 'sum'),
#             total_recovered=('Recovery in Lakhs', 'sum')
#         )
#         df_actual_paras = df_viz_data[df_viz_data['audit_para_number'].notna() & 
#                                      (~df_viz_data['audit_para_heading'].astype(str).isin([
#                                          "N/A - Header Info Only (Add Paras Manually)", 
#                                          "Manual Entry Required", 
#                                          "Manual Entry - PDF Error", 
#                                          "Manual Entry - PDF Upload Failed"
#                                      ]))]
#         para_summary = df_actual_paras.groupby('category').size().reset_index(name='num_audit_paras').set_index('category')
#         summary_df = pd.concat([dar_summary, para_summary], axis=1).reindex(categories_order).fillna(0)
#         summary_df.reset_index(inplace=True)
        
#         # --- 5. Generate ALL Charts (COMPREHENSIVE REPLICA) ---
#         charts = []
        
#         # CHART 1: Performance Summary by Category (Bar Chart)
#         if not summary_df.empty:
#             fig1 = px.bar(summary_df, x='category', y='total_detected', 
#                          title="🎯 Detection Amount by Taxpayer Category",
#                          color='category',
#                          text_auto='.2f',
#                          color_discrete_sequence=['#3A86FF', '#3DCCC7', '#90E0EF'])
#             fig1.update_layout(
#                 title_x=0.5, 
#                 xaxis_title="Category", 
#                 yaxis_title="Detection (₹ Lakhs)",
#                 paper_bgcolor='#F0F2F6', 
#                 plot_bgcolor='#FFFFFF',
#                 font=dict(family="sans-serif", color="#333")
#             )
#             fig1.update_traces(textposition="outside", cliponaxis=False)
#             charts.append(fig1)
        
#         # CHART 2: Status of Para Analysis (EXACT REPLICA)
#         if 'status_of_para' in df_viz_data.columns:
#             df_status_analysis = df_viz_data[
#                 df_viz_data['status_of_para'].notna() & 
#                 (df_viz_data['status_of_para'] != '') &
#                 df_viz_data['audit_para_number'].notna()
#             ].copy()
            
#             if not df_status_analysis.empty:
#                 status_agg = df_status_analysis.groupby('status_of_para').agg(
#                     Para_Count=('status_of_para', 'count'),
#                     Total_Detection=('Para Detection in Lakhs', 'sum'),
#                     Total_Recovery=('Para Recovery in Lakhs', 'sum')
#                 ).reset_index()
                
#                 # Status Count Chart
#                 status_agg_sorted_count = status_agg.sort_values('Para_Count', ascending=False)
#                 fig2 = px.bar(
#                     status_agg_sorted_count,
#                     x='status_of_para',
#                     y='Para_Count',
#                     title="📊 Number of Audit Paras by Status",
#                     text_auto=True,
#                     color_discrete_sequence=px.colors.qualitative.Set3,
#                     labels={
#                         'status_of_para': 'Status of Para',
#                         'Para_Count': 'Number of Paras'
#                     }
#                 )
#                 fig2.update_layout(
#                     title_x=0.5,
#                     height=450,
#                     xaxis_title="Status of Para",
#                     yaxis_title="Number of Paras",
#                     xaxis={'tickangle': 45}
#                 )
#                 fig2.update_traces(textposition="outside", cliponaxis=False)
#                 charts.append(fig2)
                
#                 # Status Detection Chart
#                 status_agg_sorted_detection = status_agg.sort_values('Total_Detection', ascending=False)
#                 fig3 = px.bar(
#                     status_agg_sorted_detection,
#                     x='status_of_para',
#                     y='Total_Detection',
#                     title="📊 Detection Amount by Status",
#                     text_auto='.2f',
#                     color_discrete_sequence=px.colors.qualitative.Pastel1,
#                     labels={
#                         'status_of_para': 'Status of Para',
#                         'Total_Detection': 'Detection Amount (₹ Lakhs)'
#                     }
#                 )
#                 fig3.update_layout(
#                     title_x=0.5,
#                     height=450,
#                     xaxis_title="Status of Para",
#                     yaxis_title="Detection Amount (₹ Lakhs)",
#                     xaxis={'tickangle': 45}
#                 )
#                 fig3.update_traces(textposition="outside", cliponaxis=False)
#                 charts.append(fig3)
        
#         # CHARTS 4-5: Group & Circle Performance (EXACT REPLICA)
#         def style_chart(fig, title_text, y_title, x_title):
#             fig.update_layout(
#                 title_text=f"<b>{title_text}</b>", title_x=0.5,
#                 yaxis_title=f"<b>{y_title}</b>", xaxis_title=f"<b>{x_title}</b>",
#                 font=dict(family="sans-serif", color="#333"),
#                 paper_bgcolor='#F0F2F6', plot_bgcolor='#FFFFFF',
#                 xaxis_type='category',
#                 yaxis=dict(showgrid=True, gridcolor='#e5e5e5'),
#                 xaxis=dict(showgrid=False), height=400
#             )
#             fig.update_traces(marker_line=dict(width=1.5, color='#333'), textposition="outside", cliponaxis=False)
#             return fig
        
#         # Group Detection Performance
#         group_detection = df_unique_reports.groupby('audit_group_number_str')['Detection in Lakhs'].sum().nlargest(10).reset_index()
#         if not group_detection.empty:
#             fig4 = px.bar(group_detection, x='audit_group_number_str', y='Detection in Lakhs', 
#                          text_auto='.2f', color_discrete_sequence=px.colors.qualitative.Vivid)
#             fig4 = style_chart(fig4, "Top 10 Groups by Detection", "Amount (₹ Lakhs)", "Audit Group")
#             charts.append(fig4)
        
#         # Circle Detection Performance
#         circle_detection = df_unique_reports.groupby('circle_number_str')['Detection in Lakhs'].sum().sort_values(ascending=False).reset_index()
#         circle_detection = circle_detection[circle_detection['circle_number_str'] != '0']
#         if not circle_detection.empty:
#             fig5 = px.bar(circle_detection, x='circle_number_str', y='Detection in Lakhs', 
#                          text_auto='.2f', color_discrete_sequence=px.colors.qualitative.Pastel1)
#             fig5 = style_chart(fig5, "Circle-wise Detection", "Amount (₹ Lakhs)", "Audit Circle")
#             charts.append(fig5)
        
#         # Group Recovery Performance
#         group_recovery = df_unique_reports.groupby('audit_group_number_str')['Recovery in Lakhs'].sum().nlargest(10).reset_index()
#         if not group_recovery.empty:
#             fig6 = px.bar(group_recovery, x='audit_group_number_str', y='Recovery in Lakhs', 
#                          text_auto='.2f', color_discrete_sequence=px.colors.qualitative.Set2)
#             fig6 = style_chart(fig6, "Top 10 Groups by Recovery", "Amount (₹ Lakhs)", "Audit Group")
#             charts.append(fig6)
        
#         # Circle Recovery Performance
#         circle_recovery = df_unique_reports.groupby('circle_number_str')['Recovery in Lakhs'].sum().sort_values(ascending=False).reset_index()
#         circle_recovery = circle_recovery[circle_recovery['circle_number_str'] != '0']
#         if not circle_recovery.empty:
#             fig7 = px.bar(circle_recovery, x='circle_number_str', y='Recovery in Lakhs', 
#                          text_auto='.2f', color_discrete_sequence=px.colors.qualitative.G10)
#             fig7 = style_chart(fig7, "Circle-wise Recovery", "Amount (₹ Lakhs)", "Audit Circle")
#             charts.append(fig7)
        
#         # CHARTS 8-9: Taxpayer Classification Analysis (EXACT REPLICA)
#         if 'taxpayer_classification' in df_unique_reports.columns:
#             class_counts = df_unique_reports['taxpayer_classification'].value_counts().reset_index()
#             class_counts.columns = ['classification', 'count']
            
#             fig8 = px.pie(class_counts, names='classification', values='count',
#                          title="Distribution of DARs by Taxpayer Classification",
#                          color_discrete_sequence=px.colors.sequential.Blues_r,
#                          labels={'classification': 'Taxpayer Classification', 'count': 'Number of DARs'})
#             fig8.update_traces(textposition='inside', textinfo='percent+label', pull=[0.05]*len(class_counts))
#             fig8.update_layout(legend_title="Classification", title_x=0.5)
#             charts.append(fig8)
            
#             # Detection Amount by Classification
#             class_agg = df_unique_reports.groupby('taxpayer_classification').agg(
#                 Total_Detection=('Detection in Lakhs', 'sum'),
#                 Total_Recovery=('Recovery in Lakhs', 'sum')
#             ).reset_index()
            
#             fig9 = px.pie(class_agg, names='taxpayer_classification', values='Total_Detection',
#                          title="Detection Amount by Taxpayer Classification",
#                          color_discrete_sequence=px.colors.sequential.Reds_r,
#                          labels={'taxpayer_classification': 'Classification', 'Total_Detection': 'Detection (₹ Lakhs)'})
#             fig9.update_traces(textposition='inside', textinfo='percent+label')
#             fig9.update_layout(legend_title="Classification", title_x=0.5)
#             charts.append(fig9)
def get_visualization_data(dbx, selected_period):
    """
    COMPREHENSIVE helper function that extracts ALL visualization data and charts 
    from the Visualizations tab in ui_pco.py. This function preserves EVERY chart,
    analysis, and feature from the original implementation.
    
    Returns vital_stats dict and list of plotly charts with all analysis features.
    """
    try:
        # --- 1. Load and Filter Core Visualization Data (EXACT REPLICA) ---
        df_viz_data = read_from_spreadsheet(dbx, MCM_DATA_PATH)
        if df_viz_data is None or df_viz_data.empty:
            return None, None
            
        df_viz_data = df_viz_data[df_viz_data['mcm_period'] == selected_period].copy()
        
        if df_viz_data.empty:
            return None, None
        
        # --- 2. Data Cleaning and Preparation (CONSOLIDATED - EXACT REPLICA) ---
        amount_cols = [
            'total_amount_detected_overall_rs', 'total_amount_recovered_overall_rs',
            'revenue_involved_rs', 'revenue_recovered_rs', 'revenue_involved_lakhs_rs', 'revenue_recovered_lakhs_rs'
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

        # Unique reports for DAR-level analysis (EXACT REPLICA)
        if 'dar_pdf_path' in df_viz_data.columns and df_viz_data['dar_pdf_path'].notna().any():
            df_unique_reports = df_viz_data.drop_duplicates(subset=['dar_pdf_path']).copy()
        else:
            df_unique_reports = df_viz_data.drop_duplicates(subset=['gstin']).copy()
        
        # --- 3. Monthly Performance Summary Metrics (EXACT REPLICA) ---
        num_dars = df_unique_reports['dar_pdf_path'].nunique()
        total_detected = df_unique_reports.get('Detection in Lakhs', 0).sum()
        total_recovered = df_unique_reports.get('Recovery in Lakhs', 0).sum()
        
        vital_stats = {
            'num_dars': num_dars,
            'total_detected': total_detected,
            'total_recovered': total_recovered
        }
        
        # --- 4. Prepare Performance Summary Table Data (EXACT REPLICA) ---
        categories_order = ['Large', 'Medium', 'Small']
        dar_summary = df_unique_reports.groupby('category').agg(
            dars_submitted=('dar_pdf_path', 'nunique'),
            total_detected=('Detection in Lakhs', 'sum'),
            total_recovered=('Recovery in Lakhs', 'sum')
        )
        df_actual_paras = df_viz_data[df_viz_data['audit_para_number'].notna() & 
                                     (~df_viz_data['audit_para_heading'].astype(str).isin([
                                         "N/A - Header Info Only (Add Paras Manually)", 
                                         "Manual Entry Required", 
                                         "Manual Entry - PDF Error", 
                                         "Manual Entry - PDF Upload Failed"
                                     ]))]
        para_summary = df_actual_paras.groupby('category').size().reset_index(name='num_audit_paras').set_index('category')
        summary_df = pd.concat([dar_summary, para_summary], axis=1).reindex(categories_order).fillna(0)
        summary_df.reset_index(inplace=True)
        
        # --- 5. Generate ALL Charts (COMPREHENSIVE REPLICA) ---
        charts = []
        
        # CHART 1: Performance Summary by Category (Bar Chart)
        if not summary_df.empty:
            # FIX: Filter out categories with zero detection to prevent ZeroDivisionError
            summary_df_filtered = summary_df[summary_df['total_detected'] > 0]
            if not summary_df_filtered.empty:
                fig1 = px.bar(summary_df_filtered, x='category', y='total_detected', 
                             title="🎯 Detection Amount by Taxpayer Category",
                             color='category',
                             text_auto='.2f',
                             color_discrete_sequence=['#3A86FF', '#3DCCC7', '#90E0EF'])
                fig1.update_layout(
                    title_x=0.5, 
                    xaxis_title="Category", 
                    yaxis_title="Detection (₹ Lakhs)",
                    paper_bgcolor='#F0F2F6', 
                    plot_bgcolor='#FFFFFF',
                    font=dict(family="sans-serif", color="#333")
                )
                fig1.update_traces(textposition="outside", cliponaxis=False)
                charts.append(fig1)
        
        # CHART 2 & 3: Status of Para Analysis (EXACT REPLICA)
        if 'status_of_para' in df_viz_data.columns:
            df_status_analysis = df_viz_data[
                df_viz_data['status_of_para'].notna() & 
                (df_viz_data['status_of_para'] != '') &
                df_viz_data['audit_para_number'].notna()
            ].copy()
            
            if not df_status_analysis.empty:
                status_agg = df_status_analysis.groupby('status_of_para').agg(
                    Para_Count=('status_of_para', 'count'),
                    Total_Detection=('Para Detection in Lakhs', 'sum'),
                    Total_Recovery=('Para Recovery in Lakhs', 'sum')
                ).reset_index()
                
                # Status Count Chart
                # FIX: Filter out statuses with zero paras
                status_agg_sorted_count = status_agg.sort_values('Para_Count', ascending=False)
                status_agg_sorted_count = status_agg_sorted_count[status_agg_sorted_count['Para_Count'] > 0]
                if not status_agg_sorted_count.empty:
                    fig2 = px.bar(
                        status_agg_sorted_count, x='status_of_para', y='Para_Count',
                        title="📊 Number of Audit Paras by Status", text_auto=True,
                        color_discrete_sequence=px.colors.qualitative.Set3,
                        labels={'status_of_para': 'Status of Para', 'Para_Count': 'Number of Paras'}
                    )
                    fig2.update_layout(title_x=0.5, height=450, xaxis_title="Status of Para",
                                     yaxis_title="Number of Paras", xaxis={'tickangle': 45})
                    fig2.update_traces(textposition="outside", cliponaxis=False)
                    charts.append(fig2)
                
                # Status Detection Chart
                # FIX: Filter out statuses with zero detection
                status_agg_sorted_detection = status_agg.sort_values('Total_Detection', ascending=False)
                status_agg_sorted_detection = status_agg_sorted_detection[status_agg_sorted_detection['Total_Detection'] > 0]
                if not status_agg_sorted_detection.empty:
                    fig3 = px.bar(
                        status_agg_sorted_detection, x='status_of_para', y='Total_Detection',
                        title="📊 Detection Amount by Status", text_auto='.2f',
                        color_discrete_sequence=px.colors.qualitative.Pastel1,
                        labels={'status_of_para': 'Status of Para', 'Total_Detection': 'Detection Amount (₹ Lakhs)'}
                    )
                    fig3.update_layout(title_x=0.5, height=450, xaxis_title="Status of Para",
                                     yaxis_title="Detection Amount (₹ Lakhs)", xaxis={'tickangle': 45})
                    fig3.update_traces(textposition="outside", cliponaxis=False)
                    charts.append(fig3)
        
        # CHARTS 4-7: Group & Circle Performance (EXACT REPLICA)
        def style_chart(fig, title_text, y_title, x_title):
            fig.update_layout(
                title_text=f"<b>{title_text}</b>", title_x=0.5, yaxis_title=f"<b>{y_title}</b>",
                xaxis_title=f"<b>{x_title}</b>", font=dict(family="sans-serif", color="#333"),
                paper_bgcolor='#F0F2F6', plot_bgcolor='#FFFFFF', xaxis_type='category',
                yaxis=dict(showgrid=True, gridcolor='#e5e5e5'), xaxis=dict(showgrid=False), height=400
            )
            fig.update_traces(marker_line=dict(width=1.5, color='#333'), textposition="outside", cliponaxis=False)
            return fig
        
        # Group Detection Performance
        group_detection = df_unique_reports.groupby('audit_group_number_str')['Detection in Lakhs'].sum().nlargest(10).reset_index()
        # FIX: Filter zero values
        group_detection = group_detection[group_detection['Detection in Lakhs'] > 0]
        if not group_detection.empty:
            fig4 = px.bar(group_detection, x='audit_group_number_str', y='Detection in Lakhs', text_auto='.2f', color_discrete_sequence=px.colors.qualitative.Vivid)
            fig4 = style_chart(fig4, "Top 10 Groups by Detection", "Amount (₹ Lakhs)", "Audit Group")
            charts.append(fig4)
        
        # Circle Detection Performance
        circle_detection = df_unique_reports.groupby('circle_number_str')['Detection in Lakhs'].sum().sort_values(ascending=False).reset_index()
        circle_detection = circle_detection[circle_detection['circle_number_str'] != '0']
        # FIX: Filter zero values
        circle_detection = circle_detection[circle_detection['Detection in Lakhs'] > 0]
        if not circle_detection.empty:
            fig5 = px.bar(circle_detection, x='circle_number_str', y='Detection in Lakhs', text_auto='.2f', color_discrete_sequence=px.colors.qualitative.Pastel1)
            fig5 = style_chart(fig5, "Circle-wise Detection", "Amount (₹ Lakhs)", "Audit Circle")
            charts.append(fig5)
        
        # Group Recovery Performance
        group_recovery = df_unique_reports.groupby('audit_group_number_str')['Recovery in Lakhs'].sum().nlargest(10).reset_index()
        # FIX: Filter zero values
        group_recovery = group_recovery[group_recovery['Recovery in Lakhs'] > 0]
        if not group_recovery.empty:
            fig6 = px.bar(group_recovery, x='audit_group_number_str', y='Recovery in Lakhs', text_auto='.2f', color_discrete_sequence=px.colors.qualitative.Set2)
            fig6 = style_chart(fig6, "Top 10 Groups by Recovery", "Amount (₹ Lakhs)", "Audit Group")
            charts.append(fig6)
        
        # Circle Recovery Performance
        circle_recovery = df_unique_reports.groupby('circle_number_str')['Recovery in Lakhs'].sum().sort_values(ascending=False).reset_index()
        circle_recovery = circle_recovery[circle_recovery['circle_number_str'] != '0']
        # FIX: Filter zero values
        circle_recovery = circle_recovery[circle_recovery['Recovery in Lakhs'] > 0]
        if not circle_recovery.empty:
            fig7 = px.bar(circle_recovery, x='circle_number_str', y='Recovery in Lakhs', text_auto='.2f', color_discrete_sequence=px.colors.qualitative.G10)
            fig7 = style_chart(fig7, "Circle-wise Recovery", "Amount (₹ Lakhs)", "Audit Circle")
            charts.append(fig7)
        
        # CHARTS 8-9: Taxpayer Classification Analysis (EXACT REPLICA)
        if 'taxpayer_classification' in df_unique_reports.columns:
            class_counts = df_unique_reports['taxpayer_classification'].value_counts().reset_index()
            class_counts.columns = ['classification', 'count']
            # FIX: Filter zero values for safety
            class_counts = class_counts[class_counts['count'] > 0]
            if not class_counts.empty:
                fig8 = px.pie(class_counts, names='classification', values='count',
                             title="Distribution of DARs by Taxpayer Classification",
                             color_discrete_sequence=px.colors.sequential.Blues_r,
                             labels={'classification': 'Taxpayer Classification', 'count': 'Number of DARs'})
                fig8.update_traces(textposition='inside', textinfo='percent+label', pull=[0.05]*len(class_counts))
                fig8.update_layout(legend_title="Classification", title_x=0.5)
                charts.append(fig8)
            
            # Detection Amount by Classification
            class_agg = df_unique_reports.groupby('taxpayer_classification').agg(
                Total_Detection=('Detection in Lakhs', 'sum'),
                Total_Recovery=('Recovery in Lakhs', 'sum')
            ).reset_index()
            # FIX: Filter zero values
            class_agg = class_agg[class_agg['Total_Detection'] > 0]
            if not class_agg.empty:
                fig9 = px.pie(class_agg, names='taxpayer_classification', values='Total_Detection',
                             title="Detection Amount by Taxpayer Classification",
                             color_discrete_sequence=px.colors.sequential.Reds_r,
                             labels={'taxpayer_classification': 'Classification', 'Total_Detection': 'Detection (₹ Lakhs)'})
                fig9.update_traces(textposition='inside', textinfo='percent+label')
                fig9.update_layout(legend_title="Classification", title_x=0.5)
                charts.append(fig9)      
        # CHARTS 10-12: Nature of Compliance Analysis (EXACT REPLICA)
        CLASSIFICATION_CODES_DESC = {
            'TP': 'TAX PAYMENT DEFAULTS', 'RC': 'REVERSE CHARGE MECHANISM',
            'IT': 'INPUT TAX CREDIT VIOLATIONS', 'IN': 'INTEREST LIABILITY DEFAULTS',
            'RF': 'RETURN FILING NON-COMPLIANCE', 'PD': 'PROCEDURAL & DOCUMENTATION',
            'CV': 'CLASSIFICATION & VALUATION', 'SS': 'SPECIAL SITUATIONS',
            'PG': 'PENALTY & GENERAL COMPLIANCE'
        }
        
        df_paras = df_viz_data[df_viz_data['para_classification_code'] != 'UNCLASSIFIED'].copy()
        if not df_paras.empty:
            df_paras['major_code'] = df_paras['para_classification_code'].str[:2]
            major_code_agg = df_paras.groupby('major_code').agg(
                Para_Count=('major_code', 'count'),
                Total_Detection=('Para Detection in Lakhs', 'sum'),
                Total_Recovery=('Para Recovery in Lakhs', 'sum')
            ).reset_index()
            major_code_agg['description'] = major_code_agg['major_code'].map(CLASSIFICATION_CODES_DESC)
            
            # Paras by Classification
            fig10 = px.bar(major_code_agg, x='description', y='Para_Count', text_auto=True,
                          title="Number of Audit Paras by Classification",
                          labels={'description': 'Classification Code', 'Para_Count': 'Number of Paras'},
                          color_discrete_sequence=['#1f77b4'])
            fig10.update_layout(title_x=0.5, xaxis_title="Classification Code", yaxis_title="Number of Paras")
            fig10.update_traces(textposition="outside", cliponaxis=False)
            charts.append(fig10)
            
            # Detection by Classification
            fig11 = px.bar(major_code_agg, x='description', y='Total_Detection', text_auto='.2f',
                          title="Detection Amount by Classification",
                          labels={'description': 'Classification Code', 'Total_Detection': 'Detection (₹ Lakhs)'},
                          color_discrete_sequence=['#ff7f0e'])
            fig11.update_layout(title_x=0.5, xaxis_title="Classification Code", yaxis_title="Detection (₹ Lakhs)")
            fig11.update_traces(textposition="outside", cliponaxis=False)
            charts.append(fig11)
            
            # Recovery by Classification
            fig12 = px.bar(major_code_agg, x='description', y='Total_Recovery', text_auto='.2f',
                          title="Recovery Amount by Classification",
                          labels={'description': 'Classification Code', 'Total_Recovery': 'Recovery (₹ Lakhs)'},
                          color_discrete_sequence=['#2ca02c'])
            fig12.update_layout(title_x=0.5, xaxis_title="Classification Code", yaxis_title="Recovery (₹ Lakhs)")
            fig12.update_traces(textposition="outside", cliponaxis=False)
            charts.append(fig12)
        
        # CHARTS 13-14: Treemap Analysis (EXACT REPLICA)
        df_treemap = df_unique_reports.dropna(subset=['category', 'trade_name']).copy()
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
                fig13 = px.treemap(
                    df_det_treemap, path=[px.Constant("All Detections"), 'category', 'trade_name'],
                    values='Detection in Lakhs', color='category', color_discrete_map=color_map,
                    custom_data=['audit_group_number_str', 'trade_name'],
                    title="Detection by Trade Name"
                )
                fig13.update_layout(
                    title_x=0.5, 
                    margin=dict(t=50, l=25, r=25, b=25), 
                    paper_bgcolor='#F0F2F6',
                    font=dict(family="sans-serif")
                )
                fig13.update_traces(
                    marker_line_width=2, marker_line_color='white',
                    hovertemplate="<b>%{customdata[1]}</b><br>Category: %{parent}<br>Detection: %{value:,.2f} L<extra></extra>"
                )
                charts.append(fig13)
            except Exception:
                pass  # Skip treemap if it fails
        
        # Recovery Treemap
        df_rec_treemap = df_treemap[df_treemap['Recovery in Lakhs'] > 0]
        if not df_rec_treemap.empty:
            try:
                fig14 = px.treemap(
                    df_rec_treemap, path=[px.Constant("All Recoveries"), 'category', 'trade_name'],
                    values='Recovery in Lakhs', color='category', color_discrete_map=color_map,
                    custom_data=['audit_group_number_str', 'trade_name'],
                    title="Recovery by Trade Name"
                )
                fig14.update_layout(
                    title_x=0.5,
                    margin=dict(t=50, l=25, r=25, b=25), 
                    paper_bgcolor='#F0F2F6',
                    font=dict(family="sans-serif")
                )
                fig14.update_traces(
                    marker_line_width=2, marker_line_color='white',
                    hovertemplate="<b>%{customdata[1]}</b><br>Category: %{parent}<br>Recovery: %{value:,.2f} L<extra></extra>"
                )
                charts.append(fig14)
            except Exception:
                pass  # Skip treemap if it fails
        
        # CHARTS 15-18: Risk Parameter Analysis (COMPREHENSIVE REPLICA)
        GST_RISK_PARAMETERS = {
            "P01": "Sale turnover (GSTR-3B) is less than the purchase turnover", 
            "P02": "IGST paid on import is more than the ITC availed in GSTR-3B",
            "P03": "High ratio of nil-rated/exempt supplies to total turnover",
            "P04": "High ratio of zero-rated supplies to total turnover", 
            "P05": "High ratio of inward supplies liable to reverse charge to total turnover",
            "P06": "Mismatch between RCM liability declared and ITC claimed on RCM",
            "P07": "High ratio of tax paid through ITC to total tax payable",
            "P08": "Low ratio of tax payment in cash to total tax liability",
            "P09": "Decline in average monthly taxable turnover in GSTR-3B",
            "P10": "High ratio of non-GST supplies to total turnover", 
            "P11": "Taxpayer has filed more than six GST returns late",
            "P12": "Taxpayer has not filed three consecutive GSTR-3B returns",
            "P13": "Taxpayer has both SEZ and non-SEZ registrations with the same PAN in the same state",
            "P14": "Positive difference between ITC availed in GSTR-3B and ITC available in GSTR-2A",
            "P15": "Positive difference between ITC on import of goods (GSTR-3B) and IGST paid at Customs",
            "P16": "Low ratio of tax paid under RCM compared to ITC claimed on RCM",
            "P17": "High ratio of ISD credit to total ITC availed",
            "P18": "Low ratio of ITC reversed to total ITC availed",
            "P19": "Mismatch between the proportion of exempt supplies and the proportion of ITC reversed",
            "P20": "Mismatch between the taxable value of exports in GSTR-1 and the IGST value in shipping bills (Customs data)",
            "P21": "High ratio of zero-rated supply to SEZ to total GST turnover",
            "P22": "High ratio of deemed exports to total GST turnover", 
            "P23": "High ratio of zero-rated supply (other than exports) to total supplies",
            "P24": "Risk associated with other linked GSTINs of the same PAN",
            "P25": "High amount of IGST Refund claimed (for Risky Exporters)",
            "P26": "High amount of LUT Export Refund claimed (for Risky Exporters)",
            "P27": "High amount of Refund claimed due to inverted duty structure (for Risky Exporters)",
            "P28": "Taxpayer is flagged in Red Flag Reports of DGARM",
            "P29": "High ratio of taxable turnover as per ITC-04 vs. total turnover in GSTR-3B", 
            "P30": "Taxpayer was selected for audit on risk criteria last year but was not audited",
            "P31": "High ratio of Credit Notes to total taxable turnover value",
            "P32": "High ratio of Debit Notes to total taxable turnover value",
            "P33": "Substantial difference between turnover in GSTR-3B and turnover in Income Tax Return (ITR)",
            "P34": "Negligible income tax payment despite substantial turnover in GSTR-3B"
        }
        
        if 'risk_flags_data' in df_viz_data.columns:
            risk_para_records = []
            valid_risk_data = df_viz_data[
                df_viz_data['risk_flags_data'].notna() & 
                (df_viz_data['risk_flags_data'] != '') & 
                (df_viz_data['risk_flags_data'] != '[]') &
                (df_viz_data['risk_flags_data'].astype(str) != 'nan')
            ]
            
            # Process risk data (EXACT REPLICA of processing logic)
            for idx, row in valid_risk_data.iterrows():
                try:
                    risk_data_str = str(row['risk_flags_data']).strip()
                    
                    if risk_data_str.startswith('[') or risk_data_str.startswith('{'):
                        risk_list = json.loads(risk_data_str)
                    else:
                        risk_list = [{"risk_flag": risk_data_str, "paras": [row.get('audit_para_number', 1)]}]
                    
                    if isinstance(risk_list, list):
                        for risk_item in risk_list:
                            if isinstance(risk_item, dict):
                                risk_flag = risk_item.get("risk_flag", risk_item.get("risk_parameter", "Unknown"))
                                paras = risk_item.get("paras", [row.get('audit_para_number', 1)])
                            else:
                                risk_flag = str(risk_item)
                                paras = [row.get('audit_para_number', 1)]
                            
                            if risk_flag and paras:
                                for para_num in paras:
                                    risk_para_records.append({
                                        "gstin": row['gstin'], 
                                        "audit_para_number": para_num, 
                                        "risk_flag": risk_flag
                                    })
                    else:
                        risk_flag = str(risk_list)
                        risk_para_records.append({
                            "gstin": row['gstin'], 
                            "audit_para_number": row.get('audit_para_number', 1), 
                            "risk_flag": risk_flag
                        })
                except Exception:
                    continue
            
            if risk_para_records:
                df_risk_long = pd.DataFrame(risk_para_records)
                df_risk_long['audit_para_number'] = pd.to_numeric(df_risk_long['audit_para_number'], errors='coerce')
                
                df_risk_analysis = pd.merge(
                    df_viz_data.dropna(subset=['audit_para_number']), 
                    df_risk_long, 
                    on=['gstin', 'audit_para_number'], 
                    how='inner'
                )
                
                if not df_risk_analysis.empty:
                    risk_agg = df_risk_analysis.groupby('risk_flag').agg(
                        Para_Count=('risk_flag', 'count'),
                        Total_Detection=('Para Detection in Lakhs', 'sum'),
                        Total_Recovery=('Para Recovery in Lakhs', 'sum')
                    ).reset_index()
                    
                    # Risk Paras Chart
                    risk_agg_sorted_count = risk_agg.sort_values('Para_Count', ascending=False).head(15)
                    fig15 = px.bar(
                        risk_agg_sorted_count, 
                        x='risk_flag', 
                        y='Para_Count', 
                        text_auto=True,
                        title="Top 15 Risk Flags by Number of Audit Paras",
                        color_discrete_sequence=px.colors.qualitative.Bold
                    )
                    fig15.update_layout(
                        title_x=0.5,
                        xaxis_title="Risk Flag",
                        yaxis_title="Number of Paras",
                        height=500
                    )
                    fig15.update_traces(textposition="outside", cliponaxis=False)
                    charts.append(fig15)
                    
                    # Risk Detection Chart
                    risk_agg_sorted_det = risk_agg.sort_values('Total_Detection', ascending=False).head(10)
                    if not risk_agg_sorted_det.empty and risk_agg_sorted_det['Total_Detection'].sum() > 0:
                        fig16 = px.bar(
                            risk_agg_sorted_det, 
                            x='risk_flag', 
                            y='Total_Detection', 
                            text_auto='.2f',
                            title="Top 10 Detection Amount by Risk Flag",
                            color_discrete_sequence=px.colors.qualitative.Prism
                        )
                        fig16.update_layout(
                            title_x=0.5,
                            xaxis_title="Risk Flag",
                            yaxis_title="Amount (₹ Lakhs)",
                            height=400
                        )
                        fig16.update_traces(textposition="outside", cliponaxis=False)
                        charts.append(fig16)
                    
                    # Risk Recovery Chart
                    risk_agg_sorted_rec = risk_agg.sort_values('Total_Recovery', ascending=False).head(10)
                    if not risk_agg_sorted_rec.empty and risk_agg_sorted_rec['Total_Recovery'].sum() > 0:
                        fig17 = px.bar(
                            risk_agg_sorted_rec, 
                            x='risk_flag', 
                            y='Total_Recovery', 
                            text_auto='.2f',
                            title="Top 10 Recovery Amount by Risk Flag",
                            color_discrete_sequence=px.colors.qualitative.Safe
                        )
                        fig17.update_layout(
                            title_x=0.5,
                            xaxis_title="Risk Flag",
                            yaxis_title="Amount (₹ Lakhs)",
                            height=400
                        )
                        fig17.update_traces(textposition="outside", cliponaxis=False)
                        charts.append(fig17)
                    
                    # Risk Recovery Percentage Chart
                    risk_agg['Percentage_Recovery'] = (risk_agg['Total_Recovery'] / risk_agg['Total_Detection'].replace(0, np.nan)).fillna(0) * 100
                    risk_with_recovery = risk_agg[risk_agg['Total_Detection'] > 0]
                    if not risk_with_recovery.empty:
                        risk_agg_sorted_perc = risk_with_recovery.sort_values('Percentage_Recovery', ascending=False).head(10)
                        fig18 = px.bar(
                            risk_agg_sorted_perc, 
                            x='risk_flag', 
                            y='Percentage_Recovery',
                            title="Top 10 Percentage Recovery by Risk Flag",
                            color='Percentage_Recovery', 
                            color_continuous_scale=px.colors.sequential.Greens
                        )
                        fig18.update_traces(texttemplate='%{y:.1f}%', textposition='outside', cliponaxis=False)
                        fig18.update_layout(
                            title_x=0.5,
                            xaxis_title="Risk Flag",
                            yaxis_title="Recovery (%)",
                            height=400,
                            coloraxis_showscale=False
                        )
                        charts.append(fig18)
        
        # Add additional summary data for detailed analysis
        vital_stats.update({
            'categories_summary': summary_df.to_dict('records') if not summary_df.empty else [],
            'status_analysis_available': 'status_of_para' in df_viz_data.columns,
            'classification_analysis_available': not df_paras.empty if 'df_paras' in locals() else False,
            'risk_analysis_available': 'risk_flags_data' in df_viz_data.columns,
            'taxpayer_classification_available': 'taxpayer_classification' in df_unique_reports.columns
        })
        
        return vital_stats, charts
        
    except Exception as e:
        print(f"Error in get_visualization_data: {e}")
        import traceback
        traceback.print_exc()
        return None, None

def get_agreed_yet_to_pay_analysis(dbx, selected_period):
    """
    Helper function to get the "Agreed yet to pay" analysis data
    This replicates the specific analysis from the original visualization tab
    """
    try:
        df_viz_data = read_from_spreadsheet(dbx, MCM_DATA_PATH)
        if df_viz_data is None or df_viz_data.empty:
            return None
            
        df_viz_data = df_viz_data[df_viz_data['mcm_period'] == selected_period].copy()
        
        if df_viz_data.empty:
            return None
        
        # Data preparation
        df_viz_data['Para Detection in Lakhs'] = df_viz_data.get('revenue_involved_rs', 0) / 100000.0
        df_viz_data['Para Recovery in Lakhs'] = df_viz_data.get('revenue_recovered_rs', 0) / 100000.0
        df_viz_data['audit_group_number_str'] = df_viz_data.get('audit_group_number', '').astype(str)
        
        if 'status_of_para' not in df_viz_data.columns:
            return None
            
        # Filter for "Agreed yet to pay" status (EXACT REPLICA)
        df_status_analysis = df_viz_data[
            df_viz_data['status_of_para'].notna() & 
            (df_viz_data['status_of_para'] != '') &
            df_viz_data['audit_para_number'].notna()
        ].copy()
        
        if df_status_analysis.empty:
            return None
            
        agreed_yet_to_pay_paras = df_status_analysis[
            df_status_analysis['status_of_para'].str.contains('Agreed yet to pay', case=False, na=False)
        ].copy()
        
        if agreed_yet_to_pay_paras.empty:
            # Try alternative search terms (EXACT REPLICA)
            agreed_yet_to_pay_paras = df_status_analysis[
                df_status_analysis['status_of_para'].str.contains('agreed.*pay|yet.*pay|pending.*payment', case=False, na=False)
            ].copy()
        
        if agreed_yet_to_pay_paras.empty:
            return None
            
        # Get top 5 by detection amount (EXACT REPLICA)
        top_5_agreed = agreed_yet_to_pay_paras.nlargest(5, 'Para Detection in Lakhs')
        
        # Summary metrics
        total_agreed_paras = len(agreed_yet_to_pay_paras)
        total_agreed_detection = agreed_yet_to_pay_paras['Para Detection in Lakhs'].sum()
        total_agreed_recovery = agreed_yet_to_pay_paras['Para Recovery in Lakhs'].sum()
        
        return {
            'top_5_paras': top_5_agreed,
            'total_paras': total_agreed_paras,
            'total_detection': total_agreed_detection,
            'total_recovery': total_agreed_recovery
        }
        
    except Exception as e:
        print(f"Error in get_agreed_yet_to_pay_analysis: {e}")
        return None

def get_detailed_classification_analysis(dbx, selected_period):
    """
    Helper function to get detailed classification analysis
    This replicates the comprehensive classification breakdown from the original
    """
    try:
        df_viz_data = read_from_spreadsheet(dbx, MCM_DATA_PATH)
        if df_viz_data is None or df_viz_data.empty:
            return None
            
        df_viz_data = df_viz_data[df_viz_data['mcm_period'] == selected_period].copy()
        
        if df_viz_data.empty:
            return None
        
        # DETAILED_CLASSIFICATION_DESC from original code
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
        
        df_viz_data['Para Detection in Lakhs'] = df_viz_data.get('revenue_involved_rs', 0) / 100000.0
        df_viz_data['Para Recovery in Lakhs'] = df_viz_data.get('revenue_recovered_rs', 0) / 100000.0
        
        df_paras = df_viz_data[df_viz_data['para_classification_code'] != 'UNCLASSIFIED'].copy()
        if df_paras.empty:
            return None
            
        df_paras['major_code'] = df_paras['para_classification_code'].str[:2]
        
        # Get detailed analysis by major code
        detailed_analysis = {}
        unique_major_codes = df_paras['major_code'].unique()
        
        for code in sorted(unique_major_codes):
            df_filtered = df_paras[df_paras['major_code'] == code].copy()
            
            # Detection analysis
            det_agg = df_filtered.groupby('para_classification_code')['Para Detection in Lakhs'].sum().reset_index()
            det_agg['description'] = det_agg['para_classification_code'].map(DETAILED_CLASSIFICATION_DESC)
            
            # Recovery analysis  
            rec_agg = df_filtered.groupby('para_classification_code')['Para Recovery in Lakhs'].sum().reset_index()
            rec_agg['description'] = rec_agg['para_classification_code'].map(DETAILED_CLASSIFICATION_DESC)
            
            detailed_analysis[code] = {
                'detection_data': det_agg,
                'recovery_data': rec_agg
            }
        
        return detailed_analysis
        
    except Exception as e:
        print(f"Error in get_detailed_classification_analysis: {e}")
        return None
