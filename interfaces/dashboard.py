"""
Dashboard routes for the Generative AI Content Evaluation System.
"""
import logging
from datetime import datetime, timedelta
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, session
from flask_login import login_required, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, SelectMultipleField, SubmitField
from wtforms.validators import Optional

from database import get_db_session
from models import (
    User, Content, Evaluation, EvaluationCriterion, EvaluationScore,
    AnalyticsReport, ImprovementSuggestion
)
from config import CONTENT_DOMAINS
from evaluator import Evaluator
from quality_control import QualityController
from analytics import AnalyticsEngine
from utils import truncate_text, format_timestamp, get_domain_label, export_evaluations_to_csv

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create Blueprint
dashboard_bp = Blueprint('dashboard_bp', __name__)

# Initialize components
evaluator = Evaluator()
quality_controller = QualityController()
analytics_engine = AnalyticsEngine()


# Form classes
class ModelComparisonForm(FlaskForm):
    """Form for generating model comparison reports."""
    models = SelectMultipleField('AI Models', choices=[], validators=[])
    domains = SelectMultipleField('Content Domains', choices=[], validators=[Optional()])
    timeframe = SelectField('Time Period', choices=[
        ('all_time', 'All Time'),
        ('last_7_days', 'Last 7 Days'),
        ('last_30_days', 'Last 30 Days'),
        ('last_90_days', 'Last 90 Days'),
        ('last_year', 'Last Year')
    ], default='last_30_days')
    submit = SubmitField('Generate Comparison')


class ExportEvaluationsForm(FlaskForm):
    """Form for exporting evaluations to CSV."""
    domain = SelectField('Domain', choices=[('', 'All Domains')], validators=[Optional()])
    model_name = StringField('Model Name', validators=[Optional()])
    source_type = SelectField('Source Type', 
                             choices=[('', 'All Sources'), ('ai', 'AI Generated'), ('human', 'Human Created')],
                             validators=[Optional()])
    submit = SubmitField('Export to CSV')


# Helper functions
def is_admin():
    """Check if the current user is an administrator."""
    if not current_user.is_authenticated:
        return False
    
    return current_user.role == 'admin'


# Custom decorator for admin-only routes
def admin_required(func):
    """Decorator for routes that require admin privileges."""
    def decorated_view(*args, **kwargs):
        if not is_admin():
            flash('You must be an administrator to access this page', 'danger')
            return redirect(url_for('index'))
        return func(*args, **kwargs)
    decorated_view.__name__ = func.__name__
    return login_required(decorated_view)


# Routes
@dashboard_bp.route('/')
@login_required
def index():
    """Dashboard landing page."""
    # Redirect to admin dashboard for admins
    if is_admin():
        return redirect(url_for('dashboard_bp.admin'))
    
    # Regular user dashboard
    with get_db_session() as session:
        # Get user's stats
        stats = evaluator.get_evaluation_statistics(current_user.id)
        
        # Get pending evaluations
        pending = evaluator.get_pending_evaluations(current_user.id)
        
        # Get recent analytics reports if any
        reports = session.query(AnalyticsReport).filter(
            AnalyticsReport.created_by == current_user.id
        ).order_by(
            AnalyticsReport.created_at.desc()
        ).limit(5).all()
    
    return render_template(
        'dashboard/index.html',
        stats=stats,
        pending=pending,
        reports=reports,
        is_admin=is_admin(),
        title='Dashboard'
    )


@dashboard_bp.route('/admin')
@admin_required
def admin():
    """Admin dashboard page."""
    with get_db_session() as session:
        # Get system stats
        content_count = session.query(Content).count()
        evaluation_count = session.query(Evaluation).count()
        user_count = session.query(User).count()
        completed_evaluations = session.query(Evaluation).filter(
            Evaluation.completion_time.isnot(None)
        ).count()
        
        # Get content by type
        ai_content = session.query(Content).filter(Content.source_type == 'ai').count()
        human_content = session.query(Content).filter(Content.source_type == 'human').count()
        
        # Get content by domain
        content_by_domain = {}
        for domain in CONTENT_DOMAINS:
            count = session.query(Content).filter(Content.domain == domain).count()
            content_by_domain[domain] = count
        
        # Get quality control issues
        quality_issues = quality_controller.flag_low_quality_evaluations()
        
        # Get recent reports
        recent_reports = analytics_engine.get_recent_reports(5)
        
        # Get improvement suggestions
        suggestions = session.query(ImprovementSuggestion).filter(
            ImprovementSuggestion.status == 'open'
        ).order_by(
            ImprovementSuggestion.created_at.desc()
        ).limit(5).all()
    
    stats = {
        'content_count': content_count,
        'evaluation_count': evaluation_count,
        'user_count': user_count,
        'completed_evaluations': completed_evaluations,
        'completion_rate': round(completed_evaluations / evaluation_count * 100, 1) if evaluation_count else 0,
        'ai_content': ai_content,
        'human_content': human_content,
        'content_by_domain': content_by_domain
    }
    
    return render_template(
        'dashboard/admin.html',
        stats=stats,
        quality_issues=quality_issues[:5] if quality_issues else [],
        quality_issues_count=len(quality_issues),
        recent_reports=recent_reports,
        suggestions=suggestions,
        title='Admin Dashboard'
    )


