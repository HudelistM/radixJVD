#Django db importovi
from django.db import transaction
from django.db.models import Q
from django.db.models import F
from django.db.models import Sum
#Import formi i modela
from .forms import UserRegisterForm, EmployeeForm
from .models import ScheduleEntry, ShiftType, Employee, WorkDay, FixedHourFund, Holiday, ExcessHours
#Django.views importovi
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
#Django http importovi
from django.http import JsonResponse
from django.http import HttpResponse


from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from datetime import date, timedelta, datetime
from django.contrib import messages
import json
from django.core import serializers
from django.template.loader import render_to_string
from django.shortcuts import get_object_or_404
import calendar
from calendar import monthrange

#Excel importovi
import xlsxwriter

#import openpyxl
#from openpyxl.styles import Alignment, Border, Side, Font, PatternFill
#from openpyxl.utils import get_column_letter
#from openpyxl.cell.text import InlineFont
#from openpyxl.cell.rich_text import CellRichText,TextBlock
#from openpyxl.worksheet.page import PageMargins
#from openpyxl.styles import Color
#from openpyxl.workbook import Workbook
#from openpyxl.styles.differential import DifferentialStyle
#from openpyxl.formatting.rule import Rule

#Reportlab importovi
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, KeepInFrame
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm,cm

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from django.http import HttpResponse
from io import BytesIO

import logging

logger = logging.getLogger(__name__)



def is_ajax(request):
    return request.headers.get('x-requested-with') == 'XMLHttpRequest'

def landingPage(request):
    return render(request, "scheduler/landing_page.html")
  
def register(request):
    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)  # Log the user in
            return redirect('landingPage')
    else:
        form = UserRegisterForm()
    return render(request, 'scheduler/register.html', {'form': form})

def get_week_dates(start_date):
    # start_date is assumed to be a Monday
    return [start_date + timedelta(days=i) for i in range(7)]

def documents_view(request):
    documents = [
        {"name": "Šihterica", "type": "xlsx", "url": "/download_sihterica"},  # Using your existing view for schedules
        {"name": "Raspored", "type": "xlsx", "url": "/download_schedule"},
        {"name": "PDF", "type": "pdf", "url": "/download_schedule_pdf"},
    ]
    return render(request, 'scheduler/dokumenti.html', {'documents': documents})

def radnici(request):
    
    employees = Employee.objects.all()

    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():  
            user = form.save()
            login(request, user) 
            return redirect('landingPage')  
    else:
        form = UserRegisterForm()
    context = {
        'form': form,
        'employees': employees,
    }
    return render(request, 'scheduler/radnici.html', context)


def add_employee(request):
    if request.method == 'POST':
        form = EmployeeForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Radnik je uspješno dodan!')
            return redirect('radnici') 
    else:
        form = EmployeeForm()
    
    return render(request, 'scheduler/radnici.html', {'form': form})


def schedule_view(request):
    # Default start_date to the current week's Monday if no parameter is passed
    start_date_str = request.GET.get('week_start')
    if start_date_str:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
    else:
        today = date.today()
        start_date = today - timedelta(days=today.weekday())  # Ensure we start on Monday
    
    week_dates = get_week_dates(start_date)

    shift_types = ShiftType.objects.all()

    # Construct the schedule data structure
    # We'll use the date as a string and the shift_type ID to identify each cell
    schedule_data = {}
    for day in week_dates:
        day_key = day.strftime('%Y-%m-%d')
        schedule_data[day_key] = {}
        for shift_type in shift_types:
            # Get the first schedule entry for this day and shift_type or None if it doesn't exist
            entry = ScheduleEntry.objects.filter(date=day, shift_type=shift_type).first()
            schedule_data[day_key][shift_type.id] = entry
    #print(schedule_data)

    context = {
        'week_dates': week_dates,
        'shift_types': shift_types,
        'schedule_data': schedule_data,
        'employees': Employee.objects.all(),
    }
    if is_ajax(request):
        # Render only the schedule part of the page for AJAX requests
        schedule_grid_html = render_to_string('scheduler/scheduler_grid_inner.html', context, request)
        return HttpResponse(schedule_grid_html)

    return render(request, 'scheduler/schedule_grid.html', context)

