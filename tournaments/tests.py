import datetime
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from players.models import Player, Team
from .models import Tournament, Division, Match, DivisionSeed
from .forms import MatchResultForm, _parse_score as _form_parse_score, _validate_set
from .scheduler import generate_round_robin, generate_bracket, generate_schedule, advance_bracket, get_bracket_data
from .standings import compute_standings, compute_group_standings, _parse_score, STANDINGS_CONFIG

User = get_user_model()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_user(username='testclub', password='testpass123'):
    return User.objects.create_user(username=username, password=password)


def make_player(name="Alice", division="A", owner=None):
    return Player.objects.create(name=name, age=20, division=division, owner=owner)


def make_team(name=None, r1=1, r2=2):
    p1 = make_player(f"P{r1}")
    p2 = make_player(f"P{r2}")
    team = Team.objects.create(player1=p1, player2=p2)
    if name:
        team.name = name
        team.save()
    return team


def make_tournament(owner=None):
    return Tournament.objects.create(
        name="Test Tournament",
        date=datetime.date.today(),
        division_model="mixed",
        scoring_model="best_of_3_21",
        owner=owner,
    )


def make_division(tournament=None, name="A Række", discipline='double', tournament_type='group'):
    t = tournament or make_tournament()
    return Division.objects.create(tournament=t, name=name, discipline=discipline, tournament_type=tournament_type)


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------

class TournamentModelTest(TestCase):
    def test_str_includes_name(self):
        t = make_tournament()
        self.assertIn("Test Tournament", str(t))

    def test_tournament_types(self):
        for ttype in ["tree", "group", "playoff"]:
            d = make_division(name=f"D-{ttype}", tournament_type=ttype)
            self.assertEqual(d.tournament_type, ttype)


class DivisionModelTest(TestCase):
    def test_str_includes_division_and_tournament_name(self):
        d = make_division()
        self.assertIn("A Række", str(d))
        self.assertIn("Test Tournament", str(d))

    def test_teams_can_be_added(self):
        d = make_division()
        t1 = make_team(r1=1, r2=2)
        t2 = make_team(r1=3, r2=4)
        d.teams.add(t1, t2)
        self.assertEqual(d.teams.count(), 2)


class MatchModelTest(TestCase):
    def setUp(self):
        self.division = make_division()
        self.t1 = make_team(r1=1, r2=2)
        self.t2 = make_team(r1=3, r2=4)

    def test_str_includes_round_and_teams(self):
        m = Match.objects.create(
            division=self.division, team1=self.t1, team2=self.t2, match_round=2
        )
        self.assertIn("R2", str(m))
        self.assertIn(self.t1.name, str(m))

    def test_default_status_is_pending(self):
        m = Match.objects.create(
            division=self.division, team1=self.t1, team2=self.t2
        )
        self.assertEqual(m.status, "pending")


# ---------------------------------------------------------------------------
# Scheduler tests
# ---------------------------------------------------------------------------

class RoundRobinSchedulerTest(TestCase):
    def setUp(self):
        self.division = make_division()
        self.teams = [make_team(r1=i*2+1, r2=i*2+2) for i in range(4)]
        self.division.teams.set(self.teams)

    def test_generates_correct_number_of_matches(self):
        # With n teams, round-robin produces n*(n-1)/2 matches
        n = len(self.teams)
        matches = generate_round_robin(self.division)
        self.assertEqual(len(matches), n * (n - 1) // 2)

    def test_all_matches_are_pending(self):
        matches = generate_round_robin(self.division)
        for m in matches:
            self.assertEqual(m.status, "pending")

    def test_regenerate_removes_old_pending_matches(self):
        generate_round_robin(self.division)
        generate_round_robin(self.division)
        n = len(self.teams)
        self.assertEqual(
            Match.objects.filter(division=self.division).count(),
            n * (n - 1) // 2,
        )

    def test_no_matches_with_fewer_than_two_teams(self):
        division = make_division(name="Empty")
        matches = generate_round_robin(division)
        self.assertEqual(matches, [])


class BracketSchedulerTest(TestCase):
    def setUp(self):
        self.division = make_division(tournament_type='tree')
        self.teams = [make_team(r1=i*2+1, r2=i*2+2) for i in range(4)]
        self.division.teams.set(self.teams)

    def test_generates_all_rounds(self):
        # 4 teams → round 1: 2 matches, round 2: 1 placeholder = 3 total
        matches = generate_bracket(self.division)
        self.assertEqual(len(matches), 3)

    def test_round1_matches_count(self):
        matches = generate_bracket(self.division)
        round1 = [m for m in matches if m.match_round == 1]
        self.assertEqual(len(round1), 2)

    def test_placeholder_created_for_final(self):
        matches = generate_bracket(self.division)
        placeholders = [m for m in matches if m.team1 is None]
        self.assertEqual(len(placeholders), 1)
        self.assertEqual(placeholders[0].match_round, 2)
        self.assertIsNotNone(placeholders[0].bracket_label)

    def test_no_matches_with_fewer_than_two_teams(self):
        division = make_division(name="Empty2", tournament_type='tree')
        matches = generate_bracket(division)
        self.assertEqual(matches, [])

    def test_bye_given_when_odd_team_count(self):
        # 3 teams → bracket_size=4, 1 bye + 1 real in round 1, 1 placeholder in round 2
        division = make_division(name="Odd", tournament_type='tree')
        teams = [make_team(r1=i*2+1, r2=i*2+2) for i in range(3)]
        division.teams.set(teams)
        matches = generate_bracket(division)
        # round1: bye + real; round2: placeholder (bye already filled team1)
        round1 = [m for m in matches if m.match_round == 1]
        bye_matches = [m for m in round1 if m.team2 is None and m.status == 'completed']
        real_matches = [m for m in round1 if m.team2 is not None]
        self.assertEqual(len(bye_matches), 1)
        self.assertEqual(len(real_matches), 1)
        self.assertIsNotNone(bye_matches[0].winner)
        # Placeholder in round 2 should have team1 filled (bye advanced)
        final = next(m for m in matches if m.match_round == 2)
        final.refresh_from_db()
        self.assertIsNotNone(final.team1)

    def test_bracket_slot_set_on_round1(self):
        matches = generate_bracket(self.division)
        round1 = [m for m in matches if m.match_round == 1]
        slots = sorted(m.bracket_slot for m in round1)
        self.assertEqual(slots, [1, 2])


class AdvanceBracketTest(TestCase):
    def setUp(self):
        self.division = make_division(tournament_type='tree')
        self.teams = [make_team(r1=i*2+1, r2=i*2+2) for i in range(4)]
        self.division.teams.set(self.teams)
        generate_bracket(self.division)

    def test_no_advance_when_other_match_not_done(self):
        # Complete only match in bracket_slot=1, round 1
        m = Match.objects.get(division=self.division, match_round=1, bracket_slot=1)
        m.winner = m.team1
        m.status = 'completed'
        m.save()
        advance_bracket(m)
        # Round 2 placeholder should still have team2=None (only team1 is filled)
        final = Match.objects.get(division=self.division, match_round=2)
        self.assertIsNone(final.team2)
        self.assertIsNotNone(final.bracket_label)  # still a placeholder

    def test_advance_fills_both_teams(self):
        for match in Match.objects.filter(division=self.division, match_round=1):
            match.winner = match.team1
            match.status = 'completed'
            match.save()
            advance_bracket(match)
        # Final should have both teams filled and bracket_label cleared
        final = Match.objects.get(division=self.division, match_round=2)
        final.refresh_from_db()
        self.assertIsNotNone(final.team1)
        self.assertIsNotNone(final.team2)
        self.assertIsNone(final.bracket_label)


class BracketDataTest(TestCase):
    def test_returns_none_when_no_matches(self):
        division = make_division(tournament_type='tree')
        self.assertIsNone(get_bracket_data(division))

    def test_returns_correct_rounds(self):
        division = make_division(tournament_type='tree')
        teams = [make_team(r1=i*2+1, r2=i*2+2) for i in range(4)]
        division.teams.set(teams)
        generate_bracket(division)
        data = get_bracket_data(division)
        self.assertIsNotNone(data)
        self.assertEqual(data['total_rounds'], 2)
        self.assertEqual(len(data['rounds']), 2)
        self.assertEqual(data['rounds'][0]['label'], 'Semifinale')
        self.assertEqual(data['rounds'][1]['label'], 'Finale')


class GenerateScheduleRouterTest(TestCase):
    def test_group_uses_round_robin(self):
        division = make_division(tournament_type='group')
        teams = [make_team(r1=i*2+1, r2=i*2+2) for i in range(3)]
        division.teams.set(teams)
        matches = generate_schedule(division)
        self.assertEqual(len(matches), 3)  # 3*(3-1)/2 = 3

    def test_tree_uses_bracket(self):
        division = make_division(tournament_type='tree')
        teams = [make_team(r1=i*2+1, r2=i*2+2) for i in range(4)]
        division.teams.set(teams)
        matches = generate_schedule(division)
        # 4 teams: 2 round-1 matches + 1 round-2 placeholder
        self.assertEqual(len(matches), 3)
        round1 = [m for m in matches if m.match_round == 1 and m.team2 is not None]
        self.assertEqual(len(round1), 2)

    def test_playoff_uses_round_robin(self):
        division = make_division(tournament_type='playoff')
        division.group_count = 1
        division.advance_count = 2
        division.save()
        teams = [make_team(r1=i*2+1, r2=i*2+2) for i in range(3)]
        division.teams.set(teams)
        matches = generate_schedule(division)
        # 3 teams in 1 group: 3 group matches + 2 bracket slots (final)
        group_matches = [m for m in matches if m.phase == 'group']
        self.assertEqual(len(group_matches), 3)


class TournamentCRUDViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = make_user()
        self.client.force_login(self.user)

    def test_tournament_create_get_returns_200(self):
        response = self.client.get(reverse("tournament_create"))
        self.assertEqual(response.status_code, 200)

    def test_tournament_create_post_creates_tournament(self):
        response = self.client.post(reverse("tournament_create"), {
            'name': 'Ny Turnering',
            'date': '2026-06-01',
            'division_model': 'mixed',
            'scoring_model': 'best_of_3_21',
            'court_count': 6,
            'start_time': '09:00',
            'single_match_duration': 30,
            'double_match_duration': 40,
            'player_break_time': 15,
        })
        tournament = Tournament.objects.get(name='Ny Turnering')
        self.assertRedirects(response, reverse("tournament_detail", args=[tournament.pk]))
        self.assertEqual(tournament.court_count, 6)
        self.assertIsNotNone(tournament.start_time)

    def test_tournament_create_invalid_stays_on_page(self):
        response = self.client.post(reverse("tournament_create"), {'name': ''})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Tournament.objects.filter(name='').exists())

    def test_tournament_edit_get_returns_200(self):
        t = make_tournament(owner=self.user)
        response = self.client.get(reverse("tournament_edit", args=[t.pk]))
        self.assertEqual(response.status_code, 200)

    def test_tournament_edit_post_updates_fields(self):
        t = make_tournament(owner=self.user)
        response = self.client.post(reverse("tournament_edit", args=[t.pk]), {
            'name': 'Opdateret',
            'date': '2026-07-01',
            'division_model': 'mixed',
            'scoring_model': 'best_of_3_21',
            'court_count': 8,
            'start_time': '10:00',
            'single_match_duration': 30,
            'double_match_duration': 40,
            'player_break_time': 15,
        })
        self.assertRedirects(response, reverse("tournament_detail", args=[t.pk]))
        t.refresh_from_db()
        self.assertEqual(t.name, 'Opdateret')
        self.assertEqual(t.court_count, 8)

    def test_tournament_edit_404_for_nonexistent(self):
        response = self.client.get(reverse("tournament_edit", args=[9999]))
        self.assertEqual(response.status_code, 404)


