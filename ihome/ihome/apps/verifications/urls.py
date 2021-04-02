from django.conf.urls import url
from . import views

urlpatterns = [
    url(r'^imagecode$', views.ImageCodeView.as_view()),
    url(r'^sms$', views.SMSCodeView.as_view())

]
