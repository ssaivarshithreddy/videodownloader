document.addEventListener('DOMContentLoaded', () => {
    const urlInput = document.getElementById('urlInput');
    const pasteBtn = document.getElementById('pasteBtn');
    const fetchBtn = document.getElementById('fetchBtn');
    const errorAlert = document.getElementById('errorAlert');
    const errorMessage = document.getElementById('errorMessage');
    const loader = document.getElementById('loader');
    const previewCard = document.getElementById('previewCard');

    const videoThumb = document.getElementById('videoThumb');
    const videoDuration = document.getElementById('videoDuration');
    const platformTag = document.getElementById('platformTag');
    const videoTitle = document.getElementById('videoTitle');
    const videoUploader = document.getElementById('videoUploader');

    const tabVideo = document.getElementById('tabVideo');
    const tabAudio = document.getElementById('tabAudio');
    const formatSelect = document.getElementById('formatSelect');
    const downloadBtn = document.getElementById('downloadBtn');

    const progressCard = document.getElementById('progressCard');
    const progressStatusText = document.getElementById('progressStatusText');
    const progressPercent = document.getElementById('progressPercent');
    const progressBarFill = document.getElementById('progressBarFill');
    const progressSpeed = document.getElementById('progressSpeed');
    const progressEta = document.getElementById('progressEta');
    const completedActions = document.getElementById('completedActions');
    const saveFileBtn = document.getElementById('saveFileBtn');

    const historyList = document.getElementById('historyList');
    const clearHistoryBtn = document.getElementById('clearHistoryBtn');

    let currentVideoData = null;
    let activeTab = 'video';
    let pollInterval = null;
    let sessionHistory = [];

    // Paste button logic
    pasteBtn.addEventListener('click', async () => {
        try {
            const text = await navigator.clipboard.readText();
            if (text) {
                urlInput.value = text.trim();
            }
        } catch (err) {
            console.warn('Clipboard read error:', err);
        }
    });

    // Fetch button logic
    fetchBtn.addEventListener('click', () => {
        const url = urlInput.value.trim();
        if (!url) {
            showError('Please enter or paste a valid video URL.');
            return;
        }
        fetchVideoInfo(url);
    });

    // Enter key support on urlInput
    urlInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            fetchBtn.click();
        }
    });

    // Tab switching
    tabVideo.addEventListener('click', () => {
        if (activeTab === 'video') return;
        activeTab = 'video';
        tabVideo.classList.add('active');
        tabAudio.classList.remove('active');
        populateFormats();
    });

    tabAudio.addEventListener('click', () => {
        if (activeTab === 'audio') return;
        activeTab = 'audio';
        tabAudio.classList.add('active');
        tabVideo.classList.remove('active');
        populateFormats();
    });

    // Fetch video info endpoint call
    async function fetchVideoInfo(url) {
        hideError();
        previewCard.classList.add('hidden');
        progressCard.classList.add('hidden');
        loader.classList.remove('hidden');

        try {
            const res = await fetch('/api/info', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url: url })
            });

            const data = await res.json();
            if (!res.ok) {
                throw new Error(data.detail || 'Failed to extract video details.');
            }

            currentVideoData = data;
            renderPreview(data);
        } catch (err) {
            showError(err.message);
        } finally {
            loader.classList.add('hidden');
        }
    }

    // Render Preview
    function renderPreview(data) {
        videoThumb.src = data.thumbnail || 'https://via.placeholder.com/480x270?text=No+Thumbnail';
        videoDuration.textContent = data.duration || 'N/A';
        platformTag.textContent = data.platform || 'Media';
        videoTitle.textContent = data.title;
        videoUploader.innerHTML = `<i class="fa-solid fa-user"></i> ${data.uploader || 'Unknown Channel'}`;

        activeTab = 'video';
        tabVideo.classList.add('active');
        tabAudio.classList.remove('active');

        populateFormats();
        previewCard.classList.remove('hidden');
    }

    // Populate format dropdown
    function populateFormats() {
        if (!currentVideoData) return;
        formatSelect.innerHTML = '';

        const formats = activeTab === 'video' ? currentVideoData.video_formats : currentVideoData.audio_formats;
        formats.forEach(f => {
            const opt = document.createElement('option');
            opt.value = f.format_id;
            opt.textContent = `${f.label} (${f.quality})`;
            formatSelect.appendChild(opt);
        });
    }

    // Start Download
    downloadBtn.addEventListener('click', async () => {
        if (!currentVideoData) return;
        const selectedFormat = formatSelect.value;
        const formatType = activeTab;

        hideError();
        progressCard.classList.remove('hidden');
        completedActions.classList.add('hidden');

        resetProgressUI();

        try {
            const res = await fetch('/api/download', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    url: currentVideoData.url,
                    format_id: selectedFormat,
                    format_type: formatType
                })
            });

            const data = await res.json();
            if (!res.ok) {
                throw new Error(data.detail || 'Failed to initiate download task.');
            }

            startPollingProgress(data.task_id);
        } catch (err) {
            showError(err.message);
            progressCard.classList.add('hidden');
        }
    });

    // Reset Progress UI
    function resetProgressUI() {
        progressStatusText.textContent = 'Initializing download...';
        progressPercent.textContent = '0%';
        progressBarFill.style.width = '0%';
        progressSpeed.textContent = '0 KB/s';
        progressEta.textContent = '--:--';
    }

    // Poll Progress Endpoint
    function startPollingProgress(taskId) {
        if (pollInterval) clearInterval(pollInterval);

        pollInterval = setInterval(async () => {
            try {
                const res = await fetch(`/api/progress/${taskId}`);
                if (!res.ok) return;

                const data = await res.json();

                if (data.status === 'downloading') {
                    progressStatusText.textContent = 'Downloading media...';
                    const pct = data.percentage || 0;
                    progressPercent.textContent = `${pct}%`;
                    progressBarFill.style.width = `${pct}%`;
                    progressSpeed.textContent = data.speed || '0 KB/s';
                    progressEta.textContent = data.eta || '--:--';
                } else if (data.status === 'processing') {
                    progressStatusText.textContent = 'Merging video & audio...';
                    progressPercent.textContent = '99%';
                    progressBarFill.style.width = '99%';
                } else if (data.status === 'completed') {
                    clearInterval(pollInterval);
                    progressStatusText.textContent = 'Download Ready!';
                    progressPercent.textContent = '100%';
                    progressBarFill.style.width = '100%';
                    progressSpeed.textContent = 'Done';
                    progressEta.textContent = '0s';

                    saveFileBtn.href = `/api/file/${encodeURIComponent(data.filename)}`;
                    completedActions.classList.remove('hidden');

                    addToHistory(data.filename, `/api/file/${encodeURIComponent(data.filename)}`);
                } else if (data.status === 'failed') {
                    clearInterval(pollInterval);
                    showError(`Download failed: ${data.error || 'Unknown error'}`);
                    progressCard.classList.add('hidden');
                }
            } catch (err) {
                console.warn('Progress poll error:', err);
            }
        }, 800);
    }

    // History tracking
    function addToHistory(filename, downloadUrl) {
        sessionHistory.unshift({ filename, downloadUrl, title: currentVideoData?.title || filename });
        renderHistory();
    }

    function renderHistory() {
        if (sessionHistory.length === 0) {
            historyList.innerHTML = '<p class="empty-history">No downloads yet in this session.</p>';
            return;
        }

        historyList.innerHTML = '';
        sessionHistory.forEach(item => {
            const div = document.createElement('div');
            div.className = 'history-item';
            div.innerHTML = `
                <span class="history-item-title">${escapeHtml(item.title)}</span>
                <a href="${item.downloadUrl}" download class="history-item-link">
                    <i class="fa-solid fa-download"></i> Save
                </a>
            `;
            historyList.appendChild(div);
        });
    }

    clearHistoryBtn.addEventListener('click', () => {
        sessionHistory = [];
        renderHistory();
    });

    // Helper functions
    function showError(msg) {
        errorMessage.textContent = msg;
        errorAlert.classList.remove('hidden');
    }

    function hideError() {
        errorAlert.classList.add('hidden');
    }

    function escapeHtml(str) {
        return str.replace(/[&<>"']/g, m => ({
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#039;'
        })[m]);
    }
});
