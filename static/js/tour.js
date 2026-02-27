/**
 * Inify Onboarding Tour — Professional Edition v2
 * جولة احترافية بتصميم عصري وواضح بدون ضبابية
 */
(function () {
    var LS_KEY  = 'inify_tour_step';
    var LS_DONE = 'inify_tour_done';

    /* ─── خطوات التور ─── */
    var STEPS = [
        null,
        {
            target  : null,
            position: 'center',
            stepNum : 0,
            total   : 3,
            color   : '#6bb8c9',
            icon    : 'wave',
            title   : 'أهلاً بك في Inify! 👋',
            desc    : 'سنرشدك خلال <strong>3 خطوات سريعة</strong> لتبدأ تحقيق أول صفقة مع وكيلك الذكي.',
            btnLabel: 'ابدأ الجولة',
            btnNext : 2,
            isLast  : false,
        },
        {
            target  : 'tour-quickactions',
            position: 'auto',
            stepNum : 1,
            total   : 3,
            color   : '#6bb8c9',
            icon    : 'home',
            title   : 'الخطوات الرئيسية',
            desc    : 'ابدأ بـ<strong>إضافة عقار</strong> لتغذية الوكيل، ثم <strong>إعدادات الوكيل</strong> لتخصيص الردود، ثم <strong>ربط الواتساب</strong> لاستقبال العملاء تلقائياً.',
            btnLabel: 'التالي',
            btnNext : 3,
            isLast  : false,
        },
        {
            target  : 'tour-stats',
            position: 'auto',
            stepNum : 2,
            total   : 3,
            color   : '#6bb8c9',
            icon    : 'chart',
            title   : 'إحصائيات نشاطك',
            desc    : 'تابع نمو أعمالك لحظة بلحظة — <strong>عقاراتك</strong>، <strong>العملاء المحتملين</strong>، <strong>المحادثات النشطة</strong>، والمهتمين بعقاراتك.',
            btnLabel: 'التالي',
            btnNext : 4,
            isLast  : false,
        },
        {
            target  : null,
            position: 'center',
            stepNum : 3,
            total   : 3,
            color   : '#25d366',
            icon    : 'check',
            title   : 'أنت جاهز للانطلاق! 🎯',
            desc    : 'ابدأ الآن بربط <strong>واتساب شركتك</strong> ليستقبل وكيلك الذكي رسائل العملاء ويرد عليهم تلقائياً على مدار الساعة.',
            btnLabel: 'ربط الواتساب الآن',
            btnNext : null,
            isLast  : true,
        },
    ];

    /* ─── SVG icons ─── */
    var ICONS = {
        wave : '<svg width="44" height="44" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/></svg>',
        home : '<svg width="44" height="44" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M3 9.5L12 3l9 6.5V20a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V9.5z"/><path d="M9 21V12h6v9"/></svg>',
        chart: '<svg width="44" height="44" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/><line x1="2" y1="20" x2="22" y2="20"/></svg>',
        check: '<svg width="44" height="44" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>',
    };

    /* ─── CSS ─── */
    var CSS = '\
/* ====== Tour Overlay ====== */\
#itSvgOverlay{position:fixed;inset:0;z-index:99990;pointer-events:all;}\
\
/* ====== Tour Card — Dark Mode (default) ====== */\
#itCard{\
  position:fixed;\
  z-index:99999;\
  width:390px;\
  max-width:calc(100vw - 32px);\
  direction:rtl;\
  background:linear-gradient(160deg,#1a2f4a 0%,#142238 100%);\
  border:1px solid rgba(107,184,201,.35);\
  border-radius:22px;\
  padding:0;\
  box-shadow:\
    0 0 0 1px rgba(107,184,201,.12),\
    0 24px 60px rgba(0,0,0,.7),\
    inset 0 1px 0 rgba(107,184,201,.08);\
  font-family:inherit;\
  overflow:hidden;\
}\
\
/* top accent bar */\
.it-accent-bar{\
  height:4px;\
  background:linear-gradient(90deg,#6bb8c9 0%,#4a9fb5 60%,rgba(107,184,201,0) 100%);\
  width:100%;\
}\
.it-accent-bar.green{\
  background:linear-gradient(90deg,#25d366 0%,#1aab52 60%,rgba(37,211,102,0) 100%);\
}\
\
/* card inner */\
.it-inner{padding:28px 26px 22px;}\
\
/* header row: icon + step dots */\
.it-header{display:flex;align-items:flex-start;justify-content:space-between;margin-bottom:20px;}\
\
/* icon box */\
.it-icon-wrap{\
  width:58px;height:58px;border-radius:16px;\
  display:flex;align-items:center;justify-content:center;\
  background:rgba(107,184,201,.14);\
  border:1px solid rgba(107,184,201,.3);\
  color:#7ecfdf;\
  flex-shrink:0;\
  box-shadow:0 0 20px rgba(107,184,201,.08);\
}\
.it-icon-wrap.green{\
  background:rgba(37,211,102,.12);\
  border-color:rgba(37,211,102,.3);\
  color:#2edb6f;\
  box-shadow:0 0 20px rgba(37,211,102,.08);\
}\
\
/* step dots */\
.it-dots{display:flex;gap:6px;align-items:center;padding-top:6px;}\
.it-dot{\
  width:8px;height:8px;border-radius:50%;\
  background:rgba(107,184,201,.18);\
  transition:all .35s cubic-bezier(.4,0,.2,1);\
}\
.it-dot.active{\
  background:#6bb8c9;\
  width:22px;\
  border-radius:4px;\
  box-shadow:0 0 8px rgba(107,184,201,.5);\
}\
.it-dot.done{background:rgba(107,184,201,.45);}\
.it-dot.green-active{\
  background:#25d366;\
  width:22px;\
  border-radius:4px;\
  box-shadow:0 0 8px rgba(37,211,102,.5);\
}\
\
/* title */\
#itCard h2{\
  color:#e8f4f8;\
  font-size:17px;\
  font-weight:800;\
  margin:0 0 10px;\
  line-height:1.45;\
  letter-spacing:-.2px;\
}\
\
/* description */\
#itCard p{\
  color:rgba(200,220,232,.75);\
  font-size:13.5px;\
  line-height:1.85;\
  margin:0 0 22px;\
}\
#itCard p strong{color:#7ecfdf;font-weight:700;}\
\
/* divider */\
.it-divider{\
  height:1px;\
  background:rgba(107,184,201,.1);\
  margin:0 0 18px;\
}\
\
/* progress */\
.it-prog-wrap{margin-bottom:20px;}\
.it-prog-label{\
  display:flex;justify-content:space-between;\
  align-items:center;margin-bottom:7px;\
}\
.it-prog-text{\
  font-size:11px;font-weight:700;\
  color:rgba(107,184,201,.65);\
  letter-spacing:.6px;text-transform:uppercase;\
}\
.it-prog-bar{\
  height:5px;\
  background:rgba(107,184,201,.1);\
  border-radius:6px;overflow:hidden;\
}\
.it-prog-fill{\
  height:100%;border-radius:6px;\
  background:linear-gradient(90deg,#4a9fb5,#6bb8c9);\
  transition:width .55s cubic-bezier(.4,0,.2,1);\
  box-shadow:0 0 8px rgba(107,184,201,.4);\
}\
.it-prog-fill.green{\
  background:linear-gradient(90deg,#1aab52,#25d366);\
  box-shadow:0 0 8px rgba(37,211,102,.4);\
}\
\
/* main button */\
.it-btn{\
  display:flex;align-items:center;justify-content:center;gap:8px;\
  width:100%;\
  background:linear-gradient(135deg,#4a9fb5 0%,#6bb8c9 100%);\
  color:#fff;\
  border:none;\
  border-radius:13px;\
  padding:14px 20px;\
  font-size:14px;font-weight:800;\
  cursor:pointer;font-family:inherit;\
  transition:all .2s ease;\
  box-sizing:border-box;\
  margin-bottom:10px;\
  letter-spacing:.3px;\
  box-shadow:0 4px 20px rgba(107,184,201,.3);\
}\
.it-btn:hover{\
  opacity:.92;\
  transform:translateY(-2px);\
  box-shadow:0 8px 28px rgba(107,184,201,.4);\
}\
.it-btn:active{transform:translateY(0);box-shadow:0 2px 10px rgba(107,184,201,.25);}\
.it-btn.green{\
  background:linear-gradient(135deg,#1aab52 0%,#25d366 100%);\
  box-shadow:0 4px 20px rgba(37,211,102,.3);\
}\
.it-btn.green:hover{box-shadow:0 8px 28px rgba(37,211,102,.4);}\
\
/* skip link */\
.it-skip{\
  background:none;border:none;\
  color:rgba(200,220,232,.28);\
  font-size:12px;\
  cursor:pointer;\
  width:100%;font-family:inherit;\
  transition:color .2s;\
  padding:6px;display:block;text-align:center;\
}\
.it-skip:hover{color:rgba(200,220,232,.6);}\
\
/* close ✕ button */\
.it-close{\
  position:absolute;top:15px;left:15px;\
  width:30px;height:30px;\
  border-radius:9px;\
  background:rgba(255,255,255,.05);\
  border:1px solid rgba(255,255,255,.1);\
  color:rgba(200,220,232,.4);\
  cursor:pointer;\
  display:flex;align-items:center;justify-content:center;\
  transition:all .2s;\
  font-family:inherit;font-size:14px;line-height:1;\
}\
.it-close:hover{\
  background:rgba(255,255,255,.1);\
  border-color:rgba(107,184,201,.3);\
  color:rgba(200,220,232,.8);\
}\
\
/* spotlight ring */\
#itRing{\
  position:fixed;\
  z-index:99995;\
  pointer-events:none;\
  border-radius:16px;\
  border:2px solid rgba(107,184,201,.95);\
  box-shadow:\
    0 0 0 4px rgba(107,184,201,.12),\
    0 0 28px rgba(107,184,201,.35);\
  transition:all .38s cubic-bezier(.4,0,.2,1);\
  animation:itPulseRing 2.4s ease-in-out infinite;\
}\
@keyframes itPulseRing{\
  0%,100%{\
    box-shadow:0 0 0 4px rgba(107,184,201,.12),0 0 24px rgba(107,184,201,.28);\
  }\
  50%{\
    box-shadow:0 0 0 8px rgba(107,184,201,.06),0 0 44px rgba(107,184,201,.4);\
  }\
}\
\
/* entry / exit animations */\
@keyframes itIn{\
  from{opacity:0;transform:scale(.93) translateY(12px)}\
  to{opacity:1;transform:scale(1) translateY(0)}\
}\
@keyframes itOut{\
  from{opacity:1;transform:scale(1) translateY(0)}\
  to{opacity:0;transform:scale(.95) translateY(6px)}\
}\
#itCard.it-entering{animation:itIn .32s cubic-bezier(.34,1.26,.64,1) forwards;}\
#itCard.it-leaving{animation:itOut .22s ease forwards;}\
\
/* ══════════════════════════════════════\
   Light mode overrides\
══════════════════════════════════════ */\
body.light-mode #itCard{\
  background:#ffffff;\
  border-color:rgba(37,99,235,.2);\
  box-shadow:\
    0 0 0 1px rgba(37,99,235,.06),\
    0 20px 60px rgba(0,0,0,.1),\
    inset 0 1px 0 rgba(255,255,255,.8);\
}\
body.light-mode .it-accent-bar{\
  background:linear-gradient(90deg,#2563EB,#3B82F6,rgba(59,130,246,0));\
}\
body.light-mode .it-accent-bar.green{\
  background:linear-gradient(90deg,#16A34A,#22C55E,rgba(34,197,94,0));\
}\
body.light-mode .it-icon-wrap{\
  background:rgba(37,99,235,.07);\
  border-color:rgba(37,99,235,.18);\
  color:#2563EB;\
  box-shadow:none;\
}\
body.light-mode .it-icon-wrap.green{\
  background:rgba(22,163,74,.07);\
  border-color:rgba(22,163,74,.18);\
  color:#16A34A;\
  box-shadow:none;\
}\
body.light-mode .it-dot{background:rgba(37,99,235,.15);}\
body.light-mode .it-dot.active{background:#2563EB;box-shadow:none;}\
body.light-mode .it-dot.done{background:rgba(37,99,235,.35);}\
body.light-mode .it-dot.green-active{background:#16A34A;box-shadow:none;}\
body.light-mode .it-divider{background:rgba(37,99,235,.08);}\
body.light-mode #itCard h2{color:#111827;}\
body.light-mode #itCard p{color:#4B5563;}\
body.light-mode #itCard p strong{color:#2563EB;}\
body.light-mode .it-prog-text{color:rgba(37,99,235,.6);}\
body.light-mode .it-prog-bar{background:rgba(37,99,235,.08);}\
body.light-mode .it-prog-fill{\
  background:linear-gradient(90deg,#2563EB,#3B82F6);\
  box-shadow:none;\
}\
body.light-mode .it-prog-fill.green{\
  background:linear-gradient(90deg,#16A34A,#22C55E);\
  box-shadow:none;\
}\
body.light-mode .it-btn{\
  background:linear-gradient(135deg,#2563EB,#3B82F6);\
  box-shadow:0 4px 16px rgba(37,99,235,.25);\
}\
body.light-mode .it-btn:hover{box-shadow:0 8px 24px rgba(37,99,235,.35);}\
body.light-mode .it-btn.green{\
  background:linear-gradient(135deg,#16A34A,#22C55E);\
  box-shadow:0 4px 16px rgba(22,163,74,.25);\
}\
body.light-mode .it-skip{color:rgba(31,41,55,.28);}\
body.light-mode .it-skip:hover{color:rgba(31,41,55,.6);}\
body.light-mode .it-close{\
  background:rgba(0,0,0,.04);\
  border-color:rgba(0,0,0,.1);\
  color:rgba(0,0,0,.35);\
}\
body.light-mode .it-close:hover{\
  background:rgba(0,0,0,.08);\
  border-color:rgba(37,99,235,.25);\
  color:rgba(0,0,0,.65);\
}\
body.light-mode #itRing{\
  border-color:rgba(37,99,235,.85);\
  box-shadow:\
    0 0 0 4px rgba(37,99,235,.1),\
    0 0 24px rgba(37,99,235,.2);\
}\
';

    /* ─── inject CSS ─── */
    function injectCSS() {
        if (document.getElementById('it-css')) return;
        var s = document.createElement('style');
        s.id = 'it-css';
        s.textContent = CSS;
        document.head.appendChild(s);
    }

    /* ─── SVG overlay (crisp cutout — no blur) ─── */
    var _svgNS = 'http://www.w3.org/2000/svg';
    function buildSvgOverlay() {
        var existing = document.getElementById('itSvgOverlay');
        if (existing) return existing;
        var svg = document.createElementNS(_svgNS, 'svg');
        svg.setAttribute('id', 'itSvgOverlay');
        svg.setAttribute('xmlns', _svgNS);
        /* defs: clip path with hole */
        var defs = document.createElementNS(_svgNS, 'defs');
        var mask = document.createElementNS(_svgNS, 'mask');
        mask.setAttribute('id', 'itMask');
        /* white full rect = visible (dark) */
        var bg = document.createElementNS(_svgNS, 'rect');
        bg.setAttribute('id', 'itMaskBg');
        bg.setAttribute('fill', 'white');
        /* black hole = transparent (spotlight) */
        var hole = document.createElementNS(_svgNS, 'rect');
        hole.setAttribute('id', 'itMaskHole');
        hole.setAttribute('fill', 'black');
        hole.setAttribute('rx', '16');
        mask.appendChild(bg);
        mask.appendChild(hole);
        defs.appendChild(mask);
        /* dark rect with mask */
        var darkRect = document.createElementNS(_svgNS, 'rect');
        darkRect.setAttribute('id', 'itDarkRect');
        darkRect.setAttribute('fill', 'rgba(0,0,0,0.72)');
        darkRect.setAttribute('mask', 'url(#itMask)');
        svg.appendChild(defs);
        svg.appendChild(darkRect);
        document.body.appendChild(svg);
        return svg;
    }

    function updateSvgSize() {
        var svg = document.getElementById('itSvgOverlay');
        if (!svg) return;
        var W = window.innerWidth, H = window.innerHeight;
        svg.setAttribute('width', W);
        svg.setAttribute('height', H);
        svg.setAttribute('viewBox', '0 0 ' + W + ' ' + H);
        document.getElementById('itMaskBg').setAttribute('width', W);
        document.getElementById('itMaskBg').setAttribute('height', H);
        document.getElementById('itDarkRect').setAttribute('width', W);
        document.getElementById('itDarkRect').setAttribute('height', H);
    }

    function setSpotlightHole(x, y, w, h, rx) {
        var hole = document.getElementById('itMaskHole');
        if (!hole) return;
        hole.setAttribute('x', x);
        hole.setAttribute('y', y);
        hole.setAttribute('width', w);
        hole.setAttribute('height', h);
        hole.setAttribute('rx', rx);
    }

    function clearSpotlightHole() {
        /* hole at 0,0 size 0 = full dark */
        setSpotlightHole(0, 0, 0, 0, 0);
        var ring = document.getElementById('itRing');
        if (ring) ring.style.display = 'none';
    }

    /* ─── build DOM ─── */
    function buildDOM() {
        if (document.getElementById('itCard')) return;
        injectCSS();

        buildSvgOverlay();
        updateSvgSize();

        /* pulse ring */
        var ring = document.createElement('div');
        ring.id = 'itRing';
        ring.style.display = 'none';
        document.body.appendChild(ring);

        /* card */
        var card = document.createElement('div');
        card.id = 'itCard';
        card.style.display = 'none';
        document.body.appendChild(card);
    }

    /* ─── spotlight element ─── */
    function spotlight(el, padding) {
        padding = padding || 14;
        var r = el.getBoundingClientRect();
        var elCenter = r.top + r.height / 2;
        var winH = window.innerHeight;

        if (elCenter < 80 || elCenter > winH - 80) {
            el.scrollIntoView({ behavior: 'smooth', block: 'center' });
            setTimeout(function () { spotlight(el, padding); }, 400);
            return null;
        }

        updateSvgSize();
        var x = r.left - padding;
        var y = r.top  - padding;
        var w = r.width  + padding * 2;
        var h = r.height + padding * 2;
        var rx = Math.min(parseFloat(getComputedStyle(el).borderRadius) || 12, 20) + 4;

        setSpotlightHole(x, y, w, h, rx);

        var ring = document.getElementById('itRing');
        ring.style.display    = 'block';
        ring.style.left       = x + 'px';
        ring.style.top        = y + 'px';
        ring.style.width      = w + 'px';
        ring.style.height     = h + 'px';
        ring.style.borderRadius = rx + 'px';

        return { x: x, y: y, w: w, h: h };
    }

    /* ─── position card smart ─── */
    function positionCard(rect) {
        var card = document.getElementById('itCard');
        var cW = card.offsetWidth  || 380;
        var cH = card.offsetHeight || 320;
        var vW = window.innerWidth;
        var vH = window.innerHeight;
        var margin = 20;
        var top, left;

        if (!rect) {
            top  = (vH - cH) / 2;
            left = (vW - cW) / 2;
        } else {
            /* prefer below */
            if (rect.y + rect.h + cH + margin < vH) {
                top = rect.y + rect.h + margin;
            } else if (rect.y - cH - margin > 0) {
                top = rect.y - cH - margin;
            } else {
                top = margin;
            }
            /* horizontal center on element, clamp to screen */
            left = rect.x + rect.w / 2 - cW / 2;
            left = Math.max(margin, Math.min(vW - cW - margin, left));
        }

        card.style.top  = Math.round(top)  + 'px';
        card.style.left = Math.round(left) + 'px';
    }

    /* ─── render card content ─── */
    function renderCard(step) {
        var d = STEPS[step];
        if (!d) return;
        var card = document.getElementById('itCard');
        var isGreen = d.color === '#25d366';
        var iconSvg = ICONS[d.icon] || ICONS.home;
        var pct = Math.round((d.stepNum / d.total) * 100);

        /* dots */
        var dotsHtml = '';
        for (var i = 0; i < d.total; i++) {
            if (i < d.stepNum) {
                dotsHtml += '<span class="it-dot done"></span>';
            } else if (i === d.stepNum) {
                dotsHtml += '<span class="it-dot ' + (isGreen ? 'green-active' : 'active') + '"></span>';
            } else {
                dotsHtml += '<span class="it-dot"></span>';
            }
        }

        var skipHtml = d.isLast
            ? '<button class="it-skip" id="itSkip">إنهاء الجولة</button>'
            : '<button class="it-skip" id="itSkip">تخطي الجولة</button>';

        var btnArrow = d.isLast
            ? '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>'
            : '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><polyline points="9 18 15 12 9 6"/></svg>';

        card.innerHTML = [
            '<div class="it-accent-bar' + (isGreen ? ' green' : '') + '"></div>',
            '<button class="it-close" id="itClose" title="إغلاق">✕</button>',
            '<div class="it-inner">',
              '<div class="it-header">',
                '<div class="it-icon-wrap' + (isGreen ? ' green' : '') + '">' + iconSvg + '</div>',
                '<div class="it-dots">' + dotsHtml + '</div>',
              '</div>',
              '<h2>' + d.title + '</h2>',
              '<p>' + d.desc + '</p>',
              '<div class="it-prog-wrap">',
                '<div class="it-prog-label">',
                  '<span class="it-prog-text">التقدم</span>',
                  '<span class="it-prog-text">' + pct + '%</span>',
                '</div>',
                '<div class="it-prog-bar">',
                  '<div class="it-prog-fill' + (isGreen ? ' green' : '') + '" style="width:' + pct + '%"></div>',
                '</div>',
              '</div>',
              '<button class="it-btn' + (isGreen ? ' green' : '') + '" id="itNext">',
                d.btnLabel,
                btnArrow,
              '</button>',
              skipHtml,
            '</div>',
        ].join('');

        document.getElementById('itNext').onclick = function () {
            if (d.isLast) {
                TOUR.finish('/dashboard/bot-settings/#whatsapp');
            } else {
                TOUR.goStep(d.btnNext);
            }
        };
        document.getElementById('itSkip').onclick = function () {
            TOUR.skip();
        };
        document.getElementById('itClose').onclick = function () {
            TOUR.skip();
        };
    }

    /* ─── Public API ─── */
    var TOUR = window.TOUR = {

        _saveDB: function () {
            var csrf = (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] || '';
            fetch('/api/tour/complete/', {
                method: 'POST',
                headers: { 'X-CSRFToken': csrf, 'Content-Type': 'application/json' }
            }).catch(function () {});
        },

        _destroyDOM: function () {
            ['itSvgOverlay','itRing','itCard'].forEach(function (id) {
                var el = document.getElementById(id);
                if (el) el.remove();
            });
        },

        _hideAll: function (cb) {
            var card = document.getElementById('itCard');
            if (card) {
                card.classList.add('it-leaving');
                setTimeout(function () {
                    TOUR._destroyDOM();
                    if (cb) cb();
                }, 220);
            } else {
                TOUR._destroyDOM();
                if (cb) cb();
            }
        },

        goStep: function (step) {
            localStorage.setItem(LS_KEY, step);
            buildDOM();
            var d = STEPS[step];
            if (!d) return;

            var card = document.getElementById('itCard');
            card.classList.remove('it-leaving', 'it-entering');

            var rect = null;
            if (d.target) {
                var el = document.getElementById(d.target);
                if (el) {
                    rect = spotlight(el);
                } else {
                    clearSpotlightHole();
                }
            } else {
                clearSpotlightHole();
            }

            renderCard(step);
            card.style.display = 'block';

            setTimeout(function () {
                positionCard(rect);
                card.classList.add('it-entering');
                setTimeout(function () { card.classList.remove('it-entering'); }, 350);
            }, 20);
        },

        finish: function (redirectUrl) {
            localStorage.setItem(LS_DONE, '1');
            localStorage.removeItem(LS_KEY);
            this._saveDB();
            this._hideAll(function () {
                if (redirectUrl) window.location.href = redirectUrl;
            });
        },

        skip: function () {
            localStorage.setItem(LS_DONE, '1');
            localStorage.removeItem(LS_KEY);
            this._saveDB();
            this._hideAll();
        },

        restart: function () {
            localStorage.removeItem(LS_DONE);
            localStorage.setItem(LS_KEY, '1');
            this._destroyDOM();
            setTimeout(function () { TOUR.goStep(1); }, 50);
        },

        autoStart: function () {
            if (localStorage.getItem(LS_DONE) === '1') return;
            var step = parseInt(localStorage.getItem(LS_KEY) || '1');
            if (step < 1 || step > 4) step = 1;
            setTimeout(function () { TOUR.goStep(step); }, 600);
        },

        resumeIfPending: function () {
            if (localStorage.getItem(LS_DONE) === '1') return;
            var step = parseInt(localStorage.getItem(LS_KEY) || '0');
            if (step >= 1 && step <= 4) {
                setTimeout(function () { TOUR.goStep(step); }, 600);
            }
        }
    };

    /* resize: update SVG dimensions */
    window.addEventListener('resize', function () {
        if (document.getElementById('itSvgOverlay')) updateSvgSize();
    });

    window.startTourFromSidebar = function () { TOUR.restart(); };

    document.addEventListener('DOMContentLoaded', function () {
        TOUR.resumeIfPending();
    });

})();
