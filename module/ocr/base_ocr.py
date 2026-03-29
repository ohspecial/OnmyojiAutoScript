# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import time
import cv2
import numpy as np

from enum import Enum


from module.base.decorator import cached_property
from module.base.utils import area_pad, crop, float2str

from module.exception import ScriptError
from module.logger import logger
from module.ocr.onnx_paddle_ocr import ONNXPaddleOcr, BoxedResult
from module.server.setting import State

if State.deploy_config.UseOcrServer:
    from module.ocr.rpc import ModelProxyFactory
    OCR_MODEL = ModelProxyFactory()
else:
    from module.ocr.models import OcrModel
    OCR_MODEL = OcrModel()

def enlarge_canvas(image):
    """
    copy from https://github.com/LmeSzinc/StarRailCopilot
    Enlarge image into a square fill with black background. In the structure of PaddleOCR,
    image with w:h=1:1 is the best while 3:1 rectangles takes three times as long.
    Also enlarge into the integer multiple of 32 cause PaddleOCR will downscale images to 1/32.
    """
    height, width = image.shape[:2]
    length = int(max(width, height) // 32 * 32 + 32)
    border = (0, length - height, 0, length - width)
    if sum(border) > 0:
        image = cv2.copyMakeBorder(image, *border, borderType=cv2.BORDER_CONSTANT, value=(0, 0, 0))
    return image


class OcrMode(Enum):
    FULL = 1  # str: "Full"
    SINGLE = 2  # str: "Single"
    DIGIT = 3  # str: "Digit"
    DIGITCOUNTER = 4  # str: "DigitCounter"
    DURATION = 5  # str: "Duration"
    QUANTITY = 6  # str: "Quantity"

class OcrMethod(Enum):
    DEFAULT = 1  # str: "Default"

class BaseCor:

    lang: str = "ch"
    score: float = 0.6  # 阈值默认为0.5

    name: str = "ocr"
    mode: OcrMode = OcrMode.FULL
    method: OcrMethod = OcrMethod.DEFAULT  # 占位符
    roi: list = []  # [x, y, width, height]
    area: list = []  # [x, y, width, height]
    keyword: str = ""  # 默认为空


    def __init__(self,
                 name: str,
                 mode: str,
                 method: str,
                 roi: tuple,
                 area: tuple,
                 keyword: str) -> None:
        """

        :param name:
        :param mode:
        :param method:
        :param roi:
        :param area:
        :param keyword:
        """
        self.name = name.upper()
        if isinstance(mode, str):
            self.mode = OcrMode[mode.upper()]
        elif isinstance(mode, OcrMode):
            self.mode = mode
        if isinstance(method, str):
            self.method = OcrMethod[method.upper()]
        elif isinstance(method, OcrMethod):
            self.method = method
        self.roi: list = list(roi)
        self.area: list = list(area)
        self.keyword = keyword

    def __str__(self):
        return f"{self.name}"

    def __repr__(self):
        return f"{self.name}"

    @cached_property
    def model(self) -> ONNXPaddleOcr:  #因为目前只有一个语言，所以直接返回对应的模型
        return OCR_MODEL.__getattribute__(self.lang)

    def pre_process(self, image):
        """
        重写
        :param image:
        :return:
        """
        # to gray
        if len(image.shape) == 3:
            image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        # to rgb
        if len(image.shape) == 2:
            image = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
        return image

    def after_process(self, result):
        """
        重写
        :param result:
        :return:
        """
        return result

    @classmethod
    def crop(cls, image: np.array, roi: tuple) -> np.array:
        """
        截取图片
        :param roi:
        :param image:
        :return:
        """
        x, y, w, h = roi
        return image[y:y + h, x:x + w]

    def ocr_item(self, image):
        """
        这个函数区别于ocr_single_line，这个函数不对图片进行裁剪，是什么就是什么的
        :param image:
        :return:
        """
        # pre process
        start_time = time.time()
        image = self.pre_process(image)
        # ocr
        result, score = self.model.ocr_single_line(image)
        if score < self.score:
            result = ""
        # after proces
        result = self.after_process(result)
        # logger.info("ocr result score: %s%s" % (result,score))
        logger.attr(name='%s %ss' % (self.name, float2str(time.time() - start_time)),
                    text=f'[{result}]')
        return result

    def ocr_single_line(self, image):
        """
        只支持横方向的单行ocr，不支持竖方向的单行ocr
        注意：这里使用了预处理和后处理
        :param image:
        :return:
        """
        # pre process
        start_time = time.time()
        image = self.crop(image, self.roi)
        image = self.pre_process(image)
        # ocr
        result, score = self.model.ocr_single_line(image)
        if score < self.score:
            result = ""
        # after proces
        result = self.after_process(result)
        # logger.info("ocr result score: %s" % score)
        logger.attr(name='%s %ss' % (self.name, float2str(time.time() - start_time)),
                    text=f'[{result}]')
        return result

    def detect_and_ocr(self, image, drop_score = None) -> list[BoxedResult]:
        """
        注意：这里使用了预处理和后处理
        :param image:
        :param drop_score: 如果不指定，则使用对象的score属性
        :return: list[BoxedResult]
        """
        # pre process
        start_time = time.time()
        image = self.crop(image, self.roi)
        image = self.pre_process(image)
        image = enlarge_canvas(image)

        if drop_score is None:
            drop_score = self.score
        # ocr
        boxed_results: list[BoxedResult] = self.model.detect_and_ocr(image,drop_score)
        results = []
        # after proces
        for result in boxed_results:
            result.ocr_text = self.after_process(result.ocr_text)
            results.append(result)

        logger.attr(name='%s %ss' % (self.name, float2str(time.time() - start_time)),
                    text=str([result.ocr_text for result in results]))
        return results

    def match(self, result: str, included: bool=False) -> bool:
        """
        使用ocr获取结果后和keyword进行匹配
        :param result:
        :param included:  ocr结果和keyword是否包含关系, 要么是包含关系，要么是相等关系
        :return:
        """
        if included:
            return self.keyword in result
        else:
            return self.keyword == result

    def filter(self, boxed_results: list[BoxedResult], keyword: str=None) -> list or None:
        """
        使用ocr获取结果后和keyword进行匹配. 返回匹配的index list
        :param keyword: 如果不指定默认适用对象的keyword
        :param boxed_results:
        :return:
        """
        if keyword is None:
            keyword = self.keyword

        strings = [boxed_result.ocr_text for boxed_result in boxed_results]
        
        # 1. 完整包含匹配：某个单独的框直接包含整个 keyword
        result = [index for index, word in enumerate(strings) if keyword in word]
        if result:
            return result

        # 2. 跨框拼接匹配：应对文字被分割到多个相邻框的情况（比如竖排文字被逐字识别）
        concatenated_string = "".join(strings)
        if keyword in concatenated_string:
            start_pos = concatenated_string.find(keyword)
            end_pos = start_pos + len(keyword)
            
            current_len = 0
            indices = []
            for i, word in enumerate(strings):
                word_end = current_len + len(word)
                if current_len < end_pos and word_end > start_pos:
                    indices.append(i)
                current_len = word_end
            if indices:
                return list(set(indices))

        # 3. 散落匹配容错：针对部分识别遗漏或混入杂符。
        # 原代码中任意单字匹配都会被视为成功，极易发生误判。
        # 这里加以严控：要求至少大部分字符都能被匹配到。
        indices = []
        matched_chars = 0
        for char in keyword:
            for i, string in enumerate(strings):
                if char in string:
                    indices.append(i)
                    matched_chars += 1
                    break
                    
        is_valid = False
        if len(keyword) <= 2:
            is_valid = matched_chars == len(keyword)
        else:
            is_valid = matched_chars >= len(keyword) * 0.7
            
        if is_valid and indices:
            return list(set(indices))

        return None

    def detect_text(self, image) -> str:
        """
        识别图片中的文字， 会按照顺序拼接起来
        :param image:
        :return:
        """
        # pre process
        start_time = time.time()
        image = self.crop(image, self.roi)
        image = self.pre_process(image)
        image = enlarge_canvas(image)
        # ocr
        boxed_results: list[BoxedResult] = self.model.detect_and_ocr(image)
        results = ''
        # after proces
        for result in boxed_results:
            # logger.info("ocr result score: %s" % result.score)
            if result.score < self.score:
                continue
            results += result.ocr_text
        # logger.info("ocr result score: %s" % score)
        logger.attr(name='%s %ss' % (self.name, float2str(time.time() - start_time)),
                    text=f'[{results}]')
        return results


# def test():
#     # strings = ["探", "索"]
#     # keyword = "探索"
#     # strings是截图ocr的结果，keyword是要匹配的关键字
#     strings = ['123', '456', '789', '101112', '131415', '456']
#     keyword = '123456'
#
#     indices = []
#     # 对于keyword中的每一个字符，都要在strings中进行匹配
#     # 如果这个字符在strings中的某一个string中，那么就记录这个string的index
#     max_index = len(strings) - 1
#     for index, char in enumerate(keyword):
#         for i, string in enumerate(strings):
#             if char not in string:
#                 continue
#             if i <= max_index:
#                 indices.append(i)
#                 break
#     if indices:
#         # 剔除掉重复的index
#         indices = list(set(indices))
#         return indices
#     else:
#         return None
# print(test())
