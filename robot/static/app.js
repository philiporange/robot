/**
 * Robot Web Interface - Main Application
 * Handles authentication, conversations, messaging, and UI interactions.
 */

// State
let token = localStorage.getItem('robot_token');
let currentUser = null;
let currentConversation = null;
let conversations = [];
let currentPath = '';
let selectedFolder = null;
let currentAbortController = null;
let thinkingInterval = null;
let thinkingStartTime = null;

// DOM Elements
const elements = {
    // Auth
    authModal: document.getElementById('authModal'),
    authForm: document.getElementById('authForm'),
    authUsername: document.getElementById('authUsername'),
    authPassword: document.getElementById('authPassword'),
    authError: document.getElementById('authError'),
    authSubmitText: document.getElementById('authSubmitText'),
    toggleAuth: document.getElementById('toggleAuth'),
    logoutBtn: document.getElementById('logoutBtn'),

    // New Conversation Modal
    newConvModal: document.getElementById('newConvModal'),
    newConvBtn: document.getElementById('newConvBtn'),
    closeNewConvBtn: document.getElementById('closeNewConvBtn'),
    folderUp: document.getElementById('folderUp'),
    currentPath: document.getElementById('currentPath'),
    folderList: document.getElementById('folderList'),
    newFolderName: document.getElementById('newFolderName'),
    createFolderBtn: document.getElementById('createFolderBtn'),
    modelSelect: document.getElementById('modelSelect'),
    convTitle: document.getElementById('convTitle'),
    createConvBtn: document.getElementById('createConvBtn'),

    // Diff Modal
    diffModal: document.getElementById('diffModal'),
    diffTitle: document.getElementById('diffTitle'),
    diffContent: document.getElementById('diffContent'),
    closeDiffBtn: document.getElementById('closeDiffBtn'),

    // Sidebar
    convList: document.getElementById('convList'),

    // Chat
    chatHeader: document.getElementById('chatHeader'),
    convTitleDisplay: document.getElementById('convTitleDisplay'),
    convPath: document.getElementById('convPath'),
    convModel: document.getElementById('convModel'),
    showFilesBtn: document.getElementById('showFilesBtn'),
    filesPanel: document.getElementById('filesPanel'),
    closeFilesBtn: document.getElementById('closeFilesBtn'),
    filesList: document.getElementById('filesList'),
    messages: document.getElementById('messages'),
    inputArea: document.getElementById('inputArea'),
    messageInput: document.getElementById('messageInput'),
    sendBtn: document.getElementById('sendBtn'),
    statusBar: document.getElementById('statusBar'),
    thinkingTimer: document.getElementById('thinkingTimer'),
    cancelBtn: document.getElementById('cancelBtn'),
};

// Utility Functions
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function showModal(modal) {
    modal.classList.remove('hidden');
}

function hideModal(modal) {
    modal.classList.add('hidden');
}

// Timer Functions
function startThinkingTimer() {
    thinkingStartTime = Date.now();
    elements.thinkingTimer.textContent = '0.0s';
    thinkingInterval = setInterval(() => {
        const elapsed = (Date.now() - thinkingStartTime) / 1000;
        elements.thinkingTimer.textContent = elapsed.toFixed(1) + 's';
    }, 100);
}

function stopThinkingTimer() {
    if (thinkingInterval) {
        clearInterval(thinkingInterval);
        thinkingInterval = null;
    }
}

// API Functions
async function api(endpoint, options = {}) {
    const headers = { 'Content-Type': 'application/json' };
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const response = await fetch(`/api${endpoint}`, {
        ...options,
        headers: { ...headers, ...options.headers }
    });

    if (response.status === 401) {
        token = null;
        localStorage.removeItem('robot_token');
        showModal(elements.authModal);
        throw new Error('Unauthorized');
    }

    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'API Error');
    }

    return response.json();
}

// Auth Functions
let isRegistering = false;

