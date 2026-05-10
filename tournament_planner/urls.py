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
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from tournaments.models import Tournament
from tournaments.public_views import public_landing, public_tournament, public_schedule
import datetime

@login_required
def home(request):
    """Render dashboard with upcoming and recent tournaments."""
    upcoming = Tournament.objects.filter(owner=request.user, date__gte=datetime.date.today()).order_by('date')[:3]
    recent = Tournament.objects.filter(owner=request.user, date__lt=datetime.date.today()).order_by('-date')[:3]
    return render(request, 'home.html', {'upcoming': upcoming, 'recent': recent})

urlpatterns = [
    path('i18n/', include('django.conf.urls.i18n')),
    path('', public_landing, name='home'),
    path('dashboard/', home, name='admin_home'),
    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('admin/', admin.site.urls),
    path('players/', include('players.urls')),
    path('tournaments/', include('tournaments.urls')),
    # ── Public / anonymous viewer ──────────────────────────────────────────
    path('public/', public_landing, name='public_landing'),
    path('public/tournament/<int:pk>/', public_tournament, name='public_tournament'),
    path('public/tournament/<int:pk>/spilleplan/', public_schedule, name='public_schedule'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
