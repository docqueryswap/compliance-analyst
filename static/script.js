let clientId = null;
let uploadedFileName = '';
let latestDraftReport = '';
let latestPlan = [];
let latestContext = [];
let latestDocumentType = 'other';

function resetCritiqueState() {
    latestDraftReport = '';
    latestPlan = [];
    latestContext = [];
    latestDocumentType = 'other';
    critiqueBtn.disabled = true;
}

function clearCritiqueSection() {
    const existingCritiqueSection = document.getElementById('critiqueSection');
    if (existingCritiqueSection) {
        existingCritiqueSection.remove();
    }
}

function escapeHtml(value) {
    return String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

async function parseJsonResponse(response, fallbackMessage) {
    try {
        return await response.json();
    } catch (error) {
        return { error: fallbackMessage };
    }
}

function safeArray(value) {
    return Array.isArray(value) ? value : [];
}

function hasActionableCritique(critiqueText) {
    const critique = String(critiqueText || '').toLowerCase();
    return Boolean(
        critique &&
        critique !== 'no critique feedback provided.' &&
        !critique.includes('no critical errors found') &&
        !critique.includes('source-grounded verification')
    );
}

// Extract a confidence score like "8/10", "confidence score of 8", etc.
function extractConfidenceFromDraft(draftText) {
    if (!draftText) return null;
    const patterns = [
        /confidence\s*score\b.*?(\d{1,2})\s*\/\s*10/i,
        /(\d{1,2})\s*\/\s*10\s*confidence\s*score/i,
        /confidence\s*score\b.*?(\d{1,2})\b/i,
    ];
    for (const regex of patterns) {
        const match = draftText.match(regex);
        if (match) {
            const num = parseInt(match[1], 10);
            if (/\/\s*10/.test(match[0]) && num >= 0 && num <= 10) {
                return num * 10;
            }
            if (num >= 0 && num <= 100) {
                return num;
            }
        }
    }
    return null;
}

// Generate dynamic verdict banner based on Critic result
function getVerdictBanner(result) {
    const safeResult = result || {};
    const numericConfidence = Number(safeResult.confidence_score);
    const confidenceScore = Number.isFinite(numericConfidence) ? numericConfidence : 55;
    const passed = safeResult.passes_validation === true;
    const critique = String(safeResult.critique || '');
    const hasCritique = hasActionableCritique(critique);
    const isFallback = safeResult._fallback_triggered === true;

    let banner = '';
    let confidenceNote = '';

    if (isFallback) {
        banner = `⚠️ Critique Unavailable — Report reflects initial draft only. Human review required.`;
        confidenceNote = `📊 Confidence: ${confidenceScore}/100`;
    } else if (passed && !hasCritique) {
        banner = `✅ Passed Validation — No errors found. Report is consistent with source document.`;
        confidenceNote = `📊 Confidence: ${confidenceScore}/100 — ${confidenceScore < 60 ? 'Moderate due to incomplete document sections.' : 'Strong evidentiary support.'}`;
    } else if (passed && hasCritique) {
        banner = `✅ Passed Validation — Minor issues noted. See feedback below.`;
        confidenceNote = `📊 Confidence: ${confidenceScore}/100`;
    } else {
        banner = `⚠️ Needs Improvement — Errors found. Report revised based on feedback.`;
        confidenceNote = `📊 Confidence: ${confidenceScore}/100`;
    }

    return { banner, confidenceNote };
}

const fileInput = document.getElementById('fileInput');
const uploadBtn = document.getElementById('uploadBtn');
const fileName = document.getElementById('fileName');
const uploadStatus = document.getElementById('uploadStatus');
const auditBtn = document.getElementById('auditBtn');
const critiqueBtn = document.getElementById('critiqueBtn');
const reportContent = document.getElementById('reportContent');

uploadBtn.addEventListener('click', () => fileInput.click());

fileInput.addEventListener('change', async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    uploadedFileName = file.name;
    fileName.textContent = `📄 ${uploadedFileName}`;

    const formData = new FormData();
    formData.append('file', file);

    uploadStatus.textContent = '⏳ Processing document...';

    try {
        const res = await fetch('/upload', {
            method: 'POST',
            body: formData
        });

        const data = await parseJsonResponse(res, 'Upload response was not valid JSON.');

        if (!res.ok) {
            throw new Error(data.error || 'Upload failed.');
        }

        if (data.error) {
            uploadStatus.textContent = `❌ ${data.error}`;
            return;
        }

        clientId = data.client_id;
        resetCritiqueState();
        clearCritiqueSection();
        uploadStatus.textContent = `✅ ${data.message}`;
        auditBtn.disabled = false;

    } catch (error) {
        uploadStatus.textContent = `❌ ${error.message || 'Upload failed.'}`;
    }
});

