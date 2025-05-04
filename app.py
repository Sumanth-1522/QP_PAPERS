from flask import Flask, render_template_string, request, redirect, url_for, flash, make_response, session, jsonify
from flask_bcrypt import Bcrypt
import sqlite3
from werkzeug.utils import secure_filename
import math
import logging
import os
import uuid
from datetime import datetime, timedelta

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'supersecretkey')  # Use env var or fallback
bcrypt = Bcrypt(app)

# SQLite database path
DATABASE = 'qpaper.db'

# SQLite connection
def get_db_connection():
    try:
        conn = sqlite3.connect(DATABASE)
        conn.row_factory = sqlite3.Row  # Enable row access by column name
        logging.info("SQLite connection successful")
        return conn
    except sqlite3.Error as e:
        logging.error(f"SQLite connection failed: {str(e)}")
        return None

# Initialize database and tables
def init_db():
    conn = get_db_connection()
    if not conn:
        logging.error("Failed to connect to SQLite database in init_db.")
        return
    try:
        cursor = conn.cursor()
        logging.debug("Creating question_papers_1 table if not exists")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS question_papers_1 (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                year_name TEXT NOT NULL,
                semester_no INTEGER NOT NULL,
                subject_name TEXT NOT NULL,
                subject_code TEXT,
                paper_type TEXT NOT NULL CHECK(paper_type IN ('Regular', 'Arrear')),
                paper_year INTEGER,
                file_data BLOB NOT NULL
            )
        """)
        logging.debug("Creating visitor_stats table if not exists")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS visitor_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME NOT NULL,
                visitor_id TEXT NOT NULL
            )
        """)
        conn.commit()
        logging.info("SQLite database initialized successfully")
    except sqlite3.Error as e:
        logging.error(f"Error initializing SQLite database: {str(e)}")
    finally:
        cursor.close()
        conn.close()

# Allowed file extensions
ALLOWED_EXTENSIONS = {'pdf'}

# Helper function to check allowed file extensions
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Check if admin is logged in
def admin_required(f):
    def wrap(*args, **kwargs):
        if 'role' not in session or session['role'] != 'admin':
            flash("Admin access required.", "error")
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    wrap.__name__ = f.__name__
    return wrap

# Get visitor statistics
def get_visitor_stats():
    conn = get_db_connection()
    if not conn:
        return {'total_visits': 0, 'unique_visitors': 0, 'daily_visits': []}
    
    try:
        cursor = conn.cursor()
        # Total visits
        cursor.execute("SELECT COUNT(*) FROM visitor_stats")
        total_visits = cursor.fetchone()[0]
        
        # Unique visitors
        cursor.execute("SELECT COUNT(DISTINCT visitor_id) FROM visitor_stats")
        unique_visitors = cursor.fetchone()[0]
        
        # Daily visits for the last 7 days
        daily_visits = []
        for i in range(6, -1, -1):
            date = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
            cursor.execute("""
                SELECT COUNT(*) FROM visitor_stats 
                WHERE DATE(timestamp) = ?
            """, (date,))
            count = cursor.fetchone()[0]
            daily_visits.append({'date': date, 'count': count})
        
        return {
            'total_visits': total_visits,
            'unique_visitors': unique_visitors,
            'daily_visits': daily_visits
        }
    except sqlite3.Error as e:
        logging.error(f"Error fetching visitor stats: {str(e)}")
        return {'total_visits': 0, 'unique_visitors': 0, 'daily_visits': []}
    finally:
        cursor.close()
        conn.close()

