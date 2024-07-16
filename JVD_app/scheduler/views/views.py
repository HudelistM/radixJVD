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
from django.views.decorators.http import require_POST
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

def playground(request):
    return render(request, "scheduler/playground.html")


def is_ajax(request):
    return request.headers.get('x-requested-with') == 'XMLHttpRequest'

@login_required
def landingPage(request):
    if not request.user.is_authenticated:
        return redirect('login')
    return render(request, "scheduler/landing_page.html")


"""def register(request):
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
"""


@login_required
def documents_view(request):
    current_year = datetime.now().year
    croatian_months = {
        1: 'Siječanj', 2: 'Veljača', 3: 'Ožujak', 4: 'Travanj', 5: 'Svibanj', 6: 'Lipanj',
        7: 'Srpanj', 8: 'Kolovoz', 9: 'Rujan', 10: 'Listopad', 11: 'Studeni', 12: 'Prosinac'
    }
    months = []
    for month in range(1, 13):
        month_name = croatian_months[month]
        month_value = f"{current_year}-{month:02d}-01"
        months.append({"name": month_name, "value": month_value})

    documents = [
        {"name": "Šihterica", "type": "xlsx", "url": reverse('download_sihterica')}, 
        {"name": "Raspored", "type": "xlsx", "url": reverse('download_schedule')},
        {"name": "Raspored PDF", "type": "pdf", "url": reverse('download_schedule_pdf')},
        #{"name": "Šihterica PDF", "type": "pdf", "url": reverse('download_timesheet_pdf')},
    ]

    return render(request, 'scheduler/dokumenti.html', {'documents': documents, 'months': months, 'current_year': current_year})

@login_required
def radnici(request):
    employees = Employee.objects.all().order_by('group')  # Ordering by group ensures groups are together
    groups = {}
    for employee in employees:
        group = employee.group
        if group not in groups:
            groups[group] = []
        groups[group].append(employee)

    total_employees = employees.count()  # Count total employees

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
        'groups': groups,  # Pass the grouped employees instead
        'total_employees': total_employees,  # Pass the total employees count
    }
    return render(request, 'scheduler/radnici.html', context)

#--------------------------------------------------------------------------
#--------------------Funkcije za CRUD rasporeda i sati---------------------
#--------------------------------------------------------------------------

def get_month_dates(start_date):
    # start_date is assumed to be the first day of the month
    month_length = monthrange(start_date.year, start_date.month)[1]
    return [start_date + timedelta(days=i) for i in range(month_length)]

def get_first_day_of_week(date):
    """Get the first day of the week for the given date. Week starts on Monday."""
    day_idx = date.weekday()  # Monday is 0 and Sunday is 6
    return date - timedelta(days=day_idx)

def get_last_day_of_week(date):
    """Get the last day of the week for the given date. Week ends on Sunday."""
    day_idx = date.weekday()
    return date + timedelta(days=(6 - day_idx))

