#Django db importovi
from django.db import transaction
from django.db.models import Q
from django.db.models import F
#Import formi i modela
from .forms import UserRegisterForm, EmployeeForm
from .models import ScheduleEntry, ShiftType, Employee
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
        {"name": "Šihterica", "type": "xlsx", "url": "/download_schedule"},  # Using your existing view for schedules
        {"name": "Raspored", "type": "xlsx", "url": "/download_schedule"},
        {"name": "PDF", "type": "pdf", "url": "#"},  # Placeholder URL
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



@csrf_exempt
@require_http_methods(["POST"])
def update_schedule(request):
    try:
        data = json.loads(request.body.decode('utf-8'))
        logger.debug(f"Received data for update: {data}")

        if any(key not in data for key in ['action', 'employeeId', 'shiftTypeId', 'date']):
            return JsonResponse({'error': 'Missing required parameters'}, status=400)

        date = datetime.strptime(data['date'], '%Y-%m-%d').date()
        employee = get_object_or_404(Employee, pk=data['employeeId'])
        shift_type = get_object_or_404(ShiftType, pk=data['shiftTypeId'])

        if data['action'] == 'move':
            original_date = datetime.strptime(data['originalDate'], '%Y-%m-%d').date()
            original_shift_type = get_object_or_404(ShiftType, pk=data['originalShiftTypeId'])

            with transaction.atomic():
                # First, remove the employee from the original entry
                original_entry = ScheduleEntry.objects.filter(date=original_date, shift_type=original_shift_type).first()
                if original_entry:
                    original_entry.employees.remove(employee)
                    # If no employees are left in the schedule entry, delete it
                    if not original_entry.employees.exists():
                        original_entry.delete()

                # Next, add the employee to the new entry, creating if necessary
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
    header_format = workbook.add_format({'bold': True, 'bg_color': '#FFFF00', 'align': 'center', 'valign': 'vcenter', 'text_wrap': True, 'border': 1})
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