# Reportlab imports
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, KeepInFrame, Image, Flowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm,inch
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics


import os
from django.http import HttpResponse
from ..models import ScheduleEntry, ShiftType, Employee, WorkDay, FixedHourFund, Holiday, ExcessHours
from io import BytesIO
import calendar
from calendar import monthrange
from django.contrib.auth.decorators import login_required
from datetime import date, timedelta
import datetime

from django.contrib.staticfiles import finders
from django.conf import settings


# Locate the font file
font_path = finders.find('fonts/DejaVu_light.ttf')
font_path_bold = finders.find('fonts/DejaVu_bold.ttf')

# Check if the font file exists and register the font
if font_path and os.path.exists(font_path):
    pdfmetrics.registerFont(TTFont('DejaVuSans', font_path))
    print("Font registered successfully.")
else:
    raise IOError(f"Font file not found at: {font_path}")

if font_path_bold and os.path.exists(font_path_bold):
    pdfmetrics.registerFont(TTFont('DejaVuSans-Bold', font_path_bold))
else:
    raise IOError(f"Bold font file not found at: {font_path_bold}")


# Croatian day names to use for mapping
day_names_cro = {
    'Monday': 'Pon', 
    'Tuesday': 'Uto', 
    'Wednesday': 'Sri', 
    'Thursday': 'Čet', 
    'Friday': 'Pet', 
    'Saturday': 'Sub', 
    'Sunday': 'Ned'
}
# Croatian month names to use for the header
croatian_months = {
    1: 'Siječanj', 2: 'Veljača', 3: 'Ožujak', 4: 'Travanj', 5: 'Svibanj', 6: 'Lipanj',
    7: 'Srpanj', 8: 'Kolovoz', 9: 'Rujan', 10: 'Listopad', 11: 'Studeni', 12: 'Prosinac'
}


def croatian_day(date_obj):
    """Return the Croatian day abbreviation for the date."""
    return day_names_cro[calendar.day_name[date_obj.weekday()]]

def get_week_dates(start_date):
    # start_date is assumed to be a Monday
    return [start_date + timedelta(days=i) for i in range(7)]

def generate_schedule_pdf(file_path, week_dates, shift_types, schedule_data, author_name):
    document = SimpleDocTemplate(file_path, pagesize=landscape(A4), rightMargin=5 * mm, leftMargin=5 * mm, topMargin=5 * mm, bottomMargin=5 * mm)
    elements = []
    styles = getSampleStyleSheet()

    # Define styles for title, author, and table
    title_author_style = ParagraphStyle(
        name='TitleAuthorStyle',
        fontName='Helvetica-Bold',
        fontSize=14,
        alignment=1,
        spaceAfter=10,
    )
    date_style = ParagraphStyle(
        name='DateStyle',
        fontName='Helvetica',
        fontSize=14,
        leading=14,
        alignment=1,
    )
    cell_style = ParagraphStyle(
        name='CellStyle',
        fontName='Helvetica',
        fontSize=7,
        leading=12,
        alignment=1,
    )
    group_styles = {
        '1': ParagraphStyle('Group1', textColor=colors.green, fontName='Helvetica', fontSize=7),
        '2': ParagraphStyle('Group2', textColor=colors.orange, fontName='Helvetica', fontSize=7),
        '3': ParagraphStyle('Group3', textColor=colors.blue, fontName='Helvetica', fontSize=7),
        # Add more group styles as needed
    }

    def get_header_style(text):
        font_size = 7
        if len(text) > 20:
            font_size -= 2
        return ParagraphStyle(
            name='HeaderStyle',
            fontName='Helvetica-Bold',
            fontSize=font_size,
            textColor=colors.whitesmoke,
            backColor=colors.grey,
            alignment=1,
            spaceAfter=6,
            wordWrap='CJK'
        )

    title_author = Paragraph(
        f"<para align='center'><b>RASPORED SMJENA-TJEDNI 2024    </b>    Izradio: {author_name}</para>",
        title_author_style
    )
    elements.append(title_author)

    headers = ['Dan Datum'] + [Paragraph(shift_type.name, get_header_style(shift_type.name)) for shift_type in shift_types]
    table_data = [headers]

    for date in week_dates:
        row = [Paragraph(f"{croatian_day(date)} {date.strftime('%d.%m.%Y')}", date_style)]
        for shift_type in shift_types:
            schedule_entry = schedule_data.get(date.strftime('%Y-%m-%d'), {}).get(shift_type.id)
            employees = schedule_entry.employees.all() if schedule_entry else []
            employees_paragraphs = [
                Paragraph(f"{emp.name} {emp.surname} ({emp.group})", group_styles.get(emp.group, cell_style))
                for emp in employees
            ]
            cell_content = "<br/>".join([p.text for p in employees_paragraphs])
            row.append(Paragraph(cell_content, cell_style))
        table_data.append(row)

    table = Table(table_data, repeatRows=1)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),  # Ensure all cells use Helvetica
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('TOPPADDING', (0, 0), (-1, 0), 8),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))

    for row_idx, date in enumerate(week_dates, start=1):
        if date.weekday() == 5:  # Saturday
            bg_color = colors.lightgreen
        elif date.weekday() == 6:  # Sunday
            bg_color = colors.lightyellow
        else:
            continue
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, row_idx), (-1, row_idx), bg_color),
        ]))

    elements.append(table)
    document.build(elements)

