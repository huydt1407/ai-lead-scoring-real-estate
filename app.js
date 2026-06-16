// App State
let leads = [];
let filteredLeads = [];
let currentPage = 1;
let pageSize = 10;
let currentLeadEditing = null;

// DOM Elements
const sheetUrlInput = document.getElementById('sheet-url');
const apiKeyInput = document.getElementById('api-key');
const scorerEngineSelect = document.getElementById('scorer-engine');
const loadDataBtn = document.getElementById('load-data-btn');
const runScoringBtn = document.getElementById('run-scoring-btn');
const exportExcelBtn = document.getElementById('export-excel-btn');

const searchInput = document.getElementById('search-input');
const categoryFilter = document.getElementById('category-filter');
const statusFilter = document.getElementById('status-filter');

const totalLeadsSpan = document.getElementById('total-leads');
const vipLeadsSpan = document.getElementById('vip-leads');
const normalLeadsSpan = document.getElementById('normal-leads');
const junkLeadsSpan = document.getElementById('junk-leads');
const reviewedLeadsSpan = document.getElementById('reviewed-leads');

const tableBody = document.getElementById('table-body');
const paginationInfo = document.getElementById('pagination-info');
const prevPageBtn = document.getElementById('prev-page');
const nextPageBtn = document.getElementById('next-page');

const editModal = document.getElementById('edit-modal');
const modalClose = document.getElementById('modal-close');
const cancelEditBtn = document.getElementById('cancel-edit-btn');
const saveEditBtn = document.getElementById('save-edit-btn');

// Detail Modal Fields
const detailId = document.getElementById('detail-id');
const detailName = document.getElementById('detail-name');
const detailPhone = document.getElementById('detail-phone');
const detailDesc = document.getElementById('detail-desc');
const detailAiScore = document.getElementById('detail-ai-score');
const detailAiReason = document.getElementById('detail-ai-reason');
const overrideReason = document.getElementById('override-reason');

// Load API key and Sheet URL from localStorage on startup
document.addEventListener('DOMContentLoaded', () => {
    const savedApiKey = localStorage.getItem('gemini_api_key');
    const savedSheetUrl = localStorage.getItem('google_sheet_url');
    
    if (savedApiKey) apiKeyInput.value = savedApiKey;
    if (savedSheetUrl) sheetUrlInput.value = savedSheetUrl;
    
    setupEventListeners();
    updateMetrics();
});

// Event Listeners
function setupEventListeners() {
    loadDataBtn.addEventListener('click', loadData);
    runScoringBtn.addEventListener('click', runScoring);
    exportExcelBtn.addEventListener('click', exportToExcel);
    
    searchInput.addEventListener('input', applyFilters);
    categoryFilter.addEventListener('change', applyFilters);
    statusFilter.addEventListener('change', applyFilters);
    
    prevPageBtn.addEventListener('click', () => {
        if (currentPage > 1) {
            currentPage--;
            renderTable();
        }
    });
    
    nextPageBtn.addEventListener('click', () => {
        const totalPages = Math.ceil(filteredLeads.length / pageSize);
        if (currentPage < totalPages) {
            currentPage++;
            renderTable();
        }
    });
    
    modalClose.addEventListener('click', closeModal);
    cancelEditBtn.addEventListener('click', closeModal);
    saveEditBtn.addEventListener('click', saveOverride);
    
    // Save settings to localStorage on change
    apiKeyInput.addEventListener('change', () => {
        localStorage.setItem('gemini_api_key', apiKeyInput.value.trim());
    });
    sheetUrlInput.addEventListener('change', () => {
        localStorage.setItem('google_sheet_url', sheetUrlInput.value.trim());
    });
}

// CSV Parser Helper
function parseCSV(csvText) {
    const lines = [];
    let row = [""];
    let inQuotes = false;

    for (let i = 0; i < csvText.length; i++) {
        const char = csvText[i];
        const nextChar = csvText[i + 1];

        if (char === '"') {
            if (inQuotes && nextChar === '"') {
                row[row.length - 1] += '"';
                i++;
            } else {
                inQuotes = !inQuotes;
            }
        } else if (char === ',' && !inQuotes) {
            row.push('');
        } else if ((char === '\r' || char === '\n') && !inQuotes) {
            if (char === '\r' && nextChar === '\n') {
                i++;
            }
            lines.push(row);
            row = [''];
        } else {
            row[row.length - 1] += char;
        }
    }
    if (row.length > 1 || row[0] !== '') {
        lines.push(row);
    }
    return lines;
}

