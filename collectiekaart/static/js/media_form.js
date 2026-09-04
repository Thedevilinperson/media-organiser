/*
  Toont alleen de velden die bij het gekozen type horen. Velden zonder
  data-profiles blijven altijd staan.
*/
(function () {
  "use strict";

  var select = document.getElementById("media_type");
  if (!select) { return; }

  function currentProfile() {
    var option = select.options[select.selectedIndex];
    return (option && option.dataset.profile) || "vrij";
  }

  function update() {
    var profile = currentProfile();
    document.querySelectorAll("[data-profiles]").forEach(function (element) {
      var visible = element.dataset.profiles.split(",").indexOf(profile) !== -1;
      element.hidden = !visible;
    });

    // Eigen velden die aan één type gekoppeld zijn: enkel tonen bij dat type.
    var option = select.options[select.selectedIndex];
    var typeId = (option && option.dataset.id) || "";
    document.querySelectorAll("[data-custom-type]").forEach(function (element) {
      var linked = element.dataset.customType;
      element.hidden = Boolean(linked) && linked !== typeId;
    });
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
