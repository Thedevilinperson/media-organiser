/* Gedeelde hulpjes voor alle pagina's. */
(function () {
  "use strict";

  window.Collectiekaart = {
    csrf: function () {
      var meta = document.querySelector('meta[name="csrf-token"]');
      return meta ? meta.getAttribute("content") : "";
    },
    post: function (url) {
      return fetch(url, {
        method: "POST",
        headers: { "X-CSRF-Token": window.Collectiekaart.csrf() },
      }).then(function (response) {
        if (!response.ok) { throw new Error("status " + response.status); }
        return response.json();
      });
    },
  };

  // Keuzelijsten die het formulier meteen versturen.
  document.querySelectorAll("select[data-autosubmit]").forEach(function (select) {
    select.addEventListener("change", function () { select.form.submit(); });
  });

  // Bevestiging vragen voor onomkeerbare acties.
  document.querySelectorAll("form[data-confirm]").forEach(function (form) {
    form.addEventListener("submit", function (event) {
      if (!window.confirm(form.dataset.confirm)) { event.preventDefault(); }
    });
  });
})();
