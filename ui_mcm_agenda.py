# ui_mcm_agenda.py
import streamlit as st
import pandas as pd
import html
from io import BytesIO
import time

# PDF manipulation libraries
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.lib import colors
from reportlab.lib.units import inch
from PyPDF2 import PdfWriter, PdfReader

# Dropbox-based imports
from dropbox_utils import read_from_spreadsheet, download_file, update_spreadsheet_from_df
from config import MCM_PERIODS_INFO_PATH, MCM_DATA_PATH

# --- Helper Functions ---

def format_inr(n):
    """Formats a number into the Indian numbering system."""
    try:
        n = float(n)
        if pd.isna(n): return "0"
        n = int(n)
    except (ValueError, TypeError):
        return "0"
    
    s = str(n)
    if n < 0: return '-' + format_inr(-n)
    if len(s) <= 3: return s
    
    last_three = s[-3:]
    other_digits = s[:-3]
    groups = []
    while len(other_digits) > 2:
        groups.append(other_digits[-2:])
        other_digits = other_digits[:-2]
    if other_digits:
        groups.append(other_digits)
    
    return ','.join(reversed(groups)) + ',' + last_three

def create_cover_page_pdf(buffer, title_text, subtitle_text):
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=1.5*inch)
    styles = getSampleStyleSheet()
    story = []
    title_style = ParagraphStyle('Title', parent=styles['h1'], fontSize=28, alignment=TA_CENTER, spaceAfter=0.3*inch, textColor=colors.HexColor("#dc3545"))
    story.append(Paragraph(title_text, title_style))
    story.append(Spacer(1, 0.3*inch))
    subtitle_style = ParagraphStyle('Subtitle', parent=styles['h2'], fontSize=16, alignment=TA_CENTER)
    story.append(Paragraph(subtitle_text, subtitle_style))
    doc.build(story)
    buffer.seek(0)
    return buffer

def create_index_page_pdf(buffer, index_data_list):
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=0.75*inch, rightMargin=0.75*inch)
    styles = getSampleStyleSheet()
    story = [Paragraph("<b>Index of DARs</b>", styles['h1']), Spacer(1, 0.2*inch)]
    table_data = [[Paragraph("<b>Audit Circle</b>", styles['Normal']), Paragraph("<b>Trade Name of DAR</b>", styles['Normal']), Paragraph("<b>Start Page</b>", styles['Normal'])]]
    
    for item in index_data_list:
        table_data.append([
            Paragraph(str(item['circle']), styles['Normal']),
            Paragraph(html.escape(item['trade_name']), styles['Normal']),
            Paragraph(str(item['start_page']), styles['Normal'])
        ])
    
    index_table = Table(table_data, colWidths=[1.5*inch, 4*inch, 1.5*inch])
    index_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.darkgrey), ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    story.append(index_table)
    doc.build(story)
    buffer.seek(0)
    return buffer

def create_high_value_paras_pdf(buffer, df_high_value_paras):
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=0.75*inch, rightMargin=0.75*inch)
    styles = getSampleStyleSheet()
    story = [Paragraph("<b>High-Value Audit Paras (> ₹5 Lakhs Detection)</b>", styles['h1']), Spacer(1, 0.2*inch)]
    
    table_data = [[Paragraph("<b>Audit Group</b>", styles['Normal']), Paragraph("<b>Para No.</b>", styles['Normal']),
                   Paragraph("<b>Para Title</b>", styles['Normal']), Paragraph("<b>Detected (₹)</b>", styles['Normal']),
                   Paragraph("<b>Recovered (₹)</b>", styles['Normal'])]]
    
    for _, row in df_high_value_paras.iterrows():
        detected_val = row.get('revenue_involved_lakhs_rs', 0) * 100000
        recovered_val = row.get('revenue_recovered_lakhs_rs', 0) * 100000
        table_data.append([
            Paragraph(str(row.get("audit_group_number", "N/A")), styles['Normal']),
            Paragraph(str(row.get("audit_para_number", "N/A")), styles['Normal']),
            Paragraph(html.escape(str(row.get("audit_para_heading", "N/A"))[:100]), styles['Normal']),
            Paragraph(format_inr(detected_val), styles['Normal']),
            Paragraph(format_inr(recovered_val), styles['Normal'])
        ])
        
    hv_table = Table(table_data, colWidths=[1*inch, 0.7*inch, 3*inch, 1.4*inch, 1.4*inch])
    hv_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.darkgrey), ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (3,1), (-1,-1), 'RIGHT'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    story.append(hv_table)
    doc.build(story)
    buffer.seek(0)
    return buffer

