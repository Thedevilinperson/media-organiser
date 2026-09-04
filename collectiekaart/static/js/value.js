/* Richtprijs per item ophalen. */
(function () {
  "use strict";

  var template = document.currentScript.dataset.url;

  document.querySelectorAll(".estimate-btn").forEach(function (button) {
    button.addEventListener("click", function () {
      var cell = document.getElementById(button.dataset.target);
      cell.textContent = "…";
      button.disabled = true;

      window.Collectiekaart.post(template.replace(/0$/, button.dataset.id))
        .then(function (data) {
          if (data.value) {
            cell.textContent = "€ " + data.value.toFixed(2).replace(".", ",");
            button.textContent = "Gevonden";
          } else {
            cell.textContent = data.error || "niets gevonden";
            button.disabled = false;
          }
        })
        .catch(function () {
          cell.textContent = "lukte niet";
          button.disabled = false;
        });
    });
  });
})();
