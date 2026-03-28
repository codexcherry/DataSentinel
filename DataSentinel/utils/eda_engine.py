import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import json

class EDAEngine:
    """Engine for exploratory data analysis and visualization"""
    
    def __init__(self, df):
        self.df = df
        self.dark_theme = {
            'paper_bgcolor': '#0B0F19',
            'plot_bgcolor': '#111827',
            'font_color': '#E5E7EB',
            'grid_color': '#1F2937',
        }
    
    def generate_summary_statistics(self):
        """Generate comprehensive summary statistics"""
        summary = {
            'overview': {
                'total_rows': len(self.df),
                'total_columns': len(self.df.columns),
                'memory_usage': float(self.df.memory_usage(deep=True).sum() / 1024 / 1024),  # MB
                'duplicate_rows': int(self.df.duplicated().sum()),
            },
            'numeric_summary': {},
            'categorical_summary': {},
        }
        
        # Numeric columns
        numeric_cols = self.df.select_dtypes(include=[np.number]).columns
        for col in numeric_cols:
            summary['numeric_summary'][col] = {
                'count': int(self.df[col].count()),
                'mean': float(self.df[col].mean()),
                'std': float(self.df[col].std()),
                'min': float(self.df[col].min()),
                'q25': float(self.df[col].quantile(0.25)),
                'median': float(self.df[col].median()),
                'q75': float(self.df[col].quantile(0.75)),
                'max': float(self.df[col].max()),
                'missing': int(self.df[col].isnull().sum()),
                'zeros': int((self.df[col] == 0).sum()),
            }
        
        # Categorical columns
        categorical_cols = self.df.select_dtypes(include=['object', 'category']).columns
        for col in categorical_cols:
            value_counts = self.df[col].value_counts().head(10)
            summary['categorical_summary'][col] = {
                'count': int(self.df[col].count()),
                'unique': int(self.df[col].nunique()),
                'top': str(self.df[col].mode()[0]) if not self.df[col].mode().empty else None,
                'freq': int(self.df[col].value_counts().iloc[0]) if len(self.df[col].value_counts()) > 0 else 0,
                'missing': int(self.df[col].isnull().sum()),
                'top_values': {str(k): int(v) for k, v in value_counts.items()},
            }
        
        return summary
    
    def generate_correlation_matrix(self):
        """Generate correlation matrix for numeric columns"""
        numeric_df = self.df.select_dtypes(include=[np.number])
        
        if numeric_df.shape[1] < 2:
            return None
        
        corr_matrix = numeric_df.corr()
        
        # Create heatmap
        fig = go.Figure(data=go.Heatmap(
            z=corr_matrix.values,
            x=corr_matrix.columns,
            y=corr_matrix.columns,
            colorscale='RdBu',
            zmid=0,
            text=corr_matrix.values,
            texttemplate='%{text:.2f}',
            textfont={"size": 10},
            colorbar=dict(title="Correlation"),
        ))
        
        fig.update_layout(
            title='Correlation Matrix',
            paper_bgcolor=self.dark_theme['paper_bgcolor'],
            plot_bgcolor=self.dark_theme['plot_bgcolor'],
            font_color=self.dark_theme['font_color'],
            xaxis=dict(showgrid=False),
            yaxis=dict(showgrid=False),
        )
        
        return {
            'matrix': corr_matrix.to_dict(),
            'chart': json.loads(fig.to_json()),
        }
    
    def generate_distribution_analysis(self, column):
        """Generate distribution analysis for a specific column"""
        if pd.api.types.is_numeric_dtype(self.df[column]):
            # Histogram for numeric
            fig = px.histogram(
                self.df, 
                x=column,
                nbins=30,
                title=f'Distribution of {column}',
                color_discrete_sequence=['#22C55E']
            )
            
            fig.update_layout(
                paper_bgcolor=self.dark_theme['paper_bgcolor'],
                plot_bgcolor=self.dark_theme['plot_bgcolor'],
                font_color=self.dark_theme['font_color'],
                xaxis=dict(gridcolor=self.dark_theme['grid_color']),
                yaxis=dict(gridcolor=self.dark_theme['grid_color']),
            )
            
            return {
                'type': 'numeric',
                'chart': json.loads(fig.to_json()),
                'stats': {
                    'mean': float(self.df[column].mean()),
                    'median': float(self.df[column].median()),
                    'std': float(self.df[column].std()),
                    'skewness': float(self.df[column].skew()),
                }
            }
        else:
            # Bar chart for categorical
            value_counts = self.df[column].value_counts().head(20)
            fig = px.bar(
                x=value_counts.index,
                y=value_counts.values,
                title=f'Distribution of {column}',
                labels={'x': column, 'y': 'Count'},
                color_discrete_sequence=['#38BDF8']
            )
            
            fig.update_layout(
                paper_bgcolor=self.dark_theme['paper_bgcolor'],
                plot_bgcolor=self.dark_theme['plot_bgcolor'],
                font_color=self.dark_theme['font_color'],
                xaxis=dict(gridcolor=self.dark_theme['grid_color']),
                yaxis=dict(gridcolor=self.dark_theme['grid_color']),
            )
            
            return {
                'type': 'categorical',
                'chart': json.loads(fig.to_json()),
                'stats': {
                    'unique_count': int(self.df[column].nunique()),
                    'top_value': str(value_counts.index[0]),
                    'top_frequency': int(value_counts.values[0]),
                }
            }
    
    def generate_value_counts_chart(self, column):
        """Generate value counts chart for categorical column"""
        value_counts = self.df[column].value_counts().head(10)
        
        fig = px.bar(
            x=value_counts.index,
            y=value_counts.values,
            title=f'Top 10 Values in {column}',
            labels={'x': column, 'y': 'Count'},
            color_discrete_sequence=['#22C55E']
        )
        
        fig.update_layout(
            paper_bgcolor=self.dark_theme['paper_bgcolor'],
            plot_bgcolor=self.dark_theme['plot_bgcolor'],
            font_color=self.dark_theme['font_color'],
            xaxis=dict(gridcolor=self.dark_theme['grid_color']),
            yaxis=dict(gridcolor=self.dark_theme['grid_color']),
        )
        
        return json.loads(fig.to_json())
    
    def generate_box_plots(self, columns):
        """Generate box plots for multiple numeric columns"""
        fig = go.Figure()
        
        for col in columns:
            fig.add_trace(go.Box(
                y=self.df[col],
                name=col,
                marker_color='#38BDF8'
            ))
        
        fig.update_layout(
            title='Numeric Column Distributions',
            paper_bgcolor=self.dark_theme['paper_bgcolor'],
            plot_bgcolor=self.dark_theme['plot_bgcolor'],
            font_color=self.dark_theme['font_color'],
            xaxis=dict(gridcolor=self.dark_theme['grid_color']),
            yaxis=dict(gridcolor=self.dark_theme['grid_color']),
        )
        
        return json.loads(fig.to_json())
    
    def create_custom_chart(self, chart_type, x_col, y_col=None, color_col=None):
        """Create custom visualization based on user selection"""
        # Validate columns exist
        available_cols = self.df.columns.tolist()
        
        if x_col not in available_cols:
            raise ValueError(f"Column '{x_col}' not found. Available columns: {available_cols}")
        
        if y_col and y_col not in available_cols:
            raise ValueError(f"Column '{y_col}' not found. Available columns: {available_cols}")
        
        if color_col and color_col not in available_cols:
            color_col = None  # Ignore invalid color column
        
        fig = None
        
        try:
            if chart_type == 'bar':
                if y_col:
                    fig = px.bar(self.df, x=x_col, y=y_col, color=color_col, color_discrete_sequence=['#22C55E', '#38BDF8', '#F59E0B'])
                else:
                    value_counts = self.df[x_col].value_counts()
                    fig = px.bar(x=value_counts.index, y=value_counts.values, color_discrete_sequence=['#22C55E'])
            
            elif chart_type == 'line':
                fig = px.line(self.df, x=x_col, y=y_col, color=color_col, color_discrete_sequence=['#38BDF8', '#22C55E'])
            
            elif chart_type == 'scatter':
                fig = px.scatter(self.df, x=x_col, y=y_col, color=color_col, color_discrete_sequence=['#22C55E', '#38BDF8', '#F59E0B'])
            
            elif chart_type == 'pie':
                value_counts = self.df[x_col].value_counts().head(10)
                fig = px.pie(values=value_counts.values, names=value_counts.index, color_discrete_sequence=px.colors.sequential.Teal)
            
            elif chart_type == 'box':
                fig = px.box(self.df, x=x_col, y=y_col, color=color_col, color_discrete_sequence=['#22C55E', '#38BDF8'])
            
            elif chart_type == 'histogram':
                fig = px.histogram(self.df, x=x_col, color=color_col, nbins=30, color_discrete_sequence=['#22C55E', '#38BDF8'])
            
            if fig:
                fig.update_layout(
                    paper_bgcolor=self.dark_theme['paper_bgcolor'],
                    plot_bgcolor=self.dark_theme['plot_bgcolor'],
                    font_color=self.dark_theme['font_color'],
                    xaxis=dict(gridcolor=self.dark_theme['grid_color']),
                    yaxis=dict(gridcolor=self.dark_theme['grid_color']),
                )
                return json.loads(fig.to_json())
        
        except Exception as e:
            raise ValueError(f"Error creating chart: {str(e)}")
        
        return None
    
    def generate_insights(self):
        """Generate automated insights from the data"""
        insights = []
        
        # Check for high correlation
        numeric_df = self.df.select_dtypes(include=[np.number])
        if numeric_df.shape[1] >= 2:
            corr_matrix = numeric_df.corr()
            high_corr = []
            for i in range(len(corr_matrix.columns)):
                for j in range(i+1, len(corr_matrix.columns)):
                    if abs(corr_matrix.iloc[i, j]) > 0.7:
                        high_corr.append({
                            'col1': corr_matrix.columns[i],
                            'col2': corr_matrix.columns[j],
                            'correlation': float(corr_matrix.iloc[i, j])
                        })
            
            if high_corr:
                insights.append({
                    'type': 'correlation',
                    'severity': 'info',
                    'message': f"Found {len(high_corr)} pairs of highly correlated features",
                    'details': high_corr[:5]
                })
        
        # Check for imbalanced data
        for col in self.df.select_dtypes(include=['object', 'category']).columns:
            if self.df[col].nunique() < 10:
                value_counts = self.df[col].value_counts()
                if len(value_counts) > 1:
                    ratio = value_counts.iloc[0] / value_counts.iloc[1]
                    if ratio > 5:
                        insights.append({
                            'type': 'imbalance',
                            'severity': 'warning',
                            'message': f"Column '{col}' is highly imbalanced (ratio: {ratio:.1f}:1)",
                            'details': {'column': col, 'ratio': float(ratio)}
                        })
        
        # Check for skewed distributions
        for col in numeric_df.columns:
            skewness = self.df[col].skew()
            if abs(skewness) > 1:
                insights.append({
                    'type': 'skewness',
                    'severity': 'info',
                    'message': f"Column '{col}' is {'right' if skewness > 0 else 'left'} skewed (skewness: {skewness:.2f})",
                    'details': {'column': col, 'skewness': float(skewness)}
                })
        
        return insights
    
    def calculate_kpis(self):
        """Calculate key performance indicators based on data"""
        kpis = {}
        
        numeric_cols = self.df.select_dtypes(include=[np.number]).columns
        
        for col in numeric_cols:
            col_lower = col.lower()
            
            # Revenue/Sales KPIs
            if any(keyword in col_lower for keyword in ['revenue', 'sales', 'amount', 'price']):
                kpis[f'{col}_total'] = {
                    'label': f'Total {col}',
                    'value': float(self.df[col].sum()),
                    'format': 'currency'
                }
                kpis[f'{col}_avg'] = {
                    'label': f'Average {col}',
                    'value': float(self.df[col].mean()),
                    'format': 'currency'
                }
            
            # Count KPIs
            elif any(keyword in col_lower for keyword in ['count', 'quantity', 'number']):
                kpis[f'{col}_total'] = {
                    'label': f'Total {col}',
                    'value': float(self.df[col].sum()),
                    'format': 'number'
                }
            
            # Rate/Percentage KPIs
            elif any(keyword in col_lower for keyword in ['rate', 'percentage', 'ratio']):
                kpis[f'{col}_avg'] = {
                    'label': f'Average {col}',
                    'value': float(self.df[col].mean()),
                    'format': 'percentage'
                }
        
        # General KPIs
        kpis['data_quality_score'] = {
            'label': 'Data Quality Score',
            'value': float((1 - self.df.isnull().sum().sum() / (len(self.df) * len(self.df.columns))) * 100),
            'format': 'percentage'
        }
        
        kpis['completeness'] = {
            'label': 'Data Completeness',
            'value': float((self.df.count().sum() / (len(self.df) * len(self.df.columns))) * 100),
            'format': 'percentage'
        }
        
        return kpis
