"""BƯỚC 4 — Cửa chặn: quyết định Release / Hold / Rework.   ★

Test:  pytest tests/test_gate.py -q

Cây quyết định Day 07 (slide Day 09: "Lỗi bắt buộc chặn pipeline; lỗi cảnh báo chuyển người xem"):

  còn ≥ 1 lỗi bắt buộc (severity ERROR)                          -> "Rework"
  không còn lỗi bắt buộc, nhưng tỉ lệ ẢNH còn cảnh báo
      >= cfg["gate"]["warn_ratio_hold"]                          -> "Hold"
  còn lại                                                        -> "Release"

Tỉ lệ cảnh báo = (số ẢNH khác nhau có ≥ 1 cảnh báo) / (tổng số ảnh).  Chú ý:
- chỉ đếm issue có `image` nằm trong `image_stems` (bỏ "<dataset>", "data.yaml");
- bỏ qua ảnh nằm trong `reviewed` (người đã xem, cảnh báo của ảnh đó coi như đã xử lý) — nhưng LỖI BẮT BUỘC thì không bao giờ được bỏ qua;
- mẫu số là số ảnh, không phải số issue.

Trả về dict: decision, n_errors, n_warn_images, n_images, warn_ratio (làm tròn 4 chữ số), reasons (list[str], giải thích bằng tiếng Việt, có số liệu).
"""
from ..common import ERROR, WARN


def decide(issues, image_stems, cfg, reviewed=frozenset()):
    issues = list(issues)
    image_stems = set(image_stems)
    reviewed = set(reviewed)

    n_images = len(image_stems)
    n_errors = sum(issue.severity == ERROR for issue in issues)
    warned_images = {
        issue.image
        for issue in issues
        if issue.severity == WARN
        and issue.image in image_stems
        and issue.image not in reviewed
    }
    n_warn_images = len(warned_images)
    warn_ratio = n_warn_images / n_images if n_images else 0.0
    hold_threshold = cfg["gate"]["warn_ratio_hold"]

    if n_errors:
        decision = "Rework"
        reasons = [
            f"Còn {n_errors} lỗi bắt buộc; cảnh báo chưa được duyệt trên "
            f"{n_warn_images}/{n_images} ảnh ({warn_ratio:.2%})."
        ]
    elif warn_ratio >= hold_threshold:
        decision = "Hold"
        reasons = [
            f"Cảnh báo chưa được duyệt trên {n_warn_images}/{n_images} ảnh "
            f"({warn_ratio:.2%}), đạt hoặc vượt ngưỡng Hold {hold_threshold:.2%}."
        ]
    else:
        decision = "Release"
        reasons = [
            f"Không còn lỗi bắt buộc; cảnh báo chưa được duyệt trên "
            f"{n_warn_images}/{n_images} ảnh ({warn_ratio:.2%}), thấp hơn "
            f"ngưỡng Hold {hold_threshold:.2%}."
        ]

    return {
        "decision": decision,
        "n_errors": n_errors,
        "n_warn_images": n_warn_images,
        "n_images": n_images,
        "warn_ratio": round(warn_ratio, 4),
        "reasons": reasons,
    }
