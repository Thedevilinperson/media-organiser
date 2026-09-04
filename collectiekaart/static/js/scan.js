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

  function lookup(code) {
    setStatus("Barcode " + code + " gelezen. Gegevens opzoeken…");
    resultEl.hidden = true;
    fetch(lookupTemplate.replace("CODE", encodeURIComponent(code)))
      .then(function (response) { return response.json(); })
      .then(function (data) { show(code, data); })
      .catch(function () {
        setStatus("Opzoeken lukte niet. Ga verder en vul de velden zelf in.");
        show(code, { barcode: code });
      });
  }

  function show(code, data) {
    document.getElementById("found-code").textContent = code;
    var list = document.getElementById("found-fields");
    list.textContent = "";

    var keys = Object.keys(data).filter(function (key) { return key !== "barcode"; });
    if (!keys.length) {
      var empty = document.createElement("li");
      empty.className = "muted";
      empty.textContent = "Deze code staat niet in Open Library of Google Books. "
        + "Ga verder en vul de velden zelf in; de barcode wordt bewaard.";
      list.appendChild(empty);
    } else {
      keys.forEach(function (key) {
        var item = document.createElement("li");
        var label = document.createElement("strong");
        label.textContent = key + ": ";
        item.appendChild(label);
        item.appendChild(document.createTextNode(String(data[key])));
        list.appendChild(item);
      });
    }

    document.getElementById("continue-link").href =
      formUrl + "?" + new URLSearchParams(data).toString();
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