@dashboard_bp.route('/reports')
@login_required
def reports():
    """Analytics reports page."""
    with get_db_session() as session:
        # Get reports
        query = session.query(AnalyticsReport)
        
        # Filter by user if not admin
        if not is_admin():
            query = query.filter(AnalyticsReport.created_by == current_user.id)
        
        # Order by creation date (newest first)
        query = query.order_by(AnalyticsReport.created_at.desc())
        
        # Get paginated results
        page = request.args.get('page', 1, type=int)
        per_page = 10
        offset = (page - 1) * per_page
        
        total = query.count()
        reports = query.limit(per_page).offset(offset).all()
    
    # Calculate pagination
    total_pages = (total + per_page - 1) // per_page
    
    return render_template(
        'dashboard/reports.html',
        reports=reports,
        page=page,
        total_pages=total_pages,
        total=total,
        is_admin=is_admin(),
        title='Analytics Reports'
    )


@dashboard_bp.route('/report/<int:report_id>')
@login_required
def view_report(report_id):
    """View a specific analytics report."""
    report = analytics_engine.get_analytics_report(report_id)
    
    if not report:
        flash('Report not found', 'danger')
        return redirect(url_for('dashboard_bp.reports'))
    
    # Check permission
    if not is_admin() and report.get('created_by') != current_user.id:
        flash('You do not have permission to view this report', 'danger')
        return redirect(url_for('dashboard_bp.reports'))
    
    return render_template(
        'dashboard/view_report.html',
        report=report,
        is_admin=is_admin(),
        title=f'Report: {report["title"]}'
    )


@dashboard_bp.route('/model-comparison', methods=['GET', 'POST'])
@login_required
def model_comparison():
    """Generate model comparison reports."""
    # Initialize form
    form = ModelComparisonForm()
    
    # Get available models
    with get_db_session() as session:
        models = session.query(Content.model_name).filter(
            Content.source_type == 'ai',
            Content.model_name.isnot(None)
        ).distinct().all()
        
        models = [m[0] for m in models if m[0]]
    
    # Set form choices
    form.models.choices = [(m, m) for m in models]
    form.domains.choices = [(d, get_domain_label(d)) for d in CONTENT_DOMAINS]
    
    # Process form submission
    if form.validate_on_submit():
        selected_models = form.models.data
        selected_domains = form.domains.data or None
        timeframe = form.timeframe.data
        
        if not selected_models:
            flash('Please select at least one model', 'danger')
            return render_template(
                'dashboard/model_comparison.html',
                form=form,
                is_admin=is_admin(),
                title='Model Comparison'
            )
        
        # Generate comparison
        comparison = analytics_engine.generate_model_comparison(
            selected_models,
            selected_domains,
            None,  # Use all criteria
            timeframe
        )
        
        if comparison:
            # Get the report ID
            report_id = None
            with get_db_session() as session:
                report = session.query(AnalyticsReport).filter(
                    AnalyticsReport.report_type == 'model_comparison'
                ).order_by(
                    AnalyticsReport.created_at.desc()
                ).first()
                
                if report:
                    report_id = report.id
            
            if report_id:
                flash('Model comparison generated successfully', 'success')
                return redirect(url_for('dashboard_bp.view_report', report_id=report_id))
            else:
                flash('Model comparison generated, but report not found', 'warning')
        else:
            flash('Failed to generate model comparison', 'danger')
    
    return render_template(
        'dashboard/model_comparison.html',
        form=form,
        is_admin=is_admin(),
        title='Model Comparison'
    )


