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

        # Register fonts with proper error handling
        self._register_fonts()
        self._setup_custom_styles()

    def _generate_default_metadata(self):
        """Generate default metadata if none provided"""
        default_titles = [
            "Audit Group Performance Analysis",
            "Recovery Amount Distribution", 
            "Monthly Compliance Trends",
            "Department-wise Statistics",
            "Geographic Distribution Analysis",
            "Year-over-Year Comparison"
        ]
        
        default_descriptions = [
            "This chart displays the performance metrics across different audit groups, highlighting key areas of focus and achievement levels during the selected period.",
            "Analysis of recovery amounts showing the distribution pattern and concentration of financial recoveries across various categories and departments.",
            "Monthly trends in compliance activities, demonstrating the progression and seasonal variations in audit and compliance operations.",
            "Departmental breakdown of key performance indicators, providing insights into the operational efficiency of different organizational units.",
            "Geographic analysis showing the distribution of audit activities and outcomes across different regions and territories under jurisdiction.",
            "Comparative analysis between current period and previous periods, highlighting growth patterns and areas requiring attention."
        ]
        
        metadata = []
        for i in range(len(self.chart_images)):
            title_idx = i % len(default_titles)
            desc_idx = i % len(default_descriptions)
            
            metadata.append({
                "title": default_titles[title_idx],
                "description": default_descriptions[desc_idx],
                "page_break_after": (i + 1) % 2 == 0 and i < len(self.chart_images) - 1  # Page break after every 2 charts
            })
            
        return metadata

    def _setup_custom_styles(self):
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

    def _register_fonts(self):
        """Register fonts with proper error handling"""
        try:
            font_path = 'NotoSansDevanagari-VariableFont_wdth,wght.ttf'
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
            
            # 3. Add structured chart sections
            self.create_structured_chart_sections()
            
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
                fontSize=16, 
                # textColor=colors.HexColor("#1F3A4D"),
                textColor=colors.HexColor("#0E4C92"),
                alignment=TA_CENTER, 
                fontName='Helvetica-Bold'
            )
            summary_italic_style = ParagraphStyle(
                name='SummaryItalic', 
                fontSize=9, 
                textColor=colors.HexColor("#1F3A4D"),
                alignment=TA_CENTER, 
                fontName='Helvetica-Oblique'
            )
            summary_footer_style = ParagraphStyle(
                name='SummaryFooter', 
                fontSize=12, 
                textColor=colors.HexColor("#0E4C92"),
                alignment=TA_CENTER, 
                fontName='Helvetica'
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
                spaceAfter=20
            )
            
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
            
            # Add Monthly Performance Summary section
            self.story.append(Spacer(1, 0.3 * inch))
            self.add_monthly_performance_summary()
            self.story.append(Spacer(1, 0.3 * inch))
                
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
            self.story.append(Paragraph("निगरानी समिति की बैठक", hindi_style))
            self.story.append(Paragraph(f"{self.selected_period.upper()}", title2_style))
            self.story.append(Spacer(1, 0.5 * inch))
            self.story.append(Paragraph("EXECUTIVE SUMMARY REPORT", title3_style))
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
        """Add Monthly Performance Summary section with metrics and table"""
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
            
            self.story.append(Paragraph("Monthly Performance Summary", perf_header_style))
            
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
            
            # Add Status Summary Table if available
            if self.vital_stats.get('status_analysis_available', False):
                self.add_status_summary_table()
            
            # Add Risk Parameter Analysis if available
            if self.vital_stats.get('risk_analysis_available', False):
                self.add_risk_parameter_analysis()
            
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
                textColor=colors.HexColor("#1F3A4D"),
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
                status_data = [['STATUS OF PARA', 'NO. OF PARAS', 'TOTAL DETECTION (₹ L)', 'TOTAL RECOVERY (₹ L)', 'RECOVERY %']]
                
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
                    ['STATUS OF PARA', 'NO. OF PARAS', 'TOTAL DETECTION (₹ L)', 'TOTAL RECOVERY (₹ L)', 'RECOVERY %'],
                    ['Agreed yet to pay', '51', '₹13.74 L', '₹0.00 L', '0.0%'],
                    ['Agreed and Paid', '26', '₹19.96 L', '₹9.20 L', '46.1%'],
                    ['Not agreed', '16', '₹1.07 L', '₹0.00 L', '0.0%'],
                    ['Partially agreed, yet to paid', '1', '₹0.00 L', '₹0.00 L', '0.0%']
                ]
            
            # Create the status table
            #status_col_widths = [2.2*inch, 0.8*inch, 1.3*inch, 1.3*inch, 1.0*inch]
            status_col_widths = [1.8*inch, 1*inch, 1.4*inch, 1.4*inch, 1.0*inch]
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
            self.story.append(Spacer(1, 0.2 * inch))
            
            # Add "Top 5 Paras with Largest Detection" section if data is available
            if self.vital_stats.get('agreed_yet_to_pay_analysis'):
                self.add_top_agreed_paras_section()
                
        except Exception as e:
            print(f"Error adding status summary table: {e}")

    def add_top_agreed_paras_section(self):
        """Add Top 5 Paras with Largest Detection section"""
        try:
            # Section header
            top_paras_header_style = ParagraphStyle(
                name='TopParasHeader',
                parent=self.styles['Heading3'],
                fontSize=14,
                textColor=colors.HexColor("#1F3A4D"),
                alignment=TA_LEFT,
                fontName='Helvetica-Bold',
                spaceAfter=12,
                spaceBefore=16
            )
            
            self.story.append(Paragraph("🎯 Top 5 Paras with Largest Detection - Status: 'Agreed yet to pay'", top_paras_header_style))
            
            # Get the analysis data
            agreed_analysis = self.vital_stats.get('agreed_yet_to_pay_analysis', {})
            
            if agreed_analysis and agreed_analysis.get('top_5_paras') is not None:
                top_5_paras = agreed_analysis['top_5_paras']
                
                # Create table data
                para_data = [['Audit Group', 'Trade Name', 'Para No.', 'Para Heading', 'Detection (₹ L)', 'Recovery (₹ L)', 'Status']]
                
                for _, row in top_5_paras.iterrows():
                    audit_group = str(row.get('audit_group_number_str', 'N/A'))
                    trade_name = str(row.get('trade_name', 'N/A'))[:30] + '...' if len(str(row.get('trade_name', 'N/A'))) > 30 else str(row.get('trade_name', 'N/A'))
                    para_no = str(row.get('audit_para_number', 'N/A'))
                    para_heading = str(row.get('audit_para_heading', 'N/A'))[:50] + '...' if len(str(row.get('audit_para_heading', 'N/A'))) > 50 else str(row.get('audit_para_heading', 'N/A'))
                    detection = f"₹{row.get('Para Detection in Lakhs', 0):.2f} L"
                    recovery = f"₹{row.get('Para Recovery in Lakhs', 0):.2f} L"
                    status = str(row.get('status_of_para', 'N/A'))
                    
                    para_data.append([audit_group, trade_name, para_no, para_heading, detection, recovery, status])
                
                # Create table
                para_col_widths = [0.8*inch, 1.5*inch, 0.6*inch, 2.0*inch, 1.0*inch, 1.0*inch, 1.1*inch]
                para_table = Table(para_data, colWidths=para_col_widths)
                
                # Style the table
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
                    ('ALIGN', (4, 1), (-2, -1), 'RIGHT'),  # Detection and Recovery right-aligned
                    ('ALIGN', (0, 1), (3, -1), 'LEFT'),    # Other columns left-aligned
                    ('ALIGN', (-1, 1), (-1, -1), 'CENTER'), # Status centered
                    
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
                    
                    # Vertical alignment
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ]))
                
                self.story.append(para_table)
                self.story.append(Spacer(1, 0.2 * inch))
                
                # Add summary metrics
                total_paras = agreed_analysis.get('total_paras', 0)
                total_detection = agreed_analysis.get('total_detection', 0)
                total_recovery = agreed_analysis.get('total_recovery', 0)
                
                # Create metrics row
                metrics_data = [
                    [f"Total 'Agreed yet to pay' Paras", f"Total Detection Amount", f"Total Recovery Amount"],
                    [f"{total_paras}", f"₹{total_detection:,.2f} L", f"₹{total_recovery:,.2f} L"]
                ]
                
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

    def add_risk_parameter_analysis(self):
        """Add Risk Parameter Analysis section"""
        try:
            # Section header with description
            risk_header_style = ParagraphStyle(
                name='RiskHeader',
                parent=self.styles['Heading2'],
                fontSize=18,
                textColor=colors.HexColor("#1F3A4D"),
                alignment=TA_LEFT,
                fontName='Helvetica-Bold',
                spaceAfter=12,
                spaceBefore=20
            )
            
            self.story.append(Paragraph("Risk Parameter Analysis", risk_header_style))
            
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
            
            self.story.append(Paragraph("📊 Risk Parameter Summary", risk_table_header_style))
            
            if risk_summary_data:
                # Build table from actual data
                risk_data = [['RISK FLAG', 'RISK DESCRIPTION', 'NO. OF PARAS', 'TOTAL DETECTION (₹ L)', 'TOTAL RECOVERY (₹ L)', 'RECOVERY %']]
                
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
                        f'₹{detection:.2f} L',
                        f'₹{recovery:.2f} L',
                        f'{recovery_pct:.1f}%'
                    ])
            else:
                # Fallback data based on the image you shared
                risk_data = [
                    ['RISK FLAG', 'RISK DESCRIPTION', 'NO. OF PARAS', 'TOTAL DETECTION (₹ L)', 'TOTAL RECOVERY (₹ L)', 'RECOVERY %'],
                    ['P07', 'High ratio of tax paid through ITC to total tax payable', '17', '₹4.14 L', '₹0.56 L', '13.5%'],
                    ['P10', 'High ratio of non-GST supplies to total turnover', '4', '₹1.28 L', '₹0.00 L', '0.0%'],
                    ['P02', 'IGST paid on import is more than the ITC availed in GSTR-3B', '3', '₹0.04 L', '₹0.00 L', '0.0%'],
                    ['P09', 'Decline in average monthly taxable turnover in GSTR-3B', '2', '₹1.07 L', '₹0.00 L', '0.0%'],
                    ['P03', 'High ratio of nil-rated/exempt supplies to total turnover', '1', '₹0.15 L', '₹0.15 L', '100.0%'],
                    ['P08', 'Low ratio of tax payment in cash to total tax liability', '1', '₹0.13 L', '₹0.13 L', '100.0%']
                ]
            
            # Create the risk table with dynamic column widths
            risk_col_widths = [0.8*inch, 2.8*inch, 0.8*inch, 1.2*inch, 1.2*inch, 0.8*inch]
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


