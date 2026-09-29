/* Light/dark theme: saved choice wins, otherwise follow the system. Loaded in <head> to avoid a flash. */
(function () {
  var KEY = "gr-theme";
  function saved() { try { return localStorage.getItem(KEY); } catch (e) { return null; } }
  function apply(v) {
    if (v === "light" || v === "dark") document.documentElement.setAttribute("data-theme", v);
    else document.documentElement.removeAttribute("data-theme");
  }
  function current() {
    var v = document.documentElement.getAttribute("data-theme");
    if (v) return v;
    return window.matchMedia && matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
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
