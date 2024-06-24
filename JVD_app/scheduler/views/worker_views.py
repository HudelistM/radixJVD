# Django imports
from django.db import transaction
from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.utils.dateparse import parse_date
from django.core import serializers
from django.template.loader import render_to_string
from django.shortcuts import get_object_or_404

# Your app imports
from ..forms import UserRegisterForm, EmployeeForm
from ..models import ScheduleEntry, ShiftType, Employee, WorkDay

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
            saved_employee = form.save()
            handle_vacation_schedule(saved_employee,
                                     request.POST.get('vacation_start'),
                                     request.POST.get('vacation_end'))
            messages.success(request, 'Employee updated successfully' if employee_id else 'Employee added successfully')
            return redirect('radnici')
    else:
        form = EmployeeForm()
    return render(request, 'scheduler/radnici.html', {'form': form})

def handle_vacation_schedule(employee, start_date, end_date):
    if start_date and end_date:
        start_date = parse_date(start_date)
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
                    defaults={'vacation_hours': hours}
                )
                if not work_created and work_day.vacation_hours != hours:
                    work_day.vacation_hours = hours
                    work_day.save()

            # Move to the next day
            current_date += timedelta(days=1)
            day_count += 1

def radnik_profil(request, employee_id):
    employee = get_object_or_404(Employee, id=employee_id)
    return render(request, 'scheduler/radnik_profil.html', {'employee': employee})