# --- Main Tab Function ---

def mcm_agenda_tab(dbx):
    st.markdown("<h3>MCM Agenda Preparation</h3>", unsafe_allow_html=True)
    
    df_periods = read_from_spreadsheet(dbx, MCM_PERIODS_INFO_PATH)
    if df_periods.empty:
        st.warning("No MCM periods found."); return
        
    period_options = df_periods.apply(lambda row: f"{row['month_name']} {row['year']}", axis=1).tolist()
    selected_period = st.selectbox("Select MCM Period for Agenda", options=period_options)

    if not selected_period: return

    month_year_str = selected_period
    st.markdown(f"#### MCM Audit Paras for {month_year_str}")
    st.markdown("---")
    
    if 'mcm_agenda_df' not in st.session_state or st.session_state.get('mcm_agenda_period') != selected_period:
        with st.spinner(f"Loading data for {month_year_str}..."):
            df_all_data = read_from_spreadsheet(dbx, MCM_DATA_PATH)
            df_all_data.reset_index(inplace=True) # Preserve original index for updating
            df_period = df_all_data[df_all_data['mcm_period'] == selected_period].copy()
            st.session_state.mcm_agenda_df = df_period
            st.session_state.mcm_agenda_period = selected_period

    df_period_data = st.session_state.mcm_agenda_df

    if df_period_data.empty:
        st.info(f"No data found for {month_year_str}."); return

    # --- UI Loop for Circles, Groups, and Paras ---
    for circle_num in sorted(df_period_data['audit_circle_number'].dropna().unique()):
        with st.expander(f"Audit Circle {int(circle_num)}"):
            df_circle = df_period_data[df_period_data['audit_circle_number'] == circle_num]
            group_tabs = st.tabs([f"Audit Group {int(g)}" for g in sorted(df_circle['audit_group_number'].unique())])

            for i, group_num in enumerate(sorted(df_circle['audit_group_number'].unique())):
                with group_tabs[i]:
                    df_group = df_circle[df_circle['audit_group_number'] == group_num]
                    for trade_name in sorted(df_group['trade_name'].unique()):
                        df_trade = df_group[df_group['trade_name'] == trade_name]
                        
                        c1, c2 = st.columns([0.7, 0.3])
                        pdf_path = df_trade['dar_pdf_path'].iloc[0]
                        if c1.button(trade_name, key=f"btn_{trade_name}_{group_num}", use_container_width=True):
                            st.session_state[f"show_{trade_name}_{group_num}"] = not st.session_state.get(f"show_{trade_name}_{group_num}", False)
                        
                        if pd.notna(pdf_path):
                            # Construct a direct download link if possible, or a link to the file page
                            c2.link_button("View DAR PDF", f"https://www.dropbox.com/home{pdf_path}", use_container_width=True)

                        if st.session_state.get(f"show_{trade_name}_{group_num}", False):
                            with st.container(border=True):
                                gstin = df_trade['gstin'].iloc[0]; category = df_trade['category'].iloc[0]
                                info_cols = st.columns(2)
                                info_cols[0].metric("GSTIN", gstin); info_cols[1].metric("Category", category)
                                
                                st.markdown("##### Audit Paras & MCM Decisions")
                                for index, row in df_trade.iterrows():
                                    para_num = int(row["audit_para_number"]) if pd.notna(row["audit_para_number"]) else "N/A"
                                    st.markdown(f"**Para {para_num}:** {row.get('audit_para_heading', 'N/A')}")
                                    
                                    p_cols = st.columns(4)
                                    p_cols[0].metric("Detection (₹)", format_inr(row.get('revenue_involved_lakhs_rs', 0) * 100000))
                                    p_cols[1].metric("Recovery (₹)", format_inr(row.get('revenue_recovered_lakhs_rs', 0) * 100000))
                                    p_cols[2].metric("Status", row.get('status_of_para', 'N/A'))
                                    
                                    options = ['Select a decision', 'Para closed since recovered', 'Para deferred', 'Para to be pursued else issue SCN']
                                    current = row.get('mcm_decision'); 
                                    current = current if pd.notna(current) and current in options else options[0]
                                    sel_decision = p_cols[3].selectbox("MCM Decision", options=options, index=options.index(current), key=f"dec_{index}")
                                    
                                    if sel_decision != current:
                                        st.session_state.mcm_agenda_df.loc[st.session_state.mcm_agenda_df['index'] == index, 'mcm_decision'] = sel_decision
                                        st.rerun()
                                st.markdown("---")
    
    if st.button("Save All Decisions", type="primary"):
        with st.spinner("Saving decisions..."):
            df_master = read_from_spreadsheet(dbx, MCM_DATA_PATH)
            if 'mcm_decision' not in df_master.columns:
                df_master['mcm_decision'] = ""
            
            update_data = st.session_state.mcm_agenda_df.set_index('index')[['mcm_decision']]
            df_master.update(update_data)
            
            if update_spreadsheet_from_df(dbx, df_master, MCM_DATA_PATH):
                st.success("Decisions saved!")
            else:
                st.error("Failed to save decisions.")

    st.markdown("---")
    if st.button("Compile Full MCM Agenda PDF", use_container_width=True):
        with st.spinner("Compiling PDF Agenda..."):
            final_merger = PdfWriter()
            
            # 1. Cover Page
            cover_buf = BytesIO(); create_cover_page_pdf(cover_buf, f"MCM Agenda: {month_year_str}", "Audit-I Commissionerate"); final_merger.append(PdfReader(cover_buf))
            
            # 2. High-Value Paras Page
            df_hv = df_period_data[df_period_data['revenue_involved_lakhs_rs'] * 100000 > 500000]
            if not df_hv.empty:
                hv_buf = BytesIO(); create_high_value_paras_pdf(hv_buf, df_hv); final_merger.append(PdfReader(hv_buf))

            # 3. Prepare for Index and Merging
            df_pdf = df_period_data.dropna(subset=['dar_pdf_path', 'trade_name', 'audit_circle_number']).drop_duplicates(subset=['dar_pdf_path']).sort_values(by=['audit_circle_number', 'trade_name'])
            
            index_data, readers = [], {}; current_page = len(final_merger.pages) + 1
            prog_bar = st.progress(0, text="Downloading DAR PDFs...")
            for i, (_, row) in enumerate(df_pdf.iterrows()):
                content = download_file(dbx, row['dar_pdf_path'])
                if content: readers[row['dar_pdf_path']] = PdfReader(BytesIO(content))
                prog_bar.progress((i + 1) / len(df_pdf), text=f"Downloading DARs... ({i+1}/{len(df_pdf)})")

            # 4. Create Index Page
            for _, row in df_pdf.iterrows():
                reader = readers.get(row['dar_pdf_path'])
                pages = len(reader.pages) if reader else 0
                index_data.append({'circle': f"Circle {int(row['audit_circle_number'])}", 'trade_name': row['trade_name'], 'start_page': current_page})
                current_page += pages
            
            index_buf = BytesIO(); create_index_page_pdf(index_buf, index_data); final_merger.append(PdfReader(index_buf))
            
            # 5. Merge DARs
            prog_bar.progress(0, text="Merging PDFs...")
            for i, (_, row) in enumerate(df_pdf.iterrows()):
                if readers.get(row['dar_pdf_path']): final_merger.append(readers[row['dar_pdf_path']])
                prog_bar.progress((i + 1) / len(df_pdf), text=f"Merging PDFs... ({i+1}/{len(df_pdf)})")

            # 6. Finalize and Download
            output_pdf_bytes = BytesIO()
            final_merger.write(output_pdf_bytes)
            output_pdf_bytes.seek(0)

            prog_bar.empty()
            st.success("PDF Compilation Complete!")
            st.download_button(
                "⬇️ Download Compiled PDF Agenda",
                data=output_pdf_bytes,
                file_name=f"MCM_Agenda_{month_year_str.replace(' ', '_')}.pdf",
                mime="application/pdf"
            )
