// static/wiki/JS/chunked_upload.js
// Uploads a File in fixed-size chunks so large attachments never depend on one long request.
// Each chunk is retried with backoff. The server always answers with how many bytes it holds,
// so a retry resumes from there instead of starting the file over.

const CHUNKED_UPLOAD_MAX_RETRIES = 8;
const CHUNKED_UPLOAD_MAX_BACKOFF_MS = 15000;

class UploadCancelledError extends Error {}

class UploadFailedError extends Error {
    constructor(message, fieldErrors = null) {
        super(message);
        this.fieldErrors = fieldErrors;
    }
}

async function _chunkedUploadPostJson(url, csrfToken, body) {
    const response = await fetch(url, {
        method: 'POST',
        headers: { 'X-CSRFToken': csrfToken, 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
    });
    let data = null;
    try { data = await response.json(); } catch (e) { /* non-JSON, e.g. a login redirect */ }
    return { ok: response.ok, status: response.status, data };
}

function _chunkedUploadSendChunk(url, csrfToken, blob, offset, onChunkProgress, xhrRef) {
    return new Promise((resolve, reject) => {
        const xhr = new XMLHttpRequest();
        xhrRef.current = xhr;
        xhr.open('POST', url);
        xhr.setRequestHeader('X-CSRFToken', csrfToken);
        xhr.setRequestHeader('X-Upload-Offset', String(offset));
        xhr.setRequestHeader('Content-Type', 'application/octet-stream');
        xhr.upload.onprogress = (e) => { if (e.lengthComputable) onChunkProgress(e.loaded); };
        xhr.onload = () => {
            let data = null;
            try { data = JSON.parse(xhr.responseText); } catch (e) { /* non-JSON error page */ }
            resolve({ status: xhr.status, data });
        };
        xhr.onerror = () => reject(new Error('Network error'));
        xhr.onabort = () => reject(new UploadCancelledError('Upload cancelled.'));
        xhr.send(blob);
    });
}

function _isRetryableStatus(status) {
    return status === 0 || status === 408 || status === 429 || status >= 500;
}

/**
 * Starts uploading `file`. Returns { promise, cancel }.
 * `promise` resolves with the server's completion payload ({status, message, file}).
 * Callbacks: onProgress(sentBytes, totalBytes), onRetry(attempt, maxAttempts).
 */
function startChunkedUpload({ file, filenameSlug, initUrl, csrfToken, onProgress, onRetry }) {
    const state = { cancelled: false, xhr: { current: null }, uploadUrl: null };

    const promise = (async () => {
        const init = await _chunkedUploadPostJson(initUrl, csrfToken, {
            filename: file.name,
            filename_slug: filenameSlug || '',
            size: file.size,
        });
        if (!init.ok || !init.data || init.data.status !== 'success') {
            const data = init.data || {};
            throw new UploadFailedError(data.message || `Upload could not start (HTTP ${init.status}).`, data.errors);
        }

        state.uploadUrl = `${initUrl}${init.data.upload_id}/`;
        const chunkSize = init.data.chunk_size;
        let offset = 0;
        let failures = 0;

        try {
            while (offset < file.size) {
                if (state.cancelled) throw new UploadCancelledError('Upload cancelled.');

                const chunkStart = offset;
                const blob = file.slice(chunkStart, Math.min(chunkStart + chunkSize, file.size));
                let result = null;
                try {
                    result = await _chunkedUploadSendChunk(
                        state.uploadUrl, csrfToken, blob, chunkStart,
                        (loaded) => onProgress && onProgress(chunkStart + loaded, file.size),
                        state.xhr,
                    );
                } catch (err) {
                    if (err instanceof UploadCancelledError) throw err;
                    // Network failure: fall through to the retry logic with result = null.
                }

                const received = result && result.data && typeof result.data.received === 'number'
                    ? result.data.received : null;

                if (result && result.status === 200 && received !== null) {
                    offset = received;
                    failures = 0;
                    if (onProgress) onProgress(offset, file.size);
                    continue;
                }
                if (result && result.status === 409 && received !== null) {
                    // Server holds a different amount than we assumed; resume from its position.
                    offset = received;
                } else if (result && !_isRetryableStatus(result.status)) {
                    const message = (result.data && result.data.message) || `Upload rejected (HTTP ${result.status}).`;
                    throw new UploadFailedError(message);
                }

                failures++;
                if (failures > CHUNKED_UPLOAD_MAX_RETRIES) {
                    throw new UploadFailedError('Upload failed after repeated network errors.');
                }
                if (onRetry) onRetry(failures, CHUNKED_UPLOAD_MAX_RETRIES);
                const delay = Math.min(1000 * 2 ** (failures - 1), CHUNKED_UPLOAD_MAX_BACKOFF_MS);
                await new Promise((r) => setTimeout(r, delay));
            }

            if (state.cancelled) throw new UploadCancelledError('Upload cancelled.');
            const done = await _chunkedUploadPostJson(`${state.uploadUrl}complete/`, csrfToken, {});
            if (!done.ok || !done.data || done.data.status !== 'success') {
                throw new UploadFailedError((done.data && done.data.message) || `Upload could not be finalized (HTTP ${done.status}).`);
            }
            return done.data;
        } catch (err) {
            // Free the server-side staging space; abandoned uploads are also purged after a day.
            _chunkedUploadPostJson(`${state.uploadUrl}cancel/`, csrfToken, {}).catch(() => {});
            throw err;
        }
    })();

    return {
        promise,
        cancel() {
            state.cancelled = true;
            if (state.xhr.current) state.xhr.current.abort();
        },
    };
}

function formatUploadBytes(bytes) {
    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    let value = bytes;
    let unit = 0;
    while (value >= 1024 && unit < units.length - 1) {
        value /= 1024;
        unit++;
    }
    return `${value.toFixed(unit === 0 ? 0 : 1)} ${units[unit]}`;
}
