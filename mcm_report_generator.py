import datetime
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from io import BytesIO
from svglib.svglib import svg2rlg

class PDFReportGenerator:
    """
    Corrected class to generate a professional PDF report for the MCM.
    This version populates the story fully before building the document.
    """

    def __init__(self, selected_period, vital_stats, chart_images):
        self.buffer = BytesIO()
        self.doc = SimpleDocTemplate(self.buffer, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch)
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

    # --- NEW: Corrected run method ---
    def run(self, detailed=False):
        # 1. Populate the self.story list with ALL content first.
        self.create_cover_page_story()
        self.story.append(PageBreak())
        self.create_summary_pages(self.chart_images, detailed)
        
        # 2. Now, build the document with the populated story.
        self.doc.build(self.story, onFirstPage=self.add_page_elements, onLaterPages=self.add_page_elements)
        
        self.buffer.seek(0)
        return self.buffer

    # --- This is a unified drawer for static page elements (backgrounds/lines) ---
    def add_page_elements(self, canvas, doc):
        canvas.saveState()
        if doc.page == 1:
            # --- Cover Page Background and static lines ---
            canvas.setFillColor(colors.HexColor("#193041")) # Dark Blue
            canvas.rect(0, self.height * 0.25, self.width, self.height, stroke=0, fill=1)
            canvas.setFillColor(colors.HexColor("#C8B59E")) # Gold
            canvas.rect(0, 0, self.width, self.height * 0.25, stroke=0, fill=1)
            canvas.setStrokeColor(colors.HexColor("#C8B59E"))
            canvas.setLineWidth(3)
            canvas.line(0, self.height * 0.25, self.width, self.height * 0.25)

            canvas.setStrokeColor(colors.HexColor("#f5ddc1"))
            canvas.setLineWidth(1)
            logo_y_pos = self.height - 1.25 * inch 
            canvas.line(1.5*inch, logo_y_pos, 3.25*inch, logo_y_pos)
            canvas.line(self.width - 3.25*inch, logo_y_pos, self.width - 1.5*inch, logo_y_pos)
        else:
            # --- Background for all other pages ---
            canvas.setFillColor(colors.HexColor("#F5F5DC"))
            canvas.rect(0, 0, self.width, self.height, stroke=0, fill=1)
        canvas.restoreState()

    def create_cover_page_story(self):
        # This method ADDS the cover page content to the main story.
        self.story.append(Spacer(1, 0.75 * inch))
        logo_style = ParagraphStyle(name='LogoStyle', fontSize=16, textColor=colors.HexColor("#f5ddc1"), alignment=TA_CENTER)
        self.story.append(Paragraph("YOUR LOGO", logo_style))
        
        self.story.append(Spacer(1, 1.8 * inch))
        title_style = ParagraphStyle(name='Title', fontSize=42, textColor=colors.HexColor("#f5ddc1"),
                                   alignment=TA_CENTER, fontName='Helvetica-Bold', leading=50)
        self.story.append(Paragraph("REPORT EXECUTIVE", title_style))
        self.story.append(Paragraph("COVER PAGE", title_style))
        
        self.story.append(Spacer(1, 3.0 * inch))
        contact_style = ParagraphStyle(name='Contact', fontSize=9, textColor=colors.HexColor("#193041"), alignment=TA_CENTER)
        self.story.append(Paragraph("[Your Company Email] | [Your Company Number] | [Your Company Website]", contact_style))

    def create_summary_pages(self, chart_images, detailed):
        # This method ADDS the summary content to the main story.
        title_style = ParagraphStyle(name='MainTitle', fontSize=28, textColor=colors.HexColor("#1F3A4D"),
                                   alignment=TA_CENTER, fontName='Helvetica-Bold', spaceAfter=12)
        hindi_style = ParagraphStyle(name='HindiTitle', parent=title_style, fontName='HindiFont', fontSize=24)
        
        self.story.append(Paragraph("Monitoring Committee Meeting (MCM)", title_style))
        self.story.append(Paragraph("निगरानी समिति की बैठक", hindi_style))
        self.story.append(Spacer(1, 0.3 * inch))

        self.add_charts_from_images(chart_images) # Assuming you want charts here

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
                error_style = ParagraphStyle(name='Error', fontSize=10, textColor=colors.red, alignment=TA_CENTER)
                self.story.append(Paragraph(f"Chart {i+1}: Unable to load image ({str(e)})", error_style))
                self.story.append(Spacer(1, 0.25 * inch))