// Load Google Sheet Data
async function loadData() {
    let rawUrl = sheetUrlInput.value.trim();
    if (!rawUrl) {
        showToast('Vui lòng nhập đường dẫn Google Sheets!', 'error');
        return;
    }
    
    showLoading(true);
    
    try {
        // Transform the Google Sheets URL to a CSV export URL
        let exportUrl = rawUrl;
        
        // Handle normal edit link
        if (rawUrl.includes('/edit')) {
            const sheetIdMatch = rawUrl.match(/\/d\/([a-zA-Z0-9-_]+)/);
            if (sheetIdMatch) {
                const sheetId = sheetIdMatch[1];
                let gid = '0';
                const gidMatch = rawUrl.match(/gid=(\d+)/);
                if (gidMatch) {
                    gid = gidMatch[1];
                }
                exportUrl = `https://docs.google.com/spreadsheets/d/${sheetId}/export?format=csv&gid=${gid}`;
            }
        }
        
        // Fallback for redirected sheet URL ID
        if (rawUrl.includes('docs.google.com/spreadsheets') && !rawUrl.includes('/export')) {
            // Check if we need to use proxy or fetch directly
        }

        // Try direct fetch
        let response;
        try {
            response = await fetch(exportUrl);
        } catch (fetchErr) {
            // If CORS blocks it, try to fetch via a CORS proxy or give user instructions
            console.warn("Direct fetch blocked by CORS, trying fallback proxy...", fetchErr);
            const proxyUrl = `https://api.allorigins.win/raw?url=${encodeURIComponent(exportUrl)}`;
            response = await fetch(proxyUrl);
        }
        
        if (!response.ok) {
            throw new Error(`Mã lỗi HTTP: ${response.status}`);
        }
        
        const csvText = await response.text();
        const parsedRows = parseCSV(csvText);
        
        if (parsedRows.length < 2) {
            throw new Error("Tệp dữ liệu rỗng hoặc không đúng định dạng CSV.");
        }
        
        // Match headers
        const headers = parsedRows[0].map(h => h.trim().toLowerCase());
        const idIndex = headers.indexOf('id');
        const nameIndex = headers.indexOf('ten_khach');
        const phoneIndex = headers.indexOf('sdt');
        const descIndex = headers.indexOf('nhu_cau_mo_ta');
        
        if (nameIndex === -1 || descIndex === -1) {
            throw new Error("Không tìm thấy các cột bắt buộc: 'ten_khach', 'nhu_cau_mo_ta'");
        }
        
        leads = [];
        for (let i = 1; i < parsedRows.length; i++) {
            const row = parsedRows[i];
            if (row.length < Math.max(nameIndex, descIndex) + 1) continue;
            if (!row[nameIndex] && !row[descIndex]) continue;
            
            leads.push({
                id: idIndex !== -1 ? (row[idIndex] || '').toString() : i.toString(),
                name: (row[nameIndex] || 'Ẩn danh').toString().trim(),
                phone: phoneIndex !== -1 ? (row[phoneIndex] || '').toString().trim() : '',
                description: (row[descIndex] || '').toString().trim(),
                aiScore: null,
                aiCategory: null,
                aiReason: 'Chưa chấm điểm',
                finalScore: null,
                finalCategory: null,
                status: 'Chưa đánh giá', // Chưa đánh giá, Đã chấm điểm, Đã duyệt
                reviewedBy: ''
            });
        }
        
        showToast(`Tải thành công ${leads.length} khách hàng!`, 'success');
        runScoringBtn.removeAttribute('disabled');
        applyFilters();
    } catch (error) {
        console.error(error);
        showToast(`Lỗi khi tải dữ liệu: ${error.message}`, 'error');
    } finally {
        showLoading(false);
    }
}

// Show Loading State
function showLoading(isLoading) {
    if (isLoading) {
        tableBody.innerHTML = `
            <tr>
                <td colspan="7">
                    <div class="spinner-container">
                        <div class="spinner"></div>
                        <p>Đang tải dữ liệu, vui lòng đợi...</p>
                    </div>
                </td>
            </tr>
        `;
        runScoringBtn.setAttribute('disabled', 'true');
        exportExcelBtn.setAttribute('disabled', 'true');
    }
}

