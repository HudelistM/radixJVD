# Django imports
from django.db import transaction
from django.contrib.auth import login
from django.contrib import messages
from django.http import JsonResponse
from django.utils.dateparse import parse_date
from django.core import serializers
from django.template.loader import render_to_string
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.views.decorators.http import require_POST
from django.utils import timezone
from collections import defaultdict
from django.db.models import Sum

from ..forms import UserRegisterForm, EmployeeForm
from ..models import ShiftType, Employee, WorkDay, FreeDay, Vacation, SickLeave, Holiday, ExcessHours

from datetime import date, timedelta, datetime
import json
import logging
from calendar import monthrange

logger = logging.getLogger(__name__)



#--------------------------------------------------------------------------
#------------------------Funkcije za CRUD radnika--------------------------
#--------------------------------------------------------------------------

def is_office_employee(employee):
    return (employee.group == '1') or (employee.group == '6' and employee.name == 'Ana' and employee.surname == 'Bazijanec')


def get_week_dates(start_date):
    # start_date is assumed to be a Monday
    return [start_date + timedelta(days=i) for i in range(7)]


def get_employee_data(request, employee_id):
    from django.http import JsonResponse
    try:
        employee = Employee.objects.get(pk=employee_id)
        return JsonResponse({
            'name': employee.name,
            'surname': employee.surname,
            'role': employee.role,
            'group': employee.group,
        })
    except Employee.DoesNotExist:
        return JsonResponse({'error': 'Employee not found'}, status=404)



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

@require_http_methods(["DELETE"])
def delete_employee(request, employee_id):
    try:
        employee = Employee.objects.get(pk=employee_id)
        employee.delete()
        return JsonResponse({'message': 'Employee deleted successfully'}, status=204)
    except Employee.DoesNotExist:
        return JsonResponse({'error': 'Employee not found'}, status=404)

def add_or_edit_employee(request):
    if request.method == 'POST':
        employee_id = request.POST.get('employee_id')
        if employee_id:
            employee = Employee.objects.get(id=employee_id)
            form = EmployeeForm(request.POST, instance=employee)
        else:
            form = EmployeeForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Employee updated successfully' if employee_id else 'Employee added successfully')
            return redirect('radnici')
    else:
        form = EmployeeForm()
    return render(request, 'scheduler/radnici.html', {'form': form})


def handle_vacation_schedule(employee, start_date, end_date):
    if start_date and end_date:
        if isinstance(start_date, str):
            start_date = parse_date(start_date)
        if isinstance(end_date, str):
            end_date = parse_date(end_date)
        
        shift_type_vacation = ShiftType.objects.get(name="Godišnji odmor")

        current_date = start_date
        day_count = 0
        while current_date <= end_date:
            if is_office_employee(employee):
                # Office employee: 8 hours weekday, 0 if weekend/holiday
                is_holiday = Holiday.objects.filter(date=current_date).exists()
                if current_date.weekday() < 5 and not is_holiday:
                    hours = 8
                else:
                    hours = 0
            else:
                # Shift employee, follow old pattern 12-5-7-0
                pattern_day = day_count % 4
                if pattern_day == 0:
                    hours = 12
                elif pattern_day == 1:
                    hours = 5
                elif pattern_day == 2:
                    hours = 7
                else:
                    hours = 0

            work_day, work_created = WorkDay.objects.get_or_create(
                employee=employee, 
                date=current_date,
                shift_type=shift_type_vacation,
                defaults={'vacation_hours': hours}
            )
            if not work_created:
                work_day.vacation_hours = hours
                work_day.save()

            current_date += timedelta(days=1)
            day_count += 1


