from django.core.management.base import BaseCommand
from django.utils import timezone
from scheduler.models import Employee
from datetime import date

class Command(BaseCommand):
    help = "Calculate and store excess hours for the previous month for all employees."

    def handle(self, *args, **options):
        # We'll calculate the excess hours for the previous month
        today = date.today()
        # If today is, say, Nov 1, we want to calculate October. If January 1, we want December of the previous year.
        previous_month = today.month - 1 if today.month > 1 else 12
        previous_year = today.year if today.month > 1 else today.year - 1

        employees = Employee.objects.all()
        for emp in employees:
            emp.calculate_and_store_excess_hours(previous_year, previous_month)

        self.stdout.write(self.style.SUCCESS(
            f"Excess hours calculated and stored for {previous_month}/{previous_year}."
        ))
