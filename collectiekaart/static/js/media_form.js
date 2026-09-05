/*
  Toont bij het wisselen van mediatype alleen de velden die voor dat type
  ingesteld staan, en zet meteen de verplichte velden goed. De instellingen
  komen uit het data-config-attribuut van het formulier; de server controleert
  bij het opslaan hetzelfde nog eens.
*/
(function () {
  "use strict";

  var form = document.getElementById("media-form");
  var select = document.getElementById("media_type");
  if (!form || !select) { return; }

  var config = {};
  try {
    config = JSON.parse(form.dataset.config || "{}");
  } catch (error) {
    return;  // zonder instellingen laten we alles staan
  }

  function apply(container, setting) {
    var zichtbaar = Boolean(setting && setting.visible);
    container.hidden = !zichtbaar;

    container.querySelectorAll("input, select, textarea").forEach(function (element) {
      if (element.type === "file" || element.type === "checkbox") {
        element.required = false;
        return;
      }
      element.required = zichtbaar && Boolean(setting && setting.required);
    });

    var markering = container.querySelector(".req");
    if (markering) {
      markering.hidden = !(setting && setting.required);
    }
  }

  function update() {
    var typeConfig = config[select.value];
    if (!typeConfig) { return; }

    document.querySelectorAll("[data-field]").forEach(function (container) {
      apply(container, typeConfig.fields[container.dataset.field]);
    });

    document.querySelectorAll("[data-custom-field]").forEach(function (container) {
      apply(container, typeConfig.custom[container.dataset.customField]);
    });

    var eigenVelden = document.getElementById("custom-fieldset");
    if (eigenVelden) {
      var zichtbaar = [].slice.call(eigenVelden.querySelectorAll("[data-custom-field]"))
        .some(function (container) { return !container.hidden; });
      eigenVelden.hidden = !zichtbaar;
    }
  }

  select.addEventListener("change", update);
  update();
})();

/* Richtprijs opzoeken vanaf het invulformulier. */
(function () {
  "use strict";

  var button = document.getElementById("value-lookup-btn");
  if (!button) { return; }

  var status = document.getElementById("value-lookup-status");
  var valueField = document.getElementById("estimated_value");

  function showLink(url, text) {
    status.textContent = text + " ";
    var link = document.createElement("a");
    link.href = url;
    link.target = "_blank";
    link.rel = "noopener";
    link.textContent = "Zelf kijken bij LastDodo";
    status.appendChild(link);
  }

  button.addEventListener("click", function () {
    var title = document.getElementById("title").value.trim();
    var seriesField = document.getElementById("series");
    if (!title) {
      status.textContent = "Vul eerst een titel in.";
      return;
    }

    status.textContent = "Bezig met opzoeken…";
    button.disabled = true;

    var body = new FormData();
    body.append("title", title);
    if (seriesField) { body.append("series", seriesField.value.trim()); }

    fetch(button.dataset.url, {
      method: "POST",
      body: body,
      headers: { "X-CSRF-Token": window.Collectiekaart.csrf() },
    })
      .then(function (response) { return response.json(); })
      .then(function (data) {
        button.disabled = false;
        if (data.value) {
          valueField.value = String(data.value).replace(".", ",");
          status.textContent = "Richtprijs gevonden. Controleer ze en sla het item op.";
        } else {
          showLink(data.url, data.error || "Niets gevonden.");
        }
      })
      .catch(function () {
        button.disabled = false;
        status.textContent = "Opzoeken lukte niet.";
      });
  });
})();
