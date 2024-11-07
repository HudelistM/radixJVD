#Django db importovi
from django.db import transaction
from django.db.models import Q
from django.db.models import F
from django.db.models import Sum
from collections import defaultdict

#Import formi i modela
from ..forms import UserRegisterForm, EmployeeForm
from ..models import ShiftType, Employee, WorkDay, FixedHourFund, Holiday, ExcessHours, Vacation, SickLeave, FreeDay
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
        {"name": "Šihterica INA", "type": "xlsx", "url": reverse('download_sihterica_ina')},
        {"name": "Raspored", "type": "xlsx", "url": reverse('download_schedule')},
        #{"name": "Raspored PDF", "type": "pdf", "url": reverse('download_schedule_pdf')},
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

def is_night_shift_start(wd):
    if not wd.shift_type.isNightShift:
        return False
    if wd.shift_type.name == 'Priprema od 19:00':
        # Check if it's the starting day based on on_call_hours
        if wd.on_call_hours == 5:
            return True  # Starting day
        else:
            return False  # Next day
    # Existing logic for other night shifts
    if wd.day_hours >= 3:
        return True
    else:
        return False


@login_required
def schedule_view(request):

    employees = Employee.objects.all().order_by('group', 'role_number')
    employee_groups = employees.values_list('group', flat=True).distinct()
    date_start_str = request.GET.get('date_start')
    date_end_str = request.GET.get('date_end')
    month_start_str = request.GET.get('month_start')

    if date_start_str and date_end_str:
        date_start = datetime.strptime(date_start_str, '%Y-%m-%d').date()
        date_end = datetime.strptime(date_end_str, '%Y-%m-%d').date()
    else:
        if month_start_str:
            date_start = datetime.strptime(month_start_str, '%Y-%m-%d').date()
        else:
            today = date.today()
            date_start = date(today.year, today.month, 1)
        # Set date_end to the last day of the month
        date_end = date_start.replace(day=calendar.monthrange(date_start.year, date_start.month)[1])

    # Extend to cover the entire week of both the first and last day
    week_start_date = get_first_day_of_week(date_start)  # Monday of the first week
    week_end_date = get_last_day_of_week(date_end)  # Sunday of the last week

    # Create a list of dates from the first Monday to the last Sunday
    num_days = (week_end_date - week_start_date).days + 1
    month_dates = [week_start_date + timedelta(days=i) for i in range(num_days)]

    shift_types = ShiftType.objects.all()

    # Prepare schedule data using WorkDay
    schedule_data = {}
    workdays = WorkDay.objects.filter(date__range=[week_start_date, week_end_date]).select_related('employee', 'shift_type')
    

    for day in month_dates:
        day_key = day.strftime('%Y-%m-%d')
        schedule_data[day_key] = {}
        for shift_type in shift_types:
            employees = []
            for wd in workdays:
                if wd.date == day and wd.shift_type == shift_type:
                    include_wd = True
                    if shift_type.isNightShift:
                        # Use the helper function to determine if this is the start of a night shift
                        if not is_night_shift_start(wd):
                            include_wd = False
                    if include_wd:
                        employees.append(wd.employee)
            schedule_data[day_key][shift_type.id] = employees if employees else None

    # Fetch employees and sort them by group and role_number
    employees = Employee.objects.all().order_by('group', 'role_number')

    context = {
        'month_dates': month_dates,  # Dates include entire weeks covering the month
        'shift_types': shift_types,
        'schedule_data': schedule_data,
        'employees': employees,  # Pass sorted employees to the template
        'schedule_view': True,
        'current_month_start': date_start.strftime('%Y-%m-%d'),
        'date_start': date_start.strftime('%Y-%m-%d'),
        'date_end': date_end.strftime('%Y-%m-%d'),
        'employee_groups': employee_groups,
    }

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'scheduler/scheduler_grid_inner.html', context)
    else:
        return render(request, 'scheduler/schedule_grid.html', context)