function showAuthModal() {
    showModal(elements.authModal);
}

function hideAuthModal() {
    hideModal(elements.authModal);
}

elements.toggleAuth.onclick = () => {
    isRegistering = !isRegistering;
    elements.authSubmitText.textContent = isRegistering ? 'Create Account' : 'Sign In';
    elements.toggleAuth.textContent = isRegistering ? 'Sign in instead' : 'Create account';
};

elements.authForm.onsubmit = async (e) => {
    e.preventDefault();
    const username = elements.authUsername.value;
    const password = elements.authPassword.value;

    try {
        const endpoint = isRegistering ? '/auth/register' : '/auth/login';
        const result = await api(endpoint, {
            method: 'POST',
            body: JSON.stringify({ username, password })
        });

        token = result.access_token;
        localStorage.setItem('robot_token', token);
        currentUser = { id: result.user_id, username: result.username };
        hideAuthModal();
        loadConversations();
    } catch (err) {
        elements.authError.textContent = err.message;
        elements.authError.classList.remove('hidden');
    }
};

elements.logoutBtn.onclick = () => {
    token = null;
    localStorage.removeItem('robot_token');
    currentUser = null;
    currentConversation = null;
    showAuthModal();
};

// Conversation Functions
async function loadConversations() {
    try {
        conversations = await api('/conversations');
        renderConversations();
    } catch (err) {
        console.error('Failed to load conversations:', err);
    }
}

function renderConversations() {
    elements.convList.innerHTML = conversations.map(c => `
        <button onclick="selectConversation('${c.id}')"
            class="conv-item ${currentConversation?.id === c.id ? 'active' : ''}">
            ${escapeHtml(c.title)}
        </button>
    `).join('');
}

async function selectConversation(id) {
    currentConversation = conversations.find(c => c.id === id);
    if (!currentConversation) return;

    renderConversations();

    elements.chatHeader.classList.remove('hidden');
    elements.inputArea.classList.remove('hidden');
    elements.convTitleDisplay.textContent = currentConversation.title;
    elements.convPath.textContent = currentConversation.working_dir;
    elements.convModel.textContent = currentConversation.model;

    await loadMessages();
    await loadModifiedFiles();
}

// Make selectConversation available globally
window.selectConversation = selectConversation;

// Message Functions
async function loadMessages() {
    if (!currentConversation) return;

    try {
        const messages = await api(`/conversations/${currentConversation.id}/messages`);
        renderMessages(messages);
    } catch (err) {
        console.error('Failed to load messages:', err);
    }
}

function renderMessages(messages) {
    if (messages.length === 0) {
        elements.messages.innerHTML = `
            <div class="messages-inner">
                <p class="empty-state">Start the conversation</p>
            </div>
        `;
        return;
    }

    elements.messages.innerHTML = `
        <div class="messages-inner">
            ${messages.map(m => renderMessage(m)).join('')}
        </div>
    `;

    // Highlight code blocks
    elements.messages.querySelectorAll('pre code').forEach(block => {
        hljs.highlightElement(block);
    });

    // Scroll to bottom
    elements.messages.scrollTop = elements.messages.scrollHeight;
}

function renderMessage(m) {
    const filesHtml = m.files_modified && m.files_modified.length > 0 ? `
        <div class="message-files">
            ${m.files_modified.map(f => `
                <button onclick="showDiff('${escapeHtml(f)}')" class="file-tag">
                    ${escapeHtml(f.split('/').pop())}
                </button>
            `).join('')}
        </div>
    ` : '';

    return `
        <div class="message fade-up">
            <div class="message-header">
                <span class="message-role ${m.role}">${m.role === 'user' ? 'You' : 'Robot'}</span>
                ${m.duration ? `<span class="message-time">${(m.duration / 1000).toFixed(1)}s</span>` : ''}
            </div>
            <div class="message-content">${marked.parse(m.content)}</div>
            ${filesHtml}
        </div>
    `;
}