def handle_sick_leave_schedule(employee, start_date, end_date):
    if start_date and end_date:
        if isinstance(start_date, str):
            start_date = parse_date(start_date)
        if isinstance(end_date, str):
            end_date = parse_date(end_date)
        
        shift_type_sick = ShiftType.objects.get(name="Bolovanje")

        current_date = start_date
        day_count = 0
        total_days = (end_date - start_date).days + 1
        switch_day = 42  # After 42 days, office employees: same logic, shift employees: 8 hours

        while current_date <= end_date:
            if is_office_employee(employee):
                # Same logic as vacation for office employees
                is_holiday = Holiday.objects.filter(date=current_date).exists()
                if current_date.weekday() < 5 and not is_holiday:
                    hours = 8
                else:
                    hours = 0
            else:
                # Shift employees: old pattern first 42 days, then 8 hours
                if day_count < switch_day:
                    pattern_day = day_count % 4
                    if pattern_day == 0:
                        hours = 12
                    elif pattern_day == 1:
                        hours = 5
                    elif pattern_day == 2:
                        hours = 7
                    else:
                        hours = 0
                else:
                    # After 42 days, 8 hours every day for shift employees
                    is_holiday = Holiday.objects.filter(date=current_date).exists()
                    if current_date.weekday() < 5 and not is_holiday:
                        hours = 8
                    else:
                        hours = 0

            work_day, created = WorkDay.objects.get_or_create(
                employee=employee,
                date=current_date,
                shift_type=shift_type_sick,
                defaults={'sick_leave_hours': hours}
            )
            if not created or work_day.sick_leave_hours != hours:
                work_day.sick_leave_hours = hours
                work_day.save()

            current_date += timedelta(days=1)
            day_count += 1



def radnik_profil(request, employee_id):
    employee = get_object_or_404(Employee, id=employee_id)
    shift_types = ShiftType.objects.all()
    free_days_choice_count = FreeDay.objects.filter(employee=employee, is_article_39=False).count()
    free_days_by_choice = FreeDay.objects.filter(employee=employee, is_article_39=False)
    vacations = Vacation.objects.filter(employee=employee)
    sick_leaves = SickLeave.objects.filter(employee=employee)
    
    # Handle month navigation
    month_str = request.GET.get('month')
    if month_str:
        selected_date = datetime.strptime(month_str, '%Y-%m-%d').date()
    else:
        selected_date = date.today()
    
    current_year = selected_date.year
    current_month = selected_date.month
    days_in_month = monthrange(current_year, current_month)[1]
    
    # Now that current_year and current_month are defined, we can get excess_record
    excess_record = ExcessHours.objects.filter(employee=employee, year=current_year, month=current_month).first()
    excess_hours_value = excess_record.excess_hours if excess_record else 0

    # Generate list of dates in the month
    month_dates = [date(current_year, current_month, day) for day in range(1, days_in_month + 1)]
    
    # Fetch WorkDay entries for the employee in the selected month
    # (You might want to filter by the month if you only want monthly data)
    workdays = WorkDay.objects.filter(employee=employee).select_related('shift_type')
    
    # Create a dictionary with date as key and list of workdays as value
    from collections import defaultdict
    workday_dict = defaultdict(list)
    for wd in workdays:
        workday_dict[wd.date].append(wd)
    
    # Calculate used and remaining vacation hours
    used_vacation_hours = employee.calculate_used_vacation_hours()
    remaining_vacation_hours = employee.remaining_vacation_hours()
    
    # For each vacation, calculate total hours and days used
    for vacation in vacations:
        vacation_workdays = WorkDay.objects.filter(
            employee=employee,
            date__range=[vacation.start_date, vacation.end_date],
            shift_type__name="Godišnji odmor"
        )
        total_vacation_hours = vacation_workdays.aggregate(total=Sum('vacation_hours'))['total'] or 0
        total_vacation_days = total_vacation_hours / 8
        vacation.total_vacation_hours = total_vacation_hours
        vacation.total_vacation_days = total_vacation_days
    
    context = {
        'employee': employee,
        'shift_types': shift_types,
        'free_days_choice_count': free_days_choice_count,
        'free_days_by_choice': free_days_by_choice,
        'vacations': vacations,
        'sick_leaves': sick_leaves,
        'month_dates': month_dates,
        'workday_dict': workday_dict,
        'selected_date': selected_date,
        'used_vacation_hours': used_vacation_hours,
        'remaining_vacation_hours': remaining_vacation_hours,
        'excess_hours_value': excess_hours_value,
    }

    return render(request, 'scheduler/radnik_profil.html', context)


