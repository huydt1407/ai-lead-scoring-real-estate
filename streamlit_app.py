import io
import re
import os
import pandas as pd
import requests
import streamlit as st
from streamlit_gsheets import GSheetsConnection

# Cấu hình giao diện Streamlit
st.set_page_config(
    page_title="AI Lead Scoring Dashboard",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# -------------------------------------------------------------
# CẤU HÌNH LOGIC NGHIỆP VỤ CHẤM ĐIỂM
# -------------------------------------------------------------
def score_lead(description):
    """
    Hàm tự động chấm điểm khách hàng tiềm năng dựa trên mô tả nhu cầu
    (Áp dụng theo quy chuẩn nghiệp vụ trong tieu_chi_cham_diem.txt / lead_scoring_skill.md)
    """
    if not isinstance(description, str) or not description.strip():
        return 0, "Normal", "Dữ liệu trống hoặc không đúng định dạng."
        
    text = description.lower()
    
    # 1. TIÊU CHÍ TRỪ 50 ĐIỂM (JUNK)
    junk_keywords = [
        "nhầm số", "không có nhu cầu", "dữ liệu cũ", "nhầm ngành",
        "hỏi giá cho vui", "chưa có ý định mua", "thái độ không hợp tác",
        "bảo hiểm", "vay vốn", "mời chào", "quảng cáo ngược",
        "thuê bao", "gọi nhiều lần không bắt máy", "không phản hồi zalo",
        "nhầm máy", "gọi nhiều lần không nhấc", "gọi nhiều lần không nghe"
    ]
    
    unrealistic_patterns = [
        r"nhà thuê nguyên căn giá 2 triệu",
        r"thuê nguyên căn giá 2 triệu",
        r"nhà thuê.*2 triệu.*trung tâm",
        r"đòi mua nhà (?:q1|quận 1) giá 1 tỷ",
        r"mua nhà (?:q1|quận 1) giá 1 tỷ",
        r"nhà q1 giá 1 tỷ",
        r"yêu cầu phi thực tế"
    ]
    
    for kw in junk_keywords:
        if kw in text:
            return -50, "Junk", f"Trừ 50 điểm: Phát hiện dấu hiệu rác / không có nhu cầu (từ khóa: '{kw}')"
            
    for pattern in unrealistic_patterns:
        if re.search(pattern, text):
            return -50, "Junk", f"Trừ 50 điểm: Yêu cầu phi thực tế hoặc không thiện chí (khớp: '{pattern}')"

    # 2. TIÊU CHÍ CỘNG 50 ĐIỂM (VIP)
    vip_keywords = [
        "tài chính mạnh", "không thành vấn đề", "tài chính cực mạnh", "thanh toán thẳng", "ngân sách lớn", "mua sỉ", "mua số lượng lớn", "gom sỉ",
        "biệt thự đơn lập", "penthouse", "shophouse mặt đường lớn", "quỹ đất công nghiệp", "sàn văn phòng diện tích lớn",
        "quận 1", "ven sông", "vinhomes ocean park", "phú mỹ hưng",
        "chủ doanh nghiệp", "nhà đầu tư chuyên nghiệp",
        "pháp lý chuẩn", "sổ hồng riêng", "gặp trực tiếp chủ đầu tư", "gặp trực tiếp giám đốc"
    ]
    
    vip_matched = []
    
    budget_match = re.search(r"(\d+)\s*tỷ", text)
    if budget_match:
        budget_val = int(budget_match.group(1))
        if budget_val >= 20:
            vip_matched.append(f"ngân sách {budget_val} tỷ (>= 20 tỷ)")
            
    for kw in vip_keywords:
        if kw in text:
            vip_matched.append(f"từ khóa: '{kw}'")
            
    if vip_matched:
        reason = "Cộng 50 điểm: Khách hàng VIP / Siêu tiềm năng (Phát hiện " + ", ".join(vip_matched[:2]) + ")"
        return 50, "VIP", reason

    # 3. TIÊU CHÍ GIỮ NGUYÊN 0 ĐIỂM (NORMAL)
    return 0, "Normal", "Giữ nguyên 0 điểm: Khách hàng tìm mua phân khúc trung cấp (chung cư, nhà phố 3-10 tỷ), cần tư vấn thêm."

# -------------------------------------------------------------
# GIAO DIỆN CHÍNH (STREAMLIT APP)
# -------------------------------------------------------------
# Tiêm CSS tùy chỉnh cho ứng dụng
st.markdown("""
<style>
.stMetric {
    background-color: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.1);
    padding: 15px;
    border-radius: 10px;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
}
div[data-testid="metric-container"] {
    text-align: center;
}
</style>
""", unsafe_allow_html=True)

# Hiển thị Logo & Banner trên đầu trang chủ
col_logo, col_title = st.columns([1, 5])
with col_logo:
    if os.path.exists("logo.png"):
        st.image("logo.png", width=120)
with col_title:
    st.title("⚡ AI Lead Scoring & Automation System")
    st.markdown("Hệ thống Đánh giá & Phân loại Khách hàng Tiềm năng Bất động sản (Human-in-the-loop)")

st.divider()

# Sidebar Cấu hình
st.sidebar.header("⚙️ Cấu hình Tích hợp")
if os.path.exists("logo.png"):
    st.sidebar.image("logo.png", use_container_width=True)
st.sidebar.markdown("---")
sheet_url = st.sidebar.text_input(
    "Đường dẫn Google Sheets (CSV Export):",
    "https://docs.google.com/spreadsheets/d/16tCAf_qqtgYZxoumYQKMEOdBhKE0wg5A/edit?gid=1542775777#gid=1542775777"
)

# Chuyển đổi link Sheets sang CSV export
export_url = sheet_url
if "/edit" in sheet_url:
    sheet_id_match = re.search(r"/d/([a-zA-Z0-9-_]+)", sheet_url)
    if sheet_id_match:
        sheet_id = sheet_id_match.group(1)
        gid = "0"
        gid_match = re.search(r"gid=(\d+)", sheet_url)
        if gid_match:
            gid = gid_match.group(1)
        export_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"

load_btn = st.sidebar.button("🔄 Tải và Chấm điểm Leads", type="primary")

# Quản lý state dữ liệu trong Streamlit
if "df_leads" not in st.session_state:
    st.session_state.df_leads = None

if load_btn:
    with st.spinner("Đang tải dữ liệu từ Google Sheets và chạy chấm điểm tự động..."):
        try:
            # Kết nối bảo mật sử dụng st-gsheets-connection
            conn = st.connection("gsheets", type=GSheetsConnection)
            df = conn.read(spreadsheet=sheet_url, ttl="10m")
            
            # Kiểm tra định dạng cột
            required_cols = ["id", "ten_khach", "sdt", "nhu_cau_mo_ta"]
            for col in required_cols:
                if col not in df.columns:
                    st.error(f"Thiếu cột bắt buộc '{col}' trong file Google Sheets.")
                    st.stop()
                    
            # Chạy chấm điểm tự động
            scores = []
            categories = []
            reasons = []
            for desc in df["nhu_cau_mo_ta"]:
                score, category, reason = score_lead(desc)
                scores.append(score)
                categories.append(category)
                reasons.append(reason)
                
            # Tạo các cột cho bản báo cáo và kiểm duyệt
            df["Điểm số AI"] = scores
            df["Phân loại AI"] = categories
            df["Lý do chấm điểm"] = reasons
            
            # Cột cho con người kiểm duyệt (Human-in-the-loop)
            df["Điểm số kiểm duyệt"] = scores
            df["Phân loại kiểm duyệt"] = categories
            df["Trạng thái duyệt"] = "AI Evaluated"
            df["Ghi chú duyệt"] = ""
            
            st.session_state.df_leads = df
            st.success(f"Tải thành công {len(df)} khách hàng và hoàn tất chấm điểm!")
        except Exception as e:
            st.error(f"Lỗi tải dữ liệu: {e}")

# Hiển thị dữ liệu và bảng điều khiển
df = st.session_state.df_leads

if df is not None:
    # 1. Thống kê KPI Cards
    total_leads = len(df)
    
    # Tính số lượng dựa trên cột kiểm duyệt (nếu có cập nhật từ người dùng)
    vip_count = (df["Phan_loai_AI"] if "Phân loại kiểm duyệt" not in df.columns else df["Phân loại kiểm duyệt"]).value_counts().get("VIP", 0)
    normal_count = (df["Phan_loai_AI"] if "Phân loại kiểm duyệt" not in df.columns else df["Phân loại kiểm duyệt"]).value_counts().get("Normal", 0)
    junk_count = (df["Phan_loai_AI"] if "Phân loại kiểm duyệt" not in df.columns else df["Phân loại kiểm duyệt"]).value_counts().get("Junk", 0)
    
    # Dùng st.columns(3) kết hợp st.metric để hiển thị: Tổng khách hàng, Khách VIP, Khách Rác
    col1, col2, col3 = st.columns(3)
    col1.metric("🏠 Tổng khách hàng BĐS", total_leads)
    col2.metric("🏆 Khách VIP (+50đ)", vip_count)
    col3.metric("🗑️ Khách Rác (-50đ)", junk_count)
    
    # 2. Trực quan hóa dữ liệu bằng Biểu đồ (Charts)
    st.markdown("### 📊 Trực quan hóa Dữ liệu")
    chart_col1, chart_col2 = st.columns(2)
    
    with chart_col1:
        cat_counts = pd.Series({"VIP (+50)": vip_count, "Thường (0)": normal_count, "Rác (-50)": junk_count})
        st.bar_chart(cat_counts, color="#38bdf8")
        st.caption("Số lượng khách hàng theo Phân loại kiểm duyệt")
        
    with chart_col2:
        status_counts = df["Trạng thái duyệt"].value_counts()
        st.bar_chart(status_counts, color="#34d399")
        st.caption("Trạng thái xử lý hệ thống (AI Evaluated vs Human Approved)")

    # 3. Bộ lọc tìm kiếm nâng cao
    st.markdown("### 🔍 Bộ lọc danh sách nâng cao")
    f_col1, f_col2, f_col3, f_col4 = st.columns(4)
    search_q = f_col1.text_input("Tìm kiếm theo tên, SĐT hoặc mô tả nhu cầu:")
    category_filter = f_col2.selectbox(
        "Lọc nhóm khách hàng (Kiểm duyệt):",
        ["Tất cả", "VIP", "Normal", "Junk"]
    )
    status_filter = f_col3.selectbox(
        "Lọc theo trạng thái duyệt:",
        ["Tất cả", "AI Evaluated (Chờ duyệt)", "Human Approved (Đã duyệt)"]
    )
    phone_filter = f_col4.selectbox(
        "Lọc theo thông tin liên hệ:",
        ["Tất cả", "Có số điện thoại", "Không có số điện thoại"]
    )
    
    # Áp dụng bộ lọc
    filtered_df = df.copy()
    if search_q:
        search_q = search_q.lower()
        mask = (
            filtered_df["ten_khach"].astype(str).str.lower().str.contains(search_q) |
            filtered_df["sdt"].astype(str).str.contains(search_q) |
            filtered_df["nhu_cau_mo_ta"].astype(str).str.lower().str.contains(search_q)
        )
        filtered_df = filtered_df[mask]
        
    if category_filter != "Tất cả":
        filtered_df = filtered_df[filtered_df["Phân loại kiểm duyệt"] == category_filter]
        
    if status_filter != "Tất cả":
        if "AI Evaluated" in status_filter:
            filtered_df = filtered_df[filtered_df["Trạng thái duyệt"] == "AI Evaluated"]
        else:
            filtered_df = filtered_df[filtered_df["Trạng thái duyệt"] == "Human Approved"]
            
    if phone_filter == "Có số điện thoại":
        filtered_df = filtered_df[filtered_df["sdt"].notna() & (filtered_df["sdt"].astype(str).str.strip() != "")]
    elif phone_filter == "Không có số điện thoại":
        filtered_df = filtered_df[filtered_df["sdt"].isna() | (filtered_df["sdt"].astype(str).str.strip() == "")]
        
    st.markdown("### ✏️ Bảng danh sách & Kiểm duyệt trực tiếp (Human-in-the-loop)")
    st.info("💡 Bạn có thể nhấp đúp trực tiếp vào ô trong các cột 'Điểm số kiểm duyệt', 'Phân loại kiểm duyệt', hoặc 'Ghi chú duyệt' để chỉnh sửa kết quả, sau đó tải về file Excel đã cập nhật.")
    
    # Cấu hình kiểu dữ liệu cột trong st.data_editor
    edited_df = st.data_editor(
        filtered_df,
        column_config={
            "id": st.column_config.TextColumn("Mã KH", disabled=True),
            "ten_khach": st.column_config.TextColumn("Tên Khách", disabled=True),
            "sdt": st.column_config.TextColumn("Số Điện Thoại", disabled=True),
            "nhu_cau_mo_ta": st.column_config.TextColumn("Mô Tả Nhu Cầu", disabled=True, width="medium"),
            "Điểm số AI": st.column_config.NumberColumn("Điểm AI", disabled=True),
            "Phân loại AI": st.column_config.TextColumn("Phân Loại AI", disabled=True),
            "Lý do chấm điểm": st.column_config.TextColumn("Lý Do AI", disabled=True, width="medium"),
            
            # Cột có thể sửa đổi (Human-in-the-loop)
            "Điểm số kiểm duyệt": st.column_config.SelectboxColumn(
                "Điểm duyệt",
                options=[50, 0, -50],
                required=True
            ),
            "Phân loại kiểm duyệt": st.column_config.SelectboxColumn(
                "Phân loại duyệt",
                options=["VIP", "Normal", "Junk"],
                required=True
            ),
            "Trạng thái duyệt": st.column_config.SelectboxColumn(
                "Trạng thái",
                options=["AI Evaluated", "Human Approved"],
                required=True
            ),
            "Ghi chú duyệt": st.column_config.TextColumn(
                "Ghi chú / Nhân viên duyệt",
                width="medium"
            )
        },
        hide_index=True,
        use_container_width=True
    )
    
    # Đồng bộ các thay đổi vào session state chính
    if not edited_df.equals(filtered_df):
        for index, row in edited_df.iterrows():
            lead_id = row["id"]
            # Tìm dòng tương ứng trong df chính bằng ID
            idx_in_main = df[df["id"] == lead_id].index
            if len(idx_in_main) > 0:
                main_idx = idx_in_main[0]
                df.at[main_idx, "Điểm số kiểm duyệt"] = row["Điểm số kiểm duyệt"]
                df.at[main_idx, "Phân loại kiểm duyệt"] = row["Phân loại kiểm duyệt"]
                df.at[main_idx, "Ghi chú duyệt"] = row["Ghi chú duyệt"]
                # Tự động chuyển trạng thái nếu điểm kiểm duyệt khác điểm AI hoặc có ghi chú
                if (row["Điểm số kiểm duyệt"] != row["Điểm số AI"] or row["Ghi chú duyệt"] != ""):
                    df.at[main_idx, "Trạng thái duyệt"] = "Human Approved"
                else:
                    df.at[main_idx, "Trạng thái duyệt"] = row["Trạng thái duyệt"]
        st.session_state.df_leads = df
        st.rerun()
        
    # 3. Xuất file Excel đã kiểm duyệt
    st.markdown("### 📥 Xuất báo cáo bàn giao")
    
    # Tạo buffer trong bộ nhớ để ghi Excel bằng openpyxl
    excel_buffer = io.BytesIO()
    with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name="Báo cáo Lead Scoring")
        # Format chiều rộng cột
        workbook = writer.book
        worksheet = writer.sheets["Báo cáo Lead Scoring"]
        for col in worksheet.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            col_letter = col[0].column_letter
            worksheet.column_dimensions[col_letter].width = min(max(max_len + 3, 10), 60)
            
    excel_data = excel_buffer.getvalue()
    
    st.download_button(
        label="📥 Tải xuống báo cáo Excel (.xlsx)",
        data=excel_data,
        file_name="Lead_Scoring_Streamlit_Report.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary"
    )

