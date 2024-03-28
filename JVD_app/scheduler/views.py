
from django.shortcuts import render, redirect
from .forms import UserRegisterForm
from django.contrib.auth import login
from datetime import date, timedelta, datetime
from .models import ScheduleEntry, ShiftType, Employee
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
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

def create_schedule_excel(week_dates, schedule_data):
    # Create a workbook and select the active worksheet
    wb = openpyxl.Workbook()
    ws = wb.active

    # Set title and headers
    ws.title = "Weekly Schedule"
    ws.append(['Date'] + [shift_type.name for shift_type in ShiftType.objects.all()])

    # Style the headers
    header_font = Font(bold=True)
    for cell in ws[1]:
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = Border(bottom=Side(border_style="thin"))
        cell.fill = PatternFill(start_color="FFFF00", end_color="FFFF00", fill_type="solid")

    # Populate the Excel file
    for day in week_dates:
        row_data = [day.strftime('%Y-%m-%d')]
        for shift_type in ShiftType.objects.all():
            schedule_entry = schedule_data.get(day.strftime('%Y-%m-%d'), {}).get(shift_type.id)
            if schedule_entry:
                # You could customize this part to include the information you want
                row_data.append(', '.join(e.name for e in schedule_entry.employees.all()))
            else:
                row_data.append('No schedule entry')
        ws.append(row_data)

    # Set column width based on the longest entry
    for column_cells in ws.columns:
        length = max(len(str(cell.value)) for cell in column_cells)
        ws.column_dimensions[get_column_letter(column_cells[0].column)].width = length

    return wb

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
    wb = create_schedule_excel(week_dates, schedule_data)

    # Save the workbook to a BytesIO object
    excel_file = BytesIO()
    wb.save(excel_file)
    excel_file.seek(0)

    # Construct response
    response = HttpResponse(content=excel_file.read())
    response['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    response['Content-Disposition'] = 'attachment; filename=weekly_schedule.xlsx'
    return response