from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from django.db.models import Q

User = get_user_model()

class DualLoginBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None:
            username = kwargs.get(User.USERNAME_FIELD) or kwargs.get('email')
        
        try:
            # Check if input matches username, email, or phone_number
            user = User.objects.get(
                Q(username=username) | 
                Q(email=username) | 
                Q(phone_number=username)
            )
            if user.check_password(password):
                return user
        except User.DoesNotExist:
            return None
        return None
