import datetime
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, PageBreak
from io import BytesIO
from svglib.svglib import svg2rlg
class PDFReportGenerator:
    """
    A class to generate a professional PDF report for the Monitoring Committee Meeting (MCM),
    accepting dynamic data for stats and charts.
    """

    def __init__(self, selected_period, vital_stats, chart_images):
        """
        Initializes the PDF report generator with dynamic data.
        :param selected_period: The string for the MCM period (e.g., "July 2025").
        :param vital_stats: A dictionary with keys like 'num_dars', 'total_detected', 'total_recovered'.
        :param chart_images: A list of image byte streams (e.g., from BytesIO).
        """
        self.buffer = BytesIO()
        self.doc = SimpleDocTemplate(self.buffer, pagesize=letter)
        self.story = []
        self.styles = getSampleStyleSheet()
        self.width, self.height = letter
        
        # Store dynamic data
        self.selected_period = selected_period
        self.vital_stats = vital_stats
        self.chart_images = chart_images
        # --- NEW: Register Hindi Font ---
        # Action: Download "NotoSansDevanagari-Regular.ttf" and place it in your project folder.
        try:
            pdfmetrics.registerFont(TTFont('HindiFont', 'NotoSansDevanagari-VariableFont_wdth,wght.ttf'))
        except:
            # Fallback if font is not found
            pdfmetrics.registerFont(TTFont('HindiFont', 'Helvetica-Bold'))
                                    
    def run(self, detailed=False):
        charts_to_include = self.chart_images if detailed else self.chart_images[:3]
        
        # --- NEW: Build the document with a custom page drawer ---
        self.doc.build(self.story, onFirstPage=self.draw_cover_page, onLaterPages=self.draw_later_pages)
        
        self.buffer.seek(0)
        return self.buffer

    # --- NEW: Custom method to draw the entire cover page canvas ---
    def draw_cover_page(self, canvas, doc):
        canvas.saveState()
        
        # --- OPTIONAL: For gradients, use a pre-made background image ---
        # To get perfect gradients, create a full-page (8.5x11 inch) image and use this:
        # canvas.drawImage('cover_background.png', 0, 0, width=self.width, height=self.height)

        # --- Fallback: Recreate using solid colors as requested ---
        # Dark Blue Top
        canvas.setFillColor(colors.HexColor("#193041"))
        canvas.rect(0, self.height * 0.25, self.width, self.height * 0.75, stroke=0, fill=1)
        # Gold Bottom
        canvas.setFillColor(colors.HexColor("#C8B59E"))
        canvas.rect(0, 0, self.width, self.height * 0.25, stroke=0, fill=1)
        # Gold border line
        canvas.setStrokeColor(colors.HexColor("#C8B59E"))
        canvas.setLineWidth(3)
        canvas.line(0, self.height * 0.25, self.width, self.height * 0.25)

        # --- Create story for cover page text ---
        cover_story = []
        
        # --- CHANGED: Logo styling ---
        logo_style = ParagraphStyle(name='LogoStyle', parent=self.styles['Normal'], fontSize=16,
                                  textColor=colors.HexColor("#f5ddc1"), alignment=TA_CENTER)
        cover_story.append(Paragraph("YOUR LOGO", logo_style))
        cover_story.append(Spacer(1, 1.2 * inch))

        # --- CHANGED: Title styling for boldness and layout ---
        title_style = ParagraphStyle(name='Title', parent=self.styles['h1'], fontSize=42,
                                   textColor=colors.HexColor("#f5ddc1"), alignment=TA_CENTER,
                                   fontName='Helvetica-Bold', leading=50)
        cover_story.append(Paragraph("REPORT EXECUTIVE", title_style))
        cover_story.append(Paragraph("COVER PAGE", title_style))
        cover_story.append(Spacer(1, 2.5 * inch))

        # --- CHANGED: Custom styles for bottom text ---
        contact_style = ParagraphStyle(name='Contact', parent=self.styles['Normal'], fontSize=9,
                                     textColor=colors.HexColor("#193041"), alignment=TA_CENTER)
        cover_story.append(Paragraph(
            "[Your Company Email] | [Your Company Number] | [Your Company Website]",
            contact_style
        ))
        
        # Draw the story on the canvas
        frame = doc.getFrame('normal')
        frame.addFromList(cover_story, canvas)

        # --- NEW: Draw elements not part of the platypus story (lines) ---
        # Draw lines next to the logo
        canvas.setStrokeColor(colors.HexColor("#f5ddc1"))
        canvas.setLineWidth(1)
        logo_y_pos = self.height - 1.6*inch # Approximate Y position of the logo text
        canvas.line(1.5*inch, logo_y_pos, 3.25*inch, logo_y_pos) # Left line
        canvas.line(self.width - 3.25*inch, logo_y_pos, self.width - 1.5*inch, logo_y_pos) # Right line
        
        canvas.restoreState()


    # --- NEW: Method for background on subsequent pages ---
    def draw_later_pages(self, canvas, doc):
        canvas.saveState()
        canvas.setFillColor(colors.HexColor("#F5F5DC")) # Light beige
        canvas.rect(0, 0, self.width, self.height, stroke=0, fill=1)
        canvas.restoreState()
        
        # --- NEW: Re-add the content for later pages here ---
        # This is necessary because we are now using a custom page drawer
        if doc.page == 2:
            self.create_summary_pages(self.chart_images, len(self.chart_images) > 3)


    def create_summary_pages(self, chart_images, detailed):
        # This function is now called by the page drawer
        # --- CHANGED: Title styling ---
        title_style = ParagraphStyle(name='Title', parent=self.styles['h1'], fontSize=28,
                                   textColor=colors.HexColor("#1F3A4D"), alignment=TA_CENTER,
                                   fontName='Helvetica-Bold')
        hindi_style = ParagraphStyle(name='HindiTitle', parent=title_style, fontName='HindiFont', fontSize=24)
        
        self.story.append(Paragraph("Monitoring Committee Meeting (MCM)", title_style))
        self.story.append(Paragraph("निगरानी समिति की बैठक", hindi_style)) # This will now render correctly
        self.story.append(Spacer(1, 0.5 * inch))

        # --- CHANGED: Executive Summary and other text styling ---
        summary_style_caps = ParagraphStyle(name='SummaryCaps', parent=self.styles['h2'], fontSize=16,
                                           textColor=colors.HexColor("#1F3A4D"), alignment=TA_CENTER,
                                           fontName='Helvetica-Bold')
        summary_italic_style = ParagraphStyle(name='SummaryItalic', parent=self.styles['Normal'], fontSize=9,
                                            textColor=colors.HexColor("#1F3A4D"), alignment=TA_CENTER,
                                            fontName='Helvetica-Oblique')
        summary_footer_style = ParagraphStyle(name='SummaryFooter', parent=self.styles['Normal'], fontSize=11,
                                            textColor=colors.HexColor("#1F3A4D"), alignment=TA_CENTER,
                                            fontName='Helvetica')

        self.story.append(Paragraph("EXECUTIVE SUMMARY", summary_style_caps))
        self.story.append(Spacer(1, 0.1 * inch))
        self.story.append(Paragraph("(Auto generated through e-MCM App)", summary_italic_style))
        self.story.append(Spacer(1, 0.1 * inch))
        self.story.append(Paragraph("Audit 1 Commissionerate, Mumbai CGST Zone", summary_footer_style))
        self.story.append(Spacer(1, 0.5 * inch))

        # --- Vital Stats Section ---
        self.add_charts_from_images(chart_images)


    def add_charts_from_images(self, chart_images):
        for i, img_bytes in enumerate(chart_images):
            try:
                img_bytes.seek(0)
                drawing = svg2rlg(img_bytes)
                render_width = 6 * inch
                scale_factor = render_width / drawing.width
                drawing.width = render_width
                drawing.height = drawing.height * scale_factor
                drawing.hAlign = 'CENTER'
                self.story.append(drawing)
                self.story.append(Spacer(1, 0.25 * inch))
                if (i + 1) % 2 == 0 and i < len(chart_images) - 1:
                    self.story.append(PageBreak())
            except Exception as e:
                error_style = ParagraphStyle(name='Error', parent=self.styles['Normal'],
                                           fontSize=10, textColor=colors.red,
                                           alignment=TA_CENTER)
                self.story.append(Paragraph(f"Chart {i+1}: Unable to load image ({str(e)})", error_style))
                self.story.append(Spacer(1, 0.25 * inch))# import datetime
