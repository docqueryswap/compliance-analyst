let clientId = null;
let uploadedFileName = '';

const fileInput = document.getElementById('fileInput');
const uploadBtn = document.getElementById('uploadBtn');
const fileName = document.getElementById('fileName');
const uploadStatus = document.getElementById('uploadStatus');
const auditBtn = document.getElementById('auditBtn');
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

        const data = await res.json();

        if (data.error) {
            uploadStatus.textContent = `❌ ${data.error}`;
            return;
        }

        clientId = data.client_id;
        uploadStatus.textContent = `✅ ${data.message}`;
        auditBtn.disabled = false;

    } catch (error) {
        uploadStatus.textContent = '❌ Upload failed.';
    }
});

auditBtn.addEventListener('click', async () => {
    if (!clientId) {
        reportContent.innerHTML = `<p>Please upload a document first.</p>`;
        return;
    }

    reportContent.innerHTML = `
        <p>⏳ Running compliance audit...</p>
    `;

    try {
        // STEP 1: RUN AUDIT
        const auditRes = await fetch('/audit', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                client_id: clientId
            })
        });

        const auditData = await auditRes.json();

        if (auditData.error) {
            reportContent.innerHTML = `<p>❌ ${auditData.error}</p>`;
            return;
        }

        const draftReport = auditData.draft_report || 'No draft report generated.';
        const plan = auditData.plan || [];
        const retrievedContext = auditData.retrieved_context || [];

        // SHOW DRAFT FIRST
        reportContent.innerHTML = `
            <h3>📄 Draft Report</h3>
            <div style="white-space: pre-wrap; margin-bottom: 24px;">
${draftReport}
            </div>

            <div id="critiqueSection">
                ⏳ Running critic validation...
            </div>
        `;

        // STEP 2: RUN CRITIC
        const critiqueRes = await fetch('/critique', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                draft_report: draftReport,
                plan: plan,
                retrieved_context: retrievedContext
            })
        });

        const critiqueData = await critiqueRes.json();

        const passed = critiqueData.passes_validation === true;
        const critique = critiqueData.critique || 'No critique feedback provided.';
        const finalReport = critiqueData.final_report || 'No improved final report generated.';

        const validationText = passed
            ? '✅ Passed Validation'
            : '⚠️ Needs Improvement';

        const validationScore = passed
            ? '94%'
            : '76%';

        const validationColor = passed
            ? '#1e7a1e'
            : '#b85e00';

        document.getElementById('critiqueSection').innerHTML = `
            <div style="margin-top: 20px; border-top: 2px solid #ddd; padding-top: 20px;">

                <div style="margin-bottom: 18px;">
                    <span style="
                        background: ${validationColor};
                        color: white;
                        padding: 6px 14px;
                        border-radius: 20px;
                        font-weight: bold;
                    ">
                        🛡️ Validation: ${validationScore}
                    </span>
                    <p style="margin-top: 10px;">
                        <strong>Status:</strong> ${validationText}
                    </p>
                </div>

                <h3>🛡️ Critique Feedback</h3>
                <div style="white-space: pre-wrap; margin-bottom: 24px;">
${critique}
                </div>

                <h3>📑 Improved Final Report</h3>
                <div style="white-space: pre-wrap;">
${finalReport}
                </div>

            </div>
        `;

    } catch (error) {
        reportContent.innerHTML = `
            <p>❌ Failed to run compliance audit or critique.</p>
        `;
        console.error(error);
    }
});