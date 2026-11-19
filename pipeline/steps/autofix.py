"""BƯỚC 2/4 — Sửa tự động những lỗi bắt buộc mà máy sửa được AN TOÀN.   ★★

Test:  pytest tests/test_autofix.py -q

`fix(ds, issues, cfg) -> list[dict]`: duyệt `issues` (chỉ lỗi severity ERROR), sửa thẳng vào thư mục `ds`,
và trả về danh sách thay đổi; mỗi phần tử có khoá: image, line, action, before, after
(đây chính là file `03_fixes.csv` — bằng chứng pipeline đã làm gì, người có thể kiểm lại).

| code lỗi                                       | cách sửa                                    | action           |
|------------------------------------------------|---------------------------------------------|------------------|
| BAD_FORMAT, BAD_CLASS_ID, BOX_ZERO, DUP_BOX    | xoá dòng đó khỏi file nhãn                  | "drop_line"      |
| BOX_OUT_OF_IMAGE                               | cắt box về trong [0,1] (giữ nguyên lớp)     | "clip_box"       |
| MISSING_LABEL_FILE                             | KHÔNG sửa file (máy không thể bịa nhãn): ghi 1 dòng fix, before="(không có file)", after="chuyển người gán" | "needs_label" |
| BAD_CLASS_NAME                                 | ghi lại `names` trong data.yaml đúng `cfg["classes"]` | "rename_classes" |
| DUP_IMAGE_*, LEAK_TEST, CORRUPT_IMAGE, BAD_SIZE| xoá ảnh + nhãn khỏi `ds`                    | "remove_image"   |

Bẫy cần nghĩ tới (có test cho từng cái)
- Một file có NHIỀU dòng lỗi: số dòng trong `issues` là số dòng GỐC. Nếu xoá từng dòng một thì số dòng lệch.
  Gom theo file, rồi ghi lại MỘT lần.
- Sau khi cắt, box có thể không còn diện tích (nằm hẳn ngoài ảnh): lúc đó xoá dòng thay vì ghi box rỗng.
- Một dòng có 2 lỗi (vd. BOX_OUT_OF_IMAGE + DUP_BOX): xoá dòng thắng, chỉ ghi 1 fix `drop_line`, không ghi thêm `clip_box`. Dòng trống ở giữa file vẫn đếm vào số dòng gốc.
- Ảnh vừa bị xoá (DUP_IMAGE_*...) mà còn issue dòng của chính nó: bỏ qua êm, không được báo lỗi/chết.
- Không động tới lỗi WARN (cảnh báo là việc của người). Không sửa file ở `data/raw/` — chỉ sửa `ds`.
- Chạy lần 2 trên dữ liệu đã sửa phải không làm gì thêm (idempotent) — NGOẠI LỆ duy nhất: `needs_label` được ghi lại mỗi lần còn lỗi `MISSING_LABEL_FILE` (vì ảnh vẫn chưa có nhãn).

- `needs_label` KHÔNG tạo file nhãn rỗng (rỗng = "ảnh nền", khác với "chưa gán"). `review_queue` sẽ đẩy ảnh này lên đầu hàng đợi cho người.

Gợi ý: `yaml.safe_load / safe_dump`.
"""
from collections import defaultdict  # noqa: F401

import yaml  # noqa: F401

from ..common import ERROR, parse_yolo_line


def fix(ds, issues, cfg):
    drop_codes = {"BAD_FORMAT", "BAD_CLASS_ID", "BOX_ZERO", "DUP_BOX"}
    remove_codes = {"LEAK_TEST", "CORRUPT_IMAGE", "BAD_SIZE"}
    clip_code = "BOX_OUT_OF_IMAGE"
    error_issues = [issue for issue in issues if issue.severity == ERROR]
    fixes = []

    removed_images = {
        issue.image
        for issue in error_issues
        if issue.code.startswith("DUP_IMAGE_") or issue.code in remove_codes
    }
    for stem in sorted(removed_images):
        image_path = ds.image_path(stem)
        label_path = ds.label_path(stem)
        before = []
        if image_path is not None:
            before.append(image_path.name)
            image_path.unlink(missing_ok=True)
        if label_path.exists():
            before.append(label_path.name)
            label_path.unlink(missing_ok=True)
        if before:
            fixes.append({
                "image": stem,
                "line": None,
                "action": "remove_image",
                "before": ", ".join(before),
                "after": "đã xóa ảnh và nhãn",
            })

    line_errors = defaultdict(lambda: defaultdict(set))
    for issue in error_issues:
        if issue.image in removed_images or issue.line is None:
            continue
        if issue.code in drop_codes or issue.code == clip_code:
            line_errors[issue.image][issue.line].add(issue.code)

    for stem in sorted(line_errors):
        label_path = ds.label_path(stem)
        if not label_path.exists():
            continue

        original_text = label_path.read_text(encoding="utf-8", errors="replace")
        original_lines = original_text.splitlines()
        updated_lines = []
        changed = False

        for line_no, original in enumerate(original_lines, start=1):
            codes = line_errors[stem].get(line_no, set())
            if not codes:
                updated_lines.append(original)
                continue

            if codes & drop_codes:
                fixes.append({
                    "image": stem,
                    "line": line_no,
                    "action": "drop_line",
                    "before": original,
                    "after": "",
                })
                changed = True
                continue

            if clip_code in codes:
                try:
                    class_id, cx, cy, width, height = parse_yolo_line(original)
                except ValueError:
                    updated_lines.append(original)
                    continue

                left = max(0.0, cx - width / 2)
                top = max(0.0, cy - height / 2)
                right = min(1.0, cx + width / 2)
                bottom = min(1.0, cy + height / 2)
                if left >= right or top >= bottom:
                    fixes.append({
                        "image": stem,
                        "line": line_no,
                        "action": "drop_line",
                        "before": original,
                        "after": "",
                    })
                    changed = True
                    continue

                clipped = (
                    class_id,
                    (left + right) / 2,
                    (top + bottom) / 2,
                    right - left,
                    bottom - top,
                )
                updated = " ".join(
                    [str(clipped[0])] + [f"{value:.10g}" for value in clipped[1:]]
                )
                updated_lines.append(updated)
                fixes.append({
                    "image": stem,
                    "line": line_no,
                    "action": "clip_box",
                    "before": original,
                    "after": updated,
                })
                changed = True
                continue

            updated_lines.append(original)

        if changed:
            updated_text = "\n".join(updated_lines)
            if original_text.endswith(("\n", "\r")) and updated_lines:
                updated_text += "\n"
            label_path.write_text(updated_text, encoding="utf-8")

    needs_label = {
        issue.image
        for issue in error_issues
        if issue.code == "MISSING_LABEL_FILE" and issue.image not in removed_images
    }
    for stem in sorted(needs_label):
        fixes.append({
            "image": stem,
            "line": None,
            "action": "needs_label",
            "before": "(không có file)",
            "after": "chuyển người gán",
        })

    if any(issue.code == "BAD_CLASS_NAME" for issue in error_issues):
        yaml_path = ds.yaml_path
        original = yaml_path.read_text(encoding="utf-8") if yaml_path.exists() else ""
        data = yaml.safe_load(original) if original.strip() else {}
        if not isinstance(data, dict):
            data = {}
        previous_names = data.get("names")
        classes = list(cfg["classes"])
        data["names"] = classes
        yaml_path.write_text(
            yaml.safe_dump(data, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )
        fixes.append({
            "image": "data.yaml",
            "line": None,
            "action": "rename_classes",
            "before": str(previous_names),
            "after": str(classes),
        })

    return fixes
