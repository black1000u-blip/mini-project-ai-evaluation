/* ================================================================
   Teacher Module — Dashboard, Assignment Management, Reports
   ================================================================ */

// ---- Skeleton Loaders ----

function showTeacherStatSkeletons() {
    ['stat-assignments', 'stat-submissions', 'stat-evaluated', 'stat-avg'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.innerHTML = '<div class="skeleton skeleton-stat"></div>';
    });
}

function showTeacherTableSkeleton(tbody, cols = 6, rows = 5) {
    if (!tbody) return;
    let html = '';
    for (let i = 0; i < rows; i++) {
        html += '<tr>';
        for (let j = 0; j < cols; j++) {
            const width = j === 0 ? 'medium' : (j === cols - 1 ? 'short' : 'medium');
            html += `<td><div class="skeleton skeleton-text ${width}"></div></td>`;
        }
        html += '</tr>';
    }
    tbody.innerHTML = html;
}

function showReportsSkeletons(container) {
    if (!container) return;
    let html = '';
    for (let i = 0; i < 2; i++) {
        html += `
        <div class="content-card">
            <div class="skeleton-row">
                <div class="skeleton skeleton-text long" style="flex: 1"></div>
            </div>
            <div class="row g-3 mt-2">
                <div class="col-md-2"><div class="skeleton skeleton-stat"></div></div>
                <div class="col-md-2"><div class="skeleton skeleton-stat"></div></div>
                <div class="col-md-2"><div class="skeleton skeleton-stat"></div></div>
                <div class="col-md-3"><div class="skeleton skeleton-stat"></div></div>
                <div class="col-md-3"><div class="skeleton skeleton-stat"></div></div>
            </div>
        </div>`;
    }
    container.innerHTML = html;
}

// ---- Animate Value ----

function animateTeacherValue(elementId, endValue, duration = 500) {
    const el = document.getElementById(elementId);
    if (!el) return;
    
    const isNumber = !isNaN(parseFloat(endValue.toString().replace('%', '')));
    if (!isNumber) {
        el.textContent = endValue;
        return;
    }
    
    const hasPercent = endValue.toString().includes('%');
    const numValue = parseFloat(endValue.toString().replace('%', ''));
    const startTime = performance.now();
    
    function update(currentTime) {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);
        const easeOut = 1 - Math.pow(1 - progress, 3);
        const current = numValue * easeOut;
        el.textContent = (hasPercent ? current.toFixed(1) + '%' : Math.round(current));
        if (progress < 1) requestAnimationFrame(update);
    }
    requestAnimationFrame(update);
}

// ---- Dashboard ----

let _teacherRefreshTimer = null;
let _teacherFirstLoad = true;

