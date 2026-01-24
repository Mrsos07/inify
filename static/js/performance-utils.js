/**
 * Performance Utilities - Prevent Layout Thrashing
 * 
 * هذا الملف يحتوي على دوال مساعدة لتحسين الأداء ومنع Layout Thrashing
 * عن طريق فصل عمليات القراءة (Read) عن عمليات الكتابة (Write) في DOM
 */

(function(window) {
    'use strict';

    // ═══════════════════════════════════════════════════════════
    // FastDOM - Batch DOM Operations
    // ═══════════════════════════════════════════════════════════

    class FastDOM {
        constructor() {
            this.reads = [];
            this.writes = [];
            this.scheduled = false;
        }

        /**
         * Schedule a DOM read operation
         * @param {Function} callback - Function to execute
         * @returns {Promise}
         */
        measure(callback) {
            return new Promise((resolve) => {
                this.reads.push(() => {
                    const result = callback();
                    resolve(result);
                });
                this.scheduleFlush();
            });
        }

        /**
         * Schedule a DOM write operation
         * @param {Function} callback - Function to execute
         * @returns {Promise}
         */
        mutate(callback) {
            return new Promise((resolve) => {
                this.writes.push(() => {
                    callback();
                    resolve();
                });
                this.scheduleFlush();
            });
        }

        /**
         * Schedule flush using requestAnimationFrame
         */
        scheduleFlush() {
            if (!this.scheduled) {
                this.scheduled = true;
                requestAnimationFrame(() => this.flush());
            }
        }

        /**
         * Execute all reads, then all writes
         */
        flush() {
            // Execute all reads first
            const reads = this.reads;
            this.reads = [];
            reads.forEach(read => read());

            // Then execute all writes
            const writes = this.writes;
            this.writes = [];
            writes.forEach(write => write());

            this.scheduled = false;

            // If new operations were scheduled during flush, schedule another flush
            if (this.reads.length || this.writes.length) {
                this.scheduleFlush();
            }
        }

        /**
         * Clear all pending operations
         */
        clear() {
            this.reads = [];
            this.writes = [];
            this.scheduled = false;
        }
    }

    // Create singleton instance
    const fastdom = new FastDOM();

    // ═══════════════════════════════════════════════════════════
    // Debounce & Throttle
    // ═══════════════════════════════════════════════════════════

    /**
     * Debounce function - delays execution until after wait time
     * @param {Function} func - Function to debounce
     * @param {Number} wait - Wait time in milliseconds
     * @returns {Function}
     */
    function debounce(func, wait = 300) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }

    /**
     * Throttle function - limits execution to once per wait time
     * @param {Function} func - Function to throttle
     * @param {Number} wait - Wait time in milliseconds
     * @returns {Function}
     */
    function throttle(func, wait = 300) {
        let inThrottle;
        return function executedFunction(...args) {
            if (!inThrottle) {
                func(...args);
                inThrottle = true;
                setTimeout(() => inThrottle = false, wait);
            }
        };
    }

    /**
     * Request Animation Frame throttle
     * @param {Function} func - Function to throttle
     * @returns {Function}
     */
    function rafThrottle(func) {
        let rafId = null;
        return function executedFunction(...args) {
            if (rafId === null) {
                rafId = requestAnimationFrame(() => {
                    func(...args);
                    rafId = null;
                });
            }
        };
    }

    // ═══════════════════════════════════════════════════════════
    // Batch Style Updates
    // ═══════════════════════════════════════════════════════════

    /**
     * Batch multiple style updates into a single operation
     * @param {HTMLElement} element - Target element
     * @param {Object} styles - Object with style properties
     */
    function batchStyles(element, styles) {
        fastdom.mutate(() => {
            Object.assign(element.style, styles);
        });
    }

    /**
     * Batch multiple class operations
     * @param {HTMLElement} element - Target element
     * @param {Object} operations - { add: [], remove: [], toggle: [] }
     */
    function batchClasses(element, operations) {
        fastdom.mutate(() => {
            if (operations.add) {
                element.classList.add(...operations.add);
            }
            if (operations.remove) {
                element.classList.remove(...operations.remove);
            }
            if (operations.toggle) {
                operations.toggle.forEach(cls => element.classList.toggle(cls));
            }
        });
    }

    // ═══════════════════════════════════════════════════════════
    // Optimized Scroll Handlers
    // ═══════════════════════════════════════════════════════════

    /**
     * Smooth scroll to element with performance optimization
     * @param {HTMLElement} element - Target element
     * @param {Object} options - Scroll options
     */
    function smoothScrollTo(element, options = {}) {
        const defaults = {
            behavior: 'smooth',
            block: 'start',
            inline: 'nearest'
        };

        fastdom.measure(() => {
            element.scrollIntoView({ ...defaults, ...options });
        });
    }

    /**
     * Optimized scroll to bottom
     * @param {HTMLElement} container - Scrollable container
     */
    function scrollToBottom(container) {
        fastdom.measure(() => {
            const scrollHeight = container.scrollHeight;
            fastdom.mutate(() => {
                container.scrollTop = scrollHeight;
            });
        });
    }

    /**
     * Check if element is in viewport (optimized)
     * @param {HTMLElement} element - Element to check
     * @returns {Promise<Boolean>}
     */
    function isInViewport(element) {
        return fastdom.measure(() => {
            const rect = element.getBoundingClientRect();
            return (
                rect.top >= 0 &&
                rect.left >= 0 &&
                rect.bottom <= (window.innerHeight || document.documentElement.clientHeight) &&
                rect.right <= (window.innerWidth || document.documentElement.clientWidth)
            );
        });
    }

    // ═══════════════════════════════════════════════════════════
    // Resize Observer Helper
    // ═══════════════════════════════════════════════════════════

    /**
     * Create optimized resize observer
     * @param {Function} callback - Callback function
     * @returns {ResizeObserver}
     */
    function createResizeObserver(callback) {
        const throttledCallback = rafThrottle(callback);
        return new ResizeObserver(throttledCallback);
    }

    // ═══════════════════════════════════════════════════════════
    // Intersection Observer Helper
    // ═══════════════════════════════════════════════════════════

    /**
     * Create intersection observer for lazy loading
     * @param {Function} callback - Callback function
     * @param {Object} options - Observer options
     * @returns {IntersectionObserver}
     */
    function createIntersectionObserver(callback, options = {}) {
        const defaults = {
            root: null,
            rootMargin: '50px',
            threshold: 0.1
        };
        return new IntersectionObserver(callback, { ...defaults, ...options });
    }

    // ═══════════════════════════════════════════════════════════
    // Performance Monitoring
    // ═══════════════════════════════════════════════════════════

    /**
     * Measure function execution time
     * @param {Function} func - Function to measure
     * @param {String} label - Label for console output
     * @returns {Function}
     */
    function measurePerformance(func, label = 'Function') {
        return function(...args) {
            const start = performance.now();
            const result = func(...args);
            const end = performance.now();
            console.log(`${label} took ${(end - start).toFixed(2)}ms`);
            return result;
        };
    }

    /**
     * Detect layout thrashing (for debugging)
     */
    function detectLayoutThrashing() {
        const originalGetBoundingClientRect = Element.prototype.getBoundingClientRect;
        let readCount = 0;
        let writeCount = 0;
        let thrashingDetected = false;

        // Override getBoundingClientRect
        Element.prototype.getBoundingClientRect = function() {
            readCount++;
            if (writeCount > 0 && !thrashingDetected) {
                console.warn('⚠️ Layout Thrashing detected! Read after write operation.');
                console.trace();
                thrashingDetected = true;
            }
            return originalGetBoundingClientRect.call(this);
        };

        // Monitor style changes
        const observer = new MutationObserver(() => {
            writeCount++;
            // Reset after a frame
            requestAnimationFrame(() => {
                readCount = 0;
                writeCount = 0;
                thrashingDetected = false;
            });
        });

        observer.observe(document.body, {
            attributes: true,
            childList: true,
            subtree: true,
            attributeFilter: ['style', 'class']
        });

        return () => {
            Element.prototype.getBoundingClientRect = originalGetBoundingClientRect;
            observer.disconnect();
        };
    }

    // ═══════════════════════════════════════════════════════════
    // Export to window
    // ═══════════════════════════════════════════════════════════

    window.PerformanceUtils = {
        // FastDOM
        fastdom,
        measure: fastdom.measure.bind(fastdom),
        mutate: fastdom.mutate.bind(fastdom),

        // Timing
        debounce,
        throttle,
        rafThrottle,

        // Batch operations
        batchStyles,
        batchClasses,

        // Scroll
        smoothScrollTo,
        scrollToBottom,
        isInViewport,

        // Observers
        createResizeObserver,
        createIntersectionObserver,

        // Monitoring
        measurePerformance,
        detectLayoutThrashing
    };

    // Also export as module if available
    if (typeof module !== 'undefined' && module.exports) {
        module.exports = window.PerformanceUtils;
    }

})(window);
