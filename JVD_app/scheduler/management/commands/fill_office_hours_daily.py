# scheduler/management/commands/fill_office_hours_daily.py
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db.models import Q
from scheduler.models import Employee, WorkDay, ShiftType, Holiday
from django.conf import settings

def is_office_employee(employee):
    return (employee.group == '1') or (employee.group == '6' and employee.name == 'Ana' and employee.surname == 'Bazijanec')

class Command(BaseCommand):
    help = "Fill in daily 8h office hours for office employees if no vacation/sick/holiday/free conditions and not weekend/holiday."

    def handle(self, *args, **options):
        today = timezone.localdate()

        # Check if holiday or weekend
        if Holiday.objects.filter(date=today).exists() or today.weekday() >= 5:
            self.stdout.write("Holiday or weekend. No office hours added.")
            return

        office_shift = ShiftType.objects.get(name="1. Smjena")

        office_employees = Employee.objects.filter(
            Q(group='1') | (Q(group='6', surname='Bazijanec', name='Ana'))
        )

        for employee in office_employees:
            existing = WorkDay.objects.filter(employee=employee, date=today)
            # Check conditions
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
                date=today,
                shift_type=office_shift,
                defaults={'day_hours': 8}
            )

        self.stdout.write(self.style.SUCCESS(f"Office hours filled for {today} where applicable."))
