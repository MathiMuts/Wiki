// static/wiki/JS/wiki_editor_enhancements.js
function initializeWikiEditorEnhancements(textareaElement, tabSize = 4) {
    if (!textareaElement) {
        console.warn("Wiki Editor Enhancements: Textarea element not provided.");
        return;
    }

    let lastUndoableState = null;
    let lastActionWasCustom = false; // Flag to track if the last action was one of our custom ones

    // Function to save state before a custom action
    function saveUndoState() {
        lastUndoableState = {
            value: textareaElement.value,
            selectionStart: textareaElement.selectionStart,
            selectionEnd: textareaElement.selectionEnd,
        };
        lastActionWasCustom = true; // Mark that a custom action is about to happen
    }

    // Function to perform our custom undo
    function performCustomUndo() {
        if (lastUndoableState) {
            textareaElement.value = lastUndoableState.value;
            textareaElement.setSelectionRange(lastUndoableState.selectionStart, lastUndoableState.selectionEnd);
            
            // Clear the saved state after undoing
            lastUndoableState = null; 
            lastActionWasCustom = false; // Reset flag
            
            // Dispatch an input event so other listeners (like auto-resize) are triggered
            textareaElement.dispatchEvent(new Event('input', { bubbles: true, cancelable: true, _customAction: true }));
        }
    }

    // Helper to get current line boundaries
    function getCurrentLineBoundaries(text, cursorPos) {
        let lineStart = text.lastIndexOf('\n', cursorPos - 1) + 1;
        let lineEnd = text.indexOf('\n', cursorPos);
        if (lineEnd === -1 || lineEnd < cursorPos) { // If no newline after cursor or cursor is on last char of line
            lineEnd = text.length;
        }
        return { lineStart, lineEnd };
    }
    
    // Handle Ctrl+X (or Cmd+X) for cutting the current line if no text is selected
    function handleCutLine(event) {
        if (textareaElement.selectionStart === textareaElement.selectionEnd) { // No text selected
            saveUndoState(); // Save state for custom undo
            event.preventDefault(); // Prevent default cut action

            const cursorPos = textareaElement.selectionStart;
            let originalText = textareaElement.value;
            const { lineStart, lineEnd: lineContentEnd } = getCurrentLineBoundaries(originalText, cursorPos);

            // If lineStart is somehow after lineContentEnd (e.g., empty textarea or weird state), do nothing.
            if (lineStart > lineContentEnd) return;

            let textToCopy = "";
            let nextCursorPos = lineStart;

            // Special case: cutting the very last line if it's just a newline character
            if (lineStart === lineContentEnd && lineStart === originalText.length && originalText.length > 0 && originalText.endsWith('\n')) {
                // This case is a bit ambiguous. If the intent is to remove the trailing newline:
                textareaElement.value = originalText.substring(0, originalText.length - 1);
                textToCopy = "\n"; // Or "" depending on desired behavior for "cutting an empty line"
                nextCursorPos = textareaElement.value.length;
            } else {
                textToCopy = originalText.substring(lineStart, lineContentEnd);
                let endOfCutPortion;
                // Include the newline character if it's part of the line being cut
                if (lineContentEnd < originalText.length && originalText[lineContentEnd] === '\n') {
                    endOfCutPortion = lineContentEnd + 1;
                } else {
                    endOfCutPortion = lineContentEnd;
                }
                // Ensure endOfCutPortion does not exceed text length
                if (endOfCutPortion > originalText.length) endOfCutPortion = originalText.length;
                if (lineStart > endOfCutPortion) return; // Should not happen with prior check
                
                const textBefore = originalText.substring(0, lineStart);
                const textAfter = originalText.substring(endOfCutPortion);
                textareaElement.value = textBefore + textAfter;
            }

            // Copy the cut text to clipboard
            if (navigator.clipboard && navigator.clipboard.writeText && textToCopy !== undefined) {
                navigator.clipboard.writeText(textToCopy).catch(err => {
                    // console.warn('Clipboard writeText error during cut line:', err);
                });
            }
            
            textareaElement.setSelectionRange(nextCursorPos, nextCursorPos);
            textareaElement.dispatchEvent(new Event('input', { bubbles: true, cancelable: true, _customAction: true }));
        }
        // If text IS selected, let the browser handle the default Ctrl+X
    }

    // Handle Tab key for indentation
    function handleTabIndent(event) {
        saveUndoState(); // Save state for custom undo
        event.preventDefault(); // Prevent default tab behavior (changing focus)

        const cursorPos = textareaElement.selectionStart;
        const text = textareaElement.value;
        
        // TODO: Implement block indent/unindent if text is selected
        // For now, just simple tab insertion or space alignment

        const lineStartForTab = text.lastIndexOf('\n', cursorPos - 1) + 1;
        const currentColumn = cursorPos - lineStartForTab;
        const spacesToAddCount = tabSize - (currentColumn % tabSize);
        const spaces = ' '.repeat(spacesToAddCount);

        // Insert spaces
        const before = text.substring(0, cursorPos);
        const after = text.substring(textareaElement.selectionEnd); // Use selectionEnd for selected text replacement
        textareaElement.value = before + spaces + after;

        // Move cursor
        const newCursorPos = cursorPos + spaces.length;
        textareaElement.setSelectionRange(newCursorPos, newCursorPos);
        textareaElement.dispatchEvent(new Event('input', { bubbles: true, cancelable: true, _customAction: true }));
    }

    // Listen for regular input events to clear the custom action flag
    textareaElement.addEventListener('input', function(event) {
        // If this input event was NOT triggered by one of our custom actions,
        // then the native undo stack has been updated by the browser.
        // We should clear our custom undo state.
        if (!event._customAction) {
            if (lastActionWasCustom) { // If the last action was custom, but this one isn't
                lastUndoableState = null; // Invalidate our custom undo state
                lastActionWasCustom = false; // Reset flag
            }
        }
    });


    textareaElement.addEventListener('keydown', function(event) {
        // Custom Undo (Ctrl+Z or Cmd+Z)
        // Check if the last action was custom and we have a state to revert to
        if ((event.ctrlKey || event.metaKey) && !event.shiftKey && (event.key === 'z' || event.key === 'Z')) {
            if (lastActionWasCustom && lastUndoableState) {
                event.preventDefault(); // Prevent native undo
                performCustomUndo();
                return; // Custom undo handled
            }
            // If not a custom action, let native undo proceed and clear our flags
            lastUndoableState = null;
            lastActionWasCustom = false;
        }

        // Cut Line Shortcut (Ctrl+X or Cmd+X)
        // Only if no text is selected (behavior of editor like VS Code)
        if ((event.ctrlKey || event.metaKey) && !event.shiftKey && !event.altKey && (event.key === 'x' || event.key === 'X' || event.code === 'KeyX')) {
            // handleCutLine is called, it will check textareaElement.selectionStart === textareaElement.selectionEnd
            // and if true, call saveUndoState and event.preventDefault()
            handleCutLine(event); 
        }

        // Tab Key for indentation (if not in a context where Tab should do something else)
        if (event.key === 'Tab' && !event.ctrlKey && !event.metaKey && !event.altKey) {
            // handleTabIndent calls saveUndoState and event.preventDefault()
            handleTabIndent(event);
        }

        // Any other keydown that's not a custom action might affect native undo,
        // but the 'input' event listener is better for catching actual text changes.
    });
}