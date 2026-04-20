from django.urls import path
from . import views

urlpatterns = [
    path('', views.tournament_list, name='tournament_list'),
    path('create/', views.tournament_create, name='tournament_create'),
    path('<int:pk>/', views.tournament_detail, name='tournament_detail'),
    path('<int:pk>/edit/', views.tournament_edit, name='tournament_edit'),
    path('<int:tournament_pk>/division/create/', views.division_create, name='division_create'),
    path('division/<int:pk>/teams/', views.division_update_teams, name='division_update_teams'),
    path('division/<int:pk>/delete/', views.division_delete, name='division_delete'),
    path('division/<int:pk>/generate/', views.division_generate_schedule, name='division_generate_schedule'),
    path('match/<int:pk>/result/', views.match_record_result, name='match_record_result'),
    path('match/<int:pk>/start/', views.match_start, name='match_start'),
    path('match/<int:pk>/walkover/', views.match_walkover, name='match_walkover'),
    path('<int:pk>/scoresheet/', views.tournament_scoresheet, name='tournament_scoresheet'),
    path('<int:pk>/program/print/', views.tournament_program_print, name='tournament_program_print'),
    path('division/<int:pk>/scoresheet/', views.division_scoresheet, name='division_scoresheet'),
    path('<int:pk>/schedule/', views.tournament_schedule, name='tournament_schedule'),
    path('<int:pk>/schedule/generate/', views.tournament_generate_time_schedule, name='tournament_generate_time_schedule'),
    path('<int:pk>/schedule/lock/', views.tournament_toggle_lock, name='tournament_toggle_lock'),
]