// Modified Files Functions
async function loadModifiedFiles() {
    if (!currentConversation) return;

    try {
        const files = await api(`/conversations/${currentConversation.id}/files`);

        if (files.length > 0) {
            elements.showFilesBtn.classList.remove('hidden');
            elements.showFilesBtn.textContent = `${files.length} files`;
            elements.filesList.innerHTML = files.map(f => `
                <button onclick="showDiff('${escapeHtml(f.file_path)}')"
                    class="file-tag" title="${escapeHtml(f.file_path)}">
                    ${escapeHtml(f.file_path.split('/').pop())}
                </button>
            `).join('');
        } else {
            elements.showFilesBtn.classList.add('hidden');
            hideModal(elements.filesPanel);
        }
    } catch (err) {
        console.error('Failed to load modified files:', err);
    }
}

elements.showFilesBtn.onclick = () => {
    elements.filesPanel.classList.toggle('hidden');
};

elements.closeFilesBtn.onclick = () => {
    elements.filesPanel.classList.add('hidden');
};

// Diff Functions
async function showDiff(filePath) {
    try {
        const result = await api(`/files/diff?file_path=${encodeURIComponent(filePath)}`);
        elements.diffTitle.textContent = filePath;
        elements.diffContent.textContent = result.diff || 'No changes';
        showModal(elements.diffModal);
    } catch (err) {
        console.error('Failed to load diff:', err);
    }
}

// Make showDiff available globally
window.showDiff = showDiff;

elements.closeDiffBtn.onclick = () => {
    hideModal(elements.diffModal);
};

// Send Message
async function sendMessage() {
    if (!currentConversation) return;

    const content = elements.messageInput.value.trim();
    if (!content) return;

    // Clear input and disable
    elements.messageInput.value = '';
    elements.messageInput.style.height = 'auto';
    elements.messageInput.disabled = true;
    elements.sendBtn.disabled = true;
    elements.statusBar.classList.remove('hidden');
    startThinkingTimer();

    currentAbortController = new AbortController();

    // Get the messages container
    let wrapper = elements.messages.querySelector('.messages-inner');
    if (!wrapper) {
        elements.messages.innerHTML = '<div class="messages-inner"></div>';
        wrapper = elements.messages.querySelector('.messages-inner');
    }

    // Add user message immediately
    wrapper.innerHTML += renderMessage({
        role: 'user',
        content: content
    });
    elements.messages.scrollTop = elements.messages.scrollHeight;

    try {
        const headers = { 'Content-Type': 'application/json' };
        if (token) headers['Authorization'] = `Bearer ${token}`;

        const response = await fetch(`/api/conversations/${currentConversation.id}/messages`, {
            method: 'POST',
            headers,
            body: JSON.stringify({ content }),
            signal: currentAbortController.signal
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'API Error');
        }

        const data = await response.json();

        // Add assistant message
        wrapper.innerHTML += renderMessage(data);

        // Highlight code blocks
        elements.messages.querySelectorAll('pre code').forEach(block => {
            hljs.highlightElement(block);
        });

        elements.messages.scrollTop = elements.messages.scrollHeight;

        // Refresh modified files and conversations
        await loadModifiedFiles();
        await loadConversations();

    } catch (err) {
        if (err.name === 'AbortError') {
            wrapper.innerHTML += `
                <div class="message fade-up">
                    <div class="message-content" style="color: var(--text-tertiary); font-style: italic;">
                        Cancelled
                    </div>
                </div>
            `;
        } else {
            wrapper.innerHTML += `
                <div class="message fade-up">
                    <div class="message-content" style="color: var(--error);">
                        ${escapeHtml(err.message)}
                    </div>
                </div>
            `;
        }
    } finally {
        stopThinkingTimer();
        currentAbortController = null;
        elements.messageInput.disabled = false;
        elements.sendBtn.disabled = false;
        elements.statusBar.classList.add('hidden');
    }
}