@csrf_exempt
@require_http_methods(["POST"])
def update_monthly_excess_hours(request, employee_id):
    employee = get_object_or_404(Employee, id=employee_id)
    data = json.loads(request.body)
    value = data.get('value')
    # We need month and year currently displayed
    # We'll pass them through the request or deduce them from the page (we have them in radnik_profil)
    # Let's say we send current_year and current_month from JS:
    current_year = int(data.get('year'))
    current_month = int(data.get('month'))

    try:
        excess_value = float(value)
    except ValueError:
        return JsonResponse({'status': 'error', 'message': 'Invalid value'}, status=400)

    # Get or create the record for ExcessHours
    excess_record, created = ExcessHours.objects.get_or_create(
        employee=employee, year=current_year, month=current_month,
        defaults={'excess_hours': 0, 'vacation_hours_used': 0}
    )
    excess_record.excess_hours = excess_value
    excess_record.save()

    return JsonResponse({'status': 'success'})


@csrf_exempt
def update_workday_hours(request, employee_id):
    if request.method == 'POST':
        data = json.loads(request.body)
        date_str = data.get('date').strip()
        field = data.get('field')
        value = data.get('value')
        shift_type_id = data.get('shift_type_id')

        if not all([date_str, field, shift_type_id]):
            return JsonResponse({'status': 'error', 'message': 'Invalid data'}, status=400)

        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
        employee = get_object_or_404(Employee, id=employee_id)
        shift_type = get_object_or_404(ShiftType, id=shift_type_id)

        workday, created = WorkDay.objects.get_or_create(
            employee=employee, 
            date=date_obj, 
            shift_type=shift_type
        )

        if value == '':
            setattr(workday, field, None)
        else:
            try:
                value_float = float(value)
            except ValueError:
                return JsonResponse({'status': 'error', 'message': 'Invalid value'}, status=400)

            setattr(workday, field, value_float)

        # If we updated overtime fields, apply on_call subtraction logic
        if field == 'overtime_hours':
            overtime_hours = workday.overtime_hours or 0
            if workday.on_call_hours > 0:
                workday.on_call_hours = max(workday.on_call_hours - overtime_hours, 0)
        elif field == 'overtime_service':
            overtime_service = workday.overtime_service or 0
            if workday.on_call_hours > 0:
                workday.on_call_hours = max(workday.on_call_hours - overtime_service, 0)

        workday.save()

        return JsonResponse({'status': 'success', 'message': 'Workday updated'})
    else:
        return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=405)

