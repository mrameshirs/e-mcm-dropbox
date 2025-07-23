import datetime
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, PageBreak, Frame
# At the top of mcm_report_generator.py
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
    A robust PDF report generator with comprehensive SVG validation and error handling.
    """

    def __init__(self, selected_period, vital_stats, chart_images):
        self.buffer = BytesIO()
        self.doc = SimpleDocTemplate(
            self.buffer, 
            pagesize=letter, 
            leftMargin=0.5*inch, 
            rightMargin=0.5*inch,
            topMargin=0.5*inch,
            bottomMargin=0.5*inch
        )
        self.story = []
        self.styles = getSampleStyleSheet()
        self.width, self.height = letter

        self.selected_period = selected_period
        self.vital_stats = vital_stats
        self.chart_images = chart_images

        # Register fonts with proper error handling
        self._register_fonts()

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
            # Register Helvetica as fallback for Hindi
            pdfmetrics.registerFont(TTFont('HindiFont', 'Helvetica'))
        except Exception as e:
            print(f"Fallback font registration failed: {e}")

    def _validate_svg_content(self, svg_content):
        """
        Validate SVG content and fix common issues that cause transformation errors
        """
        try:
            # Convert bytes to string if necessary
            if isinstance(svg_content, bytes):
                svg_string = svg_content.decode('utf-8')
            else:
                svg_string = str(svg_content)

            # Check for minimum required content
            if len(svg_string.strip()) < 10:
                return None, "SVG content too short"

            # Parse as XML to validate structure
            try:
                root = ET.fromstring(svg_string)
            except ET.ParseError as e:
                return None, f"Invalid XML structure: {e}"

            # Check if it's actually an SVG
            if not (root.tag.endswith('svg') or 'svg' in root.tag.lower()):
                return None, "Not a valid SVG element"

            # Fix common transformation issues
            svg_string = self._fix_svg_transforms(svg_string)
            
            # Ensure SVG has proper dimensions
            svg_string = self._ensure_svg_dimensions(svg_string)

            return svg_string.encode('utf-8'), None

        except Exception as e:
            return None, f"SVG validation error: {e}"

    def _fix_svg_transforms(self, svg_string):
        """Fix problematic transformation matrices in SVG"""
        # Remove or fix scale(0) transforms which cause division by zero
        svg_string = re.sub(r'scale\(0(?:\.0*)?\)', 'scale(0.001)', svg_string)
        svg_string = re.sub(r'scale\(0(?:\.0*)?[,\s]+0(?:\.0*)?\)', 'scale(0.001,0.001)', svg_string)
        
        # Fix matrix transforms with zero determinants
        # Pattern: matrix(a,b,c,d,e,f) where a*d - b*c = 0
        def fix_matrix(match):
            values = [float(x.strip()) for x in match.group(1).split(',')]
            if len(values) == 6:
                a, b, c, d, e, f = values
                det = a * d - b * c
                if abs(det) < 1e-10:  # Near zero determinant
                    # Replace with identity matrix
                    return 'matrix(1,0,0,1,0,0)'
            return match.group(0)
        
        svg_string = re.sub(r'matrix\(([^)]+)\)', fix_matrix, svg_string)
        
        return svg_string

    def _ensure_svg_dimensions(self, svg_string):
        """Ensure SVG has proper width and height attributes"""
        # If no width/height specified, add default ones
        if 'width=' not in svg_string and 'height=' not in svg_string:
            svg_string = re.sub(
                r'<svg([^>]*?)>', 
                r'<svg\1 width="400" height="300">', 
                svg_string, 
                count=1
            )
        
        # Fix zero or negative dimensions
        svg_string = re.sub(r'width=["\']0["\']', 'width="400"', svg_string)
        svg_string = re.sub(r'height=["\']0["\']', 'height="300"', svg_string)
        
        return svg_string

    def _create_safe_svg_drawing(self, img_bytes):
        """
        Create an SVG drawing with comprehensive error handling and validation
        """
        try:
            # Reset position
            img_bytes.seek(0)
            original_content = img_bytes.read()
            
            if not original_content:
                return None, "Empty image data"

            # Validate and fix SVG content
            fixed_content, error = self._validate_svg_content(original_content)
            if error:
                return None, error

            # Create a new BytesIO object with fixed content
            fixed_buffer = BytesIO(fixed_content)
            
            # Attempt to parse with svglib
            try:
                drawing = svg2rlg(fixed_buffer)
            except Exception as svg_error:
                return None, f"SVG parsing failed: {svg_error}"

            if drawing is None:
                return None, "svg2rlg returned None"

            # Validate drawing attributes
            if not hasattr(drawing, 'width') or not hasattr(drawing, 'height'):
                return None, "Drawing missing width/height attributes"

            if drawing.width <= 0 or drawing.height <= 0:
                return None, f"Invalid dimensions: {drawing.width}x{drawing.height}"

            # Check for infinite or NaN values
            if not (0 < drawing.width < 10000 and 0 < drawing.height < 10000):
                return None, f"Unreasonable dimensions: {drawing.width}x{drawing.height}"

            return drawing, None

        except Exception as e:
            return None, f"Unexpected error creating SVG drawing: {e}"

    def run(self, detailed=False):
        """Generate the full report with comprehensive error handling"""
        try:
            # 1. Populate the story with all content
            self.create_cover_page_story()
            self.story.append(PageBreak())
            self.create_summary_pages(self.chart_images, detailed)
            
            # 2. Build the document
            self.doc.build(self.story, onFirstPage=self.add_page_elements, onLaterPages=self.add_page_elements)
            
            self.buffer.seek(0)
            return self.buffer
            
        except Exception as e:
            print(f"Error generating PDF: {e}")
            # Return a minimal working PDF in case of error
            return self._generate_error_pdf(str(e))

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
            # Return empty buffer as last resort
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
                canvas.rect(0, self.height * 0.25, self.width, self.height, stroke=0, fill=1)
                canvas.setFillColor(colors.HexColor("#C8B59E"))  # Gold
                canvas.rect(0, 0, self.width, self.height * 0.25, stroke=0, fill=1)
                canvas.setStrokeColor(colors.HexColor("#C8B59E"))
                canvas.setLineWidth(3)
                canvas.line(0, self.height * 0.25, self.width, self.height * 0.25)

                # Draw static lines for the cover page
                canvas.setStrokeColor(colors.HexColor("#f5ddc1"))
                canvas.setLineWidth(1)
                logo_y_pos = self.height - 1.6 * inch
                canvas.line(1.5*inch, logo_y_pos, 3.25*inch, logo_y_pos)  # Left line
                canvas.line(self.width - 3.25*inch, logo_y_pos, self.width - 1.5*inch, logo_y_pos)  # Right line
            else:
                # Background for all other pages
                canvas.setFillColor(colors.HexColor("#F5F5DC"))  # Light beige
                canvas.rect(0, 0, self.width, self.height, stroke=0, fill=1)
            
            canvas.restoreState()
        except Exception as e:
            print(f"Error drawing page elements: {e}")
            canvas.restoreState()

    # def create_cover_page_story(self):
    #     """Method to create the cover page CONTENT"""
    #     try:
    #         logo_style = ParagraphStyle(
    #             name='LogoStyle', 
    #             fontSize=16, 
    #             textColor=colors.HexColor("#f5ddc1"), 
    #             alignment=TA_CENTER
    #         )
    #         self.story.append(Spacer(1, 1.0 * inch))
    #         # a cbic logo picture should appear in place of "YOUR LOCO" self.story.append(Paragraph("YOUR LOGO", logo_style))
    #         self.story.append(Spacer(1, 1.2 * inch))

    #         title_style = ParagraphStyle(
    #             name='Title', 
    #             fontSize=42, 
    #             textColor=colors.HexColor("#f5ddc1"),
    #             alignment=TA_CENTER, 
    #             fontName='Helvetica-Bold', 
    #             leading=50
    #         )
    #         title2_style = ParagraphStyle(
    #             name='Title', 
    #             fontSize=36, 
    #             textColor=colors.HexColor("#f5ddc1"),
    #             alignment=TA_CENTER, 
    #             fontName='Helvetica-Bold', 
    #             leading=50
    #         )
    #         title3_style = ParagraphStyle(
    #             name='Title', 
    #             fontSize=32, 
    #             textColor=colors.HexColor("#f5ddc1"),
    #             alignment=TA_CENTER, 
    #             fontName='Helvetica-Oblique', 
    #             leading=50
    #         )
    #          title4_style = ParagraphStyle(
    #             name='Title', 
    #             fontSize=24, 
    #             textColor=colors.HexColor("#f5ddc1"),
    #             alignment=TA_CENTER, 
    #             fontName='Helvetica-Oblique', 
    #             leading=50
    #         )
    #          # Check if Hindi font is available
    #         try:
    #             # Test if HindiFont is registered
    #             pdfmetrics.getFont('HindiFont')
    #             hindi_font = 'HindiFont'
    #         except:
    #             hindi_font = 'Helvetica-Bold'
                
    #         hindi_style = ParagraphStyle(
    #             name='HindiTitle', 
    #             parent=title_style, 
    #             fontName=hindi_font, 
    #             fontSize=24
    #         )
                    
    #         self.story.append(Paragraph("MONITORING COMMITTEE MEETING", title_style))
    #         self.story.append(Paragraph("निगरानी समिति की बैठक", hindi_style))
    #         self.story.append(Paragraph("JULY 2025", title2_style))
    #         self.story.append(Spacer(1, 0.5 * inch))
    #         self.story.append(Paragraph("EXECUTIVE SUMMARY REPORT", title3_style))
    #         self.story.append(Paragraph("[Auto-generated by e-MCM App]", title4_style))
            
    #         self.story.append(Spacer(1, 1.5 * inch))

    #         contact_style = ParagraphStyle(
    #             name='Contact', 
    #             fontSize=12, 
    #             textColor=colors.HexColor("#193041"), 
    #             alignment=TA_CENTER
    #         )
    #          org_style = ParagraphStyle(
    #             name='Contact', 
    #             fontSize=24, 
    #             textColor=colors.HexColor("#193041"), 
    #             alignment=TA_LEFT
    #         )
    #         # A INDIAN EMBLEM LOGO needed on left , then the below text should appear on its right
    #         self.story.append(Paragraph("Office of Commissioner of CGST Audit-1 ", org_style))
    #         self.story.append(Paragraph("Mumbai CGST Zone ", org_style))
    #         self.story.append(Paragraph("[Ph: 022 22897504] | [Email: gst-audit@gov.in]", contact_style))
    #         self.story.append(Spacer(1, 0.2 * inch))
    #     except Exception as e:
    #         print(f"Error creating cover page: {e}")
    def create_cover_page_story(self):
        """Method to create the cover page CONTENT with logos"""
        try:
            # --- 1. CBIC Logo at the Top ---
            #self.story.append(Spacer(1, 1.0 * inch))
            try:
                # Attempt to add the CBIC logo image
                cbic_logo = Image('cbic_logo.png', width=1.5*inch, height=1.5*inch)
                cbic_logo.hAlign = 'CENTER'
                self.story.append(cbic_logo)
            except Exception as e:
                # Fallback to text if image is not found
                print(f"Warning: cbic_logo.png not found. Using text placeholder. Error: {e}")
                logo_style = ParagraphStyle(name='LogoStyle', fontSize=16, textColor=colors.HexColor("#f5ddc1"), alignment=TA_CENTER)
                self.story.append(Paragraph("CBIC LOGO", logo_style))
            
            self.story.append(Spacer(1, 0.8 * inch))

            # --- Title and Subtitles ---
            title_style = ParagraphStyle(name='Title', fontSize=38, textColor=colors.HexColor("#f5ddc1"),
                                       alignment=TA_CENTER, fontName='Helvetica-Bold', leading=46)
            title2_style = ParagraphStyle(name='Title2', parent=title_style, fontSize=34)
            title3_style = ParagraphStyle(name='Title3', parent=title_style, fontSize=26, textColor=colors.HexColor("#FCC200"),fontName='Helvetica')
            title4_style = ParagraphStyle(name='Title4', parent=title_style, fontSize=20,textColor=colors.HexColor("#FC200") ,fontName='Helvetica-Oblique')
            hindi_style = ParagraphStyle(name='HindiTitle', parent=title_style, fontName='HindiFont', fontSize=24)
            
            self.story.append(Paragraph("MONITORING COMMITTEE MEETING", title_style))
            self.story.append(Paragraph("निगरानी समिति की बैठक", hindi_style))
            self.story.append(Paragraph(f"{self.selected_period.upper()}", title2_style))
            self.story.append(Spacer(1, 0.5 * inch))
            self.story.append(Paragraph("EXECUTIVE SUMMARY REPORT", title3_style))
            self.story.append(Paragraph("[Auto-generated by e-MCM App]", title4_style))
            
            self.story.append(Spacer(1, 1.3 * inch))

            # --- 2. Emblem and Address at the Bottom using a Table ---
            contact_style = ParagraphStyle(name='Contact', fontSize=12, textColor=colors.HexColor("#193041"), alignment=TA_LEFT)
            org_style = ParagraphStyle(name='Org', fontSize=18, textColor=colors.HexColor("#193041"), alignment=TA_LEFT, fontName='Helvetica-Bold', leading=18)

            # Prepare the text for the right column
            right_col_text = [
                Paragraph("Office of the Commissioner of CGST & Central Excise", org_style),
                Paragraph("Audit-I Commissionerate, Mumbai", org_style),
                Spacer(1, 0.2 * inch),
                Paragraph("Ph: 022-22617504 | Email: adcaudit1mum@gov.in", contact_style)
            ]

            # Prepare the image for the left column
            try:
                emblem_logo = Image('emblem.png', width=0.8*inch, height=1.2*inch)
            except Exception as e:
                print(f"Warning: emblem.png not found. Using a text placeholder. Error: {e}")
                emblem_logo = Paragraph("EMBLEM", contact_style)

            # Create the table data structure
            table_data = [[emblem_logo, right_col_text]]

            # Create the Table object
            bottom_table = Table(table_data, colWidths=[1.0*inch, 6*inch])

            # Style the table to align content and remove borders
            bottom_table.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (-1, -1), 0),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
            ]))

            self.story.append(bottom_table)
            self.story.append(Spacer(1, 0.2 * inch))

        except Exception as e:
            print(f"Error creating cover page: {e}")
    def create_summary_pages(self, chart_images, detailed):
        """This method adds summary content to the story"""
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
                # Test if HindiFont is registered
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
            
            self.story.append(Paragraph("Monitoring Committee Meeting (MCM)", title_style))
            self.story.append(Paragraph("निगरानी समिति की बैठक", hindi_style))
            self.story.append(Spacer(1, 0.5 * inch))

            # Other text styles
            summary_style_caps = ParagraphStyle(
                name='SummaryCaps', 
                fontSize=16, 
                textColor=colors.HexColor("#1F3A4D"),
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
                fontSize=11, 
                textColor=colors.HexColor("#1F3A4D"),
                alignment=TA_CENTER, 
                fontName='Helvetica'
            )

            self.story.append(Paragraph("EXECUTIVE SUMMARY", summary_style_caps))
            self.story.append(Spacer(1, 0.1 * inch))
            self.story.append(Paragraph("(Auto generated through e-MCM App)", summary_italic_style))
            self.story.append(Spacer(1, 0.1 * inch))
            self.story.append(Paragraph("Audit 1 Commissionerate, Mumbai CGST Zone", summary_footer_style))
            self.story.append(Spacer(1, 0.5 * inch))

            # Add charts to the story
            if chart_images and len(chart_images) > 0:
                self.add_charts_from_images(chart_images)
            else:
                # Add placeholder if no charts
                placeholder_style = ParagraphStyle(
                    name='Placeholder', 
                    parent=self.styles['Normal'],
                    fontSize=12, 
                    alignment=TA_CENTER
                )
                self.story.append(Paragraph("No charts available for this report.", placeholder_style))
                
        except Exception as e:
            print(f"Error creating summary pages: {e}")

    def add_charts_from_images(self, chart_images):
        """Add charts from images with robust error handling and validation"""
        successful_charts = 0
        
        for i, img_bytes in enumerate(chart_images):
            try:
                if img_bytes is None:
                    self._add_chart_error(i, "No image data provided")
                    continue

                print(f"Processing chart {i+1}/{len(chart_images)}")
                
                # Create safe SVG drawing with comprehensive validation
                drawing, error = self._create_safe_svg_drawing(img_bytes)
                
                if error:
                    print(f"Chart {i+1} error: {error}")
                    self._add_chart_error(i, error)
                    continue

                if drawing is None:
                    self._add_chart_error(i, "Could not create drawing")
                    continue

                # Scale the drawing safely
                try:
                    render_width = 6 * inch
                    scale_factor = render_width / drawing.width
                    drawing.width = render_width
                    drawing.height = drawing.height * scale_factor
                    drawing.hAlign = 'CENTER'
                    
                    # Add to story
                    self.story.append(drawing)
                    self.story.append(Spacer(1, 0.25 * inch))
                    successful_charts += 1
                    
                    print(f"Successfully processed chart {i+1}")
                    
                    # Add page break after every 2 charts (but not after the last one)
                    if (i + 1) % 2 == 0 and i < len(chart_images) - 1:
                        self.story.append(PageBreak())
                        
                except Exception as scale_error:
                    print(f"Chart {i+1} scaling error: {scale_error}")
                    self._add_chart_error(i, f"Scaling failed: {scale_error}")
                    
            except Exception as e:
                print(f"Unexpected error processing chart {i+1}: {e}")
                self._add_chart_error(i, f"Unexpected error: {e}")

        print(f"Successfully processed {successful_charts}/{len(chart_images)} charts")

    def _add_chart_error(self, chart_index, error_message):
        """Add error message for failed chart"""
        try:
            error_style = ParagraphStyle(
                name='ChartError', 
                parent=self.styles['Normal'],
                fontSize=10, 
                textColor=colors.red,
                alignment=TA_CENTER
            )
            self.story.append(Paragraph(f"Chart {chart_index+1}: Unable to load image ({error_message})", error_style))
            self.story.append(Spacer(1, 0.25 * inch))
        except Exception as e:
            print(f"Error adding chart error message: {e}")
            
# import datetime
# from reportlab.lib import colors
# from reportlab.lib.enums import TA_CENTER, TA_LEFT
# from reportlab.lib.pagesizes import letter
# from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
# from reportlab.lib.units import inch
# from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
# from reportlab.pdfbase import pdfmetrics
# from reportlab.pdfbase.ttfonts import TTFont
# from io import BytesIO
# from svglib.svglib import svg2rlg

# class PDFReportGenerator:
#     """
#     Corrected class to generate a professional PDF report for the MCM.
#     This version populates the story fully before building the document.
#     """

