from django.db import models

class Employee(models.Model):
    name = models.CharField(max_length=100)
    surname = models.CharField(max_length=100)
    role = models.CharField(max_length=100)
    group = models.CharField(max_length=100)

class WorkDay(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    date = models.DateField()
    day_hours = models.FloatField(default=0)
    night_hours = models.FloatField(default=0)
    holiday_hours = models.FloatField(default=0, blank=True, null=True)
    vacation_hours = models.FloatField(default=0, blank=True, null=True)
    sick_leave_hours = models.FloatField(default=0, blank=True, null=True)
    night_shift_hours = models.FloatField(default=0, blank=True, null=True)
    saturday_hours = models.FloatField(default=0, blank=True, null=True)
    sunday_hours = models.FloatField(default=0, blank=True, null=True)
    free_days = models.IntegerField(default=0, blank=True, null=True)
    extra_hours = models.FloatField(default=0, blank=True, null=True)  
    turnus = models.CharField(max_length=100, blank=True, null=True)  
    vacation_days = models.IntegerField(default=0, blank=True, null=True)


class ScheduleEntry(models.Model):
    date = models.DateField()
    employees = models.ManyToManyField(Employee, related_name='schedule_entries')
    shift_type = models.ForeignKey(ShiftType, on_delete=models.CASCADE)


    class Meta:
        unique_together = ('date', 'shift_type')

class ShiftType(models.Model):
    name = models.CharField(max_length=100)
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name
