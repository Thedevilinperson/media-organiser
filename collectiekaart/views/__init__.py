"""Alle views, opgesplitst per module (vereiste 3b)."""
from views.analysis import analysis_bp
from views.lending import lending_bp
from views.main import main_bp
from views.media import media_bp
from views.settings import settings_bp


def register_blueprints(app):
    app.register_blueprint(main_bp)
    app.register_blueprint(media_bp)
    app.register_blueprint(analysis_bp)
    app.register_blueprint(lending_bp)
    app.register_blueprint(settings_bp)
