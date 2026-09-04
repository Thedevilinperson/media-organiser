/*
  Barcode scannen. Gebruikt bij voorkeur de ingebouwde barcodelezer van de
  browser (BarcodeDetector), en valt terug op html5-qrcode wanneer die er
  niet is.
*/
(function () {
  "use strict";

  var script = document.currentScript;
  var lookupTemplate = script.dataset.lookupUrl;
  var formUrl = script.dataset.formUrl;

  var statusEl = document.getElementById("scan-status");
  var resultEl = document.getElementById("scan-result");
  var readerEl = document.getElementById("reader");
  var startBtn = document.getElementById("start-btn");
  var stopBtn = document.getElementById("stop-btn");
  var scanner = null;
  var stream = null;
  var detecting = false;

  function setStatus(text) { statusEl.textContent = text; }

  function lookup(code) {
    setStatus("Barcode " + code + " gevonden. Gegevens opzoeken…");
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
      empty.textContent = "Niets gevonden voor deze code. Vul de velden zelf in.";
      list.appendChild(empty);
    } else {
      keys.forEach(function (key) {
        var item = document.createElement("li");
        var label = document.createElement("strong");
        label.textContent = key + ": ";
        item.appendChild(label);
        // textContent, geen innerHTML: gegevens van buitenaf mogen nooit als
        // HTML uitgevoerd worden.
        item.appendChild(document.createTextNode(String(data[key])));
        list.appendChild(item);
      });
    }

    var params = new URLSearchParams(data);
    document.getElementById("continue-link").href = formUrl + "?" + params.toString();
    resultEl.hidden = false;
    setStatus("");
  }

  function stop() {
    detecting = false;
    if (scanner) { scanner.stop().catch(function () {}); scanner = null; }
    if (stream) { stream.getTracks().forEach(function (track) { track.stop(); }); stream = null; }
    readerEl.textContent = "";
    stopBtn.hidden = true;
    startBtn.hidden = false;
    setStatus("Camera gestopt.");
  }

  function startNative() {
    var video = document.createElement("video");
    video.setAttribute("playsinline", "");
    video.style.width = "100%";
    readerEl.textContent = "";
    readerEl.appendChild(video);

    var detector = new window.BarcodeDetector({
      formats: ["ean_13", "ean_8", "upc_a", "upc_e", "code_128", "isbn"],
    });

    navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } })
      .then(function (mediaStream) {
        stream = mediaStream;
        video.srcObject = mediaStream;
        return video.play();
      })
      .then(function () {
        detecting = true;
        setStatus("Richt de camera op de barcode.");
        (function tick() {
          if (!detecting) { return; }
          detector.detect(video).then(function (codes) {
            if (codes.length) {
              detecting = false;
              stop();
              lookup(codes[0].rawValue);
            } else {
              setTimeout(tick, 300);
            }
          }).catch(function () { setTimeout(tick, 500); });
        })();
      })
      .catch(function (error) { setStatus("Geen toegang tot de camera: " + error); });
  }

  function startLibrary() {
    if (typeof window.Html5Qrcode === "undefined") {
      setStatus("De scanner kon niet laden. Typ de barcode zelf in op het formulier.");
      startBtn.hidden = false;
      stopBtn.hidden = true;
      return;
    }
    scanner = new window.Html5Qrcode("reader");
    scanner.start(
      { facingMode: "environment" },
      { fps: 10, qrbox: { width: 260, height: 140 } },
      function (decoded) { stop(); lookup(decoded); }
    ).then(function () {
      setStatus("Richt de camera op de barcode.");
    }).catch(function (error) {
      setStatus("Kon de camera niet starten: " + error);
      startBtn.hidden = false;
      stopBtn.hidden = true;
    });
  }

  function start() {
    resultEl.hidden = true;
    startBtn.hidden = true;
    stopBtn.hidden = false;
    setStatus("Camera wordt gestart…");
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      setStatus("Deze browser geeft geen toegang tot de camera. Dat lukt enkel via https of localhost.");
      startBtn.hidden = false;
      stopBtn.hidden = true;
      return;
    }
    if ("BarcodeDetector" in window) { startNative(); } else { startLibrary(); }
  }

  startBtn.addEventListener("click", start);
  stopBtn.addEventListener("click", stop);
  document.getElementById("rescan-btn").addEventListener("click", start);
})();
