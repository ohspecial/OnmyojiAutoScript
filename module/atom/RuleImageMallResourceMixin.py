# This Python file uses the following encoding: utf-8
# Adapted from runhey/OnmyojiAutoScript's mall resource extension.
from module.atom.ocr import RuleOcr
from module.image.rpc import get_image_client
from module.logger import logger


class RuleImageMallResourceMixin:
    """定位商城资源图标，并构造旁边数量文本的 OCR 规则。"""

    MALL_RESOURCE_X_OFFSET = 40
    MALL_RESOURCE_RIGHT_EXTEND = 70

    def match_and_get_roi(self, image, threshold=None, frame_id=None):
        """匹配成功时返回图标 ROI，失败时返回 None。"""
        try:
            if self.method == "Default":
                # 上游商城资源规则使用 Default；仅在此扩展中映射为模板匹配。
                # 修改请求副本，保留原规则和公共匹配接口。
                rule_data = self.to_service_payload()
                rule_data["method"] = self.METHOD_TEMPLATE_MATCH
                result = get_image_client().match_rule(
                    rule_data=rule_data,
                    image=image,
                    frame_id=frame_id,
                    threshold=threshold,
                )
                ok = self._apply_match_result(result)
            else:
                ok = self.match(image, threshold=threshold, frame_id=frame_id)
        except Exception as e:
            logger.error(f"Mall resource match exception: {e}")
            return None

        if not ok:
            return None

        try:
            mat = self.image
            if mat is None or mat.shape[0] == 0 or mat.shape[1] == 0:
                return None

            h, w = mat.shape[:2]
            x = int(self.roi_front[0])
            y = int(self.roi_front[1])
            return x, y, int(w), int(h)
        except Exception:
            return None

    def get_mall_resource_text_roi(self, image, threshold=None, frame_id=None):
        """推导数量文本 ROI；图标未匹配时沿用上游的 roi_front 回退。"""
        try:
            icon_roi = self.match_and_get_roi(image, threshold, frame_id)
            if icon_roi is None:
                ix, iy, iw, ih = self.roi_front
            else:
                ix, iy, iw, ih = icon_roi

            x = int(ix) + self.MALL_RESOURCE_X_OFFSET
            y = int(iy)
            w = int(iw) + self.MALL_RESOURCE_RIGHT_EXTEND
            h = int(ih)
            return x, y, w, h
        except Exception:
            return None

    def build_mall_resource_ocr(self, image, threshold=None, name="mall_resource", frame_id=None):
        """构造 Quantity OCR 规则；保留现有调用方式并支持复用 frame_id。"""
        try:
            roi = self.get_mall_resource_text_roi(image, threshold, frame_id)
            if roi is None:
                return None

            return RuleOcr(
                roi=roi,
                area=roi,
                mode="Quantity",
                method="Default",
                keyword="",
                name=name,
            )
        except Exception:
            return None
