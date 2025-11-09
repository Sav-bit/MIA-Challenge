from django.urls import path
from . import views

urlpatterns = [
    path('calculate/', views.calculate_dice, name='calculate_dice'),
]
