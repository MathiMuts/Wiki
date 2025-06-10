function initializeWikiEditorEnhancements(textareaElement, tabSize = 4) {
    if (!textareaElement) {
        return;
    }

    let lastUndoableState = null;
    let lastActionWasCustom = false;

    function saveUndoState() {
        lastUndoableState = {
            value: textareaElement.value,
            selectionStart: textareaElement.selectionStart,
            selectionEnd: textareaElement.selectionEnd,
        };
        lastActionWasCustom = true;
    }

    function performCustomUndo() {
        if (lastUndoableState) {
            textareaElement.value = lastUndoableState.value;
            textareaElement.setSelectionRange(lastUndoableState.selectionStart, lastUndoableState.selectionEnd);
            
            lastUndoableState = null;
            lastActionWasCustom = false;
            
            textareaElement.dispatchEvent(new Event('input', { bubbles: true, cancelable: true, _customAction: true }));
        }
    }

    function getCurrentLineBoundaries(text, cursorPos) {
        let lineStart = text.lastIndexOf('\n', cursorPos - 1) + 1;
        let lineEnd = text.indexOf('\n', cursorPos);
        if (lineEnd === -1 || lineEnd < cursorPos) { lineEnd = text.length; }
        return { lineStart, lineEnd };
    }

    function handleCutLine(event) {
        if (textareaElement.selectionStart === textareaElement.selectionEnd) {
            saveUndoState();
            event.preventDefault(); 

            const cursorPos = textareaElement.selectionStart;
            let originalText = textareaElement.value;
            const { lineStart, lineEnd: lineContentEnd } = getCurrentLineBoundaries(originalText, cursorPos);

            if (lineStart > lineContentEnd) return;

            let textToCopy = "";
            let nextCursorPos = lineStart;

            if (lineStart === lineContentEnd && lineStart === originalText.length && originalText.length > 0 && originalText.endsWith('\n')) {
                textareaElement.value = originalText.substring(0, originalText.length - 1);
                textToCopy = ""; 
                nextCursorPos = textareaElement.value.length;
            } else {
                textToCopy = originalText.substring(lineStart, lineContentEnd);
                let endOfCutPortion;
                if (lineContentEnd < originalText.length && originalText[lineContentEnd] === '\n') {
                    endOfCutPortion = lineContentEnd + 1;
                } else {
                    endOfCutPortion = lineContentEnd;
                }
                if (endOfCutPortion > originalText.length) endOfCutPortion = originalText.length;
                if (lineStart > endOfCutPortion) return;
                
                const textBefore = originalText.substring(0, lineStart);
                const textAfter = originalText.substring(endOfCutPortion);
                textareaElement.value = textBefore + textAfter;
            }

            if (navigator.clipboard && navigator.clipboard.writeText && textToCopy !== undefined) {
                navigator.clipboard.writeText(textToCopy).catch(err => { /* console.warn('Clipboard error:', err) */ });
            }
            
            textareaElement.setSelectionRange(nextCursorPos, nextCursorPos);
            textareaElement.dispatchEvent(new Event('input', { bubbles: true, cancelable: true, _customAction: true }));
        }
    }

    function handleTabIndent(event) {
        saveUndoState();
        event.preventDefault(); 

        const cursorPos = textareaElement.selectionStart;
        const text = textareaElement.value;
        const lineStartForTab = text.lastIndexOf('\n', cursorPos - 1) + 1;
        const currentColumn = cursorPos - lineStartForTab;
        const spacesToAddCount = tabSize - (currentColumn % tabSize);
        const spaces = ' '.repeat(spacesToAddCount);
        const before = text.substring(0, cursorPos);
        const after = text.substring(textareaElement.selectionEnd);
        textareaElement.value = before + spaces + after;
        const newCursorPos = cursorPos + spaces.length;
        textareaElement.setSelectionRange(newCursorPos, newCursorPos);
        textareaElement.dispatchEvent(new Event('input', { bubbles: true, cancelable: true, _customAction: true }));
    }

    textareaElement.addEventListener('input', function(event) {
        if (!event._customAction) {
            if (lastActionWasCustom) {
                lastUndoableState = null;
                lastActionWasCustom = false;
            }
        }
    });


    textareaElement.addEventListener('keydown', function(event) {
        // Custom Undo (Ctrl+Z or Cmd+Z)
        if ((event.ctrlKey || event.metaKey) && !event.shiftKey && (event.key === 'z' || event.key === 'Z')) {
            if (lastActionWasCustom && lastUndoableState) {
                event.preventDefault();
                performCustomUndo();
                return;
            }
        }

        // Cut Line Shortcut (Ctrl+X or Cmd+X)
        if ((event.ctrlKey || event.metaKey) && !event.shiftKey && !event.altKey && (event.key === 'x' || event.key === 'X' || event.code === 'KeyX')) {
            handleCutLine(event); 
        }

        // Tab Key
        if (event.key === 'Tab' && !event.ctrlKey && !event.metaKey && !event.altKey) {
            handleTabIndent(event);
        }
    });
}

document.addEventListener('DOMContentLoaded', function() {
    const editorTextarea = document.getElementById('wiki-form-content-textarea');
    if (editorTextarea) {
        initializeWikiEditorEnhancements(editorTextarea, 4);
    }
});