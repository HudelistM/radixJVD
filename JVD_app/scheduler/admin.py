from django.contrib import admin
from .models import ShiftType, Employee, WorkDay, ScheduleEntry

# Register your models here.
admin.site.register(ShiftType)
admin.site.register(Employee)
admin.site.register(WorkDay)
admin.site.register(ScheduleEntry)
