"""
Core evaluation logic for the Generative AI Content Evaluation System.
"""
import logging
from datetime import datetime
import random
import json
from typing import Dict, List, Optional, Tuple, Any

from database import get_db_session
from models import (
    Content, Evaluation, EvaluationScore, EvaluationCriterion,
    QualityCheckQuestion, User, ExpertProfile
)
from quality_control import QualityController
from config import CONTENT_DOMAINS, EVALUATION_CRITERIA

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Evaluator:
    """
    Core class responsible for managing the evaluation process and logic.
    """
    
    def __init__(self):
        """Initialize the evaluator."""
        self.quality_controller = QualityController()
    
    def get_content_for_evaluation(
        self, 
        domain: str = None, 
        source_type: str = None, 
        model_name: str = None, 
        exclude_ids: List[int] = None
    ) -> Optional[Content]:
        """
        Get content for evaluation based on filtering criteria.
        
        Args:
            domain: Content domain (e.g., creative_writing)
            source_type: 'ai' or 'human'
            model_name: Specific AI model to filter by
            exclude_ids: List of content IDs to exclude
            
        Returns:
            Content object or None if no suitable content is found
        """
        with get_db_session() as session:
            query = session.query(Content)
            
            if domain:
                query = query.filter(Content.domain == domain)
            
            if source_type:
                query = query.filter(Content.source_type == source_type)
            
            if model_name:
                query = query.filter(Content.model_name == model_name)
            
            if exclude_ids:
                query = query.filter(~Content.id.in_(exclude_ids))
            
            # Get contents that need more evaluations first
            contents = query.all()
            
            if not contents:
                return None
            
            # Sort by number of existing evaluations (prioritize those with fewer)
            contents_with_counts = []
            for content in contents:
                eval_count = session.query(Evaluation).filter(
                    Evaluation.content_id == content.id
                ).count()
                contents_with_counts.append((content, eval_count))
            
            # Sort by evaluation count and add some randomness for fair distribution
            contents_with_counts.sort(key=lambda x: (x[1], random.random()))
            
            return contents_with_counts[0][0] if contents_with_counts else None

    def get_evaluation_criteria(self, domain: str = None) -> List[EvaluationCriterion]:
        """
        Get evaluation criteria, optionally filtered by domain.
        
        Args:
            domain: Content domain to get specific criteria for
            
        Returns:
            List of EvaluationCriterion objects
        """
        with get_db_session() as session:
            query = session.query(EvaluationCriterion)
            
            if domain:
                # Get both domain-specific and general criteria
                query = query.filter((EvaluationCriterion.domain == domain) | 
                                    (EvaluationCriterion.domain.is_(None)))
            
            criteria = query.all()
            return criteria

    def start_evaluation(
        self, 
        user_id: int, 
        content_id: int
    ) -> Optional[int]:
        """
        Start a new evaluation session.
        
        Args:
            user_id: ID of the evaluator
            content_id: ID of the content to evaluate
            
        Returns:
            Evaluation ID if successful, None otherwise
        """
        with get_db_session() as session:
            # Check if user and content exist
            user = session.query(User).get(user_id)
            content = session.query(Content).get(content_id)
            
            if not user or not content:
                logger.error(f"User ID {user_id} or Content ID {content_id} not found")
                return None
            
            # Check if this user already evaluated this content
            existing = session.query(Evaluation).filter(
                Evaluation.evaluator_id == user_id,
                Evaluation.content_id == content_id
            ).first()
            
            if existing:
                logger.warning(f"User {user_id} already evaluated content {content_id}")
                return existing.id
            
            # Create new evaluation record
            evaluation = Evaluation(
                evaluator_id=user_id,
                content_id=content_id,
                start_time=datetime.utcnow()
            )
            
            session.add(evaluation)
            session.commit()
            
            logger.info(f"Started evaluation ID {evaluation.id} for user {user_id} on content {content_id}")
            return evaluation.id

    def submit_evaluation(
        self,
        evaluation_id: int,
        scores: Dict[int, float],
        overall_rating: float,
        comments: str = None,
        quality_check_answers: Dict[int, str] = None
    ) -> Tuple[bool, str]:
        """
        Submit a completed evaluation.
        
        Args:
            evaluation_id: ID of the evaluation session
            scores: Dictionary mapping criterion_id to score
            overall_rating: Overall rating for the content
            comments: Optional evaluator comments
            quality_check_answers: Answers to quality check questions
            
        Returns:
            Tuple of (success, message)
        """
        with get_db_session() as session:
            evaluation = session.query(Evaluation).get(evaluation_id)
            
            if not evaluation:
                return False, f"Evaluation ID {evaluation_id} not found"
            
            if evaluation.completion_time:
                return False, f"Evaluation ID {evaluation_id} already completed"
            
            # Calculate duration
            now = datetime.utcnow()
            duration = (now - evaluation.start_time).total_seconds()
            
            # Check quality control requirements
            passed_checks = True
            if quality_check_answers:
                passed_checks = self.quality_controller.validate_quality_checks(
                    quality_check_answers
                )
            
            # Update evaluation record
            evaluation.completion_time = now
            evaluation.duration_seconds = int(duration)
            evaluation.overall_rating = overall_rating
            evaluation.comments = comments
            evaluation.passed_quality_checks = passed_checks
            
            # Add individual scores
            for criterion_id, score in scores.items():
                # Validate criterion exists
                criterion = session.query(EvaluationCriterion).get(criterion_id)
                if not criterion:
                    logger.warning(f"Criterion ID {criterion_id} not found")
                    continue
                
                # Validate score is within range
                if score < criterion.scale_min or score > criterion.scale_max:
                    logger.warning(
                        f"Score {score} out of range for criterion {criterion_id} "
                        f"({criterion.scale_min}-{criterion.scale_max})"
                    )
                    continue
                
                # Create score record
                score_record = EvaluationScore(
                    evaluation_id=evaluation_id,
                    criterion_id=criterion_id,
                    score=score
                )
                session.add(score_record)
            
            session.commit()
            
            logger.info(f"Completed evaluation ID {evaluation_id}")
            return True, "Evaluation submitted successfully"

    def get_pending_evaluations(self, user_id: int) -> List[Dict[str, Any]]:
        """
        Get list of pending evaluations for a user.
        
        Args:
            user_id: ID of the evaluator
            
        Returns:
            List of pending evaluation details
        """
        with get_db_session() as session:
            evaluations = session.query(Evaluation).filter(
                Evaluation.evaluator_id == user_id,
                Evaluation.completion_time.is_(None)
            ).all()
            
            result = []
            for eval in evaluations:
                content = session.query(Content).get(eval.content_id)
                result.append({
                    "evaluation_id": eval.id,
                    "content_id": content.id,
                    "title": content.title,
                    "domain": content.domain,
                    "start_time": eval.start_time.isoformat(),
                    "elapsed_seconds": (datetime.utcnow() - eval.start_time).total_seconds()
                })
            
            return result

    def get_evaluation_statistics(self, user_id: int = None) -> Dict[str, Any]:
        """
        Get evaluation statistics, optionally filtered by user.
        
        Args:
            user_id: Optional user ID to filter by
            
        Returns:
            Dictionary of statistics
        """
        with get_db_session() as session:
            query = session.query(Evaluation)
            
            if user_id:
                query = query.filter(Evaluation.evaluator_id == user_id)
            
            total_evaluations = query.count()
            completed_evaluations = query.filter(
                Evaluation.completion_time.isnot(None)
            ).count()
            
            # Get domain statistics
            domains = {}
            contents = session.query(Content).join(
                Evaluation, Content.id == Evaluation.content_id
            )
            
            if user_id:
                contents = contents.filter(Evaluation.evaluator_id == user_id)
            
            for domain in CONTENT_DOMAINS:
                domain_count = contents.filter(Content.domain == domain).count()
                domains[domain] = domain_count
            
            # Get AI vs human statistics
            ai_content = contents.filter(Content.source_type == 'ai').count()
            human_content = contents.filter(Content.source_type == 'human').count()
            
            return {
                "total_evaluations": total_evaluations,
                "completed_evaluations": completed_evaluations,
                "completion_rate": round(completed_evaluations / total_evaluations * 100, 1) if total_evaluations else 0,
                "domain_distribution": domains,
                "content_type_distribution": {
                    "ai": ai_content,
                    "human": human_content
                }
            }

    def get_expert_qualification(self, user_id: int, domain: str) -> bool:
        """
        Check if a user is qualified to evaluate content in a specific domain.
        
        Args:
            user_id: User ID to check
            domain: Content domain
            
        Returns:
            Boolean indicating if user is qualified
        """
        with get_db_session() as session:
            # Check if user exists and is active
            user = session.query(User).filter(
                User.id == user_id,
                User.is_active == True
            ).first()
            
            if not user:
                return False
            
            # Admins can evaluate any domain
            if user.role == 'admin':
                return True
            
            # Check expert profile
            profile = session.query(ExpertProfile).filter(
                ExpertProfile.user_id == user_id,
                ExpertProfile.verified == True
            ).first()
            
            if not profile:
                return False
            
            # Check if domain is in expertise domains
            domains = profile.domains
            if isinstance(domains, str):
                try:
                    domains = json.loads(domains)
                except:
                    domains = []
            
            return domain in domains if domains else False

    def assign_content_to_experts(self, content_id: int, domain: str) -> List[int]:
        """
        Assign content to qualified experts for evaluation.
        
        Args:
            content_id: Content ID to assign
            domain: Content domain for expert matching
            
        Returns:
            List of evaluation IDs created
        """
        evaluation_ids = []
        
        with get_db_session() as session:
            # Find qualified experts
            expert_profiles = session.query(ExpertProfile).filter(
                ExpertProfile.verified == True
            ).all()
            
            qualified_experts = []
            for profile in expert_profiles:
                domains = profile.domains
                if isinstance(domains, str):
                    try:
                        domains = json.loads(domains)
                    except:
                        domains = []
                
                if domain in domains:
                    # Check if user is active
                    user = session.query(User).filter(
                        User.id == profile.user_id,
                        User.is_active == True
                    ).first()
                    
                    if user:
                        qualified_experts.append(user.id)
            
            logger.info(f"Found {len(qualified_experts)} qualified experts for domain {domain}")
            
            # Create evaluation assignments
            for expert_id in qualified_experts:
                # Check if already assigned
                existing = session.query(Evaluation).filter(
                    Evaluation.evaluator_id == expert_id,
                    Evaluation.content_id == content_id
                ).first()
                
                if existing:
                    evaluation_ids.append(existing.id)
                    continue
                
                # Create new evaluation
                evaluation = Evaluation(
                    evaluator_id=expert_id,
                    content_id=content_id,
                    start_time=datetime.utcnow()
                )
                
                session.add(evaluation)
                session.flush()
                evaluation_ids.append(evaluation.id)
            
            session.commit()
        
        return evaluation_ids