/**
 * Robot Web Interface - Main Application
 * Handles authentication, conversations, messaging, and UI interactions.
 * Uses cookie-based sessions - authenticate via `robot auth` CLI command.
 */

// State
let isAuthenticated = false;
let currentConversation = null;
let conversations = [];
let currentPath = '';
let selectedFolder = null;
let currentAbortController = null;
let thinkingInterval = null;
let thinkingStartTime = null;

// Browser state
let browserHistory = [];
let browserCurrentPath = null;
let browserViewingFile = false;

// DOM Elements
const elements = {
    // Auth
    authModal: document.getElementById('authModal'),
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

    // Browser Modal
    browserModal: document.getElementById('browserModal'),
    browserBackBtn: document.getElementById('browserBackBtn'),
    browserBreadcrumb: document.getElementById('browserBreadcrumb'),
    closeBrowserBtn: document.getElementById('closeBrowserBtn'),
    browserList: document.getElementById('browserList'),
    browserFile: document.getElementById('browserFile'),
    browserFileName: document.getElementById('browserFileName'),
    browserFileSize: document.getElementById('browserFileSize'),
    browserFileContent: document.getElementById('browserFileContent'),
    browseBtn: document.getElementById('browseBtn'),

    // Sidebar
    convList: document.getElementById('convList'),

    // Chat
    convTitleDisplay: document.getElementById('convTitleDisplay'),
    convPath: document.getElementById('convPath'),
    convModel: document.getElementById('convModel'),
    showFilesBtn: document.getElementById('showFilesBtn'),
    filesPanel: document.getElementById('filesPanel'),
    closeFilesBtn: document.getElementById('closeFilesBtn'),
    filesList: document.getElementById('filesList'),
    messages: document.getElementById('messages'),
    inputArea: document.getElementById('inputArea'),
    inputContainer: document.querySelector('.input-container'),
    messageInput: document.getElementById('messageInput'),
    sendBtn: document.getElementById('sendBtn'),
    statusBar: document.getElementById('statusBar'),
    thinkingTimer: document.getElementById('thinkingTimer'),
    cancelBtn: document.getElementById('cancelBtn'),
};

let lastScrollTop = 0;

// Scroll listener for folder list to hide/show header on mobile
if (elements.folderList) {
    elements.folderList.addEventListener('scroll', () => {
        const scrollTop = elements.folderList.scrollTop;
        const isMobile = window.matchMedia("(max-width: 768px)").matches;
        
        if (isMobile) {
            const header = document.querySelector('.new-conv-container .modal-header');
            if (header) {
                if (scrollTop > lastScrollTop && scrollTop > 50) {
                    // Scrolling down
                    header.classList.add('hide-header');
                } else if (scrollTop < lastScrollTop) {
                    // Scrolling up
                    header.classList.remove('hide-header');
                }
            }
        }
        lastScrollTop = scrollTop;
    });
}

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

    const response = await fetch(`/api${endpoint}`, {
        ...options,
        credentials: 'include',  // Send cookies
        headers: { ...headers, ...options.headers }
    });

    if (response.status === 401) {
        isAuthenticated = false;
        showAuthModal();
        throw new Error('Unauthorized');
    }

    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'API Error');
    }

    return response.json();
}

// Auth Functions
function showAuthModal() {
    showModal(elements.authModal);
}

function hideAuthModal() {
    hideModal(elements.authModal);
}

