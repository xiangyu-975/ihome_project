from django.conf.urls import url

from . import views

urlpatterns = [
    url('^users$', views.RegisterView.as_view()),
    url('^session$', views.LoginView.as_view()),
]