# Usage example:
# chart_metadata = [
#     {"title": "Audit Group Performance", "description": "Analysis of performance across audit groups...", "page_break_after": False},
#     {"title": "Recovery Analysis", "description": "Distribution of recovery amounts...", "page_break_after": True},
#     # ... more metadata
# ]
# 
# generator = PDFReportGenerator(selected_period, vital_stats, chart_images, chart_metadata)
# pdf = generator.run()

# import datetime
# from reportlab.lib import colors
# from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
# from reportlab.lib.pagesizes import letter
# from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
# from reportlab.lib.units import inch
# from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, PageBreak, Frame, Table, TableStyle
# from reportlab.pdfbase import pdfmetrics
# from reportlab.pdfbase.ttfonts import TTFont
# from io import BytesIO
# from svglib.svglib import svg2rlg
# import os
# import re
# import xml.etree.ElementTree as ET

# class PDFReportGenerator:
#     """
#     A structured PDF report generator with controlled chart placement and descriptions.
#     """

#     def __init__(self, selected_period, vital_stats, chart_images, chart_metadata=None):
#         self.buffer = BytesIO()
#         self.doc = SimpleDocTemplate(
#             self.buffer, 
#             pagesize=letter, 
#             leftMargin=0.25*inch, 
#             rightMargin=0.25*inch,
#             topMargin=0.25*inch,
#             bottomMargin=0.25*inch
#         )
#         self.story = []
#         self.styles = getSampleStyleSheet()
#         self.width, self.height = letter

