from django.shortcuts import render, redirect
from .forms import UserRegisterForm
from django.contrib.auth import login
from datetime import date, timedelta
from .models import ScheduleEntry, ShiftType, Employee
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import json


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
    # Assume start_date is the beginning of the week (Monday)
    start_date = date.today() - timedelta(days=date.today().weekday())  # Adjust as necessary
    week_dates = get_week_dates(start_date)

    schedule = {day: ScheduleEntry.objects.filter(date=day) for day in week_dates}
    shift_types = ShiftType.objects.all()
    employees = Employee.objects.all()  # Get all employees from the database

    context = {
        'week_dates': week_dates,
        'schedule': schedule,
        'shift_types': shift_types,
        'employees': employees,  # Pass the employees to the template
    }
    return render(request, 'scheduler/schedule_grid.html', context)

@csrf_exempt
@require_http_methods(["POST"])
def update_schedule(request):
    # Parse the JSON body
    data = json.loads(request.body)
    employee_id = data.get('employeeId')
    shift_type_id = data.get('shiftTypeId')
    date = data.get('date')
    
    # Ensure all data is present
    if not all([employee_id, shift_type_id, date]):
        return JsonResponse({'error': 'Missing data'}, status=400)

    # Update the database
    try:
        employee = Employee.objects.get(id=employee_id)
        shift_type = ShiftType.objects.get(id=shift_type_id)
        schedule_entry, created = ScheduleEntry.objects.get_or_create(date=date, shift_type=shift_type)

        # Print the employees before adding a new one
        before_employees = list(schedule_entry.employees.values_list('id', flat=True))
        print("Before Adding:", before_employees)

        schedule_entry.employees.add(employee)
        
        # Print the employees after adding the new one
        after_employees = list(schedule_entry.employees.values_list('id', flat=True))
        print("After Adding:", after_employees)

        return JsonResponse({'status': 'success', 'created': created})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)