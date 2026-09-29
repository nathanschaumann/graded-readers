/* Library page: level filter, search, sort, French-only filter. Static, no build step. */
(function () {
  var KEY = "gr-library";
  var state = { level: "all", q: "", sort: "level", fr: false };
  try { Object.assign(state, JSON.parse(localStorage.getItem(KEY) || "{}")); } catch (e) {}
  state.q = "";

  var data = null;
  var $ = function (id) { return document.getElementById(id); };
  function save() { try { localStorage.setItem(KEY, JSON.stringify({ level: state.level, sort: state.sort, fr: state.fr })); } catch (e) {} }
  function fmt(n) { return n.toLocaleString("en-US"); }
  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }

  function renderLevels() {
    var box = $("levels");
    box.textContent = "";
    var total = data.stories.length;
    var items = [{ code: "all", label: "All", count: total }].concat(data.levels.filter(function (l) { return l.count > 0; }));
    items.forEach(function (l) {
      var b = el("button", "pill");
      b.type = "button";
      b.setAttribute("aria-pressed", String(state.level === l.code));
      b.appendChild(document.createTextNode(l.label + " "));
      b.appendChild(el("span", "n", String(l.count)));
      b.addEventListener("click", function () { state.level = l.code; save(); render(); });
      box.appendChild(b);
    });
  }

  function visible() {
    var q = state.q.trim().toLowerCase();
    var list = data.stories.filter(function (s) {
      if (state.level !== "all" && s.level !== state.level) return false;
      if (state.fr && !s.french) return false;
      if (q && s.title.toLowerCase().indexOf(q) < 0) return false;
      return true;
    });
    var order = {}; data.levels.forEach(function (l, i) { order[l.code] = i; });
    list.sort(function (a, b) {
      if (state.sort === "title") return a.title.localeCompare(b.title);
      if (state.sort === "short") return a.words - b.words;
      if (state.sort === "long") return b.words - a.words;
      return order[a.level] - order[b.level] || a.title.localeCompare(b.title);
    });
    return list;
  }

  function card(s) {
    var a = el("a", "card");
    a.href = "reader.html?story=" + encodeURIComponent(s.slug);
    a.appendChild(el("h2", null, s.title));
    var row = el("div", "row");
    row.appendChild(el("span", "badge lv-" + s.level, s.levelLabel));
    row.appendChild(el("span", null, fmt(s.words) + " words"));
    row.appendChild(el("span", "dot", "·"));
    row.appendChild(el("span", null, s.chapters + (s.chapters === 1 ? " chapter" : " chapters")));
    if (s.french) row.appendChild(el("span", "badge fr", "French"));
    a.appendChild(row);
    return a;
  }

  function render() {
    renderLevels();
    $("sort").value = state.sort;
    $("frbtn").setAttribute("aria-pressed", String(state.fr));
    var list = visible();
    var grid = $("grid");
    grid.textContent = "";
    list.forEach(function (s) { grid.appendChild(card(s)); });
    $("empty").hidden = list.length > 0;
    $("count").textContent = list.length + (list.length === 1 ? " story" : " stories");
  }

  function renderTable() {
    var tb = $("ltable");
    data.levels.forEach(function (l) {
      var tr = document.createElement("tr");
      var td = el("td"); td.appendChild(el("span", "badge lv-" + l.code, l.label)); tr.appendChild(td);
      [l.maxSentence + " words", l.chapterCeiling.toFixed(1), l.cumCeiling.toFixed(1), String(l.count)].forEach(function (t) {
        tr.appendChild(el("td", "num", t));
      });
      tb.appendChild(tr);
    });
  }

  fetch("data/stories.json").then(function (r) {
    if (!r.ok) throw new Error("HTTP " + r.status);
    return r.json();
  }).then(function (d) {
    data = d;
    var fr = d.stories.filter(function (s) { return s.french; }).length;
    $("lede").textContent = d.stories.length + " public-domain tales retold in plain, literal English at five levels. Each level caps sentence length and how much new vocabulary a chapter may bring in, and an open scorer checks every story against its limits. " + fr + " have a French version.";
    renderTable();
    render();
    $("q").addEventListener("input", function (e) { state.q = e.target.value; render(); });
    $("sort").addEventListener("change", function (e) { state.sort = e.target.value; save(); render(); });
    $("frbtn").addEventListener("click", function () { state.fr = !state.fr; save(); render(); });
  }).catch(function (e) {
    $("count").textContent = "Could not load the library (" + e.message + "). Serve this folder with a static server.";
  });
})();
