from django.urls import path
from . import views

urlpatterns = [
    path('', views.player_list, name='player_list'),
    path('add/', views.player_add, name='player_add'),
    path('<int:pk>/edit/', views.player_edit, name='player_edit'),
    path('<int:pk>/delete/', views.player_delete, name='player_delete'),
    path('<int:pk>/schedule/', views.player_schedule_print, name='player_schedule_print'),
    path('teams/', views.team_list, name='team_list'),
    path('teams/add/', views.team_add, name='team_add'),
    path('teams/<int:pk>/edit/', views.team_edit, name='team_edit'),
    path('teams/<int:pk>/delete/', views.team_delete, name='team_delete'),
]