# # ui_mcm_agenda.py
# import streamlit as st
# import pandas as pd
# import html
# from io import BytesIO

# # PDF manipulation libraries
# from reportlab.lib.pagesizes import A4
# from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
# from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
# from reportlab.lib.enums import TA_CENTER
# from reportlab.lib import colors
# from reportlab.lib.units import inch
# from PyPDF2 import PdfWriter, PdfReader

# # Dropbox-based imports
# from dropbox_utils import read_from_spreadsheet, download_file, update_spreadsheet_from_df
# from config import MCM_PERIODS_INFO_PATH, MCM_DATA_PATH

# # --- Helper Functions ---

# def format_inr(n):
#     """Formats a number into the Indian numbering system."""
#     try:
#         n = float(n)
#         if pd.isna(n): return "0"
#         n = int(n)
#     except (ValueError, TypeError):
#         return "0"
    
#     s = str(n)
#     if n < 0: return '-' + format_inr(-n)
#     if len(s) <= 3: return s
    
#     last_three = s[-3:]
#     other_digits = s[:-3]
#     return f"{other_digits[:-2]},{other_digits[-2:]},{last_three}" if other_digits else last_three

# def create_cover_page_pdf(buffer, title_text, subtitle_text):
#     doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=1.5*inch)
#     styles = getSampleStyleSheet()
#     story = []
#     title_style = ParagraphStyle('Title', parent=styles['h1'], fontSize=28, alignment=TA_CENTER, spaceAfter=0.3*inch, textColor=colors.HexColor("#dc3545"))
#     story.append(Paragraph(title_text, title_style))
#     story.append(Spacer(1, 0.3*inch))
#     subtitle_style = ParagraphStyle('Subtitle', parent=styles['h2'], fontSize=16, alignment=TA_CENTER)
#     story.append(Paragraph(subtitle_text, subtitle_style))
#     doc.build(story)
#     buffer.seek(0)
#     return buffer