// Run Lead Scoring
async function runScoring() {
    if (leads.length === 0) {
        showToast('Vui lòng tải dữ liệu trước!', 'warning');
        return;
    }
    
    const engine = scorerEngineSelect.value;
    const apiKey = apiKeyInput.value.trim();
    
    if (engine === 'ai' && !apiKey) {
        showToast('Vui lòng nhập API Key để dùng động cơ AI!', 'error');
        return;
    }
    
    runScoringBtn.setAttribute('disabled', 'true');
    showToast('Bắt đầu chấm điểm hàng loạt...', 'warning');
    
    let processedCount = 0;
    
    for (let i = 0; i < leads.length; i++) {
        const lead = leads[i];
        
        // Progress update in table
        tableBody.innerHTML = `
            <tr>
                <td colspan="7">
                    <div class="spinner-container">
                        <div class="spinner"></div>
                        <p>Đang chấm điểm khách hàng ${i + 1}/${leads.length}...</p>
                    </div>
                </td>
            </tr>
        `;
        
        let result;
        if (engine === 'ai') {
            result = await scoreWithGemini(lead.description, apiKey);
        } else {
            result = scoreWithRegex(lead.description);
        }
        
        lead.aiScore = result.score;
        lead.aiCategory = result.category;
        lead.aiReason = result.reason;
        
        // Initial setup for final values
        lead.finalScore = result.score;
        lead.finalCategory = result.category;
        lead.status = 'Đã chấm điểm';
        
        processedCount++;
    }
    
    showToast(`Đã hoàn tất chấm điểm ${processedCount} khách hàng!`, 'success');
    runScoringBtn.removeAttribute('disabled');
    exportExcelBtn.removeAttribute('disabled');
    
    applyFilters();
}

// Regex Scoring Engine Fallback
function scoreWithRegex(desc) {
    const text = desc.toLowerCase();
    
    // 1. Check Junk / Spams (-50 points)
    const junkKeywords = [
        "nhầm số", "không có nhu cầu", "dữ liệu cũ", "nhầm ngành",
        "hỏi giá cho vui", "chưa có ý định mua",
        "bảo hiểm", "vay vốn", "mời chào", "quảng cáo ngược",
        "thuê bao", "gọi nhiều lần không bắt máy", "gọi nhiều lần không nhấc", 
        "gọi nhiều lần không nghe", "không phản hồi zalo", "nhầm máy"
    ];
    
    const unrealisticRegex = [
        /nhà thuê nguyên căn giá 2 triệu/,
        /thuê nguyên căn giá 2 triệu/,
        /nhà thuê.*2 triệu.*trung tâm/,
        /đòi mua nhà (?:q1|quận 1) giá 1 tỷ/,
        /mua nhà (?:q1|quận 1) giá 1 tỷ/,
        /nhà q1 giá 1 tỷ/,
        /thái độ không hợp tác/,
        /yêu cầu phi thực tế/
    ];
    
    let isJunk = false;
    let junkMatched = [];
    
    for (const kw of junkKeywords) {
        if (text.includes(kw)) {
            isJunk = true;
            junkMatched.push(`Từ khóa: "${kw}"`);
        }
    }
    for (const rx of unrealisticRegex) {
        if (rx.test(text)) {
            isJunk = true;
            junkMatched.push(`Quy tắc: "${rx.source}"`);
        }
    }
    
    if (isJunk) {
        return {
            score: -50,
            category: 'Junk',
            reason: `Trừ 50 điểm vì phát hiện dấu hiệu rác/không nhu cầu (${junkMatched[0]}).`
        };
    }
    
    // 2. Check VIP / High Potential (+50 points)
    const vipKeywords = [
        "tài chính mạnh", "không thành vấn đề", "tài chính cực mạnh", "thanh toán thẳng", "ngân sách lớn", "mua sỉ", "mua số lượng lớn", "gom sỉ",
        "biệt thự đơn lập", "penthouse", "shophouse mặt đường lớn", "quỹ đất công nghiệp", "sàn văn phòng diện tích lớn",
        "quận 1", "ven sông", "vinhomes ocean park", "phú mỹ hưng",
        "chủ doanh nghiệp", "nhà đầu tư chuyên nghiệp",
        "pháp lý chuẩn", "sổ hồng riêng", "gặp trực tiếp chủ đầu tư", "gặp trực tiếp giám đốc"
    ];
    
    let isVip = false;
    let vipMatched = [];
    
    // Check custom numeric budget (>= 20 tỷ)
    const budgetMatch = text.match(/(\d+)\s*tỷ/);
    if (budgetMatch) {
        const val = parseInt(budgetMatch[1], 10);
        if (val >= 20) {
            isVip = true;
            vipMatched.push(`Ngân sách: ${val} tỷ (>= 20 tỷ)`);
        }
    }
    
    for (const kw of vipKeywords) {
        if (text.includes(kw)) {
            isVip = true;
            vipMatched.push(`Từ khóa: "${kw}"`);
        }
    }
    
    if (isVip) {
        return {
            score: 50,
            category: 'VIP',
            reason: `Cộng 50 điểm vì khách hàng VIP/Siêu tiềm năng (${vipMatched.slice(0, 2).join(', ')}).`
        };
    }
    
    // 3. Normal Leads (0 points)
    return {
        score: 0,
        category: 'Normal',
        reason: 'Khách hàng có nhu cầu bất động sản thông thường (Không có từ khóa VIP/Junk đặc thù).'
    };
}