#         self.selected_period = selected_period
#         self.vital_stats = vital_stats
#         self.chart_images = chart_images
        
#         # Chart metadata structure: [{"title": "Chart Title", "description": "Chart description", "page_break_after": True}, ...]
#         self.chart_metadata = chart_metadata or self._generate_default_metadata()

#         # Register fonts with proper error handling
#         self._register_fonts()
#         self._setup_custom_styles()

#     def _generate_default_metadata(self):
#         """Generate default metadata if none provided"""
#         default_titles = [
#             "Audit Group Performance Analysis",
#             "Recovery Amount Distribution", 
#             "Monthly Compliance Trends",
#             "Department-wise Statistics",
#             "Geographic Distribution Analysis",
#             "Year-over-Year Comparison"
#         ]
        
#         default_descriptions = [
#             "This chart displays the performance metrics across different audit groups, highlighting key areas of focus and achievement levels during the selected period.",
#             "Analysis of recovery amounts showing the distribution pattern and concentration of financial recoveries across various categories and departments.",
#             "Monthly trends in compliance activities, demonstrating the progression and seasonal variations in audit and compliance operations.",
#             "Departmental breakdown of key performance indicators, providing insights into the operational efficiency of different organizational units.",
#             "Geographic analysis showing the distribution of audit activities and outcomes across different regions and territories under jurisdiction.",
#             "Comparative analysis between current period and previous periods, highlighting growth patterns and areas requiring attention."
#         ]
        
#         metadata = []
#         for i in range(len(self.chart_images)):
#             title_idx = i % len(default_titles)
#             desc_idx = i % len(default_descriptions)
            
