from django.urls import path
from . import views

urlpatterns = [
    # Auth
    path('', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('logout/', views.logout_view, name='logout'),
    
    # Dashboard
    path('dashboard/', views.dashboard, name='dashboard'),
    
    # Datasets
    path('datasets/', views.datasets_list, name='datasets_list'),
    path('datasets/upload/', views.upload_dataset, name='upload_dataset'),
    path('datasets/load-sample/', views.load_sample_dataset, name='load_sample_dataset'),
    path('datasets/<int:dataset_id>/', views.dataset_detail, name='dataset_detail'),
    path('datasets/<int:dataset_id>/preview/', views.dataset_preview, name='dataset_preview'),
    path('datasets/<int:dataset_id>/profile/', views.profile_dataset, name='profile_dataset'),
    path('datasets/<int:dataset_id>/analyze/', views.analyze_dataset, name='analyze_dataset'),
    path('datasets/<int:dataset_id>/export/', views.export_dataset, name='export_dataset'),
    path('datasets/<int:dataset_id>/create-chart/', views.create_visualization, name='create_visualization'),
    
    # Cleaning
    path('recommendations/<int:recommendation_id>/details/', views.get_issue_details, name='get_issue_details'),
    path('recommendations/<int:recommendation_id>/apply/', views.apply_cleaning, name='apply_cleaning'),
    path('datasets/<int:dataset_id>/apply-batch/', views.apply_batch_cleaning, name='apply_batch_cleaning'),
]