# def create_index_page_pdf(buffer, index_data_list):
#     doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=0.75*inch, rightMargin=0.75*inch)
#     styles = getSampleStyleSheet()
#     story = [Paragraph("<b>Index of DARs</b>", styles['h1']), Spacer(1, 0.2*inch)]
#     table_data = [[Paragraph("<b>Audit Circle</b>", styles['Normal']), Paragraph("<b>Trade Name of DAR</b>", styles['Normal']), Paragraph("<b>Start Page</b>", styles['Normal'])]]
    
#     for item in index_data_list:
#         table_data.append([
#             Paragraph(str(item['circle']), styles['Normal']),
#             Paragraph(html.escape(item['trade_name']), styles['Normal']),
#             Paragraph(str(item['start_page']), styles['Normal'])
#         ])
    
#     index_table = Table(table_data, colWidths=[1.5*inch, 4*inch, 1.5*inch])
#     index_table.setStyle(TableStyle([
#         ('BACKGROUND', (0, 0), (-1, 0), colors.darkgrey), ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
#         ('GRID', (0, 0), (-1, -1), 1, colors.black)
#     ]))
#     story.append(index_table)
#     doc.build(story)
#     buffer.seek(0)
#     return buffer

# def create_high_value_paras_pdf(buffer, df_high_value_paras):
#     doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=0.75*inch, rightMargin=0.75*inch)
#     styles = getSampleStyleSheet()
#     story = [Paragraph("<b>High-Value Audit Paras (> ₹5 Lakhs Detection)</b>", styles['h1']), Spacer(1, 0.2*inch)]
    
#     table_data = [[Paragraph("<b>Audit Group</b>", styles['Normal']), Paragraph("<b>Para No.</b>", styles['Normal']),
#                    Paragraph("<b>Para Title</b>", styles['Normal']), Paragraph("<b>Detected (₹)</b>", styles['Normal']),
#                    Paragraph("<b>Recovered (₹)</b>", styles['Normal'])]]
    
#     for _, row in df_high_value_paras.iterrows():
#         detected_val = row.get('revenue_involved_lakhs_rs', 0) * 100000
#         recovered_val = row.get('revenue_recovered_lakhs_rs', 0) * 100000
#         table_data.append([
#             Paragraph(str(row.get("audit_group_number", "N/A")), styles['Normal']),
#             Paragraph(str(row.get("audit_para_number", "N/A")), styles['Normal']),
#             Paragraph(html.escape(str(row.get("audit_para_heading", "N/A"))[:100]), styles['Normal']),
#             Paragraph(format_inr(detected_val), styles['Normal']),
#             Paragraph(format_inr(recovered_val), styles['Normal'])
#         ])
        
#     hv_table = Table(table_data, colWidths=[1*inch, 0.7*inch, 3*inch, 1.4*inch, 1.4*inch])
#     hv_table.setStyle(TableStyle([
#         ('BACKGROUND', (0, 0), (-1, 0), colors.darkgrey), ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
#         ('ALIGN', (3,1), (-1,-1), 'RIGHT'),
#         ('GRID', (0, 0), (-1, -1), 1, colors.black)
#     ]))
#     story.append(hv_table)
#     doc.build(story)
#     buffer.seek(0)
#     return buffer

# # --- Main Tab Function ---

# def mcm_agenda_tab(dbx):
#     st.markdown("<h3>MCM Agenda Preparation</h3>", unsafe_allow_html=True)
    
#     df_periods = read_from_spreadsheet(dbx, MCM_PERIODS_INFO_PATH)
#     if df_periods.empty:
#         st.warning("No MCM periods found."); return
        
#     period_options = df_periods.apply(lambda row: f"{row['month_name']} {row['year']}", axis=1).tolist()
#     selected_period = st.selectbox("Select MCM Period for Agenda", options=period_options)

#     if not selected_period: return