# from reportlab.lib import colors
# from reportlab.lib.enums import TA_CENTER, TA_LEFT
# from reportlab.lib.pagesizes import letter
# from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
# from reportlab.lib.units import inch
# from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, PageBreak
# from io import BytesIO

# class PDFReportGenerator:
#     """
#     A class to generate a professional PDF report for the Monitoring Committee Meeting (MCM),
#     accepting dynamic data for stats and charts.
#     """

#     def __init__(self, selected_period, vital_stats, chart_images):
#         """
#         Initializes the PDF report generator with dynamic data.
#         :param selected_period: The string for the MCM period (e.g., "July 2025").
#         :param vital_stats: A dictionary with keys like 'num_dars', 'total_detected', 'total_recovered'.
#         :param chart_images: A list of image byte streams (e.g., from BytesIO).
#         """
#         self.buffer = BytesIO()
#         self.doc = SimpleDocTemplate(self.buffer, pagesize=letter)
#         self.story = []
#         self.styles = getSampleStyleSheet()
#         self.width, self.height = letter
        
#         # Store dynamic data
#         self.selected_period = selected_period
#         self.vital_stats = vital_stats
#         self.chart_images = chart_images

#     def run(self, detailed=False):
#         """
#         Generates the full report, either short or detailed.
#         Returns the generated PDF as a byte stream.
#         """
#         self.create_cover_page()
#         self.story.append(PageBreak())
        
#         # Determine which charts to include
#         charts_to_include = self.chart_images if detailed else self.chart_images[:3] # Short report gets first 3 charts
        
#         self.create_summary_pages(charts_to_include, detailed)
        
