from django.core.management.base import BaseCommand
from datetime import datetime
from myapp.models import Employee

class Command(BaseCommand):
    help = 'Calculates and stores excess hours for all employees'

    def handle(self, *args, **options):
        today = datetime.today()
        year = today.year
        month = today.month - 1  # Calculate for the previous month
        if month == 0:  # Handle January case
            month = 12
            year -= 1

        employees = Employee.objects.all()
        for employee in employees:
            # Assume calculate_and_store_excess_hours is implemented to do the job
            calculate_and_store_excess_hours(employee, year, month)
            self.stdout.write(self.style.SUCCESS(f'Successfully updated excess hours for {employee} for {month}/{year}'))