# ---------------------------------------------------------------------------
# View tests
# ---------------------------------------------------------------------------

class TournamentViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = make_user(username='viewclub')
        self.client.force_login(self.user)
        self.tournament = make_tournament(owner=self.user)
        self.division = make_division(tournament=self.tournament)
        self.t1 = make_team(r1=1, r2=2)
        self.t2 = make_team(r1=3, r2=4)
        self.division.teams.add(self.t1, self.t2)

    def test_tournament_list_returns_200(self):
        response = self.client.get(reverse("tournament_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.tournament.name)

    def test_tournament_detail_returns_200(self):
        response = self.client.get(reverse("tournament_detail", args=[self.tournament.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.division.name)
        self.assertIn('division_data', response.context)

    def test_tournament_detail_404_for_nonexistent(self):
        response = self.client.get(reverse("tournament_detail", args=[9999]))
        self.assertEqual(response.status_code, 404)

    def test_tournament_detail_has_division_form(self):
        response = self.client.get(reverse("tournament_detail", args=[self.tournament.pk]))
        self.assertIn('division_form', response.context)

    def test_division_create_post_creates_division(self):
        response = self.client.post(
            reverse("division_create", args=[self.tournament.pk]),
            {'name': 'Ny Division', 'discipline': 'single', 'tournament_type': 'group'},
        )
        self.assertRedirects(response, reverse("tournament_detail", args=[self.tournament.pk]))
        self.assertTrue(self.tournament.divisions.filter(name='Ny Division').exists())

    def test_division_create_invalid_stays_on_page(self):
        response = self.client.post(
            reverse("division_create", args=[self.tournament.pk]),
            {'name': ''},
        )
        self.assertRedirects(response, reverse("tournament_detail", args=[self.tournament.pk]))
        # Invalid form redirects but does not create
        self.assertFalse(self.tournament.divisions.filter(name='').exists())

    def test_division_update_teams(self):
        # division default discipline is 'double', so POST field is 'pairs'
        p5 = make_player("P5", owner=self.user)
        p6 = make_player("P6", owner=self.user)
        t3 = Team.objects.create(player1=p5, player2=p6)
        response = self.client.post(
            reverse("division_update_teams", args=[self.division.pk]),
            {'pairs': [t3.pk]},
        )
        self.assertRedirects(response, reverse("tournament_detail", args=[self.tournament.pk]))
        self.division.refresh_from_db()
        self.assertIn(t3, self.division.teams.all())
        # t1 and t2 are replaced
        self.assertNotIn(self.t1, self.division.teams.all())

    def test_division_update_teams_clear_all(self):
        response = self.client.post(
            reverse("division_update_teams", args=[self.division.pk]),
            {},  # no pairs selected → clears all
        )
        self.assertRedirects(response, reverse("tournament_detail", args=[self.tournament.pk]))
        self.assertEqual(self.division.teams.count(), 0)

    def test_division_update_single_auto_creates_teams(self):
        single_div = Division.objects.create(
            tournament=self.tournament, name="Herresingle", discipline='single'
        )
        p1 = make_player("Solo1", owner=self.user)
        p2 = make_player("Solo2", owner=self.user)
        response = self.client.post(
            reverse("division_update_teams", args=[single_div.pk]),
            {'players': [p1.pk, p2.pk]},
        )
        self.assertRedirects(response, reverse("tournament_detail", args=[self.tournament.pk]))
        single_div.refresh_from_db()
        self.assertEqual(single_div.teams.count(), 2)
        names = list(single_div.teams.values_list('name', flat=True))
        self.assertIn(p1.name, names)
        self.assertIn(p2.name, names)

    def test_division_detail_has_participants_form(self):
        response = self.client.get(reverse("tournament_detail", args=[self.tournament.pk]))
        dd = response.context['division_data'][0]
        self.assertIn('participants_form', dd)

    def test_division_delete_get_shows_confirm(self):
        response = self.client.get(reverse("division_delete", args=[self.division.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.division.name)

    def test_division_delete_post_removes_division(self):
        div_pk = self.division.pk
        response = self.client.post(reverse("division_delete", args=[div_pk]))
        self.assertRedirects(response, reverse("tournament_detail", args=[self.tournament.pk]))
        self.assertFalse(Division.objects.filter(pk=div_pk).exists())

    def test_division_delete_404_for_nonexistent(self):
        response = self.client.get(reverse("division_delete", args=[9999]))
        self.assertEqual(response.status_code, 404)

    def test_generate_schedule_creates_matches(self):
        response = self.client.post(
            reverse("division_generate_schedule", args=[self.division.pk])
        )
        self.assertRedirects(response, reverse("tournament_detail", args=[self.tournament.pk]))
        self.assertEqual(Match.objects.filter(division=self.division).count(), 1)

    def test_generate_schedule_assigns_match_numbers(self):
        self.client.post(reverse("division_generate_schedule", args=[self.division.pk]))
        match = Match.objects.filter(division=self.division).first()
        self.assertIsNotNone(match.match_number)
        self.assertGreater(match.match_number, 0)

    def test_generate_schedule_numbers_are_sequential_across_divisions(self):
        # Create a second division and generate schedules for both
        div2 = Division.objects.create(
            tournament=self.tournament, name="Division B", discipline='double'
        )
        t3 = make_team(r1=5, r2=6)
        t4 = make_team(r1=7, r2=8)
        div2.teams.add(t3, t4)
        self.client.post(reverse("division_generate_schedule", args=[self.division.pk]))
        self.client.post(reverse("division_generate_schedule", args=[div2.pk]))
        all_numbers = sorted(
            Match.objects.filter(division__tournament=self.tournament)
            .exclude(match_number=None)
            .values_list('match_number', flat=True)
        )
        self.assertEqual(all_numbers, list(range(1, len(all_numbers) + 1)))

    def test_scoresheet_view_returns_200(self):
        self.client.post(reverse("division_generate_schedule", args=[self.division.pk]))
        response = self.client.get(reverse("tournament_scoresheet", args=[self.tournament.pk]))
        self.assertEqual(response.status_code, 200)

    def test_scoresheet_contains_match_number(self):
        self.client.post(reverse("division_generate_schedule", args=[self.division.pk]))
        match = Match.objects.filter(division=self.division).first()
        response = self.client.get(reverse("tournament_scoresheet", args=[self.tournament.pk]))
        self.assertContains(response, f'#{match.match_number}')

    def test_scoresheet_404_for_nonexistent(self):
        response = self.client.get(reverse("tournament_scoresheet", args=[9999]))
        self.assertEqual(response.status_code, 404)

    def test_schedule_view_returns_200(self):
        response = self.client.get(reverse("tournament_schedule", args=[self.tournament.pk]))
        self.assertEqual(response.status_code, 200)

    def test_schedule_generate_without_start_time_shows_warning(self):
        # tournament from make_tournament has no start_time
        response = self.client.post(
            reverse("tournament_generate_time_schedule", args=[self.tournament.pk])
        )
        self.assertRedirects(response, reverse("tournament_schedule", args=[self.tournament.pk]))

    def test_schedule_generate_assigns_times(self):
        import datetime as dt
        self.tournament.start_time = dt.time(9, 0)
        self.tournament.court_count = 2
        self.tournament.save()
        # generate match programme first
        self.client.post(reverse("division_generate_schedule", args=[self.division.pk]))
        response = self.client.post(
            reverse("tournament_generate_time_schedule", args=[self.tournament.pk])
        )
        self.assertRedirects(response, reverse("tournament_schedule", args=[self.tournament.pk]))
        match = Match.objects.filter(division=self.division).first()
        self.assertIsNotNone(match.scheduled_time)
        self.assertIsNotNone(match.court)

    def test_standings_appear_after_completed_match(self):
        Match.objects.create(
            division=self.division, team1=self.t1, team2=self.t2,
            status='completed', winner=self.t1, score='21-15'
        )
        response = self.client.get(reverse("tournament_detail", args=[self.tournament.pk]))
        self.assertEqual(response.status_code, 200)
        dd = response.context['division_data'][0]
        standings = dd['standings']
        self.assertEqual(standings[0]['team'], self.t1)
        self.assertEqual(standings[0]['points'], 2)
        self.assertEqual(standings[1]['points'], 0)


class StandingsTest(TestCase):
    """Unit tests for the standings / tiebreaker engine."""

    def setUp(self):
        self.division = make_division()
        self.t1 = make_team(r1=1, r2=2)
        self.t2 = make_team(r1=3, r2=4)
        self.t3 = make_team(r1=5, r2=6)
        self.division.teams.add(self.t1, self.t2, self.t3)

    # ── Config ────────────────────────────────────────────────────────────
    def test_config_win_points_is_2(self):
        self.assertEqual(STANDINGS_CONFIG['win_points'], 2)

    def test_config_loss_points_is_0(self):
        self.assertEqual(STANDINGS_CONFIG['loss_points'], 0)

    def test_config_tiebreakers_order(self):
        self.assertEqual(STANDINGS_CONFIG['tiebreakers'], ['head_to_head', 'points_scored'])

    # ── Score parsing ──────────────────────────────────────────────────────
    def test_parse_score_single_set(self):
        self.assertEqual(_parse_score('21-15'), (21, 15))

    def test_parse_score_three_sets(self):
        self.assertEqual(_parse_score('21-15, 18-21, 21-18'), (60, 54))

    def test_parse_score_empty(self):
        self.assertEqual(_parse_score(''), (0, 0))

    def test_parse_score_none(self):
        self.assertEqual(_parse_score(None), (0, 0))

    # ── Basic standings ────────────────────────────────────────────────────
    def test_winner_ranks_first(self):
        Match.objects.create(
            division=self.division, team1=self.t1, team2=self.t2,
            status='completed', winner=self.t2, score='21-15'
        )
        rows = compute_standings(self.division)
        self.assertEqual(rows[0]['team'], self.t2)
        self.assertEqual(rows[0]['points'], 2)

    def test_score_for_and_against_tallied(self):
        Match.objects.create(
            division=self.division, team1=self.t1, team2=self.t2,
            status='completed', winner=self.t1, score='21-15, 21-10'
        )
        rows = compute_standings(self.division)
        r1 = next(r for r in rows if r['team'] == self.t1)
        r2 = next(r for r in rows if r['team'] == self.t2)
        self.assertEqual(r1['score_for'], 42)
        self.assertEqual(r1['score_against'], 25)
        self.assertEqual(r2['score_for'], 25)
        self.assertEqual(r2['score_against'], 42)

    # ── Head-to-head tiebreaker ────────────────────────────────────────────
    def test_head_to_head_breaks_points_tie(self):
        # t1 beats t3, t2 beats t3, t1 beats t2 → t1 > t2 > t3
        Match.objects.create(division=self.division, team1=self.t1, team2=self.t3,
                              status='completed', winner=self.t1, score='21-10')
        Match.objects.create(division=self.division, team1=self.t2, team2=self.t3,
                              status='completed', winner=self.t2, score='21-10')
        Match.objects.create(division=self.division, team1=self.t1, team2=self.t2,
                              status='completed', winner=self.t1, score='21-10')
        rows = compute_standings(self.division)
        self.assertEqual(rows[0]['team'], self.t1)
        self.assertEqual(rows[1]['team'], self.t2)
        self.assertEqual(rows[2]['team'], self.t3)

    # ── Points-scored tiebreaker ───────────────────────────────────────────
    def test_points_scored_breaks_remaining_tie(self):
        # t1 and t2 both beat t3; mutual match not played → pure points tie
        # t1 beat t3 with better net score → ranks first
        Match.objects.create(division=self.division, team1=self.t1, team2=self.t3,
                              status='completed', winner=self.t1, score='21-5')
        Match.objects.create(division=self.division, team1=self.t2, team2=self.t3,
                              status='completed', winner=self.t2, score='21-19')
        rows = compute_standings(self.division)
        self.assertEqual(rows[0]['team'], self.t1)  # net +16 > net +2
        self.assertEqual(rows[1]['team'], self.t2)


class MatchResultViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = make_user(username='resultclub')
        self.client.force_login(self.user)
        self.tournament = make_tournament(owner=self.user)
        self.division = make_division(tournament=self.tournament)
        self.t1 = make_team(r1=1, r2=2)
        self.t2 = make_team(r1=3, r2=4)
        self.match = Match.objects.create(
            division=self.division, team1=self.t1, team2=self.t2
        )

    def test_match_result_get_returns_200(self):
        response = self.client.get(reverse("match_record_result", args=[self.match.pk]))
        self.assertEqual(response.status_code, 200)

    def test_match_result_post_records_result(self):
        data = {
            "score": "21-15, 21-10",
            "winner": self.t1.pk,
            "status": "completed",
        }
        response = self.client.post(
            reverse("match_record_result", args=[self.match.pk]), data
        )
        self.assertRedirects(
            response, reverse("tournament_detail", args=[self.tournament.pk])
        )
        self.match.refresh_from_db()
        self.assertEqual(self.match.score, "21-15, 21-10")
        self.assertEqual(self.match.status, "completed")
        self.assertEqual(self.match.winner, self.t1)

    def test_match_result_post_invalid_stays_on_page(self):
        response = self.client.post(
            reverse("match_record_result", args=[self.match.pk]), {}
        )
        self.assertEqual(response.status_code, 200)

    def test_match_result_404_for_nonexistent(self):
        response = self.client.get(reverse("match_record_result", args=[9999]))
        self.assertEqual(response.status_code, 404)


# ---------------------------------------------------------------------------
# Score validation (MatchResultForm)
# ---------------------------------------------------------------------------

class MatchResultFormValidationTest(TestCase):
    """Tests for the BWF score validation added to MatchResultForm."""

    def setUp(self):
        self.tournament = make_tournament(owner=None)
        self.division = make_division(tournament=self.tournament)
        self.t1 = make_team(r1=1, r2=2)
        self.t2 = make_team(r1=3, r2=4)
        self.match = Match.objects.create(
            division=self.division, team1=self.t1, team2=self.t2
        )

    def _post(self, score, winner=None, status='completed'):
        return MatchResultForm(
            data={'score': score, 'winner': (winner or self.t1).pk, 'status': status},
            instance=self.match,
        )

    # ── _parse_score helper ────────────────────────────────────────────────
    def test_parse_score_single_set(self):
        self.assertEqual(_form_parse_score('21-15'), [(21, 15)])

    def test_parse_score_three_sets(self):
        self.assertEqual(_form_parse_score('21-15, 18-21, 21-18'), [(21, 15), (18, 21), (21, 18)])

    def test_parse_score_bad_format_raises(self):
        with self.assertRaises(ValueError):
            _form_parse_score('abc')

    def test_parse_score_missing_dash_raises(self):
        with self.assertRaises(ValueError):
            _form_parse_score('21 15')

    # ── _validate_set helper ───────────────────────────────────────────────
    def test_validate_set_normal_win(self):
        self.assertEqual(_validate_set(21, 15), '')

    def test_validate_set_deuce_win(self):
        self.assertEqual(_validate_set(22, 20), '')
        self.assertEqual(_validate_set(30, 28), '')

    def test_validate_set_max_deuce(self):
        self.assertEqual(_validate_set(30, 29), '')

    def test_validate_set_draw_invalid(self):
        self.assertNotEqual(_validate_set(21, 21), '')

    def test_validate_set_too_low_winner(self):
        self.assertNotEqual(_validate_set(19, 10), '')

    def test_validate_set_21_20_invalid(self):
        # At 20-20 you must play to 2-point lead
        self.assertNotEqual(_validate_set(21, 20), '')

    def test_validate_set_over_30_invalid(self):
        self.assertNotEqual(_validate_set(31, 29), '')

    def test_validate_set_deuce_not_2_apart_invalid(self):
        # 23-20 is not valid (not 2-point lead from deuce)
        self.assertNotEqual(_validate_set(23, 20), '')

    # ── Form-level validation ──────────────────────────────────────────────
    def test_valid_score_2_sets(self):
        form = self._post('21-15, 21-10')
        self.assertTrue(form.is_valid(), form.errors)

    def test_valid_score_3_sets(self):
        form = self._post('21-15, 18-21, 21-18')
        self.assertTrue(form.is_valid(), form.errors)

    def test_valid_score_deuce(self):
        form = self._post('22-20, 21-15')
        self.assertTrue(form.is_valid(), form.errors)

    def test_invalid_score_bad_format(self):
        form = self._post('21:15, 21-10')
        self.assertFalse(form.is_valid())
        self.assertIn('score', form.errors)

    def test_invalid_score_21_20(self):
        form = self._post('21-20, 21-10')
        self.assertFalse(form.is_valid())

    def test_invalid_only_1_set(self):
        form = self._post('21-15')
        self.assertFalse(form.is_valid())

    def test_invalid_too_many_sets(self):
        form = self._post('21-15, 21-10, 21-5, 21-3')
        self.assertFalse(form.is_valid())

    def test_invalid_unnecessary_third_set(self):
        # t1 wins first two → third set unnecessary
        form = self._post('21-15, 21-10, 21-5')
        self.assertFalse(form.is_valid())

    def test_invalid_winner_does_not_match_score(self):
        # t1 wins both sets but winner is set to t2
        form = self._post('21-15, 21-10', winner=self.t2)
        self.assertFalse(form.is_valid())
        self.assertTrue(any('sæt' in e for e in form.non_field_errors()))

    def test_correct_winner_is_valid(self):
        # t2 wins both sets, winner is t2
        form = self._post('15-21, 10-21', winner=self.t2)
        self.assertTrue(form.is_valid(), form.errors)

    def test_no_validation_when_status_not_completed(self):
        # Status in_progress → score not validated
        form = MatchResultForm(
            data={'score': 'nonsense', 'winner': self.t1.pk, 'status': 'in_progress'},
            instance=self.match,
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_empty_score_not_validated_when_completed(self):
        # Blank score with status=completed is still allowed (no score yet)
        form = MatchResultForm(
            data={'score': '', 'winner': self.t1.pk, 'status': 'completed'},
            instance=self.match,
        )
        self.assertTrue(form.is_valid(), form.errors)


class WalkoverViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = make_user(username='woclub')
        self.client.force_login(self.user)
        self.tournament = make_tournament(owner=self.user)
        self.division = make_division(tournament=self.tournament)
        self.t1 = make_team(r1=1, r2=2)
        self.t2 = make_team(r1=3, r2=4)
        self.match = Match.objects.create(
            division=self.division, team1=self.t1, team2=self.t2
        )

    def test_walkover_get_returns_200(self):
        response = self.client.get(reverse("match_walkover", args=[self.match.pk]))
        self.assertEqual(response.status_code, 200)

    def test_walkover_post_sets_wo_score_and_winner(self):
        response = self.client.post(
            reverse("match_walkover", args=[self.match.pk]),
            {'winner': self.t1.pk},
        )
        self.assertRedirects(response, reverse("tournament_detail", args=[self.tournament.pk]))
        self.match.refresh_from_db()
        self.assertEqual(self.match.score, '21-0, 21-0')
        self.assertEqual(self.match.status, 'completed')
        self.assertEqual(self.match.winner, self.t1)
        self.assertTrue(self.match.walkover)

    def test_walkover_counts_in_standings(self):
        self.division.teams.add(self.t1, self.t2)
        self.match.winner = self.t2
        self.match.score = '21-0, 21-0'
        self.match.status = 'completed'
        self.match.walkover = True
        self.match.save()
        rows = compute_standings(self.division)
        self.assertEqual(rows[0]['team'], self.t2)
        self.assertEqual(rows[0]['points'], 2)

    def test_walkover_404_for_nonexistent(self):
        response = self.client.get(reverse("match_walkover", args=[9999]))
        self.assertEqual(response.status_code, 404)


# ---------------------------------------------------------------------------
# Group standings (playoff)
# ---------------------------------------------------------------------------

class GroupStandingsTest(TestCase):
    def setUp(self):
        self.tournament = make_tournament(owner=None)
        self.division = Division.objects.create(
            tournament=self.tournament, name="Playoff", discipline='double',
            tournament_type='playoff', group_count=2, advance_count=1,
        )
        self.t1 = make_team(r1=1, r2=2)
        self.t2 = make_team(r1=3, r2=4)
        self.t3 = make_team(r1=5, r2=6)
        self.t4 = make_team(r1=7, r2=8)
        self.division.teams.add(self.t1, self.t2, self.t3, self.t4)

    def test_returns_groups_in_order(self):
        Match.objects.create(division=self.division, team1=self.t1, team2=self.t2,
                             group_number=1, phase='group', status='completed',
                             winner=self.t1, score='21-15')
        Match.objects.create(division=self.division, team1=self.t3, team2=self.t4,
                             group_number=2, phase='group', status='completed',
                             winner=self.t3, score='21-10')
        result = compute_group_standings(self.division)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0][0], 1)
        self.assertEqual(result[1][0], 2)

    def test_winner_leads_group(self):
        Match.objects.create(division=self.division, team1=self.t1, team2=self.t2,
                             group_number=1, phase='group', status='completed',
                             winner=self.t1, score='21-15')
        result = compute_group_standings(self.division)
        g1_rows = result[0][1]
        self.assertEqual(g1_rows[0]['team'], self.t1)
        self.assertEqual(g1_rows[0]['points'], 2)

    def test_empty_division_returns_no_groups(self):
        empty_div = Division.objects.create(
            tournament=self.tournament, name="Empty playoff", discipline='double',
            tournament_type='playoff',
        )
        self.assertEqual(compute_group_standings(empty_div), [])


# ---------------------------------------------------------------------------
# DivisionSeed model
# ---------------------------------------------------------------------------

class DivisionSeedModelTest(TestCase):
    def test_str_includes_seed_number_and_names(self):
        t = make_tournament()
        d = make_division(tournament=t, tournament_type='tree')
        team = make_team(r1=1, r2=2)
        d.teams.add(team)
        seed = DivisionSeed.objects.create(division=d, team=team, seed_number=1)
        s = str(seed)
        self.assertIn('1', s)
        self.assertIn(team.name, s)


# ---------------------------------------------------------------------------
# Seeds views
# ---------------------------------------------------------------------------

class DivisionSeedViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = make_user(username='seedclub')
        self.client.force_login(self.user)
        self.tournament = make_tournament(owner=self.user)
        self.division = make_division(tournament=self.tournament, tournament_type='tree')
        self.t1 = make_team(r1=1, r2=2)
        self.t2 = make_team(r1=3, r2=4)
        self.division.teams.add(self.t1, self.t2)

    def test_update_seeds_creates_entries(self):
        response = self.client.post(
            reverse('division_update_seeds', args=[self.division.pk]),
            {f'seed_{self.t1.pk}': '1', f'seed_{self.t2.pk}': '2'},
        )
        self.assertRedirects(response, reverse('tournament_detail', args=[self.tournament.pk]))
        self.assertEqual(DivisionSeed.objects.filter(division=self.division).count(), 2)
        self.assertEqual(DivisionSeed.objects.get(division=self.division, team=self.t1).seed_number, 1)

    def test_update_seeds_clears_old_entries(self):
        DivisionSeed.objects.create(division=self.division, team=self.t1, seed_number=1)
        # Re-post with only t2 seeded
        self.client.post(
            reverse('division_update_seeds', args=[self.division.pk]),
            {f'seed_{self.t2.pk}': '1'},
        )
        self.assertFalse(DivisionSeed.objects.filter(division=self.division, team=self.t1).exists())
        self.assertTrue(DivisionSeed.objects.filter(division=self.division, team=self.t2).exists())

    def test_duplicate_seed_numbers_ignored(self):
        # Both teams given seed 1 → only first accepted
        self.client.post(
            reverse('division_update_seeds', args=[self.division.pk]),
            {f'seed_{self.t1.pk}': '1', f'seed_{self.t2.pk}': '1'},
        )
        self.assertEqual(DivisionSeed.objects.filter(division=self.division).count(), 1)

    def test_invalid_seed_value_ignored(self):
        self.client.post(
            reverse('division_update_seeds', args=[self.division.pk]),
            {f'seed_{self.t1.pk}': 'abc'},
        )
        self.assertEqual(DivisionSeed.objects.filter(division=self.division).count(), 0)

    def test_seed_list_in_detail_context(self):
        DivisionSeed.objects.create(division=self.division, team=self.t1, seed_number=1)
        response = self.client.get(reverse('tournament_detail', args=[self.tournament.pk]))
        dd = response.context['division_data'][0]
        seed_list = dd['seed_list']
        team_pks = [t.pk for t, _ in seed_list]
        self.assertIn(self.t1.pk, team_pks)

    def test_seeds_dict_in_detail_context(self):
        DivisionSeed.objects.create(division=self.division, team=self.t1, seed_number=1)
        response = self.client.get(reverse('tournament_detail', args=[self.tournament.pk]))
        dd = response.context['division_data'][0]
        self.assertIn(self.t1.pk, dd['seeds_dict'])
        self.assertIn('(1)', dd['seeds_dict'][self.t1.pk])


# ---------------------------------------------------------------------------
# Bigscreen view
# ---------------------------------------------------------------------------

class BigscreenViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = make_user(username='bigscreenclub')
        self.client.force_login(self.user)
        self.tournament = make_tournament(owner=self.user)
        self.division = make_division(tournament=self.tournament)
        self.t1 = make_team(r1=1, r2=2)
        self.t2 = make_team(r1=3, r2=4)

    def test_bigscreen_returns_200(self):
        response = self.client.get(reverse('tournament_bigscreen', args=[self.tournament.pk]))
        self.assertEqual(response.status_code, 200)

    def test_bigscreen_shows_pending_matches_with_time(self):
        import datetime as dt
        from django.utils import timezone
        Match.objects.create(
            division=self.division, team1=self.t1, team2=self.t2,
            status='pending', match_number=1,
            scheduled_time=timezone.make_aware(dt.datetime(2026, 1, 1, 10, 0)),
            court='1',
        )
        response = self.client.get(reverse('tournament_bigscreen', args=[self.tournament.pk]))
        # Team name containing '&' is HTML-escaped; check player name instead
        self.assertContains(response, self.t1.player1.name)

    def test_bigscreen_excludes_completed(self):
        import datetime as dt
        from django.utils import timezone
        Match.objects.create(
            division=self.division, team1=self.t1, team2=self.t2,
            status='completed', match_number=1,
            scheduled_time=timezone.make_aware(dt.datetime(2026, 1, 1, 10, 0)),
        )
        response = self.client.get(reverse('tournament_bigscreen', args=[self.tournament.pk]))
        self.assertEqual(len(response.context['matches']), 0)

    def test_bigscreen_404_for_nonexistent(self):
        response = self.client.get(reverse('tournament_bigscreen', args=[9999]))
        self.assertEqual(response.status_code, 404)


# ---------------------------------------------------------------------------
# Tournament program print + division scoresheet
# ---------------------------------------------------------------------------

class ProgramPrintViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = make_user(username='printclub')
        self.client.force_login(self.user)
        self.tournament = make_tournament(owner=self.user)
        self.division = make_division(tournament=self.tournament)
        self.t1 = make_team(r1=1, r2=2)
        self.t2 = make_team(r1=3, r2=4)
        self.division.teams.add(self.t1, self.t2)

    def test_program_print_returns_200(self):
        response = self.client.get(reverse('tournament_program_print', args=[self.tournament.pk]))
        self.assertEqual(response.status_code, 200)

    def test_program_print_contains_division_name(self):
        response = self.client.get(reverse('tournament_program_print', args=[self.tournament.pk]))
        self.assertContains(response, self.division.name)

    def test_program_print_contains_team_names(self):
        response = self.client.get(reverse('tournament_program_print', args=[self.tournament.pk]))
        # Team names containing '&' are HTML-escaped in the response
        self.assertContains(response, self.t1.player1.name)

    def test_program_print_404_for_nonexistent(self):
        response = self.client.get(reverse('tournament_program_print', args=[9999]))
        self.assertEqual(response.status_code, 404)

    def test_schedule_print_returns_200(self):
        response = self.client.get(reverse('tournament_schedule_print', args=[self.tournament.pk]))
        self.assertEqual(response.status_code, 200)

    def test_schedule_print_404_for_nonexistent(self):
        response = self.client.get(reverse('tournament_schedule_print', args=[9999]))
        self.assertEqual(response.status_code, 404)

    def test_schedule_print_contains_match_number(self):
        from tournaments.models import Match
        match = Match.objects.create(
            division=self.division,
            team1=self.t1,
            team2=self.t2,
            match_round=1,
            match_number=42,
            scheduled_time='2026-04-22 10:00:00+00:00',
            court=2,
        )
        response = self.client.get(reverse('tournament_schedule_print', args=[self.tournament.pk]))
        self.assertContains(response, '42')
        self.assertContains(response, self.t1.player1.name)


class DivisionScoresheetViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = make_user(username='scoresheetclub')
        self.client.force_login(self.user)
        self.tournament = make_tournament(owner=self.user)
        self.division = make_division(tournament=self.tournament)
        self.t1 = make_team(r1=1, r2=2)
        self.t2 = make_team(r1=3, r2=4)
        self.division.teams.add(self.t1, self.t2)

    def test_division_scoresheet_returns_200(self):
        self.client.post(reverse('division_generate_schedule', args=[self.division.pk]))
        response = self.client.get(reverse('division_scoresheet', args=[self.division.pk]))
        self.assertEqual(response.status_code, 200)

    def test_division_scoresheet_404_for_nonexistent(self):
        response = self.client.get(reverse('division_scoresheet', args=[9999]))
        self.assertEqual(response.status_code, 404)


# ---------------------------------------------------------------------------
# Toggle lock view
# ---------------------------------------------------------------------------

class ToggleLockViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = make_user(username='lockclub')
        self.client.force_login(self.user)
        self.tournament = make_tournament(owner=self.user)

    def test_lock_toggles_on(self):
        self.assertFalse(self.tournament.schedule_locked)
        self.client.post(reverse('tournament_toggle_lock', args=[self.tournament.pk]))
        self.tournament.refresh_from_db()
        self.assertTrue(self.tournament.schedule_locked)

    def test_lock_toggles_off(self):
        self.tournament.schedule_locked = True
        self.tournament.save()
        self.client.post(reverse('tournament_toggle_lock', args=[self.tournament.pk]))
        self.tournament.refresh_from_db()
        self.assertFalse(self.tournament.schedule_locked)

    def test_lock_redirects_to_schedule(self):
        response = self.client.post(reverse('tournament_toggle_lock', args=[self.tournament.pk]))
        self.assertRedirects(response, reverse('tournament_schedule', args=[self.tournament.pk]))


# ---------------------------------------------------------------------------
# Generate time schedule – locked / no start_time paths
# ---------------------------------------------------------------------------

class TimeScheduleEdgeCaseTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = make_user(username='timeedgeclub')
        self.client.force_login(self.user)
        self.tournament = make_tournament(owner=self.user)
        self.division = make_division(tournament=self.tournament)
        self.t1 = make_team(r1=1, r2=2)
        self.t2 = make_team(r1=3, r2=4)
        self.division.teams.add(self.t1, self.t2)

    def test_generate_when_locked_shows_error(self):
        self.tournament.schedule_locked = True
        self.tournament.save()
        response = self.client.post(
            reverse('tournament_generate_time_schedule', args=[self.tournament.pk])
        )
        self.assertRedirects(response, reverse('tournament_schedule', args=[self.tournament.pk]))
        messages_list = list(response.wsgi_request._messages)
        self.assertTrue(any('låst' in str(m) for m in messages_list))

    def test_generate_with_no_matches_shows_warning(self):
        self.tournament.start_time = datetime.time(9, 0)
        self.tournament.save()
        # No matches generated → count=0 → warning
        response = self.client.post(
            reverse('tournament_generate_time_schedule', args=[self.tournament.pk])
        )
        self.assertRedirects(response, reverse('tournament_schedule', args=[self.tournament.pk]))


# ---------------------------------------------------------------------------
# Generate schedule – tree bracket_label path + locked guard
# ---------------------------------------------------------------------------

class GenerateScheduleTreeTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = make_user(username='treeclub')
        self.client.force_login(self.user)
        self.tournament = make_tournament(owner=self.user)
        self.division = make_division(tournament=self.tournament, tournament_type='tree')
        for i in range(4):
            t = make_team(r1=i * 2 + 1, r2=i * 2 + 2)
            self.division.teams.add(t)

    def test_tree_generation_updates_bracket_labels(self):
        self.client.post(reverse('division_generate_schedule', args=[self.division.pk]))
        placeholder = Match.objects.filter(division=self.division, team1__isnull=True).first()
        # Bracket label should reference match numbers, not slot codes
        self.assertIsNotNone(placeholder)
        self.assertNotIn('R1S', placeholder.bracket_label or '')

    def test_locked_tournament_blocks_generate(self):
        self.tournament.schedule_locked = True
        self.tournament.save()
        response = self.client.post(reverse('division_generate_schedule', args=[self.division.pk]))
        self.assertRedirects(response, reverse('tournament_detail', args=[self.tournament.pk]))
        self.assertEqual(Match.objects.filter(division=self.division).count(), 0)


# ---------------------------------------------------------------------------
# Generate schedule – playoff message path
# ---------------------------------------------------------------------------

class GenerateSchedulePlayoffTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = make_user(username='playoffclub')
        self.client.force_login(self.user)
        self.tournament = make_tournament(owner=self.user)
        self.division = Division.objects.create(
            tournament=self.tournament, name="Playoff D", discipline='double',
            tournament_type='playoff', group_count=2, advance_count=1,
        )
        for i in range(4):
            t = make_team(r1=i * 2 + 1, r2=i * 2 + 2)
            self.division.teams.add(t)

    def test_playoff_generate_shows_group_and_playoff_count(self):
        response = self.client.post(reverse('division_generate_schedule', args=[self.division.pk]))
        self.assertRedirects(response, reverse('tournament_detail', args=[self.tournament.pk]))
        messages_list = list(response.wsgi_request._messages)
        self.assertTrue(any('gruppe' in str(m).lower() for m in messages_list))


# ---------------------------------------------------------------------------
# Scheduler edge cases – seeding + advance_bracket for non-tree
# ---------------------------------------------------------------------------

class SchedulerSeedingTest(TestCase):
    def test_seeded_teams_placed_first_in_bracket(self):
        from .scheduler import _sort_teams_by_seed
        division = make_division(tournament_type='tree')
        t1 = make_team(r1=1, r2=2)
        t2 = make_team(r1=3, r2=4)
        division.teams.add(t1, t2)
        # Seed t2 as #1 → it should come first
        DivisionSeed.objects.create(division=division, team=t2, seed_number=1)
        sorted_teams = _sort_teams_by_seed(division, [t1, t2])
        self.assertEqual(sorted_teams[0], t2)
        self.assertEqual(sorted_teams[1], t1)

    def test_advance_bracket_non_tree_does_nothing(self):
        division = make_division(tournament_type='group')
        t1 = make_team(r1=1, r2=2)
        t2 = make_team(r1=3, r2=4)
        match = Match.objects.create(
            division=division, team1=t1, team2=t2,
            status='completed', winner=t1, bracket_slot=1, match_round=1,
        )
        # Should not raise, and no next-round placeholder is created
        advance_bracket(match)
        self.assertEqual(Match.objects.filter(division=division).count(), 1)

    def test_generate_bracket_too_few_teams_returns_empty(self):
        division = make_division(tournament_type='tree')
        t1 = make_team(r1=1, r2=2)
        division.teams.add(t1)
        result = generate_bracket(division)
        self.assertEqual(result, [])

    def test_generate_round_robin_too_few_returns_empty(self):
        division = make_division(tournament_type='group')
        t1 = make_team(r1=1, r2=2)
        division.teams.add(t1)
        result = generate_round_robin(division)
        self.assertEqual(result, [])

    def test_generate_playoff_too_few_returns_empty(self):
        from .scheduler import generate_playoff
        division = Division.objects.create(
            tournament=make_tournament(), name="P", discipline='double',
            tournament_type='playoff', group_count=2, advance_count=1,
        )
        t1 = make_team(r1=1, r2=2)
        division.teams.add(t1)
        result = generate_playoff(division)
        self.assertEqual(result, [])


# ---------------------------------------------------------------------------
# schedule_planner – placeholder + playoff barrier paths
# ---------------------------------------------------------------------------

class SchedulePlannerPlayoffTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = make_user(username='schedulerclub')
        self.client.force_login(self.user)
        self.tournament = Tournament.objects.create(
            name="TP", date=datetime.date(2026, 6, 1),
            division_model='mixed', scoring_model='best_of_3_21',
            start_time=datetime.time(9, 0), court_count=2,
            player_break_time=15, single_match_duration=30,
            owner=self.user,
        )
        self.division = Division.objects.create(
            tournament=self.tournament, name="P", discipline='double',
            tournament_type='playoff', group_count=2, advance_count=1,
        )
        for i in range(4):
            t = make_team(r1=i * 2 + 1, r2=i * 2 + 2)
            self.division.teams.add(t)

    def test_playoff_bracket_matches_scheduled_after_group_matches(self):
        from .schedule_planner import generate_time_schedule
        self.client.post(reverse('division_generate_schedule', args=[self.division.pk]))
        count = generate_time_schedule(self.tournament)
        self.assertGreater(count, 0)
        group_times = list(
            Match.objects.filter(division=self.division, phase='group')
            .exclude(scheduled_time=None)
            .values_list('scheduled_time', flat=True)
        )
        playoff_times = list(
            Match.objects.filter(division=self.division, phase='playoff')
            .exclude(scheduled_time=None)
            .values_list('scheduled_time', flat=True)
        )
        if group_times and playoff_times:
            self.assertGreaterEqual(min(playoff_times), max(group_times))


# ---------------------------------------------------------------------------
# templatetag dict_get – non-dict fallback
# ---------------------------------------------------------------------------

class DictGetFilterTest(TestCase):
    def test_non_dict_returns_empty_string(self):
        from tournaments.templatetags.tournament_extras import dict_get
        self.assertEqual(dict_get('not-a-dict', 'key'), '')
        self.assertEqual(dict_get(None, 'key'), '')
        self.assertEqual(dict_get(42, 'key'), '')

    def test_dict_returns_value(self):
        from tournaments.templatetags.tournament_extras import dict_get
        self.assertEqual(dict_get({'a': 'x'}, 'a'), 'x')
        self.assertEqual(dict_get({'a': 'x'}, 'b'), '')


# ---------------------------------------------------------------------------
# Tournament delete view
# ---------------------------------------------------------------------------

class TournamentDeleteTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = make_user(username='deleteclub')
        self.client.force_login(self.user)
        self.tournament = make_tournament(owner=self.user)

    def test_delete_get_shows_confirm(self):
        response = self.client.get(reverse('tournament_delete', args=[self.tournament.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.tournament.name)

    def test_delete_post_removes_tournament(self):
        pk = self.tournament.pk
        response = self.client.post(reverse('tournament_delete', args=[pk]))
        self.assertRedirects(response, reverse('tournament_list'))
        self.assertFalse(Tournament.objects.filter(pk=pk).exists())

    def test_delete_404_for_nonexistent(self):
        response = self.client.get(reverse('tournament_delete', args=[9999]))
        self.assertEqual(response.status_code, 404)

    def test_delete_other_owners_tournament_returns_404(self):
        other = make_user(username='otherdeleteclub')
        other_tournament = make_tournament(owner=other)
        response = self.client.get(reverse('tournament_delete', args=[other_tournament.pk]))
        self.assertEqual(response.status_code, 404)


# ---------------------------------------------------------------------------
# Tournament export view
# ---------------------------------------------------------------------------

class TournamentExportTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = make_user(username='exportclub')
        self.client.force_login(self.user)
        self.tournament = make_tournament(owner=self.user)
        self.division = make_division(tournament=self.tournament)
        t1 = make_team(r1=1, r2=2)
        t2 = make_team(r1=3, r2=4)
        self.division.teams.add(t1, t2)
        self.client.post(reverse('division_generate_schedule', args=[self.division.pk]))

    def test_export_returns_json_attachment(self):
        response = self.client.get(reverse('tournament_export', args=[self.tournament.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertIn('application/json', response['Content-Type'])
        self.assertIn('attachment', response['Content-Disposition'])

    def test_export_filename_contains_tournament_date(self):
        response = self.client.get(reverse('tournament_export', args=[self.tournament.pk]))
        self.assertIn(str(self.tournament.date), response['Content-Disposition'])

    def test_export_contains_required_sections(self):
        import json as _json
        response = self.client.get(reverse('tournament_export', args=[self.tournament.pk]))
        data = _json.loads(response.content.decode('utf-8'))
        for key in ('version', 'tournament', 'players', 'teams', 'divisions', 'matches', 'seeds'):
            self.assertIn(key, data)

    def test_export_version_is_1(self):
        import json as _json
        response = self.client.get(reverse('tournament_export', args=[self.tournament.pk]))
        data = _json.loads(response.content.decode('utf-8'))
        self.assertEqual(data['version'], 1)

    def test_export_404_for_other_owner(self):
        other = make_user(username='otherexportclub')
        other_tournament = make_tournament(owner=other)
        response = self.client.get(reverse('tournament_export', args=[other_tournament.pk]))
        self.assertEqual(response.status_code, 404)


# ---------------------------------------------------------------------------
# Tournament import view
# ---------------------------------------------------------------------------

class TournamentImportTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = make_user(username='importclub')
        self.client.force_login(self.user)
        # Build a valid backup by exporting a real tournament
        self.tournament = make_tournament(owner=self.user)
        self.division = make_division(tournament=self.tournament)
        t1 = make_team(r1=1, r2=2)
        t2 = make_team(r1=3, r2=4)
        self.division.teams.add(t1, t2)
        self.client.post(reverse('division_generate_schedule', args=[self.division.pk]))

    def _export_json(self):
        import json as _json
        response = self.client.get(reverse('tournament_export', args=[self.tournament.pk]))
        return _json.loads(response.content.decode('utf-8'))

    def _upload(self, data):
        import json as _json
        import io
        from django.core.files.uploadedfile import SimpleUploadedFile
        raw = _json.dumps(data).encode('utf-8')
        f = SimpleUploadedFile('backup.json', raw, content_type='application/json')
        return self.client.post(reverse('tournament_import'), {'backup_file': f})

    def test_import_get_returns_200(self):
        response = self.client.get(reverse('tournament_import'))
        self.assertEqual(response.status_code, 200)

    def test_import_no_file_shows_error(self):
        response = self.client.post(reverse('tournament_import'), {})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Ingen fil valgt')

    def test_import_invalid_json_shows_error(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        f = SimpleUploadedFile('bad.json', b'not valid json', content_type='application/json')
        response = self.client.post(reverse('tournament_import'), {'backup_file': f})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'JSON')

    def test_import_wrong_version_shows_error(self):
        data = self._export_json()
        data['version'] = 99
        response = self._upload(data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'version')

    def test_import_valid_backup_creates_tournament(self):
        data = self._export_json()
        count_before = Tournament.objects.count()
        response = self._upload(data)
        self.assertEqual(Tournament.objects.count(), count_before + 1)
        new_t = Tournament.objects.order_by('-pk').first()
        self.assertIn('gendannet', new_t.name)
        self.assertRedirects(response, reverse('tournament_detail', args=[new_t.pk]))

    def test_import_deduplicates_players(self):
        from players.models import Player as P
        data = self._export_json()
        # First import: creates players
        self._upload(data)
        count_after_first = P.objects.filter(owner=self.user).count()
        self.assertGreater(count_after_first, 0)
        # Second import of same data: players should be get_or_created, not duplicated
        self._upload(data)
        self.assertEqual(P.objects.filter(owner=self.user).count(), count_after_first)

    def test_import_creates_divisions_and_matches(self):
        import json as _json
        data = self._export_json()
        self._upload(data)
        new_t = Tournament.objects.order_by('-pk').first()
        self.assertEqual(new_t.divisions.count(), 1)
        self.assertGreater(Match.objects.filter(division__tournament=new_t).count(), 0)


# ---------------------------------------------------------------------------
# Division set priority view
# ---------------------------------------------------------------------------

class DivisionSetPriorityTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = make_user(username='priorityclub')
        self.client.force_login(self.user)
        self.tournament = make_tournament(owner=self.user)
        self.division = make_division(tournament=self.tournament)

    def test_set_priority_updates_value(self):
        response = self.client.post(
            reverse('division_set_priority', args=[self.division.pk]),
            {'schedule_priority': '3'},
        )
        self.assertRedirects(response, reverse('tournament_detail', args=[self.tournament.pk]))
        self.division.refresh_from_db()
        self.assertEqual(self.division.schedule_priority, 3)

    def test_set_priority_clamps_to_1_at_minimum(self):
        self.client.post(
            reverse('division_set_priority', args=[self.division.pk]),
            {'schedule_priority': '-5'},
        )
        self.division.refresh_from_db()
        self.assertEqual(self.division.schedule_priority, 1)

    def test_set_priority_clamps_to_10_at_maximum(self):
        self.client.post(
            reverse('division_set_priority', args=[self.division.pk]),
            {'schedule_priority': '99'},
        )
        self.division.refresh_from_db()
        self.assertEqual(self.division.schedule_priority, 10)

    def test_set_priority_invalid_string_leaves_value_unchanged(self):
        self.division.schedule_priority = 5
        self.division.save()
        self.client.post(
            reverse('division_set_priority', args=[self.division.pk]),
            {'schedule_priority': 'abc'},
        )
        self.division.refresh_from_db()
        self.assertEqual(self.division.schedule_priority, 5)

    def test_set_priority_get_redirects(self):
        response = self.client.get(
            reverse('division_set_priority', args=[self.division.pk])
        )
        self.assertRedirects(response, reverse('tournament_detail', args=[self.tournament.pk]))


# ---------------------------------------------------------------------------
# Match start view
# ---------------------------------------------------------------------------

class MatchStartTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = make_user(username='startclub')
        self.client.force_login(self.user)
        self.tournament = make_tournament(owner=self.user)
        self.division = make_division(tournament=self.tournament)
        self.t1 = make_team(r1=1, r2=2)
        self.t2 = make_team(r1=3, r2=4)
        self.match = Match.objects.create(
            division=self.division, team1=self.t1, team2=self.t2, match_number=1
        )

    def test_match_start_sets_in_progress(self):
        response = self.client.post(reverse('match_start', args=[self.match.pk]))
        self.assertRedirects(response, reverse('tournament_detail', args=[self.tournament.pk]))
        self.match.refresh_from_db()
        self.assertEqual(self.match.status, 'in_progress')

    def test_match_start_already_in_progress_not_changed(self):
        self.match.status = 'in_progress'
        self.match.save()
        self.client.post(reverse('match_start', args=[self.match.pk]))
        self.match.refresh_from_db()
        self.assertEqual(self.match.status, 'in_progress')

    def test_match_start_blocked_when_player_already_playing(self):
        from django.utils import timezone
        # Put t1's players in another in_progress match
        other_match = Match.objects.create(
            division=self.division, team1=self.t1, team2=self.t2,
            status='in_progress', match_number=99
        )
        response = self.client.post(reverse('match_start', args=[self.match.pk]))
        self.assertRedirects(response, reverse('tournament_detail', args=[self.tournament.pk]))
        self.match.refresh_from_db()
        # Should stay pending because player is already playing
        self.assertEqual(self.match.status, 'pending')
        messages_list = list(response.wsgi_request._messages)
        self.assertTrue(any('spiller allerede' in str(m) for m in messages_list))

    def test_match_start_404_for_nonexistent(self):
        response = self.client.post(reverse('match_start', args=[9999]))
        self.assertEqual(response.status_code, 404)


# ---------------------------------------------------------------------------
# Public views (no login required)
# ---------------------------------------------------------------------------

class PublicViewTest(TestCase):
    def setUp(self):
        self.user = make_user(username='publicclub')
        self.tournament = make_tournament(owner=self.user)
        self.division = make_division(tournament=self.tournament)
        t1 = make_team(r1=1, r2=2)
        t2 = make_team(r1=3, r2=4)
        self.division.teams.add(t1, t2)

    def test_public_landing_returns_200_without_login(self):
        response = self.client.get(reverse('public_landing'))
        self.assertEqual(response.status_code, 200)

    def test_public_landing_lists_tournaments(self):
        response = self.client.get(reverse('public_landing'))
        self.assertContains(response, self.tournament.name)

    def test_public_tournament_returns_200_without_login(self):
        response = self.client.get(reverse('public_tournament', args=[self.tournament.pk]))
        self.assertEqual(response.status_code, 200)

    def test_public_tournament_contains_division(self):
        response = self.client.get(reverse('public_tournament', args=[self.tournament.pk]))
        self.assertContains(response, self.division.name)

    def test_public_tournament_404_for_nonexistent(self):
        response = self.client.get(reverse('public_tournament', args=[9999]))
        self.assertEqual(response.status_code, 404)

    def test_public_schedule_returns_200_without_login(self):
        response = self.client.get(reverse('public_schedule', args=[self.tournament.pk]))
        self.assertEqual(response.status_code, 200)

    def test_public_schedule_404_for_nonexistent(self):
        response = self.client.get(reverse('public_schedule', args=[9999]))
        self.assertEqual(response.status_code, 404)

    def test_public_schedule_shows_scheduled_matches(self):
        import datetime as dt
        from django.utils import timezone
        t1 = make_team(r1=5, r2=6)
        t2 = make_team(r1=7, r2=8)
        Match.objects.create(
            division=self.division, team1=t1, team2=t2, match_number=10,
            scheduled_time=timezone.make_aware(dt.datetime(2026, 6, 1, 9, 0)),
            court='1',
        )
        response = self.client.get(reverse('public_schedule', args=[self.tournament.pk]))
        self.assertContains(response, t1.player1.name)


# ---------------------------------------------------------------------------
# Player status functions
# ---------------------------------------------------------------------------

class PlayerStatusFunctionTest(TestCase):
    def setUp(self):
        self.user = make_user(username='statusclub')
        self.tournament = Tournament.objects.create(
            name="Status T", date=datetime.date.today(),
            division_model='mixed', scoring_model='best_of_3_21',
            player_break_time=15, owner=self.user,
        )
        self.division = make_division(tournament=self.tournament)
        self.t1 = make_team(r1=1, r2=2)
        self.t2 = make_team(r1=3, r2=4)
        self.division.teams.add(self.t1, self.t2)

    def test_set_player_rest_sets_rest_until(self):
        from tournaments.player_status import set_player_rest
        from django.utils import timezone
        match = Match.objects.create(
            division=self.division, team1=self.t1, team2=self.t2,
            status='completed', winner=self.t1,
        )
        set_player_rest(match)
        self.t1.player1.refresh_from_db()
        self.t1.player2.refresh_from_db()
        self.assertIsNotNone(self.t1.player1.rest_until)
        self.assertIsNotNone(self.t1.player2.rest_until)
        self.assertGreater(self.t1.player1.rest_until, timezone.now())

    def test_check_match_startable_free_players_ok(self):
        from tournaments.player_status import check_match_startable
        match = Match.objects.create(
            division=self.division, team1=self.t1, team2=self.t2,
        )
        errors = check_match_startable(match)
        self.assertEqual(errors, [])

    def test_check_match_startable_resting_player_blocked(self):
        from tournaments.player_status import check_match_startable
        from django.utils import timezone
        import datetime as dt
        # Set rest_until to far future so player is resting
        self.t1.player1.rest_until = timezone.now() + dt.timedelta(minutes=30)
        self.t1.player1.save()
        match = Match.objects.create(
            division=self.division, team1=self.t1, team2=self.t2,
        )
        errors = check_match_startable(match)
        self.assertTrue(any('hviler' in e for e in errors))

    def test_check_match_startable_playing_player_blocked(self):
        from tournaments.player_status import check_match_startable
        # Create an in_progress match with t1
        Match.objects.create(
            division=self.division, team1=self.t1, team2=self.t2,
            status='in_progress',
        )
        match2 = Match.objects.create(
            division=self.division, team1=self.t1, team2=self.t2,
        )
        errors = check_match_startable(match2)
        self.assertTrue(any('spiller allerede' in e for e in errors))

    def test_team_status_playing(self):
        from tournaments.player_status import team_status, get_busy_info
        Match.objects.create(
            division=self.division, team1=self.t1, team2=self.t2,
            status='in_progress',
        )
        playing_pks, resting = get_busy_info()
        status, _ = team_status(self.t1, playing_pks, resting)
        self.assertEqual(status, 'playing')

    def test_team_status_resting(self):
        from tournaments.player_status import team_status, get_busy_info
        import datetime as dt
        from django.utils import timezone
        self.t1.player1.rest_until = timezone.now() + dt.timedelta(minutes=20)
        self.t1.player1.save()
        playing_pks, resting = get_busy_info()
        status, ru = team_status(self.t1, playing_pks, resting)
        self.assertEqual(status, 'resting')
        self.assertIsNotNone(ru)

    def test_team_status_none_team_returns_none(self):
        from tournaments.player_status import team_status
        status, ru = team_status(None, set(), {})
        self.assertIsNone(status)
        self.assertIsNone(ru)

