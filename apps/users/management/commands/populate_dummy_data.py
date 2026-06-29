import random
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from apps.social.models import Follow, Buddy, CloseBuddy, CloseBuddyRequest
from apps.content.models import Category, Post

User = get_user_model()

class Command(BaseCommand):
    help = 'Populates the database with 100 dummy users and random relationships'

    def handle(self, *args, **options):
        first_names = ["James", "Mary", "Robert", "Patricia", "John", "Jennifer", "Michael", "Linda", "David", "Elizabeth", 
                       "William", "Barbara", "Richard", "Susan", "Joseph", "Jessica", "Thomas", "Sarah", "Christopher", "Karen",
                       "Charles", "Lisa", "Daniel", "Nancy", "Matthew", "Betty", "Anthony", "Margaret", "Mark", "Sandra",
                       "Donald", "Ashley", "Steven", "Kimberly", "Paul", "Emily", "Andrew", "Donna", "Joshua", "Michelle",
                       "Kenneth", "Dorothy", "Kevin", "Carol", "Brian", "Amanda", "George", "Melissa", "Timothy", "Deborah"]
        
        last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez",
                      "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin",
                      "Lee", "Perez", "Thompson", "White", "Harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson",
                      "Walker", "Young", "Allen", "King", "Wright", "Scott", "Torres", "Nguyen", "Hill", "Flores"]

        self.stdout.write("Creating 100 dummy users...")
        users = []
        for i in range(100):
            fname = random.choice(first_names)
            lname = random.choice(last_names)
            username = f"{fname.lower()}_{lname.lower()}_{random.randint(1000, 9999)}"
            email = f"{username}@example.com"
            
            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    'username': username,
                    'first_name': fname,
                    'last_name': lname,
                    'is_verified': True
                }
            )
            if created:
                user.set_password("password123")
                user.save()
            users.append(user)

        self.stdout.write(f"Successfully ensured 100 users exist.")

        self.stdout.write("Creating random follow relationships...")
        for user in users:
            # Randomly follow 5 to 15 other users
            targets = random.sample(users, random.randint(5, 15))
            for target in targets:
                if user != target:
                    Follow.objects.get_or_create(follower=user, following=target)

        # Buddies (mutual follows) are automatically created by signals.
        buddy_count = Buddy.objects.count()
        self.stdout.write(f"Mutual buddies automatically created: {buddy_count}")

        self.stdout.write("Creating some random posts for activity...")
        categories, _ = Category.objects.get_or_create(name="General", defaults={'slug': 'general'})
        if not isinstance(categories, Category):
            categories = Category.objects.first()

        for user in random.sample(users, 30): # 30 users create posts
            post = Post.objects.create(
                author=user,
                caption=f"Hello from {user.first_name}! This is a dummy post.",
                status='active'
            )
            post.categories.set([categories])

        self.stdout.write(self.style.SUCCESS("Database population complete!"))