#     month_year_str = selected_period
#     st.markdown(f"#### MCM Audit Paras for {month_year_str}")
#     st.markdown("---")
    
#     if 'mcm_agenda_df' not in st.session_state or st.session_state.get('mcm_agenda_period') != selected_period:
#         with st.spinner(f"Loading data for {month_year_str}..."):
#             df_all_data = read_from_spreadsheet(dbx, MCM_DATA_PATH)
#             df_all_data.reset_index(inplace=True) # Preserve original index for updating master file
#             df_period = df_all_data[df_all_data['mcm_period'] == selected_period].copy()
#             st.session_state.mcm_agenda_df = df_period
#             st.session_state.mcm_agenda_period = selected_period

#     df_period_data = st.session_state.mcm_agenda_df

#     if df_period_data.empty:
#         st.info(f"No data found for {month_year_str}."); return

#     # --- UI Loop for Circles, Groups, and Paras ---
#     for circle_num in sorted(df_period_data['audit_circle_number'].dropna().unique()):
#         with st.expander(f"Audit Circle {int(circle_num)}"):
#             df_circle = df_period_data[df_period_data['audit_circle_number'] == circle_num]
            
#             group_tabs = st.tabs([f"Audit Group {int(g)}" for g in sorted(df_circle['audit_group_number'].unique())])

#             for i, group_num in enumerate(sorted(df_circle['audit_group_number'].unique())):
#                 with group_tabs[i]:
#                     df_group = df_circle[df_circle['audit_group_number'] == group_num]
#                     for trade_name in sorted(df_group['trade_name'].unique()):
#                         df_trade = df_group[df_group['trade_name'] == trade_name]
                        
#                         # --- Trade Name Header with PDF Link ---
#                         c1, c2 = st.columns([0.7, 0.3])
#                         pdf_path = df_trade['dar_pdf_path'].iloc[0]
#                         if c1.button(trade_name, key=f"btn_{trade_name}_{group_num}", use_container_width=True):
#                             st.session_state[f"show_{trade_name}_{group_num}"] = not st.session_state.get(f"show_{trade_name}_{group_num}", False)
                        
#                         if pd.notna(pdf_path):
#                              c2.link_button("View DAR PDF", f"https://www.dropbox.com/home{pdf_path}", use_container_width=True)

#                         # --- Toggleable Para Details ---
#                         if st.session_state.get(f"show_{trade_name}_{group_num}", False):
#                             with st.container(border=True):
#                                 # Display GSTIN and Category
#                                 gstin = df_trade['gstin'].iloc[0]
#                                 category = df_trade['category'].iloc[0]
#                                 info_cols = st.columns(2)
#                                 info_cols[0].metric("GSTIN", gstin)
#                                 info_cols[1].metric("Category", category)
#                                 st.markdown("##### Audit Paras & MCM Decisions")
                                
#                                 # Display Paras in a grid
#                                 for index, row in df_trade.iterrows():
#                                     para_num = int(row["audit_para_number"]) if pd.notna(row["audit_para_number"]) else "N/A"
#                                     st.markdown(f"**Para {para_num}:** {row.get('audit_para_heading', 'N/A')}")
                                    
#                                     cols = st.columns(4)
#                                     cols[0].metric("Detection (₹)", format_inr(row.get('revenue_involved_lakhs_rs', 0) * 100000))
#                                     cols[1].metric("Recovery (₹)", format_inr(row.get('revenue_recovered_lakhs_rs', 0) * 100000))
#                                     cols[2].metric("Status", row.get('status_of_para', 'N/A'))

#                                     decision_options = ['Select a decision', 'Para closed since recovered', 'Para deferred', 'Para to be pursued else issue SCN']
#                                     current_decision = row.get('mcm_decision', 'Select a decision')
#                                     if pd.isna(current_decision) or current_decision not in decision_options:
#                                         current_decision = 'Select a decision'
                                    
#                                     selected_decision = cols[3].selectbox("MCM Decision", options=decision_options, index=decision_options.index(current_decision), key=f"decision_{index}")
                                    
#                                     # Update session state immediately on change
#                                     if selected_decision != current_decision:
#                                         st.session_state.mcm_agenda_df.loc[st.session_state.mcm_agenda_df['index'] == index, 'mcm_decision'] = selected_decision
#                                         st.rerun()
#                                 st.markdown("---")

#     if st.button("Save All Decisions", type="primary", use_container_width=True):
#         with st.spinner("Saving decisions to master file..."):
#             df_master = read_from_spreadsheet(dbx, MCM_DATA_PATH)
#             if 'mcm_decision' not in df_master.columns:
#                 df_master['mcm_decision'] = ""
            
