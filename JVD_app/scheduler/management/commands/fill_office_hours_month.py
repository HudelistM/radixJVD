# scheduler/management/commands/fill_office_hours_month.py
from django.core.management.base import BaseCommand
from django.db.models import Q
from calendar import monthrange
from datetime import date
from scheduler.models import Employee, WorkDay, ShiftType, Holiday

def is_office_employee(employee):
    return (employee.group == '1') or (employee.group == '6' and employee.name == 'Ana' and employee.surname == 'Bazijanec')

class Command(BaseCommand):
    help = "Fill in a full month of 8h office hours for office employees, skipping vacation/sick/holiday/free days and weekends."

    def add_arguments(self, parser):
        parser.add_argument('year', type=int, help="Year (e.g., 2024)")
        parser.add_argument('month', type=int, help="Month (1-12)")

    def handle(self, *args, **options):
        year = options['year']
        month = options['month']

        if month < 1 or month > 12:
            self.stderr.write("Invalid month provided.")
            return

        _, num_days = monthrange(year, month)

        office_shift = ShiftType.objects.get(name="1. Smjena")
        office_employees = Employee.objects.filter(
            Q(group='1') | (Q(group='6', surname='Bazijanec', name='Ana'))
        )

        for day in range(1, num_days + 1):
            current_date = date(year, month, day)

            # Skip holiday/weekend
            if Holiday.objects.filter(date=current_date).exists() or current_date.weekday() >= 5:
                continue

            for employee in office_employees:
                existing = WorkDay.objects.filter(employee=employee, date=current_date)
                # Check special conditions
                if existing.filter(
                    Q(vacation_hours__gt=0) |
                    Q(sick_leave_hours__gt=0) |
                    Q(holiday_hours__gt=0) |
                    Q(article39_hours__gt=0) |
                    Q(shift_type__category='godišnji odmor') |
                    Q(shift_type__category='bolovanje') |
                    Q(shift_type__name__startswith='Slobodan Dan')
                ).exists():
                    continue

                WorkDay.objects.get_or_create(
                    employee=employee,
                    date=current_date,
                    shift_type=office_shift,
                    defaults={'day_hours': 8}
                )

        self.stdout.write(self.style.SUCCESS(f"Office hours filled for {month}/{year} where applicable."))
