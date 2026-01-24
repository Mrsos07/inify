/**
 * Lazy Loading Utility - تأجيل تحميل الموارد غير الضرورية
 * 
 * يستخدم Intersection Observer لتحميل الصور والموارد عند الحاجة فقط
 */

(function(window) {
    'use strict';

    // ═══════════════════════════════════════════════════════════
    // Lazy Load Images
    // ═══════════════════════════════════════════════════════════

    class LazyLoader {
        constructor(options = {}) {
            this.options = {
                rootMargin: options.rootMargin || '50px',
                threshold: options.threshold || 0.01,
                loadingClass: options.loadingClass || 'lazy-loading',
                loadedClass: options.loadedClass || 'lazy-loaded',
                errorClass: options.errorClass || 'lazy-error'
            };

            this.observer = null;
            this.init();
        }

        init() {
            // Check for Intersection Observer support
            if (!('IntersectionObserver' in window)) {
                this.loadAllImages();
                return;
            }

            this.observer = new IntersectionObserver(
                (entries) => this.handleIntersection(entries),
                {
                    rootMargin: this.options.rootMargin,
                    threshold: this.options.threshold
                }
            );

            this.observeImages();
        }

        observeImages() {
            const images = document.querySelectorAll('img[data-src], img[data-srcset]');
            images.forEach(img => this.observer.observe(img));
        }

        handleIntersection(entries) {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    this.loadImage(entry.target);
                    this.observer.unobserve(entry.target);
                }
            });
        }

        loadImage(img) {
            img.classList.add(this.options.loadingClass);

            const src = img.dataset.src;
            const srcset = img.dataset.srcset;

            if (src) {
                img.src = src;
            }

            if (srcset) {
                img.srcset = srcset;
            }

            img.onload = () => {
                img.classList.remove(this.options.loadingClass);
                img.classList.add(this.options.loadedClass);
                delete img.dataset.src;
                delete img.dataset.srcset;
            };

            img.onerror = () => {
                img.classList.remove(this.options.loadingClass);
                img.classList.add(this.options.errorClass);
            };
        }

        loadAllImages() {
            const images = document.querySelectorAll('img[data-src], img[data-srcset]');
            images.forEach(img => this.loadImage(img));
        }

        refresh() {
            if (this.observer) {
                this.observeImages();
            }
        }

        destroy() {
            if (this.observer) {
                this.observer.disconnect();
            }
        }
    }

    // ═══════════════════════════════════════════════════════════
    // Lazy Load Background Images
    // ═══════════════════════════════════════════════════════════

    class LazyBackgroundLoader {
        constructor(options = {}) {
            this.options = {
                rootMargin: options.rootMargin || '50px',
                threshold: options.threshold || 0.01
            };

            this.observer = null;
            this.init();
        }

        init() {
            if (!('IntersectionObserver' in window)) {
                this.loadAllBackgrounds();
                return;
            }

            this.observer = new IntersectionObserver(
                (entries) => this.handleIntersection(entries),
                {
                    rootMargin: this.options.rootMargin,
                    threshold: this.options.threshold
                }
            );

            this.observeElements();
        }

        observeElements() {
            const elements = document.querySelectorAll('[data-bg]');
            elements.forEach(el => this.observer.observe(el));
        }

        handleIntersection(entries) {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    this.loadBackground(entry.target);
                    this.observer.unobserve(entry.target);
                }
            });
        }

        loadBackground(element) {
            const bg = element.dataset.bg;
            if (bg) {
                element.style.backgroundImage = `url('${bg}')`;
                delete element.dataset.bg;
            }
        }

        loadAllBackgrounds() {
            const elements = document.querySelectorAll('[data-bg]');
            elements.forEach(el => this.loadBackground(el));
        }

        destroy() {
            if (this.observer) {
                this.observer.disconnect();
            }
        }
    }

    // ═══════════════════════════════════════════════════════════
    // Lazy Load Scripts
    // ═══════════════════════════════════════════════════════════

    function lazyLoadScript(src, options = {}) {
        return new Promise((resolve, reject) => {
            const script = document.createElement('script');
            script.src = src;
            script.async = options.async !== false;
            script.defer = options.defer || false;

            if (options.module) {
                script.type = 'module';
            }

            script.onload = () => resolve(script);
            script.onerror = () => reject(new Error(`Failed to load script: ${src}`));

            document.head.appendChild(script);
        });
    }

    // ═══════════════════════════════════════════════════════════
    // Lazy Load Styles
    // ═══════════════════════════════════════════════════════════

    function lazyLoadStyle(href, options = {}) {
        return new Promise((resolve, reject) => {
            const link = document.createElement('link');
            link.rel = 'stylesheet';
            link.href = href;

            if (options.media) {
                link.media = options.media;
            }

            link.onload = () => resolve(link);
            link.onerror = () => reject(new Error(`Failed to load stylesheet: ${href}`));

            document.head.appendChild(link);
        });
    }

    // ═══════════════════════════════════════════════════════════
    // Load on Interaction
    // ═══════════════════════════════════════════════════════════

    function loadOnInteraction(callback, events = ['click', 'touchstart', 'scroll']) {
        const loadResource = () => {
            callback();
            events.forEach(event => {
                window.removeEventListener(event, loadResource);
            });
        };

        events.forEach(event => {
            window.addEventListener(event, loadResource, { once: true, passive: true });
        });

        // Fallback: load after 5 seconds if no interaction
        setTimeout(loadResource, 5000);
    }

    // ═══════════════════════════════════════════════════════════
    // Load on Idle
    // ═══════════════════════════════════════════════════════════

    function loadOnIdle(callback, timeout = 2000) {
        if ('requestIdleCallback' in window) {
            requestIdleCallback(callback, { timeout });
        } else {
            setTimeout(callback, timeout);
        }
    }

    // ═══════════════════════════════════════════════════════════
    // Preload Resources
    // ═══════════════════════════════════════════════════════════

    function preloadResource(href, as, options = {}) {
        const link = document.createElement('link');
        link.rel = 'preload';
        link.href = href;
        link.as = as;

        if (options.type) {
            link.type = options.type;
        }

        if (options.crossorigin) {
            link.crossOrigin = options.crossorigin;
        }

        if (options.media) {
            link.media = options.media;
        }

        document.head.appendChild(link);
        return link;
    }

    // ═══════════════════════════════════════════════════════════
    // Prefetch Resources
    // ═══════════════════════════════════════════════════════════

    function prefetchResource(href, as) {
        const link = document.createElement('link');
        link.rel = 'prefetch';
        link.href = href;
        if (as) link.as = as;
        document.head.appendChild(link);
        return link;
    }

    // ═══════════════════════════════════════════════════════════
    // Auto Initialize
    // ═══════════════════════════════════════════════════════════

    let imageLoader = null;
    let bgLoader = null;

    function autoInit() {
        // Initialize lazy loaders
        imageLoader = new LazyLoader();
        bgLoader = new LazyBackgroundLoader();

        // Load non-critical resources on idle
        loadOnIdle(() => {
            // Load analytics, chat widgets, etc.
            console.log('Loading non-critical resources...');
        });
    }

    // Initialize on DOMContentLoaded
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', autoInit);
    } else {
        autoInit();
    }

    // ═══════════════════════════════════════════════════════════
    // Export to window
    // ═══════════════════════════════════════════════════════════

    window.LazyLoad = {
        LazyLoader,
        LazyBackgroundLoader,
        lazyLoadScript,
        lazyLoadStyle,
        loadOnInteraction,
        loadOnIdle,
        preloadResource,
        prefetchResource,
        imageLoader,
        bgLoader
    };

})(window);
