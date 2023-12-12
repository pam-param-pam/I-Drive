from django.conf import settings
from django.conf.urls.static import static
from django.urls import path, include
import oauth2_provider.views as oauth2_views

from website import views
from website.views import ApiEndpoint

oauth2_endpoint_views = [
    path('authorize/', oauth2_views.AuthorizationView.as_view(), name="authorize"),
    path('token/', oauth2_views.TokenView.as_view(), name="token"),
    path('revoke-token/', oauth2_views.RevokeTokenView.as_view(), name="revoke-token"),
]

if settings.DEBUG:
    # OAuth2 Application Management endpoints
    oauth2_endpoint_views += [
        path('applications/', oauth2_views.ApplicationList.as_view(), name="list"),
        path('applications/register/', oauth2_views.ApplicationRegistration.as_view(), name="register"),
        path('applications/<pk>/', oauth2_views.ApplicationDetail.as_view(), name="detail"),
        path('applications/<pk>/delete/', oauth2_views.ApplicationDelete.as_view(), name="delete"),
        path('applications/<pk>/update/', oauth2_views.ApplicationUpdate.as_view(), name="update"),
    ]

    # OAuth2 Token Management endpoints
    oauth2_endpoint_views += [
        path('authorized-tokens/', oauth2_views.AuthorizedTokensListView.as_view(), name="authorized-token-list"),
        path('authorized-tokens/<pk>/delete/', oauth2_views.AuthorizedTokenDeleteView.as_view(),
            name="authorized-token-delete"),
    ]

urlpatterns = [
        path("", views.index, name="index"),
        path("upload", views.upload_file, name="upload"),
        path("test", views.test, name="test"),
        path("download/<file_id>", views.download, name="download"),
        path("stream/<file_id>/key", views.streamkey, name="stream key"),
        path("stream/<file_id>", views.get_m3u8, name="get m3u8 playlist"),
        path('o/', include((oauth2_endpoint_views, 'oauth2_provider'), namespace="oauth2_provider")),
        path('api/hello', ApiEndpoint.as_view()),  # an example resource endpoint
] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