#     def __init__(self, selected_period, vital_stats, chart_images):
#         self.buffer = BytesIO()
#         self.doc = SimpleDocTemplate(self.buffer, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch)
#         self.story = []
#         self.styles = getSampleStyleSheet()
#         self.width, self.height = letter

#         self.selected_period = selected_period
#         self.vital_stats = vital_stats
#         self.chart_images = chart_images

#         # --- Register Hindi Font ---
#         try:
#             pdfmetrics.registerFont(TTFont('HindiFont', 'NotoSansDevanagari-VariableFont_wdth,wght.ttf'))
#         except:
#             pdfmetrics.registerFont(TTFont('HindiFont', 'Helvetica-Bold'))

#     # --- NEW: Corrected run method ---
#     def run(self, detailed=False):
#         # 1. Populate the self.story list with ALL content first.
#         self.create_cover_page_story()
#         self.story.append(PageBreak())
#         self.create_summary_pages(self.chart_images, detailed)
        
#         # 2. Now, build the document with the populated story.
#         self.doc.build(self.story, onFirstPage=self.add_page_elements, onLaterPages=self.add_page_elements)
        
#         self.buffer.seek(0)
#         return self.buffer

#     # --- This is a unified drawer for static page elements (backgrounds/lines) ---
#     def add_page_elements(self, canvas, doc):
#         canvas.saveState()
#         if doc.page == 1:
#             # --- Cover Page Background and static lines ---
#             canvas.setFillColor(colors.HexColor("#193041")) # Dark Blue
#             canvas.rect(0, self.height * 0.25, self.width, self.height, stroke=0, fill=1)
#             canvas.setFillColor(colors.HexColor("#C8B59E")) # Gold
#             canvas.rect(0, 0, self.width, self.height * 0.25, stroke=0, fill=1)
#             canvas.setStrokeColor(colors.HexColor("#C8B59E"))
#             canvas.setLineWidth(3)
#             canvas.line(0, self.height * 0.25, self.width, self.height * 0.25)

