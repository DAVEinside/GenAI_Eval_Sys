"""
Main application entry point for the Generative AI Content Evaluation System.
"""
import logging
import os
from flask import Flask, render_template, redirect, url_for, flash, request, jsonify, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash
from datetime import datetime, timedelta

from database import init_db, get_db_session
from models import User, Content, Evaluation, EvaluationCriterion
from evaluator import Evaluator
from quality_control import QualityController
from analytics import AnalyticsEngine
from interfaces.web_interface import web_bp
from interfaces.expert_portal import expert_bp
from interfaces.dashboard import dashboard_bp
from config import APP_PORT, APP_HOST, SECRET_KEY, DEBUG, CONTENT_DOMAINS, EVALUATION_CRITERIA

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask application
app = Flask(__name__, 
            template_folder='templates',
            static_folder='static')

# Configure application
app.config['SECRET_KEY'] = SECRET_KEY
app.config['DEBUG'] = DEBUG
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)

# Initialize LoginManager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'web_bp.login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'info'

# Register blueprints
app.register_blueprint(web_bp)
app.register_blueprint(expert_bp, url_prefix='/expert')
app.register_blueprint(dashboard_bp, url_prefix='/dashboard')

# Initialize core components
evaluator = Evaluator()
quality_controller = QualityController()
analytics_engine = AnalyticsEngine()


@login_manager.user_loader
def load_user(user_id):
    """Load a user from the database."""
    with get_db_session() as session:
        return session.query(User).get(int(user_id))


@app.before_request
def before_request():
    """Perform actions before each request."""
    # Update session last_seen time for active users
    if current_user.is_authenticated:
        session['last_seen'] = datetime.utcnow().isoformat()


@app.route('/')
def index():
    """Main landing page."""
    return render_template('index.html', 
                          content_domains=CONTENT_DOMAINS,
                          current_year=datetime.now().year)


@app.route('/about')
def about():
    """About page with system information."""
    return render_template('about.html')


@app.route('/health')
def health_check():
    """Health check endpoint for monitoring."""
    return jsonify({'status': 'ok', 'timestamp': datetime.utcnow().isoformat()})


@app.route('/api/statistics')
def api_statistics():
    """API endpoint for basic system statistics."""
    with get_db_session() as session:
        total_content = session.query(Content).count()
        total_evaluations = session.query(Evaluation).count()
        completed_evaluations = session.query(Evaluation).filter(
            Evaluation.completion_time.isnot(None)
        ).count()
        
        content_by_domain = {}
        for domain in CONTENT_DOMAINS:
            count = session.query(Content).filter(Content.domain == domain).count()
            content_by_domain[domain] = count
        
        content_by_source = {
            'ai': session.query(Content).filter(Content.source_type == 'ai').count(),
            'human': session.query(Content).filter(Content.source_type == 'human').count()
        }
        
        return jsonify({
            'total_content': total_content,
            'total_evaluations': total_evaluations,
            'completed_evaluations': completed_evaluations,
            'completion_rate': round(completed_evaluations / total_evaluations * 100, 1) if total_evaluations else 0,
            'content_by_domain': content_by_domain,
            'content_by_source': content_by_source
        })


@app.errorhandler(404)
def page_not_found(e):
    """Handle 404 errors."""
    return render_template('errors/404.html'), 404


@app.errorhandler(500)
def server_error(e):
    """Handle 500 errors."""
    logger.error(f"Server error: {e}")
    return render_template('errors/500.html'), 500


def initialize_application():
    """Initialize the application database and default data."""
    logger.info("Initializing application...")
    
    # Initialize database
    success = init_db()
    if not success:
        logger.error("Failed to initialize database")
        return False
    
    logger.info("Application initialized successfully")
    return True


if __name__ == '__main__':
    # Initialize the application if needed
    initialize_application()
    
    # Run the Flask application
    app.run(host=APP_HOST, port=APP_PORT)