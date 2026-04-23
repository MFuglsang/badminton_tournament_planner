from django.urls import path
from . import views

urlpatterns = [
    path('', views.player_list, name='player_list'),
    path('add/', views.player_add, name='player_add'),
    path('<int:pk>/edit/', views.player_edit, name='player_edit'),
    path('<int:pk>/delete/', views.player_delete, name='player_delete'),
    path('<int:pk>/schedule/', views.player_schedule_print, name='player_schedule_print'),
    path('<int:pk>/clear-rest/', views.player_clear_rest, name='player_clear_rest'),
    path('teams/', views.team_list, name='team_list'),
    path('teams/add/', views.team_add, name='team_add'),
    path('teams/<int:pk>/edit/', views.team_edit, name='team_edit'),
    path('teams/<int:pk>/delete/', views.team_delete, name='team_delete'),
    path('categories/', views.division_category_list, name='division_category_list'),
    path('categories/<int:pk>/delete/', views.division_category_delete, name='division_category_delete'),
    path('categories/seed-defaults/', views.division_category_seed_defaults, name='division_category_seed_defaults'),
]