#         self.doc.build(self.story, onFirstPage=self.add_background, onLaterPages=self.add_background)
#         self.buffer.seek(0)
#         return self.buffer

#     def add_background(self, canvas, doc):
#         """
#         Adds the background color to each page.
#         """
#         canvas.saveState()
#         if doc.page == 1:
#             # Dark blue-green for the top part of the cover
#             canvas.setFillColor(colors.HexColor("#1F3A4D"))
#             canvas.rect(0, self.height * 0.25, self.width, self.height * 0.75, stroke=0, fill=1)
#             # Gold/tan for the bottom part of the cover
#             canvas.setFillColor(colors.HexColor("#C8B59E"))
#             canvas.rect(0, 0, self.width, self.height * 0.25, stroke=0, fill=1)
#         else:
#             # Light beige for other pages
#             canvas.setFillColor(colors.HexColor("#F5F5DC"))
#             canvas.rect(0, 0, self.width, self.height, stroke=0, fill=1)
#         canvas.restoreState()

#     def create_cover_page(self):
#         """
#         Creates the stunning cover page for the report using provided data.
#         """
#         logo = Image('https://placehold.co/100x100/FFFFFF/1F3A4D?text=LOGO', width=1.25*inch, height=1.25*inch)
#         logo.hAlign = 'CENTER'
#         self.story.append(logo)
#         self.story.append(Spacer(1, 1.5 * inch))

#         # Title
#         title_style = ParagraphStyle(name='Title', parent=self.styles['h1'], fontSize=36, textColor=colors.HexColor("#F5F5DC"), alignment=TA_CENTER)
#         self.story.append(Paragraph("Monitoring Committee Meeting (MCM)", title_style))
#         self.story.append(Paragraph("निगरानी समिति की बैठक", title_style))
#         self.story.append(Spacer(1, 0.3 * inch))

#         # Subheadings
#         subtitle_style = ParagraphStyle(name='Subtitle', parent=self.styles['h2'], fontSize=18, textColor=colors.HexColor("#F5F5DC"), alignment=TA_CENTER, spaceAfter=6)
#         self.story.append(Paragraph(f"Month: {self.selected_period}", subtitle_style))
#         self.story.append(Paragraph("Audit 1 Commissionerate", subtitle_style))
#         self.story.append(Paragraph("Executive Summary (Auto generated through e-MCM App)", subtitle_style))
#         self.story.append(Paragraph("Audit 1 Commissionerate, Mumbai CGST Zone", subtitle_style))
        
#         # Spacer to push stats to the bottom gold section
#         self.story.append(Spacer(1, 1.75 * inch))

#         # Vital Statistics from the Visualizations tab
#         stats_style = ParagraphStyle(name='Stats', parent=self.styles['Normal'], fontSize=11, textColor=colors.HexColor("#1F3A4D"), alignment=TA_CENTER, leading=14)
#         stats_header_style = ParagraphStyle(name='StatsHeader', parent=stats_style, fontName='Helvetica-Bold', fontSize=14, spaceAfter=8)

#         self.story.append(Paragraph("<b>Vital Statistics from Monthly Performance</b>", stats_header_style))
        
#         # Use the passed-in stats
#         dars = self.vital_stats.get('num_dars', 'N/A')
#         detected = self.vital_stats.get('total_detected', 0)
#         recovered = self.vital_stats.get('total_recovered', 0)
        
#         self.story.append(Paragraph(f"Total DARs Submitted: <b>{dars}</b>", stats_style))
#         self.story.append(Paragraph(f"Total Revenue Involved: <b>₹{detected:.2f} Lakhs</b>", stats_style))
#         self.story.append(Paragraph(f"Total Revenue Recovered: <b>₹{recovered:.2f} Lakhs</b>", stats_style))

#     def create_summary_pages(self, chart_images, detailed):
#         """
#         Creates the summary pages with charts and text.
#         """
#         heading_style = ParagraphStyle(name='Heading', parent=self.styles['h2'], fontSize=22, textColor=colors.HexColor("#1F3A4D"), alignment=TA_LEFT, spaceAfter=12)
#         body_style = ParagraphStyle(name='Body', parent=self.styles['Normal'], fontSize=12, textColor=colors.HexColor("#333333"), alignment=TA_LEFT, spaceAfter=12, leading=14)

#         report_type = "Detailed" if detailed else "Short"
#         self.story.append(Paragraph(f"Executive Summary of Key Findings ({report_type})", heading_style))
#         self.story.append(Paragraph(
#             "This section provides a summary of the key findings from the audits conducted this month. "
#             "The following charts, sourced from the PCO Dashboard, visualize performance across different metrics.",
#             body_style
#         ))
#         self.story.append(Spacer(1, 0.25 * inch))

#         # Add charts from the provided images
#         self.add_charts_from_images(chart_images)

#     def add_charts_from_images(self, chart_images):
#         """
#         Adds charts to the story from a list of image byte streams.
#         """
#         for img_bytes in chart_images:
#             img = Image(img_bytes, width=6*inch, height=3*inch) # Adjust size as needed
#             img.hAlign = 'CENTER'
#             self.story.append(img)
#             self.story.append(Spacer(1, 0.25 * inch))
