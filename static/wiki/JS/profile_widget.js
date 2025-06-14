document.addEventListener('DOMContentLoaded', function () {
    const profileWidget = document.querySelector('.profile-widget-animate[data-widget-type="expandable"]');

    if (profileWidget) {
        const avatarTrigger = profileWidget.querySelector('.avatar-display');
        const actionsTray = profileWidget.querySelector('.actions-tray');

        const toggleWidget = (event) => {
            const isOpen = profileWidget.classList.toggle('is-open');
            avatarTrigger.setAttribute('aria-expanded', isOpen);
        };

        avatarTrigger.addEventListener('click', function(event) {
            event.stopPropagation();
            toggleWidget(event);
        });

        avatarTrigger.addEventListener('keydown', function(event) {
            if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault();
                event.stopPropagation();
                toggleWidget(event);
            }
        });

        const actionIcons = actionsTray.querySelectorAll('.action-icon');
        actionIcons.forEach(icon => {
            icon.addEventListener('click', function() {
            });
        });


        document.addEventListener('click', function (event) {
            if (profileWidget.classList.contains('is-open') && !profileWidget.contains(event.target)) {
                profileWidget.classList.remove('is-open');
                avatarTrigger.setAttribute('aria-expanded', 'false');
            }
        });

        document.addEventListener('keydown', function(event) {
            if (event.key === 'Escape' && profileWidget.classList.contains('is-open')) {
                profileWidget.classList.remove('is-open');
                avatarTrigger.setAttribute('aria-expanded', 'false');
            }
        });
    }
});