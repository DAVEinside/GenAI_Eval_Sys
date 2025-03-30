"""
Expert portal routes for the Generative AI Content Evaluation System.
"""
import logging
from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, session
from flask_login import login_required, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, IntegerField, SelectMultipleField, SubmitField
from wtforms.validators import DataRequired, Email, Length, Optional, NumberRange

from database import get_db_session
from models import User, ExpertProfile, Content, Evaluation, EvaluationCriterion
from config import CONTENT_DOMAINS
from evaluator import Evaluator
from quality_control import QualityController
from utils import truncate_text, format_timestamp, get_domain_label

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create Blueprint
expert_bp = Blueprint('expert_bp', __name__)

# Initialize components
evaluator = Evaluator()
quality_controller = QualityController()


# Form classes
class ExpertProfileForm(FlaskForm):
    """Form for updating expert profile."""
    domains = SelectMultipleField('Expertise Domains', choices=[], validators=[DataRequired()])
    years_experience = IntegerField('Years of Experience', validators=[
        DataRequired(), 
        NumberRange(min=1, max=100, message="Years must be between 1 and 100")
    ])
    qualifications = TextAreaField('Professional Qualifications', validators=[Optional(), Length(max=2000)])
    bio = TextAreaField('Professional Bio', validators=[Optional(), Length(max=2000)])
    submit = SubmitField('Save Profile')


# Helper functions
def is_expert_verified():
    """Check if the current user is a verified expert."""
    if not current_user.is_authenticated:
        return False
    
    with get_db_session() as session:
        profile = session.query(ExpertProfile).filter(
            ExpertProfile.user_id == current_user.id,
            ExpertProfile.verified == True
        ).first()
        
        return profile is not None


def get_expert_domains():
    """Get domains where the current user is considered an expert."""
    if not current_user.is_authenticated:
        return []
    
    with get_db_session() as session:
        profile = session.query(ExpertProfile).filter(
            ExpertProfile.user_id == current_user.id
        ).first()
        
        if not profile:
            return []
        
        domains = profile.domains
        if isinstance(domains, str):
            import json
            try:
                domains = json.loads(domains)
            except:
                domains = []
        
        return domains if domains else []


# Routes
@expert_bp.route('/')
@login_required
def index():
    """Expert portal landing page."""
    if not is_expert_verified():
        return redirect(url_for('expert_bp.become_expert'))
    
    # Get expert domains
    domains = get_expert_domains()
    
    # Get assigned evaluations
    with get_db_session() as session:
        assigned_evaluations = session.query(
            Evaluation,
            Content.title,
            Content.domain
        ).join(
            Content,
            Evaluation.content_id == Content.id
        ).filter(
            Evaluation.evaluator_id == current_user.id,
            Evaluation.completion_time.is_(None)
        ).order_by(
            Evaluation.start_time.desc()
        ).limit(10).all()
        
        # Get recent completed evaluations
        completed_evaluations = session.query(
            Evaluation,
            Content.title,
            Content.domain
        ).join(
            Content,
            Evaluation.content_id == Content.id
        ).filter(
            Evaluation.evaluator_id == current_user.id,
            Evaluation.completion_time.isnot(None)
        ).order_by(
            Evaluation.completion_time.desc()
        ).limit(5).all()
        
        # Count evaluations by domain
        domain_counts = {}
        for domain in domains:
            count = session.query(Evaluation).join(
                Content,
                Evaluation.content_id == Content.id
            ).filter(
                Evaluation.evaluator_id == current_user.id,
                Content.domain == domain
            ).count()
            
            domain_counts[domain] = count
    
    return render_template(
        'expert/index.html',
        domains=domains,
        domain_counts=domain_counts,
        assigned_evaluations=assigned_evaluations,
        completed_evaluations=completed_evaluations,
        is_expert=True,
        title='Expert Portal'
    )


