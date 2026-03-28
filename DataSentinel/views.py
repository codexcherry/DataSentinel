from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.core.files.storage import default_storage
from django.conf import settings
import pandas as pd
import numpy as np
import json
import os
from datetime import datetime

from .models import (
    Dataset, DatasetVersion, DataProfile, CleaningRecommendation,
    CleaningLog, AnalysisResult, AuditLog
)
from .utils.data_profiler import DataProfiler
from .utils.cleaning_engine import CleaningEngine
from .utils.eda_engine import EDAEngine

# Authentication Views
def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                AuditLog.objects.create(
                    user=user,
                    action='login',
                    details={'ip': get_client_ip(request)},
                    ip_address=get_client_ip(request)
                )
                return redirect('dashboard')
    else:
        form = AuthenticationForm()
    
    return render(request, 'auth/login.html', {'form': form})

def register_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            AuditLog.objects.create(
                user=user,
                action='register',
                details={'ip': get_client_ip(request)},
                ip_address=get_client_ip(request)
            )
            return redirect('dashboard')
    else:
        form = UserCreationForm()
    
    return render(request, 'auth/register.html', {'form': form})

def logout_view(request):
    if request.user.is_authenticated:
        AuditLog.objects.create(
            user=request.user,
            action='logout',
            details={'ip': get_client_ip(request)},
            ip_address=get_client_ip(request)
        )
    logout(request)
    return redirect('login')

# Dashboard Views
@login_required
def dashboard(request):
    datasets = Dataset.objects.filter(user=request.user)
    
    context = {
        'datasets': datasets,
        'total_datasets': datasets.count(),
        'completed_datasets': datasets.filter(status='completed').count(),
        'failed_datasets': datasets.filter(status='failed').count(),
    }
    return render(request, 'dashboard/index.html', context)

@login_required
def datasets_list(request):
    datasets = Dataset.objects.filter(user=request.user)
    return render(request, 'datasets/list.html', {'datasets': datasets})

