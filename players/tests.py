from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from .models import Player, Team

User = get_user_model()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_user(username='testclub', password='testpass123'):
    return User.objects.create_user(username=username, password=password)


def make_player(name="Alice", age=20, division="A", gender="K", owner=None):
    return Player.objects.create(name=name, age=age, division=division, gender=gender, owner=owner)


def make_team(p1=None, p2=None):
    p1 = p1 or make_player("Alice")
    p2 = p2 or make_player("Bob")
    return Team.objects.create(player1=p1, player2=p2)


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------

class PlayerModelTest(TestCase):
    def test_str_includes_name_and_division(self):
        player = make_player(name="Alice", division="U13")
        self.assertIn("Alice", str(player))
        self.assertIn("U13", str(player))

    def test_gender_choices(self):
        m = make_player(name="Bob", gender="M")
        k = make_player(name="Alice", gender="K")
        self.assertEqual(m.get_gender_display(), "Mand")
        self.assertEqual(k.get_gender_display(), "Kvinde")

    def test_valid_division_choices(self):
        valid_divisions = ["U9", "U11", "U13", "U15", "U17", "U19", "A", "B", "C"]
        for div in valid_divisions:
            p = make_player(division=div)
            self.assertEqual(p.division, div)


class TeamModelTest(TestCase):
    def test_auto_name_from_players(self):
        p1 = make_player("Alice")
        p2 = make_player("Bob")
        team = Team.objects.create(player1=p1, player2=p2)
        self.assertEqual(team.name, "Alice & Bob")

    def test_custom_name_is_preserved(self):
        p1 = make_player("Alice")
        p2 = make_player("Bob")
        team = Team.objects.create(player1=p1, player2=p2, name="Dream Team")
        self.assertEqual(team.name, "Dream Team")

    def test_str_returns_name(self):
        team = make_team()
        self.assertEqual(str(team), team.name)


# ---------------------------------------------------------------------------
# View tests – Player
# ---------------------------------------------------------------------------

class PlayerViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = make_user()
        self.client.force_login(self.user)
        self.player = make_player(owner=self.user)

    def test_player_list_returns_200(self):
        response = self.client.get(reverse("player_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.player.name)

    def test_player_add_get_returns_200(self):
        response = self.client.get(reverse("player_add"))
        self.assertEqual(response.status_code, 200)

    def test_player_add_post_creates_player(self):
        data = {"name": "Charlie", "age": 18, "division": "B", "gender": "M"}
        response = self.client.post(reverse("player_add"), data)
        self.assertRedirects(response, reverse("player_list"))
        self.assertTrue(Player.objects.filter(name="Charlie").exists())

    def test_player_add_post_invalid_does_not_redirect(self):
        response = self.client.post(reverse("player_add"), {})
        self.assertEqual(response.status_code, 200)

    def test_player_edit_get_returns_200(self):
        response = self.client.get(reverse("player_edit", args=[self.player.pk]))
        self.assertEqual(response.status_code, 200)

    def test_player_edit_post_updates_player(self):
        data = {"name": "Alice Updated", "age": 21, "division": "A", "gender": "K"}
        response = self.client.post(reverse("player_edit", args=[self.player.pk]), data)
        self.assertRedirects(response, reverse("player_list"))
        self.player.refresh_from_db()
        self.assertEqual(self.player.name, "Alice Updated")

    def test_player_list_filters_by_division(self):
        make_player("A-spiller", division="A", owner=self.user)
        make_player("B-spiller", division="B", owner=self.user)
        response = self.client.get(reverse("player_list") + "?division=A")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "A-spiller")

    def test_player_delete_get_shows_confirm(self):
        response = self.client.get(reverse("player_delete", args=[self.player.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.player.name)

    def test_player_delete_post_removes_player(self):
        response = self.client.post(reverse("player_delete", args=[self.player.pk]))
        self.assertRedirects(response, reverse("player_list"))
        self.assertFalse(Player.objects.filter(pk=self.player.pk).exists())

    def test_player_delete_nonexistent_returns_404(self):
        response = self.client.post(reverse("player_delete", args=[9999]))
        self.assertEqual(response.status_code, 404)


# ---------------------------------------------------------------------------
# View tests – Team
# ---------------------------------------------------------------------------

class TeamViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = make_user(username='teamclub')
        self.client.force_login(self.user)
        p1 = make_player("Alice", owner=self.user)
        p2 = make_player("Bob", owner=self.user)
        self.team = Team.objects.create(player1=p1, player2=p2)

    def test_team_list_returns_200(self):
        response = self.client.get(reverse("team_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.team.name, html=True)

    def test_team_add_get_returns_200(self):
        response = self.client.get(reverse("team_add"))
        self.assertEqual(response.status_code, 200)

    def test_team_add_post_creates_team(self):
        p1 = make_player("Dave", gender='M', owner=self.user)
        p2 = make_player("Eve", gender='M', owner=self.user)  # same gender → double
        data = {"player1": p1.pk, "player2": p2.pk, "pair_type": "double"}
        response = self.client.post(reverse("team_add"), data)
        self.assertRedirects(response, reverse("team_list"))
        self.assertTrue(Team.objects.filter(player1=p1, player2=p2).exists())

    def test_team_add_double_wrong_gender_fails(self):
        p1 = make_player("Man1", gender='M', owner=self.user)
        p2 = make_player("Woman1", gender='K', owner=self.user)
        data = {"player1": p1.pk, "player2": p2.pk, "pair_type": "double"}
        response = self.client.post(reverse("team_add"), data)
        self.assertEqual(response.status_code, 200)  # form error, no redirect
        self.assertFalse(Team.objects.filter(player1=p1, player2=p2).exists())

    def test_team_add_mixed_wrong_gender_fails(self):
        p1 = make_player("Man2", gender='M', owner=self.user)
        p2 = make_player("Man3", gender='M', owner=self.user)
        data = {"player1": p1.pk, "player2": p2.pk, "pair_type": "mixed"}
        response = self.client.post(reverse("team_add"), data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Team.objects.filter(player1=p1, player2=p2).exists())

    def test_team_add_mixed_correct_genders_succeeds(self):
        p1 = make_player("Man4", gender='M', owner=self.user)
        p2 = make_player("Woman2", gender='K', owner=self.user)
        data = {"player1": p1.pk, "player2": p2.pk, "pair_type": "mixed"}
        response = self.client.post(reverse("team_add"), data)
        self.assertRedirects(response, reverse("team_list"))
        self.assertTrue(Team.objects.filter(player1=p1, player2=p2, pair_type='mixed').exists())

    def test_team_add_no_pair_type_with_two_players_fails(self):
        p1 = make_player("Man5", gender='M', owner=self.user)
        p2 = make_player("Man6", gender='M', owner=self.user)
        data = {"player1": p1.pk, "player2": p2.pk}
        response = self.client.post(reverse("team_add"), data)
        self.assertEqual(response.status_code, 200)

    def test_team_edit_get_returns_200(self):
        response = self.client.get(reverse("team_edit", args=[self.team.pk]))
        self.assertEqual(response.status_code, 200)

    def test_team_edit_nonexistent_returns_404(self):
        response = self.client.get(reverse("team_edit", args=[9999]))
        self.assertEqual(response.status_code, 404)

    def test_team_delete_get_shows_confirm(self):
        response = self.client.get(reverse("team_delete", args=[self.team.pk]))
        self.assertEqual(response.status_code, 200)

    def test_team_delete_post_removes_team(self):
        pk = self.team.pk
        response = self.client.post(reverse("team_delete", args=[pk]))
        self.assertRedirects(response, reverse("team_list"))
        self.assertFalse(Team.objects.filter(pk=pk).exists())

    def test_team_delete_nonexistent_returns_404(self):
        response = self.client.get(reverse("team_delete", args=[9999]))
        self.assertEqual(response.status_code, 404)

    def test_team_list_search_by_name(self):
        response = self.client.get(reverse("team_list") + "?search=alice")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Alice")

    def test_team_list_filter_by_pair_type(self):
        response = self.client.get(reverse("team_list") + "?pair_type=double")
        self.assertEqual(response.status_code, 200)

    def test_team_edit_post_saves_changes(self):
        from players.models import Player
        p1 = make_player("EditP1", gender="M", owner=self.user)
        p2 = make_player("EditP2", gender="M", owner=self.user)
        team = Team.objects.create(player1=p1, player2=p2, pair_type="double")
        data = {"player1": p1.pk, "player2": p2.pk, "pair_type": "double"}
        response = self.client.post(reverse("team_edit", args=[team.pk]), data)
        self.assertRedirects(response, reverse("team_list"))


# ---------------------------------------------------------------------------
# player_clear_rest view
# ---------------------------------------------------------------------------

class PlayerClearRestTest(TestCase):
    def setUp(self):
        import datetime as dt
        from django.utils import timezone
        self.client = Client()
        self.user = make_user(username='restclub')
        self.client.force_login(self.user)
        # Create a player with rest_until set
        self.player = make_player("Resting Player", owner=self.user)
        self.player.rest_until = timezone.now() + dt.timedelta(minutes=20)
        self.player.save()

    def test_clear_rest_removes_rest_until(self):
        response = self.client.post(reverse("player_clear_rest", args=[self.player.pk]))
        self.assertRedirects(response, reverse("player_list"))
        self.player.refresh_from_db()
        self.assertIsNone(self.player.rest_until)

    def test_clear_rest_get_does_not_clear(self):
        response = self.client.get(reverse("player_clear_rest", args=[self.player.pk]))
        self.assertRedirects(response, reverse("player_list"))
        self.player.refresh_from_db()
        self.assertIsNotNone(self.player.rest_until)


# ---------------------------------------------------------------------------
# player_schedule_print view
# ---------------------------------------------------------------------------

class PlayerSchedulePrintTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = make_user(username='printplayer')
        self.client.force_login(self.user)
        self.player = make_player("PrintPlayer", owner=self.user)

    def test_player_schedule_print_returns_200(self):
        response = self.client.get(
            reverse("player_schedule_print", args=[self.player.pk])
        )
        self.assertEqual(response.status_code, 200)

    def test_player_schedule_print_404_for_other_owner(self):
        other = make_user("otheruser2")
        p = make_player("Other Player", owner=other)
        response = self.client.get(reverse("player_schedule_print", args=[p.pk]))
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.status_code, 200)

    def test_team_delete_post_removes_team(self):
        response = self.client.post(reverse("team_delete", args=[self.team.pk]))
        self.assertRedirects(response, reverse("team_list"))
        self.assertFalse(Team.objects.filter(pk=self.team.pk).exists())

    def test_team_delete_nonexistent_returns_404(self):
        response = self.client.post(reverse("team_delete", args=[9999]))
        self.assertEqual(response.status_code, 404)


# ---------------------------------------------------------------------------
# Player list – sorting + filtering
# ---------------------------------------------------------------------------

class PlayerListFilterSortTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = make_user(username='filterclub')
        self.client.force_login(self.user)
        self.alice = make_player("Alice", age=20, division="A", gender="K", owner=self.user)
        self.bob = make_player("Bob", age=18, division="B", gender="M", owner=self.user)
        self.charlie = make_player("Charlie", age=22, division="A", gender="M", owner=self.user)

    def test_filter_by_gender(self):
        response = self.client.get(reverse("player_list") + "?gender=M")
        self.assertContains(response, "Bob")
        self.assertNotContains(response, "Alice")

    def test_filter_by_search(self):
        response = self.client.get(reverse("player_list") + "?search=ali")
        self.assertContains(response, "Alice")
        self.assertNotContains(response, "Bob")

    def test_sort_by_name_desc(self):
        response = self.client.get(reverse("player_list") + "?sort=name&dir=desc")
        self.assertEqual(response.status_code, 200)
        names = [p.name for p in response.context['players']]
        self.assertEqual(names, sorted(names, reverse=True))

    def test_sort_by_age(self):
        response = self.client.get(reverse("player_list") + "?sort=age")
        self.assertEqual(response.status_code, 200)
        ages = [p.age for p in response.context['players']]
        self.assertEqual(ages, sorted(ages))

    def test_sort_invalid_field_falls_back_to_name(self):
        response = self.client.get(reverse("player_list") + "?sort=invalid_field")
        self.assertEqual(response.status_code, 200)

    def test_filter_by_division_and_gender_combined(self):
        response = self.client.get(reverse("player_list") + "?division=A&gender=M")
        self.assertContains(response, "Charlie")
        self.assertNotContains(response, "Alice")
        self.assertNotContains(response, "Bob")


# ---------------------------------------------------------------------------
# Player schedule print
# ---------------------------------------------------------------------------

class PlayerSchedulePrintTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = make_user(username='printclub')
        self.client.force_login(self.user)
        self.player = make_player("PrintPlayer", owner=self.user)

    def test_schedule_print_returns_200_no_matches(self):
        response = self.client.get(reverse("player_schedule_print", args=[self.player.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "PrintPlayer")

    def test_schedule_print_404_for_nonexistent(self):
        response = self.client.get(reverse("player_schedule_print", args=[9999]))
        self.assertEqual(response.status_code, 404)

    def test_schedule_print_shows_matches(self):
        import datetime as dt
        from django.utils import timezone
        from tournaments.models import Tournament, Division, Match
        tournament = Tournament.objects.create(
            name="Print T", date=dt.date(2026, 6, 1),
            division_model='mixed', scoring_model='best_of_3_21',
        )
        division = Division.objects.create(
            tournament=tournament, name="D", discipline='single',
        )
        team = Team.objects.create(player1=self.player, player2=None, name=self.player.name)
        other = make_player("Opponent")
        team2 = Team.objects.create(player1=other, player2=None, name=other.name)
        Match.objects.create(
            division=division, team1=team, team2=team2,
            match_number=1,
            scheduled_time=timezone.make_aware(dt.datetime(2026, 6, 1, 10, 0)),
            court='1', status='pending',
        )
        response = self.client.get(reverse("player_schedule_print", args=[self.player.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Opponent")


# ---------------------------------------------------------------------------
# Team model – save edge cases
# ---------------------------------------------------------------------------

class TeamModelSaveTest(TestCase):
    def test_single_player_team_uses_player_name(self):
        p = make_player("Solo")
        team = Team.objects.create(player1=p, player2=None)
        self.assertEqual(team.name, "Solo")

    def test_auto_name_two_players_alphabetical(self):
        p1 = make_player("Zara")
        p2 = make_player("Anna")
        team = Team.objects.create(player1=p1, player2=p2)
        # Name should include both
        self.assertIn("Zara", team.name)
        self.assertIn("Anna", team.name)

