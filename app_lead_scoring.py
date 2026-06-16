import os
import re
import sys
import io
import pandas as pd
import requests

# Set UTF-8 encoding for standard output on Windows
if sys.platform.startswith('win'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Link Google Sheet (dạng xuất CSV trực tiếp)
SHEET_URL = "https://docs.google.com/spreadsheets/d/16tCAf_qqtgYZxoumYQKMEOdBhKE0wg5A/export?format=csv&gid=1542775777"
OUTPUT_FILE = "Lead_Scoring_Output.xlsx"

def score_lead(description):
    """
    Hàm tự động chấm điểm khách hàng tiềm năng dựa trên mô tả nhu cầu
    (Áp dụng theo quy chuẩn nghiệp vụ trong file tieu_chi_cham_diem.txt / lead_scoring_skill.md)
    """
    if not isinstance(description, str):
        return 0, "Normal", "Dữ liệu trống hoặc không đúng định dạng."
        
    text = description.lower()
    
    # -------------------------------------------------------------
    # 1. TIÊU CHÍ TRỪ 50 ĐIỂM (KHÁCH HÀNG RÁC / KHÔNG TIỀM NĂNG - JUNK)
    # -------------------------------------------------------------
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
    
    # Kiểm tra từ khóa Junk
    for kw in junk_keywords:
        if kw in text:
            return -50, "Junk", f"Trừ 50 điểm: Phát hiện dấu hiệu rác / không có nhu cầu (từ khóa: '{kw}')"
            
    # Kiểm tra regex Junk
    for pattern in unrealistic_patterns:
        if re.search(pattern, text):
            return -50, "Junk", f"Trừ 50 điểm: Yêu cầu phi thực tế hoặc không thiện chí (khớp: '{pattern}')"

    # -------------------------------------------------------------
    # 2. TIÊU CHÍ CỘNG 50 ĐIỂM (KHÁCH HÀNG VIP / SIÊU TIỀM NĂNG - VIP)
    # -------------------------------------------------------------
    vip_keywords = [
        "tài chính mạnh", "không thành vấn đề", "tài chính cực mạnh", "thanh toán thẳng", "ngân sách lớn", "mua sỉ", "mua số lượng lớn", "gom sỉ",
        "biệt thự đơn lập", "penthouse", "shophouse mặt đường lớn", "quỹ đất công nghiệp", "sàn văn phòng diện tích lớn",
        "quận 1", "ven sông", "vinhomes ocean park", "phú mỹ hưng",
        "chủ doanh nghiệp", "nhà đầu tư chuyên nghiệp",
        "pháp lý chuẩn", "sổ hồng riêng", "gặp trực tiếp chủ đầu tư", "gặp trực tiếp giám đốc"
    ]
    
    vip_matched = []
    
    # Kiểm tra ngân sách bằng số cụ thể từ 20 tỷ trở lên
    budget_match = re.search(r"(\d+)\s*tỷ", text)
    if budget_match:
        budget_val = int(budget_match.group(1))
        if budget_val >= 20:
            vip_matched.append(f"ngân sách {budget_val} tỷ (>= 20 tỷ)")
            
    # Kiểm tra từ khóa VIP
    for kw in vip_keywords:
        if kw in text:
            vip_matched.append(f"từ khóa: '{kw}'")
            
    if vip_matched:
        reason = "Cộng 50 điểm: Khách hàng VIP / Siêu tiềm năng (Phát hiện " + ", ".join(vip_matched[:2]) + ")"
        return 50, "VIP", reason

    # -------------------------------------------------------------
    # 3. TIÊU CHÍ GIỮ NGUYÊN 0 ĐIỂM (KHÁCH HÀNG THƯỜNG - NORMAL)
    # -------------------------------------------------------------
    return 0, "Normal", "Giữ nguyên 0 điểm: Khách hàng tìm mua phân khúc trung cấp (chung cư, nhà phố 3-10 tỷ), cần tư vấn thêm."

def main():
    print("=== HỆ THỐNG TỰ ĐỘNG CHẤM ĐIỂM KHÁCH HÀNG TIỀM NĂNG ===")
    print(f"Đang kết nối tải dữ liệu từ Google Sheets...")
    
    try:
        # Tải dữ liệu CSV từ Google Sheets và đọc trực tiếp
        response = requests.get(SHEET_URL)
        response.raise_for_status()
        
        # Đọc dữ liệu trực tiếp bằng StringIO và giải mã UTF-8
        csv_data = response.content.decode('utf-8')
        df = pd.read_csv(io.StringIO(csv_data))
            
        print(f"Đã tải thành công {len(df)} dòng dữ liệu từ Google Sheets.")
        
        # Đảm bảo các cột cần thiết tồn tại
        required_cols = ["ten_khach", "nhu_cau_mo_ta"]
        for col in required_cols:
            if col not in df.columns:
                raise ValueError(f"Bảng dữ liệu thiếu cột bắt buộc: '{col}'")
                
        # Thực hiện chấm điểm
        print("Đang tiến hành phân tích và chấm điểm tự động...")
        scores = []
        categories = []
        reasons = []
        
        for desc in df["nhu_cau_mo_ta"]:
            score, category, reason = score_lead(desc)
            scores.append(score)
            categories.append(category)
            reasons.append(reason)
            
        df["Diem_So_AI"] = scores
        df["Phan_Loai_AI"] = categories
        df["Ly_Do_AI"] = reasons
        
        # Lưu kết quả ra Excel
        print(f"Đang xuất kết quả ra file Excel '{OUTPUT_FILE}'...")
        
        # Tạo writer với openpyxl để tạo định dạng đẹp
        with pd.ExcelWriter(OUTPUT_FILE, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name="Báo cáo Lead Scoring")
            
            # Tự động căn chỉnh độ rộng của các cột trong Excel
            workbook = writer.book
            worksheet = writer.sheets["Báo cáo Lead Scoring"]
            for col in worksheet.columns:
                max_len = max(len(str(cell.value or '')) for cell in col)
                col_letter = col[0].column_letter
                worksheet.column_dimensions[col_letter].width = min(max(max_len + 3, 10), 60)
                
        # Thống kê kết quả
        total = len(df)
        vip_count = categories.count("VIP")
        normal_count = categories.count("Normal")
        junk_count = categories.count("Junk")
        
        print("\n=== KẾT QUẢ THỐNG KÊ ===")
        print(f"- Tổng số khách hàng: {total}")
        print(f"- Khách hàng VIP (+50): {vip_count} ({vip_count/total*100:.1f}%)")
        print(f"- Khách hàng Thường (0): {normal_count} ({normal_count/total*100:.1f}%)")
        print(f"- Khách hàng Rác (-50): {junk_count} ({junk_count/total*100:.1f}%)")
        print("=========================")
        print(f"File kết quả đã hoàn thành: {os.path.abspath(OUTPUT_FILE)}")
        
    except Exception as e:
        print(f"\n[LỖI] Đã xảy ra lỗi trong quá trình xử lý: {e}")

if __name__ == "__main__":
    main()
