/* Verbinding met Home Assistant testen. */
(function () {
  "use strict";

  var button = document.getElementById("ha-test-btn");
  if (!button) { return; }
  var result = document.getElementById("ha-test-result");

  button.addEventListener("click", function () {
    result.textContent = "Bezig met testen…";
    result.className = "muted";
    window.Collectiekaart.post(button.dataset.url)
      .then(function (data) {
        result.textContent = data.message;
        result.className = data.ok ? "ok-text" : "overdue";
      })
      .catch(function () {
        result.textContent = "De test kon niet uitgevoerd worden.";
        result.className = "overdue";
      });
  });
})();
