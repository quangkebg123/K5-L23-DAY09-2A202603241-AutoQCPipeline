# Báo cáo Day 09 — Nguyen Manh Quang, 2A202603241

> Mỗi ý trả lời bằng **số lấy từ `submission/reports/`**, kèm mẫu số. Cả báo cáo ~1–2 trang.

## 1. Kết luận trước

Pipeline kết luận **Release**: intake nhận 203/224 ảnh và loại 21 ảnh lỗi/kích thước nhỏ/trùng/rò rỉ. Sau mô phỏng duyệt 80 ảnh, không còn lỗi bắt buộc; còn cảnh báo chưa duyệt ở 16/203 ảnh (7.88%), thấp hơn ngưỡng Hold 10%. Dataset xuất có 203 ảnh.

## 2. Lỗi và phân việc

Lấy từ `02_error_list_v1` (gom theo mã lỗi). Cột "ai sửa": **máy** (autofix) hay **người** (hàng đợi); chỉ ghi những mã có mặt trong lô của bạn.

| Mã lỗi                                                                                    |        Số ảnh/dòng | Ai sửa (máy/người) | Vì sao                                                                      |
| ----------------------------------------------------------------------------------------- | -----------------: | ------------------ | --------------------------------------------------------------------------- |
| `BAD_SIZE`; `CORRUPT_IMAGE`; `DUP_IMAGE_EXACT`; `DUP_IMAGE_NEAR`; `LEAK_TEST`             | 3; 2; 8; 3; 5 (21) | Máy                | Intake loại ảnh nhỏ/hỏng, trùng và trùng với test/val.                      |
| `BAD_CLASS_ID`; `BAD_CLASS_NAME`; `BAD_FORMAT`; `BOX_OUT_OF_IMAGE`; `BOX_ZERO`; `DUP_BOX` |   6; 2; 3; 8; 4; 7 | Máy                | Autofix xóa dòng/box lỗi, clip box tràn và chuẩn hóa tên lớp.               |
| `MISSING_LABEL_FILE`                                                                      |                  6 | Người              | Ảnh không có file nhãn cần người gán; được đưa vào `NEEDS_LABEL`.           |
| `POSSIBLE_FALSE_POS`; `POSSIBLE_LOOSE_BOX`; `POSSIBLE_MISSING`; `POSSIBLE_WRONG_CLASS`    |     29; 12; 32; 14 | Người              | Đây là cảnh báo ngữ nghĩa từ model phụ, cần người kiểm tra ảnh.             |
| `BOX_HUGE`; `BOX_TINY`; `CLASS_RARE`; `EMPTY_LABEL`                                       |        3; 6; 4; 12 | Người/đối chiếu    | Cảnh báo thống kê hoặc box cần xem ngữ cảnh; một số vẫn còn sau lượt duyệt. |

`05_review_queue.csv` có 102 ảnh. Ảnh đầu `img_0020` có priority 11.524 vì cùng lúc có `FIXED_DROP_LINE`, `POSSIBLE_MISSING` và `POSSIBLE_WRONG_CLASS`, nên trọng số ưu tiên được cộng dồn. Với ngân sách 80 ảnh, mô phỏng duyệt 80 ảnh; 68/80 ảnh có ít nhất một cảnh báo ngữ nghĩa. Trong 80 ảnh đó có 32 cờ `POSSIBLE_MISSING`, 19 `POSSIBLE_FALSE_POS`, 14 `POSSIBLE_WRONG_CLASS` và 12 `POSSIBLE_LOOSE_BOX` (một ảnh có thể có nhiều mã).

## 3. Calibration (2 ngưỡng)

Precision/recall trong bảng được đo trên bộ calib 39 ảnh; quyết định Release được kiểm tra riêng bằng cách chạy pipeline trên raw.

| Tham số                 | Khởi đầu | Đã chọn | Precision / Recall (trước → sau)                                                                                         | Lý do (đánh đổi)                                                                                                                      |
| ----------------------- | -------- | ------- | ------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------- |
| `duplicates.phash_dist` | 2        | 6       | exact 1.00/1.00 → 1.00/1.00; near 1.00/0.50 → 1.00/0.67                                                                  | Giữ precision 1.00 và tăng recall near lên 0.67; pHash 16 bắt được nhiều hơn trên calib nhưng gây báo trùng nhầm trên raw.            |
| `second_opinion.conf`   | 0.25     | 0.8     | wrong 0.56/0.83 → 1.00/0.83; missing 0.50/1.00 → 0.67/0.75; loose 0.29/0.40 → 0.50/0.20; false-pos 0.31/1.00 → 0.31/1.00 | 0.8 là mức thấp nhất trong sweep đạt Release trên raw với pHash 6; đổi lại recall missing giảm 1.00→0.75 và loose-box giảm 0.40→0.20. |