def schedule_view(request):
    print("All query params:", request.GET)
    month_start_str = request.GET.get('month_start')
    print("Month start string received:", month_start_str)

    if month_start_str:
        month_start = datetime.strptime(month_start_str, '%Y-%m-%d').date()
    else:
        today = date.today()
        month_start = date(today.year, today.month, 1)

    week_start_date = get_first_day_of_week(month_start)
    last_day_of_month = month_start.replace(day=calendar.monthrange(month_start.year, month_start.month)[1])
    week_end_date = get_last_day_of_week(last_day_of_month)

    num_days = (week_end_date - week_start_date).days + 1
    month_dates = [week_start_date + timedelta(days=i) for i in range(num_days)]

    shift_types = ShiftType.objects.all()

    schedule_data = {}
    for day in month_dates:
        day_key = day.strftime('%Y-%m-%d')
        schedule_data[day_key] = {}
        for shift_type in shift_types:
            entry = ScheduleEntry.objects.filter(date=day, shift_type=shift_type).first()
            if entry:
                schedule_data[day_key][shift_type.id] = entry
            else:
                schedule_data[day_key][shift_type.id] = None

    context = {
        'month_dates': month_dates,
        'shift_types': shift_types,
        'schedule_data': schedule_data,
        'employees': Employee.objects.all(),
        'schedule_view': True,
    }

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'scheduler/scheduler_grid_inner.html', context)
    else:
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
        shift_type_id = data.get('shift_type_id')  # Retrieve shift type ID from request
        shift_type = ShiftType.objects.get(id=shift_type_id)  # Retrieve the shift type object

        overtime_hours = float(data.get('overtime_hours', 0) or 0)
        overtime_hours_service = float(data.get('overtime_service', 0) or 0)
        day_hours = float(data.get('day_hours', 0) or 0)
        night_hours = float(data.get('night_hours', 0) or 0)

        work_day, created = WorkDay.objects.get_or_create(
            employee_id=employee_id, date=date, shift_type=shift_type
        )
        print (overtime_hours_service)
        
        if 'overtime_hours' in data:
            work_day.on_call_hours = max(work_day.on_call_hours - overtime_hours, 0)
            work_day.overtime_hours += overtime_hours
        if 'overtime_service' in data:
            work_day.on_call_hours = max(work_day.on_call_hours - overtime_hours_service, 0)
            work_day.overtime_service += overtime_hours_service
        if 'day_hours' in data:
            work_day.day_hours = day_hours
        if 'night_hours' in data:
            work_day.night_hours = night_hours

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
    shift_type_id = request.GET.get('shift_type_id')

    if not (employee_id and date and shift_type_id):
        return JsonResponse({'error': 'Missing parameters'}, status=400)

    try:
        shift_type = get_object_or_404(ShiftType, pk=shift_type_id)
        work_day = WorkDay.objects.get(employee_id=employee_id, date=date, shift_type=shift_type)
        data = {
            'day_hours': work_day.day_hours,
            'night_hours': work_day.night_hours,
            'overtime_hours': work_day.overtime_hours,
            'on_call_hours': work_day.on_call_hours,
        }
        return JsonResponse({'status': 'success', 'data': data})
    except WorkDay.DoesNotExist:
        return JsonResponse({'error': 'WorkDay matching query does not exist.'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@require_POST
@csrf_exempt
def delete_workday(request):
    try:
        data = json.loads(request.body.decode('utf-8'))
        employee_id = data.get('employee_id')
        date = data.get('date')
        shift_type_id = data.get('shift_type_id')

        date_parsed = datetime.strptime(date, '%Y-%m-%d').date()
        next_day = date_parsed + timedelta(days=1)

        with transaction.atomic():
            # Fetch the ShiftType object to check if it's a night shift
            shift_type = ShiftType.objects.get(id=shift_type_id)

            # Fetch and delete the WorkDay object
            workday = get_object_or_404(WorkDay, employee_id=employee_id, date=date_parsed, shift_type_id=shift_type_id)
            workday.delete()

            # Handle ScheduleEntry for the deleted WorkDay
            schedule_entry = ScheduleEntry.objects.filter(date=date_parsed, shift_type_id=shift_type_id).first()
            if schedule_entry:
                schedule_entry.employees.remove(employee_id)
                if not schedule_entry.employees.exists():
                    schedule_entry.delete()

            # If it is a night shift, also handle the next day's WorkDay
            if shift_type.isNightShift:
                next_day_workday = WorkDay.objects.filter(employee_id=employee_id, date=next_day, shift_type_id=shift_type_id).first()
                if next_day_workday:
                    next_day_workday.delete()

                # Optionally handle the ScheduleEntry for the next day as well
                next_day_schedule_entry = ScheduleEntry.objects.filter(date=next_day, shift_type_id=shift_type_id).first()
                if next_day_schedule_entry:
                    next_day_schedule_entry.employees.remove(employee_id)
                    if not next_day_schedule_entry.employees.exists():
                        next_day_schedule_entry.delete()

        return JsonResponse({'status': 'success', 'message': 'Workday and related entries deleted successfully.'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

def calculate_shift_hours(employee, shift_type, date):
    shift_hours = {
        'day': 0, 'night': 0, 'holiday': 0,
        'saturday': 0, 'sunday': 0,
        'sick_leave': 0, 'on_call': 0
    }

    next_day = date + timedelta(days=1)

    if shift_type.category in ['2.smjena', 'ina 2.smjena', 'janaf 2.smjena', '2.smjena priprema']:
        # Only in this condition, fetch or create the next day's WorkDay entry
        next_day_entry, created = WorkDay.objects.get_or_create(
            employee=employee, date=next_day, shift_type=shift_type
        )

        if shift_type.category == '2.smjena':
            shift_hours['day'] += 3
            shift_hours['night'] += 2
            shift_hours['on_call'] += 12

            # Adjust next day hours appropriately
            next_day_entry.night_hours = max(next_day_entry.night_hours + 6, 6)
            next_day_entry.day_hours = max(next_day_entry.day_hours + 1, 1)

        elif shift_type.category in ['ina 2.smjena', 'janaf 2.smjena']:
            shift_hours['day'] += 3
            shift_hours['night'] += 2


            next_day_entry.night_hours = max(next_day_entry.night_hours + 6, 6)
            next_day_entry.day_hours = max(next_day_entry.day_hours + 1, 1)

        elif shift_type.category == '2.smjena priprema':
            shift_hours['on_call'] += 5
            next_day_entry.on_call_hours = max(next_day_entry.on_call_hours + 7, 7)
        
        # Calculate weekend hours for the next day
        if next_day.weekday() == 5:
            next_day_entry.saturday_hours += next_day_entry.night_hours + next_day_entry.day_hours
        elif next_day.weekday() == 6:
            next_day_entry.sunday_hours += next_day_entry.night_hours + next_day_entry. day_hours

        next_day_entry.save()  # Save changes to the next day entry only if created or modified

    else:
        # Handle other shift types with fixed values as before
        if shift_type.category == '1.smjena':
            shift_hours['day'] += 12
        elif shift_type.category in ['ina 1.smjena', 'janaf 1.smjena']:
            shift_hours['day'] += 12
        elif shift_type.category == 'godišnji odmor':
            shift_hours['holiday'] = 8
        elif shift_type.category == 'bolovanje':
            shift_hours['sick_leave'] = 8

    # Calculate weekend hours if the shift date is on a weekend
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
        if shift_type.isNightShift:
            work_day.night_hours += shift_hours['night']
            work_day.day_hours += shift_hours['day']
            work_day.on_call_hours += shift_hours['on_call']
            work_day.holiday_hours = shift_hours['holiday']
            work_day.sick_leave_hours = shift_hours['sick_leave']
            work_day.saturday_hours = shift_hours['saturday']
            work_day.sunday_hours = shift_hours['sunday']
        else:
            work_day.day_hours = shift_hours['day']  # Update rather than increment
            work_day.night_hours = shift_hours['night']
            work_day.holiday_hours = shift_hours['holiday']
            work_day.sick_leave_hours = shift_hours['sick_leave']
            work_day.saturday_hours = shift_hours['saturday']
            work_day.sunday_hours = shift_hours['sunday']
            work_day.on_call_hours += shift_hours['on_call']
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
                original_workday = WorkDay.objects.filter(date=original_date, shift_type=original_shift_type, employee=employee).first()
                print("Original workday",original_workday)
                #Checking if original workday exists
                if original_workday:
                    #Checking if original workday is a night shift
                    if original_shift_type.isNightShift:
                        next_workday = WorkDay.objects.filter(date=next_day, shift_type=original_shift_type, employee=employee).first()
                        if original_workday.day_hours == 3.0 and original_workday.night_hours == 2.0 and original_workday.on_call_hours == 12.0 and next_workday.day_hours == 4.0 and next_workday.night_hours == 8.0:
                            print("This is the first 2nd shift object being moved",original_workday)
                            original_workday.delete()
                            next_workday.day_hours = 3
                            next_workday.night_hours = 2
                            next_workday.save()
                        elif original_workday.day_hours > 3.0 and original_workday.night_hours > 6.0 and original_workday.on_call_hours == 12.0 and next_workday.day_hours == 1.0 and next_workday.night_hours == 6.0:
                            print("This is the second 2nd shift object being moved",original_workday)
                            next_workday.delete()
                            original_workday.day_hours = 1
                            original_workday.night_hours = 6
                            original_workday.on_call_hours = 0
                            original_workday.save()
                        else:
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
    
