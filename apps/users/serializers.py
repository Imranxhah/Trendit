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
        }

        print(f"--- Login successful for user: {self.user.email} ---")
        return data

class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    email = serializers.EmailField()
    phone_number = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    class Meta:
        model = User
        fields = ['email', 'password', 'phone_number']

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
        fields = ['username', 'phone_number', 'email']
        read_only_fields = ['email'] # Usually email shouldn't be changed through simple profile update without verification

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
