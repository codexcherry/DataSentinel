import pandas as pd
import numpy as np

class CleaningEngine:
    """Engine for generating cleaning recommendations and applying transformations"""
    
    def __init__(self, df, profile):
        self.df = df
        self.profile = profile
    
    def generate_recommendations(self):
        """Generate cleaning recommendations based on profile"""
        recommendations = []
        
        # Missing values recommendations
        for col, info in self.profile['missing_values'].items():
            recommendations.extend(self._recommend_missing_values(col, info))
        
        # Duplicates recommendations
        if self.profile['duplicates']['count'] > 0:
            recommendations.append(self._recommend_duplicates())
        
        # Outliers recommendations
        for col, info in self.profile['outliers'].items():
            recommendations.extend(self._recommend_outliers(col, info))
        
        # Type issues recommendations
        for col, info in self.profile['data_types_issues'].items():
            recommendations.append(self._recommend_type_conversion(col, info))
        
        # Invalid values recommendations
        for col, info in self.profile['invalid_values'].items():
            recommendations.append(self._recommend_invalid_values(col, info))
        
        return recommendations
    
    def _recommend_missing_values(self, col, info):
        """Recommend actions for missing values"""
        recommendations = []
        percentage = info['percentage']
        
        if percentage > 50:
            # Too many missing values - recommend dropping column
            recommendations.append({
                'issue_type': 'missing',
                'column_name': col,
                'affected_rows': info['rows'],
                'issue_description': f"Column '{col}' has {percentage:.1f}% missing values",
                'recommended_action': 'drop_column',
                'action_params': {},
                'priority': 1,
            })
        else:
            # Recommend filling based on data type
            if pd.api.types.is_numeric_dtype(self.df[col]):
                # For numeric, offer mean/median
                recommendations.append({
                    'issue_type': 'missing',
                    'column_name': col,
                    'affected_rows': info['rows'],
                    'issue_description': f"Column '{col}' has {info['count']} missing values ({percentage:.1f}%)",
                    'recommended_action': 'fill_median',
                    'action_params': {'value': float(self.df[col].median())},
                    'priority': 2,
                })
            else:
                # For categorical, offer mode or forward fill
                recommendations.append({
                    'issue_type': 'missing',
                    'column_name': col,
                    'affected_rows': info['rows'],
                    'issue_description': f"Column '{col}' has {info['count']} missing values ({percentage:.1f}%)",
                    'recommended_action': 'fill_mode',
                    'action_params': {'value': self.df[col].mode()[0] if not self.df[col].mode().empty else 'Unknown'},
                    'priority': 2,
                })
        
        return recommendations
    
    def _recommend_duplicates(self):
        """Recommend removing duplicates"""
        info = self.profile['duplicates']
        return {
            'issue_type': 'duplicate',
            'column_name': 'all_columns',
            'affected_rows': info['row_indices'],
            'issue_description': f"Found {info['count']} duplicate rows ({info['percentage']:.1f}%)",
            'recommended_action': 'remove_duplicates',
            'action_params': {},
            'priority': 1,
        }
    
    def _recommend_outliers(self, col, info):
        """Recommend actions for outliers"""
        recommendations = []
        percentage = info['percentage']
        
        if percentage < 5:
            # Few outliers - recommend removal
            recommendations.append({
                'issue_type': 'outlier',
                'column_name': col,
                'affected_rows': info['rows'],
                'issue_description': f"Column '{col}' has {info['count']} outliers ({percentage:.1f}%) using {info['method']} method",
                'recommended_action': 'remove_outliers',
                'action_params': {'bounds': info['bounds']},
                'priority': 2,
            })
        else:
            # Many outliers - recommend capping
            recommendations.append({
                'issue_type': 'outlier',
                'column_name': col,
                'affected_rows': info['rows'],
                'issue_description': f"Column '{col}' has {info['count']} outliers ({percentage:.1f}%) using {info['method']} method",
                'recommended_action': 'cap_outliers',
                'action_params': {'bounds': info['bounds']},
                'priority': 3,
            })
        
        return recommendations
    
    def _recommend_type_conversion(self, col, info):
        """Recommend type conversion"""
        return {
            'issue_type': 'type_mismatch',
            'column_name': col,
            'affected_rows': info['rows'],
            'issue_description': f"Column '{col}' appears to be {info['expected']} but stored as {info['actual']}. {info['problematic_count']} values cannot be converted.",
            'recommended_action': 'convert_type',
            'action_params': {'target_type': info['expected']},
            'priority': 2,
        }
    
    def _recommend_invalid_values(self, col, info):
        """Recommend fixing invalid values"""
        return {
            'issue_type': 'invalid',
            'column_name': col,
            'affected_rows': info['invalid_rows'],
            'issue_description': f"Column '{col}' has {info['count']} invalid {info['pattern']} values",
            'recommended_action': 'replace_invalid',
            'action_params': {'pattern': info['pattern']},
            'priority': 2,
        }
    
    @staticmethod
    def apply_cleaning(df, action, column_name, params):
        """Apply cleaning action to dataframe"""
        try:
            df_cleaned = df.copy()
            rows_affected = 0
            details = {}
            
            if action == 'fill_mean':
                # Check if column is numeric
                if not pd.api.types.is_numeric_dtype(df_cleaned[column_name]):
                    return df_cleaned, 0, {'error': 'Cannot calculate mean on non-numeric column'}
                mean_val = df_cleaned[column_name].mean()
                if pd.isna(mean_val):
                    return df_cleaned, 0, {'error': 'Cannot calculate mean - no valid values'}
                rows_affected = int(df_cleaned[column_name].isnull().sum())
                df_cleaned[column_name] = df_cleaned[column_name].fillna(mean_val)
                details = {'method': 'mean', 'value': float(mean_val)}
            
            elif action == 'fill_median':
                # Check if column is numeric
                if not pd.api.types.is_numeric_dtype(df_cleaned[column_name]):
                    return df_cleaned, 0, {'error': 'Cannot calculate median on non-numeric column'}
                median_val = params.get('value', df_cleaned[column_name].median())
                if pd.isna(median_val):
                    return df_cleaned, 0, {'error': 'Cannot calculate median - no valid values'}
                rows_affected = int(df_cleaned[column_name].isnull().sum())
                df_cleaned[column_name] = df_cleaned[column_name].fillna(median_val)
                details = {'method': 'median', 'value': float(median_val)}
        
            elif action == 'fill_mode':
                mode_series = df_cleaned[column_name].mode()
                if len(mode_series) > 0:
                    mode_val = params.get('value', mode_series[0])
                else:
                    mode_val = params.get('value')
                
                if mode_val is None:
                    return df_cleaned, 0, {'error': 'No mode value available'}
                
                rows_affected = int(df_cleaned[column_name].isnull().sum())
                df_cleaned[column_name] = df_cleaned[column_name].fillna(mode_val)
                details = {'method': 'mode', 'value': str(mode_val)}
            
            elif action == 'fill_forward':
                rows_affected = int(df_cleaned[column_name].isnull().sum())
                df_cleaned[column_name] = df_cleaned[column_name].ffill()
                details = {'method': 'forward_fill'}
            
            elif action == 'fill_backward':
                rows_affected = int(df_cleaned[column_name].isnull().sum())
                df_cleaned[column_name] = df_cleaned[column_name].bfill()
                details = {'method': 'backward_fill'}
            
            elif action == 'drop_rows':
                rows_affected = int(df_cleaned[column_name].isnull().sum())
                df_cleaned = df_cleaned.dropna(subset=[column_name])
                details = {'method': 'drop_rows'}
            
            elif action == 'drop_column':
                rows_affected = len(df_cleaned)
                df_cleaned = df_cleaned.drop(columns=[column_name])
                details = {'method': 'drop_column'}
            
            elif action == 'remove_duplicates':
                rows_affected = int(df_cleaned.duplicated().sum())
                df_cleaned = df_cleaned.drop_duplicates()
                details = {'method': 'remove_duplicates'}
        
            elif action == 'cap_outliers':
                bounds = params.get('bounds', {})
                lower = bounds.get('lower')
                upper = bounds.get('upper')
                
                if lower is None or upper is None:
                    return df_cleaned, 0, {'error': 'Missing bounds for outlier capping'}
                
                # Count affected rows (excluding NaN)
                valid_mask = df_cleaned[column_name].notna()
                outlier_mask = (df_cleaned[column_name] < lower) | (df_cleaned[column_name] > upper)
                rows_affected = int((valid_mask & outlier_mask).sum())
                
                # Cap the values using clip (handles NaN automatically)
                df_cleaned[column_name] = df_cleaned[column_name].clip(lower=lower, upper=upper)
                details = {'method': 'cap_outliers', 'bounds': {'lower': float(lower), 'upper': float(upper)}}
            
            elif action == 'remove_outliers':
                bounds = params.get('bounds', {})
                lower = bounds.get('lower')
                upper = bounds.get('upper')
                
                if lower is None or upper is None:
                    return df_cleaned, 0, {'error': 'Missing bounds for outlier removal'}
                
                # Keep rows within bounds or with NaN values
                valid_mask = df_cleaned[column_name].notna()
                within_bounds = (df_cleaned[column_name] >= lower) & (df_cleaned[column_name] <= upper)
                keep_mask = (~valid_mask) | within_bounds  # Keep NaN or valid values
                
                rows_affected = int((~keep_mask).sum())
                df_cleaned = df_cleaned[keep_mask].reset_index(drop=True)
                details = {'method': 'remove_outliers', 'bounds': {'lower': float(lower), 'upper': float(upper)}}
            
            elif action == 'convert_type':
                target_type = params.get('target_type')
                if target_type == 'numeric':
                    before_count = df_cleaned[column_name].notna().sum()
                    df_cleaned[column_name] = pd.to_numeric(df_cleaned[column_name], errors='coerce')
                    after_count = df_cleaned[column_name].notna().sum()
                    rows_affected = int(before_count - after_count)
                details = {'method': 'convert_type', 'target': target_type}
            
            elif action == 'replace_invalid':
                # Replace invalid values with NaN or default
                rows_affected = len(params.get('rows', []))
                details = {'method': 'replace_invalid', 'pattern': params.get('pattern')}
            
            return df_cleaned, int(rows_affected), details
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return df, 0, {'error': str(e)}
