#Django db importovi
from django.db import transaction
from django.db.models import Q
from django.db.models import F
from django.db.models import Sum

#Import formi i modela
from ..forms import UserRegisterForm, EmployeeForm
from ..models import ScheduleEntry, ShiftType, Employee, WorkDay, FixedHourFund, Holiday, ExcessHours
#Django.views importovi
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
#Django http importovi
from django.http import JsonResponse
from django.http import HttpResponse
from django.urls import reverse


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
from django.utils.dateparse import parse_date

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
        {"name": "Šihterica", "type": "xlsx", "url": reverse('download_sihterica')}, 
        {"name": "Raspored", "type": "xlsx", "url": reverse('download_schedule')},
        {"name": "Raspored PDF", "type": "pdf", "url": reverse('download_schedule_pdf')},
        {"name": "Šihterica PDF", "type": "pdf", "url": reverse('download_timesheet_pdf')},
    ]
    for doc in documents:
        logger.debug(f"Document URL for {doc['name']}: {doc['url']}")
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


#--------------------------------------------------------------------------
#--------------------Funkcije za CRUD rasporeda i sati---------------------
#--------------------------------------------------------------------------

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
            employee=employee, date=next_day, shift_type=shift_type
        )
        next_day_entry.night_hours = max(next_day_entry.night_hours, 6)
        next_day_entry.day_hours = max(next_day_entry.day_hours, 1)
        next_day_entry.save()

    elif shift_type.category in ['ina 2.smjena', 'janaf 2.smjena']:
        shift_hours['day'] += 3
        shift_hours['night'] += 2

        next_day = date + timedelta(days=1)
        next_day_entry, _ = WorkDay.objects.get_or_create(
            employee=employee, date=next_day, shift_type=shift_type
        )
        next_day_entry.night_hours = max(next_day_entry.night_hours, 6)
        next_day_entry.day_hours = max(next_day_entry.day_hours, 1)
        next_day_entry.save()

    elif shift_type.category == '2.smjena priprema':
        shift_hours['on_call'] += 5

        next_day = date + timedelta(days=1)
        next_day_entry, _ = WorkDay.objects.get_or_create(
            employee=employee, date=next_day, shift_type=shift_type
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
@transaction.atomic
def update_schedule(request):
    try:
        data = json.loads(request.body.decode('utf-8'))

        if any(key not in data for key in ['action', 'employeeId', 'shiftTypeId', 'date']):
            return JsonResponse({'error': 'Missing required parameters'}, status=400)

        date = datetime.strptime(data['date'], '%Y-%m-%d').date()
        employee = get_object_or_404(Employee, pk=data['employeeId'])
        shift_type = get_object_or_404(ShiftType, pk=data['shiftTypeId'])

        # Calculate shift hours for the new schedule
        shift_hours = calculate_shift_hours(employee, shift_type, date)

        # Handling the existing entry for the date and employee
        work_day, created = WorkDay.objects.get_or_create(
            employee=employee, date=date, shift_type=shift_type
        )
        work_day.day_hours = shift_hours['day']  # Update rather than increment
        work_day.night_hours = shift_hours['night']
        work_day.holiday_hours = shift_hours['holiday']
        work_day.sick_leave_hours = shift_hours['sick_leave']
        work_day.saturday_hours = shift_hours['saturday']
        work_day.sunday_hours = shift_hours['sunday']
        work_day.on_call_hours = shift_hours['on_call']
        work_day.save()

        # Move or add action
        if data['action'] == 'move':
            original_date = datetime.strptime(data['originalDate'], '%Y-%m-%d').date()
            original_shift_type = get_object_or_404(ShiftType, pk=data['originalShiftTypeId'])
            next_day = original_date + timedelta(days=1)
            #Handling schedule entries
            with transaction.atomic():
                # Handle moving the employee to a new shift
                original_entry = ScheduleEntry.objects.filter(date=original_date, shift_type=original_shift_type).first()
                if original_entry:
                    original_entry.employees.remove(employee)
                    if not original_entry.employees.exists():
                        original_entry.delete()

                # Create or get the new schedule entry
                schedule_entry, created = ScheduleEntry.objects.get_or_create(
                    date=date, shift_type=shift_type
                )
                schedule_entry.employees.add(employee)
            #Handling workday entries
            with transaction.atomic():
                original_workday = WorkDay.objects.filter(date=original_date, shift_type=original_shift_type, employee=employee)
                print("Original workday",original_workday)

                if original_workday:
                    if original_shift_type.isNightShift:
                        next_workday = WorkDay.objects.filter(date=next_day, shift_type=original_shift_type, employee=employee)
                        print("Next workday: ",next_workday)
                        original_workday.delete()
                        next_workday.delete()
                    else:
                        original_workday.delete()

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