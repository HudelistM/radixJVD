from django.contrib import admin
from django.urls import include,path
from scheduler import views
from django_browser_reload.urls import urlpatterns as reload_urls
from scheduler.views import schedule_view,api_schedule_data,download_schedule, radnici,download_sihterica,download_schedule_pdf,add_or_edit_employee,add_employee,delete_employee

urlpatterns = [
    path("__reload__/", include("django_browser_reload.urls")),
    path('admin/', admin.site.urls),
    path('', views.landingPage, name='landingPage'),  # Root URL
    path('accounts/', include('django.contrib.auth.urls')),
    path('radnici/', radnici, name='radnici'),
    #path('add_employee/', views.add_employee, name='add_employee'),
    path('add_or_edit_employee', views.add_or_edit_employee, name='add_or_edit_employee'),
    path('get_employee_data/<int:employee_id>/', views.get_employee_data, name='get_employee_data'),
    path('delete_employee/<int:employee_id>/', views.delete_employee, name='delete_employee'),
    path('register/', views.register, name='register'),
    path('schedule/', schedule_view, name='schedule_view'),
    path('update_schedule/', views.update_schedule, name='update_schedule'),
    path('api/schedule/', api_schedule_data, name='api_schedule_data'),
    path('download_schedule/', download_schedule, name='download_schedule'),
    path('download_sihterica/', download_sihterica, name='download_sihterica'),
    path('documents/', views.documents_view, name='documents_view'),
    path('update_overtime_hours/', views.update_overtime_hours, name='update_overtime_hours'),
    path('download_schedule_pdf/', download_schedule_pdf, name='download_schedule_pdf'),
    path('get_workday_data/', views.get_workday_data, name='get_workday_data'),
]
