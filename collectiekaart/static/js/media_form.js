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
