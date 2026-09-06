"""
Collectiekaart — mediabeheerder, versie 0.1.

Applicatiefabriek. Start standalone met:  python app.py
In Home Assistant wordt dit bestand door run.sh opgestart.
"""
import atexit
import logging
import os

from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, render_template
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix

from config import Config
from extensions import db
from middleware import IngressMiddleware
from security import register_security
from services.jobs import check_overdue_loans_job, run_series_check
from version import __version__
from views import register_blueprints

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("collectiekaart")


def create_app():
    # Statische bestanden onder /assets in plaats van het standaard /static.
    #
    # De service worker van de Home Assistant-frontend bevat deze regel:
    #     registerRoute(/\/(static|frontend_latest|frontend_es5)\/.+/,
    #                   new CacheFirst({ matchOptions: { ignoreSearch: true } }))
    # Die regex is niet verankerd en matcht dus ook
    #     /api/hassio_ingress/<token>/static/js/media_form.js
    # Eenmaal opgeslagen wordt zo'n bestand nooit meer bij de server nagevraagd
    # (CacheFirst) en wordt onze ?v=-cachebreker genegeerd (ignoreSearch).
    # Gevolg: na een update van de add-on bleef de browser met de JavaScript en
    # CSS van de vorige versie werken, en reageerde het formulier niet meer op
    # een wisseling van type. Onder /assets valt de URL onder HA's '/api/'-regel
    # (NetworkOnly) en komt het bestand altijd van het netwerk; de gewone
    # browsercache en de ?v=-parameter doen dan wél hun werk.
    #
    # url_for("static", ...) en de asset()-helper werken ongewijzigd door; enkel
    # het pad in de URL verandert. Standalone (zonder Ingress) is er geen
    # service worker en maakt het niets uit.
    app = Flask(__name__, static_url_path="/assets")
    app.config.from_object(Config)
    # Veilig, want elke URL naar een statisch bestand draagt het versienummer:
    # bij een update wijzigt de URL en haalt de browser het bestand opnieuw op.
    app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 60 * 60 * 24 * 30

    # Volgorde is belangrijk: eerst de headers van de reverse proxy
    # interpreteren, dan het Ingress-subpad toepassen.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
    app.wsgi_app = IngressMiddleware(app.wsgi_app)

    db.init_app(app)
    register_filters(app)
    register_security(app)
    register_blueprints(app)
    register_error_handlers(app)

    with app.app_context():
        from models import ensure_schema, seed_defaults  # bewust laat geïmporteerd
        # Registreert de tabel voor de reeksencontrole bij db.create_all().
        # Los model in models_series.py, zodat models.py zelf niet gewijzigd
        # hoeft te worden voor deze ene extra tabel.
        import models_series  # noqa: F401
        db.create_all()
        ensure_schema()
        seed_defaults()

    log.info("Collectiekaart %s gestart — data in %s", __version__, app.config["DATA_DIR"])
    return app


def register_filters(app):
    @app.template_global("asset")
    def asset(filename):
        """
        URL naar een statisch bestand, met het versienummer erin. Zonder dat
        nummer blijft een browser het opgeslagen bestand van een vorige versie
        gebruiken, ook na een update van de add-on: het formulier werkt dan met
        oude JavaScript en reageert niet meer op een wisseling van type.

        Let op: dit werkt alleen als de URL niet door de service worker van
        Home Assistant onderschept wordt — zie het commentaar bij Flask(...)
        in create_app().
        """
        from flask import url_for
        return url_for("static", filename=filename, v=__version__)

    @app.template_filter("reeksnummer")
    def reeksnummer(value):
        """Toont 12 in plaats van 12.0, en 3.5 blijft 3.5."""
        if value is None:
            return "—"
        return str(int(value)) if float(value).is_integer() else str(value)

    @app.template_filter("euro")
    def euro(value):
        return "€ {:,.2f}".format(value or 0).replace(",", " ").replace(".", ",", 1)


def register_error_handlers(app):
    @app.errorhandler(404)
    def not_found(error):
        return render_template("errors/404.html"), 404

    @app.errorhandler(413)
    def too_large(error):
        return render_template("errors/error.html", code=413,
                               message="Het bestand is te groot (maximaal 8 MB)."), 413

    @app.errorhandler(400)
    def bad_request(error):
        message = getattr(error, "description", "Ongeldige aanvraag.")
        return render_template("errors/error.html", code=400, message=message), 400

    @app.errorhandler(Exception)
    def internal(error):
        if isinstance(error, HTTPException):
            return error
        # Geen technische details naar de browser sturen; die horen in het
        # logboek thuis (zie SECURITY.md, bevinding B7).
        log.exception("Onverwachte fout")
        db.session.rollback()
        return render_template("errors/error.html", code=500,
                               message="Er ging iets mis. Kijk in het logboek voor details."), 500


def start_scheduler(app):
    """
    Dagelijkse controle op te lang uitgeleende media, en de wekelijkse
    controle bij De Poort op nieuwe nummers per reeks. Draait niet in het
    herlaadproces van de ontwikkelserver, anders zouden de taken dubbel lopen.
    """
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true" and app.debug:
        return None
    scheduler = BackgroundScheduler(timezone="Europe/Brussels", daemon=True)
    scheduler.add_job(
        check_overdue_loans_job,
        "interval",
        hours=24,
        args=[app],
        id="overdue_check",
        replace_existing=True,
    )
    scheduler.add_job(
        run_series_check,
        "interval",
        weeks=1,
        args=[app],
        id="series_check",
        replace_existing=True,
    )
    scheduler.start()
    atexit.register(lambda: scheduler.shutdown(wait=False))
    return scheduler


application = create_app()

if __name__ == "__main__":
    debug = os.environ.get("FLASK_DEBUG") == "1"
    application.debug = debug
    start_scheduler(application)
    port = int(os.environ.get("PORT", "8099"))
    try:
        # waitress is een lichte productieserver; valt terug op de
        # ingebouwde server als hij niet geïnstalleerd is.
        from waitress import serve
        if not debug:
            log.info("Collectiekaart draait op http://localhost:%s", port)
            serve(application, host="0.0.0.0", port=port, threads=4)
        else:
            application.run(host="0.0.0.0", port=port, debug=True)
    except ImportError:
        application.run(host="0.0.0.0", port=port, debug=debug)
else:
    start_scheduler(application)
