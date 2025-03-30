"""
Configuration settings for the Generative AI Content Evaluation System.
"""
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Database Configuration
DB_TYPE = os.getenv("DB_TYPE", "sqlite")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "genai_evaluation")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "password")

# If SQLite is used
SQLITE_DB_PATH = os.getenv("SQLITE_DB_PATH", "sqlite:///genai_evaluation.db")

# Construct the database URI based on the database type
if DB_TYPE == "sqlite":
    DATABASE_URI = SQLITE_DB_PATH
elif DB_TYPE == "postgresql":
    DATABASE_URI = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
else:
    raise ValueError(f"Unsupported database type: {DB_TYPE}")

# Application Configuration
DEBUG = os.getenv("DEBUG", "True").lower() in ["true", "1", "t"]
SECRET_KEY = os.getenv("SECRET_KEY", "dev-key-replace-in-production")
APP_HOST = os.getenv("APP_HOST", "0.0.0.0")
APP_PORT = int(os.getenv("APP_PORT", "5000"))

# Content Domains
CONTENT_DOMAINS = [
    "creative_writing",
    "technical_documentation",
    "marketing_copy",
    "news_articles",
    "academic_papers",
    "social_media_posts"
]

# Evaluation Criteria
EVALUATION_CRITERIA = {
    "accuracy": {
        "description": "Factual correctness and absence of errors",
        "scale": [1, 5]
    },
    "coherence": {
        "description": "Logical flow and consistency of ideas",
        "scale": [1, 5]
    },
    "relevance": {
        "description": "Appropriateness to the given topic or context",
        "scale": [1, 5]
    },
    "creativity": {
        "description": "Originality and innovative thinking",
        "scale": [1, 5]
    },
    "completeness": {
        "description": "Comprehensive coverage of the subject matter",
        "scale": [1, 5]
    },
    "language_quality": {
        "description": "Grammar, vocabulary, and overall writing quality",
        "scale": [1, 5]
    }
}

# Quality Control Configuration
MIN_EVALUATION_TIME_SECONDS = 60  # Minimum time an evaluator should spend
QUALITY_CHECK_FREQUENCY = 0.1  # Frequency of inserting quality check questions
AGREEMENT_THRESHOLD = 0.7  # Minimum agreement level between evaluators

# Analytics Configuration
ANALYTICS_DEFAULT_TIMEFRAME = "last_30_days"
IMPROVEMENT_THRESHOLD = 0.3  # 30% improvement as mentioned in the outline

# API Configuration
API_VERSION = "v1"
API_PREFIX = f"/api/{API_VERSION}"
TOKEN_EXPIRATION = 86400  # 24 hours in seconds

# Logging Configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = os.getenv("LOG_FILE", "genai_evaluation.log")

# Expert Credentials
EXPERT_AUTH_REQUIRED = True