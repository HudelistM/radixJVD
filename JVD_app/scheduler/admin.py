from django.contrib import admin
from .models import ShiftType, Employee, WorkDay, FixedHourFund, Holiday, ExcessHours,FreeDay, SickLeave, Vacation

# Register your models here.
admin.site.register(ShiftType)
admin.site.register(Employee)
admin.site.register(WorkDay)
admin.site.register(FreeDay)
admin.site.register(FixedHourFund)
admin.site.register(Holiday)
admin.site.register(ExcessHours)
admin.site.register(SickLeave)
admin.site.register(Vacation)


