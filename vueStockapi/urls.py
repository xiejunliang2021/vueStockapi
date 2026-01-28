"""
URL configuration for vueStockapi project.

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
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView
from rest_framework_simplejwt.views import TokenRefreshView
from . import auth_views

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # 认证相关 API
    path('api/auth/login/', auth_views.login, name='login'),
    path('api/auth/user/', auth_views.get_user_info, name='user-info'),
    path('api/auth/logout/', auth_views.logout, name='logout'),
    path('api/auth/refresh/', TokenRefreshView.as_view(), name='token-refresh'),
    
    # API 文档
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
    
    # 业务 API
    path('api/basics/', include('basic.urls')),
    path('api/backtest/', include('backtest.urls')),
    path('api/weighing/', include('weighing.urls')),
]

# 静态文件和媒体文件配置
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