@expert_bp.route('/become-expert', methods=['GET', 'POST'])
@login_required
def become_expert():
    """Page for users to create or update their expert profile."""
    # Check if user already has a profile
    with get_db_session() as session:
        profile = session.query(ExpertProfile).filter(
            ExpertProfile.user_id == current_user.id
        ).first()
    
    # Initialize form
    form = ExpertProfileForm()
    
    # Set domain choices
    form.domains.choices = [(d, get_domain_label(d)) for d in CONTENT_DOMAINS]
    
    # Pre-fill form if profile exists
    if profile and request.method == 'GET':
        form.domains.data = profile.domains if isinstance(profile.domains, list) else []
        form.years_experience.data = profile.years_experience
        form.qualifications.data = profile.qualifications
        form.bio.data = profile.bio
    
    if form.validate_on_submit():
        domains = form.domains.data
        years_experience = form.years_experience.data
        qualifications = form.qualifications.data
        bio = form.bio.data
        
        from utils import create_expert_profile
        profile_id = create_expert_profile(
            current_user.id,
            domains,
            years_experience,
            qualifications,
            bio,
            verified=False if not profile else profile.verified
        )
        
        if profile_id:
            flash('Expert profile updated successfully. It will be reviewed by an administrator.', 'success')
            return redirect(url_for('expert_bp.index'))
        else:
            flash('Failed to update expert profile', 'danger')
    
    return render_template(
        'expert/become_expert.html',
        form=form,
        profile=profile,
        title='Become an Expert'
    )


@expert_bp.route('/assignments')
@login_required
def assignments():
    """View assigned content for evaluation."""
    if not is_expert_verified():
        flash('You must be a verified expert to view assignments', 'warning')
        return redirect(url_for('expert_bp.become_expert'))
    
    # Get filter parameters
    status = request.args.get('status', 'pending')
    domain = request.args.get('domain', '')
    
    with get_db_session() as session:
        # Base query
        query = session.query(
            Evaluation,
            Content.title,
            Content.domain,
            Content.source_type,
            Content.model_name
        ).join(
            Content,
            Evaluation.content_id == Content.id
        ).filter(
            Evaluation.evaluator_id == current_user.id
        )
        
        # Apply filters
        if status == 'completed':
            query = query.filter(Evaluation.completion_time.isnot(None))
        elif status == 'pending':
            query = query.filter(Evaluation.completion_time.is_(None))
        
        if domain:
            query = query.filter(Content.domain == domain)
        
        # Add expert domains filter if no specific domain selected
        if not domain:
            expert_domains = get_expert_domains()
            if expert_domains:
                query = query.filter(Content.domain.in_(expert_domains))
        
        # Order by date
        if status == 'completed':
            query = query.order_by(Evaluation.completion_time.desc())
        else:
            query = query.order_by(Evaluation.start_time.desc())
        
        # Get paginated results
        page = request.args.get('page', 1, type=int)
        per_page = 10
        offset = (page - 1) * per_page
        
        total = query.count()
        assignments = query.limit(per_page).offset(offset).all()
    
    # Calculate pagination
    total_pages = (total + per_page - 1) // per_page
    
    return render_template(
        'expert/assignments.html',
        assignments=assignments,
        status=status,
        domain=domain,
        expert_domains=get_expert_domains(),
        page=page,
        total_pages=total_pages,
        total=total,
        title='My Assignments'
    )


@expert_bp.route('/content/<int:content_id>')
@login_required
def content_detail(content_id):
    """View content details as an expert."""
    if not is_expert_verified():
        flash('You must be a verified expert to view content details', 'warning')
        return redirect(url_for('expert_bp.become_expert'))
    
    with get_db_session() as session:
        content = session.query(Content).get(content_id)
        
        if not content:
            flash('Content not found', 'danger')
            return redirect(url_for('expert_bp.assignments'))
        
        # Verify user has permission to view this content
        if content.domain not in get_expert_domains() and current_user.role != 'admin':
            flash('You do not have permission to view this content', 'danger')
            return redirect(url_for('expert_bp.assignments'))
        
        # Check if user has an assigned evaluation for this content
        evaluation = session.query(Evaluation).filter(
            Evaluation.evaluator_id == current_user.id,
            Evaluation.content_id == content_id
        ).first()
        
        if not evaluation:
            flash('This content is not assigned to you', 'warning')
            return redirect(url_for('expert_bp.assignments'))
    
    return render_template(
        'expert/content_detail.html',
        content=content,
        evaluation=evaluation,
        title='Content Detail'
    )


