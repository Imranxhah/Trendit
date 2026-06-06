from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import OTPVerification

User = get_user_model()

from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework import exceptions

from django.utils import timezone
from datetime import timedelta
from .models import OTPVerification
import random
from phonenumber_field.serializerfields import PhoneNumberField

from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from django.conf import settings
from rest_framework_simplejwt.tokens import RefreshToken

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Overrides simplejwt's default serializer so users can log in with
    username, email, OR phone number — all sent under the 'username' key.

    Why: simplejwt's base class calls User.objects.get_by_natural_key() which
    only looks up by the USERNAME_FIELD ('username'). Sending an email would
    fail that lookup before DualLoginBackend ever gets a chance to run.
    We bypass it by calling django.contrib.auth.authenticate() directly.
    """

    # Tell simplejwt the input field is called 'username' (matches Flutter payload)
    username_field = 'username'

    def validate(self, attrs):
        from django.contrib.auth import authenticate

        identifier = attrs.get('username') or attrs.get(self.username_field, '')
        password = attrs.get('password', '')

        print(f"--- CustomTokenObtainPairSerializer: identifier='{identifier}' ---")

        # Authenticate via DualLoginBackend (handles username / email / phone)
        user = authenticate(
            request=self.context.get('request'),
            username=identifier,
            password=password,
        )

        if user is None:
            print(f"!!! Authentication failed for identifier: '{identifier}' !!!")
            raise exceptions.AuthenticationFailed(
                'No active account found with the given credentials.',
                code='no_active_account',
            )

        self.user = user
        print(f"--- User authenticated: {self.user.email}. is_verified: {self.user.is_verified}, is_banned: {self.user.is_banned} ---")

        # Block unverified users — send them a fresh OTP
        if not self.user.is_verified:
            OTPVerification.objects.filter(user=self.user).delete()
            otp_code = str(random.randint(100000, 999999))
            expires_at = timezone.now() + timedelta(minutes=10)
            OTPVerification.objects.create(
                user=self.user,
                otp_code=otp_code,
                expires_at=expires_at,
            )
            print(f"!!! Login failed: User is unverified. New OTP for {self.user.email} is {otp_code} !!!")
            raise exceptions.AuthenticationFailed(
                'ACCOUNT_NOT_VERIFIED',
                code='not_verified',
            )

        # Block banned users
        if self.user.is_banned:
            reason = self.user.ban_reason or 'No reason provided.'
            print(f"!!! Login failed: User {self.user.email} is banned. Reason: {reason} !!!")
            raise exceptions.AuthenticationFailed(
                f'Your account has been banned. Reason: {reason}',
                code='account_banned',
            )

        # Generate JWT token pair manually (bypasses simplejwt's own DB lookup)
        refresh = self.get_token(self.user)
        data = {
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'user_id': self.user.id,
        }

        print(f"--- Login successful for user: {self.user.email} ---")
        return data

class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    email = serializers.EmailField()
    phone_number = PhoneNumberField(required=False, allow_blank=True, allow_null=True)

    class Meta:
        model = User
        fields = ['id', 'email', 'password', 'phone_number']

    def validate_email(self, value):
        user = User.objects.filter(email=value).first()
        if user and user.is_verified:
            raise serializers.ValidationError("user with this email address already exists.")
        return value

    def validate_phone_number(self, value):
        if value:
            user = User.objects.filter(phone_number=value).first()
            if user and user.is_verified:
                raise serializers.ValidationError("user with this phone number already exists.")      
            return value
        return None # Return None instead of '' to avoid uniqueness issues in DB

    def create(self, validated_data):
        email = validated_data['email']
        phone_number = validated_data.get('phone_number')

        # If an unverified user exists with this email or phone, delete them so they can restart registration cleanly
        existing_user = User.objects.filter(email=email, is_verified=False).first()
        if not existing_user and phone_number:
            existing_user = User.objects.filter(phone_number=phone_number, is_verified=False).first() 

        if existing_user:
            existing_user.delete()

        base_username = email.split('@')[0]
        username = base_username

        # Ensure username is unique
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}{counter}"
            counter += 1

        user = User.objects.create_user(
            username=username,
            email=email,
            password=validated_data['password'],
            phone_number=phone_number,
            is_verified=False  # Block login until verified
        )
        return user

class OTPVerifySerializer(serializers.Serializer):
    email = serializers.CharField() # accept email, username, or phone
    otp_code = serializers.CharField(max_length=6)

class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'phone_number', 'email', 'first_name', 'last_name', 'profile_picture', 'has_completed_profile']
        read_only_fields = ['id', 'email', 'has_completed_profile'] # Usually email shouldn't be changed through simple profile update without verification

    def update(self, instance, validated_data):
        # Perform standard update
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        # Check if profile is complete
        # We check both the validated_data (new changes) and the instance (existing data)
        first_name = validated_data.get('first_name', instance.first_name)
        last_name = validated_data.get('last_name', instance.last_name)
        phone_number = validated_data.get('phone_number', instance.phone_number)

        if first_name and last_name and phone_number:
            instance.has_completed_profile = True

        instance.save()
        return instance

class ForgotPasswordRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        if not User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Account with this email does not exist.")
        return value

class ForgotPasswordResetSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp_code = serializers.CharField(max_length=6)
    new_password = serializers.CharField(write_only=True, min_length=6)


class UserProfileDetailSerializer(serializers.ModelSerializer):
    profile_picture = serializers.SerializerMethodField()
    followers_count = serializers.SerializerMethodField()
    following_count = serializers.SerializerMethodField()
    buddies_count = serializers.SerializerMethodField()
    total_posts = serializers.SerializerMethodField()
    is_following = serializers.SerializerMethodField()
    is_followed_by = serializers.SerializerMethodField()
    is_buddy = serializers.SerializerMethodField()
    is_close_buddy = serializers.SerializerMethodField()
    close_buddy_request_status = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'username', 'first_name', 'last_name', 'profile_picture',
            'followers_count', 'following_count', 'buddies_count', 'total_posts',
            'is_following', 'is_followed_by', 'is_buddy', 'is_close_buddy', 'close_buddy_request_status',
            'has_completed_profile'
        ]

    def get_profile_picture(self, obj):
        if obj.profile_picture:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.profile_picture.url)
            return obj.profile_picture.url
        return None

    def get_followers_count(self, obj):
        return obj.followers.count()

    def get_following_count(self, obj):
        return obj.following.count()

    def get_buddies_count(self, obj):
        from django.db.models import Q
        from apps.social.models import Buddy
        return Buddy.objects.filter(Q(user1=obj) | Q(user2=obj)).count()

    def get_total_posts(self, obj):
        return obj.posts.filter(is_media_deleted=False).count()

    def get_is_following(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            from apps.social.models import Follow
            return Follow.objects.filter(follower=request.user, following=obj).exists()
        return False

    def get_is_followed_by(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            from apps.social.models import Follow
            return Follow.objects.filter(follower=obj, following=request.user).exists()
        return False

    def get_is_buddy(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            from apps.social.models import Buddy
            u1, u2 = sorted([request.user.id, obj.id])
            return Buddy.objects.filter(user1_id=u1, user2_id=u2).exists()
        return False

    def get_is_close_buddy(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            from apps.social.models import CloseBuddy
            return CloseBuddy.objects.filter(user=request.user, buddy=obj).exists()
        return False

    def get_close_buddy_request_status(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            from apps.social.models import CloseBuddyRequest
            # Check sent request
            req_sent = CloseBuddyRequest.objects.filter(sender=request.user, receiver=obj).first()
            if req_sent:
                return f"sent_{req_sent.status}" # sent_pending, sent_accepted, sent_rejected
            
            # Check received request
            req_received = CloseBuddyRequest.objects.filter(sender=obj, receiver=request.user).first()
            if req_received:
                return f"received_{req_received.status}" # received_pending, received_accepted, received_rejected
        return None

class GoogleLoginSerializer(serializers.Serializer):
    id_token = serializers.CharField()

    def validate(self, attrs):
        token = attrs.get('id_token')
        
        # We need to collect the allowed client IDs
        allowed_client_ids = []
        if settings.GOOGLE_CLIENT_ID_WEB:
            allowed_client_ids.append(settings.GOOGLE_CLIENT_ID_WEB)
        if settings.GOOGLE_CLIENT_ID_IOS:
            allowed_client_ids.append(settings.GOOGLE_CLIENT_ID_IOS)
        if settings.GOOGLE_CLIENT_ID_ANDROID:
            allowed_client_ids.append(settings.GOOGLE_CLIENT_ID_ANDROID)

        if not allowed_client_ids:
            raise exceptions.AuthenticationFailed("Google authentication is not configured on the server.")

        try:
            # Verify the token
            # It will raise ValueError if the token is invalid, expired, or has a wrong audience
            idinfo = id_token.verify_oauth2_token(
                token, 
                google_requests.Request()
                # If we don't pass audience here, we must verify it manually below, 
                # or we can just let google-auth verify it by not specifying a single audience,
                # but instead checking if idinfo['aud'] is in our allowed list.
            )

            # verify_oauth2_token defaults to checking against a single audience if provided.
            # Since we have multiple, we verify the audience manually.
            if idinfo['aud'] not in allowed_client_ids:
                raise exceptions.AuthenticationFailed('Could not verify audience.')

            if idinfo['iss'] not in ['accounts.google.com', 'https://accounts.google.com']:
                raise exceptions.AuthenticationFailed('Wrong issuer.')
            
            email = idinfo.get('email')
            if not email:
                raise exceptions.AuthenticationFailed('Email not provided by Google.')
                
            # Get or create the user
            user = User.objects.filter(email=email).first()
            if not user:
                # Create a new user
                base_username = email.split('@')[0]
                username = base_username
                counter = 1
                while User.objects.filter(username=username).exists():
                    username = f"{base_username}{counter}"
                    counter += 1

                first_name = idinfo.get('given_name', '')
                last_name = idinfo.get('family_name', '')
                
                # Note: We can also download the profile picture if we want, but for now we'll just create the user.
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    first_name=first_name,
                    last_name=last_name,
                    is_verified=True # Google already verified the email
                )
                user.set_unusable_password()
                user.save()
            else:
                if user.is_banned:
                    reason = user.ban_reason or 'No reason provided.'
                    raise exceptions.AuthenticationFailed(f'Your account has been banned. Reason: {reason}', code='account_banned')
                if not user.is_verified:
                    user.is_verified = True
                    user.save()

            # Generate tokens
            refresh = RefreshToken.for_user(user)
            self.user = user
            
            return {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
                'user_id': user.id,
            }

        except ValueError as e:
            # Invalid token
            raise exceptions.AuthenticationFailed(f"Invalid Google token: {str(e)}")