elements.logoutBtn.onclick = async () => {
    try {
        await fetch('/api/auth/logout', { method: 'POST', credentials: 'include' });
    } catch (err) {
        console.error('Logout error:', err);
    }
    isAuthenticated = false;
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
        <div class="conv-item-wrapper ${currentConversation?.id === c.id ? 'active' : ''}">
            <button onclick="selectConversation('${c.id}')" class="conv-item-btn">
                ${escapeHtml(c.title)}
            </button>
            <button onclick="deleteConversation('${c.id}', event)" class="conv-delete-btn" title="Delete">
                <svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M6 18L18 6M6 6l12 12"/>
                </svg>
            </button>
        </div>
    `).join('');
}

async function deleteConversation(id, event) {
    event.stopPropagation();
    if (!confirm('Delete this conversation?')) return;

    try {
        await api(`/conversations/${id}`, { method: 'DELETE' });

        // If we deleted the current conversation, clear it
        if (currentConversation?.id === id) {
            currentConversation = null;
            elements.inputArea.classList.add('hidden');
            elements.messages.innerHTML = `
                <div class="messages-inner">
                    <p class="empty-state">Select or create a conversation</p>
                </div>
            `;
        }

        await loadConversations();
    } catch (err) {
        console.error('Failed to delete conversation:', err);
    }
}

// Make deleteConversation available globally
window.deleteConversation = deleteConversation;

async function selectConversation(id) {
    currentConversation = conversations.find(c => c.id === id);
    if (!currentConversation) return;

    renderConversations();

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
        hljs.lineNumbersBlock(block);
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

    const actionsHtml = m.actions && m.actions.length > 0 ? `
        <div class="message-actions">
            <div class="message-actions-header">
                <span>Actions</span>
                <span style="font-weight: normal; text-transform: none;">(${m.actions.length})</span>
            </div>
            ${m.actions.map(a => {
                const isFileAction = ['read', 'write', 'edit'].includes(a.type);
                const clickHandler = isFileAction ? `onclick="showFileContent('${escapeHtml(a.detail)}')"` : '';
                const clickableClass = isFileAction ? 'clickable' : '';
                return `
                    <div class="action-item ${a.color} ${clickableClass}" ${clickHandler} title="${escapeHtml(a.detail)}">
                        <span class="action-icon">${a.icon}</span>
                        <span class="action-name">${escapeHtml(a.name)}</span>
                    </div>
                `;
            }).join('')}
        </div>
    ` : '';

    return `
        <div class="message fade-up">
            <div class="message-header">
                <span class="message-role ${m.role}">${m.role === 'user' ? 'You' : 'Robot'}</span>
                ${m.duration ? `<span class="message-time">${(m.duration / 1000).toFixed(1)}s</span>` : ''}
            </div>
            <div class="message-content">${marked.parse(m.content)}</div>
            ${actionsHtml}
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

// Show file content with tabs for content and diff
let currentFileTab = 'content';
let currentFileData = { content: '', diff: '', path: '' };

// Detect language from file extension
function detectLanguage(filePath) {
    const ext = filePath.split('.').pop().toLowerCase();
    const langMap = {
        'js': 'javascript', 'ts': 'typescript', 'jsx': 'javascript', 'tsx': 'typescript',
        'py': 'python', 'rb': 'ruby', 'go': 'go', 'rs': 'rust',
        'java': 'java', 'c': 'c', 'cpp': 'cpp', 'h': 'c', 'hpp': 'cpp',
        'css': 'css', 'scss': 'scss', 'html': 'html', 'xml': 'xml',
        'json': 'json', 'yaml': 'yaml', 'yml': 'yaml', 'md': 'markdown',
        'sh': 'bash', 'bash': 'bash', 'zsh': 'bash',
        'sql': 'sql', 'php': 'php', 'swift': 'swift', 'kt': 'kotlin',
    };
    return langMap[ext] || 'plaintext';
}

async function showFileContent(filePath) {
    try {
        // Fetch both content and diff in parallel
        const [contentResult, diffResult] = await Promise.all([
            api(`/files/content?file_path=${encodeURIComponent(filePath)}`).catch(() => ({ content: '' })),
            api(`/files/diff?file_path=${encodeURIComponent(filePath)}`).catch(() => ({ diff: '' }))
        ]);

        currentFileData = {
            content: contentResult.content || 'File not found or empty',
            diff: diffResult.diff || '',
            path: filePath
        };
        currentFileTab = 'content';

        elements.diffTitle.innerHTML = `
            <div class="file-content-tabs">
                <button class="file-tab active" onclick="switchFileTab('content')">Content</button>
                <button class="file-tab" onclick="switchFileTab('diff')">Diff</button>
            </div>
            <span>${escapeHtml(filePath)}</span>
        `;
        renderFileContent();
        showModal(elements.diffModal);
    } catch (err) {
        console.error('Failed to load file:', err);
    }
}

function renderFileContent() {
    if (currentFileTab === 'content') {
        // Syntax highlight the content
        const lang = detectLanguage(currentFileData.path);
        const highlighted = hljs.highlight(currentFileData.content, { language: lang, ignoreIllegals: true });
        elements.diffContent.innerHTML = `<code class="hljs">${highlighted.value}</code>`;
        
        // Add line numbers
        const codeBlock = elements.diffContent.querySelector('code');
        if (codeBlock) {
             hljs.lineNumbersBlock(codeBlock);
        }
    } else {
        // Render diff with diff2html
        if (currentFileData.diff && currentFileData.diff.trim()) {
            const diffHtml = Diff2Html.html(currentFileData.diff, {
                drawFileList: false,
                matching: 'lines',
                outputFormat: 'line-by-line',
                colorScheme: 'dark'
            });
            elements.diffContent.innerHTML = diffHtml;
        } else {
            elements.diffContent.innerHTML = '<span style="color: var(--text-tertiary)">No changes</span>';
        }
    }
}

function switchFileTab(tab) {
    currentFileTab = tab;
    const tabs = elements.diffTitle.querySelectorAll('.file-tab');
    tabs.forEach(t => t.classList.remove('active'));
    tabs.forEach(t => {
        if (t.textContent.toLowerCase() === tab) {
            t.classList.add('active');
        }
    });
    renderFileContent();
}

// Make functions available globally
window.showFileContent = showFileContent;
window.switchFileTab = switchFileTab;

elements.closeDiffBtn.onclick = () => {
    hideModal(elements.diffModal);
};

// Status indicator element (dynamically added)
let statusIndicator = null;
let actionsContainer = null;
let streamingActions = [];

// Action configuration for real-time display
const ACTION_CONFIGS = {
    'Bash': { icon: '⚡', color: 'action-command', type: 'command' },
    'Read': { icon: '📖', color: 'action-read', type: 'read' },
    'Write': { icon: '✏️', color: 'action-write', type: 'write' },
    'Edit': { icon: '🔧', color: 'action-edit', type: 'edit' },
    'Glob': { icon: '🔍', color: 'action-search', type: 'search' },
    'Grep': { icon: '🔎', color: 'action-search', type: 'search' },
    'Task': { icon: '🤖', color: 'action-agent', type: 'agent' },
    'TodoWrite': { icon: '📋', color: 'action-tool', type: 'tool' },
    'WebFetch': { icon: '🌐', color: 'action-web', type: 'web' },
    'WebSearch': { icon: '🔍', color: 'action-web', type: 'web' },
};

function updateStatusIndicator(message) {
    if (!statusIndicator) return;
    statusIndicator.textContent = message;
}

function getStatusIcon(type) {
    const icons = {
        'init': '🚀',
        'tool_start': '▶',
        'tool_complete': '✓',
        'responding': '💬',
        'complete': '✓',
        'error': '✗'
    };
    return icons[type] || '•';
}

function addStreamingAction(event) {
    if (!actionsContainer || event.type !== 'tool_start' || !event.tool_name) return;

    const config = ACTION_CONFIGS[event.tool_name] || { icon: '🔧', color: 'action-tool', type: 'tool' };
    const name = event.message || event.tool_name;
    const displayName = name.length > 50 ? name.substring(0, 47) + '...' : name;

    const actionHtml = `
        <div class="action-item ${config.color} streaming" title="${escapeHtml(name)}">
            <span class="action-icon">${config.icon}</span>
            <span class="action-name">${escapeHtml(displayName)}</span>
        </div>
    `;

    // Get or create actions list
    let actionsList = actionsContainer.querySelector('.streaming-actions-list');
    if (!actionsList) {
        actionsContainer.innerHTML = `
            <div class="message-actions-header">
                <span>Actions</span>
                <span class="action-count">(0)</span>
            </div>
            <div class="streaming-actions-list"></div>
        `;
        actionsList = actionsContainer.querySelector('.streaming-actions-list');
    }

    actionsList.innerHTML += actionHtml;
    streamingActions.push({ ...event, config });

    // Update count
    const countEl = actionsContainer.querySelector('.action-count');
    if (countEl) countEl.textContent = `(${streamingActions.length})`;

    // Scroll to show latest action
    actionsContainer.scrollTop = actionsContainer.scrollHeight;
}

// Send Message with streaming status updates
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
    elements.inputContainer.classList.add('processing');
    startThinkingTimer();

    currentAbortController = new AbortController();
    streamingActions = [];

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

    // Add status indicator with actions container
    const statusDiv = document.createElement('div');
    statusDiv.className = 'message fade-up status-message';
    statusDiv.innerHTML = `
        <div class="message-header">
            <span class="message-role assistant">Robot</span>
            <span class="status-indicator" id="currentStatus">Starting...</span>
        </div>
        <div class="streaming-actions-container"></div>
    `;
    wrapper.appendChild(statusDiv);
    statusIndicator = statusDiv.querySelector('#currentStatus');
    actionsContainer = statusDiv.querySelector('.streaming-actions-container');
    elements.messages.scrollTop = elements.messages.scrollHeight;

    try {
        // Use streaming endpoint with fetch for EventSource-like behavior
        const response = await fetch(`/api/conversations/${currentConversation.id}/messages/stream`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            credentials: 'include',
            body: JSON.stringify({ content }),
            signal: currentAbortController.signal
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'API Error');
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let finalMessage = null;

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });

            // Process SSE events from buffer
            const lines = buffer.split('\n');
            buffer = lines.pop(); // Keep incomplete line in buffer

            for (const line of lines) {
                if (line.startsWith('event: ')) {
                    // Parse event type
                    continue;
                }
                if (line.startsWith('data: ')) {
                    const data = line.slice(6);
                    try {
                        const event = JSON.parse(data);

                        if (event.type) {
                            // Status event
                            const icon = getStatusIcon(event.type);
                            updateStatusIndicator(`${icon} ${event.message}`);

                            // Add action to streaming display
                            addStreamingAction(event);
                        } else if (event.id && event.role === 'assistant') {
                            // Final message event
                            finalMessage = event;
                        } else if (event.error) {
                            throw new Error(event.error);
                        }
                    } catch (e) {
                        // Ignore parse errors for partial data
                        if (e.message !== 'Unexpected end of JSON input') {
                            console.warn('SSE parse error:', e);
                        }
                    }
                }
            }

            // Keep scrolling to bottom as actions come in
            elements.messages.scrollTop = elements.messages.scrollHeight;
        }

        // Remove status indicator and add final message
        if (statusDiv.parentNode) {
            statusDiv.remove();
        }

        if (finalMessage) {
            wrapper.innerHTML += renderMessage(finalMessage);

            // Highlight code blocks
            elements.messages.querySelectorAll('pre code').forEach(block => {
                hljs.highlightElement(block);
            });
        }

        elements.messages.scrollTop = elements.messages.scrollHeight;

        // Refresh modified files and conversations
        await loadModifiedFiles();
        await loadConversations();

    } catch (err) {
        // Remove status indicator
        if (statusDiv.parentNode) {
            statusDiv.remove();
        }

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
        statusIndicator = null;
        actionsContainer = null;
        streamingActions = [];
        currentAbortController = null;
        elements.messageInput.disabled = false;
        elements.sendBtn.disabled = false;
        elements.statusBar.classList.add('hidden');
        elements.inputContainer.classList.remove('processing');
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
        const isMobile = window.matchMedia("(max-width: 768px)").matches;
        if (!isMobile) {
            e.preventDefault();
            sendMessage();
        }
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
        hideModal(elements.browserModal);
    }
});

