"""
Utility functions for the Generative AI Content Evaluation System.
"""
import logging
import json
import csv
import os
import io
import random
import string
from datetime import datetime
from typing import Dict, List, Optional, Any, Union, Tuple
from werkzeug.security import generate_password_hash, check_password_hash

from database import get_db_session
from models import (
    User, ExpertProfile, Content, EvaluationCriterion, 
    Evaluation, EvaluationScore, QualityCheckQuestion
)
from config import CONTENT_DOMAINS, EVALUATION_CRITERIA

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def import_content_from_json(file_path: str) -> Tuple[int, int]:
    """
    Import content from a JSON file.
    
    Args:
        file_path: Path to the JSON file
        
    Returns:
        Tuple of (number of items imported, total items in file)
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if not isinstance(data, list):
            logger.error(f"Invalid JSON format in {file_path}. Expected a list of content items.")
            return 0, 0
        
        total_items = len(data)
        imported_items = 0
        
        with get_db_session() as session:
            for item in data:
                # Validate required fields
                required_fields = ['title', 'text', 'domain', 'source_type']
                if not all(field in item for field in required_fields):
                    logger.warning(f"Skipping item with missing required fields: {item}")
                    continue
                
                # Validate domain
                if item['domain'] not in CONTENT_DOMAINS:
                    logger.warning(f"Skipping item with invalid domain: {item['domain']}")
                    continue
                
                # Validate source type
                if item['source_type'] not in ['ai', 'human']:
                    logger.warning(f"Skipping item with invalid source_type: {item['source_type']}")
                    continue
                
                # Extract fields
                title = item['title']
                text = item['text']
                domain = item['domain']
                source_type = item['source_type']
                model_name = item.get('model_name')
                metadata = {k: v for k, v in item.items() if k not in required_fields + ['model_name']}
                
                # Create content record
                content = Content(
                    title=title,
                    text=text,
                    domain=domain,
                    source_type=source_type,
                    model_name=model_name,
                    metadata=metadata,
                    created_at=datetime.utcnow()
                )
                
                session.add(content)
                imported_items += 1
            
            session.commit()
        
        logger.info(f"Imported {imported_items} out of {total_items} content items from {file_path}")
        return imported_items, total_items
        
    except Exception as e:
        logger.error(f"Error importing content from {file_path}: {e}")
        return 0, 0


def export_evaluations_to_csv(file_path: str, filters: Dict[str, Any] = None) -> Tuple[bool, int]:
    """
    Export evaluations to a CSV file.
    
    Args:
        file_path: Path to save the CSV file
        filters: Optional filters to apply (domain, model_name, date_range, etc.)
        
    Returns:
        Tuple of (success, number of records exported)
    """
    try:
        with get_db_session() as session:
            # Build query with joins to get all related data
            query = session.query(
                Evaluation,
                User.username.label('evaluator_username'),
                Content.title.label('content_title'),
                Content.domain.label('content_domain'),
                Content.source_type.label('content_source_type'),
                Content.model_name.label('model_name')
            ).join(
                User, Evaluation.evaluator_id == User.id
            ).join(
                Content, Evaluation.content_id == Content.id
            )
            
            # Apply filters if provided
            if filters:
                if 'domain' in filters:
                    query = query.filter(Content.domain == filters['domain'])
                
                if 'model_name' in filters:
                    query = query.filter(Content.model_name == filters['model_name'])
                
                if 'source_type' in filters:
                    query = query.filter(Content.source_type == filters['source_type'])
                
                if 'start_date' in filters and 'end_date' in filters:
                    query = query.filter(
                        Evaluation.completion_time.between(filters['start_date'], filters['end_date'])
                    )
                
                if 'evaluator_id' in filters:
                    query = query.filter(Evaluation.evaluator_id == filters['evaluator_id'])
                
                if 'quality_check' in filters:
                    query = query.filter(Evaluation.passed_quality_checks == filters['quality_check'])
            
            # Get only completed evaluations
            query = query.filter(Evaluation.completion_time.isnot(None))
            
            # Execute query
            results = query.all()
            
            if not results:
                logger.warning("No evaluations found matching the criteria")
                return False, 0
            
            # Get all evaluation IDs
            eval_ids = [result[0].id for result in results]
            
            # Get scores for these evaluations
            scores_query = session.query(
                EvaluationScore.evaluation_id,
                EvaluationCriterion.name.label('criterion_name'),
                EvaluationScore.score
            ).join(
                EvaluationCriterion, EvaluationScore.criterion_id == EvaluationCriterion.id
            ).filter(
                EvaluationScore.evaluation_id.in_(eval_ids)
            )
            
            # Group scores by evaluation ID
            scores_by_eval = {}
            for eval_id, criterion, score in scores_query:
                if eval_id not in scores_by_eval:
                    scores_by_eval[eval_id] = {}
                scores_by_eval[eval_id][criterion] = score
            
            # Write to CSV
            with open(file_path, 'w', newline='', encoding='utf-8') as f:
                # Get all unique criteria for headers
                all_criteria = set()
                for scores in scores_by_eval.values():
                    all_criteria.update(scores.keys())
                
                # Create CSV headers
                headers = [
                    'evaluation_id', 'evaluator_username', 'content_title',
                    'content_domain', 'source_type', 'model_name',
                    'overall_rating', 'start_time', 'completion_time',
                    'duration_seconds', 'passed_quality_checks', 'comments'
                ]
                
                # Add criteria headers
                headers.extend(sorted(all_criteria))
                
                writer = csv.DictWriter(f, fieldnames=headers)
                writer.writeheader()
                
                # Write rows
                for result in results:
                    evaluation = result[0]
                    
                    row = {
                        'evaluation_id': evaluation.id,
                        'evaluator_username': result[1],
                        'content_title': result[2],
                        'content_domain': result[3],
                        'source_type': result[4],
                        'model_name': result[5],
                        'overall_rating': evaluation.overall_rating,
                        'start_time': evaluation.start_time.isoformat() if evaluation.start_time else '',
                        'completion_time': evaluation.completion_time.isoformat() if evaluation.completion_time else '',
                        'duration_seconds': evaluation.duration_seconds,
                        'passed_quality_checks': evaluation.passed_quality_checks,
                        'comments': evaluation.comments
                    }
                    
                    # Add scores
                    if evaluation.id in scores_by_eval:
                        for criterion, score in scores_by_eval[evaluation.id].items():
                            row[criterion] = score
                    
                    writer.writerow(row)
            
            logger.info(f"Exported {len(results)} evaluations to {file_path}")
            return True, len(results)
            
    except Exception as e:
        logger.error(f"Error exporting evaluations to CSV: {e}")
        return False, 0


def create_user(
    username: str,
    email: str,
    password: str,
    first_name: str = None,
    last_name: str = None,
    role: str = 'evaluator'
) -> Optional[int]:
    """
    Create a new user.
    
    Args:
        username: Username
        email: Email address
        password: Password
        first_name: First name
        last_name: Last name
        role: User role ('evaluator', 'admin', 'manager')
        
    Returns:
        User ID if created successfully, None otherwise
    """
    try:
        # Validate role
        valid_roles = ['evaluator', 'admin', 'manager']
        if role not in valid_roles:
            logger.error(f"Invalid role: {role}")
            return None
        
        with get_db_session() as session:
            # Check if username or email already exists
            existing = session.query(User).filter(
                (User.username == username) | (User.email == email)
            ).first()
            
            if existing:
                logger.error(f"User with username '{username}' or email '{email}' already exists")
                return None
            
            # Create user
            user = User(
                username=username,
                email=email,
                password_hash=generate_password_hash(password),
                first_name=first_name,
                last_name=last_name,
                role=role,
                is_active=True,
                created_at=datetime.utcnow()
            )
            
            session.add(user)
            session.commit()
            
            logger.info(f"Created new user ID {user.id} with username '{username}'")
            return user.id
            
    except Exception as e:
        logger.error(f"Error creating user: {e}")
        return None


def create_expert_profile(
    user_id: int,
    domains: List[str],
    years_experience: int,
    qualifications: str = None,
    bio: str = None,
    verified: bool = False
) -> Optional[int]:
    """
    Create or update an expert profile.
    
    Args:
        user_id: User ID
        domains: List of expertise domains
        years_experience: Years of experience
        qualifications: Professional qualifications
        bio: Expert bio
        verified: Whether the expert is verified
        
    Returns:
        Profile ID if created successfully, None otherwise
    """
    try:
        # Validate domains
        for domain in domains:
            if domain not in CONTENT_DOMAINS:
                logger.error(f"Invalid domain: {domain}")
                return None
        
        with get_db_session() as session:
            # Check if user exists
            user = session.query(User).get(user_id)
            if not user:
                logger.error(f"User ID {user_id} not found")
                return None
            
            # Check if profile already exists
            profile = session.query(ExpertProfile).filter(
                ExpertProfile.user_id == user_id
            ).first()
            
            if profile:
                # Update existing profile
                profile.domains = domains
                profile.years_experience = years_experience
                profile.qualifications = qualifications
                profile.bio = bio
                profile.verified = verified
                
                logger.info(f"Updated expert profile ID {profile.id} for user ID {user_id}")
            else:
                # Create new profile
                profile = ExpertProfile(
                    user_id=user_id,
                    domains=domains,
                    years_experience=years_experience,
                    qualifications=qualifications,
                    bio=bio,
                    verified=verified
                )
                
                session.add(profile)
                logger.info(f"Created new expert profile for user ID {user_id}")
            
            session.commit()
            return profile.id
            
    except Exception as e:
        logger.error(f"Error creating/updating expert profile: {e}")
        return None


def generate_password(length: int = 12) -> str:
    """
    Generate a random secure password.
    
    Args:
        length: Password length
        
    Returns:
        Random password
    """
    # Define character sets
    lowercase = string.ascii_lowercase
    uppercase = string.ascii_uppercase
    digits = string.digits
    special = '!@#$%^&*()-_=+[]{}|;:,.<>?'
    
    # Ensure at least one character from each set
    password = [
        random.choice(lowercase),
        random.choice(uppercase),
        random.choice(digits),
        random.choice(special)
    ]
    
    # Fill the rest randomly
    all_chars = lowercase + uppercase + digits + special
    password.extend(random.choice(all_chars) for _ in range(length - 4))
    
    # Shuffle the password
    random.shuffle(password)
    
    return ''.join(password)


def validate_evaluation_data(data: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Validate evaluation submission data.
    
    Args:
        data: Evaluation data dictionary
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    required_fields = ['evaluation_id', 'scores', 'overall_rating']
    
    # Check required fields
    for field in required_fields:
        if field not in data:
            return False, f"Missing required field: {field}"
    
    # Validate evaluation ID
    try:
        evaluation_id = int(data['evaluation_id'])
    except (ValueError, TypeError):
        return False, "Invalid evaluation ID"
    
    # Validate scores
    scores = data.get('scores', {})
    if not isinstance(scores, dict):
        return False, "Scores must be a dictionary mapping criterion IDs to scores"
    
    for criterion_id, score in scores.items():
        try:
            criterion_id = int(criterion_id)
        except (ValueError, TypeError):
            return False, f"Invalid criterion ID: {criterion_id}"
        
        try:
            score = float(score)
            if score < 1 or score > 5:
                return False, f"Score out of range (1-5): {score}"
        except (ValueError, TypeError):
            return False, f"Invalid score value: {score}"
    
    # Validate overall rating
    try:
        overall_rating = float(data['overall_rating'])
        if overall_rating < 1 or overall_rating > 5:
            return False, f"Overall rating out of range (1-5): {overall_rating}"
    except (ValueError, TypeError):
        return False, f"Invalid overall rating: {data['overall_rating']}"
    
    # Validate quality check answers if provided
    if 'quality_check_answers' in data:
        quality_checks = data['quality_check_answers']
        if not isinstance(quality_checks, dict):
            return False, "Quality check answers must be a dictionary"
        
        for question_id, answer in quality_checks.items():
            try:
                question_id = int(question_id)
            except (ValueError, TypeError):
                return False, f"Invalid question ID: {question_id}"
            
            if not isinstance(answer, str):
                return False, f"Answer must be a string: {answer}"
    
    return True, ""


def truncate_text(text: str, max_length: int = 100, ellipsis: str = '...') -> str:
    """
    Truncate text to a maximum length.
    
    Args:
        text: Text to truncate
        max_length: Maximum length
        ellipsis: String to append if truncated
        
    Returns:
        Truncated text
    """
    if not text:
        return ''
    
    if len(text) <= max_length:
        return text
    
    return text[:max_length - len(ellipsis)] + ellipsis


def format_timestamp(timestamp, format_str='%Y-%m-%d %H:%M:%S'):
    """
    Format a timestamp as a string.
    
    Args:
        timestamp: Timestamp to format
        format_str: Format string
        
    Returns:
        Formatted timestamp string
    """
    if not timestamp:
        return ''
    
    if isinstance(timestamp, str):
        try:
            timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        except ValueError:
            return timestamp
    
    try:
        return timestamp.strftime(format_str)
    except Exception:
        return str(timestamp)


def get_domain_label(domain_code):
    """
    Get a human-readable label for a domain code.
    
    Args:
        domain_code: Domain code (e.g., 'creative_writing')
        
    Returns:
        Human-readable label (e.g., 'Creative Writing')
    """
    if not domain_code:
        return ''
    
    # Convert snake_case to Title Case
    words = domain_code.split('_')
    return ' '.join(word.capitalize() for word in words)