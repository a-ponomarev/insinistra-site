// Cookie consent + Meta Pixel.
// The Pixel script is loaded only after the visitor clicks "Accept"; nothing is sent to Meta before that.
// Pixel ID comes from content/site.yaml (meta_pixel_id) via the data-pixel attribute on this script tag.
//
// Events:
//   PageView                      every page (after consent)
//   ViewContent                   /shows/ page                         {content_name: 'Shows'}
//   InitiateCheckout              "Tickets" link in a concert list     {content_name, show_date, show_city, venue, destination}
//   FacebookEventClick (custom)   "Facebook" link in a concert list    {content_name, show_date, show_city, venue}
//   SocialClick (custom)          Instagram / Facebook page / TikTok / YouTube     {platform, placement}
//   ListenClick (custom)          Bandcamp / Spotify / Apple Music / YouTube Music {platform, placement}
//   Contact                       mailto: links                        {email_type: info|booking|press}
//   PressKitDownload (custom)     EPK downloads (press kit, stage plot) {file, placement}
(function () {
    var script = document.currentScript;
    var PIXEL_ID = script && script.getAttribute('data-pixel');
    if (!PIXEL_ID) return;

    var KEY = 'insinistra_consent';
    var MAX_AGE_MS = 365 * 24 * 3600 * 1000; // ask again after a year

    function readConsent() {
        try {
            var v = JSON.parse(localStorage.getItem(KEY) || 'null');
            if (v && (v.value === 'granted' || v.value === 'denied') && Date.now() - v.time < MAX_AGE_MS) return v.value;
        } catch (e) {}
        return null;
    }

    function saveConsent(value) {
        try { localStorage.setItem(KEY, JSON.stringify({ value: value, time: Date.now() })); } catch (e) {}
    }

    // ── Meta Pixel ────────────────────────────────────────────
    var pixelLoaded = false;

    function loadPixel() {
        if (pixelLoaded) return;
        pixelLoaded = true;
        /* Standard Meta Pixel base code */
        !function (f, b, e, v, n, t, s) {
            if (f.fbq) return; n = f.fbq = function () {
                n.callMethod ? n.callMethod.apply(n, arguments) : n.queue.push(arguments);
            };
            if (!f._fbq) f._fbq = n; n.push = n; n.loaded = !0; n.version = '2.0';
            n.queue = []; t = b.createElement(e); t.async = !0;
            t.src = v; s = b.getElementsByTagName(e)[0];
            s.parentNode.insertBefore(t, s);
        }(window, document, 'script', 'https://connect.facebook.net/en_US/fbevents.js');
        window.fbq('init', PIXEL_ID);
        window.fbq('track', 'PageView');
        if (/^\/(cs\/)?shows\/?/.test(location.pathname)) {
            window.fbq('track', 'ViewContent', { content_name: 'Shows' });
        }
    }

    function track(kind, name, params) {
        if (!pixelLoaded || !window.fbq) return;
        window.fbq(kind, name, params);
    }

    function deleteMetaCookies() {
        ['_fbp', '_fbc'].forEach(function (name) {
            var host = location.hostname;
            var domains = ['', host, '.' + host, '.' + host.replace(/^www\./, '')];
            domains.forEach(function (d) {
                document.cookie = name + '=; Max-Age=0; path=/' + (d ? '; domain=' + d : '');
            });
        });
    }

    // ── Click tracking ────────────────────────────────────────
    function placementOf(el) {
        if (el.closest('.social-sidebar')) return 'sidebar';
        if (el.closest('.site-footer')) return 'footer';
        if (el.closest('.site-header')) return 'header';
        var p = location.pathname.replace(/^\/|\/?(index\.html)?$/g, '');
        return p || 'home';
    }

    function showInfo(a) {
        var li = a.closest('li');
        if (!li) return {};
        var text = function (sel) { var n = li.querySelector(sel); return n ? n.textContent.trim() : ''; };
        var date = li.getAttribute('data-date') || '';
        var city = text('.col-city');
        var venue = text('.col-venue');
        return {
            content_name: [date, city, venue].filter(Boolean).join(' '),
            show_date: date,
            show_city: city,
            venue: venue
        };
    }

    var SOCIAL = [
        [/(^|\.)instagram\.com$/, 'instagram'],
        [/(^|\.)facebook\.com$|(^|\.)fb\.me$/, 'facebook'],
        [/(^|\.)tiktok\.com$/, 'tiktok'],
        [/^(www\.|m\.)?youtube\.com$|^youtu\.be$/, 'youtube']
    ];
    var LISTEN = [
        [/(^|\.)bandcamp\.com$/, 'bandcamp'],
        [/(^|\.)spotify\.com$/, 'spotify'],
        [/^music\.apple\.com$/, 'apple_music'],
        [/^music\.youtube\.com$/, 'youtube_music']
    ];

    function match(list, host) {
        for (var i = 0; i < list.length; i++) if (list[i][0].test(host)) return list[i][1];
        return null;
    }

    document.addEventListener('click', function (e) {
        if (!pixelLoaded) return;
        var a = e.target.closest && e.target.closest('a[href]');
        if (!a) return;
        var href = a.getAttribute('href');

        if (/^mailto:/i.test(href)) {
            var addr = href.slice(7).split('?')[0].toLowerCase();
            track('track', 'Contact', { email_type: addr.split('@')[0], placement: placementOf(a) });
            return;
        }

        if (a.classList.contains('epk-technical-link-icon')) {
            var file = (a.textContent || '').trim().toLowerCase().indexOf('stage') !== -1 ? 'stage_plot' : 'press_kit';
            track('trackCustom', 'PressKitDownload', { file: file, placement: placementOf(a) });
            return;
        }

        var url;
        try { url = new URL(a.href, location.href); } catch (err) { return; }
        if (url.host === location.host) return;
        var host = url.hostname.toLowerCase();

        if (a.closest('.concert-list')) {
            var info = showInfo(a);
            if (/(^|\.)facebook\.com$/.test(host) && /\/events\//.test(url.pathname)) {
                track('trackCustom', 'FacebookEventClick', info);
            } else {
                info.destination = host.replace(/^www\./, '');
                track('track', 'InitiateCheckout', info);
            }
            return;
        }

        var listen = match(LISTEN, host);
        if (listen) { track('trackCustom', 'ListenClick', { platform: listen, placement: placementOf(a) }); return; }
        var social = match(SOCIAL, host);
        if (social) { track('trackCustom', 'SocialClick', { platform: social, placement: placementOf(a) }); return; }
    }, true);

    // ── Banner ────────────────────────────────────────────────
    var banner = null;

    function hideBanner() { if (banner) banner.hidden = true; }

    function showBanner() {
        if (!banner) {
            banner = document.createElement('div');
            banner.className = 'consent-banner';
            banner.setAttribute('role', 'dialog');
            var tx = {};
            try { tx = JSON.parse(script.getAttribute('data-i18n') || '{}'); } catch (err) { tx = {}; }
            banner.setAttribute('aria-label', tx.label || 'Cookie consent');
            var privacy = script.getAttribute('data-privacy') || '/privacy/';
            banner.innerHTML =
                '<p class="consent-text">' + (tx.text || 'We\'re an independent band. Marketing cookies help us reach more people ' +
                'like you on social media — only if you allow it.') + ' <a href="' + privacy + '">' + (tx.more || 'More info') + '</a></p>' +
                '<div class="consent-actions">' +
                '<button type="button" class="btn btn-ghost" data-consent="denied">' + (tx.decline || 'Decline') + '</button>' +
                '<button type="button" class="btn btn-ghost" data-consent="granted">' + (tx.accept || 'Accept') + '</button>' +
                '</div>';
            banner.addEventListener('click', function (e) {
                var btn = e.target.closest('[data-consent]');
                if (!btn) return;
                var value = btn.getAttribute('data-consent');
                var wasLoaded = pixelLoaded;
                saveConsent(value);
                hideBanner();
                if (value === 'granted') loadPixel();
                else if (wasLoaded) { deleteMetaCookies(); location.reload(); }
            });
            document.body.appendChild(banner);
        }
        banner.hidden = false;
    }

    function init() {
        var c = readConsent();
        if (c === 'granted') loadPixel();
        else if (c === null) showBanner();

        Array.prototype.forEach.call(document.querySelectorAll('[data-consent-settings]'), function (el) {
            el.hidden = false;
            el.addEventListener('click', function (e) { e.preventDefault(); showBanner(); });
        });
    }

    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
    else init();
})();
