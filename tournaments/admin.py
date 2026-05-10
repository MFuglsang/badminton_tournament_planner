from django.contrib import admin
from .models import Tournament, Division, Match, UserProfile

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'language')
    list_editable = ('language',)

@admin.register(Tournament)
class TournamentAdmin(admin.ModelAdmin):
    list_display = ('name', 'date', 'division_model', 'scoring_model')
    list_filter = ('division_model', 'scoring_model')
    search_fields = ('name',)

@admin.register(Division)
class DivisionAdmin(admin.ModelAdmin):
    list_display = ('name', 'tournament', 'team_count')
    list_filter = ('tournament',)
    search_fields = ('name',)
    filter_horizontal = ('teams',)

    def team_count(self, obj):
        return obj.teams.count()
    team_count.short_description = 'Hold'

@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = ('division', 'match_round', 'team1', 'team2', 'score', 'winner', 'status')
    list_filter = ('division', 'status')
    search_fields = ('team1__name', 'team2__name')
    list_editable = ('score', 'winner', 'status')

