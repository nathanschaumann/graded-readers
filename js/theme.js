/* Theme: light on every device. The Dark button is an explicit choice the reader makes (a reading preference),
   saved in this browser. The system light/dark setting is never followed. Loaded in <head> to avoid a flash. */
(function () {
  var KEY = "gr-theme";
  function saved() { try { return localStorage.getItem(KEY); } catch (e) { return null; } }
  function apply(v) {
    document.documentElement.setAttribute("data-theme", v === "dark" ? "dark" : "light");
  }
  function current() {
    return document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light";
  }
  apply(saved());
  window.grTheme = {
    toggle: function () {
      var next = current() === "dark" ? "light" : "dark";
      apply(next);
      try { localStorage.setItem(KEY, next); } catch (e) {}
      return next;
    },
    current: current
  };
  document.addEventListener("DOMContentLoaded", function () {
    var b = document.getElementById("theme-btn");
    if (!b) return;
    function label() { b.textContent = current() === "dark" ? "Light" : "Dark"; }
    label();
    b.addEventListener("click", function () { window.grTheme.toggle(); label(); });
  });
})();
