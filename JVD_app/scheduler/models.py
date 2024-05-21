from django.db import models

class Employee(models.Model):
    name = models.CharField(max_length=100)
    surname = models.CharField(max_length=100)
    role = models.CharField(max_length=100)
    group = models.CharField(max_length=100)
    
    def __str__(self):
    # Customize this to display information that helps identify the employee
        return f"{self.name} {self.surname} ({self.role})"

class WorkDay(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    date = models.DateField()
    day_hours = models.FloatField(default=0)
    night_hours = models.FloatField(default=0)
    holiday_hours = models.FloatField(default=0, blank=True, null=True)
    vacation_hours = models.FloatField(default=0, blank=True, null=True)
    sick_leave_hours = models.FloatField(default=0, blank=True, null=True)
    saturday_hours = models.FloatField(default=0, blank=True, null=True)
    sunday_hours = models.FloatField(default=0, blank=True, null=True)
    on_call_hours = models.FloatField(default=0, blank=True, null=True)
    overtime_hours = models.FloatField(default=0, blank=True, null=True)
    
    def __str__(self):
        return f"{self.employee.name} {self.employee.surname} - {self.date}"

    
class ShiftType(models.Model):
    SHIFT_CATEGORIES = [
        ('1.smjena', '1.Smjena'),
        ('1.smjena priprema', '1.Smjena Priprema'),
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

    def __str__(self):
        return self.name


class ScheduleEntry(models.Model):
    date = models.DateField()
    employees = models.ManyToManyField(Employee, related_name='schedule_entries')
    shift_type = models.ForeignKey(ShiftType, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('date', 'shift_type')

class EmployeeShiftCounter(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='shift_counters')
    week_start_date = models.DateField()
    shift_count = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ('employee', 'week_start_date')