// Gemini API Scorer
async function scoreWithGemini(description, apiKey) {
    const systemPrompt = `Bạn là một trợ lý AI chuyên nghiệp chấm điểm tiềm năng của khách hàng (Lead Scoring) cho ngành Bất động sản dựa trên mô tả nhu cầu.
Bạn hãy trả về duy nhất một chuỗi JSON hợp lệ theo định dạng dưới đây:
{
  "score": <số nguyên: 50 | -50 | 0>,
  "category": "<chuỗi: VIP | Junk | Normal>",
  "reason": "<chuỗi giải thích ngắn gọn bằng tiếng Việt>"
}

Quy tắc chấm điểm:
1. VIP (+50): Ngân sách >= 20 tỷ hoặc cụm từ "tài chính mạnh", "không thành vấn đề"; Loại hình cao cấp ("Biệt thự đơn lập", "Penthouse", "Shophouse mặt đường lớn", "Quỹ đất công nghiệp", "Sàn văn phòng diện tích lớn"); Vị trí đắc địa ("Quận 1", "Ven sông", "Vinhomes Ocean Park", "Phú Mỹ Hưng"); Chủ doanh nghiệp, nhà đầu tư mua sỉ; Pháp lý chuẩn 100%, sổ hồng riêng, muốn đàm phán trực tiếp chủ đầu tư.
2. Junk (-50): Yêu cầu phi thực tế (Ví dụ: Nhà Quận 1 giá 1-2 tỷ, nhà thuê 2 triệu ở trung tâm); Không nhu cầu ("nhầm số", "dữ liệu cũ", "nhầm ngành"); Không thiện chí ("hỏi giá cho vui", "thái độ không hợp tác"); Spam/Quảng cáo (bảo hiểm, vay vốn); Thông tin liên lạc lỗi (thuê bao, không bắt máy, không phản hồi zalo).
3. Normal (0): Mua chung cư, nhà phố trung cấp (3-10 tỷ); cần vay ngân hàng; nhu cầu thực nhưng cần tư vấn thêm.`;

    const url = `https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=${apiKey}`;
    
    try {
        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                contents: [{
                    parts: [{
                        text: `${systemPrompt}\n\nNhu cầu khách hàng cần đánh giá:\n"${description}"`
                    }]
                }],
                generationConfig: {
                    responseMimeType: "application/json"
                }
            })
        });
        
        if (!response.ok) {
            throw new Error(`Lỗi API: ${response.status}`);
        }
        
        const data = await response.json();
        const responseText = data.candidates[0].content.parts[0].text.trim();
        const result = JSON.parse(responseText);
        
        return {
            score: typeof result.score === 'number' ? result.score : 0,
            category: result.category || 'Normal',
            reason: result.reason || 'Được đánh giá bởi AI.'
        };
    } catch (err) {
        console.error("Gemini API Error, falling back to Regex scorer:", err);
        return scoreWithRegex(description);
    }
}

