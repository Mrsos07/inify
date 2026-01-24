// Newra Dashboard JavaScript

// Modal Functions (optimized to prevent layout thrashing)
function openModal(modalId) {
    // Batch DOM mutations using requestAnimationFrame
    requestAnimationFrame(() => {
        const modal = document.getElementById(modalId);
        modal.classList.add('show');
        document.body.style.overflow = 'hidden';
    });
}

function closeModal(modalId) {
    // Batch DOM mutations using requestAnimationFrame
    requestAnimationFrame(() => {
        const modal = document.getElementById(modalId);
        modal.classList.remove('show');
        document.body.style.overflow = '';
    });
}

// Close modal on overlay click
document.querySelectorAll('.modal-overlay').forEach(overlay => {
    overlay.addEventListener('click', function(e) {
        if (e.target === this) {
            this.classList.remove('show');
            document.body.style.overflow = '';
        }
    });
});

// Image Upload Preview
const imageInput = document.getElementById('propertyImages');
const imagePreview = document.getElementById('imagePreview');

if (imageInput) {
    imageInput.addEventListener('change', function(e) {
        imagePreview.innerHTML = '';
        const files = Array.from(e.target.files);
        
        files.forEach((file, index) => {
            if (file.type.startsWith('image/')) {
                const reader = new FileReader();
                reader.onload = function(e) {
                    const div = document.createElement('div');
                    div.className = 'image-preview-item';
                    div.innerHTML = `
                        <img src="${e.target.result}" alt="Preview">
                        <button type="button" class="remove" onclick="removeImage(${index})">×</button>
                    `;
                    imagePreview.appendChild(div);
                };
                reader.readAsDataURL(file);
            }
        });
    });
}

function removeImage(index) {
    const items = imagePreview.querySelectorAll('.image-preview-item');
    if (items[index]) {
        items[index].remove();
    }
}

// Add Property Form
const addPropertyForm = document.getElementById('addPropertyForm');
if (addPropertyForm) {
    addPropertyForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        const formData = new FormData(this);
        const submitBtn = this.querySelector('button[type="submit"]');
        const originalText = submitBtn.textContent;
        
        submitBtn.disabled = true;
        submitBtn.textContent = 'جاري الحفظ...';
        
        try {
            const response = await fetch('/api/v1/properties/', {
                method: 'POST',
                body: formData,
                headers: {
                    'X-CSRFToken': formData.get('csrfmiddlewaretoken')
                }
            });
            
            if (response.ok) {
                closeModal('addPropertyModal');
                window.location.reload();
            } else {
                const data = await response.json();
                alert(data.error || 'حدث خطأ أثناء حفظ العقار');
            }
        } catch (error) {
            console.error('Error:', error);
            alert('حدث خطأ في الاتصال');
        } finally {
            submitBtn.disabled = false;
            submitBtn.textContent = originalText;
        }
    });
}

// Drag and Drop for Image Upload
const uploadArea = document.querySelector('.image-upload');
if (uploadArea) {
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        uploadArea.addEventListener(eventName, preventDefaults, false);
    });

    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    ['dragenter', 'dragover'].forEach(eventName => {
        uploadArea.addEventListener(eventName, () => {
            // Batch style changes to prevent layout thrashing
            requestAnimationFrame(() => {
                uploadArea.style.borderColor = '#fff';
            });
        });
    });

    ['dragleave', 'drop'].forEach(eventName => {
        uploadArea.addEventListener(eventName, () => {
            // Batch style changes to prevent layout thrashing
            requestAnimationFrame(() => {
                uploadArea.style.borderColor = '';
            });
        });
    });

    uploadArea.addEventListener('drop', function(e) {
        const dt = e.dataTransfer;
        const files = dt.files;
        imageInput.files = files;
        imageInput.dispatchEvent(new Event('change'));
    });
}

// Format numbers
function formatNumber(num) {
    return new Intl.NumberFormat('ar-SA').format(num);
}

// Initialize
document.addEventListener('DOMContentLoaded', function() {
    // Format all stat values
    document.querySelectorAll('.stat-value').forEach(el => {
        const value = parseInt(el.textContent);
        if (!isNaN(value)) {
            el.textContent = formatNumber(value);
        }
    });
});
