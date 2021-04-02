from django.conf.urls import url

from . import views

urlpatterns = [
    url('^users$', views.RegisterView.as_view()),
    url('^session$', views.LoginView.as_view()),
    url('^user$', views.UserInfoView.as_view()),
    url('^user/avatar$', views.AvatarView.as_view()),
    url('^user/name$', views.ModifyNameView.as_view()),
    url('^user/auth$',views.UserAuthView.as_view()),
]