#             canvas.setStrokeColor(colors.HexColor("#f5ddc1"))
#             canvas.setLineWidth(1)
#             logo_y_pos = self.height - 1.25 * inch 
#             canvas.line(1.5*inch, logo_y_pos, 3.25*inch, logo_y_pos)
#             canvas.line(self.width - 3.25*inch, logo_y_pos, self.width - 1.5*inch, logo_y_pos)
#         else:
#             # --- Background for all other pages ---
#             canvas.setFillColor(colors.HexColor("#F5F5DC"))
#             canvas.rect(0, 0, self.width, self.height, stroke=0, fill=1)
#         canvas.restoreState()

#     def create_cover_page_story(self):
#         # This method ADDS the cover page content to the main story.
#         self.story.append(Spacer(1, 0.75 * inch))
#         logo_style = ParagraphStyle(name='LogoStyle', fontSize=16, textColor=colors.HexColor("#f5ddc1"), alignment=TA_CENTER)
#         self.story.append(Paragraph("YOUR LOGO", logo_style))
        
#         self.story.append(Spacer(1, 1.8 * inch))
#         title_style = ParagraphStyle(name='Title', fontSize=42, textColor=colors.HexColor("#f5ddc1"),
#                                    alignment=TA_CENTER, fontName='Helvetica-Bold', leading=50)
#         self.story.append(Paragraph("REPORT EXECUTIVE", title_style))
#         self.story.append(Paragraph("COVER PAGE", title_style))
        
