# Create target directories
New-Item -ItemType Directory -Force -Path "templates", "static\css", "static\js" | Out-Null

Write-Host "Generating JavaScript files..." -ForegroundColor Green

# JavaScript app logic
@'
document.addEventListener('DOMContentLoaded', () => {
    initFlashMessageDismissal();
    initTransactionFilters();
    initFileUploadPreview();
});

// Flash message auto-dismissal
function initFlashMessageDismissal() {
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        setTimeout(() => {
            alert.style.opacity = '0';
            setTimeout(() => alert.remove(), 500);
        }, 4000);
    });
}

// Client-side instant filtering for Transactions table
function initTransactionFilters() {
    const memberFilter = document.getElementById('filter-member');
    const accountFilter = document.getElementById('filter-account');
    const typeFilter = document.getElementById('filter-type');
    const tableRows = document.querySelectorAll('#transactions-table tbody tr');

    if (!memberFilter || !tableRows.length) return;

    function filterTable() {
        const selectedMember = memberFilter.value.toLowerCase();
        const selectedAccount = accountFilter.value.toLowerCase();
        const selectedType = typeFilter.value.toLowerCase();

        tableRows.forEach(row => {
            if (row.children.length === 1) return; // Skip empty row

            const memberText = row.children[1].textContent.toLowerCase();
            const accountText = row.children[2].textContent.toLowerCase();
            const typeText = row.children[4].textContent.toLowerCase();

            const matchMember = !selectedMember || memberText.includes(selectedMember);
            const matchAccount = !selectedAccount || accountText.includes(selectedAccount);
            const matchType = !selectedType || typeText.includes(selectedType);

            row.style.display = (matchMember && matchAccount && matchType) ? '' : 'none';
        });
    }

    memberFilter.addEventListener('change', filterTable);
    accountFilter.addEventListener('change', filterTable);
    typeFilter.addEventListener('change', filterTable);
}

// Drag & drop file upload handler
function initFileUploadPreview() {
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file');
    const fileLabel = document.getElementById('file-label');

    if (!dropZone || !fileInput) return;

    ['dragenter', 'dragover'].forEach(eventName => {
        dropZone.addEventListener(eventName, (e) => {
            e.preventDefault();
            dropZone.classList.add('highlight');
        }, false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, (e) => {
            e.preventDefault();
            dropZone.classList.remove('highlight');
        }, false);
    });

    dropZone.addEventListener('drop', (e) => {
        const dt = e.dataTransfer;
        const files = dt.files;
        fileInput.files = files;
        if (files.length > 0) {
            fileLabel.textContent = `Selected: ${files[0].name}`;
        }
    });

    fileInput.addEventListener('change', () => {
        if (fileInput.files.length > 0) {
            fileLabel.textContent = `Selected: ${fileInput.files[0].name}`;
        }
    });
}

// Delete helper via API call
async function deleteEntity(endpoint, id, elementId) {
    if (!confirm('Are you sure you want to delete this item?')) return;

    try {
        const response = await fetch(`${endpoint}/${id}`, {
            method: 'DELETE',
            headers: { 'Content-Type': 'application/json' }
        });

        if (response.ok) {
            const el = document.getElementById(elementId);
            if (el) el.remove();
        } else {
            alert('Failed to delete item.');
        }
    } catch (err) {
        console.error('Error deleting entity:', err);
    }
}
'@ | Set-Content -Path "static\js\app.js" -Encoding UTF8


Write-Host "Generating Base CSS Stylesheet..." -ForegroundColor Green

@'
:root {
  --primary-color: #2c3e50;
  --secondary-color: #3498db;
  --success-color: #2ecc71;
  --warning-color: #f1c40f;
  --danger-color: #e74c3c;
  --bg-color: #f8f9fa;
  --card-bg: #ffffff;
  --text-color: #333333;
  --border-color: #e2e8f0;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  background-color: var(--bg-color);
  color: var(--text-color);
  margin: 0; padding: 0;
}