// Browser Functions
function formatFileSize(bytes) {
    if (bytes === null || bytes === undefined) return '';
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

function getFileIcon(item) {
    if (item.is_dir) {
        return `<svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z"/>
        </svg>`;
    }
    // File icon
    return `<svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
    </svg>`;
}

function renderBreadcrumb(path) {
    if (!path) {
        elements.browserBreadcrumb.innerHTML = '<span class="breadcrumb-item">~/Code</span>';
        return;
    }

    const homePath = path.replace(/^\/home\/[^/]+/, '~');
    const parts = homePath.split('/').filter(Boolean);
    let currentPath = '';

    const breadcrumbHtml = parts.map((part, index) => {
        if (part === '~') {
            currentPath = path.split('/').slice(0, 3).join('/'); // /home/user
        } else {
            currentPath += '/' + part;
        }
        const isLast = index === parts.length - 1;
        const displayPath = currentPath;

        if (isLast) {
            return `<span class="breadcrumb-item current">${escapeHtml(part)}</span>`;
        }
        return `<span class="breadcrumb-item clickable" onclick="browserNavigateTo('${escapeHtml(displayPath)}')">${escapeHtml(part)}</span>
                <span class="breadcrumb-sep">/</span>`;
    }).join('');

    elements.browserBreadcrumb.innerHTML = breadcrumbHtml;
}

async function loadBrowserPath(path = null) {
    try {
        const url = path ? `/api/browser?path=${encodeURIComponent(path)}` : '/api/browser';
        const response = await fetch(url, {
            credentials: 'include'
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to load directory');
        }

        const items = await response.json();

        // Update state
        if (browserCurrentPath !== null && browserCurrentPath !== path) {
            browserHistory.push(browserCurrentPath);
        }
        browserCurrentPath = path;
        browserViewingFile = false;

        // Update UI
        elements.browserFile.classList.add('hidden');
        elements.browserList.classList.remove('hidden');
        renderBreadcrumb(path);
        elements.browserBackBtn.disabled = browserHistory.length === 0;

        if (items.length === 0) {
            elements.browserList.innerHTML = '<div class="browser-empty">Empty directory</div>';
            return;
        }

        elements.browserList.innerHTML = items.map(item => `
            <div class="browser-item ${item.is_dir ? 'dir' : 'file'}" onclick="${item.is_dir ? `browserNavigateTo('${escapeHtml(item.path)}')` : `browserOpenFile('${escapeHtml(item.path)}')`}">
                <span class="browser-item-icon">${getFileIcon(item)}</span>
                <span class="browser-item-name">${escapeHtml(item.name)}</span>
                ${!item.is_dir && item.size !== null ? `<span class="browser-item-size">${formatFileSize(item.size)}</span>` : ''}
            </div>
        `).join('');

    } catch (err) {
        console.error('Failed to load browser path:', err);
        elements.browserList.innerHTML = `<div class="browser-error">${escapeHtml(err.message)}</div>`;
    }
}

async function browserOpenFile(filePath) {
    try {
        const response = await fetch(`/api/browser/file?file_path=${encodeURIComponent(filePath)}`, {
            credentials: 'include'
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to load file');
        }

        const file = await response.json();

        // Update state
        if (!browserViewingFile) {
            browserHistory.push(browserCurrentPath);
        }
        browserViewingFile = true;

        // Update UI
        elements.browserList.classList.add('hidden');
        elements.browserFile.classList.remove('hidden');
        elements.browserFileName.textContent = file.name;
        elements.browserFileSize.textContent = formatFileSize(file.size);

        // Render breadcrumb for file
        renderBreadcrumb(filePath);
        elements.browserBackBtn.disabled = browserHistory.length === 0;

        // Highlight code
        const codeEl = elements.browserFileContent.querySelector('code');
        codeEl.className = `language-${file.language}`;
        codeEl.textContent = file.content;
        hljs.highlightElement(codeEl);

    } catch (err) {
        console.error('Failed to open file:', err);
        alert(err.message);
    }
}

function browserNavigateTo(path) {
    loadBrowserPath(path);
}

// Make browserNavigateTo available globally
window.browserNavigateTo = browserNavigateTo;

function browserGoBack() {
    if (browserHistory.length === 0) return;

    const previousPath = browserHistory.pop();
    browserCurrentPath = previousPath;

    if (browserViewingFile) {
        // Going back from file to directory
        browserViewingFile = false;
        loadBrowserPath(previousPath);
        // Remove the path we just navigated to from history (loadBrowserPath will add it back)
        browserHistory.pop();
    } else {
        // Going back from directory to directory
        loadBrowserPath(previousPath);
        // Remove the path we just navigated to from history
        browserHistory.pop();
    }
}

function openBrowser() {
    browserHistory = [];
    browserCurrentPath = null;
    browserViewingFile = false;
    showModal(elements.browserModal);
    loadBrowserPath(null);
}

// Browser event listeners
elements.browseBtn.onclick = openBrowser;
elements.closeBrowserBtn.onclick = () => hideModal(elements.browserModal);
elements.browserBackBtn.onclick = browserGoBack;

// Make browserOpenFile available globally
window.browserOpenFile = browserOpenFile;

// Initialize
async function init() {
    try {
        const response = await fetch('/api/auth/status', { credentials: 'include' });
        const status = await response.json();

        if (status.authenticated) {
            isAuthenticated = true;
            hideAuthModal();
            await loadConversations();
        } else {
            showAuthModal();
        }
    } catch (err) {
        console.error('Auth check failed:', err);
        showAuthModal();
    }
}

init();
