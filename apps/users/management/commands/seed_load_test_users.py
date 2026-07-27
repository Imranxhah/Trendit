import re

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.users.models import Profile


FIRST_NAMES = (
    "Aariz",
    "Adeel",
    "Ahsan",
    "Ahmed",
    "Ali",
    "Ammar",
    "Arham",
    "Asad",
    "Bilal",
    "Daniyal",
    "Fahad",
    "Farhan",
    "Hamza",
    "Haris",
    "Hassan",
    "Ibrahim",
    "Imran",
    "Junaid",
    "Kamran",
    "Kashif",
    "Moiz",
    "Muhammad",
    "Mustafa",
    "Noman",
    "Omar",
    "Osama",
    "Rehan",
    "Saad",
    "Salman",
    "Shahzaib",
    "Usman",
    "Abeer",
    "Aiman",
    "Aisha",
    "Aleena",
    "Alina",
    "Amna",
    "Anaya",
    "Anum",
    "Areeba",
    "Ayesha",
    "Dua",
    "Eman",
    "Fatima",
    "Hania",
    "Hira",
    "Iqra",
    "Laiba",
    "Maham",
    "Mahnoor",
    "Maryam",
    "Mehwish",
    "Minal",
    "Nida",
    "Noor",
    "Rabia",
    "Sana",
    "Sara",
    "Sobia",
    "Zainab",
    "Zara",
)

LAST_NAMES = (
    "Abbasi",
    "Afridi",
    "Ahmed",
    "Akhtar",
    "Ali",
    "Ansari",
    "Awan",
    "Baloch",
    "Bhatti",
    "Butt",
    "Chaudhry",
    "Dar",
    "Farooq",
    "Gill",
    "Gondal",
    "Hashmi",
    "Hayat",
    "Hussain",
    "Iqbal",
    "Jafri",
    "Kakar",
    "Kazmi",
    "Khalid",
    "Khan",
    "Khattak",
    "Khawaja",
    "Lodhi",
    "Malik",
    "Marwat",
    "Masood",
    "Mirza",
    "Mughal",
    "Naqvi",
    "Niazi",
    "Qazi",
    "Qureshi",
    "Rana",
    "Raza",
    "Rizvi",
    "Saeed",
    "Sheikh",
    "Shah",
    "Siddiqui",
    "Tanveer",
    "Tariq",
    "Usmani",
    "Warraich",
    "Yousaf",
    "Zaidi",
    "Zubair",
)

EMAIL_DOMAINS = ("example.com", "example.net", "example.org")
PREFIX_PATTERN = re.compile(r"^loadtest(?:_[a-z0-9]+)*$")


