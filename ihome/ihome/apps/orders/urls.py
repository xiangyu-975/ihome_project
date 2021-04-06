from django.conf.urls import url

from . import views

urlpatterns = [
    url('^orders$', views.OrderView.as_view()),
    url('^orders/(?P<order_id>\d+)/status$', views.OrdersStatusView.as_view()),
]
