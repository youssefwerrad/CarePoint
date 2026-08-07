from functools import wraps
from flask import redirect, session, render_template


def apology(message, code=400):
    """Render a simple error page."""
    return render_template("apology.html", message=message, code=code), code


def login_required(f):
    """Decorate routes to require login.

    Redirects to /login if user_id is not in session.
    (Same pattern as CS50 Finance's login_required.)
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function


def role_required(role):
    """Decorate routes to require both login AND a specific role.

    Usage: @role_required("doctor")
    Must be stacked below @login_required, or check session itself.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if session.get("user_id") is None:
                return redirect("/login")
            if session.get("role") != role:
                return apology("Access denied: wrong role", 403)
            return f(*args, **kwargs)
        return decorated_function
    return decorator