@login_required
def download_schedule_pdf(request):
    start_date_str = request.GET.get('week_start')
    if start_date_str:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
    else:
        today = date.today()
        start_date = today - timedelta(days=today.weekday())

    week_dates = get_week_dates(start_date)
    shift_types = ShiftType.objects.all()

    schedule_data = {}
    for day in week_dates:
        schedule_data[day.strftime('%Y-%m-%d')] = {}
        for shift_type in shift_types:
            schedule_entry = ScheduleEntry.objects.filter(date=day, shift_type=shift_type).first()
            schedule_data[day.strftime('%Y-%m-%d')][shift_type.id] = schedule_entry

    author_name = request.user.username

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="schedule.pdf"'
    generate_schedule_pdf(response, week_dates, shift_types, schedule_data, author_name)
    return response


#Pomocna funkcija za rotiranje teksta u pdfu
class verticalText(Flowable):
    '''Rotates a text in a table cell.'''
    def __init__(self, text):
        Flowable.__init__(self)
        self.text = text

    def draw(self):
        canvas = self.canv
        canvas.rotate(90)
        fs = canvas._fontsize
        canvas.translate(1, -fs / 1.2)
        canvas.drawString(0, 0, self.text)

    def wrap(self, aW, aH):
        canv = self.canv
        fn, fs = canv._fontname, canv._fontsize
        return canv._leading, 1 + canv.stringWidth(self.text, fn, fs)

#Generiranje šihte
class HeaderCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.width, self.height = landscape(A4)

    def draw_header(self):
        # Set font for the header and reduce the font size
        self.setFont("DejaVuSans-Bold", 8)  # Smaller font size

        # Define dimensions for the logo
        logo_width = 12  # Width in mm
        logo_height = 12  # Height in mm

        # Draw the logo
        self.drawImage("static/images/JVP_logo.png", 10 * mm, self.height - 18 * mm, width=logo_width * mm, height=logo_height * mm, preserveAspectRatio=True)
        
        # Define the starting position for the text
        text_x_position = 25 * mm  # Adjust this as needed to position the text correctly

        # Draw the contact information to the right of the logo
        self.drawRightString(self.width - 10 * mm, self.height - 10 * mm, "JVP Đurđevac")
        self.drawRightString(self.width - 10 * mm, self.height - 15 * mm, "48350, Đurđevac, Ul. Grada Vukovara 63")
        self.drawRightString(self.width - 10 * mm, self.height - 20 * mm, "+385 48 812 214")
        
        # Draw a line below the header
        self.line(10 * mm, self.height - 22 * mm, self.width - 10 * mm, self.height - 22 * mm)

    def showPage(self):
        self.draw_header()
        super().showPage()

def generate_timesheet_pdf(response):
    doc = SimpleDocTemplate(response, pagesize=landscape(A4), topMargin=25 * mm, leftMargin=10 * mm, rightMargin=10 * mm, bottomMargin=20 * mm)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(name='TitleStyle', fontName='DejaVuSans-Bold', fontSize=14, alignment=1, spaceAfter=10)
    title_text = f"Šihterica ({croatian_months[date.today().month]})"
    story = [Paragraph(title_text, title_style), Spacer(1, 8 * mm)]

    # Table headers
    day_headers = [Paragraph(str(day), ParagraphStyle(name='DayStyle', fontName='DejaVuSans', fontSize=6, alignment=1)) for day in range(1, 32)]
    summary_headers = [
        verticalText("Bolovanje"),
        verticalText("Sub. rad"),
        verticalText("Nedjelj. rad"),
        verticalText("Fond sati"),
        verticalText("Redovan r."),
        verticalText("Blagdan"),
        verticalText("Vr. Rada"),
        verticalText("Uk. Rad.")
    ]

    # Combine headers
    headers = [
        [Paragraph("rb", ParagraphStyle(name='rbStyle', fontName='DejaVuSans-Bold', fontSize=6, alignment=1)),
         Paragraph("PREZIME I IME", ParagraphStyle(name='NameStyle', fontName='DejaVuSans-Bold', fontSize=6, alignment=1)),
         Paragraph("Datum", ParagraphStyle(name='DatumStyle', fontName='DejaVuSans-Bold', fontSize=6, alignment=1, spaceBefore=2, spaceAfter=2)),
         "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", ""],
        ["", "", ""] + day_headers + summary_headers
    ]

    # Placeholder data for RD and RN rows (this will be replaced with actual data)
    data = [
        ["1", "Markešić Matija"] + ["8"] * 31 + [""] * 8,
        ["2", "Ivić Petar"] + [""] * 31 + [""] * 8
    ] * 6  # Example data

    # Define column widths (adjust as needed)
    rb_col_width = 9 * mm
    name_col_width = 35 * mm
    day_col_width = 6 * mm
    summary_col_width = 8 * mm
    col_widths = [rb_col_width, name_col_width, None] + [day_col_width] * 31 + [summary_col_width] * 8

    # Create the table
    table_data = headers + data
    table = Table(table_data, colWidths=col_widths, repeatRows=1)
    table.setStyle(TableStyle([
        ('SPAN', (2, 0), (-9, 0)),
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('BACKGROUND', (0, 1), (-1, 1), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 1), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 1), 'DejaVuSans-Bold'),
        ('FONTNAME', (0, 2), (-1, -1), 'DejaVuSans'),
        ('FONTSIZE', (0, 0), (-1, 1), 7),
        ('FONTSIZE', (2, 2), (-1, -1), 7),
        ('BOTTOMPADDING', (0, 0), (-1, 1), 2),
        ('TOPPADDING', (0, 0), (-1, 1), 2),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),  # Left-align the "PREZIME I IME" column
        ('VALIGN', (0, 0), (-1, 1), 'MIDDLE'),
    ]))

    story.append(table)
    doc.build(story, canvasmaker=HeaderCanvas)

@login_required
def download_timesheet_pdf(request):
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="report.pdf"'
    generate_timesheet_pdf(response)
    return response