// Filter and Search Leads
function applyFilters() {
    const query = searchInput.value.toLowerCase().trim();
    const cat = categoryFilter.value;
    const stat = statusFilter.value;
    
    filteredLeads = leads.filter(lead => {
        const matchesSearch = (lead.name || '').toLowerCase().includes(query) || 
                              (lead.phone || '').includes(query) || 
                              (lead.description || '').toLowerCase().includes(query);
        
        const matchesCategory = cat === 'all' || 
                                (cat === 'VIP' && lead.finalCategory === 'VIP') ||
                                (cat === 'Normal' && lead.finalCategory === 'Normal') ||
                                (cat === 'Junk' && lead.finalCategory === 'Junk');
                                
        const matchesStatus = stat === 'all' || 
                              (stat === 'pending' && lead.status === 'Đã chấm điểm') ||
                              (stat === 'approved' && lead.status === 'Đã duyệt');
                              
        return matchesSearch && matchesCategory && matchesStatus;
    });
    
    currentPage = 1;
    updateMetrics();
    renderTable();
}

// Update Dashboard Statistics
function updateMetrics() {
    totalLeadsSpan.textContent = leads.length;
    
    const vipCount = leads.filter(l => l.finalCategory === 'VIP').length;
    const normalCount = leads.filter(l => l.finalCategory === 'Normal').length;
    const junkCount = leads.filter(l => l.finalCategory === 'Junk').length;
    const reviewedCount = leads.filter(l => l.status === 'Đã duyệt').length;
    
    vipLeadsSpan.textContent = vipCount;
    normalLeadsSpan.textContent = normalCount;
    junkLeadsSpan.textContent = junkCount;
    reviewedLeadsSpan.textContent = reviewedCount;
}

// Render Table Page
function renderTable() {
    const totalPages = Math.ceil(filteredLeads.length / pageSize) || 1;
    
    // Bounds check
    if (currentPage > totalPages) currentPage = totalPages;
    if (currentPage < 1) currentPage = 1;
    
    const startIndex = (currentPage - 1) * pageSize;
    const endIndex = Math.min(startIndex + pageSize, filteredLeads.length);
    
    tableBody.innerHTML = '';
    
    if (filteredLeads.length === 0) {
        tableBody.innerHTML = `
            <tr>
                <td colspan="7">
                    <div class="empty-state">
                        <div class="empty-icon">📁</div>
                        <p>Không tìm thấy khách hàng nào khớp với bộ lọc.</p>
                    </div>
                </td>
            </tr>
        `;
        paginationInfo.textContent = `0 - 0 trong 0`;
        prevPageBtn.disabled = true;
        nextPageBtn.disabled = true;
        return;
    }
    
    const pageItems = filteredLeads.slice(startIndex, endIndex);
    
    pageItems.forEach(lead => {
        const tr = document.createElement('tr');
        
        let scoreBadge = `<span class="badge badge-normal">0 (Normal)</span>`;
        if (lead.finalCategory === 'VIP') {
            scoreBadge = `<span class="badge badge-vip">+50 (VIP)</span>`;
        } else if (lead.finalCategory === 'Junk') {
            scoreBadge = `<span class="badge badge-junk">-50 (Junk)</span>`;
        }
        
        let statusBadge = `<span class="badge-status status-pending">Đang chờ duyệt</span>`;
        if (lead.status === 'Đã duyệt') {
            statusBadge = `<span class="badge-status status-approved">Đã duyệt</span>`;
        } else if (lead.status === 'Chưa đánh giá') {
            statusBadge = `<span class="badge-status" style="background: rgba(255,255,255,0.05); color: var(--text-dim);">Chưa chấm</span>`;
        }
        
        tr.innerHTML = `
            <td><strong>${lead.id}</strong></td>
            <td><strong>${lead.name}</strong></td>
            <td><code>${lead.phone || 'N/A'}</code></td>
            <td><div class="text-truncate" title="${lead.description}">${lead.description}</div></td>
            <td>${scoreBadge}</td>
            <td><div class="reason-cell" title="${lead.aiReason || ''}">${lead.aiReason || '—'}</div></td>
            <td>${statusBadge}</td>
            <td>
                <button class="btn btn-secondary btn-icon-only" onclick="openEditModal('${lead.id}')" title="Kiểm duyệt & Chỉnh sửa">
                    ✏️
                </button>
            </td>
        `;
        tableBody.appendChild(tr);
    });
    
    paginationInfo.textContent = `${startIndex + 1} - ${endIndex} trong ${filteredLeads.length}`;
    prevPageBtn.disabled = currentPage === 1;
    nextPageBtn.disabled = currentPage === totalPages;
}