auditBtn.addEventListener('click', async () => {
    if (!clientId) {
        reportContent.innerHTML = `<p>Please upload a document first.</p>`;
        return;
    }

    resetCritiqueState();
    clearCritiqueSection();
    reportContent.innerHTML = `<p>⏳ Running compliance audit...</p>`;

    try {
        const auditRes = await fetch('/audit', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ client_id: clientId })
        });

        const auditData = await parseJsonResponse(auditRes, 'Audit response was not valid JSON.');

        if (!auditRes.ok) {
            throw new Error(auditData.error || 'Audit request failed.');
        }

        if (auditData.error) {
            reportContent.innerHTML = `<p>❌ ${escapeHtml(auditData.error)}</p>`;
            return;
        }

        const draftReport = auditData.draft_report || 'No draft report generated.';
        latestDraftReport = draftReport;
        latestPlan = safeArray(auditData.plan);
        latestContext = safeArray(auditData.retrieved_context);
        latestDocumentType = auditData.document_type || 'other';
        critiqueBtn.disabled = false;

        const draftConfidence = extractConfidenceFromDraft(draftReport);

        reportContent.innerHTML = `
            <h3>📄 Draft Report</h3>
            <div style="white-space: pre-wrap; margin-bottom: 24px;">${escapeHtml(draftReport)}</div>
        `;

        if (draftConfidence !== null) {
            const confColor = draftConfidence >= 70 ? '#1e7a1e' : draftConfidence >= 40 ? '#b85e00' : '#c62828';
            const confDisplay = document.createElement('div');
            confDisplay.innerHTML = `
                <div style="margin-bottom: 18px;">
                    <span style="background: ${confColor}; color: white; padding: 6px 14px; border-radius: 20px; font-weight: bold;">
                        📊 Draft Confidence: ${draftConfidence}/100
                    </span>
                    <p style="margin-top: 10px; color: #666;">Self‑assessed by the report generator.</p>
                </div>
            `;
            reportContent.appendChild(confDisplay);
        }

    } catch (error) {
        reportContent.innerHTML = `<p>❌ ${escapeHtml(error.message || 'Failed to run compliance audit.')}</p>`;
        resetCritiqueState();
        console.error(error);
    }
});

critiqueBtn.addEventListener('click', async () => {
    if (!latestDraftReport) return;

    critiqueBtn.disabled = true;
    clearCritiqueSection();

    reportContent.insertAdjacentHTML('beforeend', `
        <div id="critiqueSection" style="margin-top: 20px; border-top: 2px solid #ddd; padding-top: 20px;">
            ⏳ Running critic validation...
        </div>
    `);

    try {
        const critiqueRes = await fetch('/critique?source=button_click', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                draft_report: latestDraftReport,
                plan: latestPlan,
                context: latestContext,
                document_type: latestDocumentType
            })
        });

        let critiqueData = null;
        try {
            critiqueData = await critiqueRes.json();
        } catch (parseError) {
            throw new Error('Critique response was not valid JSON.');
        }

        if (!critiqueRes.ok) {
            throw new Error(critiqueData?.error || 'Critique request failed.');
        }

        if (!critiqueData || typeof critiqueData !== 'object' || Array.isArray(critiqueData)) {
            throw new Error('Critique response was empty.');
        }

        if (critiqueData.error) {
            throw new Error(critiqueData.error);
        }

        const passed = critiqueData.passes_validation === true;
        const critique = String(critiqueData.critique || 'No critique feedback provided.');
        const finalReport = String(critiqueData.final_report || latestDraftReport || 'No final report generated.');

        let confidenceScore = Number(critiqueData.confidence_score);
        const fallbackCritiqueMarkers = [
            'source-grounded verification',
            'too brief for a reliable compliance assessment',
            'stricter validation of evidence'
        ];
        const critiqueLower = critique.toLowerCase();
        const isFallback = critiqueData._fallback_triggered === true ||
            fallbackCritiqueMarkers.some(marker => critiqueLower.includes(marker));
        if (isFallback || !Number.isFinite(confidenceScore)) {
            const draftConf = extractConfidenceFromDraft(latestDraftReport);
            confidenceScore = draftConf !== null ? draftConf : 55;
        }
        confidenceScore = Math.max(0, Math.min(100, confidenceScore));

        const hasCritique = hasActionableCritique(critique);

        // Generate dynamic banner
        const { banner, confidenceNote } = getVerdictBanner({
            passes_validation: passed,
            critique: critique,
            confidence_score: confidenceScore,
            _fallback_triggered: isFallback
        });

        const bannerColor = isFallback ? '#b85e00' : passed ? '#1e7a1e' : '#b85e00';
        const confidenceColor = confidenceScore >= 70 ? '#1e7a1e' : confidenceScore >= 40 ? '#b85e00' : '#c62828';
        const finalReportLabel = isFallback
            ? '📑 Draft Report (Critique Unavailable)'
            : passed
                ? '📑 Validated Final Report'
                : '📑 Improved Final Report';
        const critiqueSection = document.getElementById('critiqueSection');
        if (!critiqueSection) return;

        critiqueSection.innerHTML = `
            <div style="margin-bottom: 18px; background: ${bannerColor}; color: white; padding: 12px 18px; border-radius: 8px; font-weight: bold;">
                ${banner}
            </div>
            <div style="margin-bottom: 18px; display: flex; gap: 16px; flex-wrap: wrap;">
                <span style="
                    background: ${confidenceColor};
                    color: white;
                    padding: 6px 14px;
                    border-radius: 20px;
                    font-weight: bold;
                ">
                    ${confidenceNote}
                </span>
            </div>
            ${hasCritique ? `
                <h3>🛡️ Critique Feedback</h3>
                <div style="white-space: pre-wrap; margin-bottom: 24px;">${escapeHtml(critique)}</div>
            ` : ''}
            <h3>${finalReportLabel}</h3>
            <div style="white-space: pre-wrap;">${escapeHtml(finalReport)}</div>
        `;
    } catch (error) {
        const critiqueSection = document.getElementById('critiqueSection');
        if (critiqueSection) {
            critiqueSection.innerHTML = `<p>❌ ${escapeHtml(error.message || 'Failed to run critique.')}</p>`;
        }
        console.error(error);
    } finally {
        critiqueBtn.disabled = false;
    }
});
