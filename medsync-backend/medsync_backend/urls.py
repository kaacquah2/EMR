from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from api.views.root_views import api_root, favicon

urlpatterns = [
    path("", api_root),
    path("favicon.ico", favicon),
    path("admin/", admin.site.urls),
    path("api/v1/", include("api.urls")),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    try:
        import debug_toolbar
        urlpatterns.insert(0, path("__debug__/", include("debug_toolbar.urls")))
    except ImportError:
        pass
