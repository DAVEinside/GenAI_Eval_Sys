"""
Database initialization and session management for the Generative AI Content Evaluation System.
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.ext.declarative import declarative_base
from contextlib import contextmanager
import logging

from config import DATABASE_URI
from models import Base, User, ExpertProfile, Content, EvaluationCriterion, Evaluation, EvaluationScore, QualityCheckQuestion, AnalyticsReport, ImprovementSuggestion

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create engine and session factory
engine = create_engine(DATABASE_URI, echo=False)
session_factory = sessionmaker(bind=engine)
Session = scoped_session(session_factory)


@contextmanager
def get_db_session():
    """Context manager for database sessions."""
    session = Session()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Database error: {e}")
        raise
    finally:
        session.close()


def init_db():
    """Initialize the database by creating all tables if they don't exist."""
    try:
        # Create tables if they don't exist
        Base.metadata.create_all(engine)
        logger.info("Database tables created successfully")
        
        # Initialize with default data if needed
        with get_db_session() as session:
            # Check if we need to add initial data
            if session.query(EvaluationCriterion).count() == 0:
                _add_default_criteria(session)
                
            if session.query(User).filter_by(username='admin').count() == 0:
                _create_admin_user(session)
                
        logger.info("Database initialized with default data")
        return True
        
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        return False


def _add_default_criteria(session):
    """Add default evaluation criteria."""
    default_criteria = [
        EvaluationCriterion(name="accuracy", description="Factual correctness and absence of errors", scale_min=1, scale_max=5),
        EvaluationCriterion(name="coherence", description="Logical flow and consistency of ideas", scale_min=1, scale_max=5),
        EvaluationCriterion(name="relevance", description="Appropriateness to the given topic or context", scale_min=1, scale_max=5),
        EvaluationCriterion(name="creativity", description="Originality and innovative thinking", scale_min=1, scale_max=5),
        EvaluationCriterion(name="completeness", description="Comprehensive coverage of the subject matter", scale_min=1, scale_max=5),
        EvaluationCriterion(name="language_quality", description="Grammar, vocabulary, and overall writing quality", scale_min=1, scale_max=5),
    ]
    
    for criterion in default_criteria:
        session.add(criterion)
    
    logger.info(f"Added {len(default_criteria)} default evaluation criteria")


def _create_admin_user(session):
    """Create an admin user."""
    from werkzeug.security import generate_password_hash
    
    admin_password = os.getenv("ADMIN_PASSWORD", "admin123")  # Should be changed in production
    
    admin_user = User(
        username="admin",
        email="admin@example.com",
        password_hash=generate_password_hash(admin_password),
        first_name="Admin",
        last_name="User",
        role="admin",
        is_active=True
    )
    
    session.add(admin_user)
    logger.info("Created admin user")


def drop_db():
    """Drop all tables from the database."""
    try:
        Base.metadata.drop_all(engine)
        logger.info("Database tables dropped successfully")
        return True
    except Exception as e:
        logger.error(f"Error dropping database tables: {e}")
        return False


def get_model_counts():
    """Get count of records for each model."""
    with get_db_session() as session:
        counts = {
            "users": session.query(User).count(),
            "expert_profiles": session.query(ExpertProfile).count(),
            "contents": session.query(Content).count(),
            "evaluations": session.query(Evaluation).count(),
            "evaluation_scores": session.query(EvaluationScore).count(),
            "quality_check_questions": session.query(QualityCheckQuestion).count(),
            "analytics_reports": session.query(AnalyticsReport).count(),
            "improvement_suggestions": session.query(ImprovementSuggestion).count(),
        }
        return counts