def build_identity(prefix, index, width):
    first_name = FIRST_NAMES[(index - 1) % len(FIRST_NAMES)]
    last_name = LAST_NAMES[
        ((index - 1) // len(FIRST_NAMES)) % len(LAST_NAMES)
    ]
    sequence = f"{index:0{width}d}"
    first_slug = first_name.lower()
    last_slug = last_name.lower()
    return {
        "username": f"{prefix}_{first_slug}_{last_slug}_{sequence}",
        "email": (
            f"{first_slug}.{last_slug}.{sequence}@"
            f"{EMAIL_DOMAINS[(index - 1) % len(EMAIL_DOMAINS)]}"
        ),
        "phone_number": f"+92355{index:07d}",
        "first_name": first_name,
        "last_name": last_name,
    }


class Command(BaseCommand):
    help = (
        "Create deterministic, non-login users for production search/load testing, "
        "or remove a previously created load-test dataset."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--count",
            type=int,
            default=3000,
            help="Target number of users in the dataset (default: 3000).",
        )
        parser.add_argument(
            "--prefix",
            default="loadtest",
            help="Dataset marker used in usernames (default: loadtest).",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=500,
            help="Database bulk insert batch size (default: 500).",
        )
        parser.add_argument(
            "--delete",
            action="store_true",
            help="Delete every user belonging to the selected prefix.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would change without writing to the database.",
        )
        parser.add_argument(
            "--yes",
            action="store_true",
            help="Required confirmation for create and delete operations.",
        )

    def handle(self, *args, **options):
        count = options["count"]
        prefix = options["prefix"].strip().lower()
        batch_size = options["batch_size"]
        should_delete = options["delete"]
        dry_run = options["dry_run"]

        if not PREFIX_PATTERN.fullmatch(prefix):
            raise CommandError(
                "Prefix must be 'loadtest' or start with 'loadtest_' and contain "
                "only lowercase letters, numbers, and underscores."
            )
        if count < 1 or count > 50000:
            raise CommandError("Count must be between 1 and 50000.")
        if batch_size < 1 or batch_size > 5000:
            raise CommandError("Batch size must be between 1 and 5000.")
        if not dry_run and not options["yes"]:
            raise CommandError(
                "Refusing to change the database without --yes. Use --dry-run "
                "to inspect the operation first."
            )

        User = get_user_model()
        dataset_users = User.objects.filter(username__startswith=f"{prefix}_")

        if should_delete:
            existing_count = dataset_users.count()
            if dry_run:
                self.stdout.write(
                    f"Dry run: would delete {existing_count} users with prefix "
                    f"'{prefix}_'."
                )
                return

            with transaction.atomic():
                dataset_users.delete()
            self.stdout.write(
                self.style.SUCCESS(
                    f"Deleted {existing_count} load-test users with prefix "
                    f"'{prefix}_'."
                )
            )
            return

        width = max(4, len(str(count)))
        identities = [
            build_identity(prefix, index, width)
            for index in range(1, count + 1)
        ]
        target_usernames = [identity["username"] for identity in identities]
        unexpected_count = dataset_users.exclude(
            username__in=target_usernames
        ).count()
        if unexpected_count:
            raise CommandError(
                f"Found {unexpected_count} users from an older '{prefix}_' "
                "dataset. Delete that dataset before creating the new one."
            )

        existing_usernames = set(
            User.objects.filter(username__in=target_usernames).values_list(
                "username", flat=True
            )
        )
        missing_identities = [
            identity
            for identity in identities
            if identity["username"] not in existing_usernames
        ]

        expected_emails = [
            identity["email"] for identity in missing_identities
        ]
        conflicting_emails = list(
            User.objects.filter(email__in=expected_emails)
            .values_list("email", flat=True)[:5]
        )
        if conflicting_emails:
            raise CommandError(
                "Cannot create the dataset because reserved load-test emails are "
                f"already used: {', '.join(conflicting_emails)}"
            )

        expected_phone_numbers = [
            identity["phone_number"] for identity in missing_identities
        ]
        conflicting_phone_numbers = list(
            User.objects.filter(phone_number__in=expected_phone_numbers)
            .values_list("phone_number", flat=True)[:5]
        )
        if conflicting_phone_numbers:
            raise CommandError(
                "Cannot create the dataset because reserved synthetic phone "
                "numbers are already used: "
                f"{', '.join(map(str, conflicting_phone_numbers))}"
            )

        if dry_run:
            self.stdout.write(
                f"Dry run: target={count}, existing={len(existing_usernames)}, "
                f"would_create={len(missing_identities)}, prefix='{prefix}_'."
            )
            return

        user_objects = []
        for identity in missing_identities:
            user_objects.append(
                User(
                    username=identity["username"],
                    email=identity["email"],
                    phone_number=identity["phone_number"],
                    first_name=identity["first_name"],
                    last_name=identity["last_name"],
                    password=make_password(None),
                    is_active=True,
                    is_verified=True,
                    has_completed_profile=True,
                )
            )

        with transaction.atomic():
            if user_objects:
                User.objects.bulk_create(user_objects, batch_size=batch_size)

            dataset_user_ids = list(
                User.objects.filter(username__in=target_usernames).values_list(
                    "id", flat=True
                )
            )
            profile_user_ids = set(
                Profile.objects.filter(user_id__in=dataset_user_ids).values_list(
                    "user_id", flat=True
                )
            )
            Profile.objects.bulk_create(
                [
                    Profile(user_id=user_id)
                    for user_id in dataset_user_ids
                    if user_id not in profile_user_ids
                ],
                batch_size=batch_size,
                ignore_conflicts=True,
            )

        final_count = User.objects.filter(username__in=target_usernames).count()
        self.stdout.write(
            self.style.SUCCESS(
                f"Load-test dataset ready: target={count}, created="
                f"{len(user_objects)}, total={final_count}, prefix='{prefix}_'."
            )
        )