else:
    # Giao diện chào đón khi chưa có dữ liệu
    st.info("👋 Chào mừng bạn! Vui lòng nhấn nút 'Tải và Chấm điểm Leads' ở thanh bên trái để bắt đầu phân tích dữ liệu khách hàng.")
    
    # Trình bày một số ví dụ quy tắc chấm điểm
    with st.expander("📝 Tham khảo Bộ tiêu chí chấm điểm"):
        st.markdown("""
        - **Nhóm VIP (+50 điểm):** Ngân sách >= 20 tỷ, mua shophouse/ biệt thự/ penthouse/ quỹ đất công nghiệp, thuộc khu vực đắc địa (Q1, Phú Mỹ Hưng...), chủ doanh nghiệp hoặc nhà đầu tư sỉ.
        - **Nhóm Rác (-50 điểm):** Yêu cầu phi thực tế (Q1 nhà 1 tỷ, thuê nhà 2 triệu trung tâm), nhầm số, hỏi giá cho vui, bảo hiểm/vay vốn spam, số thuê bao không liên lạc được.
        - **Nhóm Thường (0 điểm):** Chung cư, nhà phố tầm trung (3-10 tỷ), cần tư vấn thêm, cần vay ngân hàng.
        """)

# -------------------------------------------------------------
# BẢNG TỔNG KẾT KIỂM TRA (AUDIT) - LUÔN HIỂN THỊ DƯỚI CÙNG
# -------------------------------------------------------------
st.divider()
st.markdown("### 📋 Bảng Tổng kết Kiểm tra (Audit)")
st.caption("Bảng tự đánh giá thành phần kỹ năng hệ thống (Audit Checklist)")

audit_data = {
    "Thành tố": [
        "1. Input", 
        "2. Agent", 
        "3. Tools", 
        "4. Knowledge", 
        "5. Memory", 
        "6. Workflow", 
        "7. Output"
    ],
    "Tên File/Công cụ": [
        "Google Sheets", 
        "Logic chấm điểm", 
        "Streamlit, Pandas, GitHub", 
        "tieu_chi_cham_diem.txt", 
        "st.session_state", 
        "AI ➔ Người duyệt ➔ Excel", 
        "File Excel Bàn Giao"
    ],
    "Mô tả": [
        "500 khách hàng BĐS 🏠 / Spa 💄", 
        "Tự động quét mô tả nhu cầu", 
        "Nền tảng xây dựng hệ thống", 
        "Quy tắc cộng 50đ / trừ 50đ", 
        "Ghi nhớ trạng thái phiên làm việc", 
        "Human Checkpoint (Kiểm duyệt)", 
        "Dữ liệu sạch cho bộ phận Sales"
    ]
}
df_audit = pd.DataFrame(audit_data)
st.table(df_audit)

st.success("✅ Hoàn thành đủ 7 thành tố = Vượt qua Buổi 7!")
