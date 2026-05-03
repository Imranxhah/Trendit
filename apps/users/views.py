from rest_framework import status, generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from django.utils import timezone
from datetime import timedelta
from django.shortcuts import get_object_or_404
import random
from .models import User, OTPVerification
from .serializers import (
    UserRegistrationSerializer, 
    OTPVerifySerializer, 
    UserProfileSerializer,
    ForgotPasswordRequestSerializer,
    ForgotPasswordResetSerializer
)


class UserProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


class RegisterView(generics.CreateAPIView):
    serializer_class = UserRegistrationSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        # Generate 6-digit OTP
        otp_code = str(random.randint(100000, 999999))
        expires_at = timezone.now() + timedelta(minutes=10)
        
        OTPVerification.objects.create(
            user=user,
            otp_code=otp_code,
            expires_at=expires_at
        )
        
        # Print OTP to console (as requested)
        print(f"DEBUG: OTP for {user.email} is {otp_code}")
        
        return Response({
            "message": "User registered successfully. Please verify your email with the OTP sent.",
            "email": user.email
        }, status=status.HTTP_201_CREATED)


from django.db.models import Q

class VerifyOTPView(APIView):
    def post(self, request):
        serializer = OTPVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        email_or_identifier = serializer.validated_data['email'] # Using the field name from serializer, but it might contain phone/username
        otp_code = serializer.validated_data['otp_code']
        
        try:
            user = User.objects.get(
                Q(email=email_or_identifier) | 
                Q(username=email_or_identifier) | 
                Q(phone_number=email_or_identifier)
            )
            otp_obj = OTPVerification.objects.filter(
                user=user, 
                otp_code=otp_code,
                expires_at__gt=timezone.now()
            ).latest('created_at')
            
            user.is_verified = True
            user.save()
            
            # Delete the OTP after successful verification
            otp_obj.delete()
            
            return Response({"message": "Account verified successfully. You can now login."}, status=status.HTTP_200_OK)
            
        except (User.DoesNotExist, OTPVerification.DoesNotExist, User.MultipleObjectsReturned):
            return Response({"error": "Invalid or expired OTP, or account not found."}, status=status.HTTP_400_BAD_REQUEST)


class ForgotPasswordRequestView(APIView):
    def post(self, request):
        serializer = ForgotPasswordRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
            
        email = serializer.validated_data['email']
        user = User.objects.get(email=email)
        
        # Invalidate old OTPs for this user
        OTPVerification.objects.filter(user=user).delete()
        
        # Generate 6-digit OTP
        otp_code = str(random.randint(100000, 999999))
        expires_at = timezone.now() + timedelta(minutes=10)
        
        OTPVerification.objects.create(
            user=user,
            otp_code=otp_code,
            expires_at=expires_at
        )
        
        # Print OTP to console for debugging
        print(f"DEBUG: Password Reset OTP for {user.email} is {otp_code}")
        
        return Response({
            "message": "Password reset OTP sent to email.",
            "email": user.email
        }, status=status.HTTP_200_OK)


class ForgotPasswordResetView(APIView):
    def post(self, request):
        serializer = ForgotPasswordResetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
            
        email = serializer.validated_data['email']
        otp_code = serializer.validated_data['otp_code']
        new_password = serializer.validated_data['new_password']
        
        try:
            user = User.objects.get(email=email)
            otp_obj = OTPVerification.objects.filter(
                user=user, 
                otp_code=otp_code,
                expires_at__gt=timezone.now()
            ).latest('created_at')
            
            # Reset the password
            user.set_password(new_password)
            user.save()
            
            # Delete the OTP after successful verification
            otp_obj.delete()
            
            return Response({"message": "Password has been reset successfully. You can now login."}, status=status.HTTP_200_OK)
            
        except (User.DoesNotExist, OTPVerification.DoesNotExist):
            return Response({"error": "Invalid or expired OTP."}, status=status.HTTP_400_BAD_REQUEST)


# ─── Admin-only Ban / Unban Views ────────────────────────────────────────────

class BanUserView(APIView):
    """
    POST /users/ban/<user_id>/
    Admin-only. Bans a user and optionally records a reason.
    Body: { "ban_reason": "optional reason text" }
    """
    permission_classes = [permissions.IsAdminUser]

    def post(self, request, user_id):
        user = get_object_or_404(User, pk=user_id)

        if user.is_superuser:
            return Response(
                {"error": "Superusers cannot be banned."},
                status=status.HTTP_403_FORBIDDEN
            )

        if user.is_banned:
            return Response(
                {"message": f"User '{user.username}' is already banned."},
                status=status.HTTP_200_OK
            )

        user.is_banned = True
        user.ban_reason = request.data.get('ban_reason', '')
        user.save(update_fields=['is_banned', 'ban_reason'])

        return Response({
            "message": f"User '{user.username}' has been banned.",
            "ban_reason": user.ban_reason or "No reason provided."
        }, status=status.HTTP_200_OK)


class UnbanUserView(APIView):
    """
    POST /users/unban/<user_id>/
    Admin-only. Removes the ban from a user.
    """
    permission_classes = [permissions.IsAdminUser]

    def post(self, request, user_id):
        user = get_object_or_404(User, pk=user_id)

        if not user.is_banned:
            return Response(
                {"message": f"User '{user.username}' is not banned."},
                status=status.HTTP_200_OK
            )

        user.is_banned = False
        user.ban_reason = None
        user.save(update_fields=['is_banned', 'ban_reason'])

        return Response({
            "message": f"User '{user.username}' has been unbanned."
        }, status=status.HTTP_200_OK)
