/*
  Barcode scannen.

  Twee wegen naar hetzelfde doel:
  1. De ingebouwde barcodelezer van de browser (BarcodeDetector). Die zit in
     Chrome op Android en is het snelst. Let op: een onbekend formaat in de
     lijst laat het aanmaken van de lezer meteen falen, daarom vragen we eerst
     op welke formaten dit toestel echt ondersteunt.
  2. html5-qrcode van een CDN, voor toestellen zonder die lezer.

  Een gelezen code wordt pas aanvaard als het controlecijfer klopt én als hij
  twee keer na elkaar hetzelfde gelezen wordt. Zonder die controle sluipt er
  makkelijk een halve leesbeurt binnen: een boek van 9789023467588 kwam er
  eerder uit als 17896016.
*/
(function () {
  "use strict";

  var script = document.currentScript;
  var lookupTemplate = script.dataset.lookupUrl;
  var formUrl = script.dataset.formUrl;

  // Bewust géén EAN-8: dat formaat staat op kleine verpakkingen, nooit op een
  // boek of een strip. Wordt het toch toegelaten, dan leest de scanner soms de
  // halve EAN-13 als een EAN-8 die per ongeluk een kloppend controlecijfer
  // heeft. Zo werd 9789023467588 ooit 17896016.
  var WANTED_FORMATS = ["ean_13", "upc_a"];

  var statusEl = document.getElementById("scan-status");
  var resultEl = document.getElementById("scan-result");
  var readerEl = document.getElementById("reader");
  var startBtn = document.getElementById("start-btn");
  var stopBtn = document.getElementById("stop-btn");
  var manualForm = document.getElementById("manual-form");
  var manualInput = document.getElementById("manual-code");

  var scanner = null;
  var stream = null;
  var running = false;
  var lastRead = null;

  function setStatus(text) { statusEl.textContent = text; }

  /* Controlecijfer van EAN-13, EAN-8 en UPC-A. */
  function checksumOk(code) {
    if (!/^\d+$/.test(code)) { return false; }
    // Een UPC-A telt twaalf cijfers en wordt aangevuld tot dertien. Begint zo'n
    // code met 97, dan is het geen UPC-A maar een ISBN waarvan er een cijfer
    // wegviel; die weigeren we.
    if (code.length === 12) {
      if (code.indexOf("97") === 0) { return false; }
      code = "0" + code;
    }
    if (code.length !== 13) { return false; }

    var digits = code.split("").map(Number);
    var check = digits.pop();
    var sum = 0;
    digits.reverse().forEach(function (digit, index) {
      sum += digit * (index % 2 === 0 ? 3 : 1);
    });
    return (10 - (sum % 10)) % 10 === check;
  }

  /* Pas aanvaarden na twee identieke leesbeurten. */
  function accept(code) {
    code = String(code).replace(/[^0-9]/g, "");
    if (!checksumOk(code)) {
      setStatus("Onduidelijk gelezen, blijf even stil richten…");
      lastRead = null;
      return false;
    }
    if (lastRead !== code) {
      lastRead = code;
      setStatus("Even bevestigen, hou de camera stil…");
      return false;
    }
    return true;
  }

  /* Veldnamen in het Nederlands, zodat de lijst leesbaar is. */
  var LABELS = {
    title: "Titel",
    series: "Reeks",
    series_number: "Nummer in de reeks",
    author: "Auteur / tekenaar",
    musician: "Muzikant",
    collection: "Collectie",
    year: "Jaar"
  };

  var laatsteCode = null;

  function lookup(code, opnieuw) {
    laatsteCode = code;
    setStatus("Barcode " + code + " gelezen. Alle catalogi tegelijk bevragen…");
    resultEl.hidden = true;
    var url = lookupTemplate.replace("CODE", encodeURIComponent(code));
    if (opnieuw) { url += (url.indexOf("?") === -1 ? "?" : "&") + "opnieuw=1"; }
    fetch(url)
      .then(function (response) { return response.json(); })
      .then(function (data) { show(code, data); })
      .catch(function () {
        setStatus("Opzoeken lukte niet: de app zelf was niet bereikbaar. Ga verder en vul de "
          + "velden zelf in.");
        show(code, { barcode: code, fields: { barcode: code }, sources: [], links: [] });
      });
  }

  /* Eén regel in het overzicht van de bronnen. De uitleg per bron komt van de
     server: die weet welke HTTP-code er terugkwam en hoe lang het duurde. */
  function reportRow(bron) {
    var rij = document.createElement("tr");
    rij.className = "source-" + (bron.status || "empty");

    var naam = document.createElement("td");
    naam.setAttribute("data-label", "Bron");
    naam.textContent = bron.label || bron.key || "";
    rij.appendChild(naam);

    var uitkomst = document.createElement("td");
    uitkomst.setAttribute("data-label", "Uitkomst");
    var merk = document.createElement("span");
    merk.className = "source-badge source-badge-" + (bron.status || "empty");
    merk.textContent = bron.status_label || bron.status || "";
    uitkomst.appendChild(merk);
    rij.appendChild(uitkomst);

    var uitleg = document.createElement("td");
    uitleg.setAttribute("data-label", "Toelichting");
    uitleg.className = "wrap-cell";
    uitleg.appendChild(document.createTextNode(bron.message || ""));

    // De losse aanvragen erachter: adres, HTTP-code en duur. Alleen zichtbaar
    // als je ze openklapt, want in het gewone geval hoef je ze niet te zien.
    if (bron.calls && bron.calls.length) {
      var blok = document.createElement("details");
      blok.className = "source-calls";
      var kop = document.createElement("summary");
      kop.textContent = bron.calls.length === 1 ? "1 aanvraag" : bron.calls.length + " aanvragen";
      blok.appendChild(kop);

      var lijst = document.createElement("ul");
      bron.calls.forEach(function (call) {
        var item = document.createElement("li");
        var delen = [];
        delen.push(call.error ? call.error : ("HTTP " + (call.http === null ? "?" : call.http)));
        if (call.note) { delen.push(call.note); }
        delen.push(call.ms + " ms");
        var kopregel = document.createElement("strong");
        kopregel.textContent = delen.join(" · ");
        item.appendChild(kopregel);
        var adres = document.createElement("div");
        adres.className = "source-url mono";
        adres.textContent = call.url || "";
        item.appendChild(adres);
        lijst.appendChild(item);
      });
      blok.appendChild(lijst);
      uitleg.appendChild(blok);
    }
    rij.appendChild(uitleg);

    var tijd = document.createElement("td");
    tijd.setAttribute("data-label", "Tijd");
    tijd.className = "mono";
    tijd.textContent = (bron.ms || 0) + " ms";
    rij.appendChild(tijd);
    return rij;
  }

  function showReport(diagnostics) {
    var blok = document.getElementById("found-report");
    var body = document.getElementById("found-report-rows");
    if (!blok || !body) { return; }
    body.textContent = "";
    if (!diagnostics || !diagnostics.length) {
      blok.hidden = true;
      return;
    }
    diagnostics.forEach(function (bron) { body.appendChild(reportRow(bron)); });
    blok.hidden = false;
    // Ging er iets mis of leverde niets iets op, dan staat het overzicht meteen
    // open: dan is het net de informatie die je nodig hebt.
    var probleem = diagnostics.some(function (bron) {
      return bron.status === "error" || bron.status === "timeout";
    });
    var treffer = diagnostics.some(function (bron) { return bron.status === "found"; });
    blok.open = probleem || !treffer;
  }

  function show(code, data) {
    // De server stuurt sinds 0.1.13 een omhulsel met velden, bronnen en
    // zoeklinks. Een oud antwoord (enkel velden) blijft ook werken.
    var fields = data.fields || data;
    var sources = data.sources || [];
    var links = data.links || [];
    var fromCollection = data.from_collection || [];

    document.getElementById("found-code").textContent = code;
    var list = document.getElementById("found-fields");
    list.textContent = "";

    var keys = Object.keys(fields).filter(function (key) { return key !== "barcode"; });
    if (!keys.length) {
      var empty = document.createElement("li");
      empty.className = "muted";
      empty.textContent = "Geen van de geraadpleegde catalogi kent deze code. Dat komt voor bij "
        + "stripalbums zonder ISBN en bij oudere uitgaven. Ga verder en vul de velden zelf in; "
        + "de barcode wordt bewaard.";
      list.appendChild(empty);
    } else {
      var origins = data.origins || {};
      keys.forEach(function (key) {
        var item = document.createElement("li");
        var label = document.createElement("strong");
        label.textContent = (LABELS[key] || key) + ": ";
        item.appendChild(label);
        item.appendChild(document.createTextNode(String(fields[key])));
        // Erbij zetten wélke bron dit veld aanleverde. Bij tegenstrijdige
        // gegevens weet je zo meteen wie je moet geloven.
        if (origins[key]) {
          var bron = document.createElement("span");
          bron.className = "muted";
          bron.textContent = " (" + origins[key] + ")";
          item.appendChild(bron);
        }
        list.appendChild(item);
      });
    }

    var sourceEl = document.getElementById("found-sources");
    var delen = [];
    if (sources.length) { delen.push("Gevonden bij: " + sources.join(", ") + "."); }
    if (fromCollection.length) {
      delen.push("Aangevuld uit je eigen collectie: " + fromCollection.join(", ") + ".");
    }
    if (!sources.length && data.tried && data.tried.length) {
      delen.push("Bevraagd zonder resultaat: " + data.tried.join(", ") + ".");
    }
    if (data.cached) {
      delen.push("Dit antwoord kwam uit het geheugen van een eerdere opzoeking; "
        + "met \u201cOpnieuw opzoeken\u201d worden alle bronnen echt opnieuw bevraagd.");
    }
    sourceEl.textContent = delen.join(" ");

    showReport(data.diagnostics);

    var linkBlok = document.getElementById("found-links");
    var linkLijst = document.getElementById("found-links-list");
    linkLijst.textContent = "";
    if (links.length) {
      links.forEach(function (link, index) {
        if (index) { linkLijst.appendChild(document.createTextNode(" · ")); }
        var anchor = document.createElement("a");
        anchor.href = link.url;
        anchor.target = "_blank";
        anchor.rel = "noopener";
        anchor.textContent = link.label;
        linkLijst.appendChild(anchor);
      });
      linkBlok.hidden = false;
    } else {
      linkBlok.hidden = true;
    }

    var params = new URLSearchParams(fields);
    if (data.suggested_type) { params.set("media_type", data.suggested_type); }
    document.getElementById("continue-link").href = formUrl + "?" + params.toString();
    resultEl.hidden = false;
    setStatus("");
  }

  function stop() {
    running = false;
    lastRead = null;
    if (scanner) {
      scanner.stop().catch(function () {});
      scanner.clear && scanner.clear();
      scanner = null;
    }
    if (stream) {
      stream.getTracks().forEach(function (track) { track.stop(); });
      stream = null;
    }
    readerEl.textContent = "";
    stopBtn.hidden = true;
    startBtn.hidden = false;
  }

  function finish(code) {
    stop();
    setStatus("");
    lookup(code);
  }

  /* --- Weg 1: de ingebouwde lezer --- */
  function startNative(formats) {
    var detector;
    try {
      detector = new window.BarcodeDetector({ formats: formats });
    } catch (error) {
      startLibrary();
      return;
    }

    var video = document.createElement("video");
    video.setAttribute("playsinline", "");
    video.setAttribute("muted", "");
    video.style.width = "100%";
    video.style.display = "block";
    readerEl.textContent = "";
    readerEl.appendChild(video);

    navigator.mediaDevices.getUserMedia({
      video: { facingMode: { ideal: "environment" }, width: { ideal: 1280 } },
    })
      .then(function (mediaStream) {
        stream = mediaStream;
        video.srcObject = mediaStream;
        return video.play();
      })
      .then(function () {
        running = true;
        setStatus("Richt de camera op de barcode.");
        (function tick() {
          if (!running) { return; }
          detector.detect(video)
            .then(function (codes) {
              if (codes.length && accept(codes[0].rawValue)) {
                finish(String(codes[0].rawValue).replace(/[^0-9]/g, ""));
              } else {
                setTimeout(tick, 250);
              }
            })
            .catch(function () { setTimeout(tick, 500); });
        })();
      })
      .catch(function (error) { cameraError(error); });
  }

  /* --- Weg 2: de bibliotheek van het CDN --- */
  function startLibrary() {
    if (typeof window.Html5Qrcode === "undefined") {
      setStatus("De scanner kon niet laden. Typ de barcode hieronder zelf in.");
      startBtn.hidden = false;
      stopBtn.hidden = true;
      return;
    }

    var formats = [];
    if (window.Html5QrcodeSupportedFormats) {
      formats = [
        window.Html5QrcodeSupportedFormats.EAN_13,
        window.Html5QrcodeSupportedFormats.UPC_A,
      ];
    }

    scanner = new window.Html5Qrcode("reader", { formatsToSupport: formats, verbose: false });
    running = true;
    scanner.start(
      { facingMode: "environment" },
      { fps: 10, qrbox: { width: 280, height: 160 } },
      function (decoded) {
        if (accept(decoded)) {
          finish(String(decoded).replace(/[^0-9]/g, ""));
        }
      },
      function () { /* elke mislukte leesbeurt, bewust stil */ }
    ).then(function () {
      setStatus("Richt de camera op de barcode.");
    }).catch(function (error) { cameraError(error); });
  }

  function cameraError(error) {
    var name = (error && error.name) || "";
    var message;
    if (name === "NotAllowedError" || name === "SecurityError") {
      message = "De camera werd geweigerd. Sta camera toe voor deze pagina, of open "
        + "Collectiekaart in een eigen tabblad: binnen het kader van Home Assistant "
        + "geeft niet elke browser toegang tot de camera. Typen kan altijd.";
    } else if (name === "NotFoundError" || name === "OverconstrainedError") {
      message = "Er is geen camera gevonden op dit toestel.";
    } else if (name === "NotReadableError") {
      message = "De camera is al in gebruik door een andere app.";
    } else {
      message = "De camera startte niet: " + (error && (error.message || error));
    }
    setStatus(message);
    stop();
  }

  function start() {
    resultEl.hidden = true;
    lastRead = null;
    startBtn.hidden = true;
    stopBtn.hidden = false;
    setStatus("Camera wordt gestart…");

    if (!window.isSecureContext) {
      setStatus("Je browser geeft alleen toegang tot de camera op een beveiligde verbinding. "
        + "Open de app via Home Assistant, of typ de barcode hieronder in.");
      stop();
      return;
    }
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      setStatus("Deze browser kan de camera niet openen. Typ de barcode hieronder in.");
      stop();
      return;
    }

    // Alleen formaten meegeven die dit toestel echt kent: een onbekend
    // formaat laat de lezer meteen falen.
    if (window.BarcodeDetector && window.BarcodeDetector.getSupportedFormats) {
      window.BarcodeDetector.getSupportedFormats()
        .then(function (available) {
          var usable = WANTED_FORMATS.filter(function (format) {
            return available.indexOf(format) !== -1;
          });
          if (usable.length) { startNative(usable); } else { startLibrary(); }
        })
        .catch(function () { startLibrary(); });
    } else {
      startLibrary();
    }
  }

  startBtn.addEventListener("click", start);
  stopBtn.addEventListener("click", function () { stop(); setStatus("Camera gestopt."); });
  document.getElementById("rescan-btn").addEventListener("click", start);

  // Alle bronnen echt opnieuw bevragen, zonder het bewaarde antwoord. Nuttig
  // als er net één bron een foutcode gaf: dat is vaak tijdelijk.
  var retryBtn = document.getElementById("retry-btn");
  if (retryBtn) {
    retryBtn.addEventListener("click", function () {
      if (laatsteCode) { lookup(laatsteCode, true); }
    });
  }

  manualForm.addEventListener("submit", function (event) {
    event.preventDefault();
    var code = manualInput.value.replace(/[^0-9]/g, "");
    if (!code) { return; }
    if (!checksumOk(code)) {
      setStatus("Dat zijn geen geldige cijfers. Een barcode op een boek telt er dertien.");
      return;
    }
    stop();
    lookup(code);
  });
})();
