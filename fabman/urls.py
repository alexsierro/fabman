"""fabman URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.1/topics/http/urls/
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

from legacy import views as legacy_views

urlpatterns = [
    path('members/', include('members.urls')),
    path('invoicing/', include('invoicing.urls')),
    path('admin/', admin.site.urls),

    # legacy fablog api
    path('user/<uid>', legacy_views.user),
    path('user2/<uid>', legacy_views.user2),
    path('usage/<resource>/<user>/<time>', legacy_views.usage),
    path('usage/<resource>/<user>/<time>/<project>', legacy_views.usage),
    path('items/', legacy_views.items),
    path('check/<api_key>/<name>/<surname>', legacy_views.items),
]
