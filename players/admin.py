from django.contrib import admin
from .models import Player, Team, DivisionCategory

@admin.register(DivisionCategory)
class DivisionCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'sort_order', 'owner')
    list_filter = ('owner',)
    search_fields = ('name',)

@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display = ('name', 'gender', 'age', 'division')
    list_filter = ('gender', 'division')
    search_fields = ('name',)

@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ('name', 'player1', 'player2')
    search_fields = ('name',)
