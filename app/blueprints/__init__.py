def register_blueprints(app):
    from .admin import bp as admin_bp
    from .auth import bp as auth_bp
    from .consult import bp as consult_bp
    from .courses import bp as courses_bp
    from .main import bp as main_bp
    from .pay import bp as pay_bp
    from .student import bp as student_bp
    from .workshops import bp as workshops_bp

    for bp in (main_bp, auth_bp, courses_bp, workshops_bp, consult_bp, student_bp, pay_bp, admin_bp):
        app.register_blueprint(bp)
