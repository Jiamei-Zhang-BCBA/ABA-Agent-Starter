const API = '/api/v1';

function app() {
    return {
        // Auth
        token: localStorage.getItem('aba_token') || '',
        user: null,
        loginForm: { email: '', password: '' },
        loginError: '',
        loginLoading: false,

        // Navigation
        currentTab: 'features',
        categoryFilter: 'all',

        // Features
        features: [],
        categories: [],

        // Form modal
        showFormModal: false,
        activeFeature: null,
        formFields: [],
        formData: {},
        formFiles: {},
        submitLoading: false,
        submitError: '',

        // Jobs
        jobs: [],

        // Reviews
        reviews: [],

        // Output modal
        showOutputModal: false,
        viewingJob: null,
        editMode: false,
        editContent: '',
        saveLoading: false,

        // Clients & Timeline
        clients: [],
        selectedClient: null,
        clientTimeline: null,

        // Toast
        showToast: false,
        toastMsg: '',

        // Computed
        get roleLabel() {
            if (!this.user) return '';
            const map = { org_admin: '管理员', bcba: 'BCBA', teacher: '老师', parent: '家长' };
            return map[this.user.role] || this.user.role;
        },
        get filteredFeatures() {
            if (this.categoryFilter === 'all') return this.features;
            return this.features.filter(f => f.category === this.categoryFilter);
        },
        get isAdmin() {
            return this.user && (this.user.role === 'org_admin' || this.user.role === 'bcba');
        },

        // Init
        async init() {
            if (this.token) {
                try {
                    await this.loadUser();
                    await this.loadFeatures();
                } catch (e) {
                    this.token = '';
                    localStorage.removeItem('aba_token');
                }
            }
        },

        // Auth
        async login() {
            this.loginError = '';
            this.loginLoading = true;
            try {
                const res = await fetch(`${API}/auth/login`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(this.loginForm),
                });
                if (!res.ok) {
                    const err = await res.json();
                    throw new Error(err.detail || '登录失败');
                }
                const data = await res.json();
                this.token = data.access_token;
                localStorage.setItem('aba_token', this.token);
                await this.loadUser();
                await this.loadFeatures();
            } catch (e) {
                this.loginError = e.message;
            } finally {
                this.loginLoading = false;
            }
        },

        logout() {
            this.token = '';
            this.user = null;
            this.features = [];
            this.jobs = [];
            this.clients = [];
            localStorage.removeItem('aba_token');
        },

        // API helpers
        authHeaders() {
            return { 'Authorization': `Bearer ${this.token}` };
        },

        async apiFetch(path, options = {}) {
            const res = await fetch(`${API}${path}`, {
                ...options,
                headers: { ...this.authHeaders(), ...(options.headers || {}) },
            });
            if (res.status === 401) {
                this.logout();
                throw new Error('登录已过期');
            }
            return res;
        },

        // Load data
        async loadUser() {
            const res = await this.apiFetch('/auth/me');
            this.user = await res.json();
        },

        async loadFeatures() {
            const res = await this.apiFetch('/features');
            const data = await res.json();
            this.features = data.features;
            this.categories = [...new Set(this.features.map(f => f.category))];
        },

        async loadJobs() {
            const res = await this.apiFetch('/jobs');
            const data = await res.json();
            this.jobs = data.jobs;
        },

        async loadReviews() {
            const res = await this.apiFetch('/reviews');
            const data = await res.json();
            this.reviews = data.reviews;
        },

        async loadClients() {
            const res = await this.apiFetch('/clients');
            const data = await res.json();
            this.clients = data.clients;
        },

        // === Client Timeline ===
        async openClientTimeline(client) {
            this.selectedClient = client;
            try {
                const res = await this.apiFetch(`/clients/${client.id}/timeline`);
                this.clientTimeline = await res.json();
            } catch (e) {
                console.error(e);
                this.clientTimeline = { timeline: [], vault_files: {}, total_jobs: 0, completed_jobs: 0 };
            }
        },

        closeClientTimeline() {
            this.selectedClient = null;
            this.clientTimeline = null;
        },

        // === Feature form ===
        async openFeature(feature) {
            this.activeFeature = feature;
            this.formData = {};
            this.formFiles = {};
            this.submitError = '';
            try {
                const res = await this.apiFetch(`/features/${feature.id}/schema`);
                const schema = await res.json();
                this.formFields = schema.form_schema.fields;
            } catch (e) {
                this.formFields = feature.form_schema.fields;
            }
            this.showFormModal = true;
        },

        handleFile(event, fieldName) {
            const files = event.target.files;
            if (files.length > 0) {
                this.formFiles[fieldName] = files[0];
            }
        },

        async submitJob() {
            this.submitLoading = true;
            this.submitError = '';
            try {
                const fd = new FormData();
                fd.append('feature_id', this.activeFeature.id);

                const clientField = this.formFields.find(f => f.type === 'select_client');
                if (clientField && this.formData[clientField.name]) {
                    fd.append('client_id', this.formData[clientField.name]);
                }

                const textData = {};
                for (const field of this.formFields) {
                    if (field.type !== 'file' && field.type !== 'select_client' && field.type !== 'select_staff') {
                        if (this.formData[field.name]) {
                            textData[field.name] = this.formData[field.name];
                        }
                    }
                    if (field.type === 'select_staff' && this.formData[field.name]) {
                        textData['staff_id'] = this.formData[field.name];
                    }
                }
                fd.append('form_data', JSON.stringify(textData));

                for (const [key, file] of Object.entries(this.formFiles)) {
                    fd.append('files', file);
                }

                const res = await fetch(`${API}/jobs`, {
                    method: 'POST',
                    headers: this.authHeaders(),
                    body: fd,
                });

                if (!res.ok) {
                    const err = await res.json();
                    throw new Error(err.detail || '提交失败');
                }

                this.showFormModal = false;
                this.toast('任务提交成功，正在后台处理');
                this.currentTab = 'jobs';
                await this.loadJobs();
            } catch (e) {
                this.submitError = e.message;
            } finally {
                this.submitLoading = false;
            }
        },

        // === View / Edit / Download output ===
        async viewJobOutput(job) {
            try {
                const res = await this.apiFetch(`/jobs/${job.id}`);
                this.viewingJob = await res.json();
                this.editMode = false;
                this.editContent = '';
                this.showOutputModal = true;
            } catch (e) {
                console.error(e);
            }
        },

        enterEditMode() {
            this.editContent = this.viewingJob.output_content || '';
            this.editMode = true;
        },

        cancelEdit() {
            this.editMode = false;
            this.editContent = '';
        },

        async saveEdit() {
            this.saveLoading = true;
            try {
                const res = await this.apiFetch(`/jobs/${this.viewingJob.id}/output`, {
                    method: 'PATCH',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ output_content: this.editContent }),
                });
                if (!res.ok) {
                    const err = await res.json();
                    throw new Error(err.detail || '保存失败');
                }
                this.viewingJob.output_content = this.editContent;
                this.editMode = false;
                this.toast('修改已保存');
            } catch (e) {
                this.toast('保存失败: ' + e.message);
            } finally {
                this.saveLoading = false;
            }
        },

        downloadMarkdown(content, filename) {
            if (!content) return;
            const blob = new Blob([content], { type: 'text/markdown;charset=utf-8' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filename || 'output.md';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        },

        downloadCurrentOutput() {
            if (!this.viewingJob) return;
            const name = this.featureName(this.viewingJob.feature_id);
            const date = this.viewingJob.created_at ? this.viewingJob.created_at.slice(0, 10) : 'output';
            const content = this.editMode ? this.editContent : this.viewingJob.output_content;
            this.downloadMarkdown(content, `${name}-${date}.md`);
        },

        // Download from timeline
        downloadTimelineEntry(entry) {
            if (!entry.output_content) return;
            const name = this.featureName(entry.feature_id);
            const date = entry.created_at ? entry.created_at.slice(0, 10) : 'output';
            this.downloadMarkdown(entry.output_content, `${name}-${date}.md`);
        },

        // === Reviews ===
        async approveReview(reviewId) {
            try {
                await this.apiFetch(`/reviews/${reviewId}/approve`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({}),
                });
                this.toast('已批准');
                await this.loadReviews();
            } catch (e) {
                console.error(e);
            }
        },

        async rejectReview(reviewId) {
            const reason = prompt('请输入驳回原因:');
            if (!reason) return;
            try {
                await this.apiFetch(`/reviews/${reviewId}/reject`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ comments: reason }),
                });
                this.toast('已驳回');
                await this.loadReviews();
            } catch (e) {
                console.error(e);
            }
        },

        // === Helpers ===
        featureName(featureId) {
            const f = this.features.find(x => x.id === featureId);
            return f ? f.display_name : featureId;
        },

        statusLabel(status) {
            const map = {
                queued: '排队中', parsing: '解析文件', processing: 'AI处理中',
                pending_review: '待审核', delivered: '已完成', approved: '已批准',
                failed: '失败', rejected: '已驳回',
            };
            return map[status] || status;
        },

        formatTime(ts) {
            if (!ts) return '';
            const d = new Date(ts);
            return `${d.getMonth()+1}/${d.getDate()} ${d.getHours()}:${String(d.getMinutes()).padStart(2,'0')}`;
        },

        formatDate(ts) {
            if (!ts) return '';
            return ts.slice(0, 10);
        },

        iconBg(category) {
            const map = {
                '数据安全': 'bg-green-100 text-green-600',
                '建档与评估': 'bg-blue-100 text-blue-600',
                '日常教学': 'bg-amber-100 text-amber-600',
                '家校沟通': 'bg-pink-100 text-pink-600',
                '方案制定': 'bg-purple-100 text-purple-600',
                '师资管理': 'bg-cyan-100 text-cyan-600',
                '督导管理': 'bg-indigo-100 text-indigo-600',
            };
            return map[category] || 'bg-gray-100 text-gray-600';
        },

        iconEmoji(icon) {
            const map = {
                'shield-check': '🛡️', 'user-plus': '👶', 'clipboard-check': '📋',
                'book-open': '📖', 'mail-heart': '💌', 'eye': '👁️',
                'zap': '⚡', 'file-text': '📄', 'bar-chart': '📊',
                'search': '🔍', 'target': '🎯', 'scissors': '✂️',
                'star': '⭐', 'trophy': '🏆', 'brain': '🧠',
                'user-check': '✅', 'arrow-right-circle': '➡️',
            };
            return map[icon] || '📋';
        },

        featureIcon(featureId) {
            const f = this.features.find(x => x.id === featureId);
            return f ? this.iconEmoji(f.icon) : '📋';
        },

        renderMarkdown(md) {
            if (!md) return '';
            let html = md
                .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
                .replace(/^### (.*$)/gm, '<h3>$1</h3>')
                .replace(/^## (.*$)/gm, '<h2>$1</h2>')
                .replace(/^# (.*$)/gm, '<h1>$1</h1>')
                .replace(/\*\*\*(.*?)\*\*\*/g, '<strong><em>$1</em></strong>')
                .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
                .replace(/\*(.*?)\*/g, '<em>$1</em>')
                .replace(/`(.*?)`/g, '<code>$1</code>')
                .replace(/^---$/gm, '<hr>')
                .replace(/^&gt; (.*$)/gm, '<blockquote>$1</blockquote>')
                .replace(/^\|(.+)\|$/gm, (match) => {
                    const cells = match.split('|').filter(c => c.trim());
                    if (cells.every(c => /^[\s:-]+$/.test(c))) return '';
                    return '<tr>' + cells.map(c => `<td>${c.trim()}</td>`).join('') + '</tr>';
                })
                .replace(/^\* (.*$)/gm, '<li>$1</li>')
                .replace(/^- (.*$)/gm, '<li>$1</li>')
                .replace(/^\d+\. (.*$)/gm, '<li>$1</li>')
                .replace(/\n\n/g, '</p><p>')
                .replace(/\n/g, '<br>');
            html = html.replace(/(<li>.*?<\/li>)+/gs, '<ul>$&</ul>');
            html = html.replace(/(<tr>.*?<\/tr>)+/gs, '<table>$&</table>');
            return `<div class="markdown-body"><p>${html}</p></div>`;
        },

        toast(msg) {
            this.toastMsg = msg;
            this.showToast = true;
            setTimeout(() => { this.showToast = false; }, 3000);
        },
    };
}
