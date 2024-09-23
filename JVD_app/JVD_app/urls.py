from django.contrib import admin
from django.urls import include, path
from django_browser_reload.urls import urlpatterns as reload_urls
from scheduler import views
from django.contrib.auth import views as auth_views

# Corrected imports
from scheduler.views import radnici,landingPage, documents_view, schedule_view, api_schedule_data, update_overtime_hours, get_workday_data, update_schedule, delete_workday, playground, get_shift_type_details
from scheduler.views.worker_views import add_or_edit_employee, get_employee_data, delete_employee, radnik_profil, handle_overtime, handle_free_day,handle_vacation,handle_sick_leave, delete_vacation, delete_sick_leave
from scheduler.views.excel_views import download_schedule, download_sihterica, download_sihterica_ina
from scheduler.views.pdf_views import download_schedule_pdf,download_timesheet_pdf


urlpatterns = [
    path("__reload__/", include("django_browser_reload.urls")),
    path('admin/', admin.site.urls),
    path('accounts/login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('accounts/logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
    path('accounts/', include('django.contrib.auth.urls')),  # Includes built-in auth views like password reset
    #path('register/', views.register, name='register'),
    path('', views.landingPage, name='landingPage'),  # Root URL
    
    path('playground/', playground, name='playground'),

    # Worker views
    path('radnici/', radnici, name='radnici'),
    path('add_or_edit_employee', add_or_edit_employee, name='add_or_edit_employee'),
    path('get_employee_data/<int:employee_id>/', get_employee_data, name='get_employee_data'),
    path('delete_employee/<int:employee_id>/', delete_employee, name='delete_employee'),
    path('radnik_profil/<int:employee_id>/', radnik_profil, name='radnik_profil'),
    path('handle_overtime/<int:employee_id>/', handle_overtime, name='handle_overtime'),
    path('handle_free_day/<int:employee_id>/', handle_free_day, name='handle_free_day'),
    path('handle_vacation/<int:employee_id>/', handle_vacation, name='handle_vacation'),
    path('handle_sick_leave/<int:employee_id>/', handle_sick_leave, name='handle_sick_leave'),
    path('delete_vacation/<int:vacation_id>/', delete_vacation, name='delete_vacation'),
    path('delete_sick_leave/<int:sick_leave_id>/', delete_sick_leave, name='delete_sick_leave'),


    # Schedule views
    path('schedule/', schedule_view, name='schedule_view'),
    path('update_schedule/', update_schedule, name='update_schedule'),
    path('api/schedule/', api_schedule_data, name='api_schedule_data'),
    path('update_overtime_hours/', update_overtime_hours, name='update_overtime_hours'),
    path('get_workday_data/', get_workday_data, name='get_workday_data'),
    path('delete_workday/', delete_workday, name='delete_workday'),
    path('get_shift_type_details/', views.get_shift_type_details, name='get_shift_type_details'),

    # Document views
    path('documents/', documents_view, name='documents_view'), 
    path('download_sihterica/', download_sihterica, name='download_sihterica'),
    path('download_schedule/', download_schedule, name='download_schedule'),
    path('download_schedule_pdf/', download_schedule_pdf, name='download_schedule_pdf'),
    path('download_timesheet_pdf/', download_timesheet_pdf, name='download_timesheet_pdf'),
    path('download_sihterica_ina/', download_sihterica_ina, name='download_sihterica_ina'),
]