@expert_bp.route('/evaluate/<int:evaluation_id>', methods=['GET', 'POST'])
@login_required
def evaluate(evaluation_id):
    """Expert evaluation page."""
    if not is_expert_verified():
        flash('You must be a verified expert to evaluate content', 'warning')
        return redirect(url_for('expert_bp.become_expert'))
    
    with get_db_session() as session:
        # Get evaluation
        evaluation = session.query(Evaluation).get(evaluation_id)
        
        if not evaluation:
            flash('Evaluation not found', 'danger')
            return redirect(url_for('expert_bp.assignments'))
        
        # Verify user has permission to evaluate
        if evaluation.evaluator_id != current_user.id:
            flash('This evaluation is not assigned to you', 'danger')
            return redirect(url_for('expert_bp.assignments'))
        
        # Check if already completed
        if evaluation.completion_time:
            flash('This evaluation has already been completed', 'info')
            return redirect(url_for('expert_bp.view_evaluation', evaluation_id=evaluation_id))
        
        # Get content
        content = session.query(Content).get(evaluation.content_id)
        
        # Get criteria
        criteria = evaluator.get_evaluation_criteria(content.domain)
        
        # Generate quality checks (more for experts)
        quality_checks = quality_controller.generate_quality_checks(content.domain, count=3)
    
    if request.method == 'POST':
        # Validate form data
        from utils import validate_evaluation_data
        
        # Collect scores
        scores = {}
        for criterion in criteria:
            score_key = f'criterion_{criterion.id}'
            if score_key in request.form:
                try:
                    score = float(request.form[score_key])
                    scores[criterion.id] = score
                except (ValueError, TypeError):
                    flash(f'Invalid score for {criterion.name}', 'danger')
                    return redirect(url_for('expert_bp.evaluate', evaluation_id=evaluation_id))
        
        # Check if all criteria were scored
        if len(scores) != len(criteria):
            flash('Please score all criteria', 'danger')
            return redirect(url_for('expert_bp.evaluate', evaluation_id=evaluation_id))
        
        # Get overall rating
        overall_rating = request.form.get('overall_rating')
        try:
            overall_rating = float(overall_rating)
            if overall_rating < 1 or overall_rating > 5:
                flash('Overall rating must be between 1 and 5', 'danger')
                return redirect(url_for('expert_bp.evaluate', evaluation_id=evaluation_id))
        except (ValueError, TypeError):
            flash('Invalid overall rating', 'danger')
            return redirect(url_for('expert_bp.evaluate', evaluation_id=evaluation_id))
        
        # Get comments
        comments = request.form.get('comments', '')
        
        # Collect quality check answers
        quality_check_answers = {}
        for check in quality_checks:
            answer_key = f'quality_check_{check["id"]}'
            if answer_key in request.form:
                quality_check_answers[check["id"]] = request.form[answer_key]
        
        # Submit evaluation
        success, message = evaluator.submit_evaluation(
            evaluation_id,
            scores,
            overall_rating,
            comments,
            quality_check_answers
        )
        
        if success:
            flash('Evaluation submitted successfully', 'success')
            return redirect(url_for('expert_bp.view_evaluation', evaluation_id=evaluation_id))
        else:
            flash(f'Failed to submit evaluation: {message}', 'danger')
            return redirect(url_for('expert_bp.evaluate', evaluation_id=evaluation_id))
    
    return render_template(
        'expert/evaluate.html',
        evaluation=evaluation,
        content=content,
        criteria=criteria,
        quality_checks=quality_checks,
        title='Expert Evaluation'
    )


@expert_bp.route('/view-evaluation/<int:evaluation_id>')
@login_required
def view_evaluation(evaluation_id):
    """View completed evaluation details."""
    if not is_expert_verified():
        flash('You must be a verified expert to view evaluations', 'warning')
        return redirect(url_for('expert_bp.become_expert'))
    
    with get_db_session() as session:
        # Get evaluation with joins
        evaluation = session.query(Evaluation).get(evaluation_id)
        
        if not evaluation:
            flash('Evaluation not found', 'danger')
            return redirect(url_for('expert_bp.assignments'))
        
        # Verify user has permission to view
        if evaluation.evaluator_id != current_user.id and current_user.role != 'admin':
            flash('You do not have permission to view this evaluation', 'danger')
            return redirect(url_for('expert_bp.assignments'))
        
        # Get content
        content = session.query(Content).get(evaluation.content_id)
        
        # Get scores
        scores = session.query(
            EvaluationScore, 
            EvaluationCriterion.name
        ).join(
            EvaluationCriterion,
            EvaluationScore.criterion_id == EvaluationCriterion.id
        ).filter(
            EvaluationScore.evaluation_id == evaluation_id
        ).all()
    
    return render_template(
        'expert/view_evaluation.html',
        evaluation=evaluation,
        content=content,
        scores=scores,
        title='View Evaluation'
    )


