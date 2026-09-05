from django.urls import path
from . import views

urlpatterns = [
    path('', views.configuration_page_view, name='configuration_page'),
    path('run/', views.run_page_view, name='run_page'),
    path('results/', views.results_page_view, name='results_page'),
    path('logout/', views.logout_view, name='logout'),
]