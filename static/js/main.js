/**
 * Main JavaScript file for the Generative AI Content Evaluation System
 */

// Wait for the DOM to be fully loaded
document.addEventListener('DOMContentLoaded', function() {
    // Initialize tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function(tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Initialize popovers
    const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    popoverTriggerList.map(function(popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });
    
    // Auto-dismiss alerts after 5 seconds
    setTimeout(function() {
        const alerts = document.querySelectorAll('.alert:not(.alert-permanent)');
        alerts.forEach(function(alert) {
            const bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        });
    }, 5000);
    
    // Handle evaluation star ratings
    setupRatingStars();
    
    // Initialize charts if on dashboard
    setupDashboardCharts();
});

/**
 * Setup star rating functionality
 */
function setupRatingStars() {
    const ratingInputs = document.querySelectorAll('.rating-stars input');
    
    ratingInputs.forEach(input => {
        input.addEventListener('change', function() {
            // Update any visual indicators if needed
            const ratingValue = this.value;
            const criterionId = this.name;
            
            // You could update a display element to show the selected rating value
            const displayElem = document.querySelector(`.rating-value[data-for="${criterionId}"]`);
            if (displayElem) {
                displayElem.textContent = ratingValue;
            }
        });
    });
}

/**
 * Setup dashboard charts
 */
function setupDashboardCharts() {
    // Check if we're on a page with charts
    if (!document.getElementById('content-distribution-chart') && 
        !document.getElementById('evaluation-trends-chart')) {
        return;
    }
    
    // Content distribution chart
    const contentDistributionCtx = document.getElementById('content-distribution-chart');
    if (contentDistributionCtx) {
        // Get data from a data attribute or API call
        const labels = JSON.parse(contentDistributionCtx.dataset.labels || '[]');
        const data = JSON.parse(contentDistributionCtx.dataset.values || '[]');
        
        new Chart(contentDistributionCtx, {
            type: 'doughnut',
            data: {
                labels: labels,
                datasets: [{
                    data: data,
                    backgroundColor: [
                        'rgba(54, 162, 235, 0.7)',
                        'rgba(75, 192, 192, 0.7)',
                        'rgba(255, 206, 86, 0.7)',
                        'rgba(255, 99, 132, 0.7)',
                        'rgba(153, 102, 255, 0.7)',
                        'rgba(255, 159, 64, 0.7)'
                    ],
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: {
                        position: 'right',
                    },
                    title: {
                        display: true,
                        text: 'Content Distribution by Domain'
                    }
                }
            }
        });
    }
    
    // Evaluation trends chart
    const evaluationTrendsCtx = document.getElementById('evaluation-trends-chart');
    if (evaluationTrendsCtx) {
        const labels = JSON.parse(evaluationTrendsCtx.dataset.labels || '[]');
        const data = JSON.parse(evaluationTrendsCtx.dataset.values || '[]');
        
        new Chart(evaluationTrendsCtx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Evaluations Completed',
                    data: data,
                    borderColor: 'rgba(54, 162, 235, 1)',
                    backgroundColor: 'rgba(54, 162, 235, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.3
                }]
            },
            options: {
                responsive: true,
                scales: {
                    y: {
                        beginAtZero: true
                    }
                },
                plugins: {
                    title: {
                        display: true,
                        text: 'Evaluation Completion Trends'
                    }
                }
            }
        });
    }
}

/**
 * Create a model comparison chart
 * @param {string} elementId - The ID of the canvas element
 * @param {Object} data - The comparison data
 */