#             # Prepare decisions to be updated
#             update_data = st.session_state.mcm_agenda_df.set_index('index')[['mcm_decision']]
#             df_master.update(update_data)

#             if update_spreadsheet_from_df(dbx, df_master, MCM_DATA_PATH):
#                 st.success("All decisions saved successfully!")
#             else:
#                 st.error("Failed to save decisions.")

#     st.markdown("---")
#     if st.button("Compile Full MCM Agenda PDF", use_container_width=True):
#         with st.spinner("Compiling PDF Agenda... This may take a while."):
#             final_pdf_merger = PdfWriter()
            
#             # 1. Create Cover Page
#             cover_buffer = BytesIO(); create_cover_page_pdf(cover_buffer, f"MCM Agenda: {month_year_str}", "Audit-I Commissionerate"); final_pdf_merger.append(PdfReader(cover_buffer))
            
#             # 2. Create High-Value Paras Page
#             df_hv = df_period_data[df_period_data['revenue_involved_lakhs_rs'] * 100000 > 500000].copy()
#             if not df_hv.empty:
#                 hv_buffer = BytesIO(); create_high_value_paras_pdf(hv_buffer, df_hv); final_pdf_merger.append(PdfReader(hv_buffer))

#             # 3. Prepare data for Index and Merging
#             df_for_pdf = df_period_data.dropna(subset=['dar_pdf_path', 'trade_name', 'audit_circle_number']).copy()
#             unique_dars = df_for_pdf.drop_duplicates(subset=['dar_pdf_path']).sort_values(by=['audit_circle_number', 'trade_name'])
            
#             index_data, dar_readers = [], {}
#             current_page_count = len(final_pdf_merger.pages) + 1 # Start after cover/hv page
            
#             progress_bar = st.progress(0, text="Downloading DAR PDFs...")
#             for i, (_, row) in enumerate(unique_dars.iterrows()):
#                 pdf_path = row['dar_pdf_path']
#                 pdf_content = download_file(dbx, pdf_path)
#                 if pdf_content:
#                     dar_readers[pdf_path] = PdfReader(BytesIO(pdf_content))
#                 progress_bar.progress((i + 1) / len(unique_dars), text=f"Downloading DARs... ({i+1}/{len(unique_dars)})")

#             # 4. Create Index Page
#             for _, row in unique_dars.iterrows():
#                 reader = dar_readers.get(row['dar_pdf_path'])
#                 num_pages = len(reader.pages) if reader else 0
#                 index_data.append({'circle': f"Circle {int(row['audit_circle_number'])}", 'trade_name': row['trade_name'], 'start_page': current_page_count})
#                 current_page_count += num_pages
            
#             index_buffer = BytesIO(); create_index_page_pdf(index_buffer, index_data); final_pdf_merger.append(PdfReader(index_buffer))
            
#             # 5. Merge DAR PDFs
#             progress_bar.progress(0, text="Merging PDFs...")
#             for i, (_, row) in enumerate(unique_dars.iterrows()):
#                 reader = dar_readers.get(row['dar_pdf_path'])
#                 if reader: final_pdf_merger.append(reader)
#                 progress_bar.progress((i + 1) / len(unique_dars), text=f"Merging PDFs... ({i+1}/{len(unique_dars)})")

#             # 6. Finalize and Download
#             output_pdf = BytesIO()
#             final_pdf_merger.write(output_pdf)
#             output_pdf.seek(0)

#             progress_bar.empty()
#             st.success("PDF Compilation Complete!")
#             st.download_button(
#                 label="⬇️ Download Compiled PDF Agenda",
#                 data=output_pdf,
#                 file_name=f"MCM_Agenda_{month_year_str.replace(' ', '_')}.pdf",
#                 mime="application/pdf"
#             )
# # # ui_mcm_agenda.py
# # import streamlit as st
# # import pandas as pd
# # import datetime
# # import math
# # from io import BytesIO
# # import html

# # # PDF manipulation libraries
# # from reportlab.lib.pagesizes import A4
# # from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
# # from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
# # from reportlab.lib.enums import TA_CENTER
# # from reportlab.lib import colors
# # from reportlab.lib.units import inch
# # from PyPDF2 import PdfWriter, PdfReader

# # # Custom utilities
# # from dropbox_utils import read_from_spreadsheet, download_file, update_spreadsheet_from_df
# # from config import MCM_DATA_PATH, MCM_PERIODS_INFO_PATH

# # # --- Helper Functions ---

