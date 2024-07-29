# Django imports
from django.db import transaction
from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.contrib import messages
from django.http import JsonResponse
from django.utils.dateparse import parse_date
from django.core import serializers
from django.template.loader import render_to_string
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.views.decorators.http import require_POST

# Your app imports
from ..forms import UserRegisterForm, EmployeeForm
from ..models import ScheduleEntry, ShiftType, Employee, WorkDay, FreeDay, Vacation, SickLeave

from datetime import date, timedelta, datetime
import json
import logging

logger = logging.getLogger(__name__)


#--------------------------------------------------------------------------
#------------------------Funkcije za CRUD radnika--------------------------
#--------------------------------------------------------------------------

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
        # Check if the inputs are already date objects
        if isinstance(start_date, str):
            start_date = parse_date(start_date)
        if isinstance(end_date, str):
            end_date = parse_date(end_date)
        
        shift_type_vacation = ShiftType.objects.get(name="Godišnji odmor")  # Ensure this shift type exists
        current_date = start_date
        day_count = 0
        
        while current_date <= end_date:
            # Create a ScheduleEntry for every day of the vacation
            schedule, created = ScheduleEntry.objects.get_or_create(
                date=current_date,
                shift_type=shift_type_vacation
            )
            # Add employee to the schedule entry
            if created:
                schedule.employees.add(employee)
            elif not schedule.employees.filter(id=employee.id).exists():
                schedule.employees.add(employee)

            # Determine hours based on the vacation shift pattern
            if day_count % 4 == 0:  # Day 1: First Shift
                hours = 12
            elif day_count % 4 == 1:  # Day 2: Night Shift starts
                hours = 5
            elif day_count % 4 == 2:  # Day 3: Continuation of Night Shift
                hours = 7
            else:  # Day 4: Free day
                hours = 0

            if hours > 0:
                work_day, work_created = WorkDay.objects.get_or_create(
                    employee=employee, 
                    date=current_date,
                    shift_type=shift_type_vacation,  # Ensure shift_type is set
                    defaults={'vacation_hours': hours}
                )
                if not work_created and work_day.vacation_hours != hours:
                    work_day.vacation_hours = hours
                    work_day.save()

            # Move to the next day
            current_date += timedelta(days=1)
            day_count += 1

def handle_sick_leave_schedule(employee, start_date, end_date):
    if start_date and end_date:
        # Check if the inputs are already date objects
        if isinstance(start_date, str):
            start_date = parse_date(start_date)
        if isinstance(end_date, str):
            end_date = parse_date(end_date)
        
        shift_type_sick_leave = ShiftType.objects.get(name="Bolovanje")  # Ensure this shift type exists
        current_date = start_date
        day_count = 0
        
        while current_date <= end_date:
            # Create a ScheduleEntry for every day of the sick leave
            schedule, created = ScheduleEntry.objects.get_or_create(
                date=current_date,
                shift_type=shift_type_sick_leave
            )
            # Add employee to the schedule entry
            if created:
                schedule.employees.add(employee)
            elif not schedule.employees.filter(id=employee.id).exists():
                schedule.employees.add(employee)

            # Determine hours based on the sick leave shift pattern
            if day_count % 4 == 0:  # Day 1: First Shift
                hours = 12
            elif day_count % 4 == 1:  # Day 2: Night Shift starts
                hours = 5
            elif day_count % 4 == 2:  # Day 3: Continuation of Night Shift
                hours = 7
            else:  # Day 4: Free day
                hours = 0

            if hours > 0:
                work_day, work_created = WorkDay.objects.get_or_create(
                    employee=employee, 
                    date=current_date,
                    shift_type=shift_type_sick_leave,  # Ensure shift_type is set
                    defaults={'sick_leave_hours': hours}
                )
                if not work_created and work_day.sick_leave_hours != hours:
                    work_day.sick_leave_hours = hours
                    work_day.save()

            # Move to the next day
            current_date += timedelta(days=1)
            day_count += 1

def radnik_profil(request, employee_id):
    employee = get_object_or_404(Employee, id=employee_id)
    shift_types = ShiftType.objects.all()
    free_days_choice_count = FreeDay.objects.filter(employee=employee, is_article_39=False).count()
    free_days_by_choice = FreeDay.objects.filter(employee=employee, is_article_39=False)
    vacations = Vacation.objects.filter(employee=employee)
    sick_leaves = SickLeave.objects.filter(employee=employee)
    return render(request, 'scheduler/radnik_profil.html', {
        'employee': employee,
        'shift_types': shift_types,
        'free_days_choice_count': free_days_choice_count,
        'free_days_by_choice': free_days_by_choice,
        'vacations': vacations,
        'sick_leaves': sick_leaves,
    })

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
            free_day, created = FreeDay.objects.get_or_create(employee=employee, date=current_date, is_article_39=is_article_39)
            work_day, created = WorkDay.objects.get_or_create(employee=employee, date=current_date, shift_type=shift_type)

            # Determine hours based on the free day shift pattern
            if day_count % 4 == 0:  # Day 1: First Shift
                hours = 12
            elif day_count % 4 == 1:  # Day 2: Night Shift starts
                hours = 5
            elif day_count % 4 == 2:  # Day 3: Continuation of Night Shift
                hours = 7
            else:  # Day 4: Free day
                hours = 0

            work_day.article39_hours = hours
            work_day.save()

            # Create a ScheduleEntry for the free day
            schedule, created = ScheduleEntry.objects.get_or_create(
                date=current_date,
                shift_type=shift_type
            )
            if created or not schedule.employees.filter(id=employee.id).exists():
                schedule.employees.add(employee)

            current_date += timedelta(days=1)
            day_count += 1
    else:
        date = parse_date(request.POST.get('date'))
        free_day, created = FreeDay.objects.get_or_create(employee=employee, date=date, is_article_39=is_article_39)
        work_day, created = WorkDay.objects.get_or_create(employee=employee, date=date, shift_type=shift_type)
        work_day.save()

        # Create a ScheduleEntry for the free day
        schedule, created = ScheduleEntry.objects.get_or_create(
            date=date,
            shift_type=shift_type
        )
        if created or not schedule.employees.filter(id=employee.id).exists():
            schedule.employees.add(employee)
    
    return redirect('radnik_profil', employee_id=employee_id)

@require_POST
def delete_vacation(request, vacation_id):
    vacation = get_object_or_404(Vacation, id=vacation_id)
    employee_id = vacation.employee.id
    start_date = vacation.start_date
    end_date = vacation.end_date

    # Delete related workdays and schedule entries
    WorkDay.objects.filter(employee=vacation.employee, date__range=[start_date, end_date], shift_type__name="Godišnji odmor").delete()
    ScheduleEntry.objects.filter(date__range=[start_date, end_date], shift_type__name="Godišnji odmor").delete()

    vacation.delete()
    return redirect('radnik_profil', employee_id=employee_id)

@require_POST
def delete_sick_leave(request, sick_leave_id):
    sick_leave = get_object_or_404(SickLeave, id=sick_leave_id)
    employee_id = sick_leave.employee.id
    start_date = sick_leave.start_date
    end_date = sick_leave.end_date

    # Delete related workdays and schedule entries
    WorkDay.objects.filter(employee=sick_leave.employee, date__range=[start_date, end_date], shift_type__name="Bolovanje").delete()
    ScheduleEntry.objects.filter(date__range=[start_date, end_date], shift_type__name="Bolovanje").delete()

    sick_leave.delete()
    return redirect('radnik_profil', employee_id=employee_id)