# Study Planner

A simple study planner built with Python, Django, HTML, CSS and SQLite.

## Features
- Add a subject, topic and exam date
- View pending topics by nearest exam date
- Mark topics completed or pending
- Delete topics and track progress

## Run
Requires Python 3.10 or newer. Open a terminal in the project folder:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python manage.py migrate
.\.venv\Scripts\python manage.py runserver
```

Open http://127.0.0.1:8000/ in your browser.

This is a beginner project for local use, based on concepts learned in the Pentagon Space Python workshop. Built with AI coding assistance.
