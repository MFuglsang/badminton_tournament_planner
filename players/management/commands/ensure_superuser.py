import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Creates a superuser from environment variables if one does not already exist."

    def handle(self, *args, **options):
        User = get_user_model()
        username = os.environ.get("DJANGO_SUPERUSER_USERNAME", "admin")
        password = os.environ.get("DJANGO_SUPERUSER_PASSWORD", "")
        email = os.environ.get("DJANGO_SUPERUSER_EMAIL", "")

        if not password:
            self.stdout.write(
                self.style.WARNING(
                    "DJANGO_SUPERUSER_PASSWORD is not set — skipping superuser creation."
                )
            )
            return

        if User.objects.filter(username=username).exists():
            user = User.objects.get(username=username)
            if not user.has_usable_password():
                user.set_password(password)
                user.save()
                self.stdout.write(self.style.SUCCESS(f'Superuser "{username}" had no usable password — password set.'))
            else:
                self.stdout.write(f'Superuser "{username}" already exists — skipping.')
        else:
            user = User.objects.create_superuser(username=username, email=email, password=password)
            self.stdout.write(self.style.SUCCESS(f'Superuser "{username}" created successfully.'))

        # Ensure the superuser always has an unlimited profile
        from tournaments.models import UserProfile
        profile, profile_created = UserProfile.objects.get_or_create(
            user=user,
            defaults={'tier': 'unlimited'},
        )
        if not profile_created and profile.tier != 'unlimited':
            profile.tier = 'unlimited'
            profile.save(update_fields=['tier'])
            self.stdout.write(self.style.SUCCESS(f'Superuser "{username}" profile upgraded to unlimited.'))
        elif profile_created:
            self.stdout.write(self.style.SUCCESS(f'Superuser "{username}" profile created with unlimited tier.'))
