/* Controle op nieuwere nummers bij De Poort. */
(function () {
  "use strict";

  var url = document.currentScript.dataset.url;

  document.querySelectorAll(".check-new-btn").forEach(function (button) {
    button.addEventListener("click", function () {
      var target = document.getElementById(button.dataset.target);
      target.textContent = "Bezig met opzoeken…";
      button.disabled = true;

      var body = new FormData();
      body.append("series", button.dataset.series);
      (button.dataset.owned || "").split(",").filter(Boolean).forEach(function (number) {
        body.append("owned", number);
      });

      fetch(url, {
        method: "POST",
        body: body,
        headers: { "X-CSRF-Token": window.Collectiekaart.csrf() },
      })
        .then(function (response) { return response.json(); })
        .then(function (data) {
          button.disabled = false;
          if (!data.ok) {
            target.textContent = "Lukte niet: " + data.error;
            target.className = "overdue";
            return;
          }
          if (data.note) { target.textContent = data.note; return; }
          if (!data.new_numbers.length) {
            target.textContent = "Niets nieuws gevonden.";
            return;
          }
          target.textContent = "Mogelijk nieuw: " + data.new_numbers.join(", ");
          target.className = "overdue";
        })
        .catch(function () {
          button.disabled = false;
          target.textContent = "Opzoeken lukte niet.";
        });
    });
  });
})();
