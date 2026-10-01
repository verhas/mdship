// mdship site: copy buttons, mobile menu, sidebar filter, on-page highlight, terminal demo.
(function () {
  "use strict";

  function copyText(text, el) {
    if (!navigator.clipboard) return;
    navigator.clipboard.writeText(text).then(function () {
      el.classList.add("copied");
      var label = el.querySelector(".install-hint") || el;
      var old = label.textContent;
      label.textContent = "copied!";
      setTimeout(function () { el.classList.remove("copied"); label.textContent = old; }, 1600);
    });
  }

  document.querySelectorAll(".code .copy").forEach(function (btn) {
    btn.addEventListener("click", function () {
      copyText(btn.closest(".code").querySelector("pre").innerText, btn);
    });
  });
  document.querySelectorAll("[data-copy]").forEach(function (btn) {
    btn.addEventListener("click", function () { copyText(btn.getAttribute("data-copy"), btn); });
  });

  var toggle = document.querySelector(".menu-toggle");
  var sidebar = document.getElementById("sidebar");
  if (toggle && sidebar) {
    toggle.addEventListener("click", function () {
      var open = sidebar.classList.toggle("open");
      toggle.setAttribute("aria-expanded", String(open));
    });
  }

  var filter = document.querySelector("[data-nav-filter]");
  if (filter) {
    filter.addEventListener("input", function () {
      var q = filter.value.trim().toLowerCase();
      document.querySelectorAll(".sidebar li").forEach(function (li) {
        li.classList.toggle("nav-hidden", q !== "" && li.textContent.toLowerCase().indexOf(q) === -1);
      });
      document.querySelectorAll(".sidebar ul").forEach(function (ul) {
        var any = ul.querySelector("li:not(.nav-hidden)");
        ul.classList.toggle("nav-hidden", !any);
        var prev = ul.previousElementSibling;
        if (prev && prev.tagName === "H4") prev.classList.toggle("nav-hidden", !any);
      });
    });
  }

  // Bring the current page into view inside the sidebar only; scrollIntoView would also scroll the page.
  var current = document.querySelector('.sidebar a[aria-current="page"]');
  if (current && sidebar && sidebar.scrollHeight > sidebar.clientHeight) {
    sidebar.scrollTop = current.offsetTop - sidebar.offsetTop - sidebar.clientHeight / 2;
  }

  var links = document.querySelectorAll(".onpage a");
  if (links.length && "IntersectionObserver" in window) {
    var byId = {};
    links.forEach(function (a) { byId[a.getAttribute("href").slice(1)] = a; });
    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting && byId[entry.target.id]) {
          links.forEach(function (a) { a.classList.remove("active"); });
          byId[entry.target.id].classList.add("active");
        }
      });
    }, { rootMargin: "-80px 0px -70% 0px" });
    Object.keys(byId).forEach(function (id) {
      var el = document.getElementById(id);
      if (el) observer.observe(el);
    });
  }

  // Terminal demo: reveal lines one by one. Content is in the HTML, so it is
  // readable without JavaScript and for reduced-motion users.
  var term = document.querySelector("[data-typewriter]");
  var reduced = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (term && !reduced) {
    var lines = term.querySelectorAll("p");
    term.classList.add("is-typing");
    var i = 0;
    (function next() {
      if (i >= lines.length) return;
      lines[i].classList.add("shown");
      var isCmd = lines[i].classList.contains("t-cmd");
      i += 1;
      setTimeout(next, isCmd ? 650 : 900);
    })();
  }
})();