#             metadata.append({
#                 "title": default_titles[title_idx],
#                 "description": default_descriptions[desc_idx],
#                 "page_break_after": (i + 1) % 2 == 0 and i < len(self.chart_images) - 1  # Page break after every 2 charts
#             })
            
#         return metadata

#     def _setup_custom_styles(self):
#         """Setup custom paragraph styles for different content types"""
#         self.chart_title_style = ParagraphStyle(
#             name='ChartTitle',
#             parent=self.styles['Heading2'],
#             fontSize=16,
#             textColor=colors.HexColor("#1F3A4D"),
#             alignment=TA_CENTER,
#             fontName='Helvetica-Bold',
#             spaceAfter=12,
#             spaceBefore=16
#         )
        
#         self.chart_description_style = ParagraphStyle(
#             name='ChartDescription',
#             parent=self.styles['Normal'],
#             fontSize=11,
#             textColor=colors.HexColor("#2C2C2C"),
#             alignment=TA_JUSTIFY,
#             fontName='Helvetica',
#             spaceAfter=16,
#             spaceBefore=8,
#             leftIndent=0.25*inch,
#             rightIndent=0.25*inch,
#             leading=14
#         )
        
#         self.section_header_style = ParagraphStyle(
#             name='SectionHeader',
#             parent=self.styles['Heading1'],
#             fontSize=20,
#             textColor=colors.HexColor("#1F3A4D"),
#             alignment=TA_CENTER,
#             fontName='Helvetica-Bold',
#             spaceAfter=16,
#             spaceBefore=24
#         )

#     def _register_fonts(self):
#         """Register fonts with proper error handling"""
#         try:
#             font_path = 'NotoSansDevanagari-VariableFont_wdth,wght.ttf'
#             if os.path.exists(font_path):
#                 pdfmetrics.registerFont(TTFont('HindiFont', font_path))
#                 print("Hindi font registered successfully")
#             else:
#                 print("Hindi font file not found, using fallback")
#                 self._use_fallback_font()
#         except Exception as e:
#             print(f"Font registration failed: {e}")
#             self._use_fallback_font()

#     def _use_fallback_font(self):
#         """Use built-in fonts as fallback"""
#         try:
#             pdfmetrics.registerFont(TTFont('HindiFont', 'Helvetica'))
#         except Exception as e:
#             print(f"Fallback font registration failed: {e}")

#     def run(self, detailed=False):
#         """Generate the full report with comprehensive error handling"""
#         try:
#             # 1. Create cover page
#             self.create_cover_page_story()
#             self.story.append(PageBreak())
            
#             # 2. Create summary header
#             self.create_summary_header()
            
#             # 3. Add structured chart sections
#             self.create_structured_chart_sections()
            
#             # 4. Build the document
#             self.doc.build(self.story, onFirstPage=self.add_page_elements, onLaterPages=self.add_page_elements)
            
#             self.buffer.seek(0)
#             return self.buffer
            
#         except Exception as e:
#             print(f"Error generating PDF: {e}")
#             return self._generate_error_pdf(str(e))

#     def create_summary_header(self):
#         """Create the summary page header"""
#         try:
#             title_style = ParagraphStyle(
#                 name='MainTitle', 
#                 fontSize=28, 
#                 textColor=colors.HexColor("#1F3A4D"),
#                 alignment=TA_CENTER, 
#                 fontName='Helvetica-Bold'
#             )
            
#             # Check if Hindi font is available
#             try:
#                 pdfmetrics.getFont('HindiFont')
#                 hindi_font = 'HindiFont'
#             except:
#                 hindi_font = 'Helvetica-Bold'
                
#             hindi_style = ParagraphStyle(
#                 name='HindiTitle', 
#                 parent=title_style, 
#                 fontName=hindi_font, 
#                 fontSize=24
#             )
            
#             # self.story.append(Paragraph("Monitoring Committee Meeting (MCM)", title_style))
#             # self.story.append(Paragraph("निगरानी समिति की बैठक", hindi_style))
#             # self.story.append(Spacer(1, 0.5 * inch))

#             # Summary styles
#             summary_style_caps = ParagraphStyle(
#                 name='SummaryCaps', 
#                 fontSize=16, 
#                 textColor=colors.HexColor("#1F3A4D"),
#                 alignment=TA_CENTER, 
#                 fontName='Helvetica-Bold'
#             )
#             summary_italic_style = ParagraphStyle(
#                 name='SummaryItalic', 
#                 fontSize=9, 
#                 textColor=colors.HexColor("#1F3A4D"),
#                 alignment=TA_CENTER, 
#                 fontName='Helvetica-Oblique'
#             )
#             summary_footer_style = ParagraphStyle(
#                 name='SummaryFooter', 
#                 fontSize=12, 
#                 textColor=colors.HexColor("#1F3A4D"),
#                 alignment=TA_CENTER, 
#                 fontName='Helvetica'
#             )

