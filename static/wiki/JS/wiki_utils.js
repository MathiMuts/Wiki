// static/wiki/js/wiki_utils.js

/**
 * Converts a string into a URL-friendly slug.
 * @param {string} text The text to slugify.
 * @returns {string} The slugified text.
 */
function slugify_js(text) {
    if (!text) return '';
    return text.toString().toLowerCase()
        .replace(/\s+/g, '-')       // Replace spaces with -
        .replace(/[^\w-]+/g, '')    // Remove all non-word chars
        .replace(/--+/g, '-')       // Replace multiple - with single -
        .replace(/^-+/, '')          // Trim - from start of text
        .replace(/-+$/, '');         // Trim - from end of text
}

/**
 * Auto-resizes a textarea to fit its content and manages trailing empty lines.
 * @param {HTMLTextAreaElement} textareaElement The textarea to manage.
 * @param {number} [desiredMinTrailingEmptyLines=3] Minimum empty lines at the end.
 */
function initializeAutoResizeTextarea(textareaElement, desiredMinTrailingEmptyLines = 3) {
    if (!textareaElement) return;

    let previousValue = textareaElement.value;
    let previousCursorPos = textareaElement.selectionStart;

    function getTrailingEmptyLineCount(text) {
        if (!text) return 0;
        const lines = text.split('\n');
        let count = 0;
        for (let i = lines.length - 1; i >= 0; i--) {
            if (lines[i].trim() === "") {
                count++;
            } else {
                break;
            }
        }
        return count;
    }

    function autoResizeAndManageLines(event = null) {
        if (textareaElement.disabled) return;

        const currentValue = textareaElement.value;
        const currentCursorPos = textareaElement.selectionStart;
        let newCursorPos = currentCursorPos;
        let valueToProcess = currentValue;

        const savedScrollY = window.scrollY;
        const savedScrollX = window.scrollX;

        const existingTrailing = getTrailingEmptyLineCount(valueToProcess);
        const linesToAdd = desiredMinTrailingEmptyLines - existingTrailing;

        if (linesToAdd > 0) {
            const originalLengthBeforeAddingLines = valueToProcess.length;
            for (let i = 0; i < linesToAdd; i++) {
                valueToProcess += '\n';
            }
            // Adjust cursor position if it was at the very end before adding lines
            if (currentValue.length < valueToProcess.length && currentCursorPos === originalLengthBeforeAddingLines) {
                newCursorPos = originalLengthBeforeAddingLines; // Keep cursor before new newlines
            }
        }
        
        if (textareaElement.value !== valueToProcess) {
            textareaElement.value = valueToProcess;
        }

        textareaElement.style.height = 'auto';
        textareaElement.style.height = (textareaElement.scrollHeight) + 'px';
        
        // Restore cursor position carefully
        if (event || (valueToProcess.length !== currentValue.length && !event) ) {
            // If an input event happened (typing, pasting, cutting) or lines were added automatically
            if (event && event.inputType === 'insertLineBreak') {
                // Special handling for Enter key if needed, otherwise general logic applies
            }
            try {
                const textLength = textareaElement.value.length;
                if (newCursorPos > textLength) { newCursorPos = textLength; } // Cap cursor position

                // Only set selection range if it actually needs to change, or if it was an explicit event
                if (textareaElement.selectionStart !== newCursorPos || textareaElement.selectionEnd !== newCursorPos) {
                   textareaElement.setSelectionRange(newCursorPos, newCursorPos);
                }
            } catch (e) {
                // Fallback: move cursor to end if an error occurs
                // console.warn("Error setting cursor position:", e);
                const endPos = textareaElement.value.length;
                try { textareaElement.setSelectionRange(endPos, endPos); } catch (e2) { /* ignore secondary error */ }
            }
        }
        
        previousValue = textareaElement.value; // Update for next event
        previousCursorPos = textareaElement.selectionStart; // Update for next event

        // Restore scroll position after a brief delay to allow rendering
        Promise.resolve().then(() => {
            if (window.scrollY !== savedScrollY || window.scrollX !== savedScrollX) {
                window.scrollTo(savedScrollX, savedScrollY);
            }
        });
    }

    if (!textareaElement.disabled) {
        autoResizeAndManageLines(); // Initial call
    }
    textareaElement.addEventListener('input', autoResizeAndManageLines);
    // Also consider 'change' or other events if necessary, 'input' covers most cases.
}