# # def format_inr(n):
# #     """Formats a number into the Indian numbering system."""
# #     try:
# #         n = int(n)
# #     except (ValueError, TypeError):
# #         return "0"
# #     if n < 0:
# #         return '-' + format_inr(-n)
# #     s = str(n)
# #     if len(s) <= 3: return s
# #     s_last_three = s[-3:]
# #     s_remaining = s[:-3]
# #     groups = [s_remaining[max(0, i-2):i] for i in range(len(s_remaining), 0, -2)]
# #     return ','.join(reversed(groups)) + ',' + s_last_three

# # def create_cover_page_pdf(buffer, title_text, subtitle_text):
# #     doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=1.5*inch, bottomMargin=1.5*inch)
# #     styles = getSampleStyleSheet()
# #     story = []
# #     title_style = ParagraphStyle('CoverTitle', parent=styles['h1'], fontName='Helvetica-Bold', fontSize=28, alignment=TA_CENTER, textColor=colors.HexColor("#dc3545"), spaceBefore=1*inch)
# #     story.append(Paragraph(title_text, title_style))
# #     story.append(Spacer(1, 0.3*inch))
# #     subtitle_style = ParagraphStyle('CoverSubtitle', parent=styles['h2'], fontName='Helvetica', fontSize=16, alignment=TA_CENTER, textColor=colors.darkslategray)
# #     story.append(Paragraph(subtitle_text, subtitle_style))
# #     doc.build(story)
# #     buffer.seek(0)
# #     return buffer

# # def create_index_page_pdf(buffer, index_data_list):
# #     doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=0.75*inch, rightMargin=0.75*inch)
# #     styles = getSampleStyleSheet()
# #     story = [Paragraph("<b>Index of DARs</b>", styles['h1']), Spacer(1, 0.2*inch)]
# #     table_data = [[Paragraph("<b>Audit Circle</b>", styles['Normal']), Paragraph("<b>Trade Name of DAR</b>", styles['Normal']), Paragraph("<b>Start Page</b>", styles['Normal'])]]
# #     for item in index_data_list:
# #         table_data.append([Paragraph(str(item['circle']), styles['Normal']), Paragraph(html.escape(item['trade_name']), styles['Normal']), Paragraph(str(item['start_page']), styles['Normal'])])
    
# #     index_table = Table(table_data, colWidths=[1.5*inch, 4*inch, 1.5*inch])
# #     index_table.setStyle(TableStyle([
# #         ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#343a40")), ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
# #         ('ALIGN', (0, 0), (-1, -1), 'LEFT'), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
# #         ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'), ('GRID', (0, 0), (-1, -1), 1, colors.black)
# #     ]))
# #     story.append(index_table)
# #     doc.build(story)
# #     buffer.seek(0)
# #     return buffer

# # def create_high_value_paras_pdf(buffer, df_high_value):
# #     doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=0.75*inch, rightMargin=0.75*inch)
# #     styles = getSampleStyleSheet()
# #     story = [Paragraph("<b>High-Value Audit Paras (&gt; ₹5 Lakhs Detection)</b>", styles['h1']), Spacer(1, 0.2*inch)]
# #     table_data = [[Paragraph(f"<b>{col}</b>", styles['Normal']) for col in ["Audit Group", "Para No.", "Para Title", "Detected (₹)", "Recovered (₹)"]]]
# #     for _, row in df_high_value.iterrows():
# #         table_data.append([
# #             Paragraph(html.escape(str(row.get("audit_group_number", "N/A"))), styles['Normal']),
# #             Paragraph(html.escape(str(row.get("audit_para_number", "N/A"))), styles['Normal']),
# #             Paragraph(html.escape(str(row.get("audit_para_heading", "N/A"))[:100]), styles['Normal']),
# #             Paragraph(format_inr(row.get('revenue_involved_lakhs_rs', 0) * 100000), styles['Normal']),
# #             Paragraph(format_inr(row.get('revenue_recovered_lakhs_rs', 0) * 100000), styles['Normal'])
# #         ])
    
# #     hv_table = Table(table_data, colWidths=[1*inch, 0.7*inch, 3*inch, 1.4*inch, 1.4*inch])
# #     hv_table.setStyle(TableStyle([
# #         ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#343a40")), ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
# #         ('ALIGN', (0, 0), (-1, -1), 'LEFT'), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('ALIGN', (3,1), (-1,-1), 'RIGHT'),
# #         ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'), ('GRID', (0, 0), (-1, -1), 1, colors.black)
# #     ]))
# #     story.append(hv_table)
# #     doc.build(story)
# #     buffer.seek(0)
# #     return buffer

# # # --- Main Tab Function ---

# # def mcm_agenda_tab(dbx):
# #     st.markdown("### MCM Agenda Preparation")
    