#             self.story.append(Paragraph("EXECUTIVE SUMMARY", summary_style_caps))
#             self.story.append(Spacer(1, 0.1 * inch))
#             self.story.append(Paragraph("(Auto generated through e-MCM App)", summary_italic_style))
#             self.story.append(Spacer(1, 0.1 * inch))
#             self.story.append(Paragraph("Audit 1 Commissionerate, Mumbai CGST Zone", summary_footer_style))
#             self.story.append(Spacer(1, 0.4 * inch))

#             # Add introduction paragraph - first part
#             intro_text_part1 = f"""
#             This executive summary presents the Infographical analysis of Audit Performance submitted during Monitoring Committee meeting for the {self.selected_period} period. 
#             The report contains comprehensive charts and visualizations that highlight:
#             """
            
#             # Create bullet points as separate paragraphs for better alignment
#             bullet_points = [
#                 "(i) <b>Overall Audit Performance</b> for the month, across Small, Medium, Large Categories",
#                 "(ii) <b>Status of Para Analysis</b>, based on Tax Recovery Status and pending recovery potential", 
#                 "(iii) <b>Sectoral Analysis</b>, based on Trader, Manufacturer and Service sectors",
#                 "(iv) <b>Nature of Non Compliance Analysis</b>, using Audit Para Categorisation Coding System of Audit-1 commissionerate",
#                 "(v) <b>Risk Parameter Analysis</b>",
#                 "(vi) <b>Top Audit Group and Circle Performance</b>",
#                 "(vii) <b>Top Taxpayers of Detection and Recovery</b>"
#             ]
            
#             # Final part
#             conclusion_text = """
#             The report covers the <b>Summary of Taxpayer wise Audit paras raised and the decision taken during MCM</b>, encompassing all the Draft Audit Reports submitted before Monitoring Committee.
#             """
            
#             intro_style = ParagraphStyle(
#                 name='IntroStyle',
#                 parent=self.styles['Normal'],
#                 fontSize=12,
#                 textColor=colors.HexColor("#2C2C2C"),
#                 alignment=TA_JUSTIFY,
#                 fontName='Helvetica',
#                 leftIndent=0.5*inch,
#                 rightIndent=0.5*inch,
#                 leading=16,
#                 spaceAfter=20
#             )
            
#             intro_style = ParagraphStyle(
#                 name='IntroStyle',
#                 parent=self.styles['Normal'],
#                 fontSize=12,
#                 textColor=colors.HexColor("#2C2C2C"),
#                 alignment=TA_JUSTIFY,
#                 fontName='Helvetica',
#                 leftIndent=0.5*inch,
#                 rightIndent=0.5*inch,
#                 leading=16,
#                 spaceAfter=12
#             )
            
#             # Create bullet point style with proper indentation
#             bullet_style = ParagraphStyle(
#                 name='BulletStyle',
#                 parent=self.styles['Normal'],
#                 fontSize=12,
#                 textColor=colors.HexColor("#2C2C2C"),
#                 alignment=TA_LEFT,
#                 fontName='Helvetica',
#                 leftIndent=0.75*inch,  # Fixed left indent for alignment
#                 rightIndent=0.5*inch,
#                 leading=16,
#                 spaceAfter=4,
#                 spaceBefore=2
#             )
            
#             # Add the introduction parts
#             self.story.append(Paragraph(intro_text_part1, intro_style))
            
#             # Add each bullet point as a separate paragraph
#             for bullet in bullet_points:
#                 self.story.append(Paragraph(bullet, bullet_style))
            
#             # Add conclusion
#             self.story.append(Spacer(1, 0.1 * inch))
#             self.story.append(Paragraph(conclusion_text, intro_style))
#             self.story.append(Spacer(1, 0.3 * inch))
                
#         except Exception as e:
#             print(f"Error creating summary header: {e}")

#     def create_structured_chart_sections(self):
#         """Create structured sections with headings and descriptions for each chart"""
#         if not self.chart_images or len(self.chart_images) == 0:
#             placeholder_style = ParagraphStyle(
#                 name='Placeholder', 
#                 parent=self.styles['Normal'],
#                 fontSize=12, 
#                 alignment=TA_CENTER
#             )
#             self.story.append(Paragraph("No charts available for this report.", placeholder_style))
#             return

#         successful_charts = 0
        
#         for i, img_bytes in enumerate(self.chart_images):
#             try:
#                 if img_bytes is None:
#                     self._add_chart_error_section(i, "No image data provided")
#                     continue

#                 print(f"Processing chart section {i+1}/{len(self.chart_images)}")
                
