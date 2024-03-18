from django.contrib import admin
from .models import ShiftType, Employee, WorkDay, ScheduleEntry

# Register your models here.
admin.site.register(ShiftType)
admin.site.register(Employee)
admin.site.register(WorkDay)
@admin.register(ScheduleEntry)
class ScheduleEntryAdmin(admin.ModelAdmin):
    list_display = ('date', 'shift_type', 'list_employees')
    
    def list_employees(self, obj):
        return ", ".join([e.name for e in obj.employees.all()])

    list_employees.short_description = 'Employees'
