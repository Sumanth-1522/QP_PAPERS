from flask import Flask, render_template_string, request, redirect, url_for, flash, make_response, session, jsonify
from flask_bcrypt import Bcrypt
import sqlite3
from werkzeug.utils import secure_filename
import io
import math
import logging
import os

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
        logging.debug("Creating users table if not exists")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL
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

# Check if user is logged in
def login_required(f):
    def wrap(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please log in to access this page.", "error")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    wrap.__name__ = f.__name__
    return wrap

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
        cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name IN ('question_papers_1', 'users')")
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

# List users endpoint
@app.route('/list_users')
def list_users():
    conn = get_db_connection()
    if not conn:
        return jsonify({
            "status": "error",
            "message": "Failed to connect to SQLite: Check logs for details."
        }), 500
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT username FROM users")
        users = [row['username'] for row in cursor.fetchall()]
        return jsonify({
            "status": "success",
            "users": users,
            "message": f"Found {len(users)} users in '{DATABASE}' database."
        })
    except sqlite3.Error as e:
        return jsonify({
            "status": "error",
            "message": f"Failed to query users: {str(e)}"
        }), 500
    finally:
        cursor.close()
        conn.close()

# HTML template for login page
LOGIN_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Login</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body { font-family: 'Inter', sans-serif; transition: background-color 0.3s, color 0.3s; }
        .dark { background-color: #6b21a8; color: #f3f4f6; }
        .light { background-color: #f3e8ff; color: #111827; }
        .dark .bg-gray-100 { background-color: #4c1d95; }
        .dark .bg-white { background-color: #4c1d95; }
        .dark .text-gray-900 { color: #f3f4f6; }
        .dark .text-gray-700 { color: #f3f4f6; }
        .dark .text-gray-600 { color: #d1d5db; }
        .dark .border-gray-300 { border-color: #6b7280; }
        .dark .bg-red-100 { background-color: #991b1b; }
        .dark .bg-green-100 { background-color: #166534; }
        .alert { padding: 10px; margin-bottom: 20px; border-radius: 5px; }
        .alert-error { background-color: #fef2f2; color: #991b1b; }
        .alert-success { background-color: #f0fdf4; color: #166534; }
        .gradient-header { background: linear-gradient(to right, #6b21a8, #2563eb); }
        .card { transition: transform 0.2s; }
        .card:hover { transform: translateY(-5px); }
    </style>
</head>
<body class="dark">
    <header class="gradient-header text-white py-4">
        <div class="container mx-auto px-4">
            <h1 class="text-2xl font-bold">Login</h1>
        </div>
    </header>
    <div class="container mx-auto px-4 py-8 flex justify-center">
        <div class="bg-white p-6 rounded-lg shadow-md card w-full max-w-md">
            <h2 class="text-2xl font-semibold mb-4 text-gray-900">Sign In</h2>
            <!-- Flash Messages -->
            {% with messages = get_flashed_messages(with_categories=true) %}
                {% if messages %}
                    {% for category, message in messages %}
                        <div class="alert alert-{{ category }}">{{ message }}</div>
                    {% endfor %}
                {% endif %}
            {% endwith %}
            <form method="POST" action="{{ url_for('login') }}" class="space-y-4">
                <div>
                    <label class="block text-base font-bold text-gray-700">Username</label>
                    <input type="text" name="username" required maxlength="50" class="mt-1 block w-full border border-gray-300 rounded-md p-2 text-gray-900">
                </div>
                <div>
                    <label class="block text-base font-bold text-gray-700">Password</label>
                    <input type="password" name="password" required class="mt-1 block w-full border border-gray-300 rounded-md p-2 text-gray-900">
                </div>
                <button type="submit" class="bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700 w-full">Login</button>
            </form>
            <p class="mt-4 text-center text-gray-600">
                Don't have an account? <a href="{{ url_for('signup') }}" class="text-blue-600 hover:underline">Sign Up</a>
            </p>
        </div>
    </div>
    <script>
        // Theme toggle
        if (localStorage.getItem('theme') === 'light') {
            document.body.classList.remove('dark');
            document.body.classList.add('light');
        } else {
            document.body.classList.add('dark');
            localStorage.setItem('theme', 'dark');
        }
    </script>
</body>
</html>
"""

# HTML template for signup page
SIGNUP_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sign Up</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body { font-family: 'Inter', sans-serif; transition: background-color 0.3s, color 0.3s; }
        .dark { background-color: #6b21a8; color: #f3f4f6; }
        .light { background-color: #f3e8ff; color: #111827; }
        .dark .bg-gray-100 { background-color: #4c1d95; }
        .dark .bg-white { background-color: #4c1d95; }
        .dark .text-gray-900 { color: #f3f4f6; }
        .dark .text-gray-700 { color: #f3f4f6; }
        .dark .text-gray-600 { color: #d1d5db; }
        .dark .border-gray-300 { border-color: #6b7280; }
        .dark .bg-red-100 { background-color: #991b1b; }
        .dark .bg-green-100 { background-color: #166534; }
        .alert { padding: 10px; margin-bottom: 20px; border-radius: 5px; }
        .alert-error { background-color: #fef2f2; color: #991b1b; }
        .alert-success { background-color: #f0fdf4; color: #166534; }
        .gradient-header { background: linear-gradient(to right, #6b21a8, #2563eb); }
        .card { transition: transform 0.2s; }
        .card:hover { transform: translateY(-5px); }
    </style>
</head>
<body class="dark">
    <header class="gradient-header text-white py-4">
        <div class="container mx-auto px-4">
            <h1 class="text-2xl font-bold">Sign Up</h1>
        </div>
    </header>
    <div class="container mx-auto px-4 py-8 flex justify-center">
        <div class="bg-white p-6 rounded-lg shadow-md card w-full max-w-md">
            <h2 class="text-2xl font-semibold mb-4 text-gray-900">Create Account</h2>
            <!-- Flash Messages -->
            {% with messages = get_flashed_messages(with_categories=true) %}
                {% if messages %}
                    {% for category, message in messages %}
                        <div class="alert alert-{{ category }}">{{ message }}</div>
                    {% endfor %}
                {% endif %}
            {% endwith %}
            <form method="POST" action="{{ url_for('signup') }}" class="space-y-4">
                <div>
                    <label class="block text-base font-bold text-gray-700">Username</label>
                    <input type="text" name="username" required maxlength="50" class="mt-1 block w-full border border-gray-300 rounded-md p-2 text-gray-900">
                </div>
                <div>
                    <label class="block text-base font-bold text-gray-700">Password</label>
                    <input type="password" name="password" required class="mt-1 block w-full border border-gray-300 rounded-md p-2 text-gray-900">
                </div>
                <button type="submit" class="bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700 w-full">Sign Up</button>
            </form>
            <p class="mt-4 text-center text-gray-600">
                Already have an account? <a href="{{ url_for('login') }}" class="text-blue-600 hover:underline">Login</a>
            </p>
        </div>
    </div>
    <script>
        // Theme toggle
        if (localStorage.getItem('theme') === 'light') {
            document.body.classList.remove('dark');
            document.body.classList.add('light');
        } else {
            document.body.classList.add('dark');
            localStorage.setItem('theme', 'dark');
        }
    </script>
</body>
</html>
"""

# HTML template for index page
INDEX_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Question Paper Management</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body { font-family: 'Inter', sans-serif; transition: background-color 0.3s, color 0.3s; }
        .dark { background-color: #6b21a8; color: #f3f4f6; }
        .light { background-color: #f3e8ff; color: #111827; }
        .dark .bg-gray-100 { background-color: #4c1d95; }
        .dark .bg-white { background-color: #4c1d95; }
        .dark .bg-gray-200 { background-color: #6b7280; }
        .dark .text-gray-900 { color: #f3f4f6; }
        .dark .text-gray-700 { color: #f3f4f6; }
        .dark .text-gray-600 { color: #d1d5db; }
        .dark .border-gray-300 { border-color: #6b7280; }
        .dark .bg-red-100 { background-color: #991b1b; }
        .dark .bg-green-100 { background-color: #166534; }
        .alert { padding: 10px; margin-bottom: 20px; border-radius: 5px; }
        .alert-success { background-color: #f0fdf4; color: #166534; }
        .alert-error { background-color: #fef2f2; color: #991b1b; }
        .gradient-header { background: linear-gradient(to right, #6b21a8, #2563eb); }
        .card { transition: transform 0.2s; }
        .card:hover { transform: translateY(-5px); }
        .spinner { display: none; border: 4px solid #f3f3f3; border-top: 4px solid #2563eb; border-radius: 50%; width: 24px; height: 24px; animation: spin 1s linear infinite; }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
    </style>
</head>
<body class="dark">
    <header class="gradient-header text-white py-4">
        <div class="container mx-auto px-4 flex justify-between items-center">
            <h1 class="text-2xl font-bold">Question Paper Management</h1>
            <div class="flex items-center space-x-4">
                <span class="text-sm">Welcome, {{ session['username'] }}</span>
                <button id="theme-toggle" class="bg-white text-gray-900 px-3 py-1 rounded-md hover:bg-gray-200">Toggle Theme</button>
                <a href="{{ url_for('logout') }}" class="bg-red-600 text-white px-3 py-1 rounded-md hover:bg-red-700">Logout</a>
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

        <!-- Search and Sort -->
        <div class="bg-white p-6 rounded-lg shadow-md mb-8 card">
            <div class="flex flex-col md:flex-row gap-4">
                <div class="flex-1">
                    <label class="block text-base font-bold text-gray-700">Search</label>
                    <input type="text" id="search" class="mt-1 block w-full border border-gray-300 rounded-md p-2 text-gray-900" placeholder="Search by Year, Subject, or Code">
                </div>
                <div>
                    <label class="block text-base font-bold text-gray-700">Sort By</label>
                    <select id="sort" class="mt-1 block w-full border border-gray-300 rounded-md p-2 text-gray-900">
                        <option value="id">ID</option>
                        <option value="year_name">Year</option>
                        <option value="semester_no">Semester</option>
                        <option value="paper_year">Paper Year</option>
                    </select>
                </div>
            </div>
        </div>

        <!-- Add Form -->
        <div class="bg-white p-6 rounded-lg shadow-md mb-8 card">
            <h2 class="text-2xl font-semibold mb-4 text-gray-900">Add New Question Paper</h2>
            <form id="add-form" method="POST" enctype="multipart/form-data" action="{{ url_for('add') }}" class="space-y-4">
                <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                        <label class="block text-base font-bold text-gray-700">Year Name</label>
                        <input type="text" name="year_name" required maxlength="20" class="mt-1 block w-full border border-gray-300 rounded-md p-2 text-gray-900">
                    </div>
                    <div>
                        <label class="block text-base font-bold text-gray-700">Semester No</label>
                        <input type="number" name="semester_no" required min="1" max="12" class="mt-1 block w-full border border-gray-300 rounded-md p-2 text-gray-900">
                    </div>
                    <div>
                        <label class="block text-base font-bold text-gray-700">Subject Name</label>
                        <input type="text" name="subject_name" required maxlength="100" class="mt-1 block w-full border border-gray-300 rounded-md p-2 text-gray-900">
                    </div>
                    <div>
                        <label class="block text-base font-bold text-gray-700">Subject Code</label>
                        <input type="text" name="subject_code" maxlength="20" class="mt-1 block w-full border border-gray-300 rounded-md p-2 text-gray-900">
                    </div>
                    <div>
                        <label class="block text-base font-bold text-gray-700">Paper Type</label>
                        <select name="paper_type" required class="mt-1 block w-full border border-gray-300 rounded-md p-2 text-gray-900">
                            <option value="Regular">Regular</option>
                            <option value="Arrear">Arrear</option>
                        </select>
                    </div>
                    <div>
                        <label class="block text-base font-bold text-gray-700">Paper Year</label>
                        <input type="number" name="paper_year" min="1900" max="9999" class="mt-1 block w-full border border-gray-300 rounded-md p-2 text-gray-900">
                    </div>
                    <div>
                        <label class="block text-base font-bold text-gray-700">Upload File (PDF only)</label>
                        <input type="file" name="file" accept=".pdf" required class="mt-1 block w-full text-gray-900">
                    </div>
                </div>
                <button type="submit" class="bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700 flex items-center">
                    <span>Add Paper</span>
                    <span class="spinner ml-2"></span>
                </button>
            </form>
        </div>

        <!-- Records Table -->
        <div class="bg-white p-6 rounded-lg shadow-md card">
            <h2 class="text-2xl font-semibold mb-4 text-gray-900">Question Papers</h2>
            {% if records %}
                <div class="overflow-x-auto">
                    <table class="min-w-full border-collapse" id="records-table">
                        <thead>
                            <tr class="bg-gray-200">
                                <th class="border px-4 py-2">Year</th>
                                <th class="border px-4 py-2">Semester</th>
                                <th class="border px-4 py-2">Subject</th>
                                <th class="border px-4 py-2">Code</th>
                                <th class="border px-4 py-2">Type</th>
                                <th class="border px-4 py-2">Paper Year</th>
                                <th class="border px-4 py-2">File</th>
                                <th class="border px-4 py-2">Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            {% for record in records %}
                                <tr>
                                    <td class="border px-4 py-2">{{ record['year_name'] }}</td>
                                    <td class="border px-4 py-2">{{ record['semester_no'] }}</td>
                                    <td class="border px-4 py-2">{{ record['subject_name'] }}</td>
                                    <td class="border px-4 py-2">{{ record['subject_code'] }}</td>
                                    <td class="border px-4 py-2">{{ record['paper_type'] }}</td>
                                    <td class="border px-4 py-2">{{ record['paper_year'] }}</td>
                                    <td class="border px-4 py-2">
                                        <a href="{{ url_for('download', id=record['id']) }}" class="text-blue-600 hover:underline">Download</a>
                                    </td>
                                    <td class="border px-4 py-2">
                                        <a href="{{ url_for('update', id=record['id']) }}" class="text-yellow-600 hover:underline mr-2">Edit</a>
                                        <a href="{{ url_for('delete', id=record['id']) }}" onclick="return confirm('Are you sure you want to delete this record?')" class="text-red-600 hover:underline">Delete</a>
                                    </td>
                                </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
                <!-- Pagination -->
                <div class="mt-4 flex justify-between">
                    <a {% if page > 1 %}href="{{ url_for('index', page=page-1, search=search, sort=sort) }}"{% else %}class="text-gray-400 cursor-not-allowed"{% endif %} class="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700">Previous</a>
                    <span>Page {{ page }} of {{ total_pages }}</span>
                    <a {% if page < total_pages %}href="{{ url_for('index', page=page+1, search=search, sort=sort) }}"{% else %}class="text-gray-400 cursor-not-allowed"{% endif %} class="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700">Next</a>
                </div>
            {% else %}
                <p class="text-gray-600">No records found.</p>
            {% endif %}
        </div>
    </div>
    <script>
        // Theme toggle
        document.getElementById('theme-toggle').addEventListener('click', () => {
            if (document.body.classList.contains('dark')) {
                document.body.classList.remove('dark');
                document.body.classList.add('light');
                localStorage.setItem('theme', 'light');
            } else {
                document.body.classList.remove('light');
                document.body.classList.add('dark');
                localStorage.setItem('theme', 'dark');
            }
        });
        if (localStorage.getItem('theme') === 'light') {
            document.body.classList.remove('dark');
            document.body.classList.add('light');
        } else {
            document.body.classList.add('dark');
            localStorage.setItem('theme', 'dark');
        }

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
                    aValue = parseInt(a.cells[0].textContent); // ID
                    bValue = parseInt(b.cells[0].textContent);
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
        body { font-family: 'Inter', sans-serif; transition: background-color 0.3s, color 0.3s; }
        .dark { background-color: #6b21a8; color: #f3f4f6; }
        .light { background-color: #f3e8ff; color: #111827; }
        .dark .bg-gray-100 { background-color: #4c1d95; }
        .dark .bg-white { background-color: #4c1d95; }
        .dark .text-gray-900 { color: #f3f4f6; }
        .dark .text-gray-700 { color: #f3f4f6; }
        .dark .text-gray-600 { color: #d1d5db; }
        .dark .border-gray-300 { border-color: #6b7280; }
        .dark .bg-red-100 { background-color: #991b1b; }
        .dark .bg-green-100 { background-color: #166534; }
        .alert { padding: 10px; margin-bottom: 20px; border-radius: 5px; }
        .alert-success { background-color: #f0fdf4; color: #166534; }
        .alert-error { background-color: #fef2f2; color: #991b1b; }
        .gradient-header { background: linear-gradient(to right, #6b21a8, #2563eb); }
        .card { transition: transform 0.2s; }
        .card:hover { transform: translateY(-5px); }
        .spinner { display: none; border: 4px solid #f3f3f3; border-top: 4px solid #2563eb; border-radius: 50%; width: 24px; height: 24px; animation: spin 1s linear infinite; }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
    </style>
</head>
<body class="dark">
    <header class="gradient-header text-white py-4">
        <div class="container mx-auto px-4 flex justify-between items-center">
            <h1 class="text-2xl font-bold">Update Question Paper</h1>
            <div class="flex items-center space-x-4">
                <span class="text-sm">Welcome, {{ session['username'] }}</span>
                <button id="theme-toggle" class="bg-white text-gray-900 px-3 py-1 rounded-md hover:bg-gray-200">Toggle Theme</button>
                <a href="{{ url_for('logout') }}" class="bg-red-600 text-white px-3 py-1 rounded-md hover:bg-red-700">Logout</a>
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
        <div class="bg-white p-6 rounded-lg shadow-md card">
            <h2 class="text-2xl font-semibold mb-4 text-gray-900">Edit Question Paper</h2>
            <form id="update-form" method="POST" enctype="multipart/form-data" class="space-y-4">
                <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                        <label class="block text-base font-bold text-gray-700">Year Name</label>
                        <input type="text" name="year_name" value="{{ record['year_name'] }}" required maxlength="20" class="mt-1 block w-full border border-gray-300 rounded-md p-2 text-gray-900">
                    </div>
                    <div>
                        <label class="block text-base font-bold text-gray-700">Semester No</label>
                        <input type="number" name="semester_no" value="{{ record['semester_no'] }}" required min="1" max="12" class="mt-1 block w-full border border-gray-300 rounded-md p-2 text-gray-900">
                    </div>
                    <div>
                        <label class="block text-base font-bold text-gray-700">Subject Name</label>
                        <input type="text" name="subject_name" value="{{ record['subject_name'] }}" required maxlength="100" class="mt-1 block w-full border border-gray-300 rounded-md p-2 text-gray-900">
                    </div>
                    <div>
                        <label class="block text-base font-bold text-gray-700">Subject Code</label>
                        <input type="text" name="subject_code" value="{{ record['subject_code'] }}" maxlength="20" class="mt-1 block w-full border border-gray-300 rounded-md p-2 text-gray-900">
                    </div>
                    <div>
                        <label class="block text-base font-bold text-gray-700">Paper Type</label>
                        <select name="paper_type" required class="mt-1 block w-full border border-gray-300 rounded-md p-2 text-gray-900">
                            <option value="Regular" {% if record['paper_type'] == 'Regular' %}selected{% endif %}>Regular</option>
                            <option value="Arrear" {% if record['paper_type'] == 'Arrear' %}selected{% endif %}>Arrear</option>
                        </select>
                    </div>
                    <div>
                        <label class="block text-base font-bold text-gray-700">Paper Year</label>
                        <input type="number" name="paper_year" value="{{ record['paper_year'] if record['paper_year'] else '' }}" min="1900" max="9999" class="mt-1 block w-full border border-gray-300 rounded-md p-2 text-gray-900">
                    </div>
                    <div>
                        <label class="block text-base font-bold text-gray-700">Upload New File (PDF only, optional)</label>
                        <input type="file" name="file" accept=".pdf" class="mt-1 block w-full text-gray-900">
                    </div>
                </div>
                <div class="flex items-center">
                    <button type="submit" class="bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700 flex items-center">
                        <span>Update Paper</span>
                        <span class="spinner ml-2"></span>
                    </button>
                    <a href="{{ url_for('index') }}" class="ml-4 text-gray-600 hover:underline">Cancel</a>
                </div>
            </form>
        </div>
    </div>
    <script>
        // Theme toggle
        document.getElementById('theme-toggle').addEventListener('click', () => {
            if (document.body.classList.contains('dark')) {
                document.body.classList.remove('dark');
                document.body.classList.add('light');
                localStorage.setItem('theme', 'light');
            } else {
                document.body.classList.remove('light');
                document.body.classList.add('dark');
                localStorage.setItem('theme', 'dark');
            }
        });
        if (localStorage.getItem('theme') === 'light') {
            document.body.classList.remove('dark');
            document.body.classList.add('light');
        } else {
            document.body.classList.add('dark');
            localStorage.setItem('theme', 'dark');
        }

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

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    init_db()  # Ensure tables exist
    conn = get_db_connection()
    if not conn:
        flash("Database connection failed. Check SQLite database path.", "error")
        return render_template_string(SIGNUP_TEMPLATE)
    
    try:
        cursor = conn.cursor()
        if request.method == 'POST':
            username = request.form['username']
            password = request.form['password']
            
            # Validate inputs
            if not (username and password):
                flash("Username and password are required.", "error")
                return render_template_string(SIGNUP_TEMPLATE)
            if len(username) > 50:
                flash("Username exceeds maximum length.", "error")
                return render_template_string(SIGNUP_TEMPLATE)
            
            # Check if username exists
            cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
            if cursor.fetchone():
                flash("Username already exists.", "error")
                return render_template_string(SIGNUP_TEMPLATE)
            
            # Hash password and insert user
            hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
            cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, hashed_password))
            conn.commit()
            logging.info(f"User {username} signed up successfully")
            flash("Account created successfully! Please log in.", "success")
            return redirect(url_for('login'))
        
    except sqlite3.Error as e:
        logging.error(f"Signup error: {str(e)}")
        flash(f"Error creating account: {str(e)}", "error")
    finally:
        cursor.close()
        conn.close()
    
    return render_template_string(SIGNUP_TEMPLATE)

@app.route('/login', methods=['GET', 'POST'])
def login():
    init_db()  # Ensure tables exist
    conn = get_db_connection()
    if not conn:
        flash("Database connection failed. Check SQLite database path.", "error")
        return render_template_string(LOGIN_TEMPLATE)
    
    try:
        cursor = conn.cursor()
        if request.method == 'POST':
            username = request.form['username']
            password = request.form['password']
            
            # Validate inputs
            if not (username and password):
                flash("Username and password are required.", "error")
                return render_template_string(LOGIN_TEMPLATE)
            
            # Check credentials
            cursor.execute("SELECT id, username, password FROM users WHERE username = ?", (username,))
            user = cursor.fetchone()
            if user and bcrypt.check_password_hash(user['password'], password):
                session['user_id'] = user['id']
                session['username'] = user['username']
                logging.info(f"User {username} logged in successfully")
                flash("Logged in successfully!", "success")
                return redirect(url_for('index'))
            else:
                logging.warning(f"Failed login attempt for username: {username}")
                flash("Invalid username or password.", "error")
                return render_template_string(LOGIN_TEMPLATE)
        
    except sqlite3.Error as e:
        logging.error(f"Login error: {str(e)}")
        flash(f"Error logging in: {str(e)}", "error")
    finally:
        cursor.close()
        conn.close()
    
    return render_template_string(LOGIN_TEMPLATE)

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('username', None)
    logging.info("User logged out")
    flash("Logged out successfully.", "success")
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    init_db()  # Ensure tables exist
    conn = get_db_connection()
    if not conn:
        flash("Database connection failed. Check SQLite database path.", "error")
        return render_template_string(INDEX_TEMPLATE, records=[], page=1, total_pages=1, search='', sort='id')
    
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
        
        return render_template_string(INDEX_TEMPLATE, records=records, page=page, total_pages=total_pages, search=search, sort=sort)
    
    except sqlite3.Error as e:
        logging.error(f"Index error: {str(e)}")
        flash(f"Error fetching records: {str(e)}", "error")
    finally:
        cursor.close()
        conn.close()
    
    return render_template_string(INDEX_TEMPLATE, records=[], page=1, total_pages=1, search=search, sort=sort)

@app.route('/add', methods=['POST'])
@login_required
def add():
    conn = get_db_connection()
    if not conn:
        flash("Database connection failed. Check SQLite database path.", "error")
        return redirect(url_for('index'))
    
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
            return redirect(url_for('index'))
        if len(year_name) > 20 or len(subject_name) > 100 or (subject_code and len(subject_code) > 20):
            flash("Input exceeds maximum length.", "error")
            return redirect(url_for('index'))
        if not (1 <= int(semester_no) <= 12):
            flash("Semester No must be between 1 and 12.", "error")
            return redirect(url_for('index'))
        if paper_type not in ['Regular', 'Arrear']:
            flash("Invalid paper type.", "error")
            return redirect(url_for('index'))
        if not allowed_file(file.filename):
            flash("Only PDF files are allowed.", "error")
            return redirect(url_for('index'))
        
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
    
    return redirect(url_for('index'))

@app.route('/update/<int:id>', methods=['GET', 'POST'])
@login_required
def update(id):
    conn = get_db_connection()
    if not conn:
        flash("Database connection failed. Check SQLite database path.", "error")
        return redirect(url_for('index'))
    
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
            return redirect(url_for('index'))
        else:
            cursor.execute("SELECT id, year_name, semester_no, subject_name, subject_code, paper_type, paper_year FROM question_papers_1 WHERE id=?", (id,))
            record = cursor.fetchone()
            if not record:
                flash("Question paper not found.", "error")
                return redirect(url_for('index'))
            return render_template_string(UPDATE_TEMPLATE, record=record)
    
    except sqlite3.Error as e:
        logging.error(f"Update error: {str(e)}")
        flash(f"Error updating question paper: {str(e)}", "error")
    finally:
        cursor.close()
        conn.close()
    
    return redirect(url_for('index'))

@app.route('/delete/<int:id>')
@login_required
def delete(id):
    conn = get_db_connection()
    if not conn:
        flash("Database connection failed. Check SQLite database path.", "error")
        return redirect(url_for('index'))
    
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
    
    return redirect(url_for('index'))

@app.route('/download/<int:id>')
@login_required
def download(id):
    conn = get_db_connection()
    if not conn:
        flash("Database connection failed. Check SQLite database path.", "error")
        return redirect(url_for('index'))
    
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT file_data, subject_name, year_name FROM question_papers_1 WHERE id=?", (id,))
        record = cursor.fetchone()
        if not record:
            flash("Question paper not found.", "error")
            return redirect(url_for('index'))
        
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
    
    return redirect(url_for('index'))

if __name__ == '__main__':
    init_db()  # Initialize database on startup
    app.run(debug=True, host='0.0.0.0', port=int(os.getenv('PORT', 5000)))