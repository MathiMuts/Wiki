// static/wiki/js/gallery.js (UPDATED)

function initializeGallery() {
    let lightbox = document.getElementById('gallery-lightbox');
    if (!lightbox) {
        lightbox = createLightbox();
    }

    const lightboxImage = document.getElementById('lightbox-image');
    const lightboxCaption = document.getElementById('lightbox-caption');
    const closeButton = lightbox.querySelector('.lightbox-close');
    const prevButton = lightbox.querySelector('.lightbox-prev');
    const nextButton = lightbox.querySelector('.lightbox-next');
    const body = document.body; // Get a reference to the body element

    let currentGalleryItems = [];
    let currentIndex = -1;

    document.body.addEventListener('click', (e) => {
        const link = e.target.closest('.gallery-item-link');
        if (link) {
            e.preventDefault();
            const gallery = link.closest('.archive-gallery');
            currentGalleryItems = Array.from(gallery.querySelectorAll('.gallery-item-link'));
            currentIndex = currentGalleryItems.indexOf(link);
            openLightbox();
        }
    });

    function openLightbox() {
        if (currentIndex > -1) {
            // --- MODIFIED PART ---
            // Prevent content jump by compensating for the scrollbar width
            const scrollbarWidth = window.innerWidth - document.documentElement.clientWidth;
            body.style.paddingRight = `${scrollbarWidth}px`;
            // Add the class to disable scrolling
            body.classList.add('lightbox-active');
            
            updateLightboxImage();
            lightbox.style.display = 'flex';
            document.addEventListener('keydown', handleKeydown);
        }
    }

    function closeLightbox() {
        // --- MODIFIED PART ---
        // Remove the class to re-enable scrolling
        body.classList.remove('lightbox-active');
        // Remove the padding to avoid a jump
        body.style.paddingRight = '';

        lightbox.style.display = 'none';
        document.removeEventListener('keydown', handleKeydown);
    }

    function updateLightboxImage() {
        const item = currentGalleryItems[currentIndex];
        const imageUrl = item.getAttribute('href');
        const captionText = item.getAttribute('data-title');

        lightboxImage.src = imageUrl;
        lightboxCaption.textContent = captionText;
    }

    function showNext() {
        currentIndex = (currentIndex + 1) % currentGalleryItems.length;
        updateLightboxImage();
    }

    function showPrev() {
        currentIndex = (currentIndex - 1 + currentGalleryItems.length) % currentGalleryItems.length;
        updateLightboxImage();
    }

    function handleKeydown(e) {
        if (e.key === 'Escape') closeLightbox();
        if (e.key === 'ArrowRight') showNext();
        if (e.key === 'ArrowLeft') showPrev();
    }

    closeButton.addEventListener('click', closeLightbox);
    nextButton.addEventListener('click', showNext);
    prevButton.addEventListener('click', showPrev);
    lightbox.addEventListener('click', (e) => {
        if (e.target === lightbox) closeLightbox();
    });
}

function createLightbox() {
    const lightboxHTML = `
        <span class="lightbox-close" title="Close (Esc)">×</span>
        <div class="lightbox-content">
            <img id="lightbox-image" alt="Zoomed image">
            <div id="lightbox-caption"></div>
        </div>
        <a class="lightbox-prev" title="Previous (Left Arrow)">❮</a>
        <a class="lightbox-next" title="Next (Right Arrow)">❯</a>
    `;
    const lightboxElement = document.createElement('div');
    lightboxElement.id = 'gallery-lightbox';
    lightboxElement.className = 'lightbox-overlay';
    lightboxElement.innerHTML = lightboxHTML;
    document.body.appendChild(lightboxElement);
    return lightboxElement;
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeGallery);
} else {
    initializeGallery();
}