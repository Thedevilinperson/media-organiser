/*
  Wijzigen rechtstreeks in de tabel van de volledige lijst.

  Eén cel tegelijk. Tik je op een cel, dan verschijnt er een invoervakje op die
  plek; Enter of het verlaten van het vakje bewaart, Escape annuleert. Ja/nee-
  cellen hebben geen vakje nodig en wisselen met één tik.

  Wat er bewaard wordt, gaat langs dezelfde controle als het gewone formulier:
  de server kijkt of het veld voor dat mediatype aanstaat, of het niet verplicht
  is, en of de waarde binnen haar grenzen valt. Wat de server terugstuurt, is de
  tekst zoals ze in de cel hoort te staan — die wordt hier niet zelf opgemaakt,
  zodat een gewijzigde cel er exact hetzelfde uitziet als na een herlading.

  Bewust geen bibliotheek en geen bewerkmodus per rij: bij een lijst van
  honderden items telt elke overbodige klik.
*/
(function () {
  "use strict";

  var table = document.querySelector("table.data-table.editable");
  var toggle = document.getElementById("inline-edit-toggle");
  var statusEl = document.getElementById("inline-status");
  if (!table) { return; }

  var BEWAARSLEUTEL = "collectiekaart.inline-edit";
  var bezig = null;   // de cel die op dit ogenblik bewerkt wordt

  function lees(attribuut, standaard) {
    try {
      return JSON.parse(table.getAttribute(attribuut) || "null") || standaard;
    } catch (error) {
      return standaard;
    }
  }

  var owners = lees("data-owners", []);
  var conditions = lees("data-conditions", []);

  function melding(tekst, soort) {
    if (!statusEl) { return; }
    statusEl.textContent = tekst || "";
    statusEl.className = "inline-status" + (soort ? " " + soort : "");
    if (tekst && soort !== "fout") {
      window.setTimeout(function () {
        if (statusEl.textContent === tekst) { melding(""); }
      }, 2500);
    }
  }

  /* ---------- aan- en uitzetten, en onthouden ---------- */
  function pasModusToe(aan) {
    table.classList.toggle("editing", !!aan);
    if (!aan && bezig) { annuleer(bezig); }
  }

  if (toggle) {
    var bewaard = null;
    try { bewaard = window.localStorage.getItem(BEWAARSLEUTEL); } catch (error) { bewaard = null; }
    if (bewaard === "0") { toggle.checked = false; }
    pasModusToe(toggle.checked);
    toggle.addEventListener("change", function () {
      pasModusToe(toggle.checked);
      try { window.localStorage.setItem(BEWAARSLEUTEL, toggle.checked ? "1" : "0"); } catch (error) { /* privémodus */ }
    });
  } else {
    pasModusToe(true);
  }

  /* ---------- het invoerelement voor een soort veld ---------- */
  function maakInvoer(soort, waarde, veld) {
    var element;
    if (soort === "condition" || soort === "owner") {
      element = document.createElement("select");
      var leeg = document.createElement("option");
      leeg.value = "";
      leeg.textContent = "— niet ingevuld —";
      element.appendChild(leeg);

      var lijst = soort === "owner" ? owners : conditions;
      lijst.forEach(function (item) {
        var optie = document.createElement("option");
        optie.value = soort === "owner" ? String(item.id) : String(item);
        optie.textContent = soort === "owner" ? item.name : String(item);
        element.appendChild(optie);
      });
      element.value = waarde || "";
      return element;
    }

    // Commentaar mag meerdere regels bevatten. Een gewoon invoervak zou die
    // regeleinden bij het bewaren stilzwijgend wegvegen; een tekstvak niet.
    if (veld === "comment") {
      element = document.createElement("textarea");
      element.rows = 3;
      element.value = waarde || "";
      return element;
    }

    element = document.createElement("input");
    element.type = "text";
    if (soort === "int" || soort === "number") { element.inputMode = "decimal"; }
    element.value = waarde || "";
    return element;
  }

  /* ---------- bewaren ---------- */
  function bewaar(cel, ruweWaarde) {
    var rij = cel.closest("tr");
    var url = rij && rij.dataset.url;
    if (!url) { return Promise.resolve(); }

    cel.classList.add("saving");
    melding("Bewaren…");

    return fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-Token": window.Collectiekaart.csrf(),
      },
      body: JSON.stringify({ field: cel.dataset.field, value: ruweWaarde }),
    })
      .then(function (response) { return response.json(); })
      .then(function (data) {
        cel.classList.remove("saving");
        if (!data || !data.ok) {
          toon(cel, cel.dataset.value, null);
          cel.classList.add("failed");
          window.setTimeout(function () { cel.classList.remove("failed"); }, 2500);
          melding((data && data.error) || "Wijzigen lukte niet.", "fout");
          return;
        }
        toon(cel, data.value, data.display);
        cel.classList.add("saved");
        window.setTimeout(function () { cel.classList.remove("saved"); }, 1200);
        melding("Bewaard.", "ok");
      })
      .catch(function () {
        cel.classList.remove("saving");
        toon(cel, cel.dataset.value, null);
        melding("Geen verbinding met de app. De wijziging is niet bewaard.", "fout");
      });
  }

  /* Zet de cel terug in leesmodus. */
  function toon(cel, ruweWaarde, weergave) {
    cel.dataset.value = ruweWaarde === undefined || ruweWaarde === null ? "" : String(ruweWaarde);
    cel.textContent = "";
    var tekst = weergave;
    if (tekst === null || tekst === undefined) {
      tekst = cel.dataset.display || (cel.dataset.value || "—");
    }
    cel.dataset.display = tekst;
    if (cel.dataset.field === "title") {
      var vet = document.createElement("strong");
      vet.textContent = tekst;
      cel.appendChild(vet);
    } else {
      cel.appendChild(document.createTextNode(tekst));
    }
    if (bezig === cel) { bezig = null; }
    cel.classList.remove("editing-cell");
  }

  function annuleer(cel) {
    toon(cel, cel.dataset.value, cel.dataset.display);
  }

  /* ---------- bewerken starten ---------- */
  function bewerk(cel) {
    if (bezig === cel) { return; }
    if (bezig) { annuleer(bezig); }

    var soort = cel.dataset.kind || "text";

    // Ja/nee heeft geen vakje nodig: één tik wisselt en bewaart meteen.
    if (soort === "bool") {
      bewaar(cel, cel.dataset.value === "1" ? "0" : "1");
      return;
    }

    cel.dataset.display = cel.textContent.trim();
    bezig = cel;
    cel.classList.add("editing-cell");
    cel.textContent = "";

    var invoer = maakInvoer(soort, cel.dataset.value, cel.dataset.field);
    cel.appendChild(invoer);
    invoer.focus();
    if (invoer.select) { invoer.select(); }

    var afgehandeld = false;
    function afronden(bewaren) {
      if (afgehandeld) { return; }
      afgehandeld = true;
      var nieuwe = invoer.value;
      // Eerst de cel terugzetten in leesmodus, dan pas bewaren. Zo staat er
      // tijdens het bewaren geen invoervak meer in de weg als je meteen een
      // volgende cel aantikt, en kan die tweede bewerking deze niet
      // terugdraaien terwijl het antwoord nog onderweg is.
      annuleer(cel);
      if (!bewaren || nieuwe === (cel.dataset.value || "")) { return; }
      bewaar(cel, nieuwe);
    }

    invoer.addEventListener("keydown", function (event) {
      // In het tekstvak voor commentaar begint Enter gewoon een nieuwe regel;
      // daar bewaar je door het vak te verlaten of met Ctrl+Enter.
      if (event.key === "Enter" && invoer.tagName === "TEXTAREA" && !event.ctrlKey) { return; }
      if (event.key === "Enter") { event.preventDefault(); afronden(true); }
      if (event.key === "Escape") { event.preventDefault(); afronden(false); }
      if (event.key === "Tab") { afronden(true); }
    });
    invoer.addEventListener("blur", function () { afronden(true); });
    if (invoer.tagName === "SELECT") {
      invoer.addEventListener("change", function () { afronden(true); });
    }
  }

  table.addEventListener("click", function (event) {
    if (!table.classList.contains("editing")) { return; }
    // Een link of een knop in de cel blijft gewoon werken.
    if (event.target.closest("a, button, form, input, select, textarea")) { return; }
    var cel = event.target.closest("td.edit-cell");
    if (cel) { bewerk(cel); }
  });
})();
