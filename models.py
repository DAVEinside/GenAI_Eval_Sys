"""
Database models for the Generative AI Content Evaluation System.
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Text, DateTime, Boolean, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()

class User(Base):
    """User model for authentication and user management."""
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(256), nullable=False)
    first_name = Column(String(50))
    last_name = Column(String(50))
    role = Column(String(20), default='evaluator')  # 'evaluator', 'admin', 'manager'
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime)
    
    # Relationships
    evaluations = relationship("Evaluation", back_populates="evaluator")
    expertise = relationship("ExpertProfile", back_populates="user", uselist=False)
    
    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}', role='{self.role}')>"


class ExpertProfile(Base):
    """Expert profile with expertise details."""
    __tablename__ = 'expert_profiles'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), unique=True)
    domains = Column(JSON)  # List of expertise domains
    years_experience = Column(Integer)
    qualifications = Column(Text)
    bio = Column(Text)
    verified = Column(Boolean, default=False)
    
    # Relationships
    user = relationship("User", back_populates="expertise")
    
    def __repr__(self):
        return f"<ExpertProfile(id={self.id}, user_id={self.user_id}, domains={self.domains})>"


class Content(Base):
    """Content model for storing AI-generated and benchmark content."""
    __tablename__ = 'contents'
    
    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)
    text = Column(Text, nullable=False)
    domain = Column(String(50), nullable=False)  # e.g., creative_writing, technical_documentation
    source_type = Column(String(20), nullable=False)  # 'ai' or 'human'
    model_name = Column(String(100))  # AI model name if applicable
    metadata = Column(JSON)  # Additional metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    evaluations = relationship("Evaluation", back_populates="content")
    
    def __repr__(self):
        return f"<Content(id={self.id}, title='{self.title}', domain='{self.domain}', source_type='{self.source_type}')>"


class EvaluationCriterion(Base):
    """Evaluation criteria definitions."""
    __tablename__ = 'evaluation_criteria'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(50), unique=True, nullable=False)
    description = Column(Text)
    scale_min = Column(Integer, default=1)
    scale_max = Column(Integer, default=5)
    domain = Column(String(50))  # If criterion is domain-specific
    
    # Relationships
    scores = relationship("EvaluationScore", back_populates="criterion")
    
    def __repr__(self):
        return f"<EvaluationCriterion(id={self.id}, name='{self.name}')>"


class Evaluation(Base):
    """Evaluation session information."""
    __tablename__ = 'evaluations'
    
    id = Column(Integer, primary_key=True)
    evaluator_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    content_id = Column(Integer, ForeignKey('contents.id'), nullable=False)
    start_time = Column(DateTime, default=datetime.utcnow)
    completion_time = Column(DateTime)
    duration_seconds = Column(Integer)
    overall_rating = Column(Float)
    comments = Column(Text)
    passed_quality_checks = Column(Boolean)
    
    # Relationships
    evaluator = relationship("User", back_populates="evaluations")
    content = relationship("Content", back_populates="evaluations")
    scores = relationship("EvaluationScore", back_populates="evaluation")
    
    def __repr__(self):
        return f"<Evaluation(id={self.id}, evaluator_id={self.evaluator_id}, content_id={self.content_id})>"


class EvaluationScore(Base):
    """Individual criterion scores for an evaluation."""
    __tablename__ = 'evaluation_scores'
    
    id = Column(Integer, primary_key=True)
    evaluation_id = Column(Integer, ForeignKey('evaluations.id'), nullable=False)
    criterion_id = Column(Integer, ForeignKey('evaluation_criteria.id'), nullable=False)
    score = Column(Float, nullable=False)
    justification = Column(Text)
    
    # Relationships
    evaluation = relationship("Evaluation", back_populates="scores")
    criterion = relationship("EvaluationCriterion", back_populates="scores")
    
    def __repr__(self):
        return f"<EvaluationScore(id={self.id}, evaluation_id={self.evaluation_id}, criterion_id={self.criterion_id}, score={self.score})>"


class QualityCheckQuestion(Base):
    """Quality control questions to ensure reliable evaluations."""
    __tablename__ = 'quality_check_questions'
    
    id = Column(Integer, primary_key=True)
    question_text = Column(Text, nullable=False)
    correct_answer = Column(String(100), nullable=False)
    domain = Column(String(50))
    difficulty = Column(String(20), default='medium')  # easy, medium, hard
    active = Column(Boolean, default=True)
    
    def __repr__(self):
        return f"<QualityCheckQuestion(id={self.id}, difficulty='{self.difficulty}')>"


class AnalyticsReport(Base):
    """Analytics reports and insights generated from evaluations."""
    __tablename__ = 'analytics_reports'
    
    id = Column(Integer, primary_key=True)
    report_type = Column(String(50), nullable=False)  # e.g., model_comparison, domain_analysis
    title = Column(String(200), nullable=False)
    description = Column(Text)
    parameters = Column(JSON)  # Report generation parameters
    results = Column(JSON)  # Report results
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(Integer, ForeignKey('users.id'))
    
    def __repr__(self):
        return f"<AnalyticsReport(id={self.id}, report_type='{self.report_type}', title='{self.title}')>"


class ImprovementSuggestion(Base):
    """Improvement suggestions based on evaluation data."""
    __tablename__ = 'improvement_suggestions'
    
    id = Column(Integer, primary_key=True)
    model_name = Column(String(100), nullable=False)
    domain = Column(String(50), nullable=False)
    criterion = Column(String(50), nullable=False)
    current_score = Column(Float)
    target_score = Column(Float)
    suggestion = Column(Text, nullable=False)
    priority = Column(String(20), default='medium')  # high, medium, low
    status = Column(String(20), default='open')  # open, in_progress, implemented, closed
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<ImprovementSuggestion(id={self.id}, model_name='{self.model_name}', domain='{self.domain}', criterion='{self.criterion}')>"