function createModelComparisonChart(elementId, data) {
    const ctx = document.getElementById(elementId);
    if (!ctx) return;
    
    const models = data.overall_ranking.map(item => item.model);
    const scores = data.overall_ranking.map(item => item.score);
    
    new Chart(ctx, {
        type: 'bar',
        data: {
            labels: models,
            datasets: [{
                label: 'Overall Score',
                data: scores,
                backgroundColor: 'rgba(54, 162, 235, 0.7)',
                borderColor: 'rgba(54, 162, 235, 1)',
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            scales: {
                y: {
                    beginAtZero: true,
                    max: 5
                }
            },
            plugins: {
                title: {
                    display: true,
                    text: 'Model Comparison - Overall Scores'
                }
            }
        }
    });
}

/**
 * Create a criteria comparison radar chart
 * @param {string} elementId - The ID of the canvas element
 * @param {Object} data - The comparison data
 * @param {string} modelName - The model name to show
 */
function createCriteriaRadarChart(elementId, data, modelName) {
    const ctx = document.getElementById(elementId);
    if (!ctx) return;
    
    const modelData = data.models[modelName];
    if (!modelData) return;
    
    const criteriaNames = Object.keys(modelData.criteria_scores);
    const criteriaScores = Object.values(modelData.criteria_scores);
    
    new Chart(ctx, {
        type: 'radar',
        data: {
            labels: criteriaNames.map(name => name.charAt(0).toUpperCase() + name.slice(1)),
            datasets: [{
                label: modelName,
                data: criteriaScores,
                backgroundColor: 'rgba(54, 162, 235, 0.2)',
                borderColor: 'rgba(54, 162, 235, 1)',
                pointBackgroundColor: 'rgba(54, 162, 235, 1)',
                pointBorderColor: '#fff',
                pointHoverBackgroundColor: '#fff',
                pointHoverBorderColor: 'rgba(54, 162, 235, 1)'
            }]
        },
        options: {
            responsive: true,
            scales: {
                r: {
                    angleLines: {
                        display: true
                    },
                    suggestedMin: 0,
                    suggestedMax: 5
                }
            },
            plugins: {
                title: {
                    display: true,
                    text: `${modelName} - Criteria Performance`
                }
            }
        }
    });
}

/**
 * Create a human-AI gap chart
 * @param {string} elementId - The ID of the canvas element
 * @param {Object} data - The gap analysis data
 */
function createHumanAIGapChart(elementId, data) {
    const ctx = document.getElementById(elementId);
    if (!ctx) return;
    
    const criteria = Object.keys(data.criteria);
    const humanScores = criteria.map(c => data.criteria[c].human_score);
    const aiScores = criteria.map(c => data.criteria[c].ai_score);
    
    new Chart(ctx, {
        type: 'bar',
        data: {
            labels: criteria.map(c => c.charAt(0).toUpperCase() + c.slice(1)),
            datasets: [
                {
                    label: 'Human Benchmark',
                    data: humanScores,
                    backgroundColor: 'rgba(75, 192, 192, 0.7)',
                    borderColor: 'rgba(75, 192, 192, 1)',
                    borderWidth: 1
                },
                {
                    label: 'Best AI Model',
                    data: aiScores,
                    backgroundColor: 'rgba(54, 162, 235, 0.7)',
                    borderColor: 'rgba(54, 162, 235, 1)',
                    borderWidth: 1
                }
            ]
        },
        options: {
            responsive: true,
            scales: {
                y: {
                    beginAtZero: true,
                    max: 5
                }
            },
            plugins: {
                title: {
                    display: true,
                    text: 'Human vs AI Performance by Criteria'
                }
            }
        }
    });
}

/**
 * Handle API calls
 * @param {string} url - The API endpoint URL
 * @param {Object} options - Fetch options
 * @returns {Promise} - The fetch promise
 */
async function fetchAPI(url, options = {}) {
    try {
        const response = await fetch(url, {
            ...options,
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            }
        });
        
        if (!response.ok) {
            throw new Error(`API error: ${response.status}`);
        }
        
        return await response.json();
    } catch (error) {
        console.error('API request error:', error);
        throw error;
    }
}

/**
 * Validate an evaluation form
 * @param {HTMLFormElement} form - The form element
 * @returns {boolean} - Whether the form is valid
 */
function validateEvaluationForm(form) {
    let isValid = true;
    
    // Check if all criteria have been rated
    const criteriaInputs = form.querySelectorAll('[name^="criterion_"]');
    const criteriaGroups = {};
    
    // Group inputs by name
    criteriaInputs.forEach(input => {
        const name = input.name;
        if (!criteriaGroups[name]) {
            criteriaGroups[name] = [];
        }
        criteriaGroups[name].push(input);
    });
    
    // Check each group for a selected value
    for (const name in criteriaGroups) {
        const group = criteriaGroups[name];
        const hasSelection = group.some(input => input.checked);
        
        if (!hasSelection) {
            isValid = false;
            const criterionLabel = document.querySelector(`label[for="${group[0].id}"]`).closest('.criterion-container').querySelector('.criterion-name');
            alert(`Please rate the "${criterionLabel.textContent}" criterion`);
            break;
        }
    }
    
    // Check overall rating
    const overallRating = form.querySelector('[name="overall_rating"]:checked');
    if (!overallRating) {
        isValid = false;
        alert('Please provide an overall rating');
    }
    
    return isValid;
}

/**
 * Update pagination links with current filters
 */
function updatePaginationLinks() {
    const currentUrl = new URL(window.location.href);
    const paginationLinks = document.querySelectorAll('.pagination .page-link');
    
    paginationLinks.forEach(link => {
        if (link.dataset.page) {
            const url = new URL(link.href);
            
            // Copy all query parameters from current URL except page
            for (const [key, value] of currentUrl.searchParams.entries()) {
                if (key !== 'page') {
                    url.searchParams.set(key, value);
                }
            }
            
            // Set the page parameter
            url.searchParams.set('page', link.dataset.page);
            link.href = url.toString();
        }
    });
}

// Initialize pagination links when page loads
document.addEventListener('DOMContentLoaded', function() {
    updatePaginationLinks();
    
    // Update links when filter form changes
    const filterForm = document.querySelector('.filter-form');
    if (filterForm) {
        filterForm.addEventListener('change', function() {
            this.submit();
        });
    }
});