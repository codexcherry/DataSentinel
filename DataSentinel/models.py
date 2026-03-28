from django.db import models
from django.contrib.auth.models import User
import json

class Dataset(models.Model):
    STATUS_CHOICES = [
        ('uploaded', 'Uploaded'),
        ('profiling', 'Profiling'),
        ('profiled', 'Profiled'),
        ('cleaning', 'Cleaning'),
        ('cleaned', 'Cleaned'),
        ('analyzing', 'Analyzing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='datasets')
    name = models.CharField(max_length=255)
    original_filename = models.CharField(max_length=255)
    file_path = models.FileField(upload_to='datasets/%Y/%m/%d/')
    file_size = models.BigIntegerField()
    file_type = models.CharField(max_length=50)
    rows_count = models.IntegerField(null=True, blank=True)
    columns_count = models.IntegerField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='uploaded')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} - {self.user.username}"

class DatasetVersion(models.Model):
    dataset = models.ForeignKey(Dataset, on_delete=models.CASCADE, related_name='versions')
    version_number = models.IntegerField()
    file_path = models.FileField(upload_to='dataset_versions/%Y/%m/%d/')
    description = models.TextField()
    rows_count = models.IntegerField()
    columns_count = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-version_number']
        unique_together = ['dataset', 'version_number']
    
    def __str__(self):
        return f"{self.dataset.name} - v{self.version_number}"

class DataProfile(models.Model):
    dataset = models.OneToOneField(Dataset, on_delete=models.CASCADE, related_name='profile')
    column_info = models.JSONField()  # {col_name: {dtype, unique_count, null_count, etc}}
    missing_values = models.JSONField()  # {col_name: {count, percentage, rows}}
    duplicates = models.JSONField()  # {count, percentage, row_indices}
    outliers = models.JSONField()  # {col_name: {method, count, rows, values}}
    data_types_issues = models.JSONField()  # {col_name: {expected, actual, rows}}
    invalid_values = models.JSONField()  # {col_name: {pattern, invalid_rows}}
    statistics = models.JSONField()  # Basic stats for numeric columns
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Profile - {self.dataset.name}"

class CleaningRecommendation(models.Model):
    ISSUE_TYPES = [
        ('missing', 'Missing Values'),
        ('duplicate', 'Duplicates'),
        ('outlier', 'Outliers'),
        ('type_mismatch', 'Type Mismatch'),
        ('invalid', 'Invalid Values'),
    ]
    
    ACTION_TYPES = [
        ('fill_mean', 'Fill with Mean'),
        ('fill_median', 'Fill with Median'),
        ('fill_mode', 'Fill with Mode'),
        ('fill_forward', 'Forward Fill'),
        ('fill_backward', 'Backward Fill'),
        ('drop_rows', 'Drop Rows'),
        ('drop_column', 'Drop Column'),
        ('remove_duplicates', 'Remove Duplicates'),
        ('cap_outliers', 'Cap Outliers'),
        ('remove_outliers', 'Remove Outliers'),
        ('convert_type', 'Convert Data Type'),
        ('replace_invalid', 'Replace Invalid Values'),
    ]
    
    profile = models.ForeignKey(DataProfile, on_delete=models.CASCADE, related_name='recommendations')
    issue_type = models.CharField(max_length=20, choices=ISSUE_TYPES)
    column_name = models.CharField(max_length=255)
    affected_rows = models.JSONField()  # List of row indices
    issue_description = models.TextField()
    recommended_action = models.CharField(max_length=50, choices=ACTION_TYPES)
    action_params = models.JSONField(null=True, blank=True)  # Additional params for action
    priority = models.IntegerField(default=1)  # 1=high, 2=medium, 3=low
    is_applied = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['priority', '-created_at']
    
    def __str__(self):
        return f"{self.issue_type} - {self.column_name}"

class CleaningLog(models.Model):
    dataset = models.ForeignKey(Dataset, on_delete=models.CASCADE, related_name='cleaning_logs')
    recommendation = models.ForeignKey(CleaningRecommendation, on_delete=models.SET_NULL, null=True, blank=True)
    action_taken = models.CharField(max_length=50)
    column_name = models.CharField(max_length=255)
    rows_affected = models.IntegerField()
    details = models.JSONField()
    applied_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    applied_at = models.DateTimeField(auto_now_add=True)
    execution_time = models.FloatField(default=0.0)  # seconds
    status = models.CharField(max_length=20, default='success')  # success, failed, partial
    
    class Meta:
        ordering = ['-applied_at']
    
    def __str__(self):
        return f"{self.action_taken} on {self.column_name}"

class AnalysisResult(models.Model):
    ANALYSIS_TYPES = [
        ('summary', 'Summary Statistics'),
        ('correlation', 'Correlation Analysis'),
        ('distribution', 'Distribution Analysis'),
        ('trend', 'Trend Analysis'),
        ('kpi', 'KPI Analysis'),
    ]
    
    dataset = models.ForeignKey(Dataset, on_delete=models.CASCADE, related_name='analyses')
    analysis_type = models.CharField(max_length=20, choices=ANALYSIS_TYPES)
    result_data = models.JSONField()
    visualizations = models.JSONField(null=True, blank=True)  # Store chart configs
    insights = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.analysis_type} - {self.dataset.name}"

class AuditLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=100)
    dataset = models.ForeignKey(Dataset, on_delete=models.SET_NULL, null=True, blank=True)
    details = models.JSONField()
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"{self.user} - {self.action} - {self.timestamp}"
