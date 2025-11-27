/**
 * Newra Estate - Chat Widget
 * The New Era of Intelligence
 * 
 * Embeddable chat widget for real estate agents
 */

(function() {
    'use strict';

    // Default configuration
    const DEFAULT_CONFIG = {
        agentId: null,
        apiUrl: '/api/v1/chat/public/',
        position: 'bottom-right',
        primaryColor: '#000000',
        language: 'ar',
        welcomeMessage: 'مرحباً! 👋\n\nأنا مساعد Newra Estate لمساعدتك في اختيار العقار المناسب.\n\nهل تبحث عن شراء أم استئجار عقار؟',
        placeholder: 'اكتب رسالتك هنا...',
        botName: 'Newra Estate',
        botSubtitle: 'المساعد العقاري الذكي'
    };

    // Newra Chat Widget Class
    class NewraChatWidget {
        constructor(config) {
            this.config = { ...DEFAULT_CONFIG, ...config };
            this.conversationId = null;
            this.clientId = this.getClientId();
            this.isOpen = false;
            this.isTyping = false;
            
            this.init();
        }

        init() {
            this.injectStyles();
            this.createWidget();
            this.bindEvents();
            this.addWelcomeMessage();
        }

        // Inject CSS styles
        injectStyles() {
            if (document.getElementById('newra-chat-styles')) return;
            
            const link = document.createElement('link');
            link.id = 'newra-chat-styles';
            link.rel = 'stylesheet';
            link.href = this.config.cssUrl || '/static/css/chat.css';
            document.head.appendChild(link);

            // Add Cairo font
            const font = document.createElement('link');
            font.rel = 'stylesheet';
            font.href = 'https://fonts.googleapis.com/css2?family=Cairo:wght@400;500;600;700&display=swap';
            document.head.appendChild(font);
        }

        // Create widget HTML
        createWidget() {
            const widget = document.createElement('div');
            widget.id = 'newra-chat-container';
            widget.innerHTML = `
                <!-- Chat Button -->
                <button class="newra-chat-button" id="newraChatButton">
                    <svg class="chat-icon" viewBox="0 0 24 24">
                        <path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2z"/>
                    </svg>
                    <svg class="close-icon" viewBox="0 0 24 24">
                        <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>
                    </svg>
                </button>

                <!-- Chat Widget -->
                <div class="newra-chat-widget" id="newraChatWidget" dir="rtl">
                    <!-- Header -->
                    <div class="newra-chat-header">
                        <div class="avatar">
                            <svg viewBox="0 0 100 100" fill="none">
                                <circle cx="35" cy="30" r="18" stroke="#000" stroke-width="6" fill="none"/>
                                <circle cx="35" cy="30" r="6" fill="#000"/>
                                <line x1="35" y1="48" x2="35" y2="70" stroke="#000" stroke-width="6" stroke-linecap="round"/>
                                <circle cx="35" cy="78" r="8" fill="#000"/>
                            </svg>
                        </div>
                        <div class="info">
                            <h3>${this.config.botName}</h3>
                            <span class="status">${this.config.botSubtitle}</span>
                        </div>
                        <button class="close-btn" id="newraCloseBtn">
                            <svg viewBox="0 0 24 24" width="24" height="24" fill="currentColor">
                                <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>
                            </svg>
                        </button>
                    </div>

                    <!-- Messages -->
                    <div class="newra-chat-messages" id="newraMessages"></div>

                    <!-- Typing Indicator -->
                    <div class="newra-typing" id="newraTyping">
                        <div class="bubble">
                            <span class="dot"></span>
                            <span class="dot"></span>
                            <span class="dot"></span>
                        </div>
                    </div>

                    <!-- Input -->
                    <div class="newra-chat-input">
                        <div class="input-wrapper">
                            <input 
                                type="text" 
                                id="newraInput" 
                                placeholder="${this.config.placeholder}"
                                autocomplete="off"
                            >
                            <button class="send-btn" id="newraSendBtn">
                                <svg viewBox="0 0 24 24">
                                    <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/>
                                </svg>
                            </button>
                        </div>
                        <div class="newra-quick-actions" id="newraQuickActions">
                            <button data-message="أبحث عن شراء عقار">🏠 شراء</button>
                            <button data-message="أبحث عن استئجار عقار">🔑 إيجار</button>
                            <button data-message="أريد الاطلاع على العقارات المتاحة">📋 العقارات</button>
                        </div>
                    </div>

                    <!-- Footer -->
                    <div class="newra-chat-footer">
                        Powered by <a href="https://newra.ai" target="_blank">Newra</a>
                    </div>
                </div>
            `;
            
            document.body.appendChild(widget);

            // Store references
            this.elements = {
                button: document.getElementById('newraChatButton'),
                widget: document.getElementById('newraChatWidget'),
                messages: document.getElementById('newraMessages'),
                input: document.getElementById('newraInput'),
                sendBtn: document.getElementById('newraSendBtn'),
                closeBtn: document.getElementById('newraCloseBtn'),
                typing: document.getElementById('newraTyping'),
                quickActions: document.getElementById('newraQuickActions')
            };
        }

        // Bind events
        bindEvents() {
            // Toggle chat
            this.elements.button.addEventListener('click', () => this.toggle());
            this.elements.closeBtn.addEventListener('click', () => this.close());

            // Send message
            this.elements.sendBtn.addEventListener('click', () => this.sendMessage());
            this.elements.input.addEventListener('keypress', (e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    this.sendMessage();
                }
            });

            // Quick actions
            this.elements.quickActions.querySelectorAll('button').forEach(btn => {
                btn.addEventListener('click', () => {
                    const message = btn.dataset.message;
                    if (message) {
                        this.elements.input.value = message;
                        this.sendMessage();
                    }
                });
            });
        }

        // Toggle widget
        toggle() {
            this.isOpen ? this.close() : this.open();
        }

        open() {
            this.isOpen = true;
            this.elements.widget.classList.add('open');
            this.elements.button.classList.add('active');
            this.elements.input.focus();
        }

        close() {
            this.isOpen = false;
            this.elements.widget.classList.remove('open');
            this.elements.button.classList.remove('active');
        }

        // Add welcome message
        addWelcomeMessage() {
            this.addMessage(this.config.welcomeMessage, 'bot');
        }

        // Add message to chat
        addMessage(content, type, properties = null, showMedia = false) {
            const messageDiv = document.createElement('div');
            messageDiv.className = `newra-message ${type}`;
            
            const time = new Date().toLocaleTimeString('ar-SA', { 
                hour: '2-digit', 
                minute: '2-digit' 
            });

            let html = `<div class="bubble">${this.escapeHtml(content).replace(/\n/g, '<br>')}</div>`;
            
            // Add property cards with images and videos
            if (properties && properties.length > 0) {
                properties.forEach(prop => {
                    if (!prop) return;
                    
                    // Get primary image or first image
                    let primaryImage = prop.primary_image;
                    if (!primaryImage && prop.images && prop.images.length > 0) {
                        const primary = prop.images.find(img => img.is_primary);
                        primaryImage = primary ? primary.url : prop.images[0].url;
                    }
                    
                    // Check for videos
                    const hasVideos = prop.videos && prop.videos.length > 0;
                    const imageCount = prop.images ? prop.images.length : 0;
                    const videoCount = prop.videos ? prop.videos.length : 0;
                    
                    html += `
                        <div class="newra-property-card" data-id="${prop.id}">
                            <div class="media-container">
                                ${primaryImage ? `<div class="image" style="background-image: url('${primaryImage}')"></div>` : '<div class="no-image">🏠</div>'}
                                <div class="media-badges">
                                    ${imageCount > 0 ? `<span class="badge">📷 ${imageCount}</span>` : ''}
                                    ${videoCount > 0 ? `<span class="badge">🎬 ${videoCount}</span>` : ''}
                                </div>
                            </div>
                            <div class="content">
                                <div class="title">${this.escapeHtml(prop.title || '')}</div>
                                <div class="price">${prop.price_display || (prop.price ? prop.price.toLocaleString() + ' ريال' : '')}</div>
                                <div class="details">
                                    <span>📐 ${prop.size ? prop.size + ' م²' : ''}</span>
                                    <span>🛏️ ${prop.bedrooms || 0}</span>
                                    <span>🚿 ${prop.bathrooms || 0}</span>
                                </div>
                                <div class="location">📍 ${prop.city || ''}${prop.neighborhood ? ' - ' + prop.neighborhood : ''}</div>
                                ${hasVideos ? '<div class="has-video">🎥 يتوفر فيديو للعقار</div>' : ''}
                            </div>
                    `;
                    
                    // Show media gallery if requested
                    if (showMedia && (imageCount > 0 || videoCount > 0)) {
                        html += `<div class="media-gallery">`;
                        
                        // Show all images
                        if (prop.images && prop.images.length > 0) {
                            html += `<div class="gallery-section"><div class="gallery-title">📷 الصور (${prop.images.length})</div><div class="gallery-items">`;
                            prop.images.forEach((img, idx) => {
                                if (img && img.url) {
                                    html += `<div class="gallery-item image-item" data-image-url="${img.url}" data-image-index="${idx}">
                                        <img src="${img.url}" alt="صورة ${idx + 1}" loading="lazy">
                                    </div>`;
                                }
                            });
                            html += `</div></div>`;
                        }
                        
                        // Show all videos
                        if (prop.videos && prop.videos.length > 0) {
                            html += `<div class="gallery-section"><div class="gallery-title">🎬 الفيديوهات (${prop.videos.length})</div><div class="gallery-items">`;
                            prop.videos.forEach((vid, idx) => {
                                if (vid && vid.url) {
                                    html += `<div class="gallery-item video-item" data-video-url="${vid.url}">
                                        <video src="${vid.url}" preload="metadata"></video>
                                    </div>`;
                                }
                            });
                            html += `</div></div>`;
                        }
                        
                        html += `</div>`;
                    }
                    
                    html += `</div>`;
                });
            }
            
            html += `<span class="time">${time}</span>`;
            
            messageDiv.innerHTML = html;
            this.elements.messages.appendChild(messageDiv);
            
            // Bind property card clicks
            messageDiv.querySelectorAll('.newra-property-card').forEach(card => {
                card.addEventListener('click', (e) => {
                    // Don't trigger if clicking on media gallery
                    if (e.target.closest('.media-gallery')) return;
                    
                    const title = card.querySelector('.title').textContent;
                    this.elements.input.value = `أريد صور وفيديو عقار: ${title}`;
                    this.sendMessage();
                });
            });
            
            // Bind image clicks for fullscreen view
            messageDiv.querySelectorAll('.gallery-item.image-item').forEach(item => {
                item.addEventListener('click', (e) => {
                    e.stopPropagation();
                    const imageUrl = item.dataset.imageUrl;
                    if (imageUrl) {
                        this.showImageViewer(imageUrl);
                    }
                });
            });
            
            // Bind video clicks for play
            messageDiv.querySelectorAll('.gallery-item.video-item').forEach(item => {
                item.addEventListener('click', (e) => {
                    e.stopPropagation();
                    const video = item.querySelector('video');
                    if (video) {
                        if (video.paused) {
                            video.play();
                            video.controls = true;
                        } else {
                            video.pause();
                        }
                    }
                });
            });
            
            this.scrollToBottom();
        }
        
        // Show fullscreen image viewer
        showImageViewer(imageUrl) {
            // Create overlay if not exists
            let overlay = document.getElementById('newraImageViewer');
            if (!overlay) {
                overlay = document.createElement('div');
                overlay.id = 'newraImageViewer';
                overlay.className = 'image-viewer-overlay';
                overlay.innerHTML = `
                    <button class="image-viewer-close">✕</button>
                    <img src="" alt="صورة العقار">
                `;
                document.body.appendChild(overlay);
                
                // Close on click
                overlay.addEventListener('click', (e) => {
                    if (e.target === overlay || e.target.classList.contains('image-viewer-close')) {
                        overlay.classList.remove('active');
                    }
                });
                
                // Close on escape
                document.addEventListener('keydown', (e) => {
                    if (e.key === 'Escape') {
                        overlay.classList.remove('active');
                    }
                });
            }
            
            // Set image and show
            overlay.querySelector('img').src = imageUrl;
            overlay.classList.add('active');
        }

        // Send message
        async sendMessage() {
            const message = this.elements.input.value.trim();
            if (!message || this.isTyping) return;

            // Hide quick actions
            this.elements.quickActions.style.display = 'none';

            // Add user message
            this.addMessage(message, 'user');
            this.elements.input.value = '';

            // Show typing
            this.showTyping(true);

            try {
                const response = await fetch(this.config.apiUrl, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        agent_id: this.config.agentId,
                        message: message,
                        conversation_id: this.conversationId,
                        client_id: this.clientId,
                        language: this.config.language
                    })
                });

                const data = await response.json();
                
                if (response.ok) {
                    this.conversationId = data.conversation_id;
                    this.addMessage(data.response, 'bot', data.suggested_properties, data.show_media);
                } else {
                    this.addMessage('عذراً، حدث خطأ. يرجى المحاولة مرة أخرى.', 'bot');
                }
            } catch (error) {
                console.error('Newra Chat Error:', error);
                this.addMessage('عذراً، حدث خطأ في الاتصال.', 'bot');
            } finally {
                this.showTyping(false);
            }
        }

        // Show/hide typing indicator
        showTyping(show) {
            this.isTyping = show;
            this.elements.typing.classList.toggle('show', show);
            this.elements.sendBtn.disabled = show;
            if (show) this.scrollToBottom();
        }

        // Scroll to bottom
        scrollToBottom() {
            this.elements.messages.scrollTop = this.elements.messages.scrollHeight;
        }

        // Get or create client ID
        getClientId() {
            let clientId = localStorage.getItem('newra_client_id');
            if (!clientId) {
                clientId = 'web_' + Math.random().toString(36).substr(2, 9) + '_' + Date.now();
                localStorage.setItem('newra_client_id', clientId);
            }
            return clientId;
        }

        // Escape HTML
        escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
    }

    // Expose to global scope
    window.NewraChatWidget = NewraChatWidget;

    // Auto-initialize if config is present
    if (window.NEWRA_CHAT_CONFIG) {
        window.newraChat = new NewraChatWidget(window.NEWRA_CHAT_CONFIG);
    }

})();
