import datetime
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, PageBreak, Frame
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from io import BytesIO
from svglib.svglib import svg2rlg

class PDFReportGenerator:
    """
    A class to generate a professional PDF report for the Monitoring Committee Meeting (MCM),
    accepting dynamic data for stats and charts.
    """

    def __init__(self, selected_period, vital_stats, chart_images):
        self.buffer = BytesIO()
        # --- CHANGED: Use a simpler DocTemplate setup ---
        self.doc = SimpleDocTemplate(self.buffer, pagesize=letter, leftMargin=0.5*inch, rightMargin=0.5*inch)
        self.story = []
        self.styles = getSampleStyleSheet()
        self.width, self.height = letter

        self.selected_period = selected_period
        self.vital_stats = vital_stats
        self.chart_images = chart_images

        # --- Register Hindi Font ---
        try:
            pdfmetrics.registerFont(TTFont('HindiFont', 'NotoSansDevanagari-VariableFont_wdth,wght.ttf'))
        except:
            pdfmetrics.registerFont(TTFont('HindiFont', 'Helvetica-Bold'))


    # --- NEW: Restructured run method ---
    def run(self, detailed=False):
        """
        Generates the full report by populating the story first, then building.
        """
        # 1. Populate the story with all content
        self.create_cover_page_story()
        self.story.append(PageBreak())
        self.create_summary_pages(self.chart_images, detailed)
        
        # 2. Build the document with a unified page drawer
        self.doc.build(self.story, onFirstPage=self.add_page_elements, onLaterPages=self.add_page_elements)
        
        self.buffer.seek(0)
        return self.buffer

    # --- NEW: Unified method to draw static elements on ALL pages ---
    def add_page_elements(self, canvas, doc):
        canvas.saveState()
        if doc.page == 1:
            # --- Cover Page Background ---
            canvas.setFillColor(colors.HexColor("#193041")) # Dark Blue
            canvas.rect(0, self.height * 0.25, self.width, self.height, stroke=0, fill=1)
            canvas.setFillColor(colors.HexColor("#C8B59E")) # Gold
            canvas.rect(0, 0, self.width, self.height * 0.25, stroke=0, fill=1)
            canvas.setStrokeColor(colors.HexColor("#C8B59E"))
            canvas.setLineWidth(3)
            canvas.line(0, self.height * 0.25, self.width, self.height * 0.25)

            # --- Draw static lines for the cover page ---
            canvas.setStrokeColor(colors.HexColor("#f5ddc1"))
            canvas.setLineWidth(1)
            logo_y_pos = self.height - 1.6 * inch
            canvas.line(1.5*inch, logo_y_pos, 3.25*inch, logo_y_pos) # Left line
            canvas.line(self.width - 3.25*inch, logo_y_pos, self.width - 1.5*inch, logo_y_pos) # Right line
        else:
            # --- Background for all other pages ---
            canvas.setFillColor(colors.HexColor("#F5F5DC")) # Light beige
            canvas.rect(0, 0, self.width, self.height, stroke=0, fill=1)
        
        canvas.restoreState()

    # --- NEW: Method to create the cover page CONTENT ---
    def create_cover_page_story(self):
        # This method adds flowables to self.story
        logo_style = ParagraphStyle(name='LogoStyle', fontSize=16, textColor=colors.HexColor("#f5ddc1"), alignment=TA_CENTER)
        self.story.append(Spacer(1, 1.0 * inch))
        self.story.append(Paragraph("YOUR LOGO", logo_style))
        self.story.append(Spacer(1, 1.2 * inch))

        title_style = ParagraphStyle(name='Title', fontSize=42, textColor=colors.HexColor("#f5ddc1"),
                                   alignment=TA_CENTER, fontName='Helvetica-Bold', leading=50)
        self.story.append(Paragraph("REPORT EXECUTIVE", title_style))
        self.story.append(Paragraph("COVER PAGE", title_style))
        self.story.append(Spacer(1, 2.5 * inch))

        contact_style = ParagraphStyle(name='Contact', fontSize=9, textColor=colors.HexColor("#193041"), alignment=TA_CENTER)
        self.story.append(Paragraph("[Your Company Email] | [Your Company Number] | [Your Company Website]", contact_style))
        self.story.append(Spacer(1, 0.2 * inch)) # Adjust space as needed

    # --- CHANGED: This method now just adds summary content to the story ---
    def create_summary_pages(self, chart_images, detailed):
        title_style = ParagraphStyle(name='MainTitle', fontSize=28, textColor=colors.HexColor("#1F3A4D"),
                                   alignment=TA_CENTER, fontName='Helvetica-Bold')
        hindi_style = ParagraphStyle(name='HindiTitle', parent=title_style, fontName='HindiFont', fontSize=24)
        
        self.story.append(Paragraph("Monitoring Committee Meeting (MCM)", title_style))
        self.story.append(Paragraph("निगरानी समिति की बैठक", hindi_style))
        self.story.append(Spacer(1, 0.5 * inch))

        # Other text styles
        summary_style_caps = ParagraphStyle(name='SummaryCaps', fontSize=16, textColor=colors.HexColor("#1F3A4D"),
                                           alignment=TA_CENTER, fontName='Helvetica-Bold')
        summary_italic_style = ParagraphStyle(name='SummaryItalic', fontSize=9, textColor=colors.HexColor("#1F3A4D"),
                                            alignment=TA_CENTER, fontName='Helvetica-Oblique')
        summary_footer_style = ParagraphStyle(name='SummaryFooter', fontSize=11, textColor=colors.HexColor("#1F3A4D"),
                                            alignment=TA_CENTER, fontName='Helvetica')

        self.story.append(Paragraph("EXECUTIVE SUMMARY", summary_style_caps))
        self.story.append(Spacer(1, 0.1 * inch))
        self.story.append(Paragraph("(Auto generated through e-MCM App)", summary_italic_style))
        self.story.append(Spacer(1, 0.1 * inch))
        self.story.append(Paragraph("Audit 1 Commissionerate, Mumbai CGST Zone", summary_footer_style))
        self.story.append(Spacer(1, 0.5 * inch))

        # Add charts to the story
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
                self.story.append(Spacer(1, 0.25 * inch))
