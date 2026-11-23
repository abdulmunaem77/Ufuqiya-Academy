"""WSGI entry point:  gunicorn wsgi:app"""
from app import create_app

app = create_app()

if __name__ == "__main__":  # development server only
    app.run(debug=False, port=5000)
