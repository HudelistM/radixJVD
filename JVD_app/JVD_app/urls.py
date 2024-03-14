from django.contrib import admin
from django.urls import include,path
from scheduler import views
from django_browser_reload.urls import urlpatterns as reload_urls
from scheduler.views import schedule_view

urlpatterns = [
    path("__reload__/", include("django_browser_reload.urls")),
    path('admin/', admin.site.urls),
    path('', views.landingPage, name='landingPage'),  # Root URL
    path('accounts/', include('django.contrib.auth.urls')),
    path('register/', views.register, name='register'),
    path('schedule/', schedule_view, name='schedule_view'),
    #path('Radnici',views.radnici, name='Radnici'), #
    #path('Dokumenti',views.dokumenti, name='Dokumenti'), #
    #path('Raspored',views.raspored, name='Raspored') #
]