@require_http_methods(["GET"])
def api_schedule_data(request):
    date_start_str = request.GET.get('date_start')
    date_end_str = request.GET.get('date_end')
    month_start_fetch = request.GET.get('month_start')
    month_end_fetch = request.GET.get('month_end')

    if date_start_str and date_end_str:
        date_start = datetime.strptime(date_start_str, '%Y-%m-%d').date()
        date_end = datetime.strptime(date_end_str, '%Y-%m-%d').date()
    elif month_start_fetch and month_end_fetch:
        date_start = datetime.strptime(month_start_fetch, '%Y-%m-%d').date()
        date_end = datetime.strptime(month_end_fetch, '%Y-%m-%d').date()
    else:
        return JsonResponse({'error': 'Invalid or missing date parameters'}, status=400)

    workdays = WorkDay.objects.filter(
        date__range=[date_start, date_end]
    ).select_related('employee', 'shift_type')

    schedule_dict = defaultdict(lambda: defaultdict(list))

    for wd in workdays:
        include_wd = True
        if wd.shift_type.isNightShift:
            # Use the helper function to determine if this is the start of a night shift
            if not is_night_shift_start(wd):
                include_wd = False
        if include_wd:
            date_str = wd.date.strftime('%Y-%m-%d')
            shift_type_id = wd.shift_type.id
            key = (date_str, shift_type_id)

            schedule_dict[key]['date'] = date_str
            schedule_dict[key]['shift_type_id'] = shift_type_id
            if 'employees' not in schedule_dict[key]:
                schedule_dict[key]['employees'] = []
            schedule_dict[key]['employees'].append({
                'id': wd.employee.id,
                'name': wd.employee.name,
                'surname': wd.employee.surname,
                'group': wd.employee.group,
                'role_number': wd.employee.role_number
            })

    schedule_list = list(schedule_dict.values())
    return JsonResponse(schedule_list, safe=False)