// Open Human-in-the-loop Edit Modal
window.openEditModal = function(id) {
    const lead = leads.find(l => l.id === id);
    if (!lead) return;
    
    currentLeadEditing = lead;
    
    detailId.textContent = lead.id;
    detailName.textContent = lead.name;
    detailPhone.textContent = lead.phone || 'N/A';
    detailDesc.textContent = lead.description;
    
    let aiBadge = `Normal (0 điểm)`;
    if (lead.aiCategory === 'VIP') aiBadge = `VIP (+50 điểm)`;
    else if (lead.aiCategory === 'Junk') aiBadge = `Junk (-50 điểm)`;
    
    detailAiScore.textContent = aiBadge;
    detailAiReason.textContent = lead.aiReason || '—';
    
    // Set current override selection
    const scoreVal = lead.finalScore !== null ? lead.finalScore : (lead.aiScore || 0);
    const radioBtn = document.querySelector(`input[name="override-score"][value="${scoreVal}"]`);
    if (radioBtn) radioBtn.checked = true;
    
    overrideReason.value = lead.reviewedBy || '';
    
    editModal.classList.add('active');
};

function closeModal() {
    editModal.classList.remove('active');
    currentLeadEditing = null;
}

// Save Human Override Changes
function saveOverride() {
    if (!currentLeadEditing) return;
    
    const selectedRadio = document.querySelector('input[name="override-score"]:checked');
    if (!selectedRadio) {
        showToast('Vui lòng chọn một giá trị điểm để ghi đè!', 'error');
        return;
    }
    
    const newScore = parseInt(selectedRadio.value, 10);
    let newCategory = 'Normal';
    if (newScore === 50) newCategory = 'VIP';
    else if (newScore === -50) newCategory = 'Junk';
    
    currentLeadEditing.finalScore = newScore;
    currentLeadEditing.finalCategory = newCategory;
    currentLeadEditing.status = 'Đã duyệt';
    currentLeadEditing.reviewedBy = overrideReason.value.trim();
    
    closeModal();
    showToast(`Đã lưu thay đổi phê duyệt cho khách hàng ${currentLeadEditing.name}!`, 'success');
    applyFilters();
}

// Export Processed Data to Excel
function exportToExcel() {
    if (leads.length === 0) {
        showToast('Không có dữ liệu để xuất!', 'warning');
        return;
    }
    
    try {
        const exportData = leads.map(l => ({
            "Mã KH": l.id,
            "Tên Khách Hàng": l.name,
            "Số Điện Thoại": l.phone,
            "Nhu Cầu Chi Tiết": l.description,
            "Điểm Số AI": l.aiScore === null ? "—" : l.aiScore,
            "Phân Loại AI": l.aiCategory || "—",
            "Lý Do Chấm Điểm AI": l.aiReason,
            "Điểm Số Cuối Cùng": l.finalScore,
            "Phân Loại Cuối Cùng": l.finalCategory,
            "Trạng Thái Kiểm Duyệt": l.status,
            "Ghi Chú Phê Duyệt": l.reviewedBy || "—"
        }));
        
        const worksheet = XLSX.utils.json_to_sheet(exportData);
        
        // Beautiful column width adjustments
        const colWidths = [
            { wch: 8 },   // ID
            { wch: 20 },  // Name
            { wch: 15 },  // Phone
            { wch: 50 },  // Description
            { wch: 12 },  // AI Score
            { wch: 15 },  // AI Category
            { wch: 50 },  // AI Reason
            { wch: 18 },  // Final Score
            { wch: 18 },  // Final Category
            { wch: 22 },  // Status
            { wch: 25 }   // Notes
        ];
        worksheet['!cols'] = colWidths;
        
        const workbook = XLSX.utils.book_new();
        XLSX.utils.book_append_sheet(workbook, worksheet, "Lead Scoring Report");
        
        XLSX.writeFile(workbook, "Lead_Scoring_Automation_Report.xlsx");
        showToast('Xuất tệp Excel thành công!', 'success');
    } catch (err) {
        console.error(err);
        showToast(`Lỗi khi xuất Excel: ${err.message}`, 'error');
    }
}

// Notifications Helper
function showToast(message, type = 'success') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    
    toast.innerHTML = `
        <div class="toast-content">${message}</div>
        <button class="toast-close" onclick="this.parentElement.remove()">×</button>
    `;
    
    container.appendChild(toast);
    
    // Animate in
    setTimeout(() => toast.classList.add('show'), 10);
    
    // Auto dismiss
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}
