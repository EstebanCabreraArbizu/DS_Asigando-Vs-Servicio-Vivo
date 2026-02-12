// dashboard/static/dashboard/upload.js

// CSRF token para requests seguros
function getCSRFToken() {
    return document.querySelector('[name=csrfmiddlewaretoken]')?.value ||
        getCookie('csrftoken');
}

function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

// Estado
let filePA = null;
let fileSV = null;
let currentJobId = null;
let pollInterval = null;
let jobToDelete = null;

// Inicialización
document.addEventListener('DOMContentLoaded', () => {
    if (document.body.dataset.canUpload === 'true') {
        setupDropzone('pa');
        setupDropzone('sv');

        // Listener para el periodo
        document.getElementById('period-month')?.addEventListener('change', updateSubmitButton);

        // Listeners para botones de quitar archivo
        document.getElementById('clear-pa-btn')?.addEventListener('click', (e) => {
            e.stopPropagation();
            clearFile('pa');
        });
        document.getElementById('clear-sv-btn')?.addEventListener('click', (e) => {
            e.stopPropagation();
            clearFile('sv');
        });
    }
});

// Configurar dropzone
function setupDropzone(type) {
    const dropzone = document.getElementById(`dropzone-${type}`);
    const fileInput = document.getElementById(`file-${type}`);

    if (!dropzone || !fileInput) return;

    // Click para seleccionar
    dropzone.addEventListener('click', () => fileInput.click());

    // Cambio de archivo
    fileInput.addEventListener('change', (e) => {
        if (e.target.files[0]) {
            setFile(type, e.target.files[0]);
        }
    });

    // Drag events
    dropzone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropzone.classList.add('dragover');
    });

    dropzone.addEventListener('dragleave', () => {
        dropzone.classList.remove('dragover');
    });

    dropzone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropzone.classList.remove('dragover');
        if (e.dataTransfer.files[0]) {
            setFile(type, e.dataTransfer.files[0]);
        }
    });
}

// Establecer archivo
function setFile(type, file) {
    const dropzone = document.getElementById(`dropzone-${type}`);
    const contentDiv = document.getElementById(`dropzone-${type}-content`);
    const fileDiv = document.getElementById(`dropzone-${type}-file`);
    const nameEl = document.getElementById(`file-${type}-name`);
    const sizeEl = document.getElementById(`file-${type}-size`);

    if (type === 'pa') filePA = file;
    else fileSV = file;

    if (dropzone) dropzone.classList.add('has-file');
    if (contentDiv) contentDiv.classList.add('hidden');
    if (fileDiv) fileDiv.classList.remove('hidden');
    if (nameEl) nameEl.textContent = file.name;
    if (sizeEl) sizeEl.textContent = formatFileSize(file.size);

    updateSubmitButton();
}

// Limpiar archivo
function clearFile(type) {
    const dropzone = document.getElementById(`dropzone-${type}`);
    const contentDiv = document.getElementById(`dropzone-${type}-content`);
    const fileDiv = document.getElementById(`dropzone-${type}-file`);
    const fileInput = document.getElementById(`file-${type}`);

    if (type === 'pa') filePA = null;
    else fileSV = null;

    if (dropzone) dropzone.classList.remove('has-file');
    if (contentDiv) contentDiv.classList.remove('hidden');
    if (fileDiv) fileDiv.classList.add('hidden');
    if (fileInput) fileInput.value = '';

    updateSubmitButton();
}

// Actualizar botón submit
function updateSubmitButton() {
    const btn = document.getElementById('submit-btn');
    const periodInput = document.getElementById('period-month');
    if (btn) {
        const hasFiles = filePA && fileSV;
        const hasPeriod = periodInput && periodInput.value;
        btn.disabled = !hasFiles || !hasPeriod;
    }
}

// Formatear tamaño
function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

// Submit handler
document.addEventListener('DOMContentLoaded', () => {
    const submitBtn = document.getElementById('submit-btn');
    if (submitBtn && document.body.dataset.canUpload === 'true') {
        submitBtn.addEventListener('click', async () => {
            if (!filePA || !fileSV) return;

            const btn = document.getElementById('submit-btn');
            const progressSection = document.getElementById('progress-section');
            const resultSection = document.getElementById('result-section');

            btn.disabled = true;
            document.getElementById('submit-text').textContent = 'Procesando...';
            progressSection.classList.remove('hidden');
            resultSection.classList.add('hidden');

            // Preparar FormData
            const formData = new FormData();
            formData.append('input_personal_asignado', filePA);
            formData.append('input_servicio_vivo', fileSV);

            const periodMonth = document.getElementById('period-month').value;
            if (periodMonth) {
                formData.append('period_month', periodMonth);
            }

            try {
                // Enviar archivos
                updateProgress(10, 'Subiendo archivos...');

                const apiRoot = document.body.dataset.apiRoot || '/dashboard/';
                const response = await fetch(`${apiRoot}api/v1/jobs/`, {
                    method: 'POST',
                    body: formData,
                    credentials: 'same-origin'
                });

                if (!response.ok) {
                    const error = await response.json();
                    throw new Error(error.detail || error.message || 'Error al crear el job');
                }

                const data = await response.json();
                currentJobId = data.job_id;

                updateProgress(30, 'Archivos subidos. Procesando análisis...');

                // Polling del estado
                pollJobStatus();

            } catch (error) {
                showError(error.message);
            }
        });
    }
});

