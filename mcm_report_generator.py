#mcm_report_generator.py
import datetime
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, PageBreak, Frame, Table, TableStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from io import BytesIO
from svglib.svglib import svg2rlg
import os
import re
import xml.etree.ElementTree as ET
import pandas as pd
from reportlab.platypus import NextPageTemplate, PageTemplate, Frame
class PDFReportGenerator:
    """
    A structured PDF report generator with controlled chart placement and descriptions.
    """

    def __init__(self, selected_period, vital_stats, chart_images, chart_metadata=None):
        self.buffer = BytesIO()
        self.doc = SimpleDocTemplate(
            self.buffer, 
            pagesize=letter, 
            leftMargin=0.25*inch, 
            rightMargin=0.25*inch,
            topMargin=0.25*inch,
            bottomMargin=0.25*inch
        )
        self.story = []
        self.styles = getSampleStyleSheet()
        self.width, self.height = letter

        self.selected_period = selected_period
        self.vital_stats = vital_stats or {}  # Ensure it's a dict
        self.chart_images = chart_images
        
        # Chart metadata structure: [{"title": "Chart Title", "description": "Chart description", "page_break_after": True}, ...]
        self.chart_metadata = chart_metadata or self._generate_default_metadata()
        # Create chart registry for easy access
        self.chart_registry = self._create_chart_registry()
        # Register fonts with proper error handling
        self._register_fonts()
        self._setup_custom_styles()

    def _generate_default_metadata(self):
        """Generate enhanced default metadata with proper IDs from visualization charts"""
        chart_configs = [
            # Chart 1: Performance Summary by Category (fig1)
            {
                "id": "category_detection_performance",
                "title": "Detection Amount by Taxpayer Category", 
                "description": "Bar chart showing detection amounts across Large, Medium, and Small taxpayer categories.",
                "section": "performance_summary",
                "position": "after_metrics",
                "size": "medium"
            },
            # Chart 2: Status Count Chart (fig2)
            {
                "id": "status_para_count",
                "title": "Number of Audit Paras by Status",
                "description": "Distribution of audit paras by their current status (Agreed, Disputed, etc.).",
                "section": "status_analysis", 
                "position": "after_header",
                "size": "medium"
            },
            # Chart 3: Status Detection Chart (fig3)  
            {
                "id": "status_analysis",
                "title": "Detection Amount by Status",
                "description": "Analysis of detection amounts categorized by para status showing recovery potential.",
                "section": "status_analysis",
                "position": "after_table", 
                "size": "medium"
            },
            # Chart 4: Group Detection Performance (fig4)
            {
                "id": "group_detection_performance", 
                "title": "Top 10 Groups by Detection",
                "description": "Performance ranking of audit groups based on detection amounts.",
                "section": "performance_analysis",
                "position": "standalone",
                "size": "medium"
            },
            # Chart 5: Circle Detection Performance (fig5)
            {
                "id": "circle_detection_performance",
                "title": "Circle-wise Detection Performance", 
                "description": "Detection amounts across different audit circles showing regional performance.",
                "section": "performance_analysis",
                "position": "standalone",
                "size": "medium"
            },
            # Chart 6: Group Recovery Performance (fig6)
            {
                "id": "group_recovery_performance",
                "title": "Top 10 Groups by Recovery",
                "description": "Recovery performance ranking of audit groups.",
                "section": "performance_analysis", 
                "position": "standalone",
                "size": "medium"
            },
            # Chart 7: Circle Recovery Performance (fig7)
            {
                "id": "recovery_trends", 
                "title": "Circle-wise Recovery Performance",
                "description": "Recovery amounts across different audit circles showing collection efficiency.",
                "section": "status_analysis",
                "position": "after_table",
                "size": "medium"
            },
            # Chart 8: Taxpayer Classification Distribution (fig8)
            {
                "id": "taxpayer_classification_distribution",
                "title": "Distribution of DARs by Taxpayer Classification", 
                "description": "Pie chart showing distribution of Draft Audit Reports across taxpayer types.",
                "section": "sectoral_analysis",
                "position": "after_header",
                "size": "medium"
            },
            # Chart 9: Detection by Classification (fig9)
            {
                "id": "taxpayer_classification_detection",
                "title": "Detection Amount by Taxpayer Classification",
                "description": "Pie chart showing detection amounts distributed across different taxpayer classifications.",
                "section": "sectoral_analysis", 
                "position": "after_chart",
                "size": "medium"
            },
            # Chart 9b: Recovery by Classification (fig9b - NEW)
            {
                "id": "taxpayer_classification_recovery",
                "title": "Recovery Amount by Taxpayer Classification",
                "description": "Pie chart showing recovery amounts distributed across different taxpayer classifications.",
                "section": "sectoral_analysis", 
                "position": "after_chart",
                "size": "medium"
            },
            # Chart 10: Paras by Classification (fig10 -> now fig11)
            {
                "id": "classification_para_count",
                "title": "Number of Audit Paras by Categorisation", 
                "description": "Bar chart showing audit para counts across different non-compliance categories.",
                "section": "compliance_analysis",
                "position": "after_header",
                "size": "medium"
            },
            # Chart 11: Detection by Classification (fig11 -> now fig12)
            {
                "id": "classification_detection",
                "title": "Detection Amount by Categorisation",
                "description": "Detection amounts across different compliance violation categories.",
                "section": "compliance_analysis",
                "position": "after_chart", 
                "size": "medium"
            },
            # Chart 12: Recovery by Classification (fig12 -> now fig13)
            {
                "id": "classification_recovery",
                "title": "Recovery Amount by Categorisation", 
                "description": "Recovery amounts across different compliance violation categories.",
                "section": "compliance_analysis",
                "position": "after_chart",
                "size": "medium"
            },
            # Chart 13: Detection Treemap (fig13 -> now fig14)
            {
                "id": "detection_treemap",
                "title": "Detection by Trade Name Treemap",
                "description": "Hierarchical view of detection amounts by taxpayer category and trade name.",
                "section": "detailed_analysis",
                "position": "standalone", 
                "size": "large"
            },
            # Chart 14: Recovery Treemap (fig14 -> now fig15)
            {
                "id": "recovery_treemap", 
                "title": "Recovery by Trade Name Treemap",
                "description": "Hierarchical view of recovery amounts by taxpayer category and trade name.",
                "section": "detailed_analysis",
                "position": "standalone",
                "size": "large"
            },
            # Chart 15: Risk Paras Chart (fig15 -> now fig16)
            {
                "id": "risk_para_distribution",
                "title": "Top 15 Risk Flags by Number of Audit Paras", 
                "description": "Distribution of audit paras across different GST risk parameters.",
                "section": "risk_analysis",
                "position": "after_header",
                "size": "medium"
            },
            # Chart 16: Risk Detection Chart (fig16 -> now fig17) 
            {
                "id": "risk_detection_analysis",
                "title": "Top 10 Detection Amount by Risk Flag",
                "description": "Detection amounts associated with different risk parameters.",
                "section": "risk_analysis",
                "position": "after_chart",
                "size": "medium"
            },
            # Chart 17: Risk Recovery Chart (fig17 -> now fig18)
            {
                "id": "risk_recovery_analysis",
                "title": "Top 10 Recovery Amount by Risk Flag", 
                "description": "Recovery amounts associated with different risk parameters.",
                "section": "risk_analysis",
                "position": "after_chart",
                "size": "medium"
            },
            # Chart 18: Risk Recovery Percentage (fig18 -> now fig19)
            {
                "id": "risk_distribution",
                "title": "Top 10 Percentage Recovery by Risk Flag",
                "description": "Recovery efficiency percentages across different risk parameters.",
                "section": "risk_analysis",
                "position": "after_chart", 
                "size": "medium"
            }
        ]
        #ADD DETAILED CLASSIFICATION CHARTS (Charts 19+)
        # These correspond to the nc_tab2 and nc_tab3 detailed breakdown charts
        CLASSIFICATION_CODES_DESC = {
            'TP': 'TAX PAYMENT DEFAULTS', 'RC': 'REVERSE CHARGE MECHANISM',
            'IT': 'INPUT TAX CREDIT VIOLATIONS', 'IN': 'INTEREST LIABILITY DEFAULTS',
            'RF': 'RETURN FILING NON-COMPLIANCE', 'PD': 'PROCEDURAL & DOCUMENTATION',
            'CV': 'CLASSIFICATION & VALUATION', 'SS': 'SPECIAL SITUATIONS',
            'PG': 'PENALTY & GENERAL COMPLIANCE'
        }
        
        # Add detailed DETECTION charts for each classification code
        for code in ['TP', 'RC', 'IT', 'IN', 'RF', 'PD', 'CV', 'SS', 'PG']:
            chart_configs.append({
                "id": f"detailed_detection_{code}",
                "title": f"Detection for {code} - {CLASSIFICATION_CODES_DESC[code]}",
                "description": f"Detailed breakdown of detection amounts for {CLASSIFICATION_CODES_DESC[code]} subcategories.",
                "section": "detailed_compliance_analysis",
                "size": "medium"
            })
        
        # Add detailed RECOVERY charts for each classification code  
        for code in ['TP', 'RC', 'IT', 'IN', 'RF', 'PD', 'CV', 'SS', 'PG']:
            chart_configs.append({
                "id": f"detailed_recovery_{code}",
                "title": f"Recovery for {code} - {CLASSIFICATION_CODES_DESC[code]}",
                "description": f"Detailed breakdown of recovery amounts for {CLASSIFICATION_CODES_DESC[code]} subcategories.",
                "section": "detailed_compliance_analysis", 
                "size": "medium"
            })
        
        # Return only the number of charts that actually exist
        return chart_configs[:len(self.chart_images)]
      
        
    def add_section_highlight_bar(self, section_title,text_color, bar_color="#FAD6a5"):
        """Add a highlight bar for section separation"""
        try:
            # Create a table with colored background to act as highlight bar
            highlight_data = [[section_title]]
            highlight_table = Table(highlight_data, colWidths=[7*inch])
            
            # Style the highlight bar
            highlight_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor(bar_color)),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor(text_color)),
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 16),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('TOPPADDING', (0, 0), (-1, -1), 12),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
                ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ]))
            
            self.story.append(highlight_table)
            self.story.append(Spacer(1, 0.2 * inch))
            
        except Exception as e:
            print(f"Error adding section highlight bar: {e}")
            # Fallback to regular header if highlight bar fails
            fallback_style = ParagraphStyle(
                name='FallbackHeader',
                parent=self.styles['Heading2'],
                fontSize=16,
                textColor=colors.HexColor(bar_color),
                alignment=TA_CENTER,
                fontName='Helvetica-Bold',
                spaceAfter=16,
                spaceBefore=16
            )
            self.story.append(Paragraph(section_title, fallback_style))
        
    def _setup_custom_styles(self):
        """Setup custom paragraph styles for different content types"""
        self.chart_title_style = ParagraphStyle(
            name='ChartTitle',
            parent=self.styles['Heading2'],
            fontSize=14,  # CHANGED from 16
            textColor=colors.HexColor("#1F3A4D"),
            alignment=TA_CENTER,
            fontName='Helvetica-Bold',
            spaceAfter=6,   # CHANGED from 8
            spaceBefore=10  # CHANGED from 12
        )
        
        self.chart_description_style = ParagraphStyle(
            name='ChartDescription',
            parent=self.styles['Normal'],
            fontSize=10,    # CHANGED from 11
            textColor=colors.HexColor("#2C2C2C"),
            alignment=TA_JUSTIFY,
            fontName='Helvetica',
            spaceAfter=8,   # CHANGED from 16
            spaceBefore=4,  # CHANGED from 8
            leftIndent=0.25*inch,
            rightIndent=0.25*inch,
            leading=12,     # CHANGED from 13
            wordWrap='LTR'
        )
        """Setup custom paragraph styles for different content types"""
        self.chart_title_style = ParagraphStyle(
            name='ChartTitle',
            parent=self.styles['Heading2'],
            fontSize=16,
            textColor=colors.HexColor("#1F3A4D"),
            alignment=TA_CENTER,
            fontName='Helvetica-Bold',
            spaceAfter=8,  # Reduced from 12
            spaceBefore=12  # Reduced from 16
        )
        
        self.chart_description_style = ParagraphStyle(
            name='ChartDescription',
            parent=self.styles['Normal'],
            fontSize=11,
            textColor=colors.HexColor("#2C2C2C"),
            alignment=TA_JUSTIFY,
            fontName='Helvetica',
            spaceAfter=8,  # Reduced from 16
            spaceBefore=4,  # Reduced from 8
            leftIndent=0.25*inch,
            rightIndent=0.25*inch,
            leading=13,  # Reduced from 14
            wordWrap='LTR'  # Enable proper word wrapping
        )
        
        self.section_header_style = ParagraphStyle(
            name='SectionHeader',
            parent=self.styles['Heading1'],
            fontSize=20,
            textColor=colors.HexColor("#1F3A4D"),
            alignment=TA_CENTER,
            fontName='Helvetica-Bold',
            spaceAfter=16,
            spaceBefore=24
         )
        
 
    
    def _create_chart_registry(self):
        """Create a registry of charts with IDs for easy access - ENHANCED for all chart types"""
        registry = {}
        print(f"Creating chart registry with {len(self.chart_images)} images and {len(self.chart_metadata)} metadata entries")
        
        for i, chart_data in enumerate(self.chart_metadata):
            if i >= len(self.chart_images):
                print(f"Warning: Metadata entry {i} has no corresponding chart image")
                break
                
            chart_id = chart_data.get('id', f'chart_{i+1}')
            registry[chart_id] = {
                'index': i,
                'image': self.chart_images[i],
                'metadata': chart_data
            }
            print(f"Registered chart {i}: {chart_id} -> {chart_data.get('title', 'No title')}")
        
        print(f"Final registry keys: {list(registry.keys())}")
        return registry
    
    # def insert_chart_by_id(self, chart_id, size="medium", add_title=False, add_description=False):
    #     """Insert chart with proper scaling - FIXED for pie charts"""
    #     try:
    #         print('Processing Chart inside insert ',chart_id)
    #         if chart_id not in self.chart_registry:
    #             return False
    
    #         chart_info = self.chart_registry[chart_id]
    #         chart_data = chart_info['metadata']
    #         img_bytes = chart_info['image']
    
    #         if img_bytes is None:
    #             return False
    
    #         # Add title and description
    #         if add_title:
    #             self.story.append(Paragraph(chart_data.get('title', ''), self.chart_title_style))
    #         if add_description:
    #             self.story.append(Paragraph(chart_data.get('description', ''), self.chart_description_style))
    
    #         # Create drawing
    #         drawing, error = self._create_safe_svg_drawing(img_bytes)
            
    #         if error or drawing is None:
    #             return False
    
    #         # SPECIAL HANDLING FOR PIE CHARTS (square dimensions)
    #         # SPECIAL HANDLING FOR PIE CHARTS (maintain circular proportions)
    #         is_pie_row = 'combined' in chart_id or 'three_pie' in chart_id or 'taxpayer_classification_distribution' in chart_id
       
    #         #is_pie_chart = any(pie_id in chart_id for pie_id in [ 'classification_detection', 'classification_recovery'])
    #         if is_pie_row:
    #             # Wide format for three pies in row
    #             target_width = 8.5 * inch
    #             target_height = 4.5 * inch
    #         # elif is_pie_chart:
    #         #     # SQUARE dimensions for pie charts - CRITICAL for circular shape
    #         #     target_size = 3.0 * inch  # Same width and height
    #         #     target_width = target_size
    #         #     target_height = target_size
               
    #         #     # Force square aspect ratio
    #         #     original_width = getattr(drawing, 'width', 500)
    #         #     original_height = getattr(drawing, 'height', 500)
    #         #     print('Piechart found',original_width,original_height)
    #         #     # Use the same scale for both dimensions to maintain circular shape
    #         #     scale_factor = target_size / max(original_width, original_height)
    #         #     scale_x = scale_factor
    #         #     scale_y = scale_factor
    #         #     print('Scale factor ',scale_x,scale_y)
    #         else:
    #             # Regular sizing for other charts
    #             size_configs = {
    #                 "tiny": 3.5 * inch,
    #                 "small": 4 * inch,
    #                 "compact":4.5 * inch,
    #                 "medium": 5.0 * inch,
    #                 "large": 6.5 * inch
    #             }
    #             target_width = size_configs.get(size, 5.0 * inch)
    #             target_height = target_width * 0.6
    
    #         # Calculate scale factors
    #         original_width = getattr(drawing, 'width', 400)
    #         original_height = getattr(drawing, 'height', 400)
    #         scale_x = target_width / original_width
    #         scale_y = target_height / original_height
    
    #         # Create properly scaled drawing
    #         from reportlab.graphics.shapes import Drawing, Group
            
    #         scaled_drawing = Drawing(target_width, target_height)
    #         content_group = Group()
    #         content_group.transform = (scale_x, 0, 0, scale_y, 0, 0)
            
    #         # Add original contents
    #         if hasattr(drawing, 'contents'):
    #             for item in drawing.contents:
    #                 content_group.add(item)
            
    #         scaled_drawing.add(content_group)
    #         scaled_drawing.hAlign = 'CENTER'
            
    #         self.story.append(Spacer(1, 0.01 * inch))
    #         self.story.append(scaled_drawing)
    #         self.story.append(Spacer(1, 0.001 * inch))
            
    #         print(f"SUCCESS: Perfectly scaled chart '{chart_id}' added")
    #         return True
            
    #     except Exception as e:
    #         print(f"ERROR: {e}")
    #         return False
    def insert_chart_by_id(self, chart_id, size="medium", add_title=False, add_description=False):
        """Insert chart with proper scaling - ENHANCED for all chart types including detailed classification"""
        try:
            print(f'Processing Chart ID: {chart_id}')
            if chart_id not in self.chart_registry:
                print(f"Chart ID '{chart_id}' not found in registry")
                print(f"Available IDs: {list(self.chart_registry.keys())[:10]}...")  # Show first 10
                return False
    
            chart_info = self.chart_registry[chart_id]
            chart_data = chart_info['metadata']
            img_bytes = chart_info['image']
    
            if img_bytes is None:
                print(f"No image data for chart '{chart_id}'")
                return False
    
            # Add title and description with reduced spacing for detailed charts
            if add_title:
                # Use smaller title style for detailed charts
                title_style = self.chart_title_style
                if 'detailed_' in chart_id:
                    title_style = ParagraphStyle(
                        name='DetailedChartTitle',
                        parent=self.chart_title_style,
                        fontSize=12,  # Smaller font for detailed charts
                        spaceAfter=4,  # Less space after
                        spaceBefore=6  # Less space before
                    )
                self.story.append(Paragraph(chart_data.get('title', ''), title_style))
                
            if add_description:
                self.story.append(Paragraph(chart_data.get('description', ''), self.chart_description_style))
    
            # Create drawing
            drawing, error = self._create_safe_svg_drawing(img_bytes)
            
            if error or drawing is None:
                print(f"Failed to create drawing for '{chart_id}': {error}")
                return False
    
            # Enhanced size configurations with more options
            size_configs = {
                "tiny": 3.0 * inch,
                "small": 4.0 * inch,
                "compact": 4.5 * inch,     # Perfect for detailed classification charts
                "medium": 5.0 * inch,
                "large": 6.5 * inch,
                "extra_large": 7.5 * inch
            }
    
            # Special handling for different chart types
            is_pie_row = any(keyword in chart_id for keyword in ['combined', 'three_pie', 'taxpayer_classification_distribution'])
            is_treemap = 'treemap' in chart_id
            is_detailed = 'detailed_' in chart_id
            
            if is_pie_row:
                # Wide format for three pies in row  
                target_width = 7.5 * inch
                target_height = 4.0 * inch
            elif is_treemap:
                # Larger format for treemaps
                target_width = 7.0 * inch
                target_height = 5.0 * inch
            elif is_detailed:
                # Compact format for detailed breakdown charts
                target_width = 5.0 * inch
                target_height = 3.5 * inch
            else:
                # Regular sizing for other charts
                target_width = size_configs.get(size, 5.5 * inch)
                target_height = target_width * 0.6  # Standard aspect ratio
    
            # Calculate scale factors
            original_width = getattr(drawing, 'width', 400)
            original_height = getattr(drawing, 'height', 400)
            
            if original_width <= 0 or original_height <= 0:
                print(f"Invalid original dimensions for '{chart_id}': {original_width}x{original_height}")
                return False
                
            scale_x = target_width / original_width
            scale_y = target_height / original_height
    
            # Create properly scaled drawing
            from reportlab.graphics.shapes import Drawing, Group
            
            scaled_drawing = Drawing(target_width, target_height)
            content_group = Group()
            content_group.transform = (scale_x, 0, 0, scale_y, 0, 0)
            
            # Add original contents safely
            if hasattr(drawing, 'contents'):
                for item in drawing.contents:
                    content_group.add(item)
            
            scaled_drawing.add(content_group)
            scaled_drawing.hAlign = 'CENTER'
            
            # Add minimal spacing for detailed charts, regular spacing for others
            if is_detailed:
                self.story.append(Spacer(1, 0.005 * inch))  # Minimal spacing
            else:
                self.story.append(Spacer(1, 0.01 * inch))
                
            self.story.append(scaled_drawing)
            
            if is_detailed:
                self.story.append(Spacer(1, 0.005 * inch))  # Minimal spacing
            else:
                self.story.append(Spacer(1, 0.01 * inch))
            
            print(f"SUCCESS: Chart '{chart_id}' added with size {size} ({target_width:.1f}x{target_height:.1f})")
            return True
            
        except Exception as e:
            print(f"ERROR inserting chart '{chart_id}': {e}")
            import traceback
            traceback.print_exc()
            return False
    def _register_fonts(self):
        """Register fonts with proper error handling"""
        try:
            font_path = 'NotoSansDevanagari-VariableFont_wdth,wght.ttf'
            #font_path='Mangal Regular.ttf'
            if os.path.exists(font_path):
                pdfmetrics.registerFont(TTFont('HindiFont', font_path))
                print("Hindi font registered successfully")
            else:
                print("Hindi font file not found, using fallback")
                self._use_fallback_font()
        except Exception as e:
            print(f"Font registration failed: {e}")
            self._use_fallback_font()

    def _use_fallback_font(self):
        """Use built-in fonts as fallback"""
        try:
            pdfmetrics.registerFont(TTFont('HindiFont', 'Helvetica'))
        except Exception as e:
            print(f"Fallback font registration failed: {e}")

    def run(self, detailed=False):
        """Generate the full report with comprehensive error handling"""
        try:
            # 1. Create cover page
            self.create_cover_page_story()
            self.story.append(PageBreak())
            
            # 2. Create summary header
            self.create_summary_header()
            
          
            # 3. Add comprehensive monthly performance summary with charts Section II and II
            self.add_monthly_performance_summary()

            # 4. Add Section III Sectoral analysis (Two sectoral graphs Pie charts)
            self.add_sectoral_analysis()
        
            # 5. Add Section IV Nature of Non Compliance Analysis
            self.add_nature_of_non_compliance_analysis()

            # 6. Add Risk Parameter Analysis if available
            if self.vital_stats.get('risk_analysis_available', False):
                self.add_risk_parameter_analysis()
             # 7. Add Section V - Top Audit Group and Circle Performance
            self.add_top_performance_analysis()
            
            # 8. Add Section VI - Top Taxpayers of Detection and Recovery
            self.add_top_taxpayers_analysis()
    
            #self.create_structured_chart_sections()
            # 4. Build the document
            self.doc.build(self.story, onFirstPage=self.add_page_elements, onLaterPages=self.add_page_elements)
            
            self.buffer.seek(0)
            return self.buffer
            
        except Exception as e:
            print(f"Error generating PDF: {e}")
            return self._generate_error_pdf(str(e))

    def create_summary_header(self):
        """Create the summary page header"""
        try:
            title_style = ParagraphStyle(
                name='MainTitle', 
                fontSize=28, 
                textColor=colors.HexColor("#1F3A4D"),
                alignment=TA_CENTER, 
                fontName='Helvetica-Bold'
            )
            
            # Check if Hindi font is available
            try:
                pdfmetrics.getFont('HindiFont')
                hindi_font = 'HindiFont'
            except:
                hindi_font = 'Helvetica-Bold'
                
            hindi_style = ParagraphStyle(
                name='HindiTitle', 
                parent=title_style, 
                fontName=hindi_font, 
                fontSize=24
            )
            
            # self.story.append(Paragraph("Monitoring Committee Meeting (MCM)", title_style))
            # self.story.append(Paragraph("निगरानी समिति की बैठक", hindi_style))
            # self.story.append(Spacer(1, 0.5 * inch))

            # Summary styles
            summary_style_caps = ParagraphStyle(
                name='SummaryCaps', 
                fontSize=18, 
                # textColor=colors.HexColor("#1F3A4D"),
                textColor=colors.HexColor("#0E4C92"),
                alignment=TA_CENTER, 
                fontName='Helvetica-Bold'
            )
            summary_italic_style = ParagraphStyle(
                name='SummaryItalic', 
                fontSize=10, 
                textColor=colors.HexColor("#1F3A4D"),
                alignment=TA_CENTER, 
                fontName='Helvetica-Oblique'
            )
            summary_footer_style = ParagraphStyle(
                name='SummaryFooter', 
                fontSize=14, 
                textColor=colors.HexColor("#0E4C92"),
                alignment=TA_CENTER, 
                fontName='Helvetica-Bold'
            )

            self.story.append(Paragraph("EXECUTIVE SUMMARY", summary_style_caps))
            self.story.append(Spacer(1, 0.1 * inch))
            self.story.append(Paragraph("(Auto generated through e-MCM App)", summary_italic_style))
            self.story.append(Spacer(1, 0.1 * inch))
            self.story.append(Paragraph("Audit 1 Commissionerate, Mumbai CGST Zone", summary_footer_style))
            self.story.append(Spacer(1, 0.4 * inch))

            # Add introduction paragraph - first part
            intro_text_part1 = f"""
            This executive summary presents the Infographical analysis of Audit Performance submitted during Monitoring Committee meeting for the {self.selected_period} period. 
            The report contains comprehensive charts and visualizations that highlight:
            """
            
            # Create bullet points as separate paragraphs for better alignment
            bullet_points = [
                "(i) <b>Overall Audit Performance</b> for the month, across Small, Medium, Large Categories",
                "(ii) <b>Status of Para Analysis</b>, based on Tax Recovery Status and pending recovery potential", 
                "(iii) <b>Sectoral Analysis</b>, based on Trader, Manufacturer and Service sectors",
                "(iv) <b>Nature of Non Compliance Analysis</b>, using Audit Para Categorisation Coding System of Audit-1 commissionerate",
                "(v) <b>Risk Parameter Analysis</b>",
                "(vi) <b>Top Audit Group and Circle Performance</b>",
                "(vii) <b>Top Taxpayers of Detection and Recovery</b>"
            ]
            
            # Final part
            conclusion_text = """
            The report covers the <b>Summary of Taxpayer wise Audit paras raised and the decision taken during MCM</b>, encompassing all the Draft Audit Reports submitted before Monitoring Committee.
            """
            
         
            
            intro_style = ParagraphStyle(
                name='IntroStyle',
                parent=self.styles['Normal'],
                fontSize=12,
                textColor=colors.HexColor("#2C2C2C"),
                alignment=TA_JUSTIFY,
                fontName='Helvetica',
                leftIndent=0.5*inch,
                rightIndent=0.5*inch,
                leading=16,
                spaceAfter=12
            )
            
            # Create bullet point style with proper indentation
            bullet_style = ParagraphStyle(
                name='BulletStyle',
                parent=self.styles['Normal'],
                fontSize=12,
                textColor=colors.HexColor("#2C2C2C"),
                alignment=TA_LEFT,
                fontName='Helvetica',
                leftIndent=0.75*inch,  # Fixed left indent for alignment
                rightIndent=0.5*inch,
                leading=16,
                spaceAfter=4,
                spaceBefore=2
            )
            
            # Add the introduction parts
            self.story.append(Paragraph(intro_text_part1, intro_style))
            
            # Add each bullet point as a separate paragraph
            for bullet in bullet_points:
                self.story.append(Paragraph(bullet, bullet_style))
            
            # Add conclusion
            self.story.append(Spacer(1, 0.1 * inch))
            self.story.append(Paragraph(conclusion_text, intro_style))
            
            # # Add Monthly Performance Summary section
            # self.story.append(Spacer(1, 0.3 * inch))
            # self.add_monthly_performance_summary()
            # self.story.append(Spacer(1, 0.3 * inch))
                
        except Exception as e:
            print(f"Error creating summary header: {e}")

    def create_structured_chart_sections(self):
        """Create structured sections with headings and descriptions for each chart"""
        if not self.chart_images or len(self.chart_images) == 0:
            placeholder_style = ParagraphStyle(
                name='Placeholder', 
                parent=self.styles['Normal'],
                fontSize=12, 
                alignment=TA_CENTER
            )
            self.story.append(Paragraph("No charts available for this report.", placeholder_style))
            return

        successful_charts = 0
        
        for i, img_bytes in enumerate(self.chart_images):
            try:
                if img_bytes is None:
                    self._add_chart_error_section(i, "No image data provided")
                    continue

                print(f"Processing chart section {i+1}/{len(self.chart_images)}")
                
                # Get metadata for this chart
                metadata = self.chart_metadata[i] if i < len(self.chart_metadata) else {
                    "title": f"Chart {i+1}",
                    "description": "Analysis and insights from the data visualization.",
                    "page_break_after": False
                }
                
                # Add chart title
                self.story.append(Paragraph(metadata["title"], self.chart_title_style))
                
                # Add chart description
                self.story.append(Paragraph(metadata["description"], self.chart_description_style))
                
                # Create and add the chart
                drawing, error = self._create_safe_svg_drawing(img_bytes)
                # Add this after: drawing, error = self._create_safe_svg_drawing(img_bytes)
                print(f"=== DEBUG CHART {chart_id} ===")
                print(f"Requested size: {size}")
                print(f"Drawing object: {drawing}")
                if drawing:
                    print(f"Drawing width: {getattr(drawing, 'width', 'No width')}")
                    print(f"Drawing height: {getattr(drawing, 'height', 'No height')}")
                print(f"Target width should be: {size_configs.get(size, 'Unknown')}")
                print("=" * 30)
                if error:
                    print(f"Chart {i+1} error: {error}")
                    self._add_chart_error_inline(i, error)
                    continue

                if drawing is None:
                    self._add_chart_error_inline(i, "Could not create drawing")
                    continue

                # Scale and add the drawing
                try:
                    render_width = 6.5 * inch
                    scale_factor = render_width / drawing.width
                    drawing.width = render_width
                    drawing.height = drawing.height * scale_factor
                    drawing.hAlign = 'CENTER'
                    
                    # Add the chart with reduced spacing
                    self.story.append(Spacer(1, 0.1 * inch))  # Reduced from 0.3
                    self.story.append(drawing)
                    self.story.append(Spacer(1, 0.2 * inch))  # Reduced from 0.3
                    successful_charts += 1
                    
                    print(f"Successfully processed chart {i+1}")
                    
                    # Add page break if specified in metadata
                    if metadata.get("page_break_after", False):
                        self.story.append(PageBreak())
                        
                except Exception as scale_error:
                    print(f"Chart {i+1} scaling error: {scale_error}")
                    self._add_chart_error_inline(i, f"Scaling failed: {scale_error}")
                    
            except Exception as e:
                print(f"Unexpected error processing chart section {i+1}: {e}")
                self._add_chart_error_section(i, f"Unexpected error: {e}")

        print(f"Successfully processed {successful_charts}/{len(self.chart_images)} chart sections")

    def _add_chart_error_section(self, chart_index, error_message):
        """Add error section for failed chart with title"""
        try:
            metadata = self.chart_metadata[chart_index] if chart_index < len(self.chart_metadata) else {
                "title": f"Chart {chart_index+1}",
                "description": "Chart could not be generated due to technical issues."
            }
            
            # Add title even for error
            self.story.append(Paragraph(metadata["title"], self.chart_title_style))
            
            # Add error message
            error_style = ParagraphStyle(
                name='ChartError', 
                parent=self.styles['Normal'],
                fontSize=11, 
                textColor=colors.red,
                alignment=TA_CENTER,
                fontName='Helvetica-Oblique'
            )
            self.story.append(Paragraph(f"Unable to load chart: {error_message}", error_style))
            self.story.append(Spacer(1, 0.3 * inch))
        except Exception as e:
            print(f"Error adding chart error section: {e}")

    def _add_chart_error_inline(self, chart_index, error_message):
        """Add inline error message for failed chart"""
        try:
            error_style = ParagraphStyle(
                name='ChartErrorInline', 
                parent=self.styles['Normal'],
                fontSize=10, 
                textColor=colors.red,
                alignment=TA_CENTER,
                fontName='Helvetica-Oblique'
            )
            self.story.append(Paragraph(f"Chart error: {error_message}", error_style))
            self.story.append(Spacer(1, 0.3 * inch))
        except Exception as e:
            print(f"Error adding inline chart error: {e}")

    # Include all the other methods from your original class...
    # (I'll include the key ones for SVG processing)

    def _validate_svg_content(self, svg_content):
        """Validate SVG content and fix common issues that cause transformation errors"""
        try:
            if isinstance(svg_content, bytes):
                svg_string = svg_content.decode('utf-8')
            else:
                svg_string = str(svg_content)

            if len(svg_string.strip()) < 10:
                return None, "SVG content too short"

            try:
                root = ET.fromstring(svg_string)
            except ET.ParseError as e:
                return None, f"Invalid XML structure: {e}"

            if not (root.tag.endswith('svg') or 'svg' in root.tag.lower()):
                return None, "Not a valid SVG element"

            svg_string = self._fix_svg_transforms(svg_string)
            svg_string = self._ensure_svg_dimensions(svg_string)

            return svg_string.encode('utf-8'), None

        except Exception as e:
            return None, f"SVG validation error: {e}"

    def _fix_svg_transforms(self, svg_string):
        """Fix problematic transformation matrices in SVG"""
        svg_string = re.sub(r'scale\(0(?:\.0*)?\)', 'scale(0.001)', svg_string)
        svg_string = re.sub(r'scale\(0(?:\.0*)?[,\s]+0(?:\.0*)?\)', 'scale(0.001,0.001)', svg_string)
        
        def fix_matrix(match):
            values = [float(x.strip()) for x in match.group(1).split(',')]
            if len(values) == 6:
                a, b, c, d, e, f = values
                det = a * d - b * c
                if abs(det) < 1e-10:
                    return 'matrix(1,0,0,1,0,0)'
            return match.group(0)
        
        svg_string = re.sub(r'matrix\(([^)]+)\)', fix_matrix, svg_string)
        return svg_string

    def _ensure_svg_dimensions(self, svg_string):
        """Ensure SVG has proper width and height attributes"""
        if 'width=' not in svg_string and 'height=' not in svg_string:
            svg_string = re.sub(
                r'<svg([^>]*?)>', 
                r'<svg\1 width="400" height="300">', 
                svg_string, 
                count=1
            )
        
        svg_string = re.sub(r'width=["\']0["\']', 'width="400"', svg_string)
        svg_string = re.sub(r'height=["\']0["\']', 'height="300"', svg_string)
        
        return svg_string

    def _create_safe_svg_drawing(self, img_bytes):
        """Create an SVG drawing with comprehensive error handling and validation"""
        try:
            img_bytes.seek(0)
            original_content = img_bytes.read()
            
            if not original_content:
                return None, "Empty image data"

            fixed_content, error = self._validate_svg_content(original_content)
            if error:
                return None, error

            fixed_buffer = BytesIO(fixed_content)
            
            try:
                drawing = svg2rlg(fixed_buffer)
            except Exception as svg_error:
                return None, f"SVG parsing failed: {svg_error}"

            if drawing is None:
                return None, "svg2rlg returned None"

            if not hasattr(drawing, 'width') or not hasattr(drawing, 'height'):
                return None, "Drawing missing width/height attributes"

            if drawing.width <= 0 or drawing.height <= 0:
                return None, f"Invalid dimensions: {drawing.width}x{drawing.height}"

            if not (0 < drawing.width < 10000 and 0 < drawing.height < 10000):
                return None, f"Unreasonable dimensions: {drawing.width}x{drawing.height}"

            return drawing, None

        except Exception as e:
            return None, f"Unexpected error creating SVG drawing: {e}"

    def _generate_error_pdf(self, error_message):
        """Generate a simple PDF with error message if main generation fails"""
        try:
            error_buffer = BytesIO()
            error_doc = SimpleDocTemplate(error_buffer, pagesize=letter)
            error_story = []
            
            error_style = ParagraphStyle(
                name='Error', 
                parent=self.styles['Normal'],
                fontSize=12, 
                textColor=colors.red,
                alignment=TA_CENTER
            )
            
            error_story.append(Spacer(1, 2*inch))
            error_story.append(Paragraph("PDF Generation Error", error_style))
            error_story.append(Spacer(1, 0.5*inch))
            error_story.append(Paragraph(f"Error: {error_message}", self.styles['Normal']))
            error_story.append(Spacer(1, 0.5*inch))
            error_story.append(Paragraph("Please check your chart data and try again.", self.styles['Normal']))
            
            error_doc.build(error_story)
            error_buffer.seek(0)
            return error_buffer
        except Exception as fallback_error:
            print(f"Even fallback PDF generation failed: {fallback_error}")
            empty_buffer = BytesIO()
            empty_buffer.write(b"PDF generation failed")
            empty_buffer.seek(0)
            return empty_buffer

    def add_page_elements(self, canvas, doc):
        """Unified method to draw static elements on ALL pages"""
        try:
            canvas.saveState()
            if doc.page == 1:
                # Cover Page Background
                canvas.setFillColor(colors.HexColor("#193041"))  # Dark Blue
                canvas.rect(0, self.height * 0.20, self.width, self.height, stroke=0, fill=1)
                canvas.setFillColor(colors.HexColor("#C8B59E"))  # Gold
                canvas.rect(0, 0, self.width, self.height * 0.20, stroke=0, fill=1)
                canvas.setStrokeColor(colors.HexColor("#C8B59E"))
                canvas.setLineWidth(3)
                canvas.line(0, self.height * 0.20, self.width, self.height * 0.20)

                # Draw static lines for the cover page
                canvas.setStrokeColor(colors.HexColor("#f5ddc1"))
                canvas.setLineWidth(1)
                logo_y_pos = self.height - 1.6 * inch
                canvas.line(1.5*inch, logo_y_pos, 3.25*inch, logo_y_pos)  # Left line
                canvas.line(self.width - 3.25*inch, logo_y_pos, self.width - 1.5*inch, logo_y_pos)  # Right line
            else:
                # Background for all other pages
                canvas.setFillColor(colors.HexColor("#FAEBD7"))  # Light beige
                canvas.rect(0, 0, self.width, self.height, stroke=0, fill=1)
            
            canvas.restoreState()
        except Exception as e:
            print(f"Error drawing page elements: {e}")
            canvas.restoreState()

    def create_cover_page_story(self):
        """Method to create the cover page CONTENT with logos"""
        try:
            # CBIC Logo at the Top
            try:
                cbic_logo = Image('cbic_logo.png', width=1.6*inch, height=1.6*inch)
                cbic_logo.hAlign = 'CENTER'
                self.story.append(cbic_logo)
            except Exception as e:
                print(f"Warning: cbic_logo.png not found. Using text placeholder. Error: {e}")
                logo_style = ParagraphStyle(name='LogoStyle', fontSize=16, textColor=colors.HexColor("#f5ddc1"), alignment=TA_CENTER)
                self.story.append(Paragraph("CBIC LOGO", logo_style))
            
            self.story.append(Spacer(1, 0.8 * inch))

            # Title and Subtitles
            title_style = ParagraphStyle(name='Title', fontSize=38, textColor=colors.HexColor("#f5ddc1"),
                                       alignment=TA_CENTER, fontName='Helvetica-Bold', leading=46)
            title2_style = ParagraphStyle(name='Title2', parent=title_style, fontSize=34)
            title3_style = ParagraphStyle(name='Title3', parent=title_style, fontSize=26, textColor=colors.HexColor("#FCC200"),fontName='Helvetica')
            title4_style = ParagraphStyle(name='Title4', parent=title_style, fontSize=20,textColor=colors.HexColor("#FC200") ,fontName='Helvetica-Oblique')
            
            try:
                pdfmetrics.getFont('HindiFont')
                hindi_font = 'HindiFont'
            except:
                hindi_font = 'Helvetica-Bold'
            hindi_style = ParagraphStyle(name='HindiTitle', parent=title_style, fontName=hindi_font, fontSize=24)
            
            self.story.append(Paragraph("MONITORING COMMITTEE MEETING", title_style))
            #self.story.append(Paragraph("निगरानी समिति की बैठक", hindi_style))
            self.story.append(Paragraph(" िनगरानी सिमित की बैठक", hindi_style))
           
            self.story.append(Paragraph(f"{self.selected_period.upper()}", title2_style))
            self.story.append(Spacer(1, 0.5 * inch))
            self.story.append(Paragraph("EXECUTIVE SUMMARY REPORT1", title3_style))
            #self.story.append(Paragraph(" कार्यकारी सारांश प्रतिवेदन", hindi_style))
            self.story.append(Paragraph("[Auto-generated by e-MCM App]", title4_style))
            
            self.story.append(Spacer(1, 2 * inch))

            # Emblem and Address at the Bottom using a Table
            contact_style = ParagraphStyle(name='Contact', fontSize=12, textColor=colors.HexColor("#193041"), alignment=TA_LEFT)
            org_style = ParagraphStyle(name='Org', fontSize=18, textColor=colors.HexColor("#193041"), alignment=TA_LEFT, fontName='Helvetica-Bold', leading=18)

            right_col_text = [
                Paragraph("Office of the Commissioner of CGST & Central Excise", org_style),
                Paragraph("Audit-I Commissionerate, Mumbai", org_style),
                Spacer(1, 0.2 * inch),
                Paragraph("Ph: 022-22617504 | Email: audit1mum@gov.in", contact_style)
            ]

            try:
                emblem_logo = Image('emblem.png', width=0.8*inch, height=1.2*inch)
            except Exception as e:
                print(f"Warning: emblem.png not found. Using a text placeholder. Error: {e}")
                emblem_logo = Paragraph("EMBLEM", contact_style)

            table_data = [[emblem_logo, right_col_text]]
            bottom_table = Table(table_data, colWidths=[1.0*inch, 6.5*inch])

            bottom_table.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (-1, -1), 0),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
            ]))

            self.story.append(bottom_table)
            self.story.append(Spacer(1, 0.2 * inch))
        except Exception as e:
            print(f"Error creating cover page: {e}")

    def add_monthly_performance_summary(self):
        """Add I and II sections-  Monthly Performance Summary section and status of para with metrics and table"""
        try:
            # Section header
            perf_header_style = ParagraphStyle(
                name='PerfHeader',
                parent=self.styles['Heading2'],
                fontSize=18,
                # textColor=colors.HexColor("#1F3A4D"),
                textColor=colors.HexColor("#0E4C92"),
                alignment=TA_CENTER,
                fontName='Helvetica-Bold',
                spaceAfter=16,
                spaceBefore=16
            )
            para_style = ParagraphStyle(
                name='IntroStyle',
                parent=self.styles['Normal'],
                fontSize=12,
                textColor=colors.HexColor("#2C2C2C"),
                alignment=TA_JUSTIFY,
                fontName='Helvetica',
                leftIndent=0.5*inch,
                rightIndent=0.5*inch,
                leading=16,
                spaceAfter=12
            )
            self.add_section_highlight_bar("I. Monthly Performance Summary",text_color="#0E4C92")
            #self.story.append(Paragraph("I. Monthly Performance Summary", perf_header_style))
            
            # Extract metrics from vital_stats - using the correct keys from visualisation_utils.py
            dars_submitted = self.vital_stats.get('num_dars', 0)
            revenue_involved = self.vital_stats.get('total_detected', 0)
            revenue_recovered = self.vital_stats.get('total_recovered', 0)
            
            # Create metrics section using a table for better layout
            metrics_data = [
                ['✅ DARs Submitted', '💰 Revenue Involved', '💎 Revenue Recovered'],
                [f'{dars_submitted}', f'Rs.{revenue_involved:.2f} L', f'Rs.{revenue_recovered:.2f} L']
            ]
            metrics_table = Table(metrics_data, colWidths=[3*inch, 3*inch, 3*inch])
            #metrics_table = Table(metrics_data, colWidths=[2.33*inch, 2.33*inch, 2.33*inch])
            metrics_table.setStyle(TableStyle([
                # Header row styling
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 11),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor("#666666")),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                
                # Data row styling
                ('FONTNAME', (0, 1), (-1, 1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 1), (-1, 1), 24),
                #('TEXTCOLOR', (0, 1), (-1, 1), colors.HexColor("#1134A6")),
                ('TEXTCOLOR', (0, 1), (-1, 1), colors.HexColor("#0f52ba")),
                
                # Spacing
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
                ('LEFTPADDING', (0, 0), (-1, -1), 12),
                ('RIGHTPADDING', (0, 0), (-1, -1), 12),
            ]))
            
            self.story.append(metrics_table)
            self.story.append(Spacer(1, 0.2 * inch))
            
            # Performance Summary Table Header
            table_header_style = ParagraphStyle(
                name='TableHeader',
                parent=self.styles['Heading3'],
                fontSize=14,
                # textColor=colors.HexColor("#1F3A4D"),
                textColor=colors.HexColor("#1134A6"),
                alignment=TA_LEFT,
                fontName='Helvetica-Bold',
                spaceAfter=12,
                spaceBefore=16
            )
            
            self.story.append(Paragraph("🎯 Performance Summary Table", table_header_style))
            
            # Get the categories summary from vital_stats (populated by visualisation_utils.py)
            categories_summary = self.vital_stats.get('categories_summary', [])
            
            # Create the performance data table
            if categories_summary:
                # Build table from actual data
                performance_data = [['CATEGORY', 'NO. OF DARS', 'TOTAL DETECTED', 'TOTAL RECOVERED', 'NO. OF AUDIT PARAS']]
                
                total_dars = 0
                total_detected = 0
                total_recovered = 0
                total_paras = 0
                
                for category_data in categories_summary:
                    category = category_data.get('category', 'Unknown')
                    dars = int(category_data.get('dars_submitted', 0))
                    detected = float(category_data.get('total_detected', 0))
                    recovered = float(category_data.get('total_recovered', 0))
                    paras = int(category_data.get('num_audit_paras', 0))
                    
                    total_dars += dars
                    total_detected += detected
                    total_recovered += recovered
                    total_paras += paras
                    
                    performance_data.append([
                        category,
                        str(dars),
                        f'Rs.{detected:,.2f} L',
                        f'Rs.{recovered:,.2f} L',
                        str(paras)
                    ])
                
                # Add total row
                performance_data.append([
                    '📊 Total (All)',
                    str(total_dars),
                    f'Rs.{total_detected:,.2f} L',
                    f'Rs.{total_recovered:,.2f} L',
                    str(total_paras)
                ])
            else:
                # Fallback to default data if categories_summary is not available
                performance_data = [
                    ['CATEGORY', 'NO. OF DARS', 'TOTAL DETECTED', 'TOTAL RECOVERED', 'NO. OF AUDIT PARAS'],
                    ['Large', '0', '0 L', 'Rs.0.00 L', '0'],
                    ['Medium', '0', '0 L', 'Rs.15.20 L', '0'],
                    ['Small', '0', '0 L', 'Rs.0.00 L', '0'],
                    ['📊 Total (All)', '10', 'Rs.0 L', '0 ', '0']
                ]
            
            # Create table with custom column widths
            #col_widths = [1.4*inch, 0.9*inch, 1.2*inch, 1.2*inch, 1.3*inch]
            col_widths = [1*inch, 1.2*inch, 1.8*inch, 1.8*inch, 1.8*inch]
            performance_table = Table(performance_data, colWidths=col_widths)
            
            # Apply table styling
            performance_table.setStyle(TableStyle([
                # Header row styling
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#6F2E2E")),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                
                # Data rows styling
                ('FONTNAME', (0, 1), (-1, -2), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 1), (-1, -2), 10),
                ('ALIGN', (0, 1), (-1, -1), 'CENTER'),
                ('TEXTCOLOR', (0, 1), (-1, -2), colors.HexColor("#333333")),
                
                # Total row styling (last row)
                ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor("#E8F4F8")),
                ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, -1), (-1, -1), 10),
                ('TEXTCOLOR', (0, -1), (-1, -1), colors.HexColor("#1F3A4D")),
                
                # Alternating row colors for better readability
                ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor("#F8F8F8")),
                ('BACKGROUND', (0, 3), (-1, 3), colors.HexColor("#F8F8F8")),
                
                # Grid and borders
                ('GRID', (0, 0), (-1, -1), 1, colors.HexColor("#CCCCCC")),
                ('LINEBELOW', (0, 0), (-1, 0), 2, colors.HexColor("#6F2E2E")),
                ('LINEABOVE', (0, -1), (-1, -1), 2, colors.HexColor("#1F3A4D")),
                
                # Padding
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
                ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                
                # Vertical alignment
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))
            
            self.story.append(performance_table)
            self.story.append(Spacer(1, 0.3 * inch))
            print("=== TRYING TO INSERT CHARTS ===")
        
            # Add Status Summary Table if available
            self.add_section_highlight_bar("II. Status of Audit Para Analysis",text_color="#0E4C92")
            section2_description='This section provides analysis of Audit paras based on the Recovery status of the amount involved and shows potential recovery paras , actionable by the audit groups'
            self.story.append(Paragraph(section2_description, para_style))
            if self.vital_stats.get('status_analysis_available', False):
                self.add_status_summary_table()
            # INSERT STATUS ANALYSIS CHART
           
            print(f"Chart registry keys: {list(self.chart_registry.keys())}")
            print(f"Chart registry: {self.chart_registry}")
            
            # result1 = self.insert_chart_by_id("status_analysis", size="medium", add_title=False)
            # print(f"Status analysis result: {result1}")
            
            # result2 = self.insert_chart_by_id("recovery_trends", size="small") 
            # print(f"Recovery trends result: {result2}")
            # print("=== FINISHED CHART INSERTION ===")
            # if self.vital_stats.get('status_analysis_available', False):
            #     self.add_status_summary_table()
                
            # # INSERT RECOVERY TRENDS CHART
            # self.insert_chart_by_id("recovery_trends", size="small",add_title=False)
            
            # # Add Risk Parameter Analysis if available
            # if self.vital_stats.get('risk_analysis_available', False):
            #     self.add_risk_parameter_analysis()
            
        except Exception as e:
            print(f"Error adding monthly performance summary: {e}")
            # Add error message if table creation fails
            error_style = ParagraphStyle(
                name='TableError',
                parent=self.styles['Normal'],
                fontSize=10,
                textColor=colors.red,
                alignment=TA_CENTER
            )
            self.story.append(Paragraph("Error loading performance summary table", error_style))

    def add_status_summary_table(self):
        """Add Status Summary Table section"""
        try:
            # Section header
            status_header_style = ParagraphStyle(
                name='StatusHeader',
                parent=self.styles['Heading3'],
                fontSize=14,
                textColor=colors.HexColor("#1134A6"),
                alignment=TA_LEFT,
                fontName='Helvetica-Bold',
                spaceAfter=12,
                spaceBefore=16
            )
            
            self.story.append(Paragraph("📊 Status Summary Table", status_header_style))
            
            # Get status summary data from vital_stats (if available from visualization processing)
            status_summary_data = self.vital_stats.get('status_summary', [])
            
            if status_summary_data:
                # Build table from actual data
                status_data = [['STATUS OF PARA', 'NO. OF PARAS', 'TOTAL DETECTION (Rs.L)', 'TOTAL RECOVERY (Rs.L)', 'RECOVERY %']]
                
                for status_item in status_summary_data:
                    status = status_item.get('status_of_para', 'Unknown')
                    paras = int(status_item.get('Para_Count', 0))
                    detection = float(status_item.get('Total_Detection', 0))
                    recovery = float(status_item.get('Total_Recovery', 0))
                    recovery_pct = float(status_item.get('Recovery_Percentage', 0))
                    
                    status_data.append([
                        status,
                        str(paras),
                        f'Rs.{detection:,.2f} L',
                        f'Rs.{recovery:,.2f} L',
                        f'{recovery_pct:.1f}%'
                    ])
            else:
                # Fallback data based on the image you shared
                status_data = [
                    ['STATUS OF PARA', 'NO. OF PARAS', 'TOTAL DETECTION ( L)', 'TOTAL RECOVERY (L)', 'RECOVERY %'],
                    ['Agreed yet to pay', '51', '₹13.74 L', '₹0.00 L', '0.0%'],
                    ['Agreed and Paid', '26', '₹19.96 L', '₹9.20 L', '46.1%'],
                    ['Not agreed', '16', '₹1.07 L', '₹0.00 L', '0.0%'],
                    ['Partially agreed, yet to paid', '1', '₹0.00 L', '₹0.00 L', '0.0%']
                ]
            
            # Create the status table
            #status_col_widths = [2.2*inch, 0.8*inch, 1.3*inch, 1.3*inch, 1.0*inch]
            status_col_widths = [1.8*inch, 1*inch, 1.8*inch, 1.8*inch, 1.8*inch]
            status_table = Table(status_data, colWidths=status_col_widths)
            
            # Apply colorful styling similar to the image
            status_table.setStyle(TableStyle([
                # Header styling with gradient effect
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#8B4A9C")),  # Purple header
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                
                # Data rows with alternating colors
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 9),
                ('ALIGN', (1, 1), (-1, -1), 'CENTER'),  # Numbers centered
                ('ALIGN', (0, 1), (0, -1), 'LEFT'),     # Status left-aligned
                
                # Row background colors - matching the colorful theme from the image
                ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor("#E8F5E8")),    # Light green
                ('BACKGROUND', (0, 2), (-1, 2), colors.HexColor("#FFF3CD")),    # Light yellow
                ('BACKGROUND', (0, 3), (-1, 3), colors.HexColor("#F8D7DA")),    # Light red
                ('BACKGROUND', (0, 4), (-1, 4), colors.HexColor("#E2E3E5")),    # Light gray
                
                # Grid and borders
                ('GRID', (0, 0), (-1, -1), 1, colors.HexColor("#CCCCCC")),
                ('LINEBELOW', (0, 0), (-1, 0), 2, colors.HexColor("#8B4A9C")),
                
                # Padding
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('LEFTPADDING', (0, 0), (-1, -1), 8),
                ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                
                # Vertical alignment
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))
            
            self.story.append(status_table)
            self.story.append(Spacer(1, 0.05 * inch))
            self.story.append(Paragraph("📊 Total Recovery Potential", status_header_style))
            self.insert_chart_by_id("status_analysis", size="small")
            self.story.append(Spacer(1, 0.05 * inch))
            # Add "Top 5 Paras with Largest Detection" section if data is available
            # if self.vital_stats.get('agreed_yet_to_pay_analysis'):
            #     self.add_top_agreed_paras_section()
          
            try:
                # Get the analysis data
                agreed_analysis = self.vital_stats.get('agreed_yet_to_pay_analysis', {})
                
                if agreed_analysis and agreed_analysis.get('top_5_paras') is not None:
                    # Add summary metrics
                    total_paras = agreed_analysis.get('total_paras', 0)
                    total_detection = agreed_analysis.get('total_detection', 0)
                    total_recovery = agreed_analysis.get('total_recovery', 0)
                    
                    # Create metrics row
                    metrics_data = [
                        [f"Total 'Agreed yet to pay' Paras", f"Total Detection Amount", f"Total Recovery Potential"],
                        [f"{total_paras}", f"Rs.{total_detection:,.2f} L", f"Rs.{total_detection:,.2f} L"]
                    ]
                       # Section header
                    top_paras_header_style = ParagraphStyle(
                        name='TopParasHeader',
                        parent=self.styles['Heading3'],
                        fontSize=14,
                        textColor=colors.HexColor("#1134A6"),
                        alignment=TA_LEFT,
                        fontName='Helvetica-Bold',
                        spaceAfter=12,
                        spaceBefore=16
                    )
                    
                    
                    metrics_table = Table(metrics_data, colWidths=[2.33*inch, 2.33*inch, 2.33*inch])
                    metrics_table.setStyle(TableStyle([
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, 0), 10),
                        ('FONTNAME', (0, 1), (-1, 1), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 1), (-1, 1), 12),
                        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#E8F4F8")),
                        ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor("#F0F8FF")),
                        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor("#CCCCCC")),
                        ('TOPPADDING', (0, 0), (-1, -1), 6),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                    ]))
                    
                    self.story.append(metrics_table)
                    top_5_paras = agreed_analysis['top_5_paras']
                    
                    # Create table data
                    #para_data = [['Audit Group', 'Trade Name', 'Para No.', 'Para Heading', 'Detection (Rs.L)', 'Recovery (Rs.L)', 'Status']]
                    para_data = [['Audit Group', 'Trade Name', 'Para Heading', 'Detection (Rs.L)']]
                    for _, row in top_5_paras.iterrows():
                        audit_group = str(row.get('audit_group_number_str', 'N/A'))
                        trade_name = str(row.get('trade_name', 'N/A'))[:50] + '...' if len(str(row.get('trade_name', 'N/A'))) > 30 else str(row.get('trade_name', 'N/A'))
                        #para_no = str(row.get('audit_para_number', 'N/A'))
                        para_heading = str(row.get('audit_para_heading', 'N/A'))[:100] + '...' if len(str(row.get('audit_para_heading', 'N/A'))) > 100 else str(row.get('audit_para_heading', 'N/A'))
                        detection = f"Rs.{row.get('Para Detection in Lakhs', 0):.2f} L"
                        #recovery = f"₹{row.get('Para Recovery in Lakhs', 0):.2f} L"
                        #status = str(row.get('status_of_para', 'N/A'))
                        
                        #para_data.append([audit_group, trade_name, para_no, para_heading, detection, recovery, status])
                        para_data.append([audit_group, trade_name,  para_heading, detection])
                    
                    # Create table
                    para_col_widths = [0.7*inch, 1.6*inch, 4.8*inch, 1.1*inch]
                    para_table = Table(para_data, colWidths=para_col_widths)
                    
                    # FIX 3: Correct table styling for 4 columns (indices 0,1,2,3)
                    para_table.setStyle(TableStyle([
                        # Header styling
                        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#6F2E2E")),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, 0), 8),
                        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                        
                        # Data rows
                        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                        ('FONTSIZE', (0, 1), (-1, -1), 8),
                        
                        # FIXED ALIGNMENTS for 4 columns (0=Group, 1=Trade, 2=Heading, 3=Detection)
                        ('ALIGN', (3, 1), (3, -1), 'RIGHT'),   # Detection column (index 3) right-aligned
                        ('ALIGN', (0, 1), (2, -1), 'LEFT'),    # Other columns (0,1,2) left-aligned
                        # REMOVED: Status center alignment (no Status column anymore)
                        
                        # Alternating row colors
                        ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor("#F8F8F8")),
                        ('BACKGROUND', (0, 3), (-1, 3), colors.HexColor("#F8F8F8")),
                        ('BACKGROUND', (0, 5), (-1, 5), colors.HexColor("#F8F8F8")),
                        
                        # Grid and borders
                        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor("#CCCCCC")),
                        ('LINEBELOW', (0, 0), (-1, 0), 2, colors.HexColor("#6F2E2E")),
                        
                        # Padding
                        ('TOPPADDING', (0, 0), (-1, -1), 4),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                        ('LEFTPADDING', (0, 0), (-1, -1), 4),
                        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                        
                        # Vertical alignment - ADD TOP alignment for better text wrapping
                        ('VALIGN', (0, 0), (-1, -1), 'TOP'),  # Changed from MIDDLE to TOP
                    ]))
                    self.story.append(Paragraph("🎯 Top 5 Paras with Largest Detection - Status: 'Agreed yet to pay'", top_paras_header_style))
                    self.story.append(para_table)
                    self.story.append(Spacer(1, 0.2 * inch))
                    
                    
                    
                else:
                    # Fallback message
                    info_style = ParagraphStyle(
                        name='InfoStyle',
                        parent=self.styles['Normal'],
                        fontSize=10,
                        textColor=colors.HexColor("#666666"),
                        alignment=TA_CENTER
                    )
                    self.story.append(Paragraph("No 'Agreed yet to pay' paras found for this period.", info_style))
                    
            except Exception as e:
                print(f"Error adding top agreed paras section: {e}")    
        except Exception as e:
            print(f"Error adding status summary table: {e}") 
    
    
    def add_sectoral_analysis(self):
        """Add Section III - Sectoral Analysis with pie charts and summary table"""
        try:
            # Section III Header
            self.add_section_highlight_bar("III. Sectoral Analysis", text_color="#0E4C92")
            
            # Description (same as before)
            desc_style = ParagraphStyle(
                name='SectoralDesc',
                parent=self.styles['Normal'],
                fontSize=11,
                textColor=colors.HexColor("#2C2C2C"),
                alignment=TA_JUSTIFY,
                fontName='Helvetica',
                leftIndent=0.25*inch,
                rightIndent=0.25*inch,
                leading=14,
                spaceAfter=16
            )
            
            description_text = """
            This section provides sectoral analysis of audit performance across different taxpayer classifications and business categories. 
            The analysis helps identify sector-wise compliance patterns and focus areas for targeted audit interventions .
            """
            
            self.story.append(Paragraph(description_text, desc_style))
            
            # Chart heading style
            chart_header_style = ParagraphStyle(
                name='ChartHeader',
                parent=self.styles['Heading3'],
                fontSize=14,
                textColor=colors.HexColor("#1134A6"),
                alignment=TA_LEFT,
                fontName='Helvetica-Bold',
                spaceAfter=12,
                spaceBefore=16
            )
            
            # First Chart
            self.story.append(Paragraph("🎯 Taxpayer Classification Analysis- Total DARs, Detection and Recovery", chart_header_style))
            self.insert_chart_by_id("taxpayer_classification_distribution", 
                                   size="small", 
                                   add_title=False, 
                                   add_description=False)
            self.story.append(Spacer(1, 0.2 * inch))
            
            # # Second Chart
            # self.story.append(Paragraph("🎯 Detection Amount by Taxpayer Classification", chart_header_style))
            # self.insert_chart_by_id("taxpayer_classification_detection", 
            #                        size="medium", 
            #                        add_title=False, 
            #                        add_description=False)
            # self.story.append(Spacer(1, 0.2 * inch))
            # # Third Chart
            # self.story.append(Paragraph("🎯 Recovery Amount by Taxpayer Classification", chart_header_style))
            # self.insert_chart_by_id("taxpayer_classification_recovery", 
            #                        size="medium", 
            #                        add_title=False, 
            #                        add_description=False)
            # self.story.append(Spacer(1, 0.2 * inch))
            # ADD SECTORAL SUMMARY TABLE if data available
        
            if self.vital_stats.get('sectoral_analysis_available', False):
                self.add_sectoral_summary_table()
            
            self.story.append(Spacer(1, 0.3 * inch))
                
        except Exception as e:
            print(f"Error adding sectoral analysis: {e}")
    
    def add_sectoral_summary_table(self):
        """Add sectoral summary table"""
        try:
            sectoral_summary = self.vital_stats.get('sectoral_summary', [])
            print('Sectorals summary',sectoral_summary)
            if sectoral_summary:
                table_header_style = ParagraphStyle(
                    name='SectoralTableHeader',
                    parent=self.styles['Heading3'],
                    fontSize=14,
                    textColor=colors.HexColor("#1134A6"),
                    alignment=TA_LEFT,
                    fontName='Helvetica-Bold',
                    spaceAfter=12,
                    spaceBefore=16
                )
                
                self.story.append(Paragraph("📊 Sectoral Performance Summary", table_header_style))
                
                # Create sectoral table
                sectoral_data = [['Classification', 'No. of DARs', 'Detection (Rs.L)', 'Recovery (Rs.L)']]
                
                for item in sectoral_summary[:6]:  # Top 6 classifications
                    classification = item.get('classification', 'Unknown')
                    dar_count = item.get('dar_count', 0)
                    detection = item.get('total_detection', 0)
                    recovery = item.get('total_recovery', 0)
                    
                    sectoral_data.append([
                        classification,
                        str(dar_count),
                        f'Rs.{detection:.2f} L',
                        f'Rs.{recovery:.2f} L'
                    ])
                
                sectoral_table = Table(sectoral_data, colWidths=[2.5*inch, 1.2*inch, 1.4*inch, 1.4*inch])
                sectoral_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#8B4A9C")),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 9),
                    ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                    ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                    ('FONTSIZE', (0, 1), (-1, -1), 9),
                    ('ALIGN', (1, 1), (-1, -1), 'CENTER'),
                    ('ALIGN', (0, 1), (0, -1), 'LEFT'),
                    ('GRID', (0, 0), (-1, -1), 1, colors.HexColor("#CCCCCC")),
                    ('TOPPADDING', (0, 0), (-1, -1), 6),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ]))
                
                self.story.append(sectoral_table)
                self.story.append(Spacer(1, 0.2 * inch))
                
        except Exception as e:
            print(f"Error adding sectoral summary table: {e}")
            
    # def add_comprehensive_classification_page(self):
    #     #"""Add a comprehensive classification page using pre-processed data"""
    #     print(f"DEBUG: vital_stats contains: {list(self.vital_stats.keys())}")
    #     classification_data = self.vital_stats.get('classification_page_data')
    #     print(f"DEBUG: classification_page_data = {classification_data}")
       
    #     try:
    #         # Get pre-processed classification data from vital_stats
    #         classification_data = self.vital_stats.get('classification_page_data', {})
    #         print("🔍 === CLASSIFICATION PAGE DEBUG ===")
 
    
    #         print(f"🔍 classification_page_data exists: {classification_data is not None}")
    
    #         if classification_data:
    #             total_observations = classification_data.get('total_observations', 0)
    #             main_categories_count = classification_data.get('main_categories_count', 0)  
    #             sub_categories_count = classification_data.get('sub_categories_count', 0)
                
    #             # Convert category stats back to DataFrame for compatibility
    #             category_stats_records = classification_data.get('category_stats', [])
    #             category_stats = pd.DataFrame(category_stats_records)
                
    #             print(f"SUCCESS: Loaded classification data - {total_observations} observations")
    #         else:
    #             # Fallback values if no data
    #             total_observations = main_categories_count = sub_categories_count = 0
    #             category_stats = pd.DataFrame()
    #             print("WARNING: No classification data found in vital_stats")
    #         # PAGE HEADER with gradient effect using table
    #         header_style = ParagraphStyle(
    #             name='ClassificationHeader',
    #             parent=self.styles['Heading1'],
    #             fontSize=20,
    #             textColor=colors.white,
    #             alignment=TA_CENTER,
    #             fontName='Helvetica-Bold',
    #             spaceAfter=0,
    #             spaceBefore=0
    #         )
                    
    #         subtitle_style = ParagraphStyle(
    #             name='ClassificationSubtitle',
    #             parent=self.styles['Normal'],
    #             fontSize=12,
    #             textColor=colors.white,
    #             alignment=TA_CENTER,
    #             fontName='Helvetica',
    #             spaceAfter=0
    #         )
    
    #         # Create header with blue gradient background
    #         header_data = [
    #             [Paragraph("GST Audit Para Classification", header_style)],
    #             [Paragraph("Comprehensive categorization by Nature of Non-Compliance", subtitle_style)],
    #             [Paragraph(f"📅 Period: {self.selected_period} | 🔍 Real-time Analysis Data", subtitle_style)]
    #         ]
            
    #         header_table = Table(header_data, colWidths=[7.5*inch])
    #         header_table.setStyle(TableStyle([
    #             ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#2a5298")),
    #             ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
    #             ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    #             ('TOPPADDING', (0, 0), (-1, -1), 15),
    #             ('BOTTOMPADDING', (0, 0), (-1, -1), 15),
    #             ('LEFTPADDING', (0, 0), (-1, -1), 20),
    #             ('RIGHTPADDING', (0, 0), (-1, -1), 20),
    #         ]))
            
    #         self.story.append(header_table)
            
    #         # STATISTICS SECTION with purple gradient
    #         stats_header_style = ParagraphStyle(
    #             name='StatsHeader',
    #             parent=self.styles['Heading2'],
    #             fontSize=16,
    #             textColor=colors.white,
    #             alignment=TA_CENTER,
    #             fontName='Helvetica-Bold'
    #         )
            
    #         stats_data = [
    #             [Paragraph("Classification Overview", stats_header_style)],
    #             [self._create_stats_grid(main_categories_count, sub_categories_count, total_observations)]
    #         ]
            
    #         stats_table = Table(stats_data, colWidths=[7.5*inch])
    #         stats_table.setStyle(TableStyle([
    #             ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#764ba2")),
    #             ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
    #             ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    #             ('TOPPADDING', (0, 0), (-1, -1), 15),
    #             ('BOTTOMPADDING', (0, 0), (-1, -1), 15),
    #         ]))
            
    #         self.story.append(stats_table)
    #         self.story.append(Spacer(1, 0.2*inch))
    
    #         # CLASSIFICATION CATEGORIES GRID
    #         self._add_classification_categories_grid(category_stats)
            
    #         # LEGEND SECTION
    #         self._add_classification_legend()
            
    #     except Exception as e:
    #         print(f"Error adding comprehensive classification page: {e}")
    #         import traceback
    #         traceback.print_exc()
    
    # def _create_stats_grid(self, main_categories, sub_categories, total_observations):
    #         """Create statistics grid for the classification page"""
            
    #         stat_style = ParagraphStyle(
    #             name='StatNumber',
    #             fontSize=20,
    #             textColor=colors.white,
    #             alignment=TA_CENTER,
    #             fontName='Helvetica-Bold',
    #             spaceAfter=3
    #         )
            
    #         label_style = ParagraphStyle(
    #             name='StatLabel',
    #             fontSize=10,
    #             textColor=colors.white,
    #             alignment=TA_CENTER,
    #             fontName='Helvetica',
    #             spaceAfter=0
    #         )
            
    #         # Create mini tables for each stat
    #         stats_data = [
    #             [
    #                 Table([
    #                     [Paragraph(str(main_categories), stat_style)],
    #                     [Paragraph("Main Categories", label_style)]
    #                 ], colWidths=[1.5*inch]),
                    
    #                 Table([
    #                     [Paragraph(str(sub_categories), stat_style)],
    #                     [Paragraph("Sub-Categories", label_style)]
    #                 ], colWidths=[1.5*inch]),
                    
    #                 Table([
    #                     [Paragraph(str(total_observations), stat_style)],
    #                     [Paragraph("Audit Observations", label_style)]
    #                 ], colWidths=[1.5*inch]),
                    
    #                 Table([
    #                     [Paragraph("100%" if total_observations > 0 else "0%", stat_style)],
    #                     [Paragraph("Coverage", label_style)]
    #                 ], colWidths=[1.5*inch])
    #             ]
    #         ]
            
    #         grid_table = Table(stats_data, colWidths=[1.7*inch, 1.7*inch, 1.7*inch, 1.7*inch])
    #         grid_table.setStyle(TableStyle([
    #             ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
    #             ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    #         ]))
            
    #         return grid_table
        
    # def _add_classification_categories_grid(self, category_stats):
    #         """Add the 9 classification categories in a 3x3 grid"""
            
    #         categories_info = [
    #             ("TP", "Tax Payment Defaults", "#e74c3c", [
    #                 "Output Tax Short Payment", "Output Tax on Other Income", 
    #                 "Export & SEZ Related Issues", "Credit Note Related Errors"
    #             ]),
    #             ("RC", "Reverse Charge Mechanism", "#f39c12", [
    #                 "Transportation & Logistics", "Professional & Legal Services",
    #                 "Import of Services", "RCM Reconciliation Issues"
    #             ]),
    #             ("IT", "Input Tax Credit Violations", "#3498db", [
    #                 "Blocked Credit Claims (Sec 17(5))", "Ineligible ITC Claims (Sec 16)",
    #                 "Excess ITC Reconciliation", "ITC Reversal Defaults"
    #             ]),
    #             ("IN", "Interest Liability Defaults", "#9b59b6", [
    #                 "Tax Payment Related Interest", "ITC Related Interest (Sec 50)",
    #                 "Time of Supply Interest", "Self-Assessment Interest"
    #             ]),
    #             ("RF", "Return Filing Non-Compliance", "#2ecc71", [
    #                 "Late Filing Penalties", "Non-Filing Issues (ITC-04)",
    #                 "Filing Quality Issues", "Annual Return Issues"
    #             ]),
    #             ("PD", "Procedural & Documentation", "#34495e", [
    #                 "Return Reconciliation", "Documentation Deficiencies",
    #                 "Cash Payment Violations", "Record Maintenance"
    #             ]),
    #             ("CV", "Classification & Valuation", "#e67e22", [
    #                 "Service Classification Errors", "Wrong Chapter Heading",
    #                 "Incorrect Notification Claims", "Rate Classification Errors"
    #             ]),
    #             ("SS", "Special Situations", "#1abc9c", [
    #                 "Construction/Real Estate", "Job Work Related Compliance",
    #                 "Inter-Company Transactions", "Composition Scheme Issues"
    #             ]),
    #             ("PG", "Penalty & General Compliance", "#c0392b", [
    #                 "Statutory Penalties (Sec 123)", "Stock & Physical Verification",
    #                 "General Non-Compliance", "Compliance Monitoring"
    #             ])
    #         ]
            
    #         # Create 3x3 grid
    #         rows_data = []
    #         for i in range(0, 9, 3):
    #             row_cards = []
    #             for j in range(3):
    #                 if i + j < len(categories_info):
    #                     card = self._create_category_card(categories_info[i + j], category_stats)
    #                     row_cards.append(card)
    #                 else:
    #                     row_cards.append("")  # Empty cell if needed
    #             rows_data.append(row_cards)
            
    #         # Create the grid table
    #         grid_table = Table(rows_data, colWidths=[2.5*inch, 2.5*inch, 2.5*inch])
    #         grid_table.setStyle(TableStyle([
    #             ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
    #             ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    #             ('LEFTPADDING', (0, 0), (-1, -1), 5),
    #             ('RIGHTPADDING', (0, 0), (-1, -1), 5),
    #             ('TOPPADDING', (0, 0), (-1, -1), 5),
    #             ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    #         ]))
            
    #         self.story.append(grid_table)
        
    # def _create_category_card(self, category_info, category_stats):
    #         """Create a visual card for each classification category"""
    #         code, title, color, subcategories = category_info
            
    #         # Get real statistics for this category
    #         stats_text = self._get_category_stats_text(category_stats, code)
            
    #         # Card title style
    #         title_style = ParagraphStyle(
    #             name=f'CardTitle_{code}',
    #             fontSize=11,
    #             textColor=colors.HexColor("#2c3e50"),
    #             alignment=TA_LEFT,
    #             fontName='Helvetica-Bold',
    #             spaceAfter=6
    #         )
            
    #         # Subcategory style
    #         sub_style = ParagraphStyle(
    #             name=f'CardSub_{code}',
    #             fontSize=8,
    #             textColor=colors.HexColor("#5a6c7d"),
    #             alignment=TA_LEFT,
    #             fontName='Helvetica',
    #             spaceAfter=2,
    #             leftIndent=10
    #         )
            
    #         # Stats style
    #         stats_style = ParagraphStyle(
    #             name=f'CardStats_{code}',
    #             fontSize=8,
    #             textColor=colors.HexColor("#34495e"),
    #             alignment=TA_CENTER,
    #             fontName='Helvetica-Bold',
    #             spaceAfter=0
    #         )
            
    #         # Create card content
    #         card_content = [
    #             [Paragraph(f"<font color='{color}'>{code}</font> • {title}", title_style)]
    #         ]
            
    #         # Add subcategories (limit to 3 for space)
    #         for sub in subcategories[:3]:
    #             card_content.append([Paragraph(f"▶ {sub}", sub_style)])
            
    #         # Add statistics
    #         card_content.append([Paragraph(stats_text, stats_style)])
            
    #         # Create the card table
    #         card_table = Table(card_content, colWidths=[2.3*inch])
    #         card_table.setStyle(TableStyle([
    #             ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#f8f9fa")),
    #             ('BOX', (0, 0), (-1, -1), 1, colors.HexColor("#e0e0e0")),
    #             ('LEFTPADDING', (0, 0), (-1, -1), 8),
    #             ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    #             ('TOPPADDING', (0, 0), (-1, -1), 8),
    #             ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    #             ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    #             # Add colored left border
    #             ('LINEABOVE', (0, 0), (0, 0), 4, colors.HexColor(color)),
    #         ]))
            
    #         return card_table
        
    # def _get_category_stats_text(self, category_stats, category_code):
    #         """Get formatted statistics text for a category"""
    #         if category_stats.empty:
    #             return "📊 No data | 💰 ₹0 L | 💎 ₹0 L"
            
    #         category_data = category_stats[category_stats['major_code'] == category_code]
    #         if category_data.empty:
    #             return "📊 No data | 💰 ₹0 L | 💎 ₹0 L"
            
    #         paras = int(category_data['para_count'].iloc[0])
    #         detection = float(category_data['total_detection'].iloc[0])
    #         recovery = float(category_data['total_recovery'].iloc[0])
            
    #         return f"📊 {paras} paras | 💰 ₹{detection:.1f}L | 💎 ₹{recovery:.1f}L"
        
    # def _add_classification_legend(self):
    #         """Add color legend and usage guide"""
    #         legend_style = ParagraphStyle(
    #             name='LegendHeader',
    #             fontSize=14,
    #             textColor=colors.white,
    #             alignment=TA_CENTER,
    #             fontName='Helvetica-Bold'
    #         )
            
    #         legend_item_style = ParagraphStyle(
    #             name='LegendItem',
    #             fontSize=9,
    #             textColor=colors.white,
    #             alignment=TA_LEFT,
    #             fontName='Helvetica'
    #         )
            
    #         # Legend items with color indicators
    #         legend_items = [
    #             ("■", "#e74c3c", "High Risk - Tax Payment Issues"),
    #             ("■", "#f39c12", "Medium Risk - RCM Compliance"), 
    #             ("■", "#3498db", "High Volume - ITC Issues"),
    #             ("■", "#9b59b6", "Financial Impact - Interest"),
    #             ("■", "#2ecc71", "Administrative - Filing Issues"),
    #             ("■", "#34495e", "Process Related - Documentation")
    #         ]
            
    #         # Create legend grid
    #         legend_data = [
    #             [Paragraph("🎯 Classification Guide & Impact Assessment", legend_style)]
    #         ]
            
    #         # Add legend items in 2 columns
    #         for i in range(0, len(legend_items), 2):
    #             row = []
    #             for j in range(2):
    #                 if i + j < len(legend_items):
    #                     symbol, color, text = legend_items[i + j]
    #                     colored_text = f"<font color='{color}'>{symbol}</font> {text}"
    #                     row.append(Paragraph(colored_text, legend_item_style))
    #                 else:
    #                     row.append("")
    #             legend_data.append(row)
            
    #         legend_table = Table(legend_data, colWidths=[3.75*inch, 3.75*inch])
    #         legend_table.setStyle(TableStyle([
    #             ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#34495e")),
    #             ('ALIGN', (0, 0), (-1, 0), 'CENTER'),  # Center header
    #             ('ALIGN', (0, 1), (-1, -1), 'LEFT'),   # Left align items
    #             ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    #             ('TOPPADDING', (0, 0), (-1, -1), 10),
    #             ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
    #             ('LEFTPADDING', (0, 0), (-1, -1), 15),
    #             ('RIGHTPADDING', (0, 0), (-1, -1), 15),
    #             ('SPAN', (0, 0), (1, 0)),  # Span header across both columns
    #         ]))
            
    #         self.story.append(Spacer(1, 0.2*inch))
    #         self.story.append(legend_table)
    def add_comprehensive_classification_page(self):
        """Add an ultra-compact classification page that fits on one page"""
        try:
            # Get pre-processed classification data from vital_stats
            classification_data = self.vital_stats.get('classification_page_data', {})
            
            if classification_data:
                total_observations = classification_data.get('total_observations', 0)
                main_categories_count = classification_data.get('main_categories_count', 0)  
                sub_categories_count = classification_data.get('sub_categories_count', 0)
                
                # Convert category stats back to DataFrame for compatibility
                category_stats_records = classification_data.get('category_stats', [])
                category_stats = pd.DataFrame(category_stats_records)
                
                print(f"SUCCESS: Loaded classification data - {total_observations} observations")
            else:
                # Fallback values if no data
                total_observations = main_categories_count = sub_categories_count = 0
                category_stats = pd.DataFrame()
                print("WARNING: No classification data found in vital_stats")
    
            # ULTRA COMPACT HEADER - Reduced height by 50%
            header_style = ParagraphStyle(
                name='ClassificationHeader',
                parent=self.styles['Heading1'],
                fontSize=16,  # Reduced from 20
                textColor=colors.white,
                alignment=TA_CENTER,
                fontName='Helvetica-Bold',
                spaceAfter=0,
                spaceBefore=0
            )
            
            subtitle_style = ParagraphStyle(
                name='ClassificationSubtitle',
                parent=self.styles['Normal'],
                fontSize=10,  # Reduced from 12
                textColor=colors.white,
                alignment=TA_CENTER,
                fontName='Helvetica',
                spaceAfter=0
            )
    
            # Create compact header with reduced padding
            header_data = [
                [Paragraph("GST Audit Para Classification", header_style)],
                [Paragraph("Comprehensive categorization by Nature of Non-Compliance", subtitle_style)],
                [Paragraph(f"📅 Period: {self.selected_period} | 🔍 Real-time Analysis Data", subtitle_style)]
            ]
            
            header_table = Table(header_data, colWidths=[7.5*inch])
            header_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#2a5298")),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('TOPPADDING', (0, 0), (-1, -1), 8),     # Reduced from 15
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),  # Reduced from 15
                ('LEFTPADDING', (0, 0), (-1, -1), 10),   # Reduced from 20
                ('RIGHTPADDING', (0, 0), (-1, -1), 10),  # Reduced from 20
            ]))
            
            self.story.append(header_table)
            
            # ULTRA COMPACT STATISTICS SECTION - Reduced height by 60%
            stats_header_style = ParagraphStyle(
                name='StatsHeader',
                parent=self.styles['Heading2'],
                fontSize=12,  # Reduced from 16
                textColor=colors.white,
                alignment=TA_CENTER,
                fontName='Helvetica-Bold'
            )
            
            stats_data = [
                [Paragraph("Classification Overview", stats_header_style)],
                [self._create_compact_stats_grid(main_categories_count, sub_categories_count, total_observations)]
            ]
            
            stats_table = Table(stats_data, colWidths=[7.5*inch])
            stats_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#764ba2")),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('TOPPADDING', (0, 0), (-1, -1), 8),     # Reduced from 15
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),  # Reduced from 15
            ]))
            
            self.story.append(stats_table)
            self.story.append(Spacer(1, 0.1*inch))  # Reduced from 0.2*inch
    
            # ULTRA COMPACT CLASSIFICATION CATEGORIES GRID
            self._add_compact_classification_categories_grid(category_stats)
            
            # ULTRA COMPACT LEGEND SECTION
            self._add_compact_classification_legend()
            
        except Exception as e:
            print(f"Error adding comprehensive classification page: {e}")
            import traceback
            traceback.print_exc()
    
    def _create_compact_stats_grid(self, main_categories, sub_categories, total_observations):
        """Create ultra-compact statistics grid with minimal spacing"""
        
        stat_style = ParagraphStyle(
            name='StatNumber',
            fontSize=16,  # Reduced from 20
            textColor=colors.white,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold',
            spaceAfter=1,  # Reduced from 3
            spaceBefore=0
        )
        
        label_style = ParagraphStyle(
            name='StatLabel',
            fontSize=8,   # Reduced from 10
            textColor=colors.white,
            alignment=TA_CENTER,
            fontName='Helvetica',
            spaceAfter=0
        )
        
        # Create mini tables for each stat with minimal padding
        stats_data = [
            [
                Table([
                    [Paragraph(str(main_categories), stat_style)],
                    [Paragraph("Main Categories", label_style)]
                ], colWidths=[1.3*inch]),  # Reduced width
                
                Table([
                    [Paragraph(str(sub_categories), stat_style)],
                    [Paragraph("Sub-Categories", label_style)]
                ], colWidths=[1.3*inch]),  # Reduced width
                
                Table([
                    [Paragraph(str(total_observations), stat_style)],
                    [Paragraph("Audit Observations", label_style)]
                ], colWidths=[1.3*inch]),  # Reduced width
                
                Table([
                    [Paragraph("100%" if total_observations > 0 else "0%", stat_style)],
                    [Paragraph("Coverage", label_style)]
                ], colWidths=[1.3*inch])  # Reduced width
            ]
        ]
        
        grid_table = Table(stats_data, colWidths=[1.5*inch, 1.5*inch, 1.5*inch, 1.5*inch])
        grid_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 2),     # Minimal padding
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),  # Minimal padding
        ]))
        
        return grid_table
    
    def _add_compact_classification_categories_grid(self, category_stats):
        """Add ultra-compact 3x3 grid with minimal spacing"""
        
        categories_info = [
            ("TP", "Tax Payment Defaults", "#e74c3c", [
                "Output Tax Short Payment", "Output Tax on Other Income", "Export & SEZ Related Issues"
            ]),
            ("RC", "Reverse Charge Mechanism", "#f39c12", [
                "Transportation & Logistics", "Professional & Legal Services", "Import of Services"
            ]),
            ("IT", "Input Tax Credit Violations", "#3498db", [
                "Blocked Credit Claims (Sec 17(5))", "Ineligible ITC Claims (Sec 16)", "Excess ITC Reconciliation"
            ]),
            ("IN", "Interest Liability Defaults", "#9b59b6", [
                "Tax Payment Related Interest", "ITC Related Interest (Sec 50)", "Time of Supply Interest"
            ]),
            ("RF", "Return Filing Non-Compliance", "#2ecc71", [
                "Late Filing Penalties", "Non-Filing Issues (ITC-04)", "Filing Quality Issues"
            ]),
            ("PD", "Procedural & Documentation", "#34495e", [
                "Return Reconciliation", "Documentation Deficiencies", "Cash Payment Violations"
            ]),
            ("CV", "Classification & Valuation", "#e67e22", [
                "Service Classification Errors", "Wrong Chapter Heading", "Incorrect Notification Claims"
            ]),
            ("SS", "Special Situations", "#1abc9c", [
                "Construction/Real Estate", "Job Work Related Compliance", "Inter-Company Transactions"
            ]),
            ("PG", "Penalty & General Compliance", "#c0392b", [
                "Statutory Penalties (Sec 123)", "Stock & Physical Verification", "General Non-Compliance"
            ])
        ]
        
        # Create ultra-compact 3x3 grid
        rows_data = []
        for i in range(0, 9, 3):
            row_cards = []
            for j in range(3):
                if i + j < len(categories_info):
                    card = self._create_ultra_compact_category_card(categories_info[i + j], category_stats)
                    row_cards.append(card)
                else:
                    row_cards.append("")
            rows_data.append(row_cards)
        
        # Create the grid table with minimal spacing
        grid_table = Table(rows_data, colWidths=[2.4*inch, 2.4*inch, 2.4*inch])  # Slightly reduced
        grid_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 2),    # Minimal padding
            ('RIGHTPADDING', (0, 0), (-1, -1), 2),   # Minimal padding
            ('TOPPADDING', (0, 0), (-1, -1), 2),     # Minimal padding
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),  # Minimal padding
        ]))
        
        self.story.append(grid_table)
    
    def _create_ultra_compact_category_card(self, category_info, category_stats):
        """Create ultra-compact visual card with minimal spacing"""
        code, title, color, subcategories = category_info
        
        # Get real statistics for this category
        stats_text = self._get_category_stats_text(category_stats, code)
        
        # Ultra-compact card title style
        title_style = ParagraphStyle(
            name=f'CardTitle_{code}',
            fontSize=9,    # Reduced from 11
            textColor=colors.HexColor("#2c3e50"),
            alignment=TA_LEFT,
            fontName='Helvetica-Bold',
            spaceAfter=3,  # Reduced from 6
            spaceBefore=0
        )
        
        # Ultra-compact subcategory style
        sub_style = ParagraphStyle(
            name=f'CardSub_{code}',
            fontSize=7,    # Reduced from 8
            textColor=colors.HexColor("#5a6c7d"),
            alignment=TA_LEFT,
            fontName='Helvetica',
            spaceAfter=1,  # Reduced from 2
            leftIndent=8,  # Reduced from 10
            leading=8      # Tight line spacing
        )
        
        # Ultra-compact stats style
        stats_style = ParagraphStyle(
            name=f'CardStats_{code}',
            fontSize=7,    # Reduced from 8
            textColor=colors.HexColor("#34495e"),
            alignment=TA_CENTER,
            fontName='Helvetica-Bold',
            spaceAfter=0,
            spaceBefore=2  # Minimal space above
        )
        
        # Create ultra-compact card content
        card_content = [
            [Paragraph(f"<font color='{color}'>{code}</font> • {title}", title_style)]
        ]
        
        # Add only 2 subcategories for space saving
        for sub in subcategories[:2]:  # Reduced from 3 to 2
            card_content.append([Paragraph(f"▶ {sub}", sub_style)])
        
        # Add statistics
        card_content.append([Paragraph(stats_text, stats_style)])
        
        # Create the ultra-compact card table
        card_table = Table(card_content, colWidths=[2.2*inch])  # Slightly reduced
        card_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#f8f9fa")),
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor("#e0e0e0")),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),    # Reduced from 8
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),   # Reduced from 8
            ('TOPPADDING', (0, 0), (-1, -1), 4),     # Reduced from 8
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),  # Reduced from 8
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            # Add colored left border
            ('LINEABOVE', (0, 0), (0, 0), 3, colors.HexColor(color)),  # Reduced from 4
        ]))
        
        return card_table
    
    def _get_category_stats_text(self, category_stats, category_code):
        """Get formatted statistics text for a category"""
        if category_stats.empty:
            return "📊 No data | 💰 Rs.0 L | 💎 Rs.0 L"
        
        category_data = category_stats[category_stats['major_code'] == category_code]
        if category_data.empty:
            return "📊 No data | 💰 Rs.0 L | 💎 Rs.0 L"
        
        paras = int(category_data['para_count'].iloc[0])
        detection = float(category_data['total_detection'].iloc[0])
        recovery = float(category_data['total_recovery'].iloc[0])
        
        return f"📊 {paras} paras | 💰 Rs.{detection:.1f}L | 💎 Rs.{recovery:.1f}L"
    
    def _add_compact_classification_legend(self):
        """Add ultra-compact single line legend"""
        legend_style = ParagraphStyle(
            name='LegendText',
            fontSize=11,
            textColor=colors.white,
            alignment=TA_CENTER,
            fontName='Helvetica',
            leading=11
        )
        
        # Single line legend text
        legend_text = "Audit 1 Commissionerate Mumbai GST Zone codified Nature of compliances into total 58 Sub codes under 9 main classification codes for analysis"
        
        # Create simple legend table
        legend_data = [
            [Paragraph(legend_text, legend_style)]
        ]
        
        legend_table = Table(legend_data, colWidths=[7.5*inch])
        legend_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#34495e")),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('LEFTPADDING', (0, 0), (-1, -1), 15),
            ('RIGHTPADDING', (0, 0), (-1, -1), 15),
        ]))
        
        self.story.append(Spacer(1, 0.05*inch))  # Minimal spacer
        self.story.append(legend_table)
    def add_classification_summary_table(self):
            """Add classification summary table"""  
            try:
                classification_summary = self.vital_stats.get('classification_summary', [])
                
                if classification_summary:
                    table_header_style = ParagraphStyle(
                        name='ClassificationTableHeader',
                        parent=self.styles['Heading3'],
                        fontSize=14,
                        textColor=colors.HexColor("#1134A6"),
                        alignment=TA_LEFT,
                        fontName='Helvetica-Bold',
                        spaceAfter=12,
                        spaceBefore=16
                    )
                    
                    self.story.append(Paragraph("📊 Non-Compliance Categories Summary", table_header_style))
                    
                    # Classification codes mapping
                    CLASSIFICATION_CODES_DESC = {
                        'TP': 'TAX PAYMENT DEFAULTS', 
                        'RC': 'REVERSE CHARGE MECHANISM',
                        'IT': 'INPUT TAX CREDIT VIOLATIONS', 
                        'IN': 'INTEREST LIABILITY DEFAULTS',
                        'RF': 'RETURN FILING NON-COMPLIANCE', 
                        'PD': 'PROCEDURAL & DOCUMENTATION',
                        'CV': 'CLASSIFICATION & VALUATION', 
                        'SS': 'SPECIAL SITUATIONS',
                        'PG': 'PENALTY & GENERAL COMPLIANCE'
                    }
                    
                    # Create classification table
                    classification_data = [['Code', 'Description', 'Paras', 'Detection (Rs. L)', 'Recovery (Rs. L)']]
                    
                    for item in classification_summary[:7]:  # Top 7 categories
                        code = item.get('major_code', 'Unknown')
                        description = CLASSIFICATION_CODES_DESC.get(code, 'Unknown Category')
                        para_count = item.get('Para_Count', 0)
                        detection = item.get('Total_Detection', 0)
                        recovery = item.get('Total_Recovery', 0)
                        
                        classification_data.append([
                            code,
                            description[:35] + '...' if len(description) > 35 else description,
                            str(para_count),
                            f'Rs.{detection:.2f} L',
                            f'Rs.{recovery:.2f} L'
                        ])
                    
                    classification_table = Table(classification_data, 
                                               colWidths=[0.6*inch, 2.4*inch, 0.8*inch, 1.3*inch, 1.3*inch])
                    
                    classification_table.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#6F2E2E")),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, 0), 8),
                        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                        ('FONTSIZE', (0, 1), (-1, -1), 8),
                        ('ALIGN', (2, 1), (-1, -1), 'CENTER'),
                        ('ALIGN', (0, 1), (1, -1), 'LEFT'),
                        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor("#CCCCCC")),
                        ('LINEBELOW', (0, 0), (-1, 0), 2, colors.HexColor("#6F2E2E")),
                        ('TOPPADDING', (0, 0), (-1, -1), 6),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ]))
                    
                    self.story.append(classification_table)
                    self.story.append(Spacer(1, 0.01 * inch))
                    
            except Exception as e:
                print(f"Error adding classification summary table: {e}")
                
    def _add_detailed_charts_2x3_layout_simple(self, chart_type):
        """Simple approach: Add detailed charts in 2x3 layout using direct insertion"""
        try:
            # Classification codes in logical order (first 6 for first page, next 6 for second page)
            classification_codes = ['TP', 'RC', 'IT', 'IN', 'RF', 'PD', 'CV', 'SS', 'PG']
            
            # Filter available charts for this type
            available_charts = []
            for code in classification_codes:
                chart_id = f"detailed_{chart_type}_{code}"
                if chart_id in self.chart_registry:
                    available_charts.append(chart_id)
            
            print(f"Found {len(available_charts)} available {chart_type} charts")
            
            if not available_charts:
                print(f"No {chart_type} charts available")
                return
            
            # Process charts in groups of 6 (2x3 layout per page)
            charts_per_page = 6
            
            for page_start in range(0, len(available_charts), charts_per_page):
                page_charts = available_charts[page_start:page_start + charts_per_page]
                
                # Add charts in pairs (2 per row)
                for i in range(0, len(page_charts), 2):
                    # Create a table for this row (2 charts side by side)
                    row_charts = []
                    
                    # First chart in the row
                    if i < len(page_charts):
                        chart1_content = self._create_compact_chart_for_row(page_charts[i])
                        row_charts.append(chart1_content)
                    
                    # Second chart in the row (if available)
                    if i + 1 < len(page_charts):
                        chart2_content = self._create_compact_chart_for_row(page_charts[i + 1])
                        row_charts.append(chart2_content)
                    else:
                        # Empty cell if odd number of charts
                        row_charts.append("")
                    
                    # Create table for this row
                    if len(row_charts) >= 2:
                        row_table = Table([row_charts], colWidths=[3.75*inch, 3.75*inch])
                        row_table.setStyle(TableStyle([
                            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                            ('LEFTPADDING', (0, 0), (-1, -1), 2),
                            ('RIGHTPADDING', (0, 0), (-1, -1), 2),
                            ('TOPPADDING', (0, 0), (-1, -1), 2),
                            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
                        ]))
                        
                        self.story.append(row_table)
                        self.story.append(Spacer(1, 0.1 * inch))
                    else:
                        # Single chart - center it
                        single_table = Table([row_charts], colWidths=[7.5*inch])
                        single_table.setStyle(TableStyle([
                            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                        ]))
                        self.story.append(single_table)
                        self.story.append(Spacer(1, 0.1 * inch))
                
                # Add page break if there are more charts
                if page_start + charts_per_page < len(available_charts):
                    self.story.append(PageBreak())
                    
        except Exception as e:
            print(f"Error adding {chart_type} charts in simple 2x3 layout: {e}")
            import traceback
            traceback.print_exc()
    
    def _create_compact_chart_for_row(self, chart_id):
        """Create a compact chart with title for row layout"""
        try:
            if chart_id not in self.chart_registry:
                return ""
                
            chart_info = self.chart_registry[chart_id]
            chart_data = chart_info['metadata']
            img_bytes = chart_info['image']
            
            if img_bytes is None:
                return ""
            
            # Create title
            title_style = ParagraphStyle(
                name='CompactChartTitle',
                parent=self.styles['Normal'],
                fontSize=10,
                textColor=colors.HexColor("#1F3A4D"),
                alignment=TA_CENTER,
                fontName='Helvetica-Bold',
                spaceAfter=3,
                spaceBefore=0
            )
            
            chart_title = Paragraph(chart_data.get('title', ''), title_style)
            
            # Create drawing
            drawing, error = self._create_safe_svg_drawing(img_bytes)
            
            if error or drawing is None:
                print(f"Failed to create compact drawing for '{chart_id}': {error}")
                return chart_title  # Return at least the title
            
            # Compact size for side-by-side layout
            target_width = 4 * inch
            target_height = 2.5 * inch
            
            # Calculate scale factors
            original_width = getattr(drawing, 'width', 400)
            original_height = getattr(drawing, 'height', 400)
            
            if original_width <= 0 or original_height <= 0:
                return chart_title
                
            scale_x = target_width / original_width
            scale_y = target_height / original_height
            
            # Create properly scaled drawing
            from reportlab.graphics.shapes import Drawing, Group
            
            scaled_drawing = Drawing(target_width, target_height)
            content_group = Group()
            content_group.transform = (scale_x, 0, 0, scale_y, 0, 0)
            
            # Add original contents safely
            if hasattr(drawing, 'contents'):
                for item in drawing.contents:
                    content_group.add(item)
            
            scaled_drawing.add(content_group)
            scaled_drawing.hAlign = 'CENTER'
            
            # Create container with title and chart
            #container_data = [[chart_title], [scaled_drawing]]
            container_data = [[scaled_drawing]]
            container_table = Table(container_data, colWidths=[3.5*inch])
            container_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('TOPPADDING', (0, 0), (-1, -1), 0),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
                ('LEFTPADDING', (0, 0), (-1, -1), 0),
                ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ]))
            
            return container_table
            
        except Exception as e:
            print(f"Error creating compact chart for row: {e}")
            return ""
    
    # UPDATED VERSION - Replace the _add_detailed_charts_2x3_layout method with the simple version
    def _add_detailed_charts_2x3_layout(self, chart_type):
        """Add detailed charts in 2 charts per row, 3 rows per page (6 charts per page) - SIMPLE VERSION"""
        return self._add_detailed_charts_2x3_layout_simple(chart_type)
        
    def add_nature_of_non_compliance_analysis(self):
            
            """Add Section IV - Nature of Non Compliance Analysis"""
            try:
              
                self.story.append(PageBreak())
                             
                # Switch back to normal template after this section
                
                self.add_section_highlight_bar("IV. Nature of Non Compliance Analysis ", text_color="#0E4C92")
                
                # Description
                desc_style = ParagraphStyle(
                    name='ComplianceDesc',
                    parent=self.styles['Normal'],
                    fontSize=11,
                    textColor=colors.HexColor("#2C2C2C"),
                    alignment=TA_JUSTIFY,
                    fontName='Helvetica',
                    leftIndent=0.25*inch,
                    rightIndent=0.25*inch,
                    leading=14,
                    spaceAfter=16
                )
                
                # description_text = """
                # This section analyzes the nature of non-compliance using the Audit Para Categorisation Coding System of Audit-1 Commissionerate. 
                # The analysis categorizes violations into major areas like Tax Payment Defaults, ITC Violations, Return Filing issues, and Procedural Non-compliance.
                # """
                
                # self.story.append(Paragraph(description_text, desc_style))
                # ADD PAGE BREAK AND COMPREHENSIVE CLASSIFICATION PAGE
                
                self.add_comprehensive_classification_page()
              
                # Add classification summary table (only if you want it later)
                if self.vital_stats.get('compliance_analysis_available', False):
                    self.story.append(Spacer(1, 0.05 * inch))
                    self.add_classification_summary_table()
                # Chart heading style
                chart_header_style = ParagraphStyle(
                    name='ComplianceChartHeader',
                    parent=self.styles['Heading3'],
                    fontSize=14,
                    textColor=colors.HexColor("#1134A6"),
                    alignment=TA_LEFT,
                    fontName='Helvetica-Bold',
                    spaceAfter=6,
                    spaceBefore=6
                )
                
                # First Chart: Number of Paras by Classification
                self.story.append(Paragraph("🎯 Number of Audit Paras by Categorisation", chart_header_style))
                self.insert_chart_by_id("classification_para_count", 
                                       size="medium", 
                                       add_title=False, 
                                       add_description=False)
                self.story.append(Spacer(1, 0.01 * inch))
                
                # Second Chart: Detection Amount by Classification
                self.story.append(Paragraph("🎯 Detection Amount by Categorisation", chart_header_style))
                self.insert_chart_by_id("classification_detection", 
                                       size="medium", 
                                       add_title=False, 
                                       add_description=False)
                self.story.append(Spacer(1, 0.01 * inch))
                
                # Third Chart: Recovery Amount by Classification
                self.story.append(Paragraph("🎯 Recovery Amount by Categorisation", chart_header_style))
                self.insert_chart_by_id("classification_recovery", 
                                       size="medium", 
                                       add_title=False, 
                                       add_description=False)
                self.story.append(Spacer(1, 0.01 * inch))
                
                # PART B: DETAILED SUBCATEGORY ANALYSIS WITH 2x3 LAYOUT
                # Add subsection header for detailed analysis
                # detailed_header_style = ParagraphStyle(
                #     name='DetailedComplianceHeader',
                #     parent=self.styles['Heading3'],
                #     fontSize=13,
                #     textColor=colors.HexColor("#8B4A9C"),
                #     alignment=TA_LEFT,
                #     fontName='Helvetica-Bold',
                #     spaceAfter=8,
                #     spaceBefore=12
                # )
                
                # self.story.append(Paragraph("🔍 Detailed Subcategory Analysis", detailed_header_style))
                
                # Add description for detailed section
                detailed_desc_style = ParagraphStyle(
                    name='DetailedDesc',
                    parent=self.styles['Normal'],
                    fontSize=10,
                    textColor=colors.HexColor("#2C2C2C"),
                    alignment=TA_JUSTIFY,
                    fontName='Helvetica',
                    leftIndent=0.25*inch,
                    rightIndent=0.25*inch,
                    leading=12,
                    spaceAfter=12
                )
                
                detailed_description = """
                The following charts provide detailed breakdown of each major compliance category into codified specific subcategories using AI Agent, 
                showing exact types of non-compliance .
                """
                
                
                
                # PART B1: DETAILED DETECTION ANALYSIS (2x3 Layout)
                
                self.story.append(Paragraph("💰 Detection Analysis by Detailed Subcategorization", chart_header_style))
                self.story.append(Paragraph(detailed_description, detailed_desc_style))
                # Add detailed detection charts in 2x3 layout
                self._add_detailed_charts_2x3_layout("detection")
                
                #TEMPORARILY NOT SHOWING RECOVERY GRAPHS # PART B2: DETAILED RECOVERY ANALYSIS (2x3 Layout)
                # #self.story.append(PageBreak())  # Start recovery analysis on new page
                # self.story.append(Paragraph("💎 Recovery Analysis by Detailed Subcategorization", chart_header_style))
                
                # # Add detailed recovery charts in 2x3 layout
                # self._add_detailed_charts_2x3_layout("recovery")
                
                print("Added detailed classification analysis with 2x3 layout")
                    
            except Exception as e:
                print(f"Error adding nature of non compliance analysis: {e}")
    def _add_risk_charts_2x2_layout(self):
            """Add risk parameter charts in 2x2 layout"""
            try:
                # Define the 4 risk charts in order
                risk_chart_configs = [
                    ('risk_para_distribution', "Risk Flags by Audit Paras"),
                    ('risk_detection_analysis', "Detection by Risk Flag"), 
                    ('risk_recovery_analysis', "Recovery by Risk Flag"),
                    ('risk_distribution', "Recovery Percentage by Risk")
                ]
                
                # Check which charts are available
                available_charts = []
                for chart_id, title in risk_chart_configs:
                    if chart_id in self.chart_registry:
                        available_charts.append((chart_id, title))
                        print(f"Risk chart available: {chart_id}")
                    else:
                        print(f"Risk chart NOT available: {chart_id}")
                
                if len(available_charts) < 4:
                    print(f"Warning: Only {len(available_charts)} risk charts available out of 4")
                
                # Create 2x2 layout using tables
                # Row 1: First two charts
                if len(available_charts) >= 2:
                    row1_charts = []
                    
                    # First chart
                    chart1_content = self._create_compact_chart_for_risk(available_charts[0][0], available_charts[0][1])
                    row1_charts.append(chart1_content)
                    
                    # Second chart
                    chart2_content = self._create_compact_chart_for_risk(available_charts[1][0], available_charts[1][1])
                    row1_charts.append(chart2_content)
                    
                    # Create table for row 1
                    row1_table = Table([row1_charts], colWidths=[3.75*inch, 3.75*inch])
                    row1_table.setStyle(TableStyle([
                        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                        ('LEFTPADDING', (0, 0), (-1, -1), 5),
                        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
                        ('TOPPADDING', (0, 0), (-1, -1), 5),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
                    ]))
                    
                    self.story.append(row1_table)
                    self.story.append(Spacer(1, 0.15 * inch))
                
                # Row 2: Next two charts
                if len(available_charts) >= 4:
                    row2_charts = []
                    
                    # Third chart
                    chart3_content = self._create_compact_chart_for_risk(available_charts[2][0], available_charts[2][1])
                    row2_charts.append(chart3_content)
                    
                    # Fourth chart
                    chart4_content = self._create_compact_chart_for_risk(available_charts[3][0], available_charts[3][1])
                    row2_charts.append(chart4_content)
                    
                    # Create table for row 2
                    row2_table = Table([row2_charts], colWidths=[3.75*inch, 3.75*inch])
                    row2_table.setStyle(TableStyle([
                        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                        ('LEFTPADDING', (0, 0), (-1, -1), 5),
                        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
                        ('TOPPADDING', (0, 0), (-1, -1), 5),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
                    ]))
                    
                    self.story.append(row2_table)
                    self.story.append(Spacer(1, 0.2 * inch))
                elif len(available_charts) == 3:
                    # Handle case where only 3 charts available - put third chart centered
                    chart3_content = self._create_compact_chart_for_risk(available_charts[2][0], available_charts[2][1])
                    row2_table = Table([[chart3_content]], colWidths=[7.5*inch])
                    row2_table.setStyle(TableStyle([
                        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ]))
                    self.story.append(row2_table)
                    self.story.append(Spacer(1, 0.2 * inch))
                
                print(f"Successfully added {len(available_charts)} risk charts in 2x2 layout")
                
            except Exception as e:
                print(f"Error adding risk charts in 2x2 layout: {e}")
                import traceback
                traceback.print_exc()
        
    def _create_compact_chart_for_risk(self, chart_id, title):
            """Create a compact chart for risk analysis layout"""
            try:
                if chart_id not in self.chart_registry:
                    print(f"Chart ID '{chart_id}' not found in registry")
                    return ""
                    
                chart_info = self.chart_registry[chart_id]
                img_bytes = chart_info['image']
                
                if img_bytes is None:
                    print(f"No image data for chart '{chart_id}'")
                    return ""
                
                # # Create title
                # title_style = ParagraphStyle(
                #     name='RiskChartTitle',
                #     parent=self.styles['Normal'],
                #     fontSize=12,
                #     textColor=colors.HexColor("#1F3A4D"),
                #     alignment=TA_CENTER,
                #     fontName='Helvetica-Bold',
                #     spaceAfter=5,
                #     spaceBefore=0
                # )
                
                # chart_title = Paragraph(title, title_style)
                
                # Create drawing
                drawing, error = self._create_safe_svg_drawing(img_bytes)
                
                if error or drawing is None:
                    print(f"Failed to create drawing for '{chart_id}': {error}")
                    return chart_title  # Return at least the title
                
                # Compact size for 2x2 layout
                target_width = 3.5 * inch
                target_height = 2.8 * inch
                
                # Calculate scale factors
                original_width = getattr(drawing, 'width', 400)
                original_height = getattr(drawing, 'height', 400)
                
                if original_width <= 0 or original_height <= 0:
                    print(f"Invalid dimensions for '{chart_id}': {original_width}x{original_height}")
                    return chart_title
                    
                scale_x = target_width / original_width
                scale_y = target_height / original_height
                
                # Create properly scaled drawing
                from reportlab.graphics.shapes import Drawing, Group
                
                scaled_drawing = Drawing(target_width, target_height)
                content_group = Group()
                content_group.transform = (scale_x, 0, 0, scale_y, 0, 0)
                
                # Add original contents safely
                if hasattr(drawing, 'contents'):
                    for item in drawing.contents:
                        content_group.add(item)
                
                scaled_drawing.add(content_group)
                scaled_drawing.hAlign = 'CENTER'
                
                # Create container with title and chart
                #container_data = [[chart_title], [scaled_drawing]]
                container_data = [[scaled_drawing]]
                container_table = Table(container_data, colWidths=[3.5*inch])
                container_table.setStyle(TableStyle([
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ('TOPPADDING', (0, 0), (-1, -1), 0),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
                    ('LEFTPADDING', (0, 0), (-1, -1), 0),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                ]))
                
                print(f"Successfully created compact chart for '{chart_id}'")
                return container_table
                
            except Exception as e:
                print(f"Error creating compact chart for '{chart_id}': {e}")
                import traceback
                traceback.print_exc()
                return ""

   
 
           

    def add_risk_parameter_analysis(self):
        """Add Risk Parameter Analysis section"""
        try:
            # Section header with description
            risk_header_style = ParagraphStyle(
                name='RiskHeader',
                parent=self.styles['Heading2'],
                fontSize=18,
                textColor=colors.HexColor("#1134A6"),
                alignment=TA_LEFT,
                fontName='Helvetica-Bold',
                spaceAfter=12,
                spaceBefore=20
            )
            self.add_section_highlight_bar("V. Risk Parameter Analysis", text_color="#0E4C92")
            #self.story.append(Paragraph("Risk Parameter Analysis", risk_header_style))
            
            # Add description
            desc_style = ParagraphStyle(
                name='RiskDesc',
                parent=self.styles['Normal'],
                fontSize=11,
                textColor=colors.HexColor("#2C2C2C"),
                alignment=TA_JUSTIFY,
                fontName='Helvetica',
                leftIndent=0.25*inch,
                rightIndent=0.25*inch,
                leading=14,
                spaceAfter=16
            )
            
            description_text = """
            This section analyzes audit performance based on pre-defined GST risk parameters. 
            It helps identify which risks are most frequently associated with audit observations and which ones 
            contribute most to revenue detection and recovery. The charts are sorted to highlight the most significant parameters.
            """
            
            self.story.append(Paragraph(description_text, desc_style))
            
            # Get risk analysis data from vital_stats
            risk_summary_data = self.vital_stats.get('risk_summary', [])
            gstins_with_risk = self.vital_stats.get('gstins_with_risk_data', 4)
            paras_linked_to_risks = self.vital_stats.get('paras_linked_to_risks', 10)
            
            # Add metrics
            col1, col2 = st.columns(2) if 'st' in globals() else (None, None)
            
            # Create metrics table
            risk_metrics_data = [
                ['GSTINs with Risk Data', 'Paras Linked to Risks'],
                [f'{gstins_with_risk}', f'{paras_linked_to_risks}']
            ]
            
            risk_metrics_table = Table(risk_metrics_data, colWidths=[3.5*inch, 3.5*inch])
            risk_metrics_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('FONTNAME', (0, 1), (-1, 1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 1), (-1, 1), 18),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#E8F4F8")),
                ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor("#F0F8FF")),
                ('GRID', (0, 0), (-1, -1), 1, colors.HexColor("#CCCCCC")),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ]))
            
            self.story.append(risk_metrics_table)
            self.story.append(Spacer(1, 0.2 * inch))
            
            # Risk Parameter Summary Table Header
            risk_table_header_style = ParagraphStyle(
                name='RiskTableHeader',
                parent=self.styles['Heading3'],
                fontSize=14,
                textColor=colors.HexColor("#1F3A4D"),
                alignment=TA_LEFT,
                fontName='Helvetica-Bold',
                spaceAfter=12,
                spaceBefore=16
            )
              # Risk Parameter Charts in 2x2 Layout
            chart_header_style = ParagraphStyle(
                name='RiskChartHeader',
                parent=self.styles['Heading3'],
                fontSize=14,
                textColor=colors.HexColor("#1134A6"),
                alignment=TA_CENTER,
                fontName='Helvetica-Bold',
                spaceAfter=8,
                spaceBefore=12
            )
            
            self.story.append(Paragraph("📊 Risk Parameter Analysis Charts", chart_header_style))
            self.story.append(Spacer(1, 0.1 * inch))
            
            # Create 2x2 layout for risk charts
            self._add_risk_charts_2x2_layout()
            
      
            self.story.append(Paragraph("📊 Risk Parameter Summary", risk_table_header_style))
            
            if risk_summary_data:
                # Build table from actual data
                risk_data = [['RISK FLAG', 'RISK DESCRIPTION', 'NO.OF PARAS', 'TOTAL DETECTION ', 'TOTAL RECOVERY', 'RECOVERY %']]
                
                for risk_item in risk_summary_data:
                    risk_flag = risk_item.get('risk_flag', 'Unknown')
                    description = risk_item.get('description', 'Unknown Risk Code')[:60] + '...' if len(risk_item.get('description', '')) > 60 else risk_item.get('description', 'Unknown Risk Code')
                    paras = int(risk_item.get('Para_Count', 0))
                    detection = float(risk_item.get('Total_Detection', 0))
                    recovery = float(risk_item.get('Total_Recovery', 0))
                    recovery_pct = float(risk_item.get('Percentage_Recovery', 0))
                    
                    risk_data.append([
                        risk_flag,
                        description,
                        str(paras),
                        f'Rs.{detection:.2f} L',
                        f'Rs.{recovery:.2f} L',
                        f'{recovery_pct:.1f}%'
                    ])
            else:
                # Fallback data based on the image you shared
                risk_data = [
                    ['RISK FLAG', 'RISK DESCRIPTION', 'NO. OF PARAS', 'TOTAL DETECTION (Rs. L)', 'TOTAL RECOVERY (Rs. L)', 'RECOVERY %'],
                    ['P07', 'High ratio of tax paid through ITC to total tax payable', 'NA', 'NA', 'NA', 'NA'],
                    ['P10', 'High ratio of non-GST supplies to total turnover', 'NA', 'NA', 'NA', 'NA']
                  
                ]
            
            # Create the risk table with dynamic column widths
            risk_col_widths = [0.8*inch, 3.2*inch, 0.8*inch, 1.3*inch, 1.3*inch, 0.9*inch]
            risk_table = Table(risk_data, colWidths=risk_col_widths)
            
            # Apply colorful styling matching the image
            risk_table.setStyle(TableStyle([
                # Header styling with gradient colors
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#8B4A9C")),  # Purple header
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                
                # Data rows
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('ALIGN', (2, 1), (-1, -1), 'CENTER'),  # Numbers centered
                ('ALIGN', (0, 1), (1, -1), 'LEFT'),     # Flag and description left-aligned
                
                # Row background colors - creating the colorful effect from the image
                ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor("#E8F5E8")),    # Light green
                ('BACKGROUND', (0, 2), (-1, 2), colors.HexColor("#FFF3CD")),    # Light yellow  
                ('BACKGROUND', (0, 3), (-1, 3), colors.HexColor("#E2E3E5")),    # Light gray
                ('BACKGROUND', (0, 4), (-1, 4), colors.HexColor("#FFF3CD")),    # Light yellow
                ('BACKGROUND', (0, 5), (-1, 5), colors.HexColor("#D4EDDA")),    # Light green
                ('BACKGROUND', (0, 6), (-1, 6), colors.HexColor("#D4EDDA")),    # Light green
                
                # Grid and borders
                ('GRID', (0, 0), (-1, -1), 1, colors.HexColor("#CCCCCC")),
                ('LINEBELOW', (0, 0), (-1, 0), 2, colors.HexColor("#8B4A9C")),
                
                # Padding
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
                ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                
                # Vertical alignment
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))
            
            self.story.append(risk_table)
            self.story.append(Spacer(1, 0.3 * inch))
                
        except Exception as e:
              print(f"Error adding risk parameter analysis: {e}")#0, 0), (-1, -1), 'MIDDLE'),
        #     ]))
            
        #     self.story.append(performance_table)
        #     self.story.append(Spacer(1, 0.3 * inch))
            
        # except Exception as e:
        #     print(f"Error adding monthly performance summary: {e}")
        #     # Add error message if table creation fails
        #     error_style = ParagraphStyle(
        #         name='TableError',
        #         parent=self.styles['Normal'],
        #         fontSize=10,
        #         textColor=colors.red,
        #         alignment=TA_CENTER
        #     )
        #     self.story.append(Paragraph("Error loading performance summary table", error_style))

    def add_top_performance_analysis(self):
        """Add Section V - Top Audit Group and Circle Performance"""
        try:
            # Section header
            self.add_section_highlight_bar("VI. Top Audit Group and Circle Performance", text_color="#0E4C92")
            
            # Description
            desc_style = ParagraphStyle(
                name='PerformanceDesc',
                parent=self.styles['Normal'],
                fontSize=11,
                textColor=colors.HexColor("#2C2C2C"),
                alignment=TA_JUSTIFY,
                fontName='Helvetica',
                leftIndent=0.25*inch,
                rightIndent=0.25*inch,
                leading=14,
                spaceAfter=16
            )
            
            description_text = """
            This section highlights the top-performing audit groups and circles based on detection and recovery amounts. 
            """
            
            self.story.append(Paragraph(description_text, desc_style))
            
            # Chart heading style
            chart_header_style = ParagraphStyle(
                name='PerformanceChartHeader',
                parent=self.styles['Heading3'],
                fontSize=14,
                textColor=colors.HexColor("#1134A6"),
                alignment=TA_LEFT,
                fontName='Helvetica-Bold',
                spaceAfter=8,
                spaceBefore=12
            )
            
            # Group Performance Charts
            self.story.append(Paragraph("🏆 Top 10 Audit Groups by Detection Amount", chart_header_style))
            self.insert_chart_by_id("group_detection_performance", 
                                   size="medium", 
                                   add_title=False, 
                                   add_description=False)
            self.story.append(Spacer(1, 0.15 * inch))
            
            self.story.append(Paragraph("🏆 Top 10 Audit Groups by Recovery Amount", chart_header_style))
            self.insert_chart_by_id("group_recovery_performance", 
                                   size="medium", 
                                   add_title=False, 
                                   add_description=False)
            self.story.append(Spacer(1, 0.15 * inch))
            
            # Circle Performance Charts
            self.story.append(Paragraph("🎯 Circle-wise Detection Performance", chart_header_style))
            self.insert_chart_by_id("circle_detection_performance", 
                                   size="medium", 
                                   add_title=False, 
                                   add_description=False)
            self.story.append(Spacer(1, 0.15 * inch))
            
            self.story.append(Paragraph("🎯 Circle-wise Recovery Performance", chart_header_style))
            self.insert_chart_by_id("recovery_trends", 
                                   size="medium", 
                                   add_title=False, 
                                   add_description=False)
            self.story.append(Spacer(1, 0.2 * inch))
            
                       
        except Exception as e:
            print(f"Error adding top performance analysis: {e}")
    
    
    
    def add_top_taxpayers_analysis(self):
        """Add Section VI - Top Taxpayers of Detection and Recovery"""
        try:
            # Section header
            self.add_section_highlight_bar("VI. Top Taxpayers of Detection and Recovery", text_color="#0E4C92")
            
            # Description
            desc_style = ParagraphStyle(
                name='TaxpayerDesc',
                parent=self.styles['Normal'],
                fontSize=11,
                textColor=colors.HexColor("#2C2C2C"),
                alignment=TA_JUSTIFY,
                fontName='Helvetica',
                leftIndent=0.25*inch,
                rightIndent=0.25*inch,
                leading=14,
                spaceAfter=16
            )
            
            description_text = """
            This section provides hierarchical analysis of taxpayers with highest detection and recovery amounts. 
            The treemap visualizations show proportional representation of taxpayer categories and individual entities, 
            helping identify key contributors to audit performance and recovery potential.
            """
            
            self.story.append(Paragraph(description_text, desc_style))
            
            # Chart heading style
            chart_header_style = ParagraphStyle(
                name='TaxpayerChartHeader',
                parent=self.styles['Heading3'],
                fontSize=14,
                textColor=colors.HexColor("#1134A6"),
                alignment=TA_LEFT,
                fontName='Helvetica-Bold',
                spaceAfter=8,
                spaceBefore=12
            )
            
            # Detection Treemap
            self.story.append(Paragraph("🌳 Top Taxpayers by Detection Amount (Hierarchical View)", chart_header_style))
            self.insert_chart_by_id("detection_treemap", 
                                   size="large", 
                                   add_title=False, 
                                   add_description=False)
            self.story.append(Spacer(1, 0.2 * inch))
            
            Recovery Treemap
            self.story.append(Paragraph("🌳 Top Taxpayers by Recovery Amount (Hierarchical View)", chart_header_style))
            self.insert_chart_by_id("recovery_treemap", 
                                   size="large", 
                                   add_title=False, 
                                   add_description=False)
            self.story.append(Spacer(1, 0.2 * inch))
            
            # # Add top taxpayers summary table if data is available
            # if self.vital_stats.get('top_taxpayers_data'):
            #     self.add_top_taxpayers_summary_table()
                
        except Exception as e:
            print(f"Error adding top taxpayers analysis: {e}")

    def add_top_taxpayers_summary_table(self):
        """Add top taxpayers summary table"""
        try:
            top_taxpayers_data = self.vital_stats.get('top_taxpayers_data', {})
            
            if top_taxpayers_data:
                table_header_style = ParagraphStyle(
                    name='TopTaxpayersTableHeader',
                    parent=self.styles['Heading3'],
                    fontSize=14,
                    textColor=colors.HexColor("#1134A6"),
                    alignment=TA_LEFT,
                    fontName='Helvetica-Bold',
                    spaceAfter=12,
                    spaceBefore=16
                )
                
                # Top Detection Taxpayers Table
                top_detection = top_taxpayers_data.get('top_detection', [])
                if top_detection:
                    self.story.append(Paragraph("🏆 Top 5 Taxpayers by Detection Amount", table_header_style))
                    
                    detection_data = [['Trade Name', 'Category', 'Detection (Rs.L)', 'Recovery (Rs.L)', 'Recovery %']]
                    
                    for taxpayer in top_detection[:5]:
                        trade_name = str(taxpayer.get('trade_name', 'Unknown'))
                        # Truncate long trade names
                        if len(trade_name) > 40:
                            trade_name = trade_name[:37] + '...'
                        
                        category = taxpayer.get('category', 'Unknown')
                        detection = float(taxpayer.get('total_detection', 0))
                        recovery = float(taxpayer.get('total_recovery', 0))
                        recovery_pct = float(taxpayer.get('recovery_percentage', 0))
                        
                        detection_data.append([
                            trade_name,
                            category,
                            f'Rs.{detection:.2f} L',
                            f'Rs.{recovery:.2f} L',
                            f'{recovery_pct:.1f}%'
                        ])
                    
                    detection_table = Table(detection_data, colWidths=[2.5*inch, 1*inch, 1.3*inch, 1.3*inch, 1*inch])
                    detection_table.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#6F2E2E")),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, 0), 8),
                        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                        ('FONTSIZE', (0, 1), (-1, -1), 8),
                        ('ALIGN', (2, 1), (-1, -1), 'CENTER'),  # Center numeric columns
                        ('ALIGN', (0, 1), (1, -1), 'LEFT'),     # Left align text columns
                        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor("#CCCCCC")),
                        ('TOPPADDING', (0, 0), (-1, -1), 6),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                        # Alternating row colors
                        ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor("#F8F8F8")),
                        ('BACKGROUND', (0, 3), (-1, 3), colors.HexColor("#F8F8F8")),
                        ('BACKGROUND', (0, 5), (-1, 5), colors.HexColor("#F8F8F8")),
                    ]))
                    
                    self.story.append(detection_table)
                    self.story.append(Spacer(1, 0.15 * inch))
                
                # Top Recovery Taxpayers Table
                top_recovery = top_taxpayers_data.get('top_recovery', [])
                if top_recovery:
                    self.story.append(Paragraph("💎 Top 5 Taxpayers by Recovery Amount", table_header_style))
                    
                    recovery_data = [['Trade Name', 'Category', 'Detection (Rs.L)', 'Recovery (Rs.L)', 'Recovery %']]
                    
                    for taxpayer in top_recovery[:5]:
                        trade_name = str(taxpayer.get('trade_name', 'Unknown'))
                        # Truncate long trade names
                        if len(trade_name) > 40:
                            trade_name = trade_name[:37] + '...'
                        
                        category = taxpayer.get('category', 'Unknown')
                        detection = float(taxpayer.get('total_detection', 0))
                        recovery = float(taxpayer.get('total_recovery', 0))
                        recovery_pct = float(taxpayer.get('recovery_percentage', 0))
                        
                        recovery_data.append([
                            trade_name,
                            category,
                            f'Rs.{detection:.2f} L',
                            f'Rs.{recovery:.2f} L',
                            f'{recovery_pct:.1f}%'
                        ])
                    
                    recovery_table = Table(recovery_data, colWidths=[2.5*inch, 1*inch, 1.3*inch, 1.3*inch, 1*inch])
                    recovery_table.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#2E8B57")),  # Sea green
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, 0), 8),
                        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                        ('FONTSIZE', (0, 1), (-1, -1), 8),
                        ('ALIGN', (2, 1), (-1, -1), 'CENTER'),  # Center numeric columns
                        ('ALIGN', (0, 1), (1, -1), 'LEFT'),     # Left align text columns
                        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor("#CCCCCC")),
                        ('TOPPADDING', (0, 0), (-1, -1), 6),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                        # Alternating row colors
                        ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor("#F0FFF0")),
                        ('BACKGROUND', (0, 3), (-1, 3), colors.HexColor("#F0FFF0")),
                        ('BACKGROUND', (0, 5), (-1, 5), colors.HexColor("#F0FFF0")),
                    ]))
                    
                    self.story.append(recovery_table)
                    self.story.append(Spacer(1, 0.2 * inch))
            else:
                # Fallback message if no data
                info_style = ParagraphStyle(
                    name='InfoStyle',
                    parent=self.styles['Normal'],
                    fontSize=10,
                    textColor=colors.HexColor("#666666"),
                    alignment=TA_CENTER
                )
                self.story.append(Paragraph("No top taxpayers data available for this period.", info_style))
                    
        except Exception as e:
            print(f"Error adding top taxpayers summary table: {e}")
    
    