@login_required
@require_http_methods(["POST"])
def upload_dataset(request):
    if 'file' not in request.FILES:
        return JsonResponse({'error': 'No file provided'}, status=400)
    
    file = request.FILES['file']
    
    # Validate file
    if not file.name.endswith(('.csv', '.xlsx', '.xls')):
        return JsonResponse({'error': 'Invalid file type. Only CSV and Excel files are allowed.'}, status=400)
    
    if file.size > settings.FILE_UPLOAD_MAX_MEMORY_SIZE:
        return JsonResponse({'error': 'File too large. Maximum size is 10MB.'}, status=400)
    
    try:
        # Save file
        file_path = default_storage.save(f'datasets/{datetime.now().strftime("%Y/%m/%d")}/{file.name}', file)
        
        # Read file to get basic info
        full_path = os.path.join(settings.MEDIA_ROOT, file_path)
        if file.name.endswith('.csv'):
            df = pd.read_csv(full_path)
        else:
            df = pd.read_excel(full_path)
        
        # Create dataset record
        dataset = Dataset.objects.create(
            user=request.user,
            name=request.POST.get('name', file.name),
            original_filename=file.name,
            file_path=file_path,
            file_size=file.size,
            file_type=file.name.split('.')[-1],
            rows_count=len(df),
            columns_count=len(df.columns),
            status='uploaded'
        )
        
        # Log action
        AuditLog.objects.create(
            user=request.user,
            action='upload_dataset',
            dataset=dataset,
            details={'filename': file.name, 'size': file.size},
            ip_address=get_client_ip(request)
        )
        
        return JsonResponse({
            'success': True,
            'dataset_id': dataset.id,
            'message': 'Dataset uploaded successfully'
        })
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
@require_http_methods(["POST"])
def load_sample_dataset(request):
    """Load the sample dataset for new users to try the system"""
    try:
        import shutil
        
        # Path to sample dataset
        sample_file = os.path.join(settings.BASE_DIR, 'sample_dataset.csv')
        
        if not os.path.exists(sample_file):
            return JsonResponse({'error': 'Sample dataset not found'}, status=404)
        
        # Read sample file to get info
        df = pd.read_csv(sample_file)
        
        # Create destination path
        file_name = 'sample_employee_data.csv'
        file_path = f'datasets/{datetime.now().strftime("%Y/%m/%d")}/{file_name}'
        full_path = os.path.join(settings.MEDIA_ROOT, file_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        
        # Copy sample file to media directory
        shutil.copy(sample_file, full_path)
        
        # Get file size
        file_size = os.path.getsize(full_path)
        
        # Create dataset record
        dataset = Dataset.objects.create(
            user=request.user,
            name='Sample Employee Data',
            original_filename=file_name,
            file_path=file_path,
            file_size=file_size,
            file_type='csv',
            rows_count=len(df),
            columns_count=len(df.columns),
            status='uploaded'
        )
        
        # Log action
        AuditLog.objects.create(
            user=request.user,
            action='load_sample_dataset',
            dataset=dataset,
            details={'filename': file_name, 'size': file_size},
            ip_address=get_client_ip(request)
        )
        
        return JsonResponse({
            'success': True,
            'dataset_id': dataset.id,
            'message': 'Sample dataset loaded successfully'
        })
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def dataset_detail(request, dataset_id):
    dataset = get_object_or_404(Dataset, id=dataset_id, user=request.user)
    
    # Get profile if exists
    profile = None
    recommendations = []
    if hasattr(dataset, 'profile'):
        profile = dataset.profile
        recommendations = profile.recommendations.all()
    
    # Get cleaning logs
    cleaning_logs = dataset.cleaning_logs.all()[:20]
    
    # Get analyses
    analyses = dataset.analyses.all()
    
    # Calculate performance metrics
    processing_time = sum([log.execution_time for log in cleaning_logs])
    throughput = int(dataset.rows_count / processing_time) if processing_time > 0 else 0
    
    # Calculate data quality score
    data_quality_score = 100
    if profile:
        total_cells = dataset.rows_count * dataset.columns_count
        missing_count = sum([len(v.get('rows', [])) for v in profile.missing_values.values()])
        duplicate_count = profile.duplicates.get('count', 0)
        outlier_count = sum([v.get('count', 0) for v in profile.outliers.values()])
        
        issues_count = missing_count + duplicate_count + outlier_count
        data_quality_score = max(0, int(100 - (issues_count / total_cells * 100)))
    
    context = {
        'dataset': dataset,
        'profile': profile,
        'recommendations': recommendations,
        'cleaning_logs': cleaning_logs,
        'analyses': analyses,
        'processing_time': round(processing_time, 2),
        'throughput': throughput,
        'data_quality_score': data_quality_score,
    }
    return render(request, 'datasets/detail.html', context)

@login_required
@require_http_methods(["POST"])
def profile_dataset(request, dataset_id):
    dataset = get_object_or_404(Dataset, id=dataset_id, user=request.user)
    
    try:
        dataset.status = 'profiling'
        dataset.save()
        
        # Load dataset
        full_path = dataset.file_path.path
        if dataset.file_type == 'csv':
            df = pd.read_csv(full_path)
        else:
            df = pd.read_excel(full_path)
        
        # Profile data
        profiler = DataProfiler(df)
        profile_data = profiler.profile_data()
        
        # Create or update profile
        profile, created = DataProfile.objects.update_or_create(
            dataset=dataset,
            defaults={
                'column_info': profile_data['column_info'],
                'missing_values': profile_data['missing_values'],
                'duplicates': profile_data['duplicates'],
                'outliers': profile_data['outliers'],
                'data_types_issues': profile_data['data_types_issues'],
                'invalid_values': profile_data['invalid_values'],
                'statistics': profile_data['statistics'],
            }
        )
        
        # Generate recommendations
        cleaning_engine = CleaningEngine(df, profile_data)
        recommendations = cleaning_engine.generate_recommendations()
        
        # Delete old recommendations
        profile.recommendations.all().delete()
        
        # Create new recommendations
        for rec in recommendations:
            CleaningRecommendation.objects.create(
                profile=profile,
                **rec
            )
        
        dataset.status = 'profiled'
        dataset.save()
        
        # Log action
        AuditLog.objects.create(
            user=request.user,
            action='profile_dataset',
            dataset=dataset,
            details={'recommendations_count': len(recommendations)},
            ip_address=get_client_ip(request)
        )
        
        return JsonResponse({
            'success': True,
            'message': 'Dataset profiled successfully',
            'recommendations_count': len(recommendations)
        })
    
    except Exception as e:
        dataset.status = 'failed'
        dataset.save()
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def get_issue_details(request, recommendation_id):
    recommendation = get_object_or_404(CleaningRecommendation, id=recommendation_id)
    
    # Load dataset
    dataset = recommendation.profile.dataset
    full_path = dataset.file_path.path
    
    if dataset.file_type == 'csv':
        df = pd.read_csv(full_path)
    else:
        df = pd.read_excel(full_path)
    
    # Get affected rows
    affected_rows = recommendation.affected_rows[:50]  # Limit to 50 rows
    affected_data = df.iloc[affected_rows].to_dict('records')
    
    return JsonResponse({
        'recommendation': {
            'id': recommendation.id,
            'issue_type': recommendation.issue_type,
            'column_name': recommendation.column_name,
            'issue_description': recommendation.issue_description,
            'recommended_action': recommendation.recommended_action,
            'priority': recommendation.priority,
        },
        'affected_rows': affected_rows,
        'affected_data': affected_data,
        'total_affected': len(recommendation.affected_rows)
    })

@login_required
@require_http_methods(["POST"])
def apply_batch_cleaning(request, dataset_id):
    """Apply multiple cleaning actions with automatic retry and verification"""
    import time
    dataset = get_object_or_404(Dataset, id=dataset_id, user=request.user)
    
    try:
        import json
        data = json.loads(request.body)
        recommendation_ids = data.get('recommendation_ids', [])
        
        if not recommendation_ids:
            return JsonResponse({'error': 'No recommendations provided'}, status=400)
        
        recommendations = CleaningRecommendation.objects.filter(
            id__in=recommendation_ids,
            profile__dataset=dataset
        )
        
        failed_issues = []
        success_count = 0
        
        for recommendation in recommendations:
            # Try up to 10 times with different strategies
            success = False
            last_error = None
            start_time = time.time()
            
            for attempt in range(10):
                try:
                    # Load current dataset state
                    full_path = dataset.file_path.path
                    if dataset.file_type == 'csv':
                        df = pd.read_csv(full_path)
                    else:
                        df = pd.read_excel(full_path)
                    
                    # Get alternative strategies based on attempt number
                    action, params = get_cleaning_strategy(
                        recommendation, 
                        attempt,
                        df
                    )
                    
                    # Apply cleaning
                    df_cleaned, rows_affected, details = CleaningEngine.apply_cleaning(
                        df,
                        action,
                        recommendation.column_name,
                        params
                    )
                    
                    # Check if there was an error
                    if 'error' in details:
                        last_error = details['error']
                        continue
                    
                    # Verify the issue is resolved
                    if verify_issue_resolved(df_cleaned, recommendation):
                        # Create version before saving
                        version_number = dataset.versions.count() + 1
                        version_path = f'dataset_versions/{datetime.now().strftime("%Y/%m/%d")}/{dataset.name}_v{version_number}.csv'
                        full_version_path = os.path.join(settings.MEDIA_ROOT, version_path)
                        os.makedirs(os.path.dirname(full_version_path), exist_ok=True)
                        df_cleaned.to_csv(full_version_path, index=False)
                        
                        # Create version record
                        DatasetVersion.objects.create(
                            dataset=dataset,
                            version_number=version_number,
                            file_path=version_path,
                            description=f"Applied {action} on {recommendation.column_name}",
                            rows_count=len(df_cleaned),
                            columns_count=len(df_cleaned.columns)
                        )
                        
                        # Save cleaned dataset
                        df_cleaned.to_csv(full_path, index=False)
                        dataset.rows_count = len(df_cleaned)
                        dataset.save()
                        
                        execution_time = time.time() - start_time
                        
                        # Create cleaning log
                        CleaningLog.objects.create(
                            dataset=dataset,
                            recommendation=recommendation,
                            action_taken=action,
                            column_name=recommendation.column_name,
                            rows_affected=rows_affected,
                            details=details,
                            applied_by=request.user,
                            execution_time=execution_time,
                            status='success'
                        )
                        
                        # Mark as applied
                        recommendation.is_applied = True
                        recommendation.save()
                        
                        success = True
                        success_count += 1
                        break
                    else:
                        last_error = "Issue not resolved after cleaning"
                        
                except Exception as e:
                    last_error = str(e)
                    continue
            
            if not success:
                execution_time = time.time() - start_time
                # Log failed attempt
                CleaningLog.objects.create(
                    dataset=dataset,
                    recommendation=recommendation,
                    action_taken=recommendation.recommended_action,
                    column_name=recommendation.column_name,
                    rows_affected=0,
                    details={'error': last_error},
                    applied_by=request.user,
                    execution_time=execution_time,
                    status='failed'
                )
                
                failed_issues.append({
                    'column': recommendation.column_name,
                    'issue_type': recommendation.get_issue_type_display(),
                    'reason': last_error or 'Unknown error after 10 attempts'
                })
        
        # Re-profile dataset to check for remaining issues
        if success_count > 0:
            try:
                full_path = dataset.file_path.path
                if dataset.file_type == 'csv':
                    df = pd.read_csv(full_path)
                else:
                    df = pd.read_excel(full_path)
                
                from .utils.data_profiler import DataProfiler
                profiler = DataProfiler(df)
                profile_data = profiler.profile_data()
                
                # Update profile
                profile = dataset.profile
                profile.column_info = profile_data['column_info']
                profile.missing_values = profile_data['missing_values']
                profile.duplicates = profile_data['duplicates']
                profile.outliers = profile_data['outliers']
                profile.data_types_issues = profile_data['data_types_issues']
                profile.invalid_values = profile_data['invalid_values']
                profile.statistics = profile_data['statistics']
                profile.save()
                
                # Generate new recommendations for remaining issues
                cleaning_engine = CleaningEngine(df, profile_data)
                new_recommendations = cleaning_engine.generate_recommendations()
                
                # Delete old unapplied recommendations
                profile.recommendations.filter(is_applied=False).delete()
                
                # Create new recommendations
                for rec in new_recommendations:
                    CleaningRecommendation.objects.create(
                        profile=profile,
                        **rec
                    )
            except Exception as e:
                pass  # Continue even if re-profiling fails
        
        return JsonResponse({
            'success': True,
            'applied': success_count,
            'failed': failed_issues,
            'message': f'Applied {success_count} cleaning action(s)'
        })
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def get_cleaning_strategy(recommendation, attempt, df):
    """Get alternative cleaning strategy based on attempt number"""
    column_name = recommendation.column_name
    issue_type = recommendation.issue_type
    
    # Different strategies for different attempts
    if issue_type == 'missing':
        strategies = [
            ('fill_median', {}),
            ('fill_mean', {}),
            ('fill_mode', {}),
            ('fill_forward', {}),
            ('fill_backward', {}),
            ('drop_rows', {}),
        ]
        if attempt < len(strategies):
            return strategies[attempt]
        return ('drop_rows', {})
    
    elif issue_type == 'outlier':
        strategies = [
            ('cap_outliers', recommendation.action_params or {}),
            ('remove_outliers', recommendation.action_params or {}),
        ]
        if attempt < len(strategies):
            return strategies[attempt]
        return ('remove_outliers', recommendation.action_params or {})
    
    elif issue_type == 'duplicate':
        return ('remove_duplicates', {})
    
    elif issue_type == 'type_mismatch':
        return ('convert_type', recommendation.action_params or {})
    
    else:
        return (recommendation.recommended_action, recommendation.action_params or {})


def verify_issue_resolved(df, recommendation):
    """Verify if the issue has been resolved"""
    column_name = recommendation.column_name
    issue_type = recommendation.issue_type
    
    try:
        if issue_type == 'missing':
            # Check if missing values are reduced significantly
            missing_count = df[column_name].isnull().sum()
            return missing_count < len(recommendation.affected_rows) * 0.1  # 90% reduction
        
        elif issue_type == 'duplicate':
            # Check if duplicates are removed
            return df.duplicated().sum() == 0
        
        elif issue_type == 'outlier':
            # Check if outliers are reduced
            if column_name not in df.columns:
                return False
            Q1 = df[column_name].quantile(0.25)
            Q3 = df[column_name].quantile(0.75)
            IQR = Q3 - Q1
            lower_bound = Q1 - 1.5 * IQR
            upper_bound = Q3 + 1.5 * IQR
            outliers = ((df[column_name] < lower_bound) | (df[column_name] > upper_bound)).sum()
            return outliers < len(recommendation.affected_rows) * 0.2  # 80% reduction
        
        elif issue_type == 'type_mismatch':
            # Check if type conversion was successful
            return pd.to_numeric(df[column_name], errors='coerce').notna().sum() > len(df) * 0.9
        
        return True  # Default to success for other types
        
    except Exception:
        return False


@login_required
@require_http_methods(["POST"])
def apply_cleaning(request, recommendation_id):
    recommendation = get_object_or_404(CleaningRecommendation, id=recommendation_id)
    dataset = recommendation.profile.dataset
    
    try:
        # Load dataset
        full_path = dataset.file_path.path
        if dataset.file_type == 'csv':
            df = pd.read_csv(full_path)
        else:
            df = pd.read_excel(full_path)
        
        # Apply cleaning
        df_cleaned, rows_affected, details = CleaningEngine.apply_cleaning(
            df,
            recommendation.recommended_action,
            recommendation.column_name,
            recommendation.action_params or {}
        )
        
        # Save cleaned dataset
        version_number = dataset.versions.count() + 1
        version_path = f'dataset_versions/{datetime.now().strftime("%Y/%m/%d")}/{dataset.name}_v{version_number}.csv'
        full_version_path = os.path.join(settings.MEDIA_ROOT, version_path)
        os.makedirs(os.path.dirname(full_version_path), exist_ok=True)
        df_cleaned.to_csv(full_version_path, index=False)
        
        # Create version record
        DatasetVersion.objects.create(
            dataset=dataset,
            version_number=version_number,
            file_path=version_path,
            description=f"Applied {recommendation.recommended_action} on {recommendation.column_name}",
            rows_count=len(df_cleaned),
            columns_count=len(df_cleaned.columns)
        )
        
        # Update main dataset file
        df_cleaned.to_csv(full_path, index=False)
        dataset.rows_count = len(df_cleaned)
        dataset.save()
        
        # Create cleaning log
        CleaningLog.objects.create(
            dataset=dataset,
            recommendation=recommendation,
            action_taken=recommendation.recommended_action,
            column_name=recommendation.column_name,
            rows_affected=rows_affected,
            details=details,
            applied_by=request.user
        )
        
        # Mark recommendation as applied
        recommendation.is_applied = True
        recommendation.save()
        
        # Log action
        AuditLog.objects.create(
            user=request.user,
            action='apply_cleaning',
            dataset=dataset,
            details={'action': recommendation.recommended_action, 'column': recommendation.column_name},
            ip_address=get_client_ip(request)
        )
        
        return JsonResponse({
            'success': True,
            'message': 'Cleaning applied successfully',
            'rows_affected': rows_affected
        })
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def analyze_dataset(request, dataset_id):
    dataset = get_object_or_404(Dataset, id=dataset_id, user=request.user)
    
    # Delete old analysis results to prevent duplicates
    dataset.analyses.all().delete()
    
    # Load dataset
    full_path = dataset.file_path.path
    if dataset.file_type == 'csv':
        df = pd.read_csv(full_path)
    else:
        df = pd.read_excel(full_path)
    
    eda_engine = EDAEngine(df)
    
    # Generate summary statistics
    summary = eda_engine.generate_summary_statistics()
    AnalysisResult.objects.create(
        dataset=dataset,
        analysis_type='summary',
        result_data=summary,
        insights='Summary statistics generated'
    )
    
    # Generate correlation
    correlation = eda_engine.generate_correlation_matrix()
    if correlation:
        AnalysisResult.objects.create(
            dataset=dataset,
            analysis_type='correlation',
            result_data=correlation['matrix'],
            visualizations={'chart': correlation['chart']},
            insights='Correlation matrix generated'
        )
    
    # Generate insights
    insights = eda_engine.generate_insights()
    
    # Calculate KPIs
    kpis = eda_engine.calculate_kpis()
    AnalysisResult.objects.create(
        dataset=dataset,
        analysis_type='kpi',
        result_data=kpis,
        insights=json.dumps(insights)
    )
    
    dataset.status = 'completed'
    dataset.save()
    
    # Log action
    AuditLog.objects.create(
        user=request.user,
        action='analyze_dataset',
        dataset=dataset,
        details={'analyses_count': 3},
        ip_address=get_client_ip(request)
    )
    
    context = {
        'dataset': dataset,
        'summary': summary,
        'correlation': correlation,
        'insights': insights,
        'kpis': kpis,
    }
    return render(request, 'analysis/results.html', context)


@login_required
@require_http_methods(["POST"])
def create_visualization(request, dataset_id):
    dataset = get_object_or_404(Dataset, id=dataset_id, user=request.user)
    
    chart_type = request.POST.get('chart_type')
    x_col = request.POST.get('x_column')
    y_col = request.POST.get('y_column')
    color_col = request.POST.get('color_column')
    
    try:
        # Load dataset
        full_path = dataset.file_path.path
        if dataset.file_type == 'csv':
            df = pd.read_csv(full_path)
        else:
            df = pd.read_excel(full_path)
        
        eda_engine = EDAEngine(df)
        chart_json = eda_engine.create_custom_chart(chart_type, x_col, y_col, color_col)
        
        return JsonResponse({'success': True, 'chart': chart_json})
    
    except ValueError as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Error creating visualization: {str(e)}'}, status=500)

@login_required
@require_http_methods(["GET"])
def export_dataset(request, dataset_id):
    dataset = get_object_or_404(Dataset, id=dataset_id, user=request.user)
    
    # Load dataset
    full_path = dataset.file_path.path
    if dataset.file_type == 'csv':
        df = pd.read_csv(full_path)
    else:
        df = pd.read_excel(full_path)
    
    export_format = request.GET.get('format', 'csv')
    
    if export_format == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{dataset.name}_cleaned.csv"'
        df.to_csv(response, index=False)
    elif export_format == 'excel':
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename="{dataset.name}_cleaned.xlsx"'
        df.to_excel(response, index=False)
    else:
        return JsonResponse({'error': 'Invalid format'}, status=400)
    
    # Log action
    AuditLog.objects.create(
        user=request.user,
        action='export_dataset',
        dataset=dataset,
        details={'format': export_format},
        ip_address=get_client_ip(request)
    )
    
    return response

@login_required
def dataset_preview(request, dataset_id):
    dataset = get_object_or_404(Dataset, id=dataset_id, user=request.user)
    
    # Load dataset
    full_path = dataset.file_path.path
    if dataset.file_type == 'csv':
        df = pd.read_csv(full_path)
    else:
        df = pd.read_excel(full_path)
    
    # Get first 100 rows
    preview_data = df.head(100).to_dict('records')
    columns = df.columns.tolist()
    
    return JsonResponse({
        'columns': columns,
        'data': preview_data,
        'total_rows': len(df)
    })

# Helper function
def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip
