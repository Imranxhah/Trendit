"""
URL configuration for trendit_backend project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from apps.core.views import landing_page, post_share_landing
from apps.social.views import android_asset_links, community_invite_landing

urlpatterns = [
    path('', landing_page, name='landing-page'),
    path('.well-known/assetlinks.json', android_asset_links, name='android-asset-links'),
    path('post/<int:post_id>', post_share_landing, name='post-share-landing'),
    path('community-invite/<str:token>', community_invite_landing, name='community-invite-landing'),
    path('admin/', admin.site.urls),
    path('api/users/', include('apps.users.urls')),
    path('api/content/', include('apps.content.urls')),
    path('api/social/', include('apps.social.urls')),
    path('api/core/', include('apps.core.urls')),
]

# Always serve media files (PythonAnywhere handles static via web app config)
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