@dashboard_bp.route('/improvement-analysis', methods=['GET', 'POST'])
@login_required
def improvement_analysis():
    """Analyze areas for model improvement."""
    # Get available models
    with get_db_session() as session:
        models = session.query(Content.model_name).filter(
            Content.source_type == 'ai',
            Content.model_name.isnot(None)
        ).distinct().all()
        
        models = [m[0] for m in models if m[0]]
    
    # Process form submission
    if request.method == 'POST':
        model_name = request.form.get('model_name')
        comparison_model = request.form.get('comparison_model') or None
        
        if not model_name:
            flash('Please select a model', 'danger')
            return render_template(
                'dashboard/improvement_analysis.html',
                models=models,
                is_admin=is_admin(),
                title='Improvement Analysis'
            )
        
        # Generate analysis
        analysis = analytics_engine.identify_improvement_areas(
            model_name,
            comparison_model=comparison_model
        )
        
        if analysis and 'error' not in analysis:
            # Get the report ID
            report_id = None
            with get_db_session() as session:
                report = session.query(AnalyticsReport).filter(
                    AnalyticsReport.report_type == 'improvement_areas'
                ).order_by(
                    AnalyticsReport.created_at.desc()
                ).first()
                
                if report:
                    report_id = report.id
            
            if report_id:
                flash('Improvement analysis generated successfully', 'success')
                return redirect(url_for('dashboard_bp.view_report', report_id=report_id))
            else:
                flash('Improvement analysis generated, but report not found', 'warning')
        else:
            error_msg = analysis.get('error', 'Failed to generate improvement analysis')
            flash(error_msg, 'danger')
    
    return render_template(
        'dashboard/improvement_analysis.html',
        models=models,
        is_admin=is_admin(),
        title='Improvement Analysis'
    )


@dashboard_bp.route('/human-ai-gap')
@login_required
def human_ai_gap():
    """Analyze the gap between human and AI content."""
    # Get domains
    domains = CONTENT_DOMAINS
    
    # Check if analysis should be run
    run_analysis = request.args.get('run', '0') == '1'
    selected_domains = request.args.getlist('domains')
    
    if run_analysis:
        # Run the analysis
        analysis = analytics_engine.analyze_human_ai_gap(selected_domains or None)
        
        if analysis and 'error' not in analysis:
            # Get the report ID
            report_id = None
            with get_db_session() as session:
                report = session.query(AnalyticsReport).filter(
                    AnalyticsReport.report_type == 'human_ai_gap'
                ).order_by(
                    AnalyticsReport.created_at.desc()
                ).first()
                
                if report:
                    report_id = report.id
            
            if report_id:
                flash('Human-AI gap analysis generated successfully', 'success')
                return redirect(url_for('dashboard_bp.view_report', report_id=report_id))
            else:
                flash('Human-AI gap analysis generated, but report not found', 'warning')
        else:
            error_msg = analysis.get('error', 'Failed to generate human-AI gap analysis')
            flash(error_msg, 'danger')
    
    return render_template(
        'dashboard/human_ai_gap.html',
        domains=domains,
        is_admin=is_admin(),
        title='Human-AI Gap Analysis'
    )


@dashboard_bp.route('/export-evaluations', methods=['GET', 'POST'])
@login_required
def export_evaluations():
    """Export evaluations to CSV."""
    # Initialize form
    form = ExportEvaluationsForm()
    
    # Set domain choices
    form.domain.choices = [('', 'All Domains')] + [(d, get_domain_label(d)) for d in CONTENT_DOMAINS]
    
    # Process form submission
    if form.validate_on_submit():
        domain = form.domain.data or None
        model_name = form.model_name.data or None
        source_type = form.source_type.data or None
        
        # Create filters
        filters = {}
        if domain:
            filters['domain'] = domain
        
        if model_name:
            filters['model_name'] = model_name
        
        if source_type:
            filters['source_type'] = source_type
        
        # Generate filename
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        filename = f'evaluations_{timestamp}.csv'
        filepath = f'static/exports/{filename}'
        
        # Ensure exports directory exists
        import os
        os.makedirs('static/exports', exist_ok=True)
        
        # Export data
        success, count = export_evaluations_to_csv(filepath, filters)
        
        if success:
            flash(f'Successfully exported {count} evaluations to CSV', 'success')
            return redirect(url_for('static', filename=f'exports/{filename}'))
        else:
            flash('Failed to export evaluations', 'danger')
    
    return render_template(
        'dashboard/export_evaluations.html',
        form=form,
        is_admin=is_admin(),
        title='Export Evaluations'
    )


@dashboard_bp.route('/quality-issues')
@admin_required
def quality_issues():
    """View quality control issues."""
    # Get quality issues
    issues = quality_controller.flag_low_quality_evaluations()
    
    return render_template(
        'dashboard/quality_issues.html',
        issues=issues,
        title='Quality Control Issues'
    )


