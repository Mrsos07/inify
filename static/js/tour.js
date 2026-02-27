/**
 * Inify Onboarding Tour
 * يعمل من أي صفحة في الداشبورد
 */
(function () {
    var LS_KEY  = 'inify_tour_step';
    var LS_DONE = 'inify_tour_done';

    var STEPS = [
        null, // index 0 unused
        {
            badge : '🎉 مرحباً بك في Inify',
            icon  : '🤖',
            title : 'جولة تعريفية بنظام Inify',
            desc  : 'سنرشدك خلال الخصائص الرئيسية لتشغيل وكيلك الذكي وتحقيق أول صفقة.',
            progress: 0,
            dots  : [false, false, false],
            btnLabel: 'ابدأ الجولة',
            btnAction: function () { TOUR.goStep(2); },
            skipLabel: 'تخطي الجولة التعريفية',
        },
        {
            badge : 'الخطوة 1 من 3',
            icon  : '🏠',
            title : 'إضافة العقارات',
            desc  : 'من صفحة العقارات يمكنك إضافة عقاراتك بكافة تفاصيلها ليقترحها الوكيل الذكي على كل عميل تلقائياً.',
            progress: 33,
            dots  : [true, false, false],
            btnLabel: 'اذهب لإضافة عقار',
            btnAction: function () { TOUR.navigate('/dashboard/properties/', 3); },
            skipLabel: 'تخطي الجولة التعريفية',
        },
        {
            badge : 'الخطوة 2 من 3',
            icon  : '⚙️',
            title : 'إعدادات الوكيل الذكي',
            desc  : 'من إعدادات الوكيل أضف سياق شركتك ومعلوماتها وتعليمات الرد حتى يعمل الوكيل باحترافية باسمك.',
            progress: 66,
            dots  : [true, true, false],
            btnLabel: 'اذهب لإعدادات الوكيل',
            btnAction: function () { TOUR.navigate('/dashboard/bot-settings/', 4); },
            skipLabel: 'تخطي الجولة التعريفية',
        },
        {
            badge : 'الخطوة 3 من 3 🎯',
            icon  : '📱',
            title : 'ربط الواتساب',
            desc  : 'اربط واتساب شركتك ليبدأ وكيلك الذكي استقبال رسائل العملاء والرد عليهم تلقائياً على مدار الساعة.',
            progress: 100,
            dots  : [true, true, true],
            btnLabel: 'اذهب لربط الواتساب',
            btnAction: function () { TOUR.finish('/dashboard/bot-settings/?tab=whatsapp'); },
            skipLabel: 'إنهاء الجولة ✓',
        }
    ];

    /* ── CSS ── */
    var CSS = [
        '.tour-overlay{position:fixed;inset:0;background:rgba(0,0,0,.82);backdrop-filter:blur(6px);',
        'z-index:999999;display:none;align-items:center;justify-content:center;}',
        '.tour-overlay.tour-visible{display:flex;animation:tourIn .35s ease forwards;}',
        '.tour-overlay.tour-hiding{display:flex;animation:tourOut .28s ease forwards;}',
        '@keyframes tourIn{from{opacity:0;transform:scale(.96)}to{opacity:1;transform:scale(1)}}',
        '@keyframes tourOut{from{opacity:1;transform:scale(1)}to{opacity:0;transform:scale(.96)}}',
        '.tour-card{background:linear-gradient(145deg,#0f1f35,#0a1628);border:1px solid rgba(107,184,201,.25);',
        'border-radius:24px;width:520px;max-width:94vw;padding:44px 40px 36px;',
        'box-shadow:0 30px 80px rgba(0,0,0,.6);text-align:center;font-family:inherit;direction:rtl;}',
        '.t-badge{display:inline-flex;align-items:center;gap:6px;background:rgba(107,184,201,.12);',
        'border:1px solid rgba(107,184,201,.3);color:#6bb8c9;font-size:13px;font-weight:600;',
        'padding:5px 14px;border-radius:20px;margin-bottom:20px;}',
        '.t-icon{width:80px;height:80px;border-radius:50%;display:flex;align-items:center;justify-content:center;',
        'font-size:36px;margin:0 auto 20px;background:linear-gradient(135deg,rgba(107,184,201,.15),rgba(107,184,201,.05));',
        'border:2px solid rgba(107,184,201,.2);}',
        '.tour-card h2{color:#f8f8f8;font-size:23px;font-weight:700;margin:0 0 12px;line-height:1.4;}',
        '.tour-card p{color:rgba(248,248,248,.65);font-size:15px;line-height:1.7;margin:0 0 22px;}',
        '.t-dots{display:flex;justify-content:center;gap:8px;margin-bottom:26px;}',
        '.t-dot{width:8px;height:8px;border-radius:50%;background:rgba(107,184,201,.25);transition:all .3s;}',
        '.t-dot.on{background:#6bb8c9;width:24px;border-radius:4px;}',
        '.t-bar{height:3px;background:rgba(107,184,201,.1);border-radius:2px;margin-bottom:26px;overflow:hidden;}',
        '.t-fill{height:100%;background:linear-gradient(90deg,#6bb8c9,#4a9fb5);border-radius:2px;transition:width .4s ease;}',
        '.t-btn{display:flex;align-items:center;justify-content:center;gap:8px;',
        'background:linear-gradient(135deg,#6bb8c9,#4a9fb5);color:#fff;border:none;border-radius:12px;',
        'padding:14px 32px;font-size:16px;font-weight:700;cursor:pointer;width:100%;',
        'font-family:inherit;transition:all .25s;box-sizing:border-box;}',
        '.t-btn:hover{transform:translateY(-2px);box-shadow:0 8px 24px rgba(107,184,201,.35);}',
        '.t-skip{background:none;border:none;color:rgba(248,248,248,.35);font-size:13px;',
        'cursor:pointer;margin-top:14px;display:block;width:100%;font-family:inherit;',
        'transition:color .2s;padding:4px;}',
        '.t-skip:hover{color:rgba(248,248,248,.65);}'
    ].join('');

    function injectCSS() {
        if (document.getElementById('inify-tour-css')) return;
        var s = document.createElement('style');
        s.id = 'inify-tour-css';
        s.textContent = CSS;
        document.head.appendChild(s);
    }

    function buildOverlay() {
        if (document.getElementById('inifyTourOverlay')) return;
        injectCSS();
        var div = document.createElement('div');
        div.id = 'inifyTourOverlay';
        div.className = 'tour-overlay';
        div.innerHTML = '<div class="tour-card" id="inifyTourCard"></div>';
        document.body.appendChild(div);
    }

    function renderStep(step) {
        var data = STEPS[step];
        if (!data) return;
        buildOverlay();

        var dots = data.dots.map(function (on) {
            return '<div class="t-dot' + (on ? ' on' : '') + '"></div>';
        }).join('');

        document.getElementById('inifyTourCard').innerHTML = [
            '<div class="t-badge">' + data.badge + '</div>',
            '<div class="t-icon">' + data.icon + '</div>',
            '<h2>' + data.title + '</h2>',
            '<p>' + data.desc + '</p>',
            '<div class="t-bar"><div class="t-fill" style="width:' + data.progress + '%"></div></div>',
            '<div class="t-dots">' + dots + '</div>',
            '<button class="t-btn" id="inifyTourMainBtn">' + data.btnLabel +
            ' <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="9 18 15 12 9 6"/></svg></button>',
            '<button class="t-skip" id="inifyTourSkipBtn">' + data.skipLabel + '</button>',
        ].join('');

        document.getElementById('inifyTourMainBtn').onclick = data.btnAction;
        document.getElementById('inifyTourSkipBtn').onclick = (step === 4)
            ? function () { TOUR.finish(null); }
            : function () { TOUR.skip(); };
    }

    /* ── Public API ── */
    var TOUR = window.TOUR = {

        _saveDB: function () {
            var csrf = (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] || '';
            fetch('/api/tour/complete/', {
                method: 'POST',
                headers: { 'X-CSRFToken': csrf, 'Content-Type': 'application/json' }
            }).catch(function () {});
        },

        _hide: function (cb) {
            var el = document.getElementById('inifyTourOverlay');
            if (!el) { if (cb) cb(); return; }
            el.classList.add('tour-hiding');
            el.classList.remove('tour-visible');
            setTimeout(function () {
                el.classList.remove('tour-hiding');
                el.style.display = 'none';
                if (cb) cb();
            }, 300);
        },

        _open: function (step) {
            buildOverlay();
            renderStep(step);
            var el = document.getElementById('inifyTourOverlay');
            el.style.display = 'flex';
            requestAnimationFrame(function () {
                el.classList.add('tour-visible');
            });
            localStorage.setItem(LS_KEY, step);
        },

        goStep: function (step) {
            this._open(step);
        },

        navigate: function (url, nextStep) {
            localStorage.setItem(LS_KEY, nextStep);
            window.location.href = url;
        },

        finish: function (redirectUrl) {
            localStorage.setItem(LS_DONE, '1');
            localStorage.removeItem(LS_KEY);
            this._saveDB();
            if (redirectUrl) {
                window.location.href = redirectUrl;
            } else {
                this._hide();
            }
        },

        skip: function () {
            localStorage.setItem(LS_DONE, '1');
            localStorage.removeItem(LS_KEY);
            this._saveDB();
            this._hide();
        },

        /* يُستدعى من زر السايدبار — يعيد التور من البداية */
        restart: function () {
            localStorage.removeItem(LS_DONE);
            localStorage.setItem(LS_KEY, '1');
            this._open(1);
        },

        /* يُستدعى تلقائياً عند تحميل الداشبورد لأول مرة */
        autoStart: function () {
            if (localStorage.getItem(LS_DONE) === '1') return;
            var step = parseInt(localStorage.getItem(LS_KEY) || '1');
            if (step < 1 || step > 4) step = 1;
            setTimeout(function () { TOUR._open(step); }, 450);
        }
    };

    /* دالة عامة للسايدبار */
    window.startTourFromSidebar = function () {
        TOUR.restart();
    };

})();
