/*
  Waardeoverzicht: een richtprijs laten zoeken, of de waarde meteen zelf
  invullen. LastDodo weigert geautomatiseerde aanvragen vaak; in dat geval
  tonen we een zoeklink zodat je in één klik zelf kan kijken.
*/
(function () {
  "use strict";

  var template = document.currentScript.dataset.url;

  function euro(value) {
    return "€ " + value.toFixed(2).replace(".", ",");
  }

  /* Richtprijs zoeken */
  document.querySelectorAll(".estimate-btn").forEach(function (button) {
    button.addEventListener("click", function () {
      var status = document.getElementById(button.dataset.target);
      var input = button.closest("tr").querySelector(".value-input");

      status.textContent = "Bezig met opzoeken…";
      button.disabled = true;

      window.Collectiekaart.post(template.replace(/0$/, button.dataset.id))
        .then(function (data) {
          button.disabled = false;
          if (data.value) {
            input.value = String(data.value).replace(".", ",");
            status.textContent = euro(data.value) + " bewaard.";
            return;
          }
          status.textContent = (data.error || "Niets gevonden.") + " ";
          if (data.url) {
            var link = document.createElement("a");
            link.href = data.url;
            link.target = "_blank";
            link.rel = "noopener";
            link.textContent = "Zelf kijken";
            status.appendChild(link);
          }
        })
        .catch(function () {
          button.disabled = false;
          status.textContent = "Opzoeken lukte niet.";
        });
    });
  });

  /* Waarde zelf invullen en bewaren */
  function save(input, button) {
    var body = new FormData();
    body.append("value", input.value.replace(",", "."));
    button.disabled = true;

    fetch(input.dataset.url, {
      method: "POST",
      body: body,
      headers: { "X-CSRF-Token": window.Collectiekaart.csrf() },
    })
      .then(function (response) { return response.json(); })
      .then(function (data) {
        button.disabled = false;
        button.textContent = data.value === null ? "Leeg" : "Bewaard";
        setTimeout(function () { button.textContent = "Bewaar"; }, 2000);
      })
      .catch(function () {
        button.disabled = false;
        button.textContent = "Mislukt";
      });
  }

  document.querySelectorAll(".value-save-btn").forEach(function (button) {
    var input = button.parentNode.querySelector(".value-input");
    button.addEventListener("click", function () { save(input, button); });
    input.addEventListener("keydown", function (event) {
      if (event.key === "Enter") { event.preventDefault(); save(input, button); }
    });
  });
})();
