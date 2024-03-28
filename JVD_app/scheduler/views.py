
from django.shortcuts import render, redirect
from .forms import UserRegisterForm, EmployeeForm
from django.contrib.auth import login
from datetime import date, timedelta, datetime
from .models import ScheduleEntry, ShiftType, Employee
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib import messages
import json
from django.core import serializers
from django.http import HttpResponse
from django.template.loader import render_to_string
#Excel importovi
import openpyxl
from openpyxl.styles import Alignment, Border, Side, Font, PatternFill
from openpyxl.utils import get_column_letter
from django.http import HttpResponse
from io import BytesIO
from openpyxl.styles import Color
from openpyxl.workbook import Workbook
from openpyxl.styles.differential import DifferentialStyle
from openpyxl.formatting.rule import Rule



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
    # Parse request body
    data = json.loads(request.body.decode('utf-8'))
    action = data.get('action')
    employee_id = data.get('employeeId')
    shift_type_id = data.get('shiftTypeId')
    date_str = data.get('date')
    original_shift_type_id = data.get('originalShiftTypeId')
    original_date_str = data.get('originalDate')

    try:
        employee = Employee.objects.get(pk=employee_id)
        shift_type = ShiftType.objects.get(pk=shift_type_id)
        date = datetime.strptime(date_str, '%Y-%m-%d').date()
        
        # Handle moving the employee
        if action == 'move' and original_shift_type_id and original_date_str:
            original_shift_type = ShiftType.objects.get(pk=original_shift_type_id)
            original_date = datetime.strptime(original_date_str, '%Y-%m-%d').date()
            ScheduleEntry.objects.filter(date=original_date, shift_type=original_shift_type, employees=employee).delete()

        schedule_entry, created = ScheduleEntry.objects.get_or_create(date=date, shift_type=shift_type)
        if not schedule_entry.employees.filter(pk=employee.pk).exists():
            schedule_entry.employees.add(employee)

        return JsonResponse({'status': 'success', 'created': created, 'action': action})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

    # Define color coding for employee groups as font colors
    font_colors = {

    }


def as_text(value):
    if value is None:
        return ""
    return str(value)

def create_schedule_excel(week_dates, schedule_data, created_by):
    # Initialize Excel workbook and worksheet
    wb = Workbook()
    ws = wb.active

    day_names = ['Pon', 'Uto', 'Sri', 'Čet', 'Pet', 'Sub', 'Ned']

    # Set page setup to A4 and orientation to landscape
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.page_setup.orientation = ws.ORIENTATION_LANDSCAPE

    # Define styles for headers and cells
    bold_font = Font(bold=True, size=11)
    normal_font = Font(size=10)
    alignment_center = Alignment(horizontal="center", vertical="center")
    thin_border = Border(bottom=Side(style='thin'))

    ws.merge_cells('A1:C1')
    ws['A1'] = "JAVNA VATROGASNA POSTROJBA ĐURĐEVAC"
    ws.merge_cells('D1:F1')
    ws['D1'] = "Raspored smjena - Tjedni 2024"
    ws.merge_cells('G1:I1')
    ws['G1'] = f"Izradio: {created_by}"

    # Freeze panes below headers
    ws.freeze_panes = "A4"
    
    # Styling headers
    header_font = Font(size=11, bold=True)
    for cell in ws["1:1"]:
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")

    # Add column headers
    ws.append(['Date'] + [shift_type.name for shift_type in ShiftType.objects.all()])
    for cell in ws[3]:
        cell.font = bold_font
        cell.alignment = alignment_center
        cell.border = thin_border

    # Define colors for days and groups
    fill_saturday = PatternFill(start_color='CCFFCC', end_color='CCFFCC', fill_type='solid')
    fill_sunday = PatternFill(start_color='FFFF99', end_color='FFFF99', fill_type='solid')
    group_colors = {
        '1': "FF0000",  # Red color for Group 1
        '2': "0000FF",  # Blue color for Group 2
        '3': "008000",  # Green color for Group 3
        '4': "FFA500",  # Orange color for Group 4
    }

    # Populate the Excel file with data
    for day in week_dates:
        day_data = [day.strftime('%Y-%m-%d')]
        for shift in ShiftType.objects.all():
            entry = schedule_data.get(day.strftime('%Y-%m-%d'), {}).get(shift.id)
            if entry:
                entry_data = ', '.join([f"{e.name} {e.surname} ({e.group})" for e in entry.employees.all()])
                day_data.append(entry_data)
            else:
                day_data.append('-')
        ws.append(day_data)

    # Style the data rows and apply group colors
    for row in ws.iter_rows(min_row=4, max_row=ws.max_row):
        for cell in row:
            cell.font = normal_font
            if cell.col_idx == 1:
                cell.alignment = alignment_center
                cell.border = thin_border
            else:
                # Apply group colors to employee names
                text_parts = cell.value.split(', ') if cell.value else []
                for part in text_parts:
                    group = part.split(' ')[-1].strip('()')
                    cell.font = Font(color=group_colors.get(group, '000000'))

    # Adjust column widths
    for column_cells in ws.columns:
        length = max(len(as_text(cell.value)) for cell in column_cells)
        ws.column_dimensions[get_column_letter(column_cells[0].column)].width = length

    # Apply colors to weekend rows
    for row in ws.iter_rows(min_row=4, max_row=ws.max_row):
        if row[0].value:
            day_of_week = datetime.strptime(row[0].value, '%Y-%m-%d').weekday()
            if day_of_week == 5:
                for cell in row:
                    cell.fill = fill_saturday
            elif day_of_week == 6:
                for cell in row:
                    cell.fill = fill_sunday

    return wb


def as_text(value):
    if value is None:
        return ""
    return str(value)

def download_schedule(request):
    # Generate dates for the desired schedule week
    week_dates = get_week_dates(date.today())  # Replace with the dates you want to include in your Excel

    # Gather your schedule data here
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

    # Create an Excel workbook with the schedule data
    current_user_name = request.user.get_full_name() if request.user.is_authenticated else "Unknown User"
    wb = create_schedule_excel(week_dates, schedule_data, current_user_name)

    # Save the workbook to a BytesIO object
    excel_file = BytesIO()
    wb.save(excel_file)
    excel_file.seek(0)

    # Construct response
    response = HttpResponse(content=excel_file.read())
    response['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    response['Content-Disposition'] = 'attachment; filename=weekly_schedule.xlsx'
    return response