header {
  background-color: var(--primary-color);
  color: white;
  padding: 1rem 2rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

header nav a {
  color: white;
  text-decoration: none;
  margin-left: 1.5rem;
  font-weight: 500;
}

header nav a:hover { text-decoration: underline; }

main { padding: 2rem; max-width: 1200px; margin: 0 auto; }

.flash-messages { margin-bottom: 1.5rem; }
.alert {
  padding: 0.75rem 1.25rem;
  border-radius: 4px;
  margin-bottom: 0.5rem;
  transition: opacity 0.5s ease;
}
.alert-success { background-color: #d4edda; color: #155724; }
.alert-danger { background-color: #f8d7da; color: #721c24; }

.form-group { margin-bottom: 1rem; }
.form-group label { display: block; margin-bottom: 0.5rem; font-weight: bold; }
.form-group input, .form-group select {
  width: 100%; padding: 0.5rem;
  border: 1px solid var(--border-color);
  border-radius: 4px; box-sizing: border-box;
}

.btn {
  padding: 0.5rem 1rem; border: none;
  border-radius: 4px; cursor: pointer;
  font-weight: bold; text-decoration: none;
  display: inline-block;
}
.btn-primary { background-color: var(--secondary-color); color: white; }
.btn-success { background-color: var(--success-color); color: white; }
.btn-danger { background-color: var(--danger-color); color: white; }
.btn-sm { padding: 0.25rem 0.5rem; font-size: 0.8rem; }

table {
  width: 100%; border-collapse: collapse;
  background-color: var(--card-bg);
  box-shadow: 0 1px 3px rgba(0,0,0,0.1);
}
th, td { padding: 0.75rem 1rem; text-align: left; border-bottom: 1px solid var(--border-color); }
th { background-color: #edf2f7; }

.card {
  background: var(--card-bg); padding: 1.5rem;
  border-radius: 6px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);
  margin-bottom: 1.5rem;
}

.drop-zone {
  border: 2px dashed var(--secondary-color);
  padding: 2rem; text-align: center;
  border-radius: 6px; background: #f0f8ff;
  cursor: pointer; margin-bottom: 1rem;
}
.drop-zone.highlight { background: #e1f0ff; border-color: var(--primary-color); }

.grid-3 { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 1.5rem; }
.list-group { list-style: none; padding: 0; }
.list-group-item { padding: 0.75rem; border-bottom: 1px solid var(--border-color); display: flex; justify-content: space-between; align-items: center; }
.item-actions { display: flex; gap: 0.5rem; }

.metrics-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 1.5rem; margin-bottom: 2rem; }
.metric-card { background: white; padding: 1.5rem; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); border-left: 5px solid var(--primary-color); }
.metric-card.income { border-left-color: var(--success-color); }
.metric-card.expense { border-left-color: var(--danger-color); }
.metric-card.investment { border-left-color: var(--secondary-color); }
.metric-card.transfer { border-left-color: var(--warning-color); }
.metric-title { font-size: 0.875rem; color: #718096; text-transform: uppercase; }
.metric-value { font-size: 1.5rem; font-weight: bold; margin-top: 0.5rem; }
'@ | Set-Content -Path "static\css\base.css" -Encoding UTF8


Write-Host "Generating Base HTML Template..." -ForegroundColor Green

# Root base.html template rendered by run.py
@'
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}Balance Management - Finance Tracker{% endblock %}</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='css/base.css') }}">
    {% block extra_css %}{% endblock %}
</head>
<body>
    <header>
        <h1><a href="/" style="color: white; text-decoration: none;">Balance Management</a></h1>
        <nav>
            {% if current_user is defined and current_user.is_authenticated %}
                <a href="/dashboard">Dashboard</a>
                <a href="/transactions">Transactions</a>
                <a href="/upload">Upload</a>
                <a href="/manage">Manage Entities</a>
                <a href="/logout">Logout</a>
            {% else %}
                <a href="/login">Login / Register</a>
            {% endif %}
        </nav>
    </header>

    <main>
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                <div class="flash-messages">
                    {% for category, message in messages %}
                        <div class="alert alert-{{ category }}">{{ message }}</div>
                    {% endfor %}
                </div>
            {% endif %}
        {% endwith %}

        {% block content %}
        <div class="card" style="text-align: center; padding: 3rem;">
            <h2>Welcome to Balance Management App</h2>
            <p style="margin: 1.5rem 0; color: #4a5568;">
                Manage your incomes, expenses, investments, categories, and account balance records seamlessly.
            </p>
            <div style="display: flex; gap: 1rem; justify-content: center;">
                <a href="/login" class="btn btn-primary">Login / Register</a>
                <a href="/dashboard" class="btn btn-success">Go to Dashboard</a>
            </div>
        </div>
        {% endblock %}
    </main>

    <script src="{{ url_for('static', filename='js/app.js') }}"></script>
    {% block extra_js %}{% endblock %}
</body>
</html>
'@ | Set-Content -Path "templates\base.html" -Encoding UTF8

Write-Host "Base template setup complete! Execute python run.py to view." -ForegroundColor Green