@expert_bp.route('/dashboard')
@login_required
def dashboard():
    """Expert dashboard with statistics."""
    if not is_expert_verified():
        flash('You must be a verified expert to view the dashboard', 'warning')
        return redirect(url_for('expert_bp.become_expert'))
    
    # Get statistics
    stats = evaluator.get_evaluation_statistics(current_user.id)
    
    # Get domains and counts
    domains = get_expert_domains()
    
    with get_db_session() as session:
        # Get counts by domain
        domain_stats = {}
        for domain in domains:
            # Count evaluations in this domain
            eval_count = session.query(Evaluation).join(
                Content,
                Evaluation.content_id == Content.id
            ).filter(
                Evaluation.evaluator_id == current_user.id,
                Content.domain == domain
            ).count()
            
            # Count completed evaluations
            completed_count = session.query(Evaluation).join(
                Content,
                Evaluation.content_id == Content.id
            ).filter(
                Evaluation.evaluator_id == current_user.id,
                Content.domain == domain,
                Evaluation.completion_time.isnot(None)
            ).count()
            
            domain_stats[domain] = {
                'total': eval_count,
                'completed': completed_count,
                'completion_rate': round(completed_count / eval_count * 100, 1) if eval_count else 0
            }
        
        # Get quality check stats
        quality_stats = {
            'passed': session.query(Evaluation).filter(
                Evaluation.evaluator_id == current_user.id,
                Evaluation.passed_quality_checks == True
            ).count(),
            'failed': session.query(Evaluation).filter(
                Evaluation.evaluator_id == current_user.id,
                Evaluation.passed_quality_checks == False
            ).count(),
            'unknown': session.query(Evaluation).filter(
                Evaluation.evaluator_id == current_user.id,
                Evaluation.passed_quality_checks.is_(None),
                Evaluation.completion_time.isnot(None)
            ).count()
        }
        
        total_with_checks = sum(quality_stats.values())
        quality_stats['pass_rate'] = round(quality_stats['passed'] / total_with_checks * 100, 1) if total_with_checks else 0
    
    return render_template(
        'expert/dashboard.html',
        stats=stats,
        domain_stats=domain_stats,
        quality_stats=quality_stats,
        title='Expert Dashboard'
    )


@expert_bp.route('/api/expert/statistics')
@login_required
def api_expert_statistics():
    """API endpoint for expert statistics."""
    if not is_expert_verified():
        return jsonify({'error': 'Not authorized as an expert'}), 403
    
    # Get statistics
    stats = evaluator.get_evaluation_statistics(current_user.id)
    
    return jsonify(stats)


@expert_bp.route('/api/domain-content/<domain>')
@login_required
def api_domain_content(domain):
    """API endpoint to get content in a specific domain."""
    if not is_expert_verified():
        return jsonify({'error': 'Not authorized as an expert'}), 403
    
    # Check if user is expert in this domain
    expert_domains = get_expert_domains()
    if domain not in expert_domains and current_user.role != 'admin':
        return jsonify({'error': 'Not authorized for this domain'}), 403
    
    with get_db_session() as session:
        # Get content in this domain
        content_items = session.query(Content).filter(
            Content.domain == domain
        ).order_by(
            Content.created_at.desc()
        ).limit(20).all()
        
        result = [{
            'id': item.id,
            'title': item.title,
            'source_type': item.source_type,
            'model_name': item.model_name,
            'created_at': item.created_at.isoformat() if item.created_at else None
        } for item in content_items]
        
        return jsonify(result)


# Error handlers
@expert_bp.app_errorhandler(404)
def page_not_found(e):
    """Handle 404 errors."""
    return render_template('errors/404.html'), 404


@expert_bp.app_errorhandler(500)
def server_error(e):
    """Handle 500 errors."""
    logger.error(f"Server error: {e}")
    return render_template('errors/500.html'), 500