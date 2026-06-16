# HƯỚNG DẪN THỰC HÀNH (HANDS-ON GUIDELINES)
## Nâng cấp Hệ thống Lead Scoring & Automation trên Streamlit

Tài liệu này cung cấp hướng dẫn từng bước để bạn tự thực hành nâng cấp ứng dụng Web Streamlit (`streamlit_app.py`) của mình lên một phiên bản chuyên nghiệp, tích hợp thêm các tính năng nâng cao phục vụ cho thực tế doanh nghiệp.

---

## BÀI TẬP NÂNG CẤP 1: Tích hợp Động cơ Trí tuệ Nhân tạo (Gemini API)

**Mục tiêu:** Cho phép người dùng chuyển đổi giữa động cơ chấm điểm bằng quy tắc cứng (Regex) và chấm điểm thông minh bằng Mô hình Ngôn ngữ lớn (LLM - Gemini 1.5 Flash).

### Các bước thực hiện:
1. **Bổ sung thư viện:** Thêm `google-generativeai` vào `requirements.txt`.
2. **Cấu hình trên Giao diện (Sidebar):**
   Thêm ô nhập API Key và hộp lựa chọn động cơ vào sidebar:
   ```python
   api_key = st.sidebar.text_input("Gemini API Key (Nếu chọn động cơ AI):", type="password")
   engine_choice = st.sidebar.selectbox("Động cơ chấm điểm:", ["Quy tắc Regex (Local)", "Trí tuệ nhân tạo (Gemini AI)"])
   ```
3. **Viết hàm gọi Gemini API:**
   Sử dụng thư viện `google-generativeai` để gửi prompt chấm điểm:
   ```python
   import google.generativeai as genai
   import json

   def score_lead_with_gemini(description, api_key):
       try:
           genai.configure(api_key=api_key)
           model = genai.GenerativeModel('gemini-1.5-flash')
           
           prompt = f"""
           Bạn là chuyên gia thẩm định khách hàng bất động sản. Hãy đọc mô tả và trả về JSON:
           {{
             "score": <50 | 0 | -50>,
             "category": "<VIP | Normal | Junk>",
             "reason": "<lý do ngắn gọn bằng tiếng Việt>"
           }}
           
           Quy tắc:
           - VIP (+50): Mua shophouse/ biệt thự/ penthouse/ quỹ đất công nghiệp; tài chính >= 20 tỷ; khu vực đắc địa; mua sỉ; muốn đàm phán chủ đầu tư.
           - Junk (-50): Yêu cầu phi thực tế (Q1 nhà 1 tỷ), không nhu cầu, hỏi cho vui, spam, sai số điện thoại.
           - Normal (0): Các trường hợp trung cấp thông thường khác.
           
           Nội dung cần phân tích: "{description}"
           """
           
           response = model.generate_content(
               prompt,
               generation_config={"response_mime_type": "application/json"}
           )
           result = json.loads(response.text.strip())
           return result.get("score", 0), result.get("category", "Normal"), result.get("reason", "Chấm điểm bởi AI")
       except Exception as e:
           # Fallback sang regex nếu lỗi API
           return score_lead(description)
   ```

---

## BÀI TẬP NÂNG CẤP 2: Trực quan hóa dữ liệu bằng Biểu đồ (Charts)

**Mục tiêu:** Hiển thị biểu đồ phân bố khách hàng trực quan thay vì chỉ xem các khối số liệu thô.

### Các bước thực hiện:
1. Sử dụng tính năng vẽ biểu đồ mặc định của Streamlit (`st.bar_chart` hoặc `st.pyplot`).
2. Đoạn mã gợi ý vẽ biểu đồ tròn (Pie Chart) phân loại khách hàng bằng `matplotlib` hoặc biểu đồ cột mặc định:
   ```python
   st.markdown("### 📊 Biểu đồ Phân bổ Khách hàng")
   
   # Chuẩn bị dữ liệu vẽ biểu đồ
   category_counts = df["Phân loại kiểm duyệt"].value_counts().reset_index()
   category_counts.columns = ["Phân loại", "Số lượng"]
   
   # Vẽ biểu đồ cột trực tiếp trong Streamlit
   st.bar_chart(data=category_counts, x="Phân loại", y="Số lượng", color="Phân loại")
   ```

---

## BÀI TẬP NÂNG CẤP 3: Lưu trữ dữ liệu Kiểm duyệt (Persistence)

**Mục tiêu:** Khi nhấn tải lại trang (Refresh), các sửa đổi kiểm duyệt (Human-in-the-loop) sẽ không bị mất. Ta sẽ lưu dữ liệu kiểm duyệt vào một cơ sở dữ liệu SQLite cục bộ.

### Các bước thực hiện:
1. Khởi tạo kết nối SQLite khi ứng dụng chạy:
   ```python
   import sqlite3

   def init_db():
       conn = sqlite3.connect("leads_database.db")
       cursor = conn.cursor()
       cursor.execute('''
           CREATE TABLE IF NOT EXISTS lead_reviews (
               lead_id TEXT PRIMARY KEY,
               final_score INTEGER,
               final_category TEXT,
               review_status TEXT,
               review_notes TEXT
           )
       ''')
       conn.commit()
       conn.close()
   ```
2. Mỗi khi có thay đổi kiểm duyệt, lưu trực tiếp vào cơ sở dữ liệu:
   ```python
   def save_review_to_db(lead_id, score, category, notes):
       conn = sqlite3.connect("leads_database.db")
       cursor = conn.cursor()
       cursor.execute('''
           INSERT INTO lead_reviews (lead_id, final_score, final_category, review_status, review_notes)
           VALUES (?, ?, ?, 'Human Approved', ?)
           ON CONFLICT(lead_id) DO UPDATE SET
               final_score=excluded.final_score,
               final_category=excluded.final_category,
               review_status='Human Approved',
               review_notes=excluded.review_notes
       ''', (lead_id, score, category, notes))
       conn.commit()
       conn.close()
   ```
3. Khi tải dữ liệu mới từ Google Sheets, tiến hành `LEFT JOIN` hoặc kết hợp với dữ liệu đã lưu trong bảng `lead_reviews` để điền trước các kết quả đã được con người duyệt trước đó.

---

## BÀI TẬP NÂNG CẤP 4: Triển khai dự án lên Internet (Deploy Streamlit Cloud)

**Mục tiêu:** Đưa ứng dụng của bạn lên mạng trực tuyến để giảng viên và đồng nghiệp có thể dùng thử.

### Các bước thực hiện:
1. **Đưa toàn bộ code lên GitHub:** (Bước này đã được Antigravity thực hiện giúp bạn).
2. **Đăng nhập vào Streamlit Community Cloud:**
   - Truy cập **[share.streamlit.io](https://share.streamlit.io)**.
   - Chọn "Sign in with GitHub" và cấp quyền liên kết.
3. **Deploy Ứng dụng:**
   - Nhấn nút **"New app"**.
   - Chọn Repository: `huydt1407/ai-lead-scoring-real-estate`.
   - Chọn Branch: `main`.
   - Chọn Main file path: `streamlit_app.py`.
   - Nhấn nút **"Deploy!"**.
4. Chờ ứng dụng cài đặt các thư viện trong `requirements.txt`. Hệ thống sẽ cung cấp cho bạn một đường dẫn URL công khai (dạng: `https://[app-name].streamlit.app/`).