# Custom 404 error handler
@app.errorhandler(404)
def page_not_found(e):
    logging.error(f"404 error: Requested URL {request.url} not found")
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>404 - Page Not Found</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <style>
            body { font-family: 'Inter', sans-serif; background-color: #F9FAFB; color: #1E293B; }
            .gradient-header { background: linear-gradient(to right, #4F46E5, #06B6D4); }
            .card { transition: transform 0.2s, box-shadow 0.2s; }
            .card:hover { transform: translateY(-0.25rem); box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); }
        </style>
    </head>
    <body>
        <header class="gradient-header text-white py-4">
            <div class="container mx-auto px-4">
                <h1 class="text-2xl font-bold">Q_papers</h1>
            </div>
        </header>
        <div class="container mx-auto px-4 py-8 flex justify-center">
            <div class="bg-white p-6 rounded-lg shadow-sm card w-full max-w-md">
                <h2 class="text-2xl font-semibold mb-4 text-slate-900">404 - Page Not Found</h2>
                <p class="text-slate-900 mb-4">The page you are looking for does not exist. Please check the URL or try the link below.</p>
                <div class="space-y-4">
                    <a href="{{ url_for('papers') }}" class="block bg-indigo-600 text-white px-4 py-2 rounded-md hover:bg-amber-500 transition-colors duration-200 text-center">Papers Section</a>
                </div>
            </div>
        </div>
    </body>
    </html>
    """), 404

# Test database connection endpoint
@app.route('/test_db')
def test_db():
    conn = get_db_connection()
    if not conn:
        return jsonify({
            "status": "error",
            "message": "Failed to connect to SQLite: Check logs for details."
        }), 500
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='question_papers_1'")
        table_count = cursor.fetchone()[0]
        return jsonify({
            "status": "success",
            "message": f"Connected to SQLite. Found {table_count} tables in '{DATABASE}' database."
        })
    except sqlite3.Error as e:
        return jsonify({
            "status": "error",
            "message": f"Failed to query SQLite: {str(e)}"
        }), 500
    finally:
        cursor.close()
        conn.close()

# HTML template for admin login page
ADMIN_LOGIN_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Admin Login</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body { font-family: 'Inter', sans-serif; background-color: #F9FAFB; color: #1E293B; }
        .alert { padding: 10px; margin-bottom: 20px; border-radius: 5px; }
        .alert-error { background-color: #FEE2E2; color: #B91C1C; }
        .alert-success { background-color: #D1FAE5; color: #065F46; }
        .gradient-header { background: linear-gradient(to right, #4F46E5, #06B6D4); }
        .card { transition: transform 0.2s, box-shadow 0.2s; }
        .card:hover { transform: translateY(-0.25rem); box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); }
        button { transition: all 0.2s; }
        button:hover { transform: scale(1.05); }
    </style>
</head>
<body>
    <header class="gradient-header text-white py-4">
        <div class="container mx-auto px-4">
            <h1 class="text-2xl font-bold">Admin Login</h1>
        </div>
    </header>
    <div class="container mx-auto px-4 py-8 flex justify-center">
        <div class="bg-white p-6 rounded-lg shadow-sm card w-full max-w-md">
            <h2 class="text-2xl font-semibold mb-4 text-slate-900">Admin Sign In</h2>
            <!-- Flash Messages -->
            {% with messages = get_flashed_messages(with_categories=true) %}
                {% if messages %}
                    {% for category, message in messages %}
                        <div class="alert alert-{{ category }}">{{ message }}</div>
                    {% endfor %}
                {% endif %}
            {% endwith %}
            <form method="POST" action="{{ url_for('admin_login') }}" class="space-y-4">
                <div>
                    <label class="block text-base font-bold text-slate-900">Email</label>
                    <input type="email" name="email" required class="mt-1 block w-full border border-gray-300 rounded-md p-2 text-slate-900 focus:ring-indigo-500 focus:border-indigo-500">
                </div>
                <div>
                    <label class="block text-base font-bold text-slate-900">Password</label>
                    <input type="password" name="password" required class="mt-1 block w-full border border-gray-300 rounded-md p-2 text-slate-900 focus:ring-indigo-500 focus:border-indigo-500">
                </div>
                <button type="submit" class="bg-indigo-600 text-white px-4 py-2 rounded-md hover:bg-amber-500 w-full transition-colors duration-200">Login</button>
            </form>
        </div>
    </div>
</body>
</html>
"""

# HTML template for admin page
ADMIN_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Admin - Question Paper Management</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body { font-family: 'Inter', sans-serif; background-color: #F9FAFB; color: #1E293B; }
        .alert { padding: 10px; margin-bottom: 20px; border-radius: 5px; }
        .alert-success { background-color: #D1FAE5; color: #065F46; }
        .alert-error { background-color: #FEE2E2; color: #B91C1C; }
        .gradient-header { background: linear-gradient(to right, #4F46E5, #06B6D4); }
        .card { transition: transform 0.2s, box-shadow 0.2s; }
        .card:hover { transform: translateY(-0.25rem); box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); }
        .spinner { display: none; border: 4px solid #E5E7EB; border-top: 4px solid #4F46E5; border-radius: 50%; width: 24px; height: 24px; animation: spin 1s linear infinite; }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        #splash { position: fixed; top: 0; left: 0; width: 100%; height: 100%; background-color: #F9FAFB; display: flex; align-items: center; justify-content: center; z-index: 1000; animation: fadeOut 0.5s ease-out 2.5s forwards; }
        #splash-content { text-align: center; position: relative; }
        #splash-content::before { content: ''; position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); width: 200px; height: 200px; background: radial-gradient(circle, rgba(6, 182, 212, 0.3), transparent); z-index: -1; }
        #splash-content h1 { animation: fadeInScale 1s ease-out; }
        #splash-content p.subtitle { animation: slideInUp 1s ease-out 0.5s both; }
        #splash::before, #splash::after { content: ''; position: absolute; width: 10px; height: 10px; background: rgba(79, 70, 229, 0.7); border-radius: 50%; animation: particle 3s linear; }
        #splash::before { top: 20%; left: 30%; animation-name: particleLeft; }
        #splash::after { top: 70%; left: 60%; animation-name: particleRight; }
        #splash-content p { margin-top: 20px; font-size: 1.2rem; }
        @keyframes gradientShift {
            0% { background: linear-gradient(45deg, #4F46E5, #06B6D4); }
            50% { background: linear-gradient(45deg, #06B6D4, #F59E0B); }
            100% { background: linear-gradient(45deg, #F59E0B, #4F46E5); }
        }
        #splash { background: linear-gradient(45deg, #4F46E5, #06B6D4); animation: gradientShift 3s ease infinite; }
        @keyframes fadeInScale {
            from { opacity: 0; transform: scale(0.8); color: #1E293B; }
            to { opacity: 1; transform: scale(1); color: #4F46E5; }
        }
        @keyframes slideInUp {
            from { opacity: 0; transform: translateY(20px); }
            to { opacity: 1; transform: translateY(0); }
        }
        @keyframes particleLeft {
            0% { transform: translate(0, 0); opacity: 0.7; }
            100% { transform: translate(-100px, -100px); opacity: 0; }
        }
        @keyframes particleRight {
            0% { transform: translate(0, 0); opacity: 0.7; }
            100% { transform: translate(100px, 100px); opacity: 0; }
        }
        @keyframes fadeOut { to { opacity: 0; } }
        button, a { transition: all 0.2s; }
        button:hover, a:hover:not(.disabled) { transform: scale(1.05); }
    </style>
</head>
<body>
    <div id="splash">
        <div id="splash-content">
            <h1 class="text-3xl font-bold text-slate-900">Welcome to Q_papers</h1>
            <p class="text-slate-900 subtitle">It is only for Dhanalaxmi Srinivasan University</p>
        </div>
        <div class="absolute bottom-4 right-4 text-slate-900 font-bold">
            <p>D. Sumanth</p>
            <p>J. Praveen</p>
        </div>
    </div>
    <header class="gradient-header text-white py-4">
        <div class="container mx-auto px-4 flex justify-between items-center">
            <h1 class="text-2xl font-bold">Admin - Question Paper Management</h1>
            <div class="flex items-center space-x-4">
                <span class="text-sm">Welcome, Admin</span>
                <a href="{{ url_for('admin_logout') }}" class="bg-red-600 text-white px-3 py-1 rounded-md hover:bg-amber-500 transition-colors duration-200">Logout</a>
            </div>
        </div>
    </header>
    <div class="container mx-auto px-4 py-8">
        <!-- Flash Messages -->
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="alert {% if category == 'success' %}alert-success{% else %}alert-error{% endif %}">
                        {{ message }}
                    </div>
                {% endfor %}
            {% endif %}
        {% endwith %}

        <!-- Visitor Statistics -->
        <div class="bg-white p-6 rounded-lg shadow-sm mb-8 card">
            <h2 class="text-2xl font-semibold mb-4 text-slate-900">Visitor Statistics</h2>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                <div>
                    <p class="text-base font-bold text-slate-900">Total Visits</p>
                    <p class="text-2xl text-indigo-600">{{ visitor_stats.total_visits }}</p>
                </div>
                <div>
                    <p class="text-base font-bold text-slate-900">Unique Visitors</p>
                    <p class="text-2xl text-indigo-600">{{ visitor_stats.unique_visitors }}</p>
                </div>
            </div>
            <div>
                <h3 class="text-lg font-semibold mb-2 text-slate-900">Daily Visits (Last 7 Days)</h3>
                <canvas id="dailyVisitsChart" height="100"></canvas>
            </div>
        </div>

        <!-- Search and Sort -->
        <div class="bg-white p-6 rounded-lg shadow-sm mb-8 card">
            <div class="flex flex-col md:flex-row gap-4">
                <div class="flex-1">
                    <label class="block text-base font-bold text-slate-900">Search</label>
                    <input type="text" id="search" class="mt-1 block w-full border border-gray-300 rounded-md p-2 text-slate-900 focus:ring-indigo-500 focus:border-indigo-500" placeholder="Search by Year, Subject, or Code">
                </div>
                <div>
                    <label class="block text-base font-bold text-slate-900">Sort By</label>
                    <select id="sort" class="mt-1 block w-full border border-gray-300 rounded-md p-2 text-slate-900 focus:ring-indigo-500 focus:border-indigo-500">
                        <option value="id">ID</option>
                        <option value="year_name">Year</option>
                        <option value="semester_no">Semester</option>
                        <option value="paper_year">Paper Year</option>
                    </select>
                </div>
            </div>
        </div>

        <!-- Add Form -->
        <div class="bg-white p-6 rounded-lg shadow-sm mb-8 card">
            <h2 class="text-2xl font-semibold mb-4 text-slate-900">Add New Question Paper</h2>
            <form id="add-form" method="POST" enctype="multipart/form-data" action="{{ url_for('add') }}" class="space-y-4">
                <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                        <label class="block text-base font-bold text-slate-900">Year Name</label>
                        <input type="text" name="year_name" required maxlength="20" class="mt-1 block w-full border border-gray-300 rounded-md p-2 text-slate-900 focus:ring-indigo-500 focus:border-indigo-500">
                    </div>
                    <div>
                        <label class="block text-base font-bold text-slate-900">Semester No</label>
                        <input type="number" name="semester_no" required min="1" max="12" class="mt-1 block w-full border border-gray-300 rounded-md p-2 text-slate-900 focus:ring-indigo-500 focus:border-indigo-500">
                    </div>
                    <div>
                        <label class="block text-base font-bold text-slate-900">Subject Name</label>
                        <input type="text" name="subject_name" required maxlength="100" class="mt-1 block w-full border border-gray-300 rounded-md p-2 text-slate-900 focus:ring-indigo-500 focus:border-indigo-500">
                    </div>
                    <div>
                        <label class="block text-base font-bold text-slate-900">Subject Code</label>
                        <input type="text" name="subject_code" maxlength="20" class="mt-1 block w-full border border-gray-300 rounded-md p-2 text-slate-900 focus:ring-indigo-500 focus:border-indigo-500">
                    </div>
                    <div>
                        <label class="block text-base font-bold text-slate-900">Paper Type</label>
                        <select name="paper_type" required class="mt-1 block w-full border border-gray-300 rounded-md p-2 text-slate-900 focus:ring-indigo-500 focus:border-indigo-500">
                            <option value="Regular">Regular</option>
                            <option value="Arrear">Arrear</option>
                        </select>
                    </div>
                    <div>
                        <label class="block text-base font-bold text-slate-900">Paper Year</label>
                        <input type="number" name="paper_year" min="1900" max="9999" class="mt-1 block w-full border border-gray-300 rounded-md p-2 text-slate-900 focus:ring-indigo-500 focus:border-indigo-500">
                    </div>
                    <div>
                        <label class="block text-base font-bold text-slate-900">Upload File (PDF only)</label>
                        <input type="file" name="file" accept=".pdf" required class="mt-1 block w-full text-slate-900">
                    </div>
                </div>
                <button type="submit" class="bg-indigo-600 text-white px-4 py-2 rounded-md hover:bg-amber-500 transition-colors duration-200 flex items-center">
                    <span>Add Paper</span>
                    <span class="spinner ml-2"></span>
                </button>
            </form>
        </div>

        <!-- Records Table -->
        <div class="bg-white p-6 rounded-lg shadow-sm card">
            <h2 class="text-2xl font-semibold mb-4 text-slate-900">Question Papers</h2>
            {% if records %}
                <div class="overflow-x-auto">
                    <table class="min-w-full border-collapse" id="records-table">
                        <thead>
                            <tr class="bg-gray-100">
                                <th class="border px-4 py-2 text-slate-900">Year</th>
                                <th class="border px-4 py-2 text-slate-900">Semester</th>
                                <th class="border px-4 py-2 text-slate-900">Subject</th>
                                <th class="border px-4 py-2 text-slate-900">Code</th>
                                <th class="border px-4 py-2 text-slate-900">Type</th>
                                <th class="border px-4 py-2 text-slate-900">Paper Year</th>
                                <th class="border px-4 py-2 text-slate-900">File</th>
                                <th class="border px-4 py-2 text-slate-900">Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            {% for record in records %}
                                <tr>
                                    <td class="border px-4 py-2 text-slate-900">{{ record['year_name'] }}</td>
                                    <td class="border px-4 py-2 text-slate-900">{{ record['semester_no'] }}</td>
                                    <td class="border px-4 py-2 text-slate-900">{{ record['subject_name'] }}</td>
                                    <td class="border px-4 py-2 text-slate-900">{{ record['subject_code'] }}</td>
                                    <td class="border px-4 py-2 text-slate-900">{{ record['paper_type'] }}</td>
                                    <td class="border px-4 py-2 text-slate-900">{{ record['paper_year'] }}</td>
                                    <td class="border px-4 py-2">
                                        <a href="{{ url_for('download', id=record['id']) }}" class="text-indigo-600 hover:text-amber-500 transition-colors duration-200">Download</a>
                                    </td>
                                    <td class="border px-4 py-2">
                                        <a href="{{ url_for('update', id=record['id']) }}" class="text-yellow-600 hover:text-amber-500 mr-2 transition-colors duration-200">Edit</a>
                                        <a href="{{ url_for('delete', id=record['id']) }}" onclick="return confirm('Are you sure you want to delete this record?')" class="text-red-600 hover:text-amber-500 transition-colors duration-200">Delete</a>
                                    </td>
                                </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
                <!-- Pagination -->
                <div class="mt-4 flex justify-between">
                    <a {% if page > 1 %}href="{{ url_for('admin', page=page-1, search=search, sort=sort) }}"{% else %}class="text-gray-400 cursor-not-allowed disabled"{% endif %} class="px-4 py-2 bg-indigo-600 text-white rounded-md hover:bg-amber-500 transition-colors duration-200">Previous</a>
                    <span class="text-slate-900">Page {{ page }} of {{ total_pages }}</span>
                    <a {% if page < total_pages %}href="{{ url_for('admin', page=page+1, search=search, sort=sort) }}"{% else %}class="text-gray-400 cursor-not-allowed disabled"{% endif %} class="px-4 py-2 bg-indigo-600 text-white rounded-md hover:bg-amber-500 transition-colors duration-200">Next</a>
                </div>
            {% else %}
                <p class="text-slate-900">No records found.</p>
            {% endif %}
        </div>
    </div>
    <script>
        // Hide splash screen after 3 seconds
        setTimeout(() => {
            document.getElementById('splash').style.display = 'none';
        }, 3000);

        // Form validation and spinner
        document.getElementById('add-form').addEventListener('submit', (e) => {
            const yearName = document.querySelector('input[name="year_name"]').value;
            const semesterNo = document.querySelector('input[name="semester_no"]').value;
            const subjectName = document.querySelector('input[name="subject_name"]').value;
            const file = document.querySelector('input[name="file"]').files[0];
            if (yearName.length > 20 || subjectName.length > 100) {
                alert('Year Name or Subject Name exceeds maximum length.');
                e.preventDefault();
                return;
            }
            if (semesterNo < 1 || semesterNo > 12) {
                alert('Semester No must be between 1 and 12.');
                e.preventDefault();
                return;
            }
            if (file && !file.name.endsWith('.pdf')) {
                alert('Please upload a PDF file.');
                e.preventDefault();
                return;
            }
            document.querySelector('.spinner').style.display = 'inline-block';
        });

        // Search and sort
        const recordsTable = document.getElementById('records-table').getElementsByTagName('tbody')[0];
        const originalRows = Array.from(recordsTable.getElementsByTagName('tr'));
        document.getElementById('search').addEventListener('input', (e) => {
            const query = e.target.value.toLowerCase();
            const filteredRows = originalRows.filter(row => {
                const year = row.cells[0].textContent.toLowerCase();
                const subject = row.cells[2].textContent.toLowerCase();
                const code = row.cells[3].textContent.toLowerCase();
                return year.includes(query) || subject.includes(query) || code.includes(query);
            });
            recordsTable.innerHTML = '';
            filteredRows.forEach(row => recordsTable.appendChild(row));
        });

        document.getElementById('sort').addEventListener('change', (e) => {
            const sortBy = e.target.value;
            const rows = Array.from(recordsTable.getElementsByTagName('tr'));
            rows.sort((a, b) => {
                let aValue, bValue;
                if (sortBy === 'year_name') {
                    aValue = a.cells[0].textContent;
                    bValue = b.cells[0].textContent;
                } else if (sortBy === 'semester_no') {
                    aValue = parseInt(a.cells[1].textContent);
                    bValue = parseInt(b.cells[1].textContent);
                } else if (sortBy === 'paper_year') {
                    aValue = parseInt(a.cells[5].textContent) || 0;
                    bValue = parseInt(b.cells[5].textContent) || 0;
                } else {
                    aValue = parseInt(a.cells[0].textContent);
                    bValue = parseInt(b.cells[0].textContent);
                }
                return aValue > bValue ? 1 : -1;
            });
            recordsTable.innerHTML = '';
            rows.forEach(row => recordsTable.appendChild(row));
        });

        // Chart.js for daily visits
        const dailyVisits = {{ visitor_stats.daily_visits | tojson }};
        const ctx = document.getElementById('dailyVisitsChart').getContext('2d');
        new Chart(ctx, {
            type: 'bar',
            data: {
                labels: dailyVisits.map(d => d.date),
                datasets: [{
                    label: 'Daily Visits',
                    data: dailyVisits.map(d => d.count),
                    backgroundColor: '#4F46E5',
                    borderColor: '#4F46E5',
                    borderWidth: 1,
                    hoverBackgroundColor: '#F59E0B'
                }]
            },
            options: {
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: { stepSize: 1 }
                    }
                },
                plugins: {
                    legend: { display: false }
                }
            }
        });
    </script>
</body>
</html>
"""

# HTML template for papers section
PAPERS_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Question Papers</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body { font-family: 'Inter', sans-serif; background-color: #F9FAFB; color: #1E293B; }
        .alert { padding: 10px; margin-bottom: 20px; border-radius: 5px; }
        .alert-success { background-color: #D1FAE5; color: #065F46; }
        .alert-error { background-color: #FEE2E2; color: #B91C1C; }
        .gradient-header { background: linear-gradient(to right, #4F46E5, #06B6D4); }
        .card { transition: transform 0.2s, box-shadow 0.2s; }
        .card:hover { transform: translateY(-0.25rem); box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); }
        #splash { position: fixed; top: 0; left: 0; width: 100%; height: 100%; background-color: #F9FAFB; display: flex; align-items: center; justify-content: center; z-index: 1000; animation: fadeOut 0.5s ease-out 2.5s forwards; }
        #splash-content { text-align: center; position: relative; }
        #splash-content::before { content: ''; position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); width: 200px; height: 200px; background: radial-gradient(circle, rgba(6, 182, 212, 0.3), transparent); z-index: -1; }
        #splash-content h1 { animation: fadeInScale 1s ease-out; }
        #splash-content p.subtitle { animation: slideInUp 1s ease-out 0.5s both; }
        #splash::before, #splash::after { content: ''; position: absolute; width: 10px; height: 10px; background: rgba(79, 70, 229, 0.7); border-radius: 50%; animation: particle 3s linear; }
        #splash::before { top: 20%; left: 30%; animation-name: particleLeft; }
        #splash::after { top: 70%; left: 60%; animation-name: particleRight; }
        #splash-content p { margin-top: 20px; font-size: 1.2rem; }
        @keyframes gradientShift {
            0% { background: linear-gradient(45deg, #4F46E5, #06B6D4); }
            50% { background: linear-gradient(45deg, #06B6D4, #F59E0B); }
            100% { background: linear-gradient(45deg, #F59E0B, #4F46E5); }
        }
        #splash { background: linear-gradient(45deg, #4F46E5, #06B6D4); animation: gradientShift 3s ease infinite; }
        @keyframes fadeInScale {
            from { opacity: 0; transform: scale(0.8); color: #1E293B; }
            to { opacity: 1; transform: scale(1); color: #4F46E5; }
        }
        @keyframes slideInUp {
            from { opacity: 0; transform: translateY(20px); }
            to { opacity: 1; transform: translateY(0); }
        }
        @keyframes particleLeft {
            0% { transform: translate(0, 0); opacity: 0.7; }
            100% { transform: translate(-100px, -100px); opacity: 0; }
        }
        @keyframes particleRight {
            0% { transform: translate(0, 0); opacity: 0.7; }
            100% { transform: translate(100px, 100px); opacity: 0; }
        }
        @keyframes fadeOut { to { opacity: 0; } }
        a { transition: all 0.2s; }
        a:hover:not(.disabled) { transform: scale(1.05); }
    </style>
</head>
<body>
    <div id="splash">
        <div id="splash-content">
            <h1 class="text-3xl font-bold text-slate-900">Welcome to Q_papers</h1>
            <p class="text-slate-900 subtitle">It is only for Dhanalaxmi Srinivasan University</p>
        </div>
        <div class="absolute bottom-4 right-4 text-slate-900 font-bold">
            <p>D. Sumanth</p>
            <p>J. Praveen</p>
        </div>
    </div>
    <header class="gradient-header text-white py-4">
        <div class="container mx-auto px-4 flex justify-between items-center">
            <h1 class="text-2xl font-bold">Question Papers</h1>
        </div>
    </header>
    <div class="container mx-auto px-4 py-8">
        <!-- Flash Messages -->
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="alert {% if category == 'success' %}alert-success{% else %}alert-error{% endif %}">
                        {{ message }}
                    </div>
                {% endfor %}
            {% endif %}
        {% endwith %}

        <!-- Search and Sort -->
        <div class="bg-white p-6 rounded-lg shadow-sm mb-8 card">
            <div class="flex flex-col md:flex-row gap-4">
                <div class="flex-1">
                    <label class="block text-base font-bold text-slate-900">Search</label>
                    <input type="text" id="search" class="mt-1 block w-full border border-gray-300 rounded-md p-2 text-slate-900 focus:ring-indigo-500 focus:border-indigo-500" placeholder="Search by Year, Subject, or Code">
                </div>
                <div>
                    <label class="block text-base font-bold text-slate-900">Sort By</label>
                    <select id="sort" class="mt-1 block w-full border border-gray-300 rounded-md p-2 text-slate-900 focus:ring-indigo-500 focus:border-indigo-500">
                        <option value="id">ID</option>
                        <option value="year_name">Year</option>
                        <option value="semester_no">Semester</option>
                        <option value="paper_year">Paper Year</option>
                    </select>
                </div>
            </div>
        </div>

        <!-- Records Table -->
        <div class="bg-white p-6 rounded-lg shadow-sm card">
            <h2 class="text-2xl font-semibold mb-4 text-slate-900">Question Papers</h2>
            {% if records %}
                <div class="overflow-x-auto">
                    <table class="min-w-full border-collapse" id="records-table">
                        <thead>
                            <tr class="bg-gray-100">
                                <th class="border px-4 py-2 text-slate-900">Year</th>
                                <th class="border px-4 py-2 text-slate-900">Semester</th>
                                <th class="border px-4 py-2 text-slate-900">Subject</th>
                                <th class="border px-4 py-2 text-slate-900">Code</th>
                                <th class="border px-4 py-2 text-slate-900">Type</th>
                                <th class="border px-4 py-2 text-slate-900">Paper Year</th>
                                <th class="border px-4 py-2 text-slate-900">File</th>
                            </tr>
                        </thead>
                        <tbody>
                            {% for record in records %}
                                <tr>
                                    <td class="border px-4 py-2 text-slate-900">{{ record['year_name'] }}</td>
                                    <td class="border px-4 py-2 text-slate-900">{{ record['semester_no'] }}</td>
                                    <td class="border px-4 py-2 text-slate-900">{{ record['subject_name'] }}</td>
                                    <td class="border px-4 py-2 text-slate-900">{{ record['subject_code'] }}</td>
                                    <td class="border px-4 py-2 text-slate-900">{{ record['paper_type'] }}</td>
                                    <td class="border px-4 py-2 text-slate-900">{{ record['paper_year'] }}</td>
                                    <td class="border px-4 py-2">
                                        <a href="{{ url_for('download', id=record['id']) }}" class="text-indigo-600 hover:text-amber-500 transition-colors duration-200">Download</a>
                                    </td>
                                </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
                <!-- Pagination -->
                <div class="mt-4 flex justify-between">
                    <a {% if page > 1 %}href="{{ url_for('papers', page=page-1, search=search, sort=sort) }}"{% else %}class="text-gray-400 cursor-not-allowed disabled"{% endif %} class="px-4 py-2 bg-indigo-600 text-white rounded-md hover:bg-amber-500 transition-colors duration-200">Previous</a>
                    <span class="text-slate-900">Page {{ page }} of {{ total_pages }}</span>
                    <a {% if page < total_pages %}href="{{ url_for('papers', page=page+1, search=search, sort=sort) }}"{% else %}class="text-gray-400 cursor-not-allowed disabled"{% endif %} class="px-4 py-2 bg-indigo-600 text-white rounded-md hover:bg-amber-500 transition-colors duration-200">Next</a>
                </div>
            {% else %}
                <p class="text-slate-900">No records found.</p>
            {% endif %}
        </div>
    </div>
    <script>
        // Hide splash screen after 3 seconds
        setTimeout(() => {
            document.getElementById('splash').style.display = 'none';
        }, 3000);

        // Search and sort
        const recordsTable = document.getElementById('records-table').getElementsByTagName('tbody')[0];
        const originalRows = Array.from(recordsTable.getElementsByTagName('tr'));
        document.getElementById('search').addEventListener('input', (e) => {
            const query = e.target.value.toLowerCase();
            const filteredRows = originalRows.filter(row => {
                const year = row.cells[0].textContent.toLowerCase();
                const subject = row.cells[2].textContent.toLowerCase();
                const code = row.cells[3].textContent.toLowerCase();
                return year.includes(query) || subject.includes(query) || code.includes(query);
            });
            recordsTable.innerHTML = '';
            filteredRows.forEach(row => recordsTable.appendChild(row));
        });

        document.getElementById('sort').addEventListener('change', (e) => {
            const sortBy = e.target.value;
            const rows = Array.from(recordsTable.getElementsByTagName('tr'));
            rows.sort((a, b) => {
                let aValue, bValue;
                if (sortBy === 'year_name') {
                    aValue = a.cells[0].textContent;
                    bValue = b.cells[0].textContent;
                } else if (sortBy === 'semester_no') {
                    aValue = parseInt(a.cells[1].textContent);
                    bValue = parseInt(b.cells[1].textContent);
                } else if (sortBy === 'paper_year') {
                    aValue = parseInt(a.cells[5].textContent) || 0;
                    bValue = parseInt(a.cells[5].textContent) || 0;
                } else {
                    aValue = parseInt(a.cells[0].textContent);
                    bValue = parseInt(a.cells[0].textContent);
                }
                return aValue > bValue ? 1 : -1;
            });
            recordsTable.innerHTML = '';
            rows.forEach(row => recordsTable.appendChild(row));
        });
    </script>
</body>
</html>
"""

# HTML template for update page
UPDATE_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Update Question Paper</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body { font-family: 'Inter', sans-serif; background-color: #F9FAFB; color: #1E293B; }
        .alert { padding: 10px; margin-bottom: 20px; border-radius: 5px; }
        .alert-success { background-color: #D1FAE5; color: #065F46; }
        .alert-error { background-color: #FEE2E2; color: #B91C1C; }
        .gradient-header { background: linear-gradient(to right, #4F46E5, #06B6D4); }
        .card { transition: transform 0.2s, box-shadow 0.2s; }
        .card:hover { transform: translateY(-0.25rem); box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); }
        .spinner { display: none; border: 4px solid #E5E7EB; border-top: 4px solid #4F46E5; border-radius: 50%; width: 24px; height: 24px; animation: spin 1s linear infinite; }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        button, a { transition: all 0.2s; }
        button:hover, a:hover:not(.disabled) { transform: scale(1.05); }
    </style>
</head>
<body>
    <header class="gradient-header text-white py-4">
        <div class="container mx-auto px-4 flex justify-between items-center">
            <h1 class="text-2xl font-bold">Update Question Paper</h1>
            <div class="flex items-center space-x-4">
                <span class="text-sm">Welcome, Admin</span>
                <a href="{{ url_for('admin_logout') }}" class="bg-red-600 text-white px-3 py-1 rounded-md hover:bg-amber-500 transition-colors duration-200">Logout</a>
            </div>
        </div>
    </header>
    <div class="container mx-auto px-4 py-8">
        <!-- Flash Messages -->
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="alert {% if category == 'success' %}alert-success{% else %}alert-error{% endif %}">
                        {{ message }}
                    </div>
                {% endfor %}
            {% endif %}
        {% endwith %}

        <!-- Update Form -->
        <div class="bg-white p-6 rounded-lg shadow-sm card">
            <h2 class="text-2xl font-semibold mb-4 text-slate-900">Edit Question Paper</h2>
            <form id="update-form" method="POST" enctype="multipart/form-data" class="space-y-4">
                <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                        <label class="block text-base font-bold text-slate-900">Year Name</label>
                        <input type="text" name="year_name" value="{{ record['year_name'] }}" required maxlength="20" class="mt-1 block w-full border border-gray-300 rounded-md p-2 text-slate-900 focus:ring-indigo-500 focus:border-indigo-500">
                    </div>
                    <div>
                        <label class="block text-base font-bold text-slate-900">Semester No</label>
                        <input type="number" name="semester_no" value="{{ record['semester_no'] }}" required min="1" max="12" class="mt-1 block w-full border border-gray-300 rounded-md p-2 text-slate-900 focus:ring-indigo-500 focus:border-indigo-500">
                    </div>
                    <div>
                        <label class="block text-base font-bold text-slate-900">Subject Name</label>
                        <input type="text" name="subject_name" value="{{ record['subject_name'] }}" required maxlength="100" class="mt-1 block w-full border border-gray-300 rounded-md p-2 text-slate-900 focus:ring-indigo-500 focus:border-indigo-500">
                    </div>
                    <div>
                        <label class="block text-base font-bold text-slate-900">Subject Code</label>
                        <input type="text" name="subject_code" value="{{ record['subject_code'] }}" maxlength="20" class="mt-1 block w-full border border-gray-300 rounded-md p-2 text-slate-900 focus:ring-indigo-500 focus:border-indigo-500">
                    </div>
                    <div>
                        <label class="block text-base font-bold text-slate-900">Paper Type</label>
                        <select name="paper_type" required class="mt-1 block w-full border border-gray-300 rounded-md p-2 text-slate-900 focus:ring-indigo-500 focus:border-indigo-500">
                            <option value="Regular" {% if record['paper_type'] == 'Regular' %}selected{% endif %}>Regular</option>
                            <option value="Arrear" {% if record['paper_type'] == 'Arrear' %}selected{% endif %}>Arrear</option>
                        </select>
                    </div>
                    <div>
                        <label class="block text-base font-bold text-slate-900">Paper Year</label>
                        <input type="number" name="paper_year MIDTERM 2 Practice Questions – Spring 2025  value="{{ record['paper_year'] if record['paper_year'] else '' }}" min="1900" max="9999" class="mt-1 block w-full border border-gray-300 rounded-md p-2 text-slate-900 focus:ring-indigo-500 focus:border-indigo-500">
                    </div>
                    <div>
                        <label class="block text-base font-bold text-slate-900">Upload New File (PDF only, optional)</label>
                        <input type="file" name="file" accept=".pdf" class="mt-1 block w-full text-slate-900">
                    </div>
                </div>
                <div class="flex items-center">
                    <button type="submit" class="bg-indigo-600 text-white px-4 py-2 rounded-md hover:bg-amber-500 transition-colors duration-200 flex items-center">
                        <span>Update Paper</span>
                        <span class="spinner ml-2"></span>
                    </button>
                    <a href="{{ url_for('admin') }}" class="ml-4 text-slate-900 hover:text-amber-500 transition-colors duration-200">Cancel</a>
                </div>
            </form>
        </div>
    </div>
    <script>
        // Form validation and spinner
        document.getElementById('update-form').addEventListener('submit', (e) => {
            const yearName = document.querySelector('input[name="year_name"]').value;
            const semesterNo = document.querySelector('input[name="semester_no"]').value;
            const subjectName = document.querySelector('input[name="subject_name"]').value;
            const file = document.querySelector('input[name="file"]').files[0];
            if (yearName.length > 20 || subjectName.length > 100) {
                alert('Year Name or Subject Name exceeds maximum length.');
                e.preventDefault();
                return;
            }
            if (semesterNo < 1 || semesterNo > 12) {
                alert('Semester No must be between 1 and 12.');
                e.preventDefault();
                return;
            }
            if (file && !file.name.endsWith('.pdf')) {
                alert('Please upload a PDF file.');
                e.preventDefault();
                return;
            }
            document.querySelector('.spinner').style.display = 'inline-block';
        });
    </script>
</body>
</html>
"""

# Papers section route (root)
@app.route('/')
def papers():
    init_db()  # Ensure tables exist
    conn = get_db_connection()
    if not conn:
        flash("Database connection failed. Check SQLite database path.", "error")
        return render_template_string(PAPERS_TEMPLATE, records=[], page=1, total_pages=1, search='', sort='id')
    
    try:
        cursor = conn.cursor()
        # Track visitor
        visitor_id = request.cookies.get('visitor_id')
        if not visitor_id:
            visitor_id = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO visitor_stats (timestamp, visitor_id)
            VALUES (?, ?)
        """, (datetime.now(), visitor_id))
        conn.commit()
        
        page = int(request.args.get('page', 1))
        search = request.args.get('search', '')
        sort = request.args.get('sort', 'id')
        per_page = 10

        # Build query
        query = "SELECT id, year_name, semester_no, subject_name, subject_code, paper_type, paper_year FROM question_papers_1"
        params = []
        if search:
            query += " WHERE year_name LIKE ? OR subject_name LIKE ? OR subject_code LIKE ?"
            params.extend([f'%{search}%', f'%{search}%', f'%{search}%'])
        
        # Sorting
        if sort in ['year_name', 'semester_no', 'paper_year']:
            query += f" ORDER BY {sort}"
        else:
            query += " ORDER BY id"
        
        # Count total records
        count_query = "SELECT COUNT(*) FROM question_papers_1" + (query.split("FROM question_papers_1")[1].split("ORDER BY")[0])
        cursor.execute(count_query, params)
        total_records = cursor.fetchone()[0]
        total_pages = math.ceil(total_records / per_page)

        # Paginate
        query += " LIMIT ? OFFSET ?"
        params.extend([per_page, (page - 1) * per_page])
        cursor.execute(query, params)
        records = cursor.fetchall()
        
        response = make_response(render_template_string(PAPERS_TEMPLATE, records=records, page=page, total_pages=total_pages, search=search, sort=sort))
        if not request.cookies.get('visitor_id'):
            response.set_cookie('visitor_id', visitor_id, max_age=30*24*60*60)  # 30 days
        return response
    
    except sqlite3.Error as e:
        logging.error(f"Papers page error: {str(e)}")
        flash(f"Error fetching records: {str(e)}", "error")
    finally:
        cursor.close()
        conn.close()
    
    return render_template_string(PAPERS_TEMPLATE, records=[], page=1, total_pages=1, search=search, sort=sort)

# Admin login route
@app.route('/8688294640', methods=['GET', 'POST'])
def admin_login():
    init_db()  # Ensure tables exist
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        # Hardcoded admin credentials
        if email == 'sumanthdaripalli03@gmail.com' and password == 'sumanth#03':
            session['role'] = 'admin'
            session['username'] = 'Admin'
            logging.info("Admin logged in successfully")
            flash("Admin logged in successfully!", "success")
            return redirect(url_for('admin'))
        else:
            logging.warning(f"Failed admin login attempt for email: {email}")
            flash("Invalid email or password.", "error")
            return render_template_string(ADMIN_LOGIN_TEMPLATE)
    
    return render_template_string(ADMIN_LOGIN_TEMPLATE)

# Admin logout route
@app.route('/admin_logout')
def admin_logout():
    session.pop('role', None)
    session.pop('username', None)
    logging.info("Admin logged out")
    flash("Logged out successfully.", "success")
    return redirect(url_for('papers'))

# Admin route
@app.route('/admin')
@admin_required
def admin():
    init_db()  # Ensure tables exist
    conn = get_db_connection()
    if not conn:
        flash("Database connection failed. Check SQLite database path.", "error")
        return render_template_string(ADMIN_TEMPLATE, records=[], page=1, total_pages=1, search='', sort='id', visitor_stats={'total_visits': 0, 'unique_visitors': 0, 'daily_visits': []})
    
    try:
        cursor = conn.cursor()
        page = int(request.args.get('page', 1))
        search = request.args.get('search', '')
        sort = request.args.get('sort', 'id')
        per_page = 10

        # Build query
        query = "SELECT id, year_name, semester_no, subject_name, subject_code, paper_type, paper_year FROM question_papers_1"
        params = []
        if search:
            query += " WHERE year_name LIKE ? OR subject_name LIKE ? OR subject_code LIKE ?"
            params.extend([f'%{search}%', f'%{search}%', f'%{search}%'])
        
        # Sorting
        if sort in ['year_name', 'semester_no', 'paper_year']:
            query += f" ORDER BY {sort}"
        else:
            query += " ORDER BY id"
        
        # Count total records
        count_query = "SELECT COUNT(*) FROM question_papers_1" + (query.split("FROM question_papers_1")[1].split("ORDER BY")[0])
        cursor.execute(count_query, params)
        total_records = cursor.fetchone()[0]
        total_pages = math.ceil(total_records / per_page)

        # Paginate
        query += " LIMIT ? OFFSET ?"
        params.extend([per_page, (page - 1) * per_page])
        cursor.execute(query, params)
        records = cursor.fetchall()
        
        # Get visitor stats
        visitor_stats = get_visitor_stats()
        
        return render_template_string(ADMIN_TEMPLATE, records=records, page=page, total_pages=total_pages, search=search, sort=sort, visitor_stats=visitor_stats)
    
    except sqlite3.Error as e:
        logging.error(f"Admin page error: {str(e)}")
        flash(f"Error fetching records: {str(e)}", "error")
    finally:
        cursor.close()
        conn.close()
    
    return render_template_string(ADMIN_TEMPLATE, records=[], page=1, total_pages=1, search=search, sort=sort, visitor_stats={'total_visits': 0, 'unique_visitors': 0, 'daily_visits': []})

@app.route('/add', methods=['POST'])
@admin_required
def add():
    conn = get_db_connection()
    if not conn:
        flash("Database connection failed. Check SQLite database path.", "error")
        return redirect(url_for('admin'))
    
    try:
        cursor = conn.cursor()
        year_name = request.form['year_name']
        semester_no = request.form['semester_no']
        subject_name = request.form['subject_name']
        subject_code = request.form['subject_code']
        paper_type = request.form['paper_type']
        paper_year = request.form['paper_year'] or None
        file = request.files['file']
        
        # Validate inputs
        if not (year_name and semester_no and subject_name and paper_type and file):
            flash("All required fields must be filled.", "error")
            return redirect(url_for('admin'))
        if len(year_name) > 20 or len(subject_name) > 100 or (subject_code and len(subject_code) > 20):
            flash("Input exceeds maximum length.", "error")
            return redirect(url_for('admin'))
        if not (1 <= int(semester_no) <= 12):
            flash("Semester No must be between 1 and 12.", "error")
            return redirect(url_for('admin'))
        if paper_type not in ['Regular', 'Arrear']:
            flash("Invalid paper type.", "error")
            return redirect(url_for('admin'))
        if not allowed_file(file.filename):
            flash("Only PDF files are allowed.", "error")
            return redirect(url_for('admin'))
        
        # Read file
        file_data = file.read()
        cursor.execute("""
            INSERT INTO question_papers_1 (year_name, semester_no, subject_name, subject_code, paper_type, paper_year, file_data)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (year_name, semester_no, subject_name, subject_code, paper_type, paper_year, file_data))
        conn.commit()
        logging.info(f"Added question paper: {subject_name} ({year_name})")
        flash("Question paper added successfully!", "success")
    
    except sqlite3.Error as e:
        logging.error(f"Add error: {str(e)}")
        flash(f"Error adding question paper: {str(e)}", "error")
    finally:
        cursor.close()
        conn.close()
    
    return redirect(url_for('admin'))

@app.route('/update/<int:id>', methods=['GET', 'POST'])
@admin_required
def update(id):
    conn = get_db_connection()
    if not conn:
        flash("Database connection failed. Check SQLite database path.", "error")
        return redirect(url_for('admin'))
    
    try:
        cursor = conn.cursor()
        if request.method == 'POST':
            year_name = request.form['year_name']
            semester_no = request.form['semester_no']
            subject_name = request.form['subject_name']
            subject_code = request.form['subject_code']
            paper_type = request.form['paper_type']
            paper_year = request.form['paper_year'] or None
            file = request.files['file']
            
            # Validate inputs
            if not (year_name and semester_no and subject_name and paper_type):
                flash("All required fields must be filled.", "error")
                return redirect(url_for('update', id=id))
            if len(year_name) > 20 or len(subject_name) > 100 or (subject_code and len(subject_code) > 20):
                flash("Input exceeds maximum length.", "error")
                return redirect(url_for('update', id=id))
            if not (1 <= int(semester_no) <= 12):
                flash("Semester No must be between 1 and 12.", "error")
                return redirect(url_for('update', id=id))
            if paper_type not in ['Regular', 'Arrear']:
                flash("Invalid paper type.", "error")
                return redirect(url_for('update', id=id))
            if file and not allowed_file(file.filename):
                flash("Only PDF files are allowed.", "error")
                return redirect(url_for('update', id=id))
            
            if file:
                file_data = file.read()
                cursor.execute("""
                    UPDATE question_papers_1
                    SET year_name=?, semester_no=?, subject_name=?, subject_code=?, paper_type=?, paper_year=?, file_data=?
                    WHERE id=?
                """, (year_name, semester_no, subject_name, subject_code, paper_type, paper_year, file_data, id))
            else:
                cursor.execute("""
                    UPDATE question_papers_1
                    SET year_name=?, semester_no=?, subject_name=?, subject_code=?, paper_type=?, paper_year=?
                    WHERE id=?
                """, (year_name, semester_no, subject_name, subject_code, paper_type, paper_year, id))
            conn.commit()
            logging.info(f"Updated question paper ID: {id}")
            flash("Question paper updated successfully!", "success")
            return redirect(url_for('admin'))
        else:
            cursor.execute("SELECT id, year_name, semester_no, subject_name, subject_code, paper_type, paper_year FROM question_papers_1 WHERE id=?", (id,))
            record = cursor.fetchone()
            if not record:
                flash("Question paper not found.", "error")
                return redirect(url_for('admin'))
            return render_template_string(UPDATE_TEMPLATE, record=record)
    
    except sqlite3.Error as e:
        logging.error(f"Update error: {str(e)}")
        flash(f"Error updating question paper: {str(e)}", "error")
    finally:
        cursor.close()
        conn.close()
    
    return redirect(url_for('admin'))

@app.route('/delete/<int:id>')
@admin_required
def delete(id):
    conn = get_db_connection()
    if not conn:
        flash("Database connection failed. Check SQLite database path.", "error")
        return redirect(url_for('admin'))
    
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM question_papers_1 WHERE id=?", (id,))
        conn.commit()
        logging.info(f"Deleted question paper ID: {id}")
        flash("Question paper deleted successfully!", "success")
    
    except sqlite3.Error as e:
        logging.error(f"Delete error: {str(e)}")
        flash(f"Error deleting question paper: {str(e)}", "error")
    finally:
        cursor.close()
        conn.close()
    
    return redirect(url_for('admin'))

@app.route('/download/<int:id>')
def download(id):
    conn = get_db_connection()
    if not conn:
        flash("Database connection failed. Check SQLite database path.", "error")
        return redirect(url_for('papers'))
    
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT file_data, subject_name, year_name FROM question_papers_1 WHERE id=?", (id,))
        record = cursor.fetchone()
        if not record:
            flash("Question paper not found.", "error")
            return redirect(url_for('papers'))
        
        file_data, subject_name, year_name = record['file_data'], record['subject_name'], record['year_name']
        filename = secure_filename(f"{subject_name}_{year_name}.pdf")
        response = make_response(file_data)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename={filename}'
        logging.info(f"Downloaded question paper ID: {id}")
        return response
    
    except sqlite3.Error as e:
        logging.error(f"Download error: {str(e)}")
        flash(f"Error downloading question paper: {str(e)}", "error")
    finally:
        cursor.close()
        conn.close()
    
    return redirect(url_for('papers'))

if __name__ == '__main__':
    init_db()  # Initialize database on startup
    app.run(debug=True, host='0.0.0.0', port=int(os.getenv('PORT', 5000)))
