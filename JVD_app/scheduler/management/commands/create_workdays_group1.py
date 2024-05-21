from django.core.management.base import BaseCommand
from django.utils import timezone
from scheduler.models import Employee, WorkDay
from datetime import datetime

class Command(BaseCommand):
    help = 'Generira WorkDay zapise za sve radnike grupe 1, default datum je trenutni'

    def add_arguments(self, parser):
        # Add an optional argument to specify a specific date
        parser.add_argument('--date', type=str, help='Specificirajte datum (format: YYYY-MM-DD)')

    def handle(self, *args, **kwargs):
        date_arg = kwargs['date']
        
        # If a date is provided, use it; otherwise, use today
        if date_arg:
            try:
                target_date = datetime.strptime(date_arg, '%Y-%m-%d').date()
            except ValueError:
                self.stderr.write(self.style.ERROR('Invalid date format. Use YYYY-MM-DD.'))
                return
        else:
            target_date = timezone.now().date()

        group1_employees = Employee.objects.filter(group='1')

        for employee in group1_employees:
            work_day, created = WorkDay.objects.get_or_create(
                employee=employee,
                date=target_date,
                defaults={'day_hours': 8, 'night_hours': 0}
            )
            if not created:
                work_day.day_hours = 8
                work_day.night_hours = 0
                work_day.save()

            self.stdout.write(self.style.SUCCESS(f'Processed {employee} for date {target_date}'))