"""
Quality control mechanisms for ensuring consistent and reliable human evaluations.
"""
import logging
import random
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any

from database import get_db_session
from models import (
    QualityCheckQuestion, Evaluation, User, Content, EvaluationScore, 
    EvaluationCriterion
)
from config import (
    MIN_EVALUATION_TIME_SECONDS, QUALITY_CHECK_FREQUENCY, 
    AGREEMENT_THRESHOLD, CONTENT_DOMAINS
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class QualityController:
    """
    Class responsible for implementing quality control measures for evaluations.
    """
    
    def __init__(self):
        """Initialize the quality controller."""
        pass
    
    def generate_quality_checks(self, domain: str = None, count: int = 2) -> List[Dict[str, Any]]:
        """
        Generate quality check questions for an evaluation.
        
        Args:
            domain: Content domain for domain-specific questions
            count: Number of questions to generate
            
        Returns:
            List of quality check questions
        """
        with get_db_session() as session:
            query = session.query(QualityCheckQuestion).filter(
                QualityCheckQuestion.active == True
            )
            
            if domain:
                # Get domain-specific questions and general questions
                query = query.filter((QualityCheckQuestion.domain == domain) | 
                                    (QualityCheckQuestion.domain.is_(None)))
            
            questions = query.all()
            
            if not questions:
                logger.warning(f"No quality check questions available for domain: {domain}")
                return []
            
            # Select random questions
            selected = random.sample(questions, min(count, len(questions)))
            
            return [
                {
                    "id": q.id,
                    "question": q.question_text,
                    "domain": q.domain
                }
                for q in selected
            ]
    
    def validate_quality_checks(self, answers: Dict[int, str]) -> bool:
        """
        Validate answers to quality check questions.
        
        Args:
            answers: Dictionary mapping question ID to answer
            
        Returns:
            Boolean indicating if quality checks passed
        """
        if not answers:
            return False
        
        correct_count = 0
        total_count = len(answers)
        
        with get_db_session() as session:
            for question_id, answer in answers.items():
                question = session.query(QualityCheckQuestion).get(question_id)
                
                if not question:
                    logger.warning(f"Quality check question ID {question_id} not found")
                    continue
                
                if question.correct_answer.lower() == answer.lower():
                    correct_count += 1
        
        # Must get at least 70% correct
        pass_threshold = 0.7
        passed = (correct_count / total_count) >= pass_threshold if total_count > 0 else False
        
        logger.info(f"Quality check validation: {correct_count}/{total_count} correct ({passed})")
        return passed
    
    def check_evaluation_time(self, evaluation_id: int) -> bool:
        """
        Check if an evaluation took a reasonable amount of time.
        
        Args:
            evaluation_id: ID of the evaluation to check
            
        Returns:
            Boolean indicating if time spent is reasonable
        """
        with get_db_session() as session:
            evaluation = session.query(Evaluation).get(evaluation_id)
            
            if not evaluation or not evaluation.completion_time:
                return False
            
            duration = evaluation.duration_seconds
            
            # Check if duration is reasonable
            if duration < MIN_EVALUATION_TIME_SECONDS:
                logger.warning(
                    f"Evaluation {evaluation_id} completed too quickly: {duration} seconds"
                )
                return False
            
            # Get content details to determine expected time
            content = session.query(Content).get(evaluation.content_id)
            if not content:
                return False
            
            # Calculate expected time based on content length
            text_length = len(content.text)
            expected_time = max(MIN_EVALUATION_TIME_SECONDS, text_length / 10)  # 10 chars per second as baseline
            
            # Allow some flexibility (50% of expected time minimum)
            min_acceptable = expected_time * 0.5
            
            if duration < min_acceptable:
                logger.warning(
                    f"Evaluation {evaluation_id} completed too quickly: "
                    f"{duration} seconds (expected: {expected_time:.1f} seconds)"
                )
                return False
            
            return True
    
    def analyze_evaluator_patterns(self, user_id: int) -> Dict[str, Any]:
        """
        Analyze patterns in an evaluator's ratings to detect suspicious behavior.
        
        Args:
            user_id: User ID to analyze
            
        Returns:
            Dictionary with analysis results
        """
        with get_db_session() as session:
            # Get all completed evaluations by this user
            evaluations = session.query(Evaluation).filter(
                Evaluation.evaluator_id == user_id,
                Evaluation.completion_time.isnot(None)
            ).all()
            
            if not evaluations:
                return {"status": "No completed evaluations"}
            
            # Get all scores for these evaluations
            evaluation_ids = [e.id for e in evaluations]
            scores = session.query(EvaluationScore).filter(
                EvaluationScore.evaluation_id.in_(evaluation_ids)
            ).all()
            
            if not scores:
                return {"status": "No evaluation scores found"}
            
            # Group scores by criterion
            scores_by_criterion = {}
            for score in scores:
                criterion_id = score.criterion_id
                if criterion_id not in scores_by_criterion:
                    scores_by_criterion[criterion_id] = []
                scores_by_criterion[criterion_id].append(score.score)
            
            # Calculate variance for each criterion
            variance_by_criterion = {}
            for criterion_id, criterion_scores in scores_by_criterion.items():
                if len(criterion_scores) < 2:
                    continue
                
                mean = sum(criterion_scores) / len(criterion_scores)
                variance = sum((s - mean) ** 2 for s in criterion_scores) / len(criterion_scores)
                variance_by_criterion[criterion_id] = variance
            
            # Flag very low variance (suggests pattern scoring)
            low_variance_threshold = 0.2
            low_variance_criteria = [
                c_id for c_id, var in variance_by_criterion.items() 
                if var < low_variance_threshold
            ]
            
            # Check for straight-line scores (all criteria scored the same)
            straight_line_count = 0
            for eval_id in evaluation_ids:
                eval_scores = [s for s in scores if s.evaluation_id == eval_id]
                if len(eval_scores) < 2:
                    continue
                
                # Check if all scores are the same
                first_score = eval_scores[0].score
                if all(s.score == first_score for s in eval_scores):
                    straight_line_count += 1
            
            # Check time patterns
            completion_times = [e.duration_seconds for e in evaluations if e.duration_seconds]
            time_variance = 0
            if completion_times and len(completion_times) > 1:
                mean_time = sum(completion_times) / len(completion_times)
                time_variance = sum((t - mean_time) ** 2 for t in completion_times) / len(completion_times)
            
            return {
                "total_evaluations": len(evaluations),
                "low_variance_criteria": low_variance_criteria,
                "low_variance_criteria_count": len(low_variance_criteria),
                "straight_line_evaluations": straight_line_count,
                "straight_line_percentage": round(straight_line_count / len(evaluations) * 100, 1),
                "time_variance": time_variance,
                "suspicious_patterns": len(low_variance_criteria) > 0 or straight_line_count > len(evaluations) * 0.3,
                "status": "Analysis completed"
            }
    
    def calculate_inter_rater_agreement(self, content_id: int) -> Dict[str, Any]:
        """
        Calculate inter-rater agreement for evaluations of a specific content.
        
        Args:
            content_id: Content ID to analyze
            
        Returns:
            Dictionary with agreement metrics
        """
        with get_db_session() as session:
            # Get all evaluations for this content
            evaluations = session.query(Evaluation).filter(
                Evaluation.content_id == content_id,
                Evaluation.completion_time.isnot(None)
            ).all()
            
            if not evaluations or len(evaluations) < 2:
                return {"status": "Insufficient evaluations", "agreement": None}
            
            # Get all scores for these evaluations
            evaluation_ids = [e.id for e in evaluations]
            scores = session.query(EvaluationScore).filter(
                EvaluationScore.evaluation_id.in_(evaluation_ids)
            ).all()
            
            # Group scores by criterion
            scores_by_criterion = {}
            for score in scores:
                criterion_id = score.criterion_id
                if criterion_id not in scores_by_criterion:
                    scores_by_criterion[criterion_id] = []
                scores_by_criterion[criterion_id].append(score.score)
            
            # Calculate agreement for each criterion
            agreement_by_criterion = {}
            overall_agreements = []
            
            for criterion_id, criterion_scores in scores_by_criterion.items():
                if len(criterion_scores) < 2:
                    continue
                
                # Get criterion details
                criterion = session.query(EvaluationCriterion).get(criterion_id)
                if not criterion:
                    continue
                
                # Calculate standard deviation
                mean = sum(criterion_scores) / len(criterion_scores)
                variance = sum((s - mean) ** 2 for s in criterion_scores) / len(criterion_scores)
                std_dev = variance ** 0.5
                
                # Calculate agreement as 1 - normalized standard deviation
                # (Scale to range 0-1 where 1 is perfect agreement)
                scale_range = criterion.scale_max - criterion.scale_min
                if scale_range == 0:
                    agreement = 1.0
                else:
                    normalized_std_dev = std_dev / scale_range
                    agreement = max(0, 1 - normalized_std_dev)
                
                agreement_by_criterion[criterion.name] = agreement
                overall_agreements.append(agreement)
            
            # Calculate overall agreement
            overall_agreement = sum(overall_agreements) / len(overall_agreements) if overall_agreements else 0
            
            return {
                "overall_agreement": overall_agreement,
                "agreement_by_criterion": agreement_by_criterion,
                "evaluator_count": len(evaluations),
                "meets_threshold": overall_agreement >= AGREEMENT_THRESHOLD,
                "status": "Analysis completed"
            }
    
    def flag_low_quality_evaluations(self) -> List[Dict[str, Any]]:
        """
        Identify evaluations that may have quality issues.
        
        Returns:
            List of potentially problematic evaluations with reasons
        """
        flagged_evaluations = []
        
        with get_db_session() as session:
            # Get all completed evaluations
            evaluations = session.query(Evaluation).filter(
                Evaluation.completion_time.isnot(None)
            ).all()
            
            for evaluation in evaluations:
                flags = []
                
                # Check evaluation duration
                if evaluation.duration_seconds and evaluation.duration_seconds < MIN_EVALUATION_TIME_SECONDS:
                    flags.append(f"Fast completion: {evaluation.duration_seconds} seconds")
                
                # Check quality checks
                if evaluation.passed_quality_checks is False:
                    flags.append("Failed quality checks")
                
                # Check for straight-line scoring
                scores = session.query(EvaluationScore).filter(
                    EvaluationScore.evaluation_id == evaluation.id
                ).all()
                
                if len(scores) >= 2:
                    first_score = scores[0].score
                    if all(s.score == first_score for s in scores):
                        flags.append("Straight-line scoring")
                
                # If any flags, add to the result
                if flags:
                    flagged_evaluations.append({
                        "evaluation_id": evaluation.id,
                        "evaluator_id": evaluation.evaluator_id,
                        "content_id": evaluation.content_id,
                        "flags": flags,
                        "completion_time": evaluation.completion_time.isoformat()
                    })
        
        return flagged_evaluations
    
    def create_quality_check_question(
        self, 
        question_text: str, 
        correct_answer: str, 
        domain: str = None, 
        difficulty: str = "medium"
    ) -> Optional[int]:
        """
        Create a new quality check question.
        
        Args:
            question_text: The question text
            correct_answer: The correct answer
            domain: Optional content domain for the question
            difficulty: Question difficulty (easy, medium, hard)
            
        Returns:
            Question ID if created successfully, None otherwise
        """
        try:
            with get_db_session() as session:
                question = QualityCheckQuestion(
                    question_text=question_text,
                    correct_answer=correct_answer,
                    domain=domain,
                    difficulty=difficulty,
                    active=True
                )
                
                session.add(question)
                session.commit()
                
                logger.info(f"Created quality check question ID {question.id}")
                return question.id
                
        except Exception as e:
            logger.error(f"Error creating quality check question: {e}")
            return None