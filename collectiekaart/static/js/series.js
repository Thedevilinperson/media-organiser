/*
  Eén knop die de controle bij De Poort voor alle reeksen tegelijk start. De
  server doet het echte werk op de achtergrond (met een pauze tussen elke
  reeks, zie services/jobs.py), dus dit script wacht niet op een resultaat -
  het meldt enkel dat de controle gestart is en dat de pagina straks
  ververst kan worden om de uitkomst te zien.
*/
(function () {
  "use strict";

  var button = document.getElementById("check-all-btn");
  if (!button) { return; }

  var status = document.getElementById("check-all-status");

  button.addEventListener("click", function () {
    button.disabled = true;
    status.textContent = "Bezig gestart…";

    window.Collectiekaart.post(button.dataset.url)
      .then(function (data) {
        if (data.ok) {
          status.textContent = "Controle gestart. Dit kan enkele minuten duren; ververs de " +
            "pagina straks om de resultaten te zien.";
        } else {
          status.textContent = data.error || "Kon de controle niet starten.";
          button.disabled = false;
        }
      })
      .catch(function () {
        status.textContent = "Kon de controle niet starten.";
        button.disabled = false;
      });
  });
})();
