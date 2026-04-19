from django.contrib import admin
from .models import Tournament, Division, Match

@admin.register(Tournament)
class TournamentAdmin(admin.ModelAdmin):
    list_display = ('name', 'tournament_type', 'date', 'division_model', 'scoring_model')
    list_filter = ('tournament_type', 'division_model', 'scoring_model')
    search_fields = ('name',)

@admin.register(Division)
class DivisionAdmin(admin.ModelAdmin):
    list_display = ('name', 'tournament')
    list_filter = ('tournament',)
    search_fields = ('name',)

@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = ('division', 'team1', 'team2', 'scheduled_time', 'score')
    list_filter = ('division',)
    search_fields = ('team1__name', 'team2__name')