@csrf_exempt
@require_http_methods(["POST"])
def update_employee_field(request, employee_id):
    employee = get_object_or_404(Employee, id=employee_id)
    data = json.loads(request.body)
    field = data.get('field')
    value = data.get('value')

    if field not in ['role_number', 'excess_hours']:
        return JsonResponse({'status': 'error', 'message': 'Invalid field'}, status=400)

    try:
        if field == 'role_number':
            employee.role_number = int(value)
        elif field == 'excess_hours':
            employee.excess_hours = float(value)

        employee.save()
        return JsonResponse({'status': 'success'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


@csrf_exempt
def remove_workday_entry(request, employee_id):
    if request.method == 'DELETE':
        try:
            data = json.loads(request.body)
            date_str = data.get('date')
            shift_type_id = data.get('shift_type_id')

            if not date_str or not shift_type_id:
                return JsonResponse({'status': 'error', 'message': 'Invalid data'}, status=400)

            date_parsed = datetime.strptime(date_str, '%Y-%m-%d').date()
            employee = get_object_or_404(Employee, id=employee_id)
            shift_type = get_object_or_404(ShiftType, id=shift_type_id)

            # Fetch and delete the WorkDay object
            workday = get_object_or_404(WorkDay, employee=employee, date=date_parsed, shift_type=shift_type)
            
            # If it is a night shift, also handle the next day's WorkDay
            if shift_type.isNightShift:
                next_day = date_parsed + timedelta(days=1)
                next_day_workday = WorkDay.objects.filter(employee=employee, date=next_day, shift_type=shift_type).first()

                if (workday.day_hours == 3.0 and workday.night_hours == 2.0 and
                    next_day_workday and next_day_workday.day_hours == 4.0 and next_day_workday.night_hours == 8.0):
                    # This is the first 2nd shift being deleted
                    workday.delete()
                    next_day_workday.day_hours = 3
                    next_day_workday.night_hours = 2
                    if next_day.weekday() == 5:
                        next_day_workday.saturday_hours = 5
                    if next_day.weekday() == 6:
                        next_day_workday.sunday_hours = 5
                    next_day_workday.save()
                elif (workday.day_hours > 3.0 and workday.night_hours > 6.0 and
                      next_day_workday and next_day_workday.day_hours == 1.0 and next_day_workday.night_hours == 6.0):
                    # This is the second 2nd shift being deleted
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
                    # Default case
                    workday.delete()
                    if next_day_workday:
                        next_day_workday.delete()
            else:
                workday.delete()

            return JsonResponse({'status': 'success', 'message': 'Workday and related entries deleted successfully.'})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    else:
        return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=405)



def handle_vacation(request, employee_id):
    employee = get_object_or_404(Employee, id=employee_id)
    start_date = request.POST.get('start_date')
    end_date = request.POST.get('end_date')
    
    # Convert start_date and end_date to date objects if they are strings
    if isinstance(start_date, str):
        start_date = parse_date(start_date)
    if isinstance(end_date, str):
        end_date = parse_date(end_date)
    
    # Call the existing handle_vacation_schedule function
    handle_vacation_schedule(employee, start_date, end_date)
    
    # Save the vacation period
    Vacation.objects.create(employee=employee, start_date=start_date, end_date=end_date)
    
    return redirect('radnik_profil', employee_id=employee_id)

@csrf_exempt
@require_http_methods(["POST"])
def edit_vacation(request, vacation_id):
    data = json.loads(request.body)
    start_date_str = data.get('start_date')
    end_date_str = data.get('end_date')

    vacation = get_object_or_404(Vacation, id=vacation_id)
    employee = vacation.employee
    old_start_date = vacation.start_date
    old_end_date = vacation.end_date

    # Delete old workdays
    WorkDay.objects.filter(employee=employee, date__range=[old_start_date, old_end_date], shift_type__name="Godišnji odmor").delete()

    # Update vacation dates
    vacation.start_date = parse_date(start_date_str)
    vacation.end_date = parse_date(end_date_str)
    vacation.save()

    # Recreate workdays
    handle_vacation_schedule(employee, vacation.start_date, vacation.end_date)

    return JsonResponse({'status': 'success', 'message': 'Vacation updated successfully'})

@require_POST
def update_total_vacation_hours(request, employee_id):
    employee = get_object_or_404(Employee, id=employee_id)
    total_vacation_hours = request.POST.get('total_vacation_hours')
    try:
        total_vacation_hours = int(total_vacation_hours)
        employee.total_vacation_hours = total_vacation_hours
        employee.save()
        messages.success(request, 'Ukupni godišnji sati su ažurirani.')
    except ValueError:
        messages.error(request, 'Neispravan unos za ukupne godišnje sate.')
    return redirect('radnik_profil', employee_id=employee_id)


def handle_sick_leave(request, employee_id):
    employee = get_object_or_404(Employee, id=employee_id)
    start_date = request.POST.get('start_date')
    end_date = request.POST.get('end_date')
    
    # Convert start_date and end_date to date objects if they are strings
    if isinstance(start_date, str):
        start_date = parse_date(start_date)
    if isinstance(end_date, str):
        end_date = parse_date(end_date)
    
    # Call the existing handle_sick_leave_schedule function
    handle_sick_leave_schedule(employee, start_date, end_date)
    
    # Save the sick leave period
    SickLeave.objects.create(employee=employee, start_date=start_date, end_date=end_date)
    
    return redirect('radnik_profil', employee_id=employee_id)

@csrf_exempt
@require_http_methods(["POST"])
def edit_sick_leave(request, sick_leave_id):
    data = json.loads(request.body)
    start_date_str = data.get('start_date')
    end_date_str = data.get('end_date')

    sick_leave = get_object_or_404(SickLeave, id=sick_leave_id)
    employee = sick_leave.employee
    old_start_date = sick_leave.start_date
    old_end_date = sick_leave.end_date

    # Delete old workdays
    WorkDay.objects.filter(employee=employee, date__range=[old_start_date, old_end_date], shift_type__name="Bolovanje").delete()

    # Update sick leave dates
    sick_leave.start_date = parse_date(start_date_str)
    sick_leave.end_date = parse_date(end_date_str)
    sick_leave.save()

    # Recreate workdays
    handle_sick_leave_schedule(employee, sick_leave.start_date, sick_leave.end_date)

    return JsonResponse({'status': 'success', 'message': 'Sick leave updated successfully'})


def handle_overtime(request, employee_id):
    employee = get_object_or_404(Employee, id=employee_id)
    date = parse_date(request.POST.get('date'))
    hours = float(request.POST.get('hours'))
    overtime_type = request.POST.get('overtime_type')
    shift_type_id = request.POST.get('shift_type')
    shift_type = ShiftType.objects.get(id=shift_type_id)
    
    work_day, created = WorkDay.objects.get_or_create(employee=employee, date=date, shift_type=shift_type)
    
    # Update specific overtime fields based on type
    if overtime_type == 'overtime_free_day':
        work_day.overtime_free_day += hours
    elif overtime_type == 'overtime_free_day_service':
        work_day.overtime_free_day_service += hours

    # Decrement on_call_hours by the added overtime hours if needed
    #work_day.on_call_hours = max(0, work_day.on_call_hours - hours)
    work_day.save()
    
    return redirect('radnik_profil', employee_id=employee_id)


def handle_free_day(request, employee_id):
    employee = get_object_or_404(Employee, id=employee_id)
    is_article_39 = request.POST.get('is_article_39') == 'true'
    if not is_article_39:
        free_days_choice_count = FreeDay.objects.filter(employee=employee, is_article_39=False).count()
        if free_days_choice_count >= 2:
            messages.error(request, 'Radnik već ima 2 slobodna dana po izboru!')
            return redirect('radnik_profil', employee_id=employee_id)
    
    shift_type_id = request.POST.get('shift_type')
    shift_type = get_object_or_404(ShiftType, id=shift_type_id)

    if is_article_39:
        start_date = parse_date(request.POST.get('date_start'))
        end_date = parse_date(request.POST.get('date_end'))

        current_date = start_date
        day_count = 0
        while current_date <= end_date:
            free_day, created = FreeDay.objects.get_or_create(employee=employee, date=current_date, is_article_39=True)
            work_day, created = WorkDay.objects.get_or_create(employee=employee, date=current_date, shift_type=shift_type)

            if is_office_employee(employee):
                is_holiday = Holiday.objects.filter(date=current_date).exists()
                if current_date.weekday() < 5 and not is_holiday:
                    hours = 8
                else:
                    hours = 0
                work_day.article39_hours = hours
            else:
                # Old cycle for shift employees: 12/5/7/0 pattern
                pattern_day = day_count % 4
                if pattern_day == 0:
                    hours = 12
                elif pattern_day == 1:
                    hours = 5
                elif pattern_day == 2:
                    hours = 7
                else:
                    hours = 0
                work_day.article39_hours = hours

            work_day.save()
            current_date += timedelta(days=1)
            day_count += 1
    else:
        date = parse_date(request.POST.get('date'))
        free_day, created = FreeDay.objects.get_or_create(employee=employee, date=date, is_article_39=False)
        work_day, created = WorkDay.objects.get_or_create(employee=employee, date=date, shift_type=shift_type)

        if is_office_employee(employee):
            is_holiday = Holiday.objects.filter(date=date).exists()
            if date.weekday() < 5 and not is_holiday:
                hours = 8
            else:
                hours = 0
        else:
            # For a single free day by choice for shift employees, could default to 0 or follow a specific pattern if desired
            # If you previously treated it as 0 hours, keep it 0:
            hours = 0

        work_day.article39_hours = hours
        work_day.save()

    return redirect('radnik_profil', employee_id=employee_id)


@require_POST
def delete_vacation(request, vacation_id):
    vacation = get_object_or_404(Vacation, id=vacation_id)
    employee_id = vacation.employee.id
    start_date = vacation.start_date
    end_date = vacation.end_date

    # Delete related workdays
    WorkDay.objects.filter(employee=vacation.employee, date__range=[start_date, end_date], shift_type__name="Godišnji odmor").delete()

    vacation.delete()
    return redirect('radnik_profil', employee_id=employee_id)


@require_POST
def delete_sick_leave(request, sick_leave_id):
    sick_leave = get_object_or_404(SickLeave, id=sick_leave_id)
    employee_id = sick_leave.employee.id
    start_date = sick_leave.start_date
    end_date = sick_leave.end_date

    # Delete related workdays
    WorkDay.objects.filter(employee=sick_leave.employee, date__range=[start_date, end_date], shift_type__name="Bolovanje").delete()

    sick_leave.delete()
    return redirect('radnik_profil', employee_id=employee_id)
