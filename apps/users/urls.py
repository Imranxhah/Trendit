from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
    RegisterView, VerifyOTPView, UserProfileView, UserProfileDetailView,
    BanUserView, UnbanUserView, ForgotPasswordRequestView, ForgotPasswordResetView,
    RecordViolationView, GoogleLoginView
)
from .serializers import CustomTokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView
from apps.social.views import UserSearchView


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer


urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('verify-otp/', VerifyOTPView.as_view(), name='verify-otp'),
    path('login/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('google-login/', GoogleLoginView.as_view(), name='google_login'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('profile/', UserProfileView.as_view(), name='user-profile'),
    path('profile/<int:user_id>/', UserProfileDetailView.as_view(), name='user-profile-detail'),
    path('search/', UserSearchView.as_view(), name='user-search'),

    # Forgot password
    path('forgot-password/', ForgotPasswordRequestView.as_view(), name='forgot-password'),
    path('reset-password/', ForgotPasswordResetView.as_view(), name='reset-password'),

    # Admin-only ban / unban
    path('ban/<int:user_id>/', BanUserView.as_view(), name='ban-user'),
    path('unban/<int:user_id>/', UnbanUserView.as_view(), name='unban-user'),
    
    # Violations / Strikes
    path('violations/', RecordViolationView.as_view(), name='record-violation'),
]
