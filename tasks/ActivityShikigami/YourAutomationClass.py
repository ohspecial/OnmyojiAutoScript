import os

from module.atom.image import RuleImage


class YourAutomationClass:
    def __init__(self):
        # 图片文件夹路径（建议放在项目根目录的assets目录）
        self.image_folder = "./tasks/GlobalGame/ui/"

        # 动态加载所有图片（支持png/jpg/jpeg格式）
        self.image_rules = self._load_image_rules()

        # 原来的硬编码对象改为列表
        # self.I_UI_CONFIRM_SAMLL = RuleImage(...)

    def _load_image_rules(self):
        """动态加载图片文件夹中的所有图片"""
        image_rules = []

        # 支持的图片格式
        supported_formats = ('.png', '.jpg', '.jpeg')

        # 遍历图片文件夹
        for filename in os.listdir(self.image_folder):
            # 过滤非图片文件
            if not filename.lower().endswith(supported_formats):
                continue

            # 构建完整路径
            file_path = os.path.join(self.image_folder, filename)

            # 创建RuleImage对象并添加到列表
            image_rule = RuleImage(
                roi_front=(0, 0, 1280, 720),  # 保持与原来相同的ROI参数
                roi_back=(0, 0, 1280, 720),
                threshold=0.8,
                method="Template matching",
                file=file_path
            )
            image_rules.append(image_rule)

        return image_rules

    def check_and_click(self):
        """遍历所有图片规则进行检测和点击"""
        for image_rule in self.image_rules:
            if self.appear_then_click(image_rule, interval=1):
                print(f"成功点击图片: {os.path.basename(image_rule.file)}")
                return True

        print("未找到匹配图片")
        return False

# 使用示例
if __name__ == "__main__":
    automator = YourAutomationClass()
    automator.check_and_click()