from django.urls import path
from .views import (
    CleanupExpiredMediaView,
    NotificationListView,
    NotificationReadView,
    ReportCreateView,
    record_apk_download,
)

urlpatterns = [
    path('apk-download/', record_apk_download, name='apk-download-count'),
    path('notifications/', NotificationListView.as_view(), name='notification-list'),
    path('notifications/<int:pk>/read/', NotificationReadView.as_view(), name='notification-read'),
    path('report/', ReportCreateView.as_view(), name='report-create'),
    path('cleanup-media/', CleanupExpiredMediaView.as_view(), name='cleanup-media'),
]