@require_http_methods(["POST"])
@transaction.atomic
def update_overtime_hours(request):
    try:
        # Parse JSON data from the request
        data = json.loads(request.body.decode('utf-8'))

        # Extract required identifiers
        employee_id = data.get('employee_id')
        date = data.get('date')
        shift_type_id = data.get('shift_type_id')

        # Fetch the ShiftType instance
        shift_type = ShiftType.objects.get(id=shift_type_id)

        # Get or create the WorkDay instance
        work_day, created = WorkDay.objects.get_or_create(
            employee_id=employee_id, date=date, shift_type=shift_type
        )

        # Update fields based on the data received
        if 'day_hours' in data:
            work_day.day_hours = float(data.get('day_hours', 0))
        if 'night_hours' in data:
            work_day.night_hours = float(data.get('night_hours', 0))
        if 'overtime_hours' in data:
            overtime_hours = float(data.get('overtime_hours', 0))
            # Adjust on_call_hours by subtracting overtime_hours
            work_day.on_call_hours = max(work_day.on_call_hours - overtime_hours, 0)
            work_day.overtime_hours = overtime_hours
        if 'overtime_service' in data:
            overtime_service = float(data.get('overtime_service', 0))
            # Adjust on_call_hours by subtracting overtime_service
            work_day.on_call_hours = max(work_day.on_call_hours - overtime_service, 0)
            work_day.overtime_service = overtime_service
        if 'note' in data:
            work_day.note = data.get('note', '')

        # Save the updated WorkDay instance
        work_day.save()

        return JsonResponse({'status': 'success'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

    
    
@require_http_methods(["GET"])
def get_shift_type_details(request):
    shift_type_id = request.GET.get('shift_type_id')

    if not shift_type_id:
        return JsonResponse({'error': 'Missing shift_type_id parameter'}, status=400)

    try:
        shift_type = ShiftType.objects.get(pk=shift_type_id)
        data = {
            'id': shift_type.id,
            'name': shift_type.name,
            'category': shift_type.category,
        }
        return JsonResponse(data)
    except ShiftType.DoesNotExist:
        return JsonResponse({'error': 'ShiftType not found'}, status=404)


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
            'overtime_service': work_day.overtime_service,
            'on_call_hours': work_day.on_call_hours,
            'note': work_day.note,
        }
        return JsonResponse({'status': 'success', 'data': data})
    except WorkDay.DoesNotExist:
        return JsonResponse({'status': 'success', 'data': {}})
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

        shift_type = ShiftType.objects.get(id=shift_type_id)
        # Fetch and delete the WorkDay object
        workday = get_object_or_404(WorkDay, employee_id=employee_id, date=date_parsed, shift_type_id=shift_type_id)
        
        # If it is a night shift, also handle the next day's WorkDay
        if shift_type.isNightShift:
            print("We are about to delete a night shift")
            next_day_workday = WorkDay.objects.filter(employee_id=employee_id, date=next_day, shift_type_id=shift_type_id).first()
            if workday.day_hours == 3.0 and workday.night_hours == 2.0 and next_day_workday.day_hours == 4.0 and next_day_workday.night_hours == 8.0:
                print("This is the first 2nd shift being deleted")
                workday.delete()
                next_day_workday.day_hours = 3
                next_day_workday.night_hours = 2
                if next_day.weekday() == 5:
                    next_day_workday.saturday_hours = 5
                if next_day.weekday() == 6:
                    next_day_workday.sunday_hours = 5
                next_day_workday.save()
                
            elif workday.day_hours > 3.0 and workday.night_hours > 6.0 and next_day_workday.day_hours == 1.0 and next_day_workday.night_hours == 6.0:
                print("This is  the second 2nd shift being deleted")
                next_day_workday.delete()
                workday.day_hours = 1
                workday.night_hours = 6
                workday.on_call_hours = 0
                if date_parsed.weekday() == 5:
                    workday.saturday_hours = 7
                if date_parsed.weekday() == 6:
                    workday.sunday_hours = 7
                workday.save()   
            else:
                print("We are defaulting")
                workday.delete()
                next_day_workday.delete()
        else:               
            workday.delete()

        return JsonResponse({'status': 'success', 'message': 'Workday and related entries deleted successfully.'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

def calculate_shift_hours(employee, shift_type, date):
    current_day_hours = {
        'day_hours': 0, 'night_hours': 0, 'holiday_hours': 0,
        'saturday_hours': 0, 'sunday_hours': 0,
        'sick_leave_hours': 0, 'on_call_hours': 0,
        'vacation_hours': 0
    }

    next_day_hours = None

    next_day = date + timedelta(days=1)

    is_holiday_today = Holiday.objects.filter(date=date).exists()
    is_holiday_next_day = Holiday.objects.filter(date=next_day).exists()

    if shift_type.category in ['2.smjena', 'ina 2.smjena', 'janaf 2.smjena', '2.smjena priprema']:
        # Night shifts
        next_day_hours = {
            'day_hours': 0, 'night_hours': 0, 'holiday_hours': 0,
            'saturday_hours': 0, 'sunday_hours': 0,
            'sick_leave_hours': 0, 'on_call_hours': 0,
            'vacation_hours': 0
        }

        if shift_type.category == '2.smjena':
            current_day_hours['day_hours'] += 3
            current_day_hours['night_hours'] += 2
            current_day_hours['on_call_hours'] += 12

            # Next day hours
            next_day_hours['night_hours'] += 6
            next_day_hours['day_hours'] += 1

            # Handle holiday hours
            if is_holiday_today:
                current_day_hours['holiday_hours'] += current_day_hours['day_hours'] + current_day_hours['night_hours']
            if is_holiday_next_day:
                next_day_hours['holiday_hours'] = next_day_hours['day_hours'] + next_day_hours['night_hours']

        elif shift_type.category in ['ina 2.smjena', 'janaf 2.smjena']:
            current_day_hours['day_hours'] += 3
            current_day_hours['night_hours'] += 2

            # Next day hours
            next_day_hours['night_hours'] += 6
            next_day_hours['day_hours'] += 1

            # Handle holiday hours
            if is_holiday_today:
                current_day_hours['holiday_hours'] += current_day_hours['day_hours'] + current_day_hours['night_hours']
            if is_holiday_next_day:
                next_day_hours['holiday_hours'] = next_day_hours['day_hours'] + next_day_hours['night_hours']

        elif shift_type.category == '2.smjena priprema':
            current_day_hours['on_call_hours'] += 5
            next_day_hours['on_call_hours'] += 7

            # Handle holiday hours
            if is_holiday_today:
                current_day_hours['holiday_hours'] += current_day_hours['on_call_hours']
            if is_holiday_next_day:
                next_day_hours['holiday_hours'] = next_day_hours['on_call_hours']

        # Calculate weekend hours for the next day
        if next_day.weekday() == 5:
            next_day_hours['saturday_hours'] = next_day_hours['day_hours'] + next_day_hours['night_hours']
        elif next_day.weekday() == 6:
            next_day_hours['sunday_hours'] = next_day_hours['day_hours'] + next_day_hours['night_hours']

    else:
        # Handle other shift types with fixed values as before
        if shift_type.category in ['1.smjena', 'ina 1.smjena', 'janaf 1.smjena']:
            current_day_hours['day_hours'] = 12
        elif shift_type.category == 'godišnji odmor':
            current_day_hours['vacation_hours'] = 8
        elif shift_type.category == 'bolovanje':
            current_day_hours['sick_leave_hours'] = 8

        # Handle holiday hours
        if is_holiday_today:
            if shift_type.category in ['1.smjena', 'ina 1.smjena', 'janaf 1.smjena']:
                current_day_hours['holiday_hours'] = current_day_hours['day_hours']
            # For 'godišnji odmor' and 'bolovanje', holiday hours are not counted

    # Calculate weekend hours if the shift date is on a weekend
    if date.weekday() == 5:
        current_day_hours['saturday_hours'] = current_day_hours['day_hours'] + current_day_hours['night_hours']
    elif date.weekday() == 6:
        current_day_hours['sunday_hours'] = current_day_hours['day_hours'] + current_day_hours['night_hours']

    return current_day_hours, next_day_hours



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

        # Check if employee is on vacation, sick leave, or free day on that date
        on_vacation = Vacation.objects.filter(employee=employee, start_date__lte=date, end_date__gte=date).exists()
        on_sick_leave = SickLeave.objects.filter(employee=employee, start_date__lte=date, end_date__gte=date).exists()
        has_free_day = FreeDay.objects.filter(employee=employee, date=date).exists()

        if on_vacation:
            return JsonResponse({'status': 'error', 'message': 'Ovaj radnik je na godišnjem odmoru.'}, status=400)
        if on_sick_leave:
            return JsonResponse({'status': 'error', 'message': 'Ovaj radnik je na bolovanju.'}, status=400)
        if has_free_day:
            return JsonResponse({'status': 'error', 'message': 'Ovaj radnik ima slobodan dan.'}, status=400)

        # Start an atomic transaction
        with transaction.atomic():
            # Calculate shift hours for the new schedule
            current_day_hours, next_day_hours = calculate_shift_hours(employee, shift_type, date)

            # Handling the existing entry for the date and employee
            work_day, created = WorkDay.objects.get_or_create(
                employee=employee, date=date, shift_type=shift_type
            )

            # Update work_day fields for the current day
            for key, value in current_day_hours.items():
                if shift_type.isNightShift and key in ['day_hours', 'night_hours', 'on_call_hours', 'saturday_hours', 'sunday_hours']:
                    setattr(work_day, key, getattr(work_day, key) + value)
                else:
                    setattr(work_day, key, value)

            work_day.save()

            # If there is a next_day_hours, handle it
            if next_day_hours:
                next_day = date + timedelta(days=1)
                next_work_day, created = WorkDay.objects.get_or_create(
                    employee=employee, date=next_day, shift_type=shift_type
                )

                for key, value in next_day_hours.items():
                    if shift_type.isNightShift and key in ['day_hours', 'night_hours', 'on_call_hours', 'saturday_hours', 'sunday_hours']:
                        setattr(next_work_day, key, getattr(next_work_day, key) + value)
                    else:
                        setattr(next_work_day, key, value)
                next_work_day.save()

            # Process the action ('move' or 'add')
            if data['action'] == 'move':
                original_date = datetime.strptime(data['originalDate'], '%Y-%m-%d').date()
                original_shift_type = get_object_or_404(ShiftType, pk=data['originalShiftTypeId'])
                next_day = original_date + timedelta(days=1)

                # Handling workday entries for night shifts
                original_workday = WorkDay.objects.filter(date=original_date, shift_type=original_shift_type, employee=employee).first()
                if original_workday:
                    if original_shift_type.isNightShift:
                        next_workday = WorkDay.objects.filter(date=next_day, shift_type=original_shift_type, employee=employee).first()
                        if original_workday.day_hours == 3.0 and original_workday.night_hours == 2.0 and next_workday and next_workday.day_hours == 4.0 and next_workday.night_hours == 8.0:
                            original_workday.delete()
                            next_workday.day_hours = 3
                            next_workday.night_hours = 2
                            next_workday.save()
                        elif original_workday.day_hours > 3.0 and original_workday.night_hours > 6.0 and next_workday and next_workday.day_hours == 1.0 and next_workday.night_hours == 6.0:
                            next_workday.delete()
                            original_workday.day_hours = 1
                            original_workday.night_hours = 6
                            original_workday.on_call_hours = 0
                            original_workday.save()
                        else:
                            original_workday.delete()
                            if next_workday:
                                next_workday.delete()
                    else:
                        original_workday.delete()

            elif data['action'] == 'add':
                pass  # No additional action required

            # Logging success
            logger.info(f"Schedule updated successfully for employee {employee.id} on {date}")

        return JsonResponse({'status': 'success', 'message': 'Schedule updated', 'created': created}, status=200)

    except Exception as e:
        logger.error(f"Exception in update_schedule: {str(e)}")
        return JsonResponse({'error': 'Server error', 'details': str(e)}, status=500)