Điểm mù calibration: bộ calib chỉ có 39 ảnh và không có lỗi `LEAK_TEST`. Ở ngưỡng pHash 16, raw báo nhầm cặp `img_0061`/`img_0186` (distance 10) và `img_0008`/`img_0011` (distance 16), là hai cảnh khác nhau; vì vậy giữ 6 để tránh gộp nhầm ảnh tốt dù recall near trên calib là 0.67 thay vì 0.83. Với `phash_dist=6`, thử raw cho thấy `conf=0.4` còn cảnh báo 50/203 ảnh (24.63%), `0.5` còn 44/203 (21.67%), `0.6` còn 38/203 (18.72%), `0.7` còn 29/203 (14.29%) — đều Hold; `0.8` còn 16/203 (7.88%) sau mô phỏng duyệt 80 ảnh nên gate Release. Tuy nhiên, conf cao làm recall missing giảm 1.00→0.75 và loose-box giảm 0.40→0.20 trên calib; Release là kết quả gate mô phỏng, không chứng minh nhãn đã hết lỗi.

## 4. Cửa chặn và điều pipeline KHÔNG bắt được

Đối chứng gate với ngân sách 0 (chạy trong thư mục tạm): intake nhận 203/224 ảnh; không có lượt duyệt, còn 6 lỗi bắt buộc và cảnh báo trên 85/203 ảnh (41.87%). Kết luận **Rework**, mã thoát 20, và không tạo export. Đây cho thấy thiếu nhãn không được biến thành Release khi chưa có người gán.

Điểm mù ghi nhận khi xem ảnh: (1) `img_001.png` thiếu nhãn cho person; (2) `img_001.png`, id 2, person bị che hơn 80% nhưng không được gán nhãn; (3) `img_0030.png`, id 11, person bị gán sai lớp. Những trường hợp bị bỏ sót hoặc gán nhầm ngữ nghĩa vẫn cần người xem ảnh.

## 5. Train: raw vs clean (tùy chọn, chấm riêng)

Hai biến thể dùng cùng mô hình `yolo26n.pt`, 20 epoch, batch 16 và kích thước ảnh 640; mỗi biến thể chạy trên 2 seed (0 và 1). Tập `raw` có 224 ảnh train; tập `clean` sau intake có 203 ảnh train.

| Biến thể             | Số ảnh | Seed |           mAP50 |        mAP50-95 |       Precision |          Recall |
| -------------------- | -----: | ---: | --------------: | --------------: | --------------: | --------------: |
| raw                  |    224 |    0 |          0.7256 |          0.5144 |          0.8068 |          0.6291 |
| raw                  |    224 |    1 |          0.7259 |          0.5090 |          0.7203 |          0.6689 |
| clean                |    203 |    0 |          0.6962 |          0.4904 |          0.8319 |          0.5557 |
| clean                |    203 |    1 |          0.7173 |          0.5015 |          0.7443 |          0.6352 |
| raw (TB ± độ lệch)   |    224 |    2 | 0.7258 ± 0.0002 | 0.5117 ± 0.0038 | 0.7635 ± 0.0612 | 0.6490 ± 0.0281 |
| clean (TB ± độ lệch) |    203 |    2 | 0.7067 ± 0.0149 | 0.4960 ± 0.0078 | 0.7881 ± 0.0619 | 0.5955 ± 0.0562 |

Kết luận thí nghiệm: **raw tốt hơn ở các chỉ số phát hiện tổng thể trong thử nghiệm này**, vì có mAP50 và mAP50-95 cao hơn đồng thời recall cao hơn. Tuy nhiên, `clean` có precision cao hơn và chỉ có 203 ảnh train sau khi loại 21 ảnh. Vì thí nghiệm chỉ lặp 2 seed và độ lệch clean–raw tương đối nhỏ ở recall/mAP, kết quả chưa đủ mạnh để khẳng định một tập luôn tốt hơn tập kia. Cần thêm seed hoặc nhiều lần huấn luyện trước khi chốt quyết định cuối.

## 6. Quyết định và ghi chú AI

Quyết định: **Release theo gate sau mô phỏng duyệt 80 ảnh**, còn 16/203 ảnh có cảnh báo chưa duyệt; cần người phụ trách kiểm tra trước khi phát hành thật.

- Có dùng AI: yêu cầu triển khai bốn module theo docstring và các test có sẵn.
- Kiểm tra: chạy pytest (79 test passed), calibration sweep và pipeline trên raw; kết quả gate được đối chiếu với `08_summary.json`.
- Lần AI sai: ban đầu đưa cả class ID vào phép tính IoU của box nhãn; test phát hiện lỗi và cách tính được sửa để chỉ dùng tọa độ box.

_(Thưởng +2, tùy chọn)_ CVAT: lọc `width < 20`, ảnh/số box khớp, đối chiếu `BOX_TINY` (xem docs/CVAT_FILTER.md), 1 câu về `can_review`.
