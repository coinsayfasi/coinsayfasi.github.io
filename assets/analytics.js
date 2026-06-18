/* Tabserve — GA4 analytics (tek dosyadan yönetilir, tüm sayfalara <script defer> ile bağlı).
   GA4 mülkü: "Tabserve Web" (coinsayfasi.github.io). Tek kod 3 uygulamanın da
   site trafiğini sayar; raporda URL yoluna (/onebag/ /routevia-app/ /rentflow/) göre ayrılır. */
(function () {
  var ID = "G-EDZWXP6EEG";

  // gtag.js'i yükle
  var s = document.createElement("script");
  s.async = true;
  s.src = "https://www.googletagmanager.com/gtag/js?id=" + ID;
  document.head.appendChild(s);

  window.dataLayer = window.dataLayer || [];
  window.gtag = function () { dataLayer.push(arguments); };
  gtag("js", new Date());
  gtag("config", ID);

  // Store-intent ölçümü: /go/<app>/ linklerine tıklamayı "store_click" event'i olarak yolla.
  // (Bunlar aynı domainde olduğu için GA'nın otomatik "outbound" ölçümü yakalamaz.)
  document.addEventListener("click", function (e) {
    var a = e.target.closest && e.target.closest('a[href*="/go/"], a[href*="apps.apple.com"], a[href*="play.google.com"]');
    if (!a) return;
    var href = a.getAttribute("href") || "";
    var app = (href.match(/\/go\/([a-z]+)/) || [])[1]
           || (/apple\.com/.test(href) ? "appstore" : /play\.google/.test(href) ? "googleplay" : "store");
    gtag("event", "store_click", { app: app, link_url: href, page_path: location.pathname });
  }, { passive: true });
})();
