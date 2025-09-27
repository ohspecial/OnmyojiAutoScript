import cv2
import numpy as np
from module.base.utils import color_similarity_2d, load_image
from module.ocr.base_ocr import BaseCor

def apply_mask(image, mask):
    image16 = image.astype(np.uint16)
    mask16 = mask.astype(np.uint16)
    mask16 = cv2.merge([mask16, mask16, mask16])
    image16 = cv2.multiply(image16, mask16)
    # cv2.multiply(image16, mask16, dst=image16)
    image16 = cv2.convertScaleAbs(image16, alpha=1 / 255)
    # cv2.convertScaleAbs(image16, alpha=1 / 255, dst=image16)
    # Image.fromarray(image16.astype(np.uint8)).show()
    return image16.astype(np.uint8)

class StoneOcr(BaseCor):
    def pre_process(self, image):
        yuv = cv2.cvtColor(image, cv2.COLOR_RGB2YUV)
        _, u, _ = cv2.split(yuv)
        cv2.subtract(128, u, dst=u)
        cv2.multiply(u, 8, dst=u)

        color = color_similarity_2d(image, color=(234, 213, 181))
        hsv = cv2.cvtColor(image, cv2.COLOR_RGB2HSV)
        _, _, v = cv2.split(hsv)
        image = apply_mask(image, u)
        image = apply_mask(image, color)
        image = apply_mask(image, v)

        cv2.convertScaleAbs(image, alpha=3, dst=image)
        cv2.subtract((255, 255, 255, 0), image, dst=image)

        return image


if __name__ == '__main__':
    from tasks.SixRealms.assets import SixRealmsAssets
    file = r'E:\img_tmp\MuMu12-20250722-235421.png'
    image = load_image(file)
    ocr = StoneOcr(roi=(0,0,1280,720), area=(0,0,1280,720), mode="Full", method="Default", keyword="", name="ocr_map")
    results = ocr.detect_and_ocr(image)
    for r in results:
        print(r.box, r.ocr_text)