@dashboard_bp.route('/evaluator/<int:user_id>')
@admin_required
def evaluator_analysis(user_id):
    """Analyze a specific evaluator's patterns."""
    with get_db_session() as session:
        # Get user
        user = session.query(User).get(user_id)
        
        if not user:
            flash('User not found', 'danger')
            return redirect(url_for('dashboard_bp.admin'))
        
        # Get evaluation statistics
        stats = evaluator.get_evaluation_statistics(user_id)
        
        # Get evaluator patterns
        patterns = quality_controller.analyze_evaluator_patterns(user_id)
        
        # Get recent evaluations
        recent_evaluations = session.query(
            Evaluation,
            Content.title,
            Content.domain
        ).join(
            Content,
            Evaluation.content_id == Content.id
        ).filter(
            Evaluation.evaluator_id == user_id,
            Evaluation.completion_time.isnot(None)
        ).order_by(
            Evaluation.completion_time.desc()
        ).limit(10).all()
    
    return render_template(
        'dashboard/evaluator_analysis.html',
        user=user,
        stats=stats,
        patterns=patterns,
        recent_evaluations=recent_evaluations,
        title=f'Evaluator Analysis: {user.username}'
    )


@dashboard_bp.route('/improvement-suggestions')
@admin_required
def improvement_suggestions():
    """View improvement suggestions."""
    # Get filter parameters
    model_name = request.args.get('model_name', '')
    domain = request.args.get('domain', '')
    status = request.args.get('status', '')
    
    # Get suggestions
    suggestions = analytics_engine.get_improvement_suggestions(
        model_name or None,
        domain or None,
        status or None
    )
    
    # Get models and domains for filter dropdowns
    with get_db_session() as session:
        models = session.query(Content.model_name).filter(
            Content.source_type == 'ai',
            Content.model_name.isnot(None)
        ).distinct().all()
        
        models = [m[0] for m in models if m[0]]
    
    return render_template(
        'dashboard/improvement_suggestions.html',
        suggestions=suggestions,
        models=models,
        domains=CONTENT_DOMAINS,
        selected_model=model_name,
        selected_domain=domain,
        selected_status=status,
        title='Improvement Suggestions'
    )


@dashboard_bp.route('/api/dashboard/stats')
@login_required
def api_dashboard_stats():
    """API endpoint for dashboard statistics."""
    with get_db_session() as session:
        # Get counts
        content_count = session.query(Content).count()
        evaluation_count = session.query(Evaluation).count()
        completed_count = session.query(Evaluation).filter(
            Evaluation.completion_time.isnot(None)
        ).count()
        
        # Get content type breakdown
        ai_content = session.query(Content).filter(Content.source_type == 'ai').count()
        human_content = session.query(Content).filter(Content.source_type == 'human').count()
        
        # Get domain breakdown
        domains = {}
        for domain in CONTENT_DOMAINS:
            count = session.query(Content).filter(Content.domain == domain).count()
            domains[domain] = count
        
        # Get recent activity
        activity = []
        recent_evals = session.query(
            Evaluation,
            User.username,
            Content.title
        ).join(
            User,
            Evaluation.evaluator_id == User.id
        ).join(
            Content,
            Evaluation.content_id == Content.id
        ).filter(
            Evaluation.completion_time.isnot(None)
        ).order_by(
            Evaluation.completion_time.desc()
        ).limit(5).all()
        
        for eval, username, title in recent_evals:
            activity.append({
                'type': 'evaluation',
                'user': username,
                'content': title,
                'timestamp': eval.completion_time.isoformat() if eval.completion_time else None
            })
    
    return jsonify({
        'content_count': content_count,
        'evaluation_count': evaluation_count,
        'completion_rate': round(completed_count / evaluation_count * 100, 1) if evaluation_count else 0,
        'content_types': {
            'ai': ai_content,
            'human': human_content
        },
        'domains': domains,
        'recent_activity': activity
    })


@dashboard_bp.route('/api/report/<int:report_id>')
@login_required
def api_report(report_id):
    """API endpoint to get a specific report."""
    report = analytics_engine.get_analytics_report(report_id)
    
    if not report:
        return jsonify({'error': 'Report not found'}), 404
    
    # Check permission
    if not is_admin() and report.get('created_by') != current_user.id:
        return jsonify({'error': 'Not authorized to view this report'}), 403
    
    return jsonify(report)


# Error handlers
@dashboard_bp.app_errorhandler(404)
def page_not_found(e):
    """Handle 404 errors."""
    return render_template('errors/404.html'), 404


@dashboard_bp.app_errorhandler(500)
def server_error(e):
    """Handle 500 errors."""
    logger.error(f"Server error: {e}")
    return render_template('errors/500.html'), 500