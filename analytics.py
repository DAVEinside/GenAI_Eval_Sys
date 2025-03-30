"""
Analytics functionality for analyzing evaluation data and generating insights.
"""
import logging
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
import pandas as pd
import numpy as np
from sqlalchemy import func, desc, and_, or_

from database import get_db_session
from models import (
    Content, Evaluation, EvaluationScore, EvaluationCriterion,
    AnalyticsReport, ImprovementSuggestion, User
)
from config import IMPROVEMENT_THRESHOLD, CONTENT_DOMAINS, ANALYTICS_DEFAULT_TIMEFRAME

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AnalyticsEngine:
    """
    Class responsible for analyzing evaluation data and generating insights.
    """
    
    def __init__(self):
        """Initialize the analytics engine."""
        pass
    
    def generate_model_comparison(
        self, 
        model_names: List[str], 
        domains: List[str] = None, 
        criteria: List[str] = None,
        timeframe: str = ANALYTICS_DEFAULT_TIMEFRAME
    ) -> Dict[str, Any]:
        """
        Generate a comparison between different AI models.
        
        Args:
            model_names: List of AI model names to compare
            domains: Optional list of content domains to filter by
            criteria: Optional list of criteria to include
            timeframe: Time period for analysis
            
        Returns:
            Dictionary with comparison results
        """
        # Define timeframe date range
        end_date = datetime.utcnow()
        if timeframe == "last_7_days":
            start_date = end_date - timedelta(days=7)
        elif timeframe == "last_30_days":
            start_date = end_date - timedelta(days=30)
        elif timeframe == "last_90_days":
            start_date = end_date - timedelta(days=90)
        elif timeframe == "last_year":
            start_date = end_date - timedelta(days=365)
        else:  # Default to all time
            start_date = datetime(2000, 1, 1)  # Effectively all time
        
        # Collect data for each model
        results = {
            "models": {},
            "overall_ranking": [],
            "criteria_rankings": {},
            "domain_rankings": {},
            "timeframe": timeframe,
            "generated_at": datetime.utcnow().isoformat(),
            "total_evaluations_analyzed": 0
        }
        
        with get_db_session() as session:
            # Get all criteria if not specified
            all_criteria = {}
            for criterion in session.query(EvaluationCriterion).all():
                all_criteria[criterion.id] = criterion.name
            
            criteria_ids = None
            if criteria:
                # Map criteria names to IDs
                criteria_map = {name: id for id, name in all_criteria.items()}
                criteria_ids = [criteria_map.get(name) for name in criteria if name in criteria_map]
            
            # Create base query to get evaluation scores
            total_evaluations = 0
            
            for model_name in model_names:
                # Get all content IDs for this model
                content_query = session.query(Content.id).filter(
                    Content.model_name == model_name,
                    Content.source_type == 'ai'
                )
                
                if domains:
                    content_query = content_query.filter(Content.domain.in_(domains))
                
                content_ids = [row[0] for row in content_query.all()]
                
                if not content_ids:
                    # Skip if no content found for this model
                    results["models"][model_name] = {
                        "score": 0,
                        "evaluations": 0,
                        "criteria_scores": {},
                        "domain_scores": {}
                    }
                    continue
                
                # Get all evaluations for these contents within timeframe
                eval_query = session.query(Evaluation).filter(
                    Evaluation.content_id.in_(content_ids),
                    Evaluation.completion_time.between(start_date, end_date),
                    Evaluation.passed_quality_checks != False  # Include NULL and True
                )
                
                evaluation_ids = [evaluation.id for evaluation in eval_query.all()]
                total_evaluations += len(evaluation_ids)
                
                if not evaluation_ids:
                    # Skip if no evaluations found
                    results["models"][model_name] = {
                        "score": 0,
                        "evaluations": 0,
                        "criteria_scores": {},
                        "domain_scores": {}
                    }
                    continue
                
                # Get scores for these evaluations
                score_query = session.query(
                    EvaluationScore.criterion_id,
                    func.avg(EvaluationScore.score).label('avg_score')
                ).filter(
                    EvaluationScore.evaluation_id.in_(evaluation_ids)
                )
                
                if criteria_ids:
                    score_query = score_query.filter(EvaluationScore.criterion_id.in_(criteria_ids))
                
                score_query = score_query.group_by(EvaluationScore.criterion_id)
                
                # Collect scores by criterion
                model_criteria_scores = {}
                for criterion_id, avg_score in score_query.all():
                    criterion_name = all_criteria.get(criterion_id, f"criterion_{criterion_id}")
                    model_criteria_scores[criterion_name] = float(avg_score)
                
                # Calculate overall score for model
                overall_score = sum(model_criteria_scores.values()) / len(model_criteria_scores) if model_criteria_scores else 0
                
                # Get scores by domain if domains specified
                model_domain_scores = {}
                if domains:
                    for domain in domains:
                        # Get content IDs for this domain
                        domain_content_ids = session.query(Content.id).filter(
                            Content.model_name == model_name,
                            Content.domain == domain,
                            Content.source_type == 'ai'
                        ).all()
                        
                        domain_content_ids = [row[0] for row in domain_content_ids]
                        
                        if not domain_content_ids:
                            model_domain_scores[domain] = 0
                            continue
                        
                        # Get evaluation IDs for these contents
                        domain_eval_ids = [
                            e.id for e in session.query(Evaluation).filter(
                                Evaluation.content_id.in_(domain_content_ids),
                                Evaluation.completion_time.between(start_date, end_date),
                                Evaluation.passed_quality_checks != False
                            ).all()
                        ]
                        
                        if not domain_eval_ids:
                            model_domain_scores[domain] = 0
                            continue
                        
                        # Get average score across all criteria for this domain
                        domain_avg = session.query(
                            func.avg(EvaluationScore.score)
                        ).filter(
                            EvaluationScore.evaluation_id.in_(domain_eval_ids)
                        ).scalar()
                        
                        model_domain_scores[domain] = float(domain_avg) if domain_avg else 0
                
                # Store results for this model
                results["models"][model_name] = {
                    "score": overall_score,
                    "evaluations": len(evaluation_ids),
                    "criteria_scores": model_criteria_scores,
                    "domain_scores": model_domain_scores
                }
            
            # Calculate overall rankings
            model_scores = [(model, data["score"]) for model, data in results["models"].items()]
            model_scores.sort(key=lambda x: x[1], reverse=True)
            results["overall_ranking"] = [{"model": model, "score": score} for model, score in model_scores]
            
            # Calculate criteria rankings
            all_criteria_used = set()
            for model_data in results["models"].values():
                all_criteria_used.update(model_data["criteria_scores"].keys())
            
            for criterion in all_criteria_used:
                criterion_scores = []
                for model, data in results["models"].items():
                    if criterion in data["criteria_scores"]:
                        criterion_scores.append({"model": model, "score": data["criteria_scores"][criterion]})
                
                criterion_scores.sort(key=lambda x: x["score"], reverse=True)
                results["criteria_rankings"][criterion] = criterion_scores
            
            # Calculate domain rankings
            if domains:
                for domain in domains:
                    domain_scores = []
                    for model, data in results["models"].items():
                        if domain in data["domain_scores"]:
                            domain_scores.append({"model": model, "score": data["domain_scores"][domain]})
                    
                    domain_scores.sort(key=lambda x: x["score"], reverse=True)
                    results["domain_rankings"][domain] = domain_scores
            
            results["total_evaluations_analyzed"] = total_evaluations
            
            # Save the report
            self.save_analytics_report(
                "model_comparison",
                f"Model Comparison ({timeframe})",
                "Comparison of performance across different AI models",
                {
                    "model_names": model_names,
                    "domains": domains,
                    "criteria": criteria,
                    "timeframe": timeframe
                },
                results
            )
            
            return results
    
    def identify_improvement_areas(
        self, 
        model_name: str, 
        threshold: float = IMPROVEMENT_THRESHOLD,
        comparison_model: str = None
    ) -> Dict[str, Any]:
        """
        Identify areas where a model needs improvement.
        
        Args:
            model_name: AI model name to analyze
            threshold: Improvement threshold (default from config)
            comparison_model: Optional model to compare against
            
        Returns:
            Dictionary with improvement suggestions
        """
        results = {
            "model_name": model_name,
            "suggestions": [],
            "domains_to_improve": [],
            "criteria_to_improve": [],
            "generated_at": datetime.utcnow().isoformat()
        }
        
        with get_db_session() as session:
            # Get baseline scores for the model
            model_scores = self._get_model_scores(session, model_name)
            
            if not model_scores["criteria"]:
                return {
                    "model_name": model_name,
                    "error": "No evaluation data found for this model",
                    "generated_at": datetime.utcnow().isoformat()
                }
            
            # Get comparison scores
            comparison_scores = {}
            if comparison_model:
                comparison_scores = self._get_model_scores(session, comparison_model)
                
                if not comparison_scores["criteria"]:
                    comparison_model = None
                    comparison_scores = {}
            
            # If no comparison model, use human content as benchmark
            if not comparison_model:
                human_scores = self._get_human_benchmark_scores(session)
                comparison_scores = human_scores
                comparison_model = "human benchmark"
            
            # Find criteria gaps
            for criterion, model_score in model_scores["criteria"].items():
                if criterion in comparison_scores["criteria"]:
                    comparison_score = comparison_scores["criteria"][criterion]
                    gap = comparison_score - model_score
                    
                    if gap >= threshold:
                        results["criteria_to_improve"].append({
                            "criterion": criterion,
                            "model_score": model_score,
                            "benchmark_score": comparison_score,
                            "gap": gap
                        })
            
            # Find domain gaps
            for domain, model_score in model_scores["domains"].items():
                if domain in comparison_scores["domains"]:
                    comparison_score = comparison_scores["domains"][domain]
                    gap = comparison_score - model_score
                    
                    if gap >= threshold:
                        results["domains_to_improve"].append({
                            "domain": domain,
                            "model_score": model_score,
                            "benchmark_score": comparison_score,
                            "gap": gap
                        })
            
            # Generate improvement suggestions
            suggestions = []
            
            # Domain-specific suggestions
            for domain_gap in results["domains_to_improve"]:
                domain = domain_gap["domain"]
                
                # Find the worst criteria in this domain
                domain_criteria = {}
                for content_id in model_scores["domain_contents"].get(domain, []):
                    for eval_id in model_scores["content_evals"].get(content_id, []):
                        for criterion, score in model_scores["eval_scores"].get(eval_id, {}).items():
                            if criterion not in domain_criteria:
                                domain_criteria[criterion] = []
                            domain_criteria[criterion].append(score)
                
                # Calculate average score per criterion in this domain
                domain_criteria_avg = {}
                for criterion, scores in domain_criteria.items():
                    if scores:
                        domain_criteria_avg[criterion] = sum(scores) / len(scores)
                
                # Find lowest scoring criteria in this domain
                sorted_criteria = sorted(domain_criteria_avg.items(), key=lambda x: x[1])
                
                if sorted_criteria:
                    worst_criterion, worst_score = sorted_criteria[0]
                    
                    # Create improvement suggestion
                    suggestion = self._create_improvement_suggestion(
                        model_name, 
                        domain, 
                        worst_criterion, 
                        worst_score,
                        domain_gap["benchmark_score"]
                    )
                    
                    suggestions.append(suggestion)
            
            # General criteria suggestions
            for criterion_gap in results["criteria_to_improve"]:
                criterion = criterion_gap["criterion"]
                
                # Check if we already have a suggestion for this criterion
                existing = any(s["criterion"] == criterion for s in suggestions)
                if existing:
                    continue
                
                # Create general suggestion
                suggestion = self._create_improvement_suggestion(
                    model_name, 
                    None,  # No specific domain
                    criterion, 
                    criterion_gap["model_score"],
                    criterion_gap["benchmark_score"]
                )
                
                suggestions.append(suggestion)
            
            results["suggestions"] = suggestions
            
            # Save suggestions to database
            for suggestion in suggestions:
                improvement = ImprovementSuggestion(
                    model_name=model_name,
                    domain=suggestion["domain"] if "domain" in suggestion else None,
                    criterion=suggestion["criterion"],
                    current_score=suggestion["current_score"],
                    target_score=suggestion["target_score"],
                    suggestion=suggestion["suggestion"],
                    priority=suggestion["priority"],
                    status="open"
                )
                
                session.add(improvement)
            
            # Save report
            self.save_analytics_report(
                "improvement_areas",
                f"Improvement Areas for {model_name}",
                f"Analysis of areas where {model_name} needs improvement compared to {comparison_model}",
                {
                    "model_name": model_name,
                    "threshold": threshold,
                    "comparison_model": comparison_model
                },
                results
            )
            
            return results
    
    def _get_model_scores(self, session, model_name: str) -> Dict[str, Any]:
        """
        Get all evaluation scores for a specific model.
        
        Args:
            session: Database session
            model_name: AI model name
            
        Returns:
            Dictionary with score data
        """
        result = {
            "criteria": {},     # Avg score by criterion
            "domains": {},      # Avg score by domain
            "domain_contents": {},  # Content IDs by domain
            "content_evals": {},    # Evaluation IDs by content
            "eval_scores": {}       # Scores by evaluation
        }
        
        # Get all content for this model
        contents = session.query(Content).filter(
            Content.model_name == model_name,
            Content.source_type == 'ai'
        ).all()
        
        if not contents:
            return result
        
        # Group content by domain
        for content in contents:
            if content.domain not in result["domain_contents"]:
                result["domain_contents"][content.domain] = []
            result["domain_contents"][content.domain].append(content.id)
        
        # Get all evaluations for these contents
        content_ids = [content.id for content in contents]
        evaluations = session.query(Evaluation).filter(
            Evaluation.content_id.in_(content_ids),
            Evaluation.passed_quality_checks != False,
            Evaluation.completion_time.isnot(None)
        ).all()
        
        if not evaluations:
            return result
        
        # Group evaluations by content
        for evaluation in evaluations:
            if evaluation.content_id not in result["content_evals"]:
                result["content_evals"][evaluation.content_id] = []
            result["content_evals"][evaluation.content_id].append(evaluation.id)
        
        # Get all scores
        evaluation_ids = [evaluation.id for evaluation in evaluations]
        scores = session.query(
            EvaluationScore,
            EvaluationCriterion.name.label('criterion_name')
        ).join(
            EvaluationCriterion,
            EvaluationScore.criterion_id == EvaluationCriterion.id
        ).filter(
            EvaluationScore.evaluation_id.in_(evaluation_ids)
        ).all()
        
        # Process all scores
        criteria_scores = {}
        domain_scores = {domain: [] for domain in result["domain_contents"]}
        
        for score, criterion_name in scores:
            # Add to eval_scores
            if score.evaluation_id not in result["eval_scores"]:
                result["eval_scores"][score.evaluation_id] = {}
            result["eval_scores"][score.evaluation_id][criterion_name] = score.score
            
            # Add to criteria scores
            if criterion_name not in criteria_scores:
                criteria_scores[criterion_name] = []
            criteria_scores[criterion_name].append(score.score)
            
            # Find which domain this score belongs to
            for domain, content_ids in result["domain_contents"].items():
                for content_id in content_ids:
                    if content_id in result["content_evals"] and score.evaluation_id in result["content_evals"][content_id]:
                        domain_scores[domain].append(score.score)
                        break
        
        # Calculate averages
        for criterion, scores in criteria_scores.items():
            if scores:
                result["criteria"][criterion] = sum(scores) / len(scores)
        
        for domain, scores in domain_scores.items():
            if scores:
                result["domains"][domain] = sum(scores) / len(scores)
        
        return result
    
    def _get_human_benchmark_scores(self, session) -> Dict[str, Any]:
        """
        Get benchmark scores from human-created content.
        
        Args:
            session: Database session
            
        Returns:
            Dictionary with benchmark score data
        """
        result = {
            "criteria": {},     # Avg score by criterion
            "domains": {},      # Avg score by domain
        }
        
        # Get all human content
        contents = session.query(Content).filter(
            Content.source_type == 'human'
        ).all()
        
        if not contents:
            return result
        
        # Get all evaluations for human content
        content_ids = [content.id for content in contents]
        evaluations = session.query(Evaluation).filter(
            Evaluation.content_id.in_(content_ids),
            Evaluation.passed_quality_checks != False,
            Evaluation.completion_time.isnot(None)
        ).all()
        
        if not evaluations:
            return result
        
        # Get content domains for each evaluation
        eval_domains = {}
        for content in contents:
            for evaluation in evaluations:
                if evaluation.content_id == content.id:
                    eval_domains[evaluation.id] = content.domain
        
        # Get all scores
        evaluation_ids = [evaluation.id for evaluation in evaluations]
        scores = session.query(
            EvaluationScore,
            EvaluationCriterion.name.label('criterion_name')
        ).join(
            EvaluationCriterion,
            EvaluationScore.criterion_id == EvaluationCriterion.id
        ).filter(
            EvaluationScore.evaluation_id.in_(evaluation_ids)
        ).all()
        
        # Process scores
        criteria_scores = {}
        domain_scores = {}
        
        for score, criterion_name in scores:
            # Add to criteria scores
            if criterion_name not in criteria_scores:
                criteria_scores[criterion_name] = []
            criteria_scores[criterion_name].append(score.score)
            
            # Add to domain scores
            if score.evaluation_id in eval_domains:
                domain = eval_domains[score.evaluation_id]
                if domain not in domain_scores:
                    domain_scores[domain] = []
                domain_scores[domain].append(score.score)
        
        # Calculate averages
        for criterion, scores in criteria_scores.items():
            if scores:
                result["criteria"][criterion] = sum(scores) / len(scores)
        
        for domain, scores in domain_scores.items():
            if scores:
                result["domains"][domain] = sum(scores) / len(scores)
        
        return result
    
    def _create_improvement_suggestion(
        self, 
        model_name: str, 
        domain: Optional[str], 
        criterion: str, 
        current_score: float, 
        target_score: float
    ) -> Dict[str, Any]:
        """
        Create an improvement suggestion based on scores.
        
        Args:
            model_name: AI model name
            domain: Optional content domain
            criterion: Criterion name
            current_score: Current model score
            target_score: Target score to achieve
            
        Returns:
            Dictionary with suggestion details
        """
        # Format scores
        current_formatted = f"{current_score:.2f}"
        target_formatted = f"{target_formatted:.2f}" if isinstance(target_score, float) else "N/A"
        score_gap = target_score - current_score if isinstance(target_score, float) else 0
        
        # Set priority based on gap
        if score_gap >= 1.0:
            priority = "high"
        elif score_gap >= 0.5:
            priority = "medium"
        else:
            priority = "low"
        
        suggestion = {
            "model_name": model_name,
            "criterion": criterion,
            "current_score": current_score,
            "target_score": target_score,
            "priority": priority
        }
        
        if domain:
            suggestion["domain"] = domain
        
        # Generate suggestion text
        suggestion_text = f"Improve {criterion} "
        if domain:
            suggestion_text += f"in {domain} content "
        suggestion_text += f"from {current_formatted} to {target_formatted}."
        
        # Add specific suggestions based on criterion
        if criterion.lower() == "accuracy":
            suggestion_text += " Enhance factual correctness by improving source validation and fact-checking processes."
        elif criterion.lower() == "coherence":
            suggestion_text += " Improve logical flow and narrative consistency by strengthening contextual awareness across longer texts."
        elif criterion.lower() == "relevance":
            suggestion_text += " Improve focus on provided topics by enhancing prompt understanding and topic adherence mechanisms."
        elif criterion.lower() == "creativity":
            suggestion_text += " Increase originality by expanding the model's diverse expression patterns and reducing repetitive structures."
        elif criterion.lower() == "completeness":
            suggestion_text += " Ensure comprehensive coverage of subjects by improving the model's thoroughness in addressing all aspects of a topic."
        elif criterion.lower() == "language_quality":
            suggestion_text += " Enhance grammar, vocabulary and writing style by refining linguistic patterns and reducing awkward phrasing."
        
        suggestion["suggestion"] = suggestion_text
        return suggestion
    
    def analyze_human_ai_gap(self, domains: List[str] = None) -> Dict[str, Any]:
        """
        Analyze the gap between human and AI-generated content.
        
        Args:
            domains: Optional list of domains to filter by
            
        Returns:
            Dictionary with gap analysis
        """
        results = {
            "overall_gap": 0,
            "domains": {},
            "criteria": {},
            "generated_at": datetime.utcnow().isoformat()
        }
        
        with get_db_session() as session:
            # Get human benchmark scores
            human_scores = self._get_human_benchmark_scores(session)
            
            if not human_scores["criteria"]:
                return {
                    "error": "No human benchmark data available",
                    "generated_at": datetime.utcnow().isoformat()
                }
            
            # Get all AI models
            ai_models = session.query(Content.model_name).filter(
                Content.source_type == 'ai'
            ).distinct().all()
            
            ai_models = [model[0] for model in ai_models if model[0]]
            
            if not ai_models:
                return {
                    "error": "No AI model data available",
                    "generated_at": datetime.utcnow().isoformat()
                }
            
            # Get scores for each model
            all_model_scores = {}
            for model in ai_models:
                all_model_scores[model] = self._get_model_scores(session, model)
            
            # Filter domains if needed
            if domains:
                valid_domains = []
                for domain in domains:
                    # Check if we have data for this domain
                    human_has_domain = domain in human_scores["domains"]
                    ai_has_domain = any(domain in model_data["domains"] for model_data in all_model_scores.values())
                    
                    if human_has_domain and ai_has_domain:
                        valid_domains.append(domain)
                
                domains = valid_domains
            else:
                # Use all available domains
                domains = set(human_scores["domains"].keys())
                for model_data in all_model_scores.values():
                    domains.update(model_data["domains"].keys())
                domains = list(domains)
            
            # Calculate best AI score for each criterion and domain
            best_ai_criteria = {}
            best_ai_domains = {}
            
            # For each criterion
            for criterion in human_scores["criteria"]:
                best_score = 0
                best_model = None
                
                for model, model_data in all_model_scores.items():
                    if criterion in model_data["criteria"]:
                        score = model_data["criteria"][criterion]
                        if score > best_score:
                            best_score = score
                            best_model = model
                
                if best_model:
                    best_ai_criteria[criterion] = {
                        "score": best_score,
                        "model": best_model
                    }
            
            # For each domain
            for domain in domains:
                best_score = 0
                best_model = None
                
                for model, model_data in all_model_scores.items():
                    if domain in model_data["domains"]:
                        score = model_data["domains"][domain]
                        if score > best_score:
                            best_score = score
                            best_model = model
                
                if best_model:
                    best_ai_domains[domain] = {
                        "score": best_score,
                        "model": best_model
                    }
            
            # Calculate gaps
            criteria_gaps = {}
            for criterion, human_score in human_scores["criteria"].items():
                if criterion in best_ai_criteria:
                    ai_score = best_ai_criteria[criterion]["score"]
                    gap = human_score - ai_score
                    
                    criteria_gaps[criterion] = {
                        "human_score": human_score,
                        "ai_score": ai_score,
                        "gap": gap,
                        "best_model": best_ai_criteria[criterion]["model"]
                    }
            
            domain_gaps = {}
            for domain, human_score in human_scores["domains"].items():
                if domain in best_ai_domains:
                    ai_score = best_ai_domains[domain]["score"]
                    gap = human_score - ai_score
                    
                    domain_gaps[domain] = {
                        "human_score": human_score,
                        "ai_score": ai_score,
                        "gap": gap,
                        "best_model": best_ai_domains[domain]["model"]
                    }
            
            # Calculate overall gap
            all_gaps = []
            for gap_data in criteria_gaps.values():
                all_gaps.append(gap_data["gap"])
            for gap_data in domain_gaps.values():
                all_gaps.append(gap_data["gap"])
            
            overall_gap = sum(all_gaps) / len(all_gaps) if all_gaps else 0
            
            results["overall_gap"] = overall_gap
            results["criteria"] = criteria_gaps
            results["domains"] = domain_gaps
            
            # Save report
            self.save_analytics_report(
                "human_ai_gap",
                "Human vs AI Content Gap Analysis",
                "Analysis of the performance gap between human and AI-generated content",
                {
                    "domains": domains
                },
                results
            )
            
            return results
    
    def save_analytics_report(self, report_type: str, title: str, description: str, 
                            parameters: Dict[str, Any], results: Dict[str, Any], 
                            user_id: int = None) -> int:
        """
        Save an analytics report to the database.
        
        Args:
            report_type: Type of report
            title: Report title
            description: Report description
            parameters: Parameters used to generate the report
            results: Report results
            user_id: Optional user ID of the creator
            
        Returns:
            Report ID
        """
        try:
            with get_db_session() as session:
                report = AnalyticsReport(
                    report_type=report_type,
                    title=title,
                    description=description,
                    parameters=parameters,
                    results=results,
                    created_at=datetime.utcnow(),
                    created_by=user_id
                )
                
                session.add(report)
                session.commit()
                
                logger.info(f"Saved analytics report ID {report.id} of type {report_type}")
                return report.id
                
        except Exception as e:
            logger.error(f"Error saving analytics report: {e}")
            return None
    
    def get_analytics_report(self, report_id: int) -> Optional[Dict[str, Any]]:
        """
        Get a saved analytics report.
        
        Args:
            report_id: Report ID to retrieve
            
        Returns:
            Report data or None if not found
        """
        with get_db_session() as session:
            report = session.query(AnalyticsReport).get(report_id)
            
            if not report:
                return None
            
            return {
                "id": report.id,
                "report_type": report.report_type,
                "title": report.title,
                "description": report.description,
                "parameters": report.parameters,
                "results": report.results,
                "created_at": report.created_at.isoformat()
            }
    
    def get_recent_reports(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get list of recent analytics reports.
        
        Args:
            limit: Maximum number of reports to return
            
        Returns:
            List of report summaries
        """
        with get_db_session() as session:
            reports = session.query(AnalyticsReport).order_by(
                AnalyticsReport.created_at.desc()
            ).limit(limit).all()
            
            result = []
            for report in reports:
                result.append({
                    "id": report.id,
                    "report_type": report.report_type,
                    "title": report.title,
                    "description": report.description,
                    "created_at": report.created_at.isoformat()
                })
            
            return result
    
    def get_improvement_suggestions(
        self, 
        model_name: str = None, 
        domain: str = None,
        status: str = None
    ) -> List[Dict[str, Any]]:
        """
        Get improvement suggestions with optional filters.
        
        Args:
            model_name: Optional AI model name to filter by
            domain: Optional content domain to filter by
            status: Optional suggestion status to filter by
            
        Returns:
            List of improvement suggestions
        """
        with get_db_session() as session:
            query = session.query(ImprovementSuggestion)
            
            if model_name:
                query = query.filter(ImprovementSuggestion.model_name == model_name)
            
            if domain:
                query = query.filter(ImprovementSuggestion.domain == domain)
            
            if status:
                query = query.filter(ImprovementSuggestion.status == status)
            
            # Order by priority and creation date
            query = query.order_by(
                case(
                    (ImprovementSuggestion.priority == 'high', 1),
                    (ImprovementSuggestion.priority == 'medium', 2),
                    else_=3
                ),
                ImprovementSuggestion.created_at.desc()
            )
            
            suggestions = query.all()
            
            result = []
            for suggestion in suggestions:
                result.append({
                    "id": suggestion.id,
                    "model_name": suggestion.model_name,
                    "domain": suggestion.domain,
                    "criterion": suggestion.criterion,
                    "current_score": suggestion.current_score,
                    "target_score": suggestion.target_score,
                    "suggestion": suggestion.suggestion,
                    "priority": suggestion.priority,
                    "status": suggestion.status,
                    "created_at": suggestion.created_at.isoformat()
                })
            
            return result