# #     mcm_periods = read_from_spreadsheet(dbx, MCM_PERIODS_INFO_PATH)
# #     if mcm_periods.empty:
# #         st.warning("No MCM periods found. Please create them first.")
# #         return

# #     period_options = {f"{row['month_name']} {row['year']}": row for _, row in mcm_periods.iterrows()}
# #     selected_period_str = st.selectbox("Select MCM Period for Agenda", options=list(period_options.keys()))

# #     if not selected_period_str:
# #         st.info("Please select an MCM period.")
# #         return

# #     st.markdown(f"<h2 style='text-align: center; color: #007bff;'>MCM Audit Paras for {selected_period_str}</h2>", unsafe_allow_html=True)
# #     st.markdown("---")
    
# #     df_all_data = read_from_spreadsheet(dbx, MCM_DATA_PATH)
# #     if df_all_data is None or df_all_data.empty:
# #         st.info(f"No data found in the central data file.")
# #         return

# #     df_period_data = df_all_data[df_all_data['mcm_period'] == selected_period_str].copy()
# #     if df_period_data.empty:
# #         st.info(f"No data found for the selected period: {selected_period_str}")
# #         return
        
# #     # Data processing and UI rendering logic
# #     for col in ['audit_circle_number', 'audit_group_number', 'revenue_involved_lakhs_rs', 'revenue_recovered_lakhs_rs']:
# #         if col in df_period_data.columns:
# #             df_period_data[col] = pd.to_numeric(df_period_data[col], errors='coerce').fillna(0)

# #     for circle_num in range(1, 11):
# #         circle_label = f"Audit Circle {circle_num}"
# #         df_circle_data = df_period_data[df_period_data['audit_circle_number'] == circle_num]

# #         with st.expander(f"View Details for {circle_label}", expanded=False):
# #             if df_circle_data.empty:
# #                 st.write(f"No data for {circle_label}.")
# #                 continue
# #             # ... (rest of the detailed UI for displaying paras and decisions)

# #     # --- PDF Compilation Logic ---
# #     if st.button("Compile Full MCM Agenda PDF", type="primary", use_container_width=True):
# #         with st.spinner("Compiling PDF Agenda..."):
# #             final_pdf_merger = PdfWriter()
            
# #             # 1. Cover Page
# #             cover_buffer = BytesIO()
# #             create_cover_page_pdf(cover_buffer, f"Audit Paras for MCM {selected_period_str}", "Audit 1 Commissionerate Mumbai")
# #             final_pdf_merger.append(cover_buffer)
            
# #             # 2. High-Value Paras
# #             df_hv = df_period_data[df_period_data['revenue_involved_lakhs_rs'] * 100000 > 500000]
# #             if not df_hv.empty:
# #                 hv_buffer = BytesIO()
# #                 create_high_value_paras_pdf(hv_buffer, df_hv)
# #                 final_pdf_merger.append(hv_buffer)

# #             # 3. Index and DAR Merging
# #             df_for_pdf = df_period_data.dropna(subset=['dar_pdf_path', 'trade_name']).drop_duplicates(subset=['dar_pdf_path'])
# #             if not df_for_pdf.empty:
# #                 index_items = []
# #                 current_page = len(final_pdf_merger.pages) + 1 # Start after cover and HV pages
                
# #                 # First pass to build index data
# #                 for _, row in df_for_pdf.iterrows():
# #                     pdf_content = download_file(dbx, row['dar_pdf_path'])
# #                     if pdf_content:
# #                         reader = PdfReader(BytesIO(pdf_content))
# #                         num_pages = len(reader.pages)
# #                         index_items.append({'circle': row['audit_circle_number'], 'trade_name': row['trade_name'], 'start_page': current_page, 'reader': reader})
# #                         current_page += num_pages
                
# #                 # Create and add index page
# #                 index_buffer = BytesIO()
# #                 create_index_page_pdf(index_buffer, index_items)
# #                 final_pdf_merger.append(index_buffer)

# #                 # Second pass to merge DARs
# #                 for item in index_items:
# #                     final_pdf_merger.append(item['reader'])

# #             # Finalize PDF
# #             output_pdf = BytesIO()
# #             final_pdf_merger.write(output_pdf)
# #             output_pdf.seek(0)
            
# #             st.success("PDF Compilation Complete!")
# #             st.download_button(
# #                 label="⬇️ Download Compiled PDF Agenda",
# #                 data=output_pdf,
# #                 file_name=f"MCM_Agenda_{selected_period_str.replace(' ', '_')}.pdf",
# #                 mime="application/pdf"
# #             )
