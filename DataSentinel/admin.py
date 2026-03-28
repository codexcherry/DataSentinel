from django.contrib import admin
from .models import (
    Dataset, DatasetVersion, DataProfile, CleaningRecommendation,
    CleaningLog, AnalysisResult, AuditLog
)

@admin.register(Dataset)
class DatasetAdmin(admin.ModelAdmin):
    list_display = ['name', 'user', 'file_type', 'rows_count', 'columns_count', 'status', 'created_at']
    list_filter = ['status', 'file_type', 'created_at']
    search_fields = ['name', 'original_filename', 'user__username']
    readonly_fields = ['created_at', 'updated_at']

@admin.register(DatasetVersion)
class DatasetVersionAdmin(admin.ModelAdmin):
    list_display = ['dataset', 'version_number', 'rows_count', 'columns_count', 'created_at']
    list_filter = ['created_at']
    search_fields = ['dataset__name', 'description']

@admin.register(DataProfile)
class DataProfileAdmin(admin.ModelAdmin):
    list_display = ['dataset', 'created_at']
    search_fields = ['dataset__name']

@admin.register(CleaningRecommendation)
class CleaningRecommendationAdmin(admin.ModelAdmin):
    list_display = ['column_name', 'issue_type', 'recommended_action', 'priority', 'is_applied', 'created_at']
    list_filter = ['issue_type', 'recommended_action', 'priority', 'is_applied']
    search_fields = ['column_name', 'issue_description']

@admin.register(CleaningLog)
class CleaningLogAdmin(admin.ModelAdmin):
    list_display = ['dataset', 'action_taken', 'column_name', 'rows_affected', 'applied_by', 'applied_at']
    list_filter = ['action_taken', 'applied_at']
    search_fields = ['dataset__name', 'column_name']

@admin.register(AnalysisResult)
class AnalysisResultAdmin(admin.ModelAdmin):
    list_display = ['dataset', 'analysis_type', 'created_at']
    list_filter = ['analysis_type', 'created_at']
    search_fields = ['dataset__name']

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ['user', 'action', 'dataset', 'ip_address', 'timestamp']
    list_filter = ['action', 'timestamp']
    search_fields = ['user__username', 'action', 'ip_address']
    readonly_fields = ['timestamp']
