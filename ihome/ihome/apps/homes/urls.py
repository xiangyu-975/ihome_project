from django.conf.urls import url

from . import views

urlpatterns = [
    url('^areas$', views.AreaView.as_view()),
    url('^houses$', views.HouseView.as_view()),
    url('^user/houses$', views.UserHouseView.as_view()),
    url('^houses/(?P<house_id>\d+)/images$', views.HouseImageView.as_view()),
]
