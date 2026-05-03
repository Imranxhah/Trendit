from django.urls import path
from .views import NotificationListView, NotificationReadView, ReportCreateView

urlpatterns = [
    path('notifications/', NotificationListView.as_view(), name='notification-list'),
    path('notifications/<int:pk>/read/', NotificationReadView.as_view(), name='notification-read'),
    path('report/', ReportCreateView.as_view(), name='report-create'),
]
