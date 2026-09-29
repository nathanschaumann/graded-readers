/* Reader page: one story, chapter by chapter. English, French, or side by side. */
(function () {
  var KEY = "gr-reader";
  var prefs = { lang: "en", size: 19, summaries: false };
  try { Object.assign(prefs, JSON.parse(localStorage.getItem(KEY) || "{}")); } catch (e) {}
  function save() { try { localStorage.setItem(KEY, JSON.stringify(prefs)); } catch (e) {} }

  var $ = function (id) { return document.getElementById(id); };
  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }
  function fmt(n) { return n.toLocaleString("en-US"); }
  function fail(msg) {
    var l = $("loading");
    l.className = "err";
    l.textContent = msg;
  }

  var slug = new URLSearchParams(location.search).get("story") || "";
  if (!/^[a-z0-9_]+$/.test(slug)) { fail("No story chosen. Go back to the library and pick one."); return; }

  var story = null;

  function applySize() {
    prefs.size = Math.max(15, Math.min(27, prefs.size));
    document.documentElement.style.setProperty("--read-size", prefs.size + "px");
  }

  function sentenceText(s, lang) { return lang === "fr" ? s.fr : s.t; }

  function paraEl(p, lang, script) {
    if (script && lang !== "fr") {
      var box = el("div", "para script");
      p.s.forEach(function (s) {
        var line = el("span", "line");
        if (s.sp) line.appendChild(el("span", "sp", s.sp));
        line.appendChild(document.createTextNode(s.t));
        box.appendChild(line);
      });
      return box;
    }
    var d = el("p", "para" + (lang === "fr" ? " fr" : ""));
    if (lang === "fr") d.lang = "fr";
    d.textContent = p.s.map(function (s) { return sentenceText(s, lang); }).join(" ");
    return d;
  }

  function render() {
    var lang = story.french ? prefs.lang : "en";
    var paper = $("paper");
    paper.textContent = "";
    paper.classList.toggle("wide", lang === "both");

    var head = el("div", "story-head");
    head.appendChild(el("h1", null, story.title));
    var row = el("div", "row");
    row.appendChild(el("span", "badge lv-" + story.level, story.levelLabel));
    row.appendChild(el("span", null, fmt(story.words) + " words"));
    row.appendChild(el("span", null, story.chapters + (story.chapters === 1 ? " chapter" : " chapters")));
    if (story.french) row.appendChild(el("span", "badge fr", "French"));
    head.appendChild(row);

    var rep = el("details", "report");
    rep.appendChild(el("summary", null, "Scorer report"));
    var ok = story.guiraud <= story.guiraudCeiling;
    rep.appendChild(el("p", null,
      "Whole-story Guiraud " + story.guiraud.toFixed(2) + " against a ceiling of " + story.guiraudCeiling.toFixed(1) +
      (ok ? " (within)." : " (above it).") +
      " Longest sentence " + story.longest + " words, cap " + story.sentenceCap +
      ". " + story.chaptersOverCeiling + " of " + story.chapters + " chapters above the chapter ceiling of " + story.chapterCeiling.toFixed(1) + "."));
    if (story.chapterLengthFlags > 0) {
      rep.appendChild(el("p", null, story.chapterLengthFlags + " chapters are outside the current 300 to 600 word band. This story was written under older, shorter-chapter limits."));
    }
    rep.appendChild(el("p", null, "Reproduce it: python3 scorer/score.py stories/" + slugFile() + " --all"));
    head.appendChild(rep);
    paper.appendChild(head);

    story.chapterList.forEach(function (ch, i) {
      var sec = el("section", "chapter");
      sec.id = "c" + (i + 1);
      sec.appendChild(el("div", "eyebrow", "Chapter " + (i + 1)));
      sec.appendChild(el("h2", null, ch.title));
      if (ch.also && ch.also.length) sec.appendChild(el("p", "also", "Also in this chapter: " + ch.also.join(", ")));
      ch.paras.forEach(function (p) {
        if (lang === "both") {
          var pair = el("div", "pair two");
          var en = paraEl(p, "en", story.script);
          var fr = paraEl(p, "fr", false);
          en.classList.add("en");
          pair.appendChild(en);
          pair.appendChild(fr);
          sec.appendChild(pair);
        } else {
          sec.appendChild(paraEl(p, lang, story.script));
        }
        if (prefs.summaries && p.summary) sec.appendChild(el("p", "summary", p.summary));
      });
      paper.appendChild(sec);
    });

    var pager = el("div", "pager");
    var back = el("a", "btn", "Back to library"); back.href = "index.html";
    var top = el("a", "btn", "Back to top"); top.href = "#";
    top.addEventListener("click", function (e) { e.preventDefault(); window.scrollTo({ top: 0 }); });
    pager.appendChild(back); pager.appendChild(top);
    paper.appendChild(pager);
  }

  var slugFileName = null;
  function slugFile() { return slugFileName || (slug + ".txt"); }

  function syncControls() {
    var segs = document.querySelectorAll("#langseg button");
    Array.prototype.forEach.call(segs, function (b) {
      b.setAttribute("aria-pressed", String(b.getAttribute("data-lang") === prefs.lang));
    });
    $("sumtoggle").checked = prefs.summaries;
  }

  function build() {
    $("loading").hidden = true;
    $("paper").hidden = false;
    $("bar").hidden = false;
    document.title = story.title + " | Graded Readers";
    var sel = $("chsel");
    story.chapterList.forEach(function (ch, i) {
      var o = document.createElement("option");
      o.value = "c" + (i + 1);
      var t = (i + 1) + ". " + ch.title;
      o.textContent = t.length > 34 ? t.slice(0, 33) + "…" : t;
      sel.appendChild(o);
    });
    sel.addEventListener("change", function () {
      var t = document.getElementById(sel.value);
      if (t) t.scrollIntoView({ behavior: "smooth", block: "start" });
    });
    if (story.french) $("langseg").hidden = false;
    else prefs.lang = "en";

    Array.prototype.forEach.call(document.querySelectorAll("#langseg button"), function (b) {
      b.addEventListener("click", function () { prefs.lang = b.getAttribute("data-lang"); save(); syncControls(); render(); });
    });
    $("smaller").addEventListener("click", function () { prefs.size -= 1.5; save(); applySize(); });
    $("larger").addEventListener("click", function () { prefs.size += 1.5; save(); applySize(); });
    $("sumtoggle").addEventListener("change", function (e) { prefs.summaries = e.target.checked; save(); render(); });
    applySize();
    syncControls();
    render();
    if (location.hash && /^#c\d+$/.test(location.hash)) {
      var t = document.querySelector(location.hash);
      if (t) t.scrollIntoView();
    }
  }

  fetch("data/stories/" + slug + ".json").then(function (r) {
    if (!r.ok) throw new Error("HTTP " + r.status);
    return r.json();
  }).then(function (d) {
    story = d;
    slugFileName = d.file || null;
    build();
  }).catch(function (e) {
    fail("Could not load this story (" + e.message + ").");
  });
})();
