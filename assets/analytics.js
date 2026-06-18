/* Tabserve — store-click tracking.
   The GA4 base tag (gtag.js + config G-EDZWXP6EEG) is the standard inline snippet
   placed in each page's <head> (so Google detects it). This file ONLY adds the
   custom "store_click" event — it does not load gtag again (no double tag). */
(function () {
  if (typeof window.gtag !== "function") return;
  document.addEventListener("click", function (e) {
    var a = e.target.closest && e.target.closest('a[href*="/go/"], a[href*="apps.apple.com"], a[href*="play.google.com"]');
    if (!a) return;
    var href = a.getAttribute("href") || "";
    var app = (href.match(/\/go\/([a-z]+)/) || [])[1]
           || (/apple\.com/.test(href) ? "appstore" : /play\.google/.test(href) ? "googleplay" : "store");
    gtag("event", "store_click", { app: app, link_url: href, page_path: location.pathname });
  }, { passive: true });
})();
