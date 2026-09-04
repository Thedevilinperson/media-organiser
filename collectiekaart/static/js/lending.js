/* Meteen een herinnering naar Home Assistant sturen. */
(function () {
  "use strict";

  document.querySelectorAll(".remind-btn").forEach(function (button) {
    button.addEventListener("click", function () {
      button.disabled = true;
      var original = button.textContent;
      button.textContent = "Bezig…";
      window.Collectiekaart.post(button.dataset.url)
        .then(function (data) {
          button.textContent = data.ok ? "Verstuurd" : "Lukte niet";
          if (!data.ok) { button.title = data.error || ""; button.disabled = false; }
        })
        .catch(function () { button.textContent = original; button.disabled = false; });
    });
  });
})();