async function loadTeacherDashboard() {
    // Show skeletons on first load
    if (_teacherFirstLoad) {
        showTeacherStatSkeletons();
        showTeacherTableSkeleton(document.getElementById('submissions-body'), 6, 5);
        _teacherFirstLoad = false;
    }
    
    try {
        const [subData, reportData] = await Promise.all([
            apiRequest('/teacher/submissions'),
            apiRequest('/teacher/reports'),
        ]);

        const submissions = subData.submissions || [];
        const reports = reportData.reports || [];

        // Stats with animation
        animateTeacherValue('stat-assignments', reports.length);
        animateTeacherValue('stat-submissions', submissions.length);

        const evaluated = submissions.filter(s => s.status === 'evaluated');
        animateTeacherValue('stat-evaluated', evaluated.length);

        if (evaluated.length > 0) {
            const avg = evaluated.reduce((sum, s) => sum + s.similarity_score, 0) / evaluated.length;
            animateTeacherValue('stat-avg', (avg * 100).toFixed(1) + '%');
        } else {
            document.getElementById('stat-avg').textContent = 'N/A';
        }

        // Auto-refresh if any submissions are still processing
        const hasPending = submissions.some(s => s.status === 'processing' || s.status === 'pending');
        if (hasPending) {
            clearTimeout(_teacherRefreshTimer); // Clear existing to avoid duplicates
            _teacherRefreshTimer = setTimeout(() => loadTeacherDashboard(), 3000);
        } else if (!hasPending && _teacherRefreshTimer) {
            clearTimeout(_teacherRefreshTimer);
            _teacherRefreshTimer = null;
        }

        // Submissions table
        const tbody = document.getElementById('submissions-body');
        if (submissions.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="6">
                        <div class="empty-state">
                            <div class="empty-state-icon">📚</div>
                            <div class="empty-state-title">No submissions yet</div>
                            <div class="empty-state-text">Student submissions will appear here once they start submitting.</div>
                        </div>
                    </td>
                </tr>`;
            return;
        }

        tbody.innerHTML = submissions.slice(0, 20).map((s, idx) => {
            const isProcessing = s.status === 'processing';
            return `
            <tr style="animation: cardSlideUp 0.3s ease-out ${idx * 0.05}s both">
                <td>${escapeHtml(s.student_name)}</td>
                <td>${escapeHtml(s.assignment_title)}</td>
                <td>
                    <span class="badge-status badge-${s.status}">${s.status.toUpperCase()}</span>
                    ${isProcessing ? `
                    <div class="eval-progress mt-1">
                        <div class="progress" style="height:14px">
                            <div class="progress-bar" style="width:${s.progress || 0}%;font-size:0.65rem">${s.progress || 0}%</div>
                        </div>
                        <div class="progress-step" style="font-size:0.7rem">${escapeHtml(s.progress_step) || ''}</div>
                    </div>` : ''}
                    ${s.status === 'error' && s.error_message ? `
                    <div class="progress-step text-danger mt-1" style="font-size:0.7rem">${escapeHtml(s.error_message)}</div>
                    ` : ''}
                </td>
                <td>${s.status === 'evaluated' ? (s.similarity_score * 100).toFixed(1) + '%' : '-'}</td>
                <td>${s.status === 'evaluated' ? s.marks_obtained + '/' + s.total_marks : '-'}</td>
                <td>${formatDate(s.submitted_at)}</td>
            </tr>`;
        }).join('');

    } catch (err) {
        console.error('Teacher dashboard error:', err);
        showToast('Failed to load dashboard data', 'error');
    }
}

// ---- Assignment Form ----

function setupAssignmentForm() {
    const form = document.getElementById('assignment-form');
    if (!form) return;

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const btn = document.getElementById('create-btn');
        btn.disabled = true;
        btn.textContent = 'Creating...';

        try {
            const data = await apiRequest('/teacher/assignment', {
                method: 'POST',
                body: JSON.stringify({
                    title: document.getElementById('title').value,
                    subject: document.getElementById('subject').value,
                    total_marks: parseInt(document.getElementById('total-marks').value) || 100,
                    model_answer: document.getElementById('model-answer').value
                }),
            });

            showAlert(data.message || 'Assignment created successfully!', 'success');
            form.reset();
            document.getElementById('total-marks').value = '100'; // Reset to default
            loadMyAssignments();

        } catch (err) {
            showAlert(err.message);
        } finally {
            btn.disabled = false;
            btn.textContent = 'Create Assignment';
        }
    });
}

// ---- My Assignments (sidebar) ----

async function loadMyAssignments() {
    const container = document.getElementById('my-assignments');
    if (!container) return;

    try {
        const data = await apiRequest('/teacher/assignments');
        const assignments = data.assignments || [];

        if (assignments.length === 0) {
            container.innerHTML = '<p class="text-muted small">No assignments created yet.</p>';
            return;
        }

        container.innerHTML = assignments.map(a => `
            <div class="border-bottom pb-2 mb-2">
                <div class="fw-bold small">${escapeHtml(a.title)}</div>
                <div class="text-muted" style="font-size: 0.75rem">${escapeHtml(a.subject)} | ${a.total_marks} marks</div>
            </div>
        `).join('');

    } catch (err) {
        container.innerHTML = '<p class="text-danger small">Failed to load.</p>';
    }
}

// ---- Reports ----

let _reportsFirstLoad = true;
let _reportSubmissions = {}; // Cache for loaded submissions

async function loadReports() {
    const container = document.getElementById('reports-container');
    if (!container) return;
    
    // Show skeleton on first load
    if (_reportsFirstLoad) {
        showReportsSkeletons(container);
        _reportsFirstLoad = false;
    }

    try {
        const data = await apiRequest('/teacher/reports');
        const reports = data.reports || [];

        if (reports.length === 0) {
            container.innerHTML = `
                <div class="content-card">
                    <div class="empty-state">
                        <div class="empty-state-icon">📊</div>
                        <div class="empty-state-title">No assignments yet</div>
                        <div class="empty-state-text">Create your first assignment to start receiving submissions.</div>
                        <a href="/teacher/upload_model.html" class="btn btn-primary">Create Assignment</a>
                    </div>
                </div>`;
            return;
        }

        container.innerHTML = reports.map(r => `
            <div class="report-card" id="report-${r.assignment_id}">
                <div class="report-card-header" onclick="toggleReportCard('${r.assignment_id}')">
                    <div class="report-card-title">
                        <h5>${escapeHtml(r.title)}</h5>
                        <span class="subject-badge">${escapeHtml(r.subject)}</span>
                    </div>
                    <div class="report-card-actions">
                        <button class="download-btn" onclick="event.stopPropagation(); downloadReportExcel('${r.assignment_id}', '${escapeAttr(r.title)}')" title="Download Excel">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                                <polyline points="7 10 12 15 17 10"></polyline>
                                <line x1="12" y1="15" x2="12" y2="3"></line>
                            </svg>
                            Download Excel
                        </button>
                        <button class="expand-btn" title="View Details">
                            <svg class="arrow" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <polyline points="6 9 12 15 18 9"></polyline>
                            </svg>
                        </button>
                    </div>
                </div>
                <div class="report-card-stats">
                    <div class="stat-card text-center p-2" style="flex:1">
                        <div class="fw-bold fs-4">${r.total_submissions}</div>
                        <div class="small text-muted">Submissions</div>
                    </div>
                    <div class="stat-card success text-center p-2" style="flex:1">
                        <div class="fw-bold fs-4">${r.evaluated_count}</div>
                        <div class="small text-muted">Evaluated</div>
                    </div>
                    <div class="stat-card warning text-center p-2" style="flex:1">
                        <div class="fw-bold fs-4">${r.pending_count}</div>
                        <div class="small text-muted">Pending</div>
                    </div>
                    <div class="stat-card info text-center p-2" style="flex:1">
                        <div class="fw-bold fs-4">${r.average_similarity}%</div>
                        <div class="small text-muted">Avg Similarity</div>
                    </div>
                    <div class="stat-card text-center p-2" style="flex:1">
                        <div class="fw-bold fs-4">${r.average_marks}</div>
                        <div class="small text-muted">Avg Marks</div>
                    </div>
                </div>
                <div class="report-card-content">
                    <div class="report-card-body" id="report-body-${r.assignment_id}">
                        <div class="text-center py-3 text-muted">Loading submissions...</div>
                    </div>
                </div>
            </div>
        `).join('');

    } catch (err) {
        container.innerHTML = `<div class="alert alert-danger">${err.message}</div>`;
        showToast('Failed to load reports', 'error');
    }
}

async function toggleReportCard(assignmentId) {
    const card = document.getElementById(`report-${assignmentId}`);
    if (!card) return;
    
    const isExpanded = card.classList.contains('expanded');
    
    if (isExpanded) {
        card.classList.remove('expanded');
    } else {
        card.classList.add('expanded');
        // Load submissions if not cached
        if (!_reportSubmissions[assignmentId]) {
            await loadAssignmentSubmissions(assignmentId);
        } else {
            renderSubmissionsTable(assignmentId, _reportSubmissions[assignmentId]);
        }
    }
}

async function loadAssignmentSubmissions(assignmentId) {
    const body = document.getElementById(`report-body-${assignmentId}`);
    if (!body) return;
    
    try {
        const data = await apiRequest(`/teacher/submissions?assignment_id=${assignmentId}`);
        const submissions = data.submissions || [];
        _reportSubmissions[assignmentId] = submissions;
        renderSubmissionsTable(assignmentId, submissions);
    } catch (err) {
        body.innerHTML = `<div class="alert alert-danger">${err.message}</div>`;
    }
}

function renderSubmissionsTable(assignmentId, submissions) {
    const body = document.getElementById(`report-body-${assignmentId}`);
    if (!body) return;
    
    if (submissions.length === 0) {
        body.innerHTML = `<div class="text-center py-3 text-muted">No submissions yet for this assignment.</div>`;
        return;
    }
    
    body.innerHTML = `
        <h6 class="mb-3">Student Submissions (${submissions.length})</h6>
        <div class="table-responsive">
            <table class="student-submissions-table">
                <thead>
                    <tr>
                        <th>Student Name</th>
                        <th>Status</th>
                        <th>Similarity</th>
                        <th>Marks</th>
                        <th>Manual Check</th>
                        <th>Action</th>
                    </tr>
                </thead>
                <tbody>
                    ${submissions.map(s => `
                        <tr>
                            <td><strong>${escapeHtml(s.student_name)}</strong></td>
                            <td>
                                <span class="badge-status badge-${s.status}">${s.status.toUpperCase()}</span>
                                ${s.status === 'error' && s.error_message ? `<div class="small text-danger mt-1">${escapeHtml(s.error_message)}</div>` : ''}
                            </td>
                            <td>${s.status === 'evaluated' ? (s.similarity_score * 100).toFixed(1) + '%' : '-'}</td>
                            <td>${s.status === 'evaluated' ? s.marks_obtained + '/' + s.total_marks : '-'}</td>
                            <td>${s.manual_check ? '<span class="text-success">Yes</span>' : '<span class="text-muted">No</span>'}</td>
                            <td>
                                ${s.status === 'evaluated' ? `
                                <a href="/teacher/edit_marks.html?submission_id=${s.id}" class="btn btn-sm btn-outline-primary">
                                    <svg width="16" height="16" fill="currentColor" class="bi bi-pencil-square" viewBox="0 0 16 16">
                                      <path d="M15.502 1.94a.5.5 0 0 1 0 .706L14.459 3.69l-2-2L13.502.646a.5.5 0 0 1 .707 0l1.293 1.293zm-1.75 2.456-2-2L4.939 9.21a.5.5 0 0 0-.121.196l-.805 2.414a.25.25 0 0 0 .316.316l2.414-.805a.5.5 0 0 0 .196-.12l6.813-6.814z"/>
                                      <path fill-rule="evenodd" d="M1 13.5A1.5 1.5 0 0 0 2.5 15h11a1.5 1.5 0 0 0 1.5-1.5v-6a.5.5 0 0 0-1 0v6a.5.5 0 0 1-.5.5h-11a.5.5 0 0 1-.5-.5v-11a.5.5 0 0 1 .5-.5H9a.5.5 0 0 0 0-1H2.5A1.5 1.5 0 0 0 1 2.5v11z"/>
                                    </svg> Edit
                                </a>` : '-'}
                            </td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        </div>
    `;
}

// ---- Manual Evaluation (Edit Marks) ----

async function setupEditMarksPage() {
    const params = new URLSearchParams(window.location.search);
    const submissionId = params.get('submission_id');
    
    if (!submissionId) {
        showToast('No submission ID provided', 'error');
        return;
    }
    
    const container = document.getElementById('questions-container');
    const studentInfo = document.getElementById('student-info');
    const subStatus = document.getElementById('sub-status');
    const aiMarksTotal = document.getElementById('ai-marks-total');
    const aiSimTotal = document.getElementById('ai-sim-total');

    try {
        const data = await apiRequest(`/teacher/submission/${submissionId}`);
        const submission = data.submission;
        const assignment = data.assignment;

        studentInfo.textContent = `Student: ${submission.student_name} | Assignment: ${assignment.title}`;
        subStatus.textContent = submission.status.toUpperCase();
        subStatus.className = `badge bg-${submission.status === 'evaluated' ? 'success' : 'secondary'}`;
        aiMarksTotal.textContent = `${submission.marks_obtained}/${assignment.total_marks}`;
        aiSimTotal.textContent = `${(submission.similarity_score * 100).toFixed(1)}% Score`;
        
        document.getElementById('teacher-comments').value = submission.teacher_comments || '';

        const results = submission.question_results || [];
        container.innerHTML = assignment.questions.map((q, idx) => {
            const res = results.find(r => r.question_index === idx) || {};
            const q_num = q.original_num || (idx + 1);
            
            return `
                <div class="question-edit-card row g-3" data-idx="${idx}">

    <!-- LEFT SIDE : Answers -->
    <div class="col-md-7">

        <label class="small fw-bold mb-1">🧑‍🎓 Student Answer Extracted:</label>
        <div class="answer-box student-answer">
            ${escapeHtml(res.extracted_answer || ("Answer not clearly found for Question " + q_num + "."))}
        </div>

        <label class="small fw-bold mb-1">📘 Model Answer (Reference):</label>
        <div class="answer-box model-answer">
            ${escapeHtml(q.model_answer)}
        </div>

    </div>

    <!-- RIGHT SIDE : AI Evaluation -->
    <div class="col-md-5">

        <div class="content-card p-3 shadow-sm">

            <div class="mb-3 d-flex justify-content-between align-items-center">
                <span class="small fw-bold">AI Similarity:</span>
                <span class="ai-badge">${(res.similarity_score * 100 || 0).toFixed(1)}%</span>
            </div>

            <div class="mb-3 d-flex justify-content-between align-items-center">
                <span class="small fw-bold">AI Suggestion:</span>
                <span class="fw-bold text-primary">${res.ai_marks || 0} / ${q.marks} Marks</span>
            </div>

            <hr>

            <label class="form-label fw-bold">Assign Marks:</label>

            <div class="input-group">
                <input type="number"
                       step="0.5"
                       class="form-control form-control-lg edit-q-marks"
                       value="${res.marks_obtained ?? 0}"
                       min="0"
                       max="${q.marks}"
                       onchange="updateManualTotalMarks()">

                <span class="input-group-text">/ ${q.marks}</span>
            </div>

        </div>

    </div>

</div>
            `;
        }).join('');

        updateManualTotalMarks();
        // attach input listeners so arrows update total immediately
        document.querySelectorAll('.edit-q-marks').forEach((input, i) => {
    const marks = Number(input.value);
        });
        
        document.getElementById('edit-marks-form').onsubmit = async (e) => {
            e.preventDefault();
            const btn = document.getElementById('save-btn');
            btn.disabled = true;
            btn.textContent = 'Saving Changes...';

            const question_results = [];
            // iterate through each mark input; wrapper may not exist in older code
            document.querySelectorAll('.edit-q-marks').forEach((input, i) => {
                const marks = parseFloat(input.value) || 0;
                // try to get question index from parent card data attribute
                let idx;
                const card = input.closest('.question-edit-card');
                if (card && card.dataset.idx !== undefined) {
                    idx = parseInt(card.dataset.idx);
                } else {
                    idx = i; // fallback to order
                }
                const existing = results.find(r => r.question_index === idx) || {};
                question_results.push({
                    ...existing,
                    question_index: idx,
                    marks_obtained: marks
                });
            });

            try {
                // debug: show what will be submitted
                console.log('submitting manual results', question_results);
                await apiRequest(`/teacher/edit-marks/${submissionId}`, {
                    method: 'POST',
                    body: JSON.stringify({
                        question_results,
                        teacher_comments: document.getElementById('teacher-comments').value
                    })
                });
                showToast('Marks updated successfully!', 'success');
                setTimeout(() => window.location.href = '/teacher/reports.html', 1500);
            } catch (err) {
                showToast(err.message, 'error');
                btn.disabled = false;
                btn.textContent = 'Save Manual Evaluation';
            }
        };

    } catch (err) {
        container.innerHTML = `<div class="alert alert-danger">${err.message}</div>`;
    }
}

function updateManualTotalMarks() {
    let total = 0;
    document.querySelectorAll('.edit-q-marks').forEach(input => {
        total += Number(input.value) || 0;
    });
    const display = document.getElementById('total-marks-display');
    if (display) display.textContent = total;
}

async function downloadReportExcel(assignmentId, assignmentTitle) {
    if (typeof XLSX === 'undefined') {
        showToast('Excel export library not loaded. Please refresh the page.', 'error');
        return;
    }
    
    try {
        if (!_reportSubmissions[assignmentId]) {
            const data = await apiRequest(`/teacher/submissions?assignment_id=${assignmentId}`);
            _reportSubmissions[assignmentId] = data.submissions || [];
        }
        
        const submissions = _reportSubmissions[assignmentId];
        
        if (submissions.length === 0) {
            showToast('No submissions to export', 'warning');
            return;
        }
        
        const excelData = submissions.map((s, idx) => ({
            'S.No': idx + 1,
            'Student Name': s.student_name,
            'Status': s.status.toUpperCase(),
            'Similarity Score (%)': s.status === 'evaluated' ? (s.similarity_score * 100).toFixed(2) : 'N/A',
            'Marks Obtained': s.status === 'evaluated' ? s.marks_obtained : 'N/A',
            'Total Marks': s.total_marks,
            'Manual Check': s.manual_check ? 'Yes' : 'No',
            'Submitted At': s.submitted_at ? new Date(s.submitted_at).toLocaleString() : 'N/A'
        }));
        
        const ws = XLSX.utils.json_to_sheet(excelData);
        const wb = XLSX.utils.book_new();
        
        ws['!cols'] = [
            { wch: 6 },  { wch: 25 }, { wch: 12 }, { wch: 18 }, { wch: 14 }, { wch: 12 }, { wch: 12 }, { wch: 20 },
        ];
        
        XLSX.utils.book_append_sheet(wb, ws, 'Submissions');
        
        const safeTitle = assignmentTitle.replace(/[^a-z0-9]/gi, '_').substring(0, 30);
        const filename = `${safeTitle}_submissions_${new Date().toISOString().split('T')[0]}.xlsx`;
        
        XLSX.writeFile(wb, filename);
        showToast(`Downloaded ${submissions.length} submission(s)`, 'success');
        
    } catch (err) {
        showToast('Failed to export: ' + err.message, 'error');
    }
}

function escapeAttr(text) {
    if (!text) return '';
    return text.replace(/'/g, "\\'").replace(/"/g, '&quot;');
}

// ---- Helpers ----

function formatDate(iso) {
    if (!iso) return '';
    return new Date(iso).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