elements.cancelBtn.onclick = () => {
    if (currentAbortController) {
        currentAbortController.abort();
    }
};

elements.sendBtn.onclick = sendMessage;

elements.messageInput.onkeydown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
};

elements.messageInput.oninput = () => {
    elements.messageInput.style.height = 'auto';
    elements.messageInput.style.height = Math.min(elements.messageInput.scrollHeight, 200) + 'px';
};

// New Conversation Modal
elements.newConvBtn.onclick = async () => {
    showModal(elements.newConvModal);
    currentPath = '';
    selectedFolder = null;
    await loadFolders();
};

elements.closeNewConvBtn.onclick = () => {
    hideModal(elements.newConvModal);
};

// Folder Functions
async function loadFolders(path = null) {
    try {
        const url = path ? `/folders?path=${encodeURIComponent(path)}` : '/folders';
        const folders = await api(url);

        currentPath = path || '~/Code';
        elements.currentPath.textContent = currentPath;

        const dirs = folders.filter(f => f.is_dir);

        if (dirs.length === 0) {
            elements.folderList.innerHTML = '';
        } else {
            elements.folderList.innerHTML = dirs.map(f => `
                <div class="folder-item ${selectedFolder === f.path ? 'selected' : ''}"
                    onclick="selectNewFolder('${escapeHtml(f.path)}')">
                    <span class="folder-item-name">${escapeHtml(f.name)}</span>
                    <span class="folder-item-arrow" onclick="event.stopPropagation(); openFolder('${escapeHtml(f.path)}')">
                        <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 5l7 7-7 7"/>
                        </svg>
                    </span>
                </div>
            `).join('');
        }
    } catch (err) {
        console.error('Failed to load folders:', err);
    }
}

function selectNewFolder(path) {
    selectedFolder = path;
    loadFolders(currentPath === '~/Code' ? null : currentPath);
}

// Make selectNewFolder available globally
window.selectNewFolder = selectNewFolder;

function openFolder(path) {
    loadFolders(path);
}

// Make openFolder available globally
window.openFolder = openFolder;

elements.folderUp.onclick = () => {
    if (currentPath && currentPath !== '~/Code') {
        const parent = currentPath.split('/').slice(0, -1).join('/');
        loadFolders(parent || null);
    }
};

elements.createFolderBtn.onclick = async () => {
    const name = elements.newFolderName.value.trim();
    if (!name) return;

    try {
        const folders = await api('/folders');
        const parentPath = currentPath === '~/Code'
            ? (folders[0]?.path?.split('/').slice(0, -1).join('/') || '')
            : currentPath;

        await api('/folders', {
            method: 'POST',
            body: JSON.stringify({ name, parent_path: parentPath })
        });

        elements.newFolderName.value = '';
        await loadFolders(currentPath === '~/Code' ? null : currentPath);
    } catch (err) {
        alert(err.message);
    }
};

elements.createConvBtn.onclick = async () => {
    if (!selectedFolder) {
        alert('Please select a folder');
        return;
    }

    try {
        const conv = await api('/conversations', {
            method: 'POST',
            body: JSON.stringify({
                working_dir: selectedFolder,
                model: elements.modelSelect.value,
                title: elements.convTitle.value || null
            })
        });

        hideModal(elements.newConvModal);
        await loadConversations();
        selectConversation(conv.id);
    } catch (err) {
        alert(err.message);
    }
};

// Keyboard shortcut to close modals
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        hideModal(elements.newConvModal);
        hideModal(elements.diffModal);
    }
});

// Initialize
async function init() {
    if (token) {
        try {
            currentUser = await api('/auth/me');
            hideAuthModal();
            await loadConversations();
        } catch (err) {
            showAuthModal();
        }
    } else {
        showAuthModal();
    }
}

init();
