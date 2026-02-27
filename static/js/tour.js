/**
 * Inify Onboarding Tour — Spotlight Edition
 * تور احترافي بتظليل العناصر على الصفحة
 */
(function () {
    var LS_KEY  = 'inify_tour_step';
    var LS_DONE = 'inify_tour_done';

    /* ─── تعريف خطوات التور ─── */
    var STEPS = [
        null,
        {
            /* خطوة الترحيب — بدون spotlight */
            target  : null,
            position: 'center',
            badge   : '👋 أهلاً بك في Inify',
            icon    : '<svg width="52" height="52" viewBox="0 0 24 24" fill="none" stroke="#6bb8c9" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="8" r="4"/><path d="M4 20c0-4 3.6-7 8-7s8 3 8 7"/><path d="M17 11l2 2 4-4" stroke="#25d366"/></svg>',
            title   : 'مرحباً! سنرشدك خلال 3 خطوات',
            desc    : 'في هذه الجولة ستتعرف على أهم خصائص النظام لتبدأ تحقيق أول صفقة مع وكيلك الذكي.',
            progress: 0,
            step    : '1 / 4',
            btnLabel: 'ابدأ الجولة',
            btnNext : 2,
            isLast  : false,
        },
        {
            target  : 'tour-quickactions',
            position: 'auto',
            badge   : 'الخطوة 1 من 3',
            icon    : '<svg width="52" height="52" viewBox="0 0 24 24" fill="none" stroke="#6bb8c9" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M3 9.5L12 3l9 6.5V20a1 1 0 01-1 1H4a1 1 0 01-1-1V9.5z"/><path d="M9 21V12h6v9"/></svg>',
            title   : 'الخطوات الرئيسية',
            desc    : 'هنا تجد الخطوات الأساسية للبدء: <strong>إضافة عقار</strong> لتغذية الوكيل بمعلومات العقارات، ثم <strong>إعدادات الوكيل</strong> لتخصيص طريقة الرد، ثم <strong>ربط الواتساب</strong> لاستقبال العملاء تلقائياً.',
            progress: 25,
            step    : '2 / 4',
            btnLabel: 'التالي',
            btnNext : 3,
            isLast  : false,
        },
        {
            target  : 'tour-stats',
            position: 'auto',
            badge   : 'الخطوة 2 من 3',
            icon    : '<svg width="52" height="52" viewBox="0 0 24 24" fill="none" stroke="#6bb8c9" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>',
            title   : 'إحصائيات نشاطك',
            desc    : 'تتبّع نمو أعمالك في الوقت الفعلي — عدد العقارات المُضافة، العملاء المحتملين، المحادثات النشطة، والمهتمين بعقاراتك.',
            progress: 58,
            step    : '3 / 4',
            btnLabel: 'التالي',
            btnNext : 4,
            isLast  : false,
        },
        {
            target  : null,
            position: 'center',
            badge   : '🎯 جاهز للانطلاق!',
            icon    : '<svg width="52" height="52" viewBox="0 0 24 24" fill="none" stroke="#25d366" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>',
            title   : 'أنت جاهز للانطلاق!',
            desc    : 'ابدأ الآن بربط واتساب شركتك ليستقبل وكيلك الذكي رسائل العملاء ويرد عليهم تلقائياً على مدار الساعة.',
            progress: 100,
            step    : '4 / 4',
            btnLabel: 'اذهب لربط الواتساب ←',
            btnNext : null,
            isLast  : true,
        },
    ];

    /* ─── CSS ─── */
    var CSS = [
        /* بطاقة التور */
        '#itCard{position:fixed;z-index:99999;width:360px;max-width:92vw;direction:rtl;',
        'background:linear-gradient(145deg,#0d1b2e,#0a1525);',
        'border:1px solid rgba(107,184,201,.3);border-radius:20px;',
        'padding:28px 26px 22px;box-shadow:0 24px 64px rgba(0,0,0,.7),0 0 0 1px rgba(107,184,201,.08);',
        'font-family:inherit;transition:top .4s cubic-bezier(.4,0,.2,1),left .4s cubic-bezier(.4,0,.2,1);}',
        /* pulse ring حول العنصر المضاء */
        '#itRing{position:fixed;z-index:99991;border-radius:inherit;pointer-events:none;',
        'box-shadow:0 0 0 3px rgba(107,184,201,.7),0 0 0 6px rgba(107,184,201,.25),0 0 30px rgba(107,184,201,.15);',
        'transition:all .4s cubic-bezier(.4,0,.2,1);animation:itPulse 2s ease-in-out infinite;}',
        '@keyframes itPulse{0%,100%{box-shadow:0 0 0 3px rgba(107,184,201,.7),0 0 0 6px rgba(107,184,201,.25),0 0 30px rgba(107,184,201,.15);}',
        '50%{box-shadow:0 0 0 4px rgba(107,184,201,.9),0 0 0 10px rgba(107,184,201,.2),0 0 50px rgba(107,184,201,.2);}}',
        /* arrow connector */
        '#itArrow{position:fixed;z-index:99998;width:0;height:0;pointer-events:none;}',
        /* badge */
        '.it-badge{display:inline-flex;align-items:center;gap:6px;background:rgba(107,184,201,.1);',
        'border:1px solid rgba(107,184,201,.3);color:#6bb8c9;font-size:12px;font-weight:700;',
        'padding:4px 12px;border-radius:20px;margin-bottom:14px;}',
        /* icon */
        '.it-icon{display:flex;justify-content:center;margin-bottom:14px;}',
        /* texts */
        '#itCard h2{color:#f8f8f8;font-size:18px;font-weight:800;margin:0 0 10px;line-height:1.4;}',
        '#itCard p{color:rgba(248,248,248,.6);font-size:13.5px;line-height:1.75;margin:0 0 18px;}',
        /* progress */
        '.it-progress{height:3px;background:rgba(107,184,201,.12);border-radius:2px;margin-bottom:18px;overflow:hidden;}',
        '.it-progress-fill{height:100%;background:linear-gradient(90deg,#6bb8c9,#4a9fb5);border-radius:2px;transition:width .5s ease;}',
        /* step counter */
        '.it-meta{display:flex;align-items:center;justify-content:space-between;margin-bottom:16px;}',
        '.it-step{color:rgba(107,184,201,.6);font-size:12px;font-weight:600;}',
        /* buttons */
        '.it-btn{display:flex;align-items:center;justify-content:center;gap:8px;width:100%;',
        'background:linear-gradient(135deg,#6bb8c9,#4a9fb5);color:#fff;border:none;border-radius:11px;',
        'padding:13px 20px;font-size:14px;font-weight:700;cursor:pointer;font-family:inherit;',
        'transition:all .2s;box-sizing:border-box;margin-bottom:10px;}',
        '.it-btn:hover{opacity:.88;transform:translateY(-1px);}',
        '.it-skip{background:none;border:none;color:rgba(248,248,248,.3);font-size:12px;',
        'cursor:pointer;width:100%;font-family:inherit;transition:color .2s;padding:4px;}',
        '.it-skip:hover{color:rgba(248,248,248,.6);}',
        /* animations */
        '@keyframes itIn{from{opacity:0;transform:scale(.94) translateY(6px)}to{opacity:1;transform:scale(1) translateY(0)}}',
        '@keyframes itOut{from{opacity:1;transform:scale(1)}to{opacity:0;transform:scale(.94)}}',
        '#itCard.it-entering{animation:itIn .3s ease forwards;}',
        '#itCard.it-leaving{animation:itOut .2s ease forwards;}',
    ].join('');

    /* ─── inject CSS once ─── */
    function injectCSS() {
        if (document.getElementById('it-css')) return;
        var s = document.createElement('style');
        s.id = 'it-css';
        s.textContent = CSS;
        document.head.appendChild(s);
    }

    /* ─── build DOM elements ─── */
    function buildDOM() {
        if (document.getElementById('itCard')) return;
        injectCSS();

        /* full-screen dark backdrop */
        var ov = document.createElement('div');
        ov.id = 'itOverlay';
        document.body.appendChild(ov);

        /* highlight box — sits ON TOP of overlay, transparent itself, box-shadow creates dark surround */
        var hl = document.createElement('div');
        hl.id = 'itHighlight';
        hl.style.cssText = 'display:none;position:fixed;z-index:99992;pointer-events:none;border-radius:16px;transition:all .35s cubic-bezier(.4,0,.2,1);';
        document.body.appendChild(hl);

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

    /* ─── spotlight on element ─── */
    function spotlight(el, padding) {
        padding = padding || 16;
        var r = el.getBoundingClientRect();

        /* scroll element into view smoothly */
        var elCenter = r.top + r.height / 2;
        var winH = window.innerHeight;
        if (elCenter < 100 || elCenter > winH - 100) {
            el.scrollIntoView({ behavior: 'smooth', block: 'center' });
            /* wait for scroll then recalculate */
            setTimeout(function () { spotlight(el, padding); }, 380);
            return null;
        }

        var x = r.left - padding;
        var y = r.top  - padding;
        var w = r.width  + padding * 2;
        var h = r.height + padding * 2;
        var borderR = Math.min(parseFloat(getComputedStyle(el).borderRadius) || 16, 24) + 4;

        /* overlay: full screen dark */
        var ov = document.getElementById('itOverlay');
        ov.style.cssText = 'position:fixed;inset:0;z-index:99991;background:rgba(0,0,0,0.75);backdrop-filter:blur(2px);pointer-events:all;';

        /* highlight: punches out the element — uses massive box-shadow to darken outside */
        var hl = document.getElementById('itHighlight');
        hl.style.display  = 'block';
        hl.style.left     = x + 'px';
        hl.style.top      = y + 'px';
        hl.style.width    = w + 'px';
        hl.style.height   = h + 'px';
        hl.style.borderRadius = borderR + 'px';
        /* huge inset-like shadow to cut through overlay */
        hl.style.boxShadow = '0 0 0 9999px rgba(0,0,0,0.75)';
        hl.style.background = 'transparent';

        /* ring */
        var ring = document.getElementById('itRing');
        ring.style.display = 'block';
        ring.style.left    = x + 'px';
        ring.style.top     = y + 'px';
        ring.style.width   = w + 'px';
        ring.style.height  = h + 'px';
        ring.style.borderRadius = borderR + 'px';

        return { x: x, y: y, w: w, h: h };
    }

    /* ─── remove spotlight ─── */
    function clearSpotlight() {
        var ov = document.getElementById('itOverlay');
        var hl = document.getElementById('itHighlight');
        var ring = document.getElementById('itRing');

        if (hl)   hl.style.display  = 'none';
        if (ring) ring.style.display = 'none';

        /* solid dark backdrop for center steps */
        if (ov) {
            ov.style.cssText = 'position:fixed;inset:0;z-index:99991;background:rgba(0,0,0,0.75);backdrop-filter:blur(4px);pointer-events:all;';
        }
    }

    /* ─── position card near spotlight ─── */
    function positionCard(rect) {
        var card = document.getElementById('itCard');
        var cW = card.offsetWidth  || 360;
        var cH = card.offsetHeight || 300;
        var vW = window.innerWidth;
        var vH = window.innerHeight;
        var margin = 20;
        var top, left;

        if (!rect) {
            /* center of screen */
            top  = (vH - cH) / 2;
            left = (vW - cW) / 2;
        } else {
            /* try below */
            if (rect.y + rect.h + cH + margin < vH) {
                top = rect.y + rect.h + margin;
            } else if (rect.y - cH - margin > 0) {
                /* above */
                top = rect.y - cH - margin;
            } else {
                top = margin;
            }
            /* horizontal: prefer right side if room, else left */
            if (rect.x + rect.w / 2 + cW / 2 + margin < vW) {
                left = Math.max(margin, rect.x + rect.w / 2 - cW / 2);
            } else {
                left = Math.max(margin, vW - cW - margin);
            }
        }
        card.style.top  = top  + 'px';
        card.style.left = left + 'px';
    }

    /* ─── render step card content ─── */
    function renderCard(step) {
        var d = STEPS[step];
        if (!d) return;
        var card = document.getElementById('itCard');

        var skipHtml = d.isLast
            ? '<button class="it-skip" id="itSkip">إنهاء الجولة ✓</button>'
            : '<button class="it-skip" id="itSkip">تخطي الجولة</button>';

        card.innerHTML = [
            '<div class="it-badge">' + d.badge + '</div>',
            '<div class="it-icon">' + d.icon + '</div>',
            '<h2>' + d.title + '</h2>',
            '<p>' + d.desc + '</p>',
            '<div class="it-meta">',
              '<div class="it-progress" style="flex:1;margin-left:12px;"><div class="it-progress-fill" style="width:' + d.progress + '%"></div></div>',
              '<span class="it-step">' + d.step + '</span>',
            '</div>',
            '<button class="it-btn" id="itNext">' + d.btnLabel,
            d.isLast ? '' : ' <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="9 18 15 12 9 6"/></svg>',
            '</button>',
            skipHtml,
        ].join('');

        document.getElementById('itNext').onclick = function () {
            if (d.isLast) {
                TOUR.finish('/dashboard/bot-settings/?tab=whatsapp');
            } else {
                TOUR.goStep(d.btnNext);
            }
        };
        document.getElementById('itSkip').onclick = function () {
            if (d.isLast) TOUR.finish(null);
            else TOUR.skip();
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
            ['itOverlay','itHighlight','itRing','itCard'].forEach(function (id) {
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
            card.classList.remove('it-leaving','it-entering');

            var rect = null;
            if (d.target) {
                var el = document.getElementById(d.target);
                if (el) {
                    rect = spotlight(el);
                } else {
                    clearSpotlight();
                }
            } else {
                clearSpotlight();
            }

            renderCard(step);
            card.style.display = 'block';

            /* position then animate */
            setTimeout(function () {
                positionCard(rect);
                card.classList.add('it-entering');
                setTimeout(function () { card.classList.remove('it-entering'); }, 320);
            }, 30);
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
            setTimeout(function () { TOUR.goStep(step); }, 500);
        },

        resumeIfPending: function () {
            if (localStorage.getItem(LS_DONE) === '1') return;
            var step = parseInt(localStorage.getItem(LS_KEY) || '0');
            if (step >= 1 && step <= 4) {
                setTimeout(function () { TOUR.goStep(step); }, 500);
            }
        }
    };

    window.startTourFromSidebar = function () { TOUR.restart(); };

    document.addEventListener('DOMContentLoaded', function () {
        TOUR.resumeIfPending();
    });

})();
