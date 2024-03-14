from django.shortcuts import render, redirect
from .forms import UserRegisterForm
from django.contrib.auth import login
from datetime import date, timedelta
from .models import ScheduleEntry, ShiftType, Employee


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

    shift_types = ShiftType.objects.all()  # Get all shift types from the database

    context = {
        'week_dates': week_dates,
        'schedule': schedule,
        'shift_types': shift_types,  # Pass the shift types to the template
    }
    return render(request, 'scheduler/schedule_grid.html', context)