// Poll job status
function pollJobStatus() {
    pollInterval = setInterval(async () => {
        try {
            const apiRoot = document.body.dataset.apiRoot || '/dashboard/';
            const response = await fetch(`${apiRoot}api/v1/jobs/${currentJobId}/status/`, {
                credentials: 'same-origin'
            });
            const data = await response.json();

            if (data.status === 'succeeded') {
                clearInterval(pollInterval);
                updateProgress(100, '¡Completado!');
                showSuccess();
                refreshJobsList();
            } else if (data.status === 'failed') {
                clearInterval(pollInterval);
                showError(data.error_message || 'Error desconocido');
                refreshJobsList();
            } else if (data.status === 'running') {
                updateProgress(60, 'Ejecutando análisis PA vs SV...');
            } else {
                updateProgress(40, 'En cola de procesamiento...');
            }
        } catch (error) {
            clearInterval(pollInterval);
            showError('Error al verificar estado: ' + error.message);
        }
    }, 1500);
}

// Actualizar progreso
function updateProgress(percent, status) {
    document.getElementById('progress-bar').style.width = percent + '%';
    document.getElementById('progress-percent').textContent = percent + '%';
    document.getElementById('progress-status').textContent = status;
}

// Mostrar éxito
function showSuccess() {
    const apiRoot = document.body.dataset.apiRoot || '/dashboard/';
    document.getElementById('progress-section').classList.add('hidden');
    document.getElementById('result-section').classList.remove('hidden');
    document.getElementById('result-success').classList.remove('hidden');
    document.getElementById('result-error').classList.add('hidden');
    document.getElementById('download-link').href = `${apiRoot}api/v1/jobs/${currentJobId}/excel/`;
    document.getElementById('submit-text').textContent = 'Iniciar Análisis';
}

// Mostrar error
function showError(message) {
    document.getElementById('progress-section').classList.add('hidden');
    document.getElementById('result-section').classList.remove('hidden');
    document.getElementById('result-success').classList.add('hidden');
    document.getElementById('result-error').classList.remove('hidden');
    document.getElementById('error-message').textContent = message;
    document.getElementById('submit-text').textContent = 'Iniciar Análisis';
    document.getElementById('submit-btn').disabled = false;
}

// Reset form
function resetForm() {
    clearFile('pa');
    clearFile('sv');
    document.getElementById('period-month').value = '';
    document.getElementById('progress-section').classList.add('hidden');
    document.getElementById('result-section').classList.add('hidden');
    document.getElementById('submit-btn').disabled = true;
    document.getElementById('submit-text').textContent = 'Iniciar Análisis';
    currentJobId = null;
    if (pollInterval) clearInterval(pollInterval);
}
document.getElementById('clear-pa-btn')?.addEventListener('click', (e) => {e.stopPropagation(); clearFile('pa');});
document.getElementById('clear-sv-btn')?.addEventListener('click', (e) => {e.stopPropagation(); clearFile('sv');});
document.getElementById('reset-form-btn')?.addEventListener('click', resetForm);
document.getElementById('reset-form-btn-2')?.addEventListener('click', resetForm);
document.getElementById('refresh-jobs-btn')?.addEventListener('click', refreshJobsList);
document.getElementById('cancel-delete-btn')?.addEventListener('click', closeDeleteModal);
document.getElementById('confirm-delete-btn')?.addEventListener('click', confirmDelete);
document.getElementById('logout-btn').addEventListener('click', (e) => {
    e.preventDefault();
    document.getElementById('logout-form').submit();
});
// CRUD: Eliminar job
document.addEventListener('click', (e) => {
    const btn = e.target.closest('.delete-job-btn');
    if (btn) deleteJob(btn.dataset.jobId);
});
async function deleteJob(jobId) {
    if (document.body.dataset.canDelete !== 'true') {
        alert('No tienes permisos para eliminar análisis');
        return;
    }
    jobToDelete = jobId;
    const modal = document.getElementById('delete-modal');
    modal.classList.remove('hidden');
    modal.classList.add('flex');
}

function closeDeleteModal() {
    const modal = document.getElementById('delete-modal');
    if (modal) {
        modal.classList.add('hidden');
        modal.classList.remove('flex');
    }
    jobToDelete = null;
}

async function confirmDelete() {
    if (!jobToDelete) return;

    try {
        const apiRoot = document.body.dataset.apiRoot || '/dashboard/';
        const response = await fetch(`${apiRoot}api/v1/jobs/${jobToDelete}/`, {
            method: 'DELETE',
            credentials: 'same-origin'
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Error al eliminar');
        }

        // Eliminar fila de la tabla
        const row = document.querySelector(`tr[data-job-id="${jobToDelete}"]`);
        if (row) row.remove();

        closeDeleteModal();

        // Mostrar notificación
        showNotification('Job eliminado exitosamente', 'success');
    } catch (error) {
        alert('Error: ' + error.message);
    }
}

// Refrescar lista de jobs
async function refreshJobsList() {
    try {
        const apiRoot = document.body.dataset.apiRoot || '/dashboard/';
        const response = await fetch(`${apiRoot}api/v1/jobs/?limit=10`, {
            credentials: 'same-origin'
        });
        const data = await response.json();

        // Recargar página para simplicidad (se puede optimizar con renderizado dinámico)
        window.location.reload();
    } catch (error) {
        console.error('Error refreshing jobs:', error);
    }
}

// Notificación simple
function showNotification(message, type = 'info') {
    const colors = {
        success: 'bg-green-500',
        error: 'bg-red-500',
        info: 'bg-blue-500'
    };

    const notification = document.createElement('div');
    notification.className = `fixed bottom-4 right-4 ${colors[type]} text-white px-6 py-3 rounded-lg shadow-lg z-50`;
    notification.textContent = message;
    document.body.appendChild(notification);

    setTimeout(() => notification.remove(), 3000);
}
