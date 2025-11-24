const API_URL = 'http://localhost:8000';

// State
let token = localStorage.getItem('token');

// DOM Elements
const app = document.getElementById('app');
const authContainer = document.getElementById('auth-container');
const dashboardContainer = document.getElementById('dashboard-container');
const loginForm = document.getElementById('login-form');
const registerForm = document.getElementById('register-form');
const tabLogin = document.getElementById('tab-login');
const tabRegister = document.getElementById('tab-register');
const fileInput = document.getElementById('file-input');
const uploadPreview = document.getElementById('upload-preview');
const uploadPlaceholder = document.getElementById('upload-placeholder');
const fileNameDisplay = document.getElementById('file-name');
const previewImage = document.getElementById('preview-image');
const uploadBtn = document.getElementById('upload-btn');
const cancelUploadBtn = document.getElementById('cancel-upload-btn');
const imageGrid = document.getElementById('image-grid');
const dropZone = document.getElementById('drop-zone');
const loadingSpinner = document.getElementById('loading-spinner');
const emptyState = document.getElementById('empty-state');
const alertMessage = document.getElementById('alert-message');
const alertText = document.getElementById('alert-text');

// Modal Elements
const imageModal = document.getElementById('image-modal');
const closeModalBtn = document.querySelector('.close-modal');
const modalImage = document.getElementById('modal-image');
const modalFilename = document.getElementById('modal-filename');
const modalDate = document.getElementById('modal-date');
const modalLabels = document.getElementById('modal-labels');

// Initialization
function init() {
    if (token) {
        showDashboard();
    } else {
        showAuth();
    }
}

// Navigation
function showAuth() {
    authContainer.classList.remove('hidden');
    dashboardContainer.classList.add('hidden');
}

function showDashboard() {
    authContainer.classList.add('hidden');
    dashboardContainer.classList.remove('hidden');
    fetchImages();
}

function showAlert(type, message) {
    alertMessage.className = `alert alert-${type}`;
    alertText.textContent = message;
    alertMessage.classList.remove('hidden');
    
    // Auto hide after 5 seconds
    setTimeout(() => {
        alertMessage.classList.add('hidden');
    }, 5000);
}

function switchTab(tab) {
    if (tab === 'login') {
        loginForm.classList.add('active');
        registerForm.classList.remove('active');
        tabLogin.classList.add('active');
        tabRegister.classList.remove('active');
        loginForm.style.display = 'block';
        registerForm.style.display = 'none';
    } else {
        loginForm.classList.remove('active');
        registerForm.classList.add('active');
        tabLogin.classList.remove('active');
        tabRegister.classList.add('active');
        loginForm.style.display = 'none';
        registerForm.style.display = 'block';
    }
}

function logout() {
    token = null;
    localStorage.removeItem('token');
    showAuth();
}

// Auth Actions
loginForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const username = document.getElementById('login-username').value;
    const password = document.getElementById('login-password').value;
    const errorMsg = document.getElementById('login-error');
    
    try {
        const res = await fetch(`${API_URL}/api/login?username=${encodeURIComponent(username)}&password=${encodeURIComponent(password)}`, {
            method: 'POST'
        });
        
        const data = await res.json();
        
        if (res.ok && data.token) {
            token = data.token;
            localStorage.setItem('token', token);
            errorMsg.textContent = '';
            showDashboard();
        } else {
            errorMsg.textContent = data.error || 'Login failed';
        }
    } catch (err) {
        errorMsg.textContent = 'Network error';
        console.error(err);
    }
});

registerForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const username = document.getElementById('register-username').value;
    const password = document.getElementById('register-password').value;
    const errorMsg = document.getElementById('register-error');
    
    try {
        const res = await fetch(`${API_URL}/api/signup?username=${encodeURIComponent(username)}&password=${encodeURIComponent(password)}`, {
            method: 'POST'
        });
        
        const data = await res.json();
        
        if (res.ok) {
            alert('Registration successful! Please login.');
            switchTab('login');
            errorMsg.textContent = '';
        } else {
            errorMsg.textContent = 'Registration failed';
        }
    } catch (err) {
        errorMsg.textContent = 'Network error';
        console.error(err);
    }
});

// File Upload Handling
dropZone.addEventListener('click', (e) => {
    // Only trigger file input if clicking on the placeholder area, not buttons
    if (e.target.closest('#upload-placeholder')) {
        fileInput.click();
    }
});

dropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropZone.style.borderColor = 'var(--primary)';
    dropZone.style.backgroundColor = 'var(--primary-light)';
});

dropZone.addEventListener('dragleave', (e) => {
    e.preventDefault();
    dropZone.style.borderColor = 'var(--border)';
    dropZone.style.backgroundColor = 'transparent';
});

dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropZone.style.borderColor = 'var(--border)';
    dropZone.style.backgroundColor = 'transparent';
    
    if (e.dataTransfer.files.length) {
        handleFileSelect(e.dataTransfer.files[0]);
    }
});

fileInput.addEventListener('change', (e) => {
    if (e.target.files.length) {
        handleFileSelect(e.target.files[0]);
    }
});

let selectedFile = null;

function handleFileSelect(file) {
    if (!file.type.startsWith('image/')) {
        showAlert('error', 'Please select an image file');
        return;
    }
    selectedFile = file;
    fileNameDisplay.textContent = file.name;
    
    // Show preview
    previewImage.src = URL.createObjectURL(file);
    
    uploadPreview.classList.remove('hidden');
    uploadPlaceholder.classList.add('hidden');
}

cancelUploadBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    resetUpload();
});

function resetUpload() {
    selectedFile = null;
    fileInput.value = '';
    previewImage.src = '';
    uploadPreview.classList.add('hidden');
    uploadPlaceholder.classList.remove('hidden');
}

uploadBtn.addEventListener('click', async (e) => {
    e.stopPropagation();
    if (!selectedFile) return;
    
    const formData = new FormData();
    formData.append('file', selectedFile);
    
    uploadBtn.disabled = true;
    uploadBtn.textContent = 'Uploading...';
    
    try {
        const res = await fetch(`${API_URL}/api/upload`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`
            },
            body: formData
        });
        
        if (res.ok) {
            const data = await res.json();
            showAlert('success', `Image uploaded successfully! Found ${data.labels?.length || 0} labels.`);
            resetUpload();
            fetchImages(); // Refresh list
        } else {
            const error = await res.json();
            showAlert('error', error.detail || 'Upload failed');
        }
    } catch (err) {
        console.error(err);
        showAlert('error', 'Error uploading file');
    } finally {
        uploadBtn.disabled = false;
        uploadBtn.textContent = 'Upload to Cloud';
    }
});

// Image Gallery
async function fetchImages() {
    loadingSpinner.classList.remove('hidden');
    imageGrid.innerHTML = '';
    emptyState.classList.add('hidden');

    try {
        const res = await fetch(`${API_URL}/api/images`, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        
        if (res.status === 401) {
            logout();
            return;
        }
        
        const images = await res.json();
        renderImages(images);
    } catch (err) {
        console.error('Failed to fetch images', err);
        showAlert('error', 'Failed to load images');
    } finally {
        loadingSpinner.classList.add('hidden');
    }
}

// Modal Logic
function openModal(img) {
    modalImage.src = `${API_URL}${img.image_url}`;
    modalFilename.textContent = img.filename;
    
    // Format date
    const date = img.created_at ? new Date(img.created_at).toLocaleString() : 'Unknown date';
    modalDate.textContent = `Uploaded on ${date}`;
    
    // Labels
    modalLabels.innerHTML = img.labels.map(label => 
        `<span class="badge">${label}</span>`
    ).join('');
    
    imageModal.classList.remove('hidden');
}

function closeModal() {
    imageModal.classList.add('hidden');
    modalImage.src = '';
}

if (closeModalBtn) {
    closeModalBtn.addEventListener('click', closeModal);
}

if (imageModal) {
    imageModal.addEventListener('click', (e) => {
        if (e.target === imageModal) {
            closeModal();
        }
    });
}

function renderImages(images) {
    imageGrid.innerHTML = '';
    
    if (images.length === 0) {
        emptyState.classList.remove('hidden');
        return;
    }
    
    images.forEach(img => {
        const card = document.createElement('div');
        card.className = 'image-card';
        card.style.cursor = 'pointer';
        card.onclick = (e) => {
            if (e.target.closest('.delete-btn')) return;
            openModal(img);
        };
        
        const fullImageUrl = `${API_URL}${img.image_url}`;
        
        // Create badges HTML
        const badgesHtml = img.labels.slice(0, 3).map(label => 
            `<span class="badge">${label}</span>`
        ).join('');

        card.innerHTML = `
            <div class="image-wrapper">
                <img src="${fullImageUrl}" 
                     alt="${img.filename}" 
                     loading="lazy"
                     onerror="this.onerror=null; this.parentElement.innerHTML='<div style=\'position:absolute;top:0;left:0;width:100%;height:100%;display:flex;flex-direction:column;align-items:center;justify-content:center;background:#f8fafc;color:#94a3b8;\'><svg xmlns=\'http://www.w3.org/2000/svg\' width=\'24\' height=\'24\' viewBox=\'0 0 24 24\' fill=\'none\' stroke=\'currentColor\' stroke-width=\'2\' stroke-linecap=\'round\' stroke-linejoin=\'round\'><circle cx=\'12\' cy=\'12\' r=\'10\'/><line x1=\'12\' y1=\'8\' x2=\'12\' y2=\'12\'/><line x1=\'12\' y1=\'16\' x2=\'12.01\' y2=\'16\'/></svg><span style=\'font-size:0.75rem;margin-top:0.5rem\'>Image Error</span></div>'">
            </div>
            <div class="image-info">
                <div class="image-name" title="${img.filename}">${img.filename}</div>
                <div class="badge-container">
                    ${badgesHtml}
                </div>
                <button onclick="deleteImage(${img.id})" class="delete-btn">
                    <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
                    Delete
                </button>
            </div>
        `;
        imageGrid.appendChild(card);
    });
}

async function deleteImage(id) {
    if (!confirm('Are you sure you want to delete this image?')) return;
    
    try {
        const res = await fetch(`${API_URL}/api/images/${id}`, {
            method: 'DELETE',
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        
        if (res.ok) {
            showAlert('success', 'Image deleted successfully');
            fetchImages();
        } else {
            showAlert('error', 'Failed to delete image');
        }
    } catch (err) {
        console.error(err);
        showAlert('error', 'Error deleting image');
    }
}

// Start
// Ensure correct initial tab state
switchTab('login');
init();
