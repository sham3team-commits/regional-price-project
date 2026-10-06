from django.urls import path

from . import views

app_name = "posts"

urlpatterns = [
    path("", views.PostListView.as_view(), name="post_list"),
    path("new/", views.PostEditView.as_view(), name="post_create"),
    path("<int:pk>/", views.PostEditView.as_view(), name="post_update"),
    path("<int:pk>/send-test/", views.SendTestView.as_view(), name="send_test"),
    path("generate/", views.GeneratorView.as_view(), name="generators"),
]
