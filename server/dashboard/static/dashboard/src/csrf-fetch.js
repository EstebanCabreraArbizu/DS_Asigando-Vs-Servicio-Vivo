(function () {
    function getCookie(name) {
        if (!document.cookie) {
            return null;
        }

        const cookies = document.cookie.split(';');
        for (let index = 0; index < cookies.length; index += 1) {
            const cookie = cookies[index].trim();
            if (cookie.substring(0, name.length + 1) === name + '=') {
                return decodeURIComponent(cookie.substring(name.length + 1));
            }
        }
        return null;
    }

    function getCSRFToken() {
        const tokenField = document.querySelector('[name=csrfmiddlewaretoken]');
        if (tokenField && tokenField.value) {
            return tokenField.value;
        }
        return getCookie('__Host-csrftoken') || getCookie('csrftoken');
    }

    function isUnsafeMethod(method) {
        const normalizedMethod = (method || 'GET').toUpperCase();
        return !['GET', 'HEAD', 'OPTIONS', 'TRACE'].includes(normalizedMethod);
    }

    const originalFetch = window.fetch;
    window.fetch = function patchedFetch(input, init = {}) {
        const requestUrl = typeof input === 'string' ? input : input.url;
        const requestMethod = init.method || (typeof input !== 'string' ? input.method : 'GET');

        if (!isUnsafeMethod(requestMethod)) {
            return originalFetch(input, init);
        }

        const token = getCSRFToken();
        if (!token) {
            return originalFetch(input, init);
        }

        const url = new URL(requestUrl, window.location.origin);
        if (url.origin !== window.location.origin) {
            return originalFetch(input, init);
        }

        const headers = new Headers(init.headers || (typeof input !== 'string' ? input.headers : undefined));
        if (!headers.has('X-CSRFToken')) {
            headers.set('X-CSRFToken', token);
        }

        return originalFetch(input, {
            ...init,
            headers,
        });
    };
})();
