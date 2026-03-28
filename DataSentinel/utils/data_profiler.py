import pandas as pd
import numpy as np
from scipy import stats
import re

class DataProfiler:
    """Core engine for analyzing datasets and detecting issues"""
    
    def __init__(self, df):
        self.df = df
        self.profile = {}
    
    def profile_data(self):
        """Run complete data profiling"""
        self.profile = {
            'column_info': self._get_column_info(),
            'missing_values': self._detect_missing_values(),
            'duplicates': self._detect_duplicates(),
            'outliers': self._detect_outliers(),
            'data_types_issues': self._detect_type_issues(),
            'invalid_values': self._detect_invalid_values(),
            'statistics': self._calculate_statistics(),
        }
        return self.profile
    
    def _get_column_info(self):
        """Get basic info about each column"""
        info = {}
        for col in self.df.columns:
            info[col] = {
                'dtype': str(self.df[col].dtype),
                'unique_count': int(self.df[col].nunique()),
                'null_count': int(self.df[col].isnull().sum()),
                'null_percentage': float(self.df[col].isnull().sum() / len(self.df) * 100),
                'sample_values': self.df[col].dropna().head(5).tolist(),
            }
        return info
    
    def _detect_missing_values(self):
        """Detect missing values in each column"""
        missing = {}
        for col in self.df.columns:
            null_mask = self.df[col].isnull()
            null_count = null_mask.sum()
            if null_count > 0:
                missing[col] = {
                    'count': int(null_count),
                    'percentage': float(null_count / len(self.df) * 100),
                    'rows': self.df[null_mask].index.tolist()[:100],  # Limit to first 100
                }
        return missing
    
    def _detect_duplicates(self):
        """Detect duplicate rows"""
        duplicates = self.df.duplicated(keep='first')
        dup_count = duplicates.sum()
        return {
            'count': int(dup_count),
            'percentage': float(dup_count / len(self.df) * 100) if len(self.df) > 0 else 0,
            'row_indices': self.df[duplicates].index.tolist()[:100],
        }
    
    def _detect_outliers(self):
        """Detect outliers using IQR method for numeric columns"""
        outliers = {}
        numeric_cols = self.df.select_dtypes(include=[np.number]).columns
        
        for col in numeric_cols:
            if self.df[col].nunique() > 10:  # Skip if too few unique values
                Q1 = self.df[col].quantile(0.25)
                Q3 = self.df[col].quantile(0.75)
                IQR = Q3 - Q1
                lower_bound = Q1 - 1.5 * IQR
                upper_bound = Q3 + 1.5 * IQR
                
                outlier_mask = (self.df[col] < lower_bound) | (self.df[col] > upper_bound)
                outlier_count = outlier_mask.sum()
                
                if outlier_count > 0:
                    outliers[col] = {
                        'method': 'IQR',
                        'count': int(outlier_count),
                        'percentage': float(outlier_count / len(self.df) * 100),
                        'rows': self.df[outlier_mask].index.tolist()[:100],
                        'values': self.df.loc[outlier_mask, col].tolist()[:100],
                        'bounds': {'lower': float(lower_bound), 'upper': float(upper_bound)},
                    }
        return outliers
    
    def _detect_type_issues(self):
        """Detect potential data type mismatches"""
        issues = {}
        
        for col in self.df.columns:
            if self.df[col].dtype == 'object':
                # Check if column should be numeric
                non_null = self.df[col].dropna()
                if len(non_null) > 0:
                    # Try to convert to numeric
                    numeric_convertible = pd.to_numeric(non_null, errors='coerce')
                    non_numeric_mask = numeric_convertible.isnull() & non_null.notna()
                    
                    if non_numeric_mask.sum() > 0 and non_numeric_mask.sum() < len(non_null) * 0.5:
                        # Some values can't be converted but majority can
                        issues[col] = {
                            'expected': 'numeric',
                            'actual': 'object',
                            'problematic_count': int(non_numeric_mask.sum()),
                            'rows': non_null[non_numeric_mask].index.tolist()[:100],
                            'sample_values': non_null[non_numeric_mask].tolist()[:10],
                        }
        return issues
    
    def _detect_invalid_values(self):
        """Detect invalid values based on common patterns"""
        invalid = {}
        
        for col in self.df.columns:
            col_lower = col.lower()
            
            # Email validation
            if 'email' in col_lower:
                email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
                invalid_mask = ~self.df[col].astype(str).str.match(email_pattern, na=False)
                invalid_mask = invalid_mask & self.df[col].notna()
                
                if invalid_mask.sum() > 0:
                    invalid[col] = {
                        'pattern': 'email',
                        'count': int(invalid_mask.sum()),
                        'invalid_rows': self.df[invalid_mask].index.tolist()[:100],
                        'sample_values': self.df.loc[invalid_mask, col].tolist()[:10],
                    }
            
            # Phone validation (basic)
            elif 'phone' in col_lower or 'mobile' in col_lower:
                phone_pattern = r'^\+?[\d\s\-\(\)]{10,}$'
                invalid_mask = ~self.df[col].astype(str).str.match(phone_pattern, na=False)
                invalid_mask = invalid_mask & self.df[col].notna()
                
                if invalid_mask.sum() > 0:
                    invalid[col] = {
                        'pattern': 'phone',
                        'count': int(invalid_mask.sum()),
                        'invalid_rows': self.df[invalid_mask].index.tolist()[:100],
                        'sample_values': self.df.loc[invalid_mask, col].tolist()[:10],
                    }
            
            # Negative values where they shouldn't be
            elif any(keyword in col_lower for keyword in ['age', 'price', 'amount', 'quantity', 'count']):
                if pd.api.types.is_numeric_dtype(self.df[col]):
                    invalid_mask = self.df[col] < 0
                    if invalid_mask.sum() > 0:
                        invalid[col] = {
                            'pattern': 'negative_value',
                            'count': int(invalid_mask.sum()),
                            'invalid_rows': self.df[invalid_mask].index.tolist()[:100],
                            'sample_values': self.df.loc[invalid_mask, col].tolist()[:10],
                        }
        
        return invalid
    
    def _calculate_statistics(self):
        """Calculate basic statistics for numeric columns"""
        stats_dict = {}
        numeric_cols = self.df.select_dtypes(include=[np.number]).columns
        
        for col in numeric_cols:
            stats_dict[col] = {
                'mean': float(self.df[col].mean()) if not self.df[col].isnull().all() else None,
                'median': float(self.df[col].median()) if not self.df[col].isnull().all() else None,
                'std': float(self.df[col].std()) if not self.df[col].isnull().all() else None,
                'min': float(self.df[col].min()) if not self.df[col].isnull().all() else None,
                'max': float(self.df[col].max()) if not self.df[col].isnull().all() else None,
                'q25': float(self.df[col].quantile(0.25)) if not self.df[col].isnull().all() else None,
                'q75': float(self.df[col].quantile(0.75)) if not self.df[col].isnull().all() else None,
                'skewness': float(self.df[col].skew()) if not self.df[col].isnull().all() else None,
                'kurtosis': float(self.df[col].kurtosis()) if not self.df[col].isnull().all() else None,
            }
        
        return stats_dict
