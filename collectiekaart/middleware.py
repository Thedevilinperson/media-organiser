"""
WSGI-middleware voor Home Assistant Ingress.

DIT IS DE FIX VOOR DE 404's EN DE ONTBREKENDE OPMAAK.

Home Assistant serveert een add-on niet op de root, maar achter een subpad:
    /api/hassio_ingress/<willekeurig-token>/
De Supervisor stuurt dat pad mee in de header 'X-Ingress-Path'. Zonder deze
middleware weet Flask daar niets van: url_for() genereert dan '/static/css/
style.css' en '/media/add' in plaats van '/api/hassio_ingress/<token>/...'.
Het gevolg is precies wat er in het logboek te zien was: enkel 'GET /' komt
binnen, terwijl de stylesheet en alle navigatielinks buiten de add-on om
worden opgevraagd en dus een 404 geven.

Door SCRIPT_NAME te zetten weet Flask onder welk prefix hij draait en bouwt
url_for() automatisch de juiste URL's. Zonder Ingress (standalone Windows,
losse Docker) is de header afwezig en verandert er niets.
"""


class IngressMiddleware:
    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        prefix = environ.get("HTTP_X_INGRESS_PATH", "")
        if prefix:
            prefix = "/" + prefix.strip("/")
            environ["SCRIPT_NAME"] = prefix
            path = environ.get("PATH_INFO", "")
            if path.startswith(prefix):
                environ["PATH_INFO"] = path[len(prefix):] or "/"
        return self.wsgi_app(environ, start_response)
