from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('update', views.update, name='update'),
    path('ajax_login', views.ajax_login, name='ajax_login'),
    path('ajax_logout', views.ajax_logout, name='ajax_logout'),
]