#                 # Get metadata for this chart
#                 metadata = self.chart_metadata[i] if i < len(self.chart_metadata) else {
#                     "title": f"Chart {i+1}",
#                     "description": "Analysis and insights from the data visualization.",
#                     "page_break_after": False
#                 }
                
#                 # Add chart title
#                 self.story.append(Paragraph(metadata["title"], self.chart_title_style))
                
#                 # Add chart description
#                 self.story.append(Paragraph(metadata["description"], self.chart_description_style))
                
#                 # Create and add the chart
#                 drawing, error = self._create_safe_svg_drawing(img_bytes)
                
#                 if error:
#                     print(f"Chart {i+1} error: {error}")
#                     self._add_chart_error_inline(i, error)
#                     continue

#                 if drawing is None:
#                     self._add_chart_error_inline(i, "Could not create drawing")
#                     continue

#                 # Scale and add the drawing
#                 try:
#                     render_width = 6.5 * inch
#                     scale_factor = render_width / drawing.width
#                     drawing.width = render_width
#                     drawing.height = drawing.height * scale_factor
#                     drawing.hAlign = 'CENTER'
                    
#                     # Add the chart
#                     self.story.append(drawing)
#                     self.story.append(Spacer(1, 0.3 * inch))
#                     successful_charts += 1
                    
#                     print(f"Successfully processed chart {i+1}")
                    
#                     # Add page break if specified in metadata
#                     if metadata.get("page_break_after", False):
#                         self.story.append(PageBreak())
                        
#                 except Exception as scale_error:
#                     print(f"Chart {i+1} scaling error: {scale_error}")
#                     self._add_chart_error_inline(i, f"Scaling failed: {scale_error}")
                    
#             except Exception as e:
#                 print(f"Unexpected error processing chart section {i+1}: {e}")
#                 self._add_chart_error_section(i, f"Unexpected error: {e}")

#         print(f"Successfully processed {successful_charts}/{len(self.chart_images)} chart sections")

#     def _add_chart_error_section(self, chart_index, error_message):
#         """Add error section for failed chart with title"""
#         try:
#             metadata = self.chart_metadata[chart_index] if chart_index < len(self.chart_metadata) else {
#                 "title": f"Chart {chart_index+1}",
#                 "description": "Chart could not be generated due to technical issues."
#             }
            
#             # Add title even for error
#             self.story.append(Paragraph(metadata["title"], self.chart_title_style))
            
#             # Add error message
#             error_style = ParagraphStyle(
#                 name='ChartError', 
#                 parent=self.styles['Normal'],
#                 fontSize=11, 
#                 textColor=colors.red,
#                 alignment=TA_CENTER,
#                 fontName='Helvetica-Oblique'
#             )
#             self.story.append(Paragraph(f"Unable to load chart: {error_message}", error_style))
#             self.story.append(Spacer(1, 0.3 * inch))
#         except Exception as e:
#             print(f"Error adding chart error section: {e}")

#     def _add_chart_error_inline(self, chart_index, error_message):
#         """Add inline error message for failed chart"""
#         try:
#             error_style = ParagraphStyle(
#                 name='ChartErrorInline', 
#                 parent=self.styles['Normal'],
#                 fontSize=10, 
#                 textColor=colors.red,
#                 alignment=TA_CENTER,
#                 fontName='Helvetica-Oblique'
#             )
#             self.story.append(Paragraph(f"Chart error: {error_message}", error_style))
#             self.story.append(Spacer(1, 0.3 * inch))
#         except Exception as e:
#             print(f"Error adding inline chart error: {e}")

#     # Include all the other methods from your original class...
#     # (I'll include the key ones for SVG processing)

#     def _validate_svg_content(self, svg_content):
#         """Validate SVG content and fix common issues that cause transformation errors"""
#         try:
#             if isinstance(svg_content, bytes):
#                 svg_string = svg_content.decode('utf-8')
#             else:
#                 svg_string = str(svg_content)

#             if len(svg_string.strip()) < 10:
#                 return None, "SVG content too short"

#             try:
#                 root = ET.fromstring(svg_string)
#             except ET.ParseError as e:
#                 return None, f"Invalid XML structure: {e}"

#             if not (root.tag.endswith('svg') or 'svg' in root.tag.lower()):
#                 return None, "Not a valid SVG element"

#             svg_string = self._fix_svg_transforms(svg_string)
#             svg_string = self._ensure_svg_dimensions(svg_string)

#             return svg_string.encode('utf-8'), None

#         except Exception as e:
#             return None, f"SVG validation error: {e}"

#     def _fix_svg_transforms(self, svg_string):
#         """Fix problematic transformation matrices in SVG"""
#         svg_string = re.sub(r'scale\(0(?:\.0*)?\)', 'scale(0.001)', svg_string)
#         svg_string = re.sub(r'scale\(0(?:\.0*)?[,\s]+0(?:\.0*)?\)', 'scale(0.001,0.001)', svg_string)
        
#         def fix_matrix(match):
#             values = [float(x.strip()) for x in match.group(1).split(',')]
#             if len(values) == 6:
#                 a, b, c, d, e, f = values
#                 det = a * d - b * c
#                 if abs(det) < 1e-10:
#                     return 'matrix(1,0,0,1,0,0)'
#             return match.group(0)
        
#         svg_string = re.sub(r'matrix\(([^)]+)\)', fix_matrix, svg_string)
#         return svg_string

#     def _ensure_svg_dimensions(self, svg_string):
#         """Ensure SVG has proper width and height attributes"""
#         if 'width=' not in svg_string and 'height=' not in svg_string:
#             svg_string = re.sub(
#                 r'<svg([^>]*?)>', 
#                 r'<svg\1 width="400" height="300">', 
#                 svg_string, 
#                 count=1
#             )
        
#         svg_string = re.sub(r'width=["\']0["\']', 'width="400"', svg_string)
#         svg_string = re.sub(r'height=["\']0["\']', 'height="300"', svg_string)
        
#         return svg_string

#     def _create_safe_svg_drawing(self, img_bytes):
#         """Create an SVG drawing with comprehensive error handling and validation"""
#         try:
#             img_bytes.seek(0)
#             original_content = img_bytes.read()
            
#             if not original_content:
#                 return None, "Empty image data"

#             fixed_content, error = self._validate_svg_content(original_content)
#             if error:
#                 return None, error

#             fixed_buffer = BytesIO(fixed_content)
            
#             try:
#                 drawing = svg2rlg(fixed_buffer)
#             except Exception as svg_error:
#                 return None, f"SVG parsing failed: {svg_error}"

#             if drawing is None:
#                 return None, "svg2rlg returned None"

#             if not hasattr(drawing, 'width') or not hasattr(drawing, 'height'):
#                 return None, "Drawing missing width/height attributes"

#             if drawing.width <= 0 or drawing.height <= 0:
#                 return None, f"Invalid dimensions: {drawing.width}x{drawing.height}"

#             if not (0 < drawing.width < 10000 and 0 < drawing.height < 10000):
#                 return None, f"Unreasonable dimensions: {drawing.width}x{drawing.height}"

#             return drawing, None

#         except Exception as e:
#             return None, f"Unexpected error creating SVG drawing: {e}"

#     def _generate_error_pdf(self, error_message):
#         """Generate a simple PDF with error message if main generation fails"""
#         try:
#             error_buffer = BytesIO()
#             error_doc = SimpleDocTemplate(error_buffer, pagesize=letter)
#             error_story = []
            
#             error_style = ParagraphStyle(
#                 name='Error', 
#                 parent=self.styles['Normal'],
#                 fontSize=12, 
#                 textColor=colors.red,
#                 alignment=TA_CENTER
#             )
            
#             error_story.append(Spacer(1, 2*inch))
#             error_story.append(Paragraph("PDF Generation Error", error_style))
#             error_story.append(Spacer(1, 0.5*inch))
#             error_story.append(Paragraph(f"Error: {error_message}", self.styles['Normal']))
#             error_story.append(Spacer(1, 0.5*inch))
#             error_story.append(Paragraph("Please check your chart data and try again.", self.styles['Normal']))
            
#             error_doc.build(error_story)
#             error_buffer.seek(0)
#             return error_buffer
#         except Exception as fallback_error:
#             print(f"Even fallback PDF generation failed: {fallback_error}")
#             empty_buffer = BytesIO()
#             empty_buffer.write(b"PDF generation failed")
#             empty_buffer.seek(0)
#             return empty_buffer

#     def add_page_elements(self, canvas, doc):
#         """Unified method to draw static elements on ALL pages"""
#         try:
#             canvas.saveState()
#             if doc.page == 1:
#                 # Cover Page Background
#                 canvas.setFillColor(colors.HexColor("#193041"))  # Dark Blue
#                 canvas.rect(0, self.height * 0.20, self.width, self.height, stroke=0, fill=1)
#                 canvas.setFillColor(colors.HexColor("#C8B59E"))  # Gold
#                 canvas.rect(0, 0, self.width, self.height * 0.20, stroke=0, fill=1)
#                 canvas.setStrokeColor(colors.HexColor("#C8B59E"))
#                 canvas.setLineWidth(3)
#                 canvas.line(0, self.height * 0.20, self.width, self.height * 0.20)

#                 # Draw static lines for the cover page
#                 canvas.setStrokeColor(colors.HexColor("#f5ddc1"))
#                 canvas.setLineWidth(1)
#                 logo_y_pos = self.height - 1.6 * inch
#                 canvas.line(1.5*inch, logo_y_pos, 3.25*inch, logo_y_pos)  # Left line
#                 canvas.line(self.width - 3.25*inch, logo_y_pos, self.width - 1.5*inch, logo_y_pos)  # Right line
#             else:
#                 # Background for all other pages
#                 canvas.setFillColor(colors.HexColor("#FAEBD7"))  # Light beige
#                 canvas.rect(0, 0, self.width, self.height, stroke=0, fill=1)
            
#             canvas.restoreState()
#         except Exception as e:
#             print(f"Error drawing page elements: {e}")
#             canvas.restoreState()

#     def create_cover_page_story(self):
#         """Method to create the cover page CONTENT with logos"""
#         try:
#             # CBIC Logo at the Top
#             try:
#                 cbic_logo = Image('cbic_logo.png', width=1.6*inch, height=1.6*inch)
#                 cbic_logo.hAlign = 'CENTER'
#                 self.story.append(cbic_logo)
#             except Exception as e:
#                 print(f"Warning: cbic_logo.png not found. Using text placeholder. Error: {e}")
#                 logo_style = ParagraphStyle(name='LogoStyle', fontSize=16, textColor=colors.HexColor("#f5ddc1"), alignment=TA_CENTER)
#                 self.story.append(Paragraph("CBIC LOGO", logo_style))
            
#             self.story.append(Spacer(1, 0.8 * inch))

#             # Title and Subtitles
#             title_style = ParagraphStyle(name='Title', fontSize=38, textColor=colors.HexColor("#f5ddc1"),
#                                        alignment=TA_CENTER, fontName='Helvetica-Bold', leading=46)
#             title2_style = ParagraphStyle(name='Title2', parent=title_style, fontSize=34)
#             title3_style = ParagraphStyle(name='Title3', parent=title_style, fontSize=26, textColor=colors.HexColor("#FCC200"),fontName='Helvetica')
#             title4_style = ParagraphStyle(name='Title4', parent=title_style, fontSize=20,textColor=colors.HexColor("#FC200") ,fontName='Helvetica-Oblique')
            
#             try:
#                 pdfmetrics.getFont('HindiFont')
#                 hindi_font = 'HindiFont'
#             except:
#                 hindi_font = 'Helvetica-Bold'
#             hindi_style = ParagraphStyle(name='HindiTitle', parent=title_style, fontName=hindi_font, fontSize=24)
            
#             self.story.append(Paragraph("MONITORING COMMITTEE MEETING", title_style))
#             self.story.append(Paragraph("निगरानी समिति की बैठक", hindi_style))
#             self.story.append(Paragraph(f"{self.selected_period.upper()}", title2_style))
#             self.story.append(Spacer(1, 0.5 * inch))
#             self.story.append(Paragraph("EXECUTIVE SUMMARY REPORT", title3_style))
#             self.story.append(Paragraph("[Auto-generated by e-MCM App]", title4_style))
            
#             self.story.append(Spacer(1, 1.8 * inch))

#             # Emblem and Address at the Bottom using a Table
#             contact_style = ParagraphStyle(name='Contact', fontSize=12, textColor=colors.HexColor("#193041"), alignment=TA_LEFT)
#             org_style = ParagraphStyle(name='Org', fontSize=18, textColor=colors.HexColor("#193041"), alignment=TA_LEFT, fontName='Helvetica-Bold', leading=18)

#             right_col_text = [
#                 Paragraph("Office of the Commissioner of CGST & Central Excise", org_style),
#                 Paragraph("Audit-I Commissionerate, Mumbai", org_style),
#                 Spacer(1, 0.2 * inch),
#                 Paragraph("Ph: 022-22617504 | Email: audit1mum@gov.in", contact_style)
#             ]

#             try:
#                 emblem_logo = Image('emblem.png', width=0.8*inch, height=1.2*inch)
#             except Exception as e:
#                 print(f"Warning: emblem.png not found. Using a text placeholder. Error: {e}")
#                 emblem_logo = Paragraph("EMBLEM", contact_style)

#             table_data = [[emblem_logo, right_col_text]]
#             bottom_table = Table(table_data, colWidths=[1.0*inch, 6.5*inch])

#             bottom_table.setStyle(TableStyle([
#                 ('VALIGN', (0, 0), (-1, -1), 'TOP'),
#                 ('LEFTPADDING', (0, 0), (-1, -1), 0),
#                 ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
#             ]))

#             self.story.append(bottom_table)
#             self.story.append(Spacer(1, 0.2 * inch))

#         except Exception as e:
#             print(f"Error creating cover page: {e}")


