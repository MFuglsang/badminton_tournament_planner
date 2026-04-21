import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tournament_planner.settings')
django.setup()

from tournaments.models import Match, Tournament
from datetime import timedelta

t = Tournament.objects.first()
print(f'Courts: {t.court_count}, break: {t.player_break_time} min, single: {t.single_match_duration}, double: {t.double_match_duration}')
print()

matches = Match.objects.filter(
    division__tournament=t
).exclude(match_number=None).select_related(
    'division','team1__player1','team1__player2','team2__player1','team2__player2'
).order_by('scheduled_time','match_number')

for m in matches:
    t1 = str(m.team1) if m.team1 else 'TBD'
    t2 = str(m.team2) if m.team2 else 'TBD'
    pks = [pk for pk in [
        m.team1.player1_id if m.team1 else None,
        getattr(m.team1, 'player2_id', None) if m.team1 else None,
        m.team2.player1_id if m.team2 else None,
        getattr(m.team2, 'player2_id', None) if m.team2 else None,
    ] if pk]
    sched = m.scheduled_time.strftime('%H:%M') if m.scheduled_time else 'N/A'
    phase = getattr(m, 'phase', '?')
    print(f'#{m.match_number} R{m.match_round} {phase} {m.division.name}: {t1} vs {t2} | players={pks} | {sched} court={m.court}')