# New view function to serve schedule data as JSON
@require_http_methods(["GET"])
def api_schedule_data(request):
    # Extract query parameters for week start and end dates
    week_start = request.GET.get('week_start')
    week_end = request.GET.get('week_end')
    
    # Parse the dates from strings to datetime objects
    week_start_date = datetime.strptime(week_start, '%Y-%m-%d').date() if week_start else None
    week_end_date = datetime.strptime(week_end, '%Y-%m-%d').date() if week_end else None
    
    if not week_start_date or not week_end_date:
        return JsonResponse({'error': 'Invalid or missing date parameters'}, status=400)
    
    schedule_entries = ScheduleEntry.objects.filter(
        date__range=[week_start_date, week_end_date]
    ).select_related('shift_type').prefetch_related('employees')
    
    schedule_list = []
    for entry in schedule_entries:
        schedule_list.append({
            "date": entry.date.strftime('%Y-%m-%d'),
            "shift_type_id": entry.shift_type.id,
            "employees": list(entry.employees.values('id', 'name', 'surname', 'group'))
        })
    
    return JsonResponse(schedule_list, safe=False)

@require_http_methods(["POST"])
@transaction.atomic
def update_overtime_hours(request):
    try:
        data = json.loads(request.body.decode('utf-8'))
        employee_id = data.get('employee_id')
        date = data.get('date')
        overtime_hours = float(data.get('overtime_hours', 0) or 0)
        day_hours = float(data.get('day_hours', 0) or 0)
        night_hours = float(data.get('night_hours', 0) or 0)

        work_day, created = WorkDay.objects.get_or_create(employee_id=employee_id, date=date)
        
        if 'overtime_hours' in data:
            work_day.on_call_hours = max(work_day.on_call_hours - overtime_hours, 0)
            work_day.overtime_hours += overtime_hours
        if 'day_hours' in data:
            work_day.day_hours += day_hours
        if 'night_hours' in data:
            work_day.night_hours += night_hours

        work_day.save()

        return JsonResponse({'status': 'success'})
    except WorkDay.DoesNotExist:
        return JsonResponse({'error': 'WorkDay matching query does not exist.'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

@require_http_methods(["GET"])
def get_workday_data(request):
    employee_id = request.GET.get('employee_id')
    date = request.GET.get('date')
    
    try:
        work_day = WorkDay.objects.get(employee_id=employee_id, date=date)
        data = {
            'day_hours': work_day.day_hours,
            'night_hours': work_day.night_hours,
            'overtime_hours': work_day.overtime_hours,
            'on_call_hours': work_day.on_call_hours,
        }
        return JsonResponse({'status': 'success', 'data': data})
    except WorkDay.DoesNotExist:
        return JsonResponse({'error': 'WorkDay matching query does not exist.'}, status=400)

def calculate_shift_hours(employee, shift_type, date):
    shift_hours = {
        'day': 0, 'night': 0, 'holiday': 0,
        'saturday': 0, 'sunday': 0,
        'sick_leave': 0, 'on_call': 0
    }
        # Handle regular 2nd shift separately to add on-call hours
    if shift_type.category == '2.smjena':
        shift_hours['day'] += 3
        shift_hours['night'] += 2
        shift_hours['on_call'] += 12  # Adding 12 hours of on-call duty only for regular 2nd shift

        next_day = date + timedelta(days=1)
        next_day_entry, _ = WorkDay.objects.get_or_create(
            employee=employee, date=next_day
        )
        next_day_entry.night_hours = max(next_day_entry.night_hours, 6)
        next_day_entry.day_hours = max(next_day_entry.day_hours, 1)
        next_day_entry.save()

    elif shift_type.category in ['ina 2.smjena', 'janaf 2.smjena']:
        shift_hours['day'] += 3
        shift_hours['night'] += 2

        next_day = date + timedelta(days=1)
        next_day_entry, _ = WorkDay.objects.get_or_create(
            employee=employee, date=next_day
        )
        next_day_entry.night_hours = max(next_day_entry.night_hours, 6)
        next_day_entry.day_hours = max(next_day_entry.day_hours, 1)
        next_day_entry.save()

    elif shift_type.category == '2.smjena priprema':
        shift_hours['on_call'] += 5

        next_day = date + timedelta(days=1)
        next_day_entry, _ = WorkDay.objects.get_or_create(
            employee=employee, date=next_day
        )
        next_day_entry.on_call_hours = max(next_day_entry.on_call_hours, 7)
        next_day_entry.save()

    else:
        if shift_type.category == '1.smjena':
            shift_hours['day'] += 12
        elif shift_type.category in ['ina 1.smjena', 'janaf 1.smjena']:
            shift_hours['day'] += 12
        elif shift_type.category == 'godišnji odmor':
            shift_hours['holiday'] = 8
        elif shift_type.category == 'bolovanje':
            shift_hours['sick_leave'] = 8

    if date.weekday() == 5:
        shift_hours['saturday'] = shift_hours['day'] + shift_hours['night']
    elif date.weekday() == 6:
        shift_hours['sunday'] = shift_hours['day'] + shift_hours['night']

    return shift_hours


@csrf_exempt
@require_http_methods(["POST"])
def update_schedule(request):
    try:
        data = json.loads(request.body.decode('utf-8'))

        if any(key not in data for key in ['action', 'employeeId', 'shiftTypeId', 'date']):
            return JsonResponse({'error': 'Missing required parameters'}, status=400)

        date = datetime.strptime(data['date'], '%Y-%m-%d').date()
        employee = get_object_or_404(Employee, pk=data['employeeId'])
        shift_type = get_object_or_404(ShiftType, pk=data['shiftTypeId'])

        shift_hours = calculate_shift_hours(employee, shift_type, date)

        work_day, created = WorkDay.objects.get_or_create(
            employee=employee, date=date
        )
        work_day.day_hours += shift_hours['day']
        work_day.night_hours += shift_hours['night']
        work_day.holiday_hours = shift_hours['holiday']
        work_day.sick_leave_hours = shift_hours['sick_leave']
        work_day.saturday_hours = shift_hours['saturday']
        work_day.sunday_hours = shift_hours['sunday']
        work_day.on_call_hours += shift_hours['on_call']
        work_day.save()

        if data['action'] == 'move':
            original_date = datetime.strptime(data['originalDate'], '%Y-%m-%d').date()
            original_shift_type = get_object_or_404(ShiftType, pk=data['originalShiftTypeId'])

            with transaction.atomic():
                original_entry = ScheduleEntry.objects.filter(date=original_date, shift_type=original_shift_type).first()
                if original_entry:
                    original_entry.employees.remove(employee)
                    if not original_entry.employees.exists():
                        original_entry.delete()

                schedule_entry, created = ScheduleEntry.objects.get_or_create(
                    date=date, shift_type=shift_type
                )
                schedule_entry.employees.add(employee)

        elif data['action'] == 'add':
            with transaction.atomic():
                schedule_entry, created = ScheduleEntry.objects.get_or_create(
                    date=date, shift_type=shift_type
                )
                schedule_entry.employees.add(employee)

        return JsonResponse({'status': 'success', 'message': 'Schedule updated', 'created': created}, status=200)

    except Exception as e:
        logger.error(f"Exception in update_schedule: {str(e)}")
        return JsonResponse({'error': 'Server error', 'details': str(e)}, status=500)



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

def croatian_day(date_obj):
    """Return the Croatian day abbreviation for the date."""
    return day_names_cro[calendar.day_name[date_obj.weekday()]]


def create_schedule_excel(week_dates, shift_types, schedule_data, author_name):
    output = BytesIO()
    workbook = xlsxwriter.Workbook(output, {'in_memory': True})
    worksheet = workbook.add_worksheet()

    worksheet.set_landscape()
    worksheet.set_paper(9)
    worksheet.fit_to_pages(1, 1)

    # Define formats
    title_format = workbook.add_format({'bold': True, 'font_size': 18, 'align': 'center', 'valign': 'vcenter'})
    author_format = workbook.add_format({'font_size': 12, 'align': 'right', 'valign': 'vcenter'})
    header_format = workbook.add_format({'bold': True, 'bg_color': '#d9e1f2', 'align': 'center', 'valign': 'vcenter', 'text_wrap': True, 'border': 1})
    date_format = workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter', 'font_size': 14, 'border': 2})
    cell_format = workbook.add_format({'border': 1, 'align': 'center', 'valign': 'vcenter'})
    saturday_date_format = workbook.add_format({'border': 1, 'align': 'center', 'valign': 'vcenter', 'bg_color': '#CCFFCC', 'font_size': 14})
    sunday_date_format = workbook.add_format({'border': 1, 'align': 'center', 'valign': 'vcenter', 'bg_color': '#FFFF99', 'font_size': 14})

    # Text color formats for groups
    group_text_formats = {
        '1': workbook.add_format({'color': '#1E8449'}),
        '2': workbook.add_format({'color': '#D35400'}),
        '3': workbook.add_format({'color': '#2980B9'}),
        # Add more groups as needed
    }

    # Set column widths
    worksheet.set_column(0, 0, 20)
    for idx, _ in enumerate(shift_types, 1):
        worksheet.set_column(idx, idx, 15)

    # Write title and author rows
    title = f"Weekly Schedule for {week_dates[0].strftime('%B')}"
    worksheet.merge_range('A1:H1', title, title_format)
    worksheet.merge_range('A2:H2', f"Made by: {author_name}", author_format)

    # Write header row
    headers = ['Dan Datum'] + [shift_type.name for shift_type in shift_types]
    worksheet.write_row('A3', headers, header_format)

    current_row = 3

    for date in week_dates:
        max_employees = 1
        for shift_type in shift_types:
            schedule_entry = schedule_data.get(date.strftime('%Y-%m-%d'), {}).get(shift_type.id)
            employees = schedule_entry.employees.all() if schedule_entry else []
            max_employees = max(max_employees, len(employees))

        # Determine row formatting for the date cell
        if date.weekday() == 5:  # Saturday
            date_cell_format = saturday_date_format
        elif date.weekday() == 6:  # Sunday
            date_cell_format = sunday_date_format
        else:
            date_cell_format = date_format

        # Merge the date cell dynamically
        merge_to = current_row + max_employees - 1
        worksheet.merge_range(current_row, 0, merge_to, 0, croatian_day(date) + ' ' + date.strftime('%d.%m.%Y.'), date_cell_format)

        for col_idx, shift_type in enumerate(shift_types, start=1):
            schedule_entry = schedule_data.get(date.strftime('%Y-%m-%d'), {}).get(shift_type.id)
            employees = schedule_entry.employees.all() if schedule_entry else []
            emp_blocks = [employees[i:i + 7] for i in range(0, len(employees), 7)]
            for block_idx, block in enumerate(emp_blocks):
                for emp_idx, employee in enumerate(block):
                    cell_value = f"{employee.name} {employee.surname}"
                    group_format = group_text_formats.get(employee.group)
                    zero_width_space = "\u200B"
                    if group_format:
                        worksheet.write_rich_string(current_row + emp_idx, col_idx + block_idx, zero_width_space, group_format, cell_value, cell_format)
                    else:
                        worksheet.write(current_row + emp_idx, col_idx + block_idx, cell_value, cell_format)

        current_row += max_employees or 1

    workbook.close()
    output.seek(0)
    return output



@login_required
def download_schedule(request):
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
            schedule_entry = ScheduleEntry.objects.filter(
                date=day, shift_type=shift_type
            ).first()
            schedule_data[day.strftime('%Y-%m-%d')][shift_type.id] = schedule_entry

    author_name = request.user.username

    excel_file = create_schedule_excel(week_dates, shift_types, schedule_data, author_name)

    response = HttpResponse(content=excel_file.read(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="schedule.xlsx"'
    return response

@login_required
def download_sihterica(request):
    # Define Croatian month names
    croatian_months = {
        1: 'Siječanj', 2: 'Veljača', 3: 'Ožujak',
        4: 'Travanj', 5: 'Svibanj', 6: 'Lipanj',
        7: 'Srpanj', 8: 'Kolovoz', 9: 'Rujan',
        10: 'Listopad', 11: 'Studeni', 12: 'Prosinac'
    }

    # Extract current month and year for the title
    current_date = date.today()
    current_month = current_date.month  # Use the month's numeric value directly
    current_year = current_date.year
    days_in_month = monthrange(current_year, current_month)[1]
    
    output = BytesIO()
    workbook = xlsxwriter.Workbook(output, {'in_memory': True})
    worksheet = workbook.add_worksheet()

    # Set up formats
    title_format = workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter', 'font_size': 16})
    bold_format = workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter', 'font_size': 12})
    header_format = workbook.add_format({'align': 'center', 'bold': True, 'bg_color': '#f0f0f0'})
    total_format = workbook.add_format({'align': 'center', 'bg_color': '#d9e1f2'})
    hours_format = workbook.add_format({'align': 'center'})
    saturday_format = workbook.add_format({'align': 'center', 'bg_color': '#CCFFCC'})  # Green
    sunday_format = workbook.add_format({'align': 'center', 'bg_color': '#FFFF99'})  # Yellow
    gray_format = workbook.add_format({'bg_color': '#E0E0E0', 'align': 'center'})  # Gray
    white_format = workbook.add_format({'bg_color': '#FFFFFF', 'align': 'center'})  # White


    # Group text color formats
    group_text_formats = {
        '1': workbook.add_format({'color': '#1E8449', 'align': 'center', 'valign': 'vcenter', 'font_size': 12, 'bold': True}),
        '2': workbook.add_format({'color': '#D35400', 'align': 'center', 'valign': 'vcenter', 'font_size': 12, 'bold': True}),
        '3': workbook.add_format({'color': '#2980B9', 'align': 'center', 'valign': 'vcenter', 'font_size': 12, 'bold': True}),
    }

    # Set column widths
    worksheet.set_column(0, 0, 20)  # Employee names
    worksheet.set_column(1, 1, 3)    # RD/RN column
    worksheet.set_column(2, 33, 4)   # Day columns
    worksheet.set_column(34, 43, 10) # Aggregate columns

    # Add title row
    month_name = croatian_months[current_month]
    title = f"Evidencija prisutnosti na radu za mjesec {month_name} {current_year}"
    worksheet.merge_range(0, 0, 0, 42, title, title_format)

    # Add headers
    worksheet.merge_range(1, 0, 2, 0, 'Prezime i ime', header_format)

    # Day abbreviations for each day of the week (Monday to Sunday)
    day_abbreviations = ['P', 'U', 'S', 'Č', 'P', 'S', 'N']
    for day in range(1, days_in_month + 1):
        weekday = date(year=current_year, month=current_date.month, day=day).weekday()
        format_to_use = saturday_format if weekday == 5 else sunday_format if weekday == 6 else header_format
        worksheet.write(1, day + 1, day_abbreviations[weekday], format_to_use)
        worksheet.write(2, day + 1, str(day), format_to_use)

    worksheet.merge_range(1, 34, 2, 34, 'Fond sati', total_format)
    worksheet.merge_range(1, 35, 2, 35, 'Regularni rad', total_format)
    worksheet.merge_range(1, 36, 2, 36, 'Turnus', total_format)
    worksheet.merge_range(1, 37, 2, 37, 'Višak fonda', total_format)
    worksheet.merge_range(1, 38, 2, 38, 'Subota', total_format)
    worksheet.merge_range(1, 39, 2, 39, 'Nedjelja', total_format)
    worksheet.merge_range(1, 40, 2, 40, 'Noćni rad', total_format)
    worksheet.merge_range(1, 41, 2, 41, 'Blagdan', total_format)
    worksheet.merge_range(1, 42, 2, 42, 'Bolovanje', total_format)

    # Fill employee data
    row_idx = 3
    employees = Employee.objects.all()
    for employee in employees:
        group_format = group_text_formats.get(employee.group, bold_format)
        worksheet.merge_range(row_idx, 0, row_idx + 1, 0, f"{employee.name} {employee.surname}", group_format)
        worksheet.write(row_idx, 1, 'RD', bold_format)
        worksheet.write(row_idx + 1, 1, 'RN', bold_format)

        # Initialize aggregates
        total_day_hours = total_night_hours = total_saturday_hours = 0
        total_sunday_hours = total_holiday_hours = total_sick_leave_hours = 0

        # Iterate over each day of the month
        for day in range(1, days_in_month + 1):
            current_date = date(year=date.today().year, month=date.today().month, day=day)
            work_day = WorkDay.objects.filter(employee=employee, date=current_date).first()
            weekday = current_date.weekday()
            cell_format = saturday_format if weekday == 5 else sunday_format if weekday == 6 else hours_format

            if work_day:
                worksheet.write(row_idx, day + 1, work_day.day_hours, cell_format)
                worksheet.write(row_idx + 1, day + 1, work_day.night_hours, cell_format)
                total_day_hours += work_day.day_hours
                total_night_hours += work_day.night_hours
                total_saturday_hours += work_day.saturday_hours
                total_sunday_hours += work_day.sunday_hours
                total_holiday_hours += work_day.holiday_hours
                total_sick_leave_hours += work_day.sick_leave_hours
            else:
                worksheet.write(row_idx, day + 1, '', cell_format)
                worksheet.write(row_idx + 1, day + 1, '', cell_format)

        # Load or calculate hourly funds
        try:
            hour_fund = FixedHourFund.objects.get(month__year=current_year, month__month=current_month).required_hours
        except FixedHourFund.DoesNotExist:
            hour_fund = 168  # Default or error handling scenario

        redovan_rad = employee.calculate_redovan_rad(current_month, current_year)
        turnus = employee.calculate_monthly_hours(current_month, current_year)
        visak_sati = employee.calculate_visak_sati(current_month, current_year)

        # Fill in the aggregate data
        worksheet.merge_range(row_idx, 34, row_idx + 1, 34, hour_fund, total_format)
        worksheet.merge_range(row_idx, 35, row_idx + 1, 35, redovan_rad, total_format)
        worksheet.merge_range(row_idx, 36, row_idx + 1, 36, turnus, total_format)
        worksheet.merge_range(row_idx, 37, row_idx + 1, 37, visak_sati, total_format)
        worksheet.merge_range(row_idx, 38, row_idx + 1, 38, total_saturday_hours, total_format)
        worksheet.merge_range(row_idx, 39, row_idx + 1, 39, total_sunday_hours, total_format)
        worksheet.merge_range(row_idx, 40, row_idx + 1, 40, total_night_hours, total_format)
        worksheet.merge_range(row_idx, 41, row_idx + 1, 41, total_holiday_hours, total_format)
        worksheet.merge_range(row_idx, 42, row_idx + 1, 42, total_sick_leave_hours, total_format)

        row_idx += 2
        
    #-----------------------Aggregate table for total overview----------------------------
        
    # First aggregate table start (Assuming row_idx is last used row index)
    agg_start_row = row_idx + 2

    # Title for the first aggregate table, spanning all relevant columns
    worksheet.merge_range(agg_start_row, 0, agg_start_row, 15, f'Ukupni sati za {month_name} {current_year}', title_format)
    agg_start_row += 1

    # Define headers for the first aggregate table and merge cells horizontally
    worksheet.write(agg_start_row, 0, 'Ime i Prezime', header_format)  # Not merged
    worksheet.write(agg_start_row, 1, 'rb.', header_format)  # Not merged
    worksheet.merge_range(agg_start_row, 2, agg_start_row, 3, 'Fond sati', header_format)
    worksheet.merge_range(agg_start_row, 4, agg_start_row, 5, 'Regularni rad', header_format)
    worksheet.merge_range(agg_start_row, 6, agg_start_row, 7, 'Drž. pr. i bla.', header_format)
    worksheet.merge_range(agg_start_row, 8, agg_start_row, 9, 'Godišnji o.', header_format)
    worksheet.merge_range(agg_start_row, 10, agg_start_row, 11, 'Bolovanje', header_format)
    worksheet.merge_range(agg_start_row, 12, agg_start_row, 13, 'Noćni rad', header_format)
    worksheet.merge_range(agg_start_row, 14, agg_start_row, 15, 'Rad sub.', header_format)
    worksheet.merge_range(agg_start_row + 1, 16, agg_start_row + 1, 17, 'Rad. ned.', header_format)
    worksheet.merge_range(agg_start_row + 1, 18, agg_start_row + 1, 19, 'Slobodan dan', header_format)
    worksheet.merge_range(agg_start_row + 1, 20, agg_start_row + 1, 21, 'Turnus', header_format)
    worksheet.merge_range(agg_start_row + 1, 22, agg_start_row + 1, 23, 'Priprema', header_format)
    worksheet.merge_range(agg_start_row + 1, 24, agg_start_row + 1, 25, 'Prek.rad', header_format)
    worksheet.merge_range(agg_start_row + 1, 26, agg_start_row + 1, 27, 'Prek. USLUGA', header_format)
    worksheet.merge_range(agg_start_row + 1, 28, agg_start_row + 1, 29, 'Prek. Višak Fonda', header_format)

    agg_start_row += 2  # Adjust to start filling data

    # Add first aggregate data
    for idx, employee in enumerate(employees):
        work_days = WorkDay.objects.filter(employee=employee, date__year=current_year, date__month=current_date.month)
        total_vacation_hours = sum(day.vacation_hours for day in work_days)
        total_sick_leave_hours = sum(day.sick_leave_hours for day in work_days)
        total_holiday_hours = sum(day.holiday_hours for day in work_days)
        total_day_hours = sum(day.day_hours for day in work_days)
        total_night_hours = sum(day.night_hours for day in work_days)
        total_saturday_hours = sum(day.saturday_hours for day in work_days)
        total_sunday_hours = sum(day.sunday_hours for day in work_days)
        total_on_call_hours = sum(day.on_call_hours for day in work_days)
        total_overtime_hours = sum(day.overtime_hours for day in work_days)
        total_free_days_hours = 0  # Replace placeholder with actual calculation

        row_format = gray_format if idx % 2 == 0 else white_format
        
        worksheet.write(agg_start_row, 0, f"{employee.name} {employee.surname}", row_format)
        worksheet.write(agg_start_row, 1, idx + 1, row_format)
        worksheet.write(agg_start_row, 2, hour_fund, row_format)
        worksheet.write(agg_start_row, 3, total_day_hours, row_format)
        worksheet.write(agg_start_row, 4, total_holiday_hours, row_format)
        worksheet.write(agg_start_row, 5, total_vacation_hours, row_format)
        worksheet.write(agg_start_row, 6, total_sick_leave_hours, row_format)
        worksheet.write(agg_start_row, 7, total_night_hours, row_format)
        worksheet.write(agg_start_row, 8, total_saturday_hours, row_format)
        worksheet.write(agg_start_row, 9, total_sunday_hours, row_format)
        worksheet.write(agg_start_row, 10, total_free_days_hours, row_format)
        worksheet.write(agg_start_row, 11, total_day_hours + total_night_hours, row_format)
        worksheet.write(agg_start_row, 12, total_on_call_hours, row_format)
        worksheet.write(agg_start_row, 13, total_overtime_hours, row_format)
        worksheet.write(agg_start_row, 14, 0, row_format)  # Prek. USLUGA
        worksheet.write(agg_start_row, 15, 0, row_format)  # Prek. Višak Fonda

        agg_start_row += 1

    # Add "Ukupno" row for the first aggregate table
    first_data_row = agg_start_row - len(employees)  # This should be the row index where your first data entry starts
    last_data_row = agg_start_row  # The row before the aggregate starts

    # Add "Ukupno" title in the first column of the total row
    worksheet.write(last_data_row , 0, 'Ukupno', header_format)

    # Writing sum formulas directly below the last data entry
    for col_num in range(2, 16):  # Adjusting the column range for sum
        column_letter_value = column_letter(col_num + 1)  # Using a helper function for Excel column letters
        formula_range = f"{column_letter_value}{first_data_row}:{column_letter_value}{last_data_row}"
        worksheet.write_formula(last_data_row, col_num, f"=SUM({formula_range})", total_format)

    total_preparation_overtime=0


   #-----------------------Aggregate table for sati pripreme-----------------------------
   
   
    first_day_of_month = date(current_year, current_month, 1)
    last_day_of_month = date(current_year, current_month, calendar.monthrange(current_year, current_month)[1])
    weeks = {((first_day_of_month + timedelta(days=x)).isocalendar()[1]) for x in range((last_day_of_month - first_day_of_month).days + 1)}

    # Start the second aggregate table
    agg_start_row += 3  # Space after the first aggregate table
    title_row = agg_start_row
    worksheet.merge_range(title_row, 0, title_row, 9, 'BROJ SATI PRIPREME', title_format)
    agg_start_row += 1

    # Calculate the number of weeks in the current month
    first_day_of_month = date(current_year, current_month, 1)
    last_day_of_month = date(current_year, current_month, calendar.monthrange(current_year, current_month)[1])
    weeks = {((first_day_of_month + timedelta(days=x)).isocalendar()[1]) for x in range((last_day_of_month - first_day_of_month).days + 1)}
    num_weeks = len(weeks)

    # Ensure not to overlap with already merged title
    worksheet.write(agg_start_row, 0, 'Ime i Prezime', header_format)
    worksheet.write(agg_start_row, 1, 'rb.', header_format)

    # Merging the week columns under one header 'Prip. iz rasporeda'
    start_week_col = 2
    end_week_col = start_week_col + num_weeks - 1  # Determine the last column index for weeks

    # Correct merging by ensuring it does not overlap with previous merges
    if title_row == agg_start_row:
        worksheet.merge_range(title_row + 1, start_week_col, title_row + 1, end_week_col, 'Prip. iz rasporeda', header_format)
    else:
        worksheet.merge_range(agg_start_row, start_week_col, agg_start_row, end_week_col, 'Prip. iz rasporeda', header_format)

    # Headers for other columns
    worksheet.write(agg_start_row, end_week_col + 1, 'Priprema um. prekovremene', header_format)
    worksheet.write(agg_start_row, end_week_col + 2, 'Ukupno', header_format)

    agg_start_row += 1  # Move to the next row to start adding weekly data

    for idx, employee in enumerate(employees):
        worksheet.write(agg_start_row, 0, f"{employee.name} {employee.surname}", row_format)
        worksheet.write(agg_start_row, 1, idx + 1, row_format)
        col_offset = 2  # Starting column for week data
        total_weekly_hours = 0  # Reset for each employee
        for week_num in sorted(weeks):
            week_days = [first_day_of_month + timedelta(days=x) for x in range((last_day_of_month - first_day_of_month).days + 1) if (first_day_of_month + timedelta(days=x)).isocalendar()[1] == week_num]
            weekly_hours = sum(WorkDay.objects.filter(employee=employee, date__in=week_days).values_list('on_call_hours', flat=True))
            worksheet.write(agg_start_row, col_offset, weekly_hours, row_format)
            total_weekly_hours += weekly_hours  # Accumulate for total
            col_offset += 1
        # Correct the total column position
        worksheet.write(agg_start_row, col_offset, total_preparation_overtime, row_format)
        worksheet.write(agg_start_row, col_offset + 1, total_weekly_hours, row_format)  # Corrected position for total

        agg_start_row += 1
    
    #-----------------------Aggregate table for višak manjak sati-----------------------------
    
    # Calculate the cumulative excess up to the last month
    previous_month = current_month - 1 if current_month > 1 else 12
    previous_year = current_year if current_month > 1 else current_year - 1
    last_day_of_previous_month = monthrange(previous_year, previous_month)[1]
    previous_month_header = f"Fond sati s {last_day_of_previous_month}.{previous_month}.{previous_year}"

    current_month_excess_header = f"Višak fonda ({croatian_months[current_month]} {current_year})"
    last_day_of_current_month = monthrange(current_year, current_month)[1]
    current_month_header = f"Fond sati s {last_day_of_current_month}.{current_month}.{current_year}"

    # Begin writing the table for cumulative excess
    worksheet.merge_range(agg_start_row, 0, agg_start_row, 4, 'EVIDENCIJA VIŠKA-MANJKA SATI', title_format)
    sub_headers = ['PREZIME I IME', 'rb', previous_month_header, current_month_excess_header, current_month_header]
    worksheet.write_row(agg_start_row + 1, 0, sub_headers, header_format)
    agg_start_row += 2

    # Populate the table with the correct excess hours calculations
    for idx, employee in enumerate(employees):
        # Fetch the previous month's cumulative excess from the database
        try:
            previous_excess_record = ExcessHours.objects.get(employee=employee, year=previous_year, month=previous_month)
            previous_excess = previous_excess_record.excess_hours
        except ExcessHours.DoesNotExist:
            previous_excess = 0  # Handle the case where no record exists

        # Calculate the current month's excess
        current_excess = employee.calculate_visak_sati(current_month, current_year)
        cumulative_excess_current_month = previous_excess + current_excess

        worksheet.write(agg_start_row, 0, f"{employee.surname} {employee.name}", white_format)
        worksheet.write(agg_start_row, 1, idx + 1, white_format)
        worksheet.write(agg_start_row, 2, previous_excess, hours_format)
        worksheet.write(agg_start_row, 3, current_excess, hours_format)
        worksheet.write(agg_start_row, 4, cumulative_excess_current_month, hours_format)

        agg_start_row += 1
        
        # Aggregate table for vacation data
    agg_vacation_start_row = agg_start_row + 2  # Space after the last table

    previous_month_header = f"GO s {last_day_of_previous_month}.{previous_month}.{previous_year}"
    current_month_header_hours = f"GO sati ({croatian_months[current_month]} {current_year})"
    current_month_header_days = f"GO dani ({croatian_months[current_month]} {current_year})"
    previous_month_header = f"GO s {last_day_of_previous_month}.{previous_month}.{previous_year}"

    worksheet.merge_range(agg_vacation_start_row, 0, agg_vacation_start_row, 4, 'EVIDENCIJA GODIŠNJIH ODMORA', title_format)
    vacation_headers = ['Prezime i ime', previous_month_header, current_month_header_hours, current_month_header_days, previous_month_header]
    worksheet.write_row(agg_vacation_start_row + 1, 0, vacation_headers, header_format)
    agg_vacation_start_row += 2

    # Populate the table
    for idx, employee in enumerate(employees):
        # Retrieve vacation data from ExcessHours for previous month
        previous_month = current_month - 1 if current_month > 1 else 12
        previous_year = current_year if current_month > 1 else current_year - 1
        previous_vacation_record = ExcessHours.objects.filter(employee=employee, year=previous_year, month=previous_month).first()
        previous_vacation_hours = previous_vacation_record.vacation_hours_used if previous_vacation_record else 0

        # Current month vacation hours and calculation to days
        current_vacation_hours = WorkDay.objects.filter(employee=employee, date__year=current_year, date__month=current_month).aggregate(Sum('vacation_hours'))['vacation_hours__sum'] or 0
        current_vacation_days = current_vacation_hours / 8  # Assuming 8 hours per day for conversion to days

        # Calculate new cumulative vacation hours and convert to days
        new_cumulative_vacation_hours = previous_vacation_hours + current_vacation_hours
        new_cumulative_vacation_days = new_cumulative_vacation_hours / 8

        # Write data to the worksheet
        worksheet.write(agg_vacation_start_row, 0, f"{employee.surname} {employee.name}", white_format)
        worksheet.write(agg_vacation_start_row, 1, previous_vacation_hours / 8, hours_format)  # Previous month cumulative in days
        worksheet.write(agg_vacation_start_row, 2, current_vacation_hours, hours_format)
        worksheet.write(agg_vacation_start_row, 3, current_vacation_days, hours_format)
        worksheet.write(agg_vacation_start_row, 4, new_cumulative_vacation_days, hours_format)  # New cumulative in days

        agg_vacation_start_row += 1

    workbook.close()
    output.seek(0)

    response = HttpResponse(content=output.read(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="sihterica.xlsx"'
    return response

def column_letter(index):
    """ Convert column index to Excel-style column letter (1-indexed). """
    index -= 1  # Adjusting from 1-indexed to 0-indexed
    result = ''
    while index >= 0:
        result = chr(index % 26 + 65) + result
        index = index // 26 - 1
    return result



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