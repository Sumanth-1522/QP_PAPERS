# **Q_papers** 📚

**Q_papers** is a Flask-based web application designed for **Dhanalakshmi Srinivasan University** to manage and distribute academic question papers. Users can search, sort, and download PDF question papers, while administrators can perform CRUD operations (Create, Read, Update, Delete) and view visitor statistics.

The app features:
- A modern UI using **Tailwind CSS**
- A splash screen with branding
- A secure **admin panel**
- A **visitor tracking system**

🔗 **Live App:** [https://qp-papers-3.onrender.com](https://qp-papers-3.onrender.com)

---

## **🚀 Features**

### **👨‍🎓 User Interface**
- 🎬 Splash screen with animated gradient and university branding
- 🔍 Search papers by year, subject, or code
- 📊 Sort papers by ID, year, semester, or paper year
- 📥 Download question papers in PDF format

### **🔐 Admin Panel**
- Admin login with restricted access
- Add, update, or delete question papers (PDF uploads)
- Visitor statistics:
  - Total visits to papers section
  - Unique visitors (via cookies)
  - Daily visits (last 7 days) using Chart.js

### **⚙️ Technical Stack**
- **Backend:** Flask (Python)
- **Database:** SQLite
- **Frontend:** Tailwind CSS
- **Charts:** Chart.js
- Secure cookie-based visitor tracking (30-day expiration)
- Client-side form validation
- Logging for debugging

---

## **📦 Prerequisites**

- Python 3.8+
- Git
- SQLite (included with Python)
- Modern browser (Chrome, Firefox, Edge)

---

## **🧰 Setup Instructions**

### **1. Clone the Repository**
```bash
git clone https://github.com/<your-username>/qp-papers.git
cd qp-papers
2. Create a Virtual Environment
bash
Copy
Edit
python -m venv venv
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate
3. Install Dependencies
bash
Copy
Edit
pip install -r requirements.txt
4. Initialize the Database
The app will automatically create the SQLite database (qpaper.db) and required tables on first run.

bash
Copy
Edit
python app.py
▶️ Running the App Locally
bash
Copy
Edit
python app.py
App will run at: http://localhost:5000

Papers section: http://localhost:5000/

📂 Usage
Papers Section (/)
View, search, and sort papers

Click "Download" to get PDFs

Each visit sets a visitor_id cookie (30-day expiry)

Admin Panel
Log in securely

Upload, edit, or delete papers

View:

Total Visits

Unique Visitors

Daily chart of last 7 days

🧪 Testing Visitor Stats
Open the app in different browsers or incognito tabs

Access the admin panel to see updated stats

🌍 Deployment on Render.com
1. Create a Render Account
Sign up at https://render.com

2. Create a New Web Service
Click "New" > "Web Service"

Connect your GitHub repo (qp-papers)

3. Configure Service
Build Command: pip install -r requirements.txt

Start Command: gunicorn app:app

Environment: Python 3

Instance Type: Free or paid

Add an environment variable:

Key: FLASK_SECRET_KEY

Value: Secure random string (e.g. from os.urandom(24).hex())

4. Deploy
Click Create Web Service

Live at: https://<your-app-name>.onrender.com

Notes:
gunicorn must be in requirements.txt

qpaper.db will be created automatically

Check Render logs for debugging

🗂 Project Structure
bash
Copy
Edit
qp-papers/
├── app.py              # Flask app
├── requirements.txt    # Dependencies
├── qpaper.db           # SQLite DB (auto-created)
└── README.md           # This file
🤝 Contributing
Fork the repo

Create a branch: git checkout -b feature/your-feature

Commit: git commit -m "Add feature"

Push: git push origin feature/your-feature

Open a pull request 🚀

Report issues via GitHub Issues

📜 License
This project is licensed under the MIT License.
See the LICENSE file for details.

👨‍💻 Developers
Developed by Sumanth and Praveen



