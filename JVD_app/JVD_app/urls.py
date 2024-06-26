from django.contrib import admin
from django.urls import include, path
from django_browser_reload.urls import urlpatterns as reload_urls
from scheduler import views

# Corrected imports
from scheduler.views import radnici,landingPage, register, documents_view, schedule_view, api_schedule_data, update_overtime_hours, get_workday_data, update_schedule, delete_workday
from scheduler.views.worker_views import add_or_edit_employee, get_employee_data, delete_employee, radnik_profil
from scheduler.views.excel_views import download_schedule, download_sihterica
from scheduler.views.pdf_views import download_schedule_pdf,download_timesheet_pdf


urlpatterns = [
    path("__reload__/", include("django_browser_reload.urls")),
    path('admin/', admin.site.urls),
    path('', landingPage, name='landingPage'),  # Root URL
    path('accounts/', include('django.contrib.auth.urls')),

    # Worker views
    path('radnici/', radnici, name='radnici'),
    path('add_or_edit_employee', add_or_edit_employee, name='add_or_edit_employee'),
    path('get_employee_data/<int:employee_id>/', get_employee_data, name='get_employee_data'),
    path('delete_employee/<int:employee_id>/', delete_employee, name='delete_employee'),
    path('radnik_profil/<int:employee_id>/', radnik_profil, name='radnik_profil'),

    # Other views
    path('register/', register, name='register'),

    # Schedule views
    path('schedule/', schedule_view, name='schedule_view'),
    path('update_schedule/', update_schedule, name='update_schedule'),
    path('api/schedule/', api_schedule_data, name='api_schedule_data'),
    path('update_overtime_hours/', update_overtime_hours, name='update_overtime_hours'),
    path('get_workday_data/', get_workday_data, name='get_workday_data'),
    path('delete_workday/', delete_workday, name='delete_workday'),

    # Document views
    path('documents/', documents_view, name='documents_view'), 
    path('download_sihterica/', download_sihterica, name='download_sihterica'),
    path('download_schedule/', download_schedule, name='download_schedule'),
    path('download_schedule_pdf/', download_schedule_pdf, name='download_schedule_pdf'),
    path('download_timesheet_pdf/', download_timesheet_pdf, name='download_timesheet_pdf'),
]
