from django.db import models
from django.db.models import Sum
from django.db.models import F

class Employee(models.Model):
    name = models.CharField(max_length=100)
    surname = models.CharField(max_length=100)
    role = models.CharField(max_length=100)
    role_number = models.IntegerField(null=True, blank=True)
    group = models.CharField(max_length=100)
    total_vacation_hours = models.IntegerField(default=0)  # New field for assigned vacation hours

    def __str__(self):
        return f"{self.name} {self.surname} ({self.role})"

    def calculate_used_vacation_hours(self):
        total_used_hours = WorkDay.objects.filter(
            employee=self,
            vacation_hours__gt=0
        ).aggregate(total=Sum('vacation_hours'))['total'] or 0
        return total_used_hours

    def remaining_vacation_hours(self):
        return self.total_vacation_hours - self.calculate_used_vacation_hours()
    
    def calculate_monthly_hours(self, month, year):
        work_days = self.workday_set.filter(date__year=year, date__month=month)
        total_hours = work_days.aggregate(
            total=Sum(F('day_hours') + F('night_hours'))
        )['total'] or 0
        return total_hours

    def calculate_redovan_rad(self, month, year):
        work_days = self.workday_set.filter(date__year=year, date__month=month)
        total_special_hours = work_days.aggregate(
            total=Sum('vacation_hours') + Sum('sick_leave_hours') + Sum('holiday_hours')
        )['total'] or 0
        hour_fond = FixedHourFund.objects.get(month__year=year, month__month=month).required_hours
        return hour_fond - total_special_hours

    def calculate_visak_sati(self, month, year):
        # Calculate Turnus (hours worked during day and night)
        turnus = self.calculate_monthly_hours(month, year)
        
        # Fetch work days for the specified month and year
        work_days = self.workday_set.filter(date__year=year, date__month=month)
        
        # Sum vacation_hours, sick_leave_hours, and article39_hours (Free Day Article 39 Hours)
        special_hours = work_days.aggregate(
            total=Sum('vacation_hours') + Sum('sick_leave_hours') + Sum('article39_hours')
        )['total'] or 0
        
        # Get the Hour Fond for the month
        hour_fond = FixedHourFund.objects.get(month__year=year, month__month=month).required_hours
        
        # Calculate Višak Fonda
        visak_fonda = turnus + special_hours - hour_fond
        return visak_fonda

    
    def calculate_and_store_excess_hours(self, year, month):
        if month == 1:
            previous_excess = 0
            previous_vacation = 0
        else:
            previous_month = month - 1 if month > 1 else 12
            previous_year = year if month > 1 else year - 1
            previous_record, created = ExcessHours.objects.get_or_create(
                employee=self, year=previous_year, month=previous_month,
                defaults={'excess_hours': 0, 'vacation_hours_used': 0}
            )
            previous_excess = previous_record.excess_hours
            previous_vacation = previous_record.vacation_hours_used

        current_excess = self.calculate_visak_sati(month, year)
        vacation_hours_this_month = self.workday_set.filter(
            date__year=year, date__month=month
        ).aggregate(Sum('vacation_hours'))['vacation_hours__sum'] or 0

        cumulative_excess = previous_excess + current_excess
        cumulative_vacation = previous_vacation + vacation_hours_this_month

        # Store or update the record
        ExcessHours.objects.update_or_create(
            employee=self, year=year, month=month,
            defaults={
                'excess_hours': cumulative_excess,
                'vacation_hours_used': cumulative_vacation
            }
        )


class ExcessHours(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    year = models.IntegerField()
    month = models.IntegerField()
    excess_hours = models.IntegerField(default=0)
    vacation_hours_used = models.IntegerField(default=0)

    class Meta:
        unique_together = ('employee', 'year', 'month')

    def __str__(self):
        return f"{self.employee} {self.month}/{self.year} Excess: {self.excess_hours}, Vacation: {self.vacation_hours_used}"



    
class ShiftType(models.Model):
    SHIFT_CATEGORIES = [
        ('1.smjena', '1.Smjena'),
        ('2.smjena', '2.Smjena'),
        ('2.smjena priprema', '2.Smjena Priprema'),
        ('ina 1.smjena', 'INA 1.Smjena'),
        ('ina 2.smjena', 'INA 2.Smjena'),
        ('janaf 1.smjena', 'JANAF 1.Smjena'),
        ('janaf 2.smjena', 'JANAF 2.Smjena'),
        ('godišnji odmor', 'Godišnji Odmor'),
        ('bolovanje', 'Bolovanje'),
        ('slobodan dan','Slobodan Dan'),
    ]

    name = models.CharField(max_length=100)
    category = models.CharField(max_length=20, choices=SHIFT_CATEGORIES,default='1.smjena')
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    is_on_call = models.BooleanField(default=False)
    is_regular = models.BooleanField(default=True)
    isNightShift = models.BooleanField(default=False)

    def __str__(self):
        return self.name


class WorkDay(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    date = models.DateField()
    shift_type = models.ForeignKey(ShiftType, on_delete=models.CASCADE)
    day_hours = models.FloatField(default=0.0)
    night_hours = models.FloatField(default=0.0)
    holiday_hours = models.FloatField(default=0.0, blank=True, null=True)
    vacation_hours = models.FloatField(default=0.0, blank=True, null=True)
    sick_leave_hours = models.FloatField(default=0.0, blank=True, null=True)
    article39_hours = models.FloatField(default=0.0, blank=True, null=True)
    saturday_hours = models.FloatField(default=0.0, blank=True, null=True)
    sunday_hours = models.FloatField(default=0.0, blank=True, null=True)
    on_call_hours = models.FloatField(default=0.0, blank=True, null=True)
    overtime_hours = models.FloatField(default=0.0, blank=True, null=True)
    overtime_service = models.FloatField(default=0.0, blank=True, null=True)
    overtime_free_day = models.FloatField(default=0.0, blank=True, null=True)
    overtime_free_day_service = models.FloatField(default=0.0, blank=True, null=True)
    overtime_excess_fond = models.FloatField(default=0.0, blank=True, null=True)
    note = models.CharField(max_length=255, blank=True, null=True)  # New note field

    def __str__(self):
        return f"{self.employee.name} {self.employee.surname} - {self.date}"

class FreeDay(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    date = models.DateField()
    is_article_39 = models.BooleanField(default=False)
    is_byChoice = models.BooleanField(default=False)

    def __str__(self):
        return f"Free Day on {self.date} for {self.employee.name} ({'Article 39' if self.is_article_39 else 'Choice'})"
    
class Vacation(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    start_date = models.DateField()
    end_date = models.DateField()

    def __str__(self):
        return f"Vacation from {self.start_date} to {self.end_date} for {self.employee.name}"
    
class SickLeave(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    start_date = models.DateField()
    end_date = models.DateField()

    def __str__(self):
        return f"Sick leave from {self.start_date} to {self.end_date} for {self.employee.name}"
        
class FixedHourFund(models.Model):
    month = models.DateField()  # Use just year and month for tracking
    required_hours = models.IntegerField(help_text="Fixed number of hours for the month")

    def __str__(self):
        return f"{self.month.strftime('%B %Y')} - {self.required_hours} hours"

class Holiday(models.Model):
    date = models.DateField()
    description = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.date} - {self.description}"