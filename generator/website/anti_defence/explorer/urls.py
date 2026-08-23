from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('protein_list/', views.protein_list, name='protein_list'),
    path('details/<str:pk>/', views.details, name='details'),
    path('serve_blob/<str:pk>/<str:column_name>/', views.serve_blob_as_file, name='serve_blob_as_file'),
    path('euk_virus_homologs/<str:pk>/', views.serve_euk_virus_homologs, name='serve_euk_virus_homologs'),
]
