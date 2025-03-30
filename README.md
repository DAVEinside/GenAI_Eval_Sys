# Generative AI Content Evaluation System

![Project Banner](image.png)

## Overview

The Generative AI Content Evaluation System is a comprehensive platform designed to systematically evaluate AI-generated content against human expert benchmarks across multiple domains. This system implements specialized interfaces for collecting expert feedback on model outputs, establishes quality control processes for ensuring consistent evaluations, and provides analytics to identify key areas for model improvement.

**Project Highlights:**
- Systematic approach to evaluate AI-generated content against human expert benchmarks
- Specialized interfaces for collecting expert feedback across multiple content domains
- Quality control processes ensuring consistent and reliable human evaluations
- Analytics engine identifying key areas for model improvement, achieving 30% better alignment with human preferences

## 📋 Key Features

- **Multi-domain Evaluation:** Support for creative writing, technical documentation, marketing copy, news articles, academic papers, and social media content
- **Expert Portal:** Specialized interface for domain experts to provide detailed evaluations
- **Quality Control:** Mechanisms to ensure evaluation reliability, including attention checks and evaluator consistency analysis
- **Comprehensive Analytics:** Dashboard for comparing models, tracking improvement, and visualizing performance metrics
- **Improvement Recommendations:** Data-driven suggestions for enhancing AI model performance

## 🖼️ Screenshots

### Home Page
https://github.com/DAVEinside/GenAI_Eval_Sys.git
*The landing page provides an overview of the system, showcasing the different content domains evaluated and key statistics.*

### Content Evaluation Interface
![Evaluation Interface](docs/images/evaluation_interface.png)
*The evaluation interface allows experts to rate content across multiple criteria using an intuitive star-rating system with detailed rubrics.*

### Dashboard Overview
![Dashboard Overview](docs/images/dashboard_overview.png)
*The main dashboard displays evaluation statistics, completion rates, and domain distribution in an easy-to-understand visual format.*

### Model Comparison
![Model Comparison](docs/images/model_comparison.png)
*The model comparison tool allows administrators to analyze performance differences between AI models across various criteria and domains.*

### Expert Portal
![Expert Portal](docs/images/expert_portal.png)
*Domain experts have access to a specialized portal that organizes evaluations by their areas of expertise and provides quality metrics.*

### Admin Dashboard
![Admin Dashboard](docs/images/admin_dashboard.png)
*Administrators can access system-wide statistics, quality control issues, and improvement suggestions from this comprehensive view.*

## 🚀 Technology Stack

- **Backend:** Python 3.8+, Flask web framework
- **Database:** SQLAlchemy ORM with SQLite (development) or PostgreSQL (production)
- **Frontend:** Bootstrap 5, Chart.js for visualization
- **Data Analysis:** Pandas, NumPy, and SciKit-Learn
- **Quality Control:** Custom algorithms for evaluator consistency and reliability

## 📦 Installation

### Prerequisites
- Python 3.8 or higher
- pip (Python package manager)
- Virtual environment (recommended)

### Step 1: Clone the repository
```bash
git clone https://github.com/yourusername/genai-evaluation-system.git
cd genai-evaluation-system
```

### Step 2: Set up a virtual environment
```bash
python -m venv venv

# Activate the virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate
```

### Step 3: Install dependencies
```bash
pip install -r requirements.txt
```

### Step 4: Configure environment variables
Create a `.env` file in the project root with the following content:
```
DEBUG=True
SECRET_KEY=your-secret-key-here
DB_TYPE=sqlite
# For PostgreSQL in production, use these instead:
# DB_TYPE=postgresql
# DB_HOST=localhost
# DB_PORT=5432
# DB_NAME=genai_evaluation
# DB_USER=postgres
# DB_PASSWORD=yourpassword
```

### Step 5: Initialize the database
```bash
# The application will initialize the database on first run,
# but you can also run this script directly:
python -c "from database import init_db; init_db()"
```

## 🚦 Usage

### Development Mode
```bash
python main.py
```

### Production Mode
```bash
gunicorn -w 4 -b 0.0.0.0:5000 main:app
```

Access the application by opening a web browser and navigating to:
```
http://localhost:5000/
```

### Default Admin Account
Username: admin
Password: admin123 (change this in production!)

## 📁 Project Structure

```
genai_evaluation/
├── main.py                 # Main application entry point
├── config.py               # Configuration settings
├── models.py               # Database models
├── database.py             # Database connection and session management
├── evaluator.py            # Core evaluation logic
├── quality_control.py      # Quality control mechanisms
├── analytics.py            # Analytics and reporting functionality
├── utils.py                # Utility functions
├── interfaces/             # Web interface modules
│   ├── web_interface.py    # Main web interface
│   ├── expert_portal.py    # Expert portal interface
│   └── dashboard.py        # Analytics dashboard
├── templates/              # HTML templates
├── static/                 # Static assets (CSS, JS, images)
└── tests/                  # Unit and integration tests
```

## 🔧 Configuration Options

The system can be configured through the `config.py` file or environment variables:

- **Content Domains:** Add or modify domains in `CONTENT_DOMAINS`
- **Evaluation Criteria:** Customize criteria in `EVALUATION_CRITERIA`
- **Quality Control:** Adjust thresholds in quality control parameters
- **Analytics:** Configure reporting timeframes and improvement thresholds

## 📊 Data Management

### Importing Content
```python
from utils import import_content_from_json
import_content_from_json('path/to/content.json')
```

### Exporting Evaluations
```python
from utils import export_evaluations_to_csv
export_evaluations_to_csv('evaluations.csv', {'domain': 'creative_writing'})
```

## 👥 User Roles

1. **Evaluators:** Regular users who can evaluate content
2. **Experts:** Domain specialists with verified expertise
3. **Admins:** System administrators with full access

## 📈 Evaluation Process

1. Content is added to the system (AI-generated or human-created)
2. Experts are assigned content in their domains of expertise
3. Evaluations are completed with quality control checks
4. Analytics are generated to identify improvement areas
5. Model improvement suggestions are provided based on evaluation data

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📧 Contact

Project Maintainer - yourname@example.com

---

*Note: Replace placeholder image paths with actual screenshots once the application is running.*
