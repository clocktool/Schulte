import os
import cv2
import numpy as np

TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")

DIGITS = list(range(1, 26))


class TemplateMatcher:
    def __init__(self, template_dir=TEMPLATE_DIR):
        self.templates = {}
        self.template_dir = template_dir
        self._load_templates()

    def _load_templates(self):
        if not os.path.isdir(self.template_dir):
            raise RuntimeError(f"模板目录不存在: {self.template_dir}")

        missing = []
        for d in DIGITS:
            path = os.path.join(self.template_dir, f"{d}.png")
            if not os.path.exists(path):
                missing.append(d)
                continue

            img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
            if img is None:
                missing.append(d)
                continue

            _, binary = cv2.threshold(img, 128, 255, cv2.THRESH_BINARY_INV)

            ys, xs = np.where(binary > 0)
            if len(xs) == 0:
                missing.append(d)
                continue

            x1, x2, y1, y2 = xs.min(), xs.max(), ys.min(), ys.max()
            roi = binary[y1:y2 + 1, x1:x2 + 1]

            norm = cv2.resize(roi, (60, 40), interpolation=cv2.INTER_AREA)
            self.templates[d] = norm

        if missing:
            raise RuntimeError(f"缺少模板: {missing}")

        print(f"已加载 {len(self.templates)} 个数字模板：{sorted(self.templates.keys())}")

    def match(self, cell_img):
        if cell_img is None or cell_img.size == 0:
            return None, 1e9

        img = cell_img
        if img.ndim == 3:
            img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        if img.max() <= 1:
            binary = (img * 255).astype(np.uint8)
        else:
            _, binary = cv2.threshold(img, 128, 255, cv2.THRESH_BINARY_INV)

        ys, xs = np.where(binary > 0)
        if len(xs) == 0:
            return None, 1e9

        x1, x2, y1, y2 = xs.min(), xs.max(), ys.min(), ys.max()
        roi = binary[y1:y2 + 1, x1:x2 + 1]

        rh, rw = roi.shape
        if rh < 5 or rw < 2:
            return None, 1e9

        norm = cv2.resize(roi, (60, 40), interpolation=cv2.INTER_AREA)

        best_digit = None
        best_score = 1e9
        for d, tpl in self.templates.items():
            diff = cv2.absdiff(norm, tpl)
            score = diff.mean() / 255.0
            if score < best_score:
                best_score = score
                best_digit = d

        return best_digit, best_score


if __name__ == "__main__":
    m = TemplateMatcher()
    print("模板加载成功！")