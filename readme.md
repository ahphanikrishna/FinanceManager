workout_tracker/
├── venv/                    # Virtual environment (DO NOT commit)
├── requirements.txt         # List of dependencies (flask, sqlalchemy, etc.)
├── run.py                   # Main entry point for the application
│
├── app/                     # Core application package (The main Python logic)
│   ├── __init__.py          # Initializes the Flask app and Blueprint
│   ├── models.py            # ALL SQLAlchemy Model Definitions (Category, ExerciseType, etc.)
│   ├── database.py          # Logic for initial setup and database session management
│   └── utils.py             # Helper functions (e.g., password hashing, date formatting)
│
├── api/                     # RESTful API Endpoints (The Backend Routes)
│   ├── __init__.py          # Initializes the API blueprint
│   ├── auth_routes.py       # /api/login, /api/register
│   └── workout_routes.py    # /api/workout/add_item, /api/workout/history
│
├── templates/               # HTML Templates (Jinja2 files)
│   ├── base.html            # Base layout template (header, footer, links)
│   ├── index.html           # The main dashboard (The tracker UI)
│   ├── login.html           # Authentication view
│   └── setup.html           # (Optional) Admin view to add new Exercise Types
│
└── static/                  # Client-Side Assets (Assets served directly to the browser)
    ├── css/
    │   └── style.css        # Global styling
    ├── js/
    │   └── main.js          # Main client-side logic (fetch calls, form handling)
    └── images/
        └── profile.png      # User avatars, icons, etc.
