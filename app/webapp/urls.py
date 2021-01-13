from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('analyze', views.analyze, name='analyze'),
    path('finalize', views.finalize, name='finalize'),
    path('list', views.list, name='list'),
    path('show/<uuid:job_id>', views.show, name='show'),
    path('new_count_text', views.new_count_text, name='new_count_text'),
]
