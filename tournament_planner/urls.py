"""
URL configuration for tournament_planner project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.shortcuts import render
from django.conf import settings
from django.conf.urls.static import static
from tournaments.models import Tournament
import datetime

def home(request):
    upcoming = Tournament.objects.filter(date__gte=datetime.date.today()).order_by('date')[:3]
    recent = Tournament.objects.filter(date__lt=datetime.date.today()).order_by('-date')[:3]
    return render(request, 'home.html', {'upcoming': upcoming, 'recent': recent})

urlpatterns = [
    path('', home, name='home'),
    path('admin/', admin.site.urls),
    path('players/', include('players.urls')),
    path('tournaments/', include('tournaments.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