/**
 * Initializes a "hold-to-delete" button.
 * @param {HTMLElement} buttonElement The button element.
 * @param {HTMLFormElement} formElement The form to submit on successful hold.
 * @param {string} itemTitle The title of the item being deleted (for confirmation).
 * @param {object} [config] Optional configuration.
 * @param {number} [config.holdDuration=5000] Duration to hold in ms.
 * @param {string} [config.defaultText='Delete'] Default button text.
 * @param {string} [config.holdingText='Hold to Delete...'] Text while holding.
 * @param {string} [config.readyText='Release to Delete!'] Text when ready.
 */
function initializeHoldToDeleteButton(buttonElement, formElement, itemTitle, config = {}) {
    if (!buttonElement || !formElement) {
        console.warn('Hold-to-delete: Button or Form element not found.');
        return;
    }

    const HOLD_DURATION = config.holdDuration || 5000;
    const defaultText = config.defaultText || buttonElement.dataset.defaultText || 'Delete';
    const holdingText = config.holdingText || buttonElement.dataset.holdingText || 'Hold to Delete...';
    const readyText = config.readyText || buttonElement.dataset.readyText || 'Release to Delete!';

    let actionTimeoutId = null;
    let animationFrameId = null;
    let isHolding = false;

    const progressFillSpan = buttonElement.querySelector('.progress-fill');
    const btnTextSpan = buttonElement.querySelector('.btn-text');

    if (!progressFillSpan || !btnTextSpan) {
        console.warn('Hold-to-delete: Progress fill or text span not found within the button.');
        // return; // Allow to proceed without visual feedback if structure is different but core logic is desired.
    }
    
    const setButtonText = (textKey) => {
        if (!btnTextSpan) return;
        if (textKey === 'default') btnTextSpan.textContent = defaultText;
        else if (textKey === 'holding') btnTextSpan.textContent = holdingText;
        else if (textKey === 'ready') btnTextSpan.textContent = readyText;
    };
    setButtonText('default');

    const resetHoldState = (performNudge = false) => {
        clearTimeout(actionTimeoutId);
        cancelAnimationFrame(animationFrameId);
        actionTimeoutId = null;
        animationFrameId = null;
        buttonElement.classList.remove('is-filling', 'is-ready-to-delete');
        setButtonText('default');
        
        const wasHolding = isHolding; // Capture state before resetting
        isHolding = false;

        if (progressFillSpan) {
            if (performNudge && wasHolding) { // Only nudge if it was actively being held
                progressFillSpan.style.transition = 'none'; // No transition for the jump back
                progressFillSpan.style.width = '15%'; // Nudge amount
                requestAnimationFrame(() => { // Ensure the 15% width is rendered
                    requestAnimationFrame(() => { // Then animate back to 0%
                        progressFillSpan.style.transition = 'width 0.3s ease-out';
                        progressFillSpan.style.width = '0%';
                    });
                });
            } else {
                progressFillSpan.style.transition = 'width 0.1s linear'; // Quick reset
                progressFillSpan.style.width = '0%';
            }
        }
    };

    const startHold = (event) => {
        // Allow context menu on right-click even if it's a mousedown
        if (event.type === 'mousedown' && event.button !== 0) return; 
        
        event.preventDefault(); // Prevent text selection, etc.
        if (isHolding) return; // Already holding
        isHolding = true;

        buttonElement.classList.add('is-filling');
        if (progressFillSpan) {
            progressFillSpan.style.transition = 'none'; // Start fill from 0 without animation
            progressFillSpan.style.width = '0%';
        }
        setButtonText('holding');

        const startTime = Date.now();

        function animateFill() {
            if (!isHolding) { // If holding was cancelled
                cancelAnimationFrame(animationFrameId);
                return;
            }
            const elapsedTime = Date.now() - startTime;
            const progress = Math.min(100, (elapsedTime / HOLD_DURATION) * 100);
            if (progressFillSpan) progressFillSpan.style.width = progress + '%';

            if (elapsedTime < HOLD_DURATION) {
                animationFrameId = requestAnimationFrame(animateFill);
            } else {
                // Ensure ready state is set if timer completes before animation frame
                if (!buttonElement.classList.contains('is-ready-to-delete')) {
                    buttonElement.classList.add('is-ready-to-delete');
                    setButtonText('ready');
                }
            }
        }
        animationFrameId = requestAnimationFrame(animateFill);

        actionTimeoutId = setTimeout(() => {
            if (isHolding) { // Check if still holding when timeout fires
                buttonElement.classList.add('is-ready-to-delete');
                setButtonText('ready');
            }
        }, HOLD_DURATION);
    };

    const endHold = (isReleasedOnButtonContext) => {
        if (!isHolding) return;

        const wasReadyForDelete = buttonElement.classList.contains('is-ready-to-delete');
        const currentlyWasHolding = isHolding; // Capture before potential reset by confirm dialog

        if (isReleasedOnButtonContext && wasReadyForDelete) {
            // isHolding = false; // Reset state before confirm to avoid re-triggering issues
                               // This is now handled by resetHoldState or form submission
            const confirmMessage = `Are you sure you want to delete "${itemTitle}"? This action cannot be undone.`;
            if (confirm(confirmMessage)) {
                formElement.submit();
                // No need to resetHoldState here as the page will navigate away
                return; 
            } else {
                resetHoldState(false); // User cancelled the confirm dialog
            }
        } else if (isReleasedOnButtonContext && !wasReadyForDelete && currentlyWasHolding) {
            // Released too early, perform nudge
            resetHoldState(true);
        } else {
            // Released outside, or some other interruption
            resetHoldState(false);
        }
    };
    
    buttonElement.addEventListener('mousedown', startHold);
    buttonElement.addEventListener('touchstart', (e) => startHold(e), { passive: false }); // passive: false to allow preventDefault
    
    // Reset if mouse leaves button while still pressed OR if touch is cancelled
    buttonElement.addEventListener('mouseleave', (event) => {
        // Only reset if the primary mouse button is NOT still pressed (i.e., dragging off then releasing elsewhere)
        // If event.buttons is 0, it means no button is pressed. If 1, left is pressed.
        if(isHolding && event.buttons === 0) { // Mouse button was released *outside*
            resetHoldState(false);
        } else if (isHolding && event.buttons !== 1) { // Some other mouse button scenario, or no button pressed
             resetHoldState(false);
        }
        // If event.buttons === 1, it means mouse is still down and dragged off. Mouseup on document will handle it.
    });
    buttonElement.addEventListener('touchcancel', () => { if(isHolding) resetHoldState(false); });
    buttonElement.addEventListener('blur', () => { // E.g., user tabs away
        if(isHolding) resetHoldState(false);
    });
    
    // Use document-level listeners for mouseup/touchend to catch releases outside the button
    document.addEventListener('mouseup', (event) => {
        if (isHolding && event.button === 0) { // Only react to left mouse button up
            const isReleasedOnButton = event.target === buttonElement || buttonElement.contains(event.target);
            endHold(isReleasedOnButton);
        }
    });
    document.addEventListener('touchend', (event) => {
         if (isHolding) {
            let isReleasedOnButton = false;
            // Check if any of the changed touches ended on the button
            for (let i = 0; i < event.changedTouches.length; i++) {
                const touch = event.changedTouches[i];
                const endTarget = document.elementFromPoint(touch.clientX, touch.clientY);
                if (endTarget === buttonElement || buttonElement.contains(endTarget)) {
                    isReleasedOnButton = true;
                    break;
                }
            }
            endHold(isReleasedOnButton);
        }
    });
}