#         self.story.append(Spacer(1, 3.0 * inch))
#         contact_style = ParagraphStyle(name='Contact', fontSize=9, textColor=colors.HexColor("#193041"), alignment=TA_CENTER)
#         self.story.append(Paragraph("[Your Company Email] | [Your Company Number] | [Your Company Website]", contact_style))

#     def create_summary_pages(self, chart_images, detailed):
#         # This method ADDS the summary content to the main story.
#         title_style = ParagraphStyle(name='MainTitle', fontSize=28, textColor=colors.HexColor("#1F3A4D"),
#                                    alignment=TA_CENTER, fontName='Helvetica-Bold', spaceAfter=12)
#         hindi_style = ParagraphStyle(name='HindiTitle', parent=title_style, fontName='HindiFont', fontSize=24)
        
#         self.story.append(Paragraph("Monitoring Committee Meeting (MCM)", title_style))
#         self.story.append(Paragraph("निगरानी समिति की बैठक", hindi_style))
#         self.story.append(Spacer(1, 0.3 * inch))

#         self.add_charts_from_images(chart_images) # Assuming you want charts here

#     def add_charts_from_images(self, chart_images):
#         for i, img_bytes in enumerate(chart_images):
#             try:
#                 img_bytes.seek(0)
#                 drawing = svg2rlg(img_bytes)
#                 render_width = 6 * inch
#                 scale_factor = render_width / drawing.width
#                 drawing.width = render_width
#                 drawing.height = drawing.height * scale_factor
#                 drawing.hAlign = 'CENTER'
#                 self.story.append(drawing)
#                 self.story.append(Spacer(1, 0.25 * inch))
#                 if (i + 1) % 2 == 0 and i < len(chart_images) - 1:
#                     self.story.append(PageBreak())
#             except Exception as e:
#                 error_style = ParagraphStyle(name='Error', fontSize=10, textColor=colors.red, alignment=TA_CENTER)
#                 self.story.append(Paragraph(f"Chart {i+1}: Unable to load image ({str(e)})", error_style))
#                 self.story.append(Spacer(1, 0.25 * inch))
