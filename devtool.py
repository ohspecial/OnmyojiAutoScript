from tkinter import filedialog

import customtkinter as ctk
import cv2
import numpy as np
import os
import subprocess
from PIL import Image, ImageTk
from datetime import datetime
import pyperclip
from tkinter import messagebox

class DevTool(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.last_selected_image = None
        self.last_selected_folder = None
        self.np_image = None  # 截图的 NumPy 图像
        self.current_image = None  # 当前显示的图像
        self.rect = {"x1": 0, "y1": 0, "x2": 0, "y2": 0}  # 矩形框
        self.is_dragging = False
        self.drag_start_x = 0
        self.drag_start_y = 0
        self.rect_start_x1 = 0
        self.rect_start_y1 = 0
        self.rect_start_x2 = 0
        self.rect_start_y2 = 0
        self.img_info = None  # 保存图片信息
        # 创建窗口
        self.geometry("1690x750")
        self.title("DevTool")
        self.resizable(False, False)

        # 设置默认路径
        self.screenshots_path = r"D:\共享文件夹\Screenshots"
        self.save_img_path = r"D:\共享文件夹\Screenshots"

        # 确保默认路径存在
        if not os.path.exists(self.screenshots_path):
            try:
                os.makedirs(self.screenshots_path)
            except:
                self.screenshots_path = os.getcwd()  # 如果创建失败，使用当前目录

        if not os.path.exists(self.save_img_path):
            try:
                os.makedirs(self.save_img_path)
            except:
                self.save_img_path = os.getcwd()  # 如果创建失败，使用当前目录

        self.screen_canvas = ctk.CTkCanvas(self, width=1280, height=720)
        self.screen_canvas.configure(borderwidth=2, relief="solid")
        self.screen_canvas.bind("<Enter>", self.in_canvas)
        self.screen_canvas.bind("<Leave>", self.out_canvas)
        self.screen_canvas.bind("<Button-1>", self.on_click)
        self.screen_canvas.bind("<B1-Motion>", self.on_move)
        self.screen_canvas.bind("<ButtonRelease-1>", self.on_release)
        self.mouse_is_in_canvas = False
        # 画布
        self.screen_canvas.grid(row=0, column=0, padx=10, pady=10)
        # 左框架
        self.left_frame = ctk.CTkFrame(self, width=300, height=620)
        self.left_frame.grid(row=0, column=1, padx=0, pady=10, sticky="sn")

        # 文件夹路径输入框
        self.folder_path_entry = ctk.CTkEntry(self.left_frame, placeholder_text="请选择保存图片文件夹", width=260, justify="center")
        self.folder_path_entry.grid(row=1, column=1, columnspan=2, padx=10, pady=10, sticky="ew")
        # 选择文件夹按钮
        self.choese_folder_button = ctk.CTkButton(self.left_frame, text="保存文件夹", width=20, command=self.choose_folder)
        self.choese_folder_button.grid(row=1, column=3, padx=10, pady=10, sticky="w")

        # 图片名称输入框
        self.img_name = ctk.CTkEntry(self.left_frame, placeholder_text="请选择加载的图片",  width=260, justify="center")
        self.img_name.grid(row=2, column=1, columnspan=2, padx=10, pady=10, sticky="ew")
        # 读取图片按钮
        self.load_image_button = ctk.CTkButton(self.left_frame, text="加载图片", width=20, command=self.load_image)
        self.load_image_button.grid(row=2, column=3, padx=10, pady=10, sticky="ew")

        # 请输入保存图片名称
        self.save_name_entry = ctk.CTkEntry(self.left_frame, placeholder_text="请输入保存图片的名字", width=260, justify="center")
        self.save_name_entry.grid(row=3, column=1, columnspan=2, padx=10, pady=10, sticky="ew")
        # 保存按钮
        self.save_and_fmt_button = ctk.CTkButton(self.left_frame, text="保存图片",  width=20, command=self.save_img)
        self.save_and_fmt_button.grid(row=3, column=3, padx=10, pady=10, sticky="ew")

        # 框选坐标显示框
        self.rect_info = ctk.CTkEntry(self.left_frame, placeholder_text="矩形框坐标", width=260, justify="center")
        self.rect_info.grid(row=4, column=1, columnspan=2, padx=10, pady=10, sticky="ew")
        # 绑定回车键事件，当在坐标输入框按回车时显示矩形框
        self.rect_info.bind("<KeyRelease>", self.show_rectangle_from_entry)
        # 复制按钮
        self.copy_button = ctk.CTkButton(self.left_frame, width=20, text="复制坐标", command=lambda: self.copy_to_clipboard(str(self.coordinates)))
        self.copy_button.grid(row=4, column=3, padx=10, pady=10, sticky="ew")

        # # 图片信息显示框
        # self.img_info = ctk.CTkEntry(self.left_frame, placeholder_text="图片信息", width=250, justify="center")
        # self.img_info.grid(row=5, column=1, columnspan=2, padx=10, pady=10, sticky="ew")
        # # 图片信息保存按钮
        # self.img_info_save_btn = ctk.CTkButton(self.left_frame, width=20, text="image_info", command=lambda: self.write_to_file("image"))
        # self.img_info_save_btn.grid(row=5, column=3, padx=10, pady=10, sticky="ew")

        # # 页面信息显示框
        # self.page_info = ctk.CTkEntry(self.left_frame, placeholder_text="page信息", width=250, justify="center")
        # self.page_info.grid(row=6, column=1, columnspan=2, padx=10, pady=10, sticky="ew")
        # # 页面信息保存按钮
        # self.page_info_save_btn = ctk.CTkButton(self.left_frame, width=20, text="page_info", command=lambda: self.write_to_file("page"))
        # self.page_info_save_btn.grid(row=6, column=3, padx=10, pady=10, sticky="ew")

        # # 点击坐标显示框
        # self.click_info = ctk.CTkEntry(self.left_frame, placeholder_text="点击坐标", width=250, justify="center")
        # self.click_info.grid(row=7, column=1, columnspan=2, padx=10, pady=10, sticky="ew")
        # # 点击坐标保存按钮
        # self.click_info_save_btn = ctk.CTkButton(self.left_frame, width=20, text="click_info", command=lambda: self.write_to_file("coor"))
        # self.click_info_save_btn.grid(row=7, column=3, padx=10, pady=10, sticky="ew")

        # log显示框
        self.log_box = ctk.CTkTextbox(self.left_frame, bg_color="#dadada", fg_color="#000000", text_color="#48BB31", width=120, height=520)
        self.log_box.grid(row=5, column=1, columnspan=3, padx=10, pady=10, sticky="nsew")

        # 初始化保存路径输入框为默认保存路径
        self.folder_path_entry.insert(0, self.save_img_path)

    def log_print(self, text):
        self.log_box.insert("end", f"{text}\n")
        self.log_box.update()
        self.log_box.see("end")

    def copy_to_clipboard(self, text):
        # 修改这里：改变复制到剪贴板的坐标格式
        x1, y1, x2, y2 = self.coordinates
        width = x2 - x1
        height = y2 - y1
        formatted_text = f"{x1-4},{y1-4},{width},{height}"
        # 彻底清理所有空白字符
        import re
        formatted_text = re.sub(r'\s+', '', formatted_text)

        # 使用更可靠的剪贴板方法
        pyperclip.copy(formatted_text)
        self.log_print(f"复制坐标 {formatted_text} 到剪贴板")

    def choose_folder(self):
        # 使用上次选择的路径或默认路径作为初始目录
        initial_dir = self.last_selected_folder or self.save_img_path
        folder_path = filedialog.askdirectory(initialdir=initial_dir)
        if folder_path:  # 如果选择了文件夹
            self.last_selected_folder = folder_path  # 记住选择的路径
            self.folder_path_entry.delete(0, "end")
            self.folder_path_entry.insert(0, folder_path)
            self.log_print(folder_path)

    def choose_image_file(self):
        """打开文件对话框选择PNG图片文件"""
        # 使用上次选择的路径或默认路径作为初始目录
        initial_dir = self.last_selected_image or self.screenshots_path
        file_path = filedialog.askopenfilename(
            initialdir=initial_dir,
            title="选择PNG图片",
            filetypes=(("PNG图片", "*.png"), ("所有文件", "*.*"))
        )
        if file_path:  # 如果选择了文件
            self.last_selected_image = os.path.dirname(file_path)  # 记住文件所在目录
        return file_path

    def load_image(self):
        """通过文件对话框加载PNG图片"""
        image_path = self.choose_image_file()
        if not image_path:  # 用户取消选择
            return

        self.log_print(f"加载图片: {os.path.basename(image_path)}")
        try:
            # 使用cv2读取图片
            self.np_image = cv2.imdecode(np.fromfile(image_path, dtype=np.uint8), cv2.IMREAD_COLOR)

            # 检查图片是否存在
            if self.np_image is None:
                self.log_print("无法读取图片文件")
                return

            # 检查图片尺寸
            if self.np_image.shape[1] != 1280 or self.np_image.shape[0] != 720:
                self.log_print(f"警告: 图片尺寸为 {self.np_image.shape[1]}x{self.np_image.shape[0]}，不是1280x720")

            # 转换为PIL Image并显示
            pil_image = Image.fromarray(cv2.cvtColor(self.np_image, cv2.COLOR_BGR2RGB))
            self.current_image = ImageTk.PhotoImage(pil_image)
            self.screen_canvas.create_image(4, 4, anchor="nw", image=self.current_image)

            # 设置图片名称为文件名（不含扩展名）
            img_name = os.path.splitext(os.path.basename(image_path))[0]
            self.img_name.delete(0, "end")
            self.img_name.insert(0, img_name)

            # 设置默认保存名称为加载图片名_1
            self.save_name_entry.delete(0, "end")
            self.save_name_entry.insert(0, f"{img_name}_1")

            # 自动填充文件夹路径为默认保存路径
            self.folder_path_entry.delete(0, "end")
            self.folder_path_entry.insert(0, self.save_img_path)

            # 重新绘制矩形框（如果存在）
            if self.rect["x1"] != self.rect["x2"] and self.rect["y1"] != self.rect["y2"]:
                self.draw_rectangle()

        except Exception as e:
            self.log_print(f"加载图片时出错: {e}")

    @property
    def coordinates(self):
        x1, y1, x2, y2 = self.rect.values()
        return min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)

    @property
    def name(self):
        return self.img_name.get()

    @property
    def file_path(self):
        base_path = self.folder_path_entry.get()
        img_name = self.name
        # 检查文件名是否合法
        if not img_name or not img_name.strip():
            self.log_print("图片名称不能为空")
            return
        # if not re.match(r"^[\w\-. ]+$", img_name):
        #     self.log_print("图片名称含有非法字符")
        #     return

        # 检查目录是否存在
        if not os.path.exists(base_path):
            self.log_print("保存路径不存在")
            return
        timestamp = datetime.now().strftime("%H%M%S")
        path = os.path.relpath(base_path, start=os.curdir) + "/" + img_name + f"_{timestamp}.png"  # 保存路径x
        path = path.replace("\\", "/")  # 路径格式化

        return path

    def save_img(self):

        # 检查是否已加载图片
        if self.np_image is None:
            self.log_print("请先加载图片")
            return

        # 检查是否已选择有效区域
        x1, y1, x2, y2 = self.coordinates
        if not (x1 != x2 and y1 != y2):  # 检查是否已选择区域
            self.log_print("请先选择要保存的区域")
            return

        # 获取保存名称输入框的内容作为文件名
        save_name = self.save_name_entry.get().strip()

        # 如果输入框为空，使用加载的图片名称作为基础名称
        if not save_name:
            base_name = self.name.strip()
            if base_name:
                save_name = f"{base_name}_1"
            else:
                self.log_print("保存图片的名字不能为空")
                return

        path = os.path.join(self.folder_path_entry.get(), f"{save_name}.png")

        # 检查文件是否已存在
        if os.path.exists(path):
            # 弹窗提示用户文件已存在，提供三个选项
            # self.withdraw()  # 隐藏主窗口，使对话框成为模态
            result = messagebox.askyesno(
                "文件已存在",
                f"文件 {save_name}.png 已存在，是否要覆盖该文件？\n\n '是' 覆盖文件\n '否' 取消保存"
            )
            # self.deiconify()  # 恢复主窗口

            if not result:  # 用户选择否，取消保存
                self.log_print("取消保存操作")
                return
            else:  # 用户选择是，覆盖文件
                self.log_print(f"将覆盖文件: {save_name}.png")

        if self.np_image is not None and any(self.rect.values()):  # 确保 np_image 和矩形框有效
            x1, y1, x2, y2 = self.coordinates
            # 检查裁剪框的有效性
            if not (0 <= x1 < x2 <= self.np_image.shape[1] and 0 <= y1 < y2 <= self.np_image.shape[0]):
                self.log_print("裁剪框的坐标无效")
                return
            try:
                cropped_image = self.np_image[y1 - 4 : y2 - 4, x1 - 4 : x2 - 4]
                cv2.imencode(".png", cropped_image)[1].tofile(path)
                self.log_print(f"{save_name}.png 保存成功")
            except Exception as e:
                self.log_print(f"保存图像时出错: {e}")

    def format_img(self, fmt_type):
        x1, y1, x2, y2 = self.coordinates
        match fmt_type:
            case "image":
                img_info = f"{self.name}=['{self.file_path}', [{x1-4}, {y1-4}, {x2-4}, {y2-4}], '{self.name}']"
            case "page":
                img_info = f"{self.name}=Page('{self.name}',['{self.file_path}', [{x1-4}, {y1-4}, {x2-4}, {y2-4}], '{self.name}'])"
            case "coor":
                img_info = f"{self.name}=({x1-4}, {y1-4}, {x2-4}, {y2-4})"
        return img_info
        pass

    def write_to_file(self, save_type):
        try:
            self._img_info = self.format_img(save_type)
            self.log_print(self._img_info)
            if self._img_info:
                if not os.path.exists(os.path.join(self.folder_path_entry.get(), "img_info_auto_create.py")):
                    with open(os.path.join(self.folder_path_entry.get(), "img_info_auto_create.py"), "w") as file:
                        file.write(f"# this file is auto created by devtool at {datetime.now()}\n\n")  # 写入内容
                        self.log_print("创建文件成功")

                with open(os.path.join(self.folder_path_entry.get(), "img_info_auto_create.py"), "a") as f:
                    f.write(str(self._img_info) + "\n")  # 写入内容
                    self.log_print("写入文件成功")
            else:
                self.log_print("没有图像信息或图像名称")
        except Exception as e:
            self.log_print(f"写入文件时出错: {e}")

    def in_canvas(self, event):
        self.mouse_is_in_canvas = True
        # self.log_print("鼠标进入画布")

    def out_canvas(self, event):
        self.mouse_is_in_canvas = False
        # self.log_print("鼠标离开画布")

    def on_click(self, event):
        if self.mouse_is_in_canvas:
            x1, y1, x2, y2 = self.rect["x1"], self.rect["y1"], self.rect["x2"], self.rect["y2"]
            # Normalize coordinates to check if inside
            norm_x1, norm_x2 = min(x1, x2), max(x1, x2)
            norm_y1, norm_y2 = min(y1, y2), max(y1, y2)

            if norm_x1 <= event.x <= norm_x2 and norm_y1 <= event.y <= norm_y2 and (x1 != x2 or y1 != y2):
                self.is_dragging = True
                self.drag_start_x = event.x
                self.drag_start_y = event.y
                self.rect_start_x1 = self.rect["x1"]
                self.rect_start_y1 = self.rect["y1"]
                self.rect_start_x2 = self.rect["x2"]
                self.rect_start_y2 = self.rect["y2"]
            else:
                self.is_dragging = False
                self.rect["x1"] = event.x
                self.rect["y1"] = event.y
                self.rect["x2"] = event.x
                self.rect["y2"] = event.y
                self.draw_rectangle() # Clear previous rectangle and draw a point

    def on_move(self, event):
        if self.mouse_is_in_canvas:
            if self.is_dragging:
                dx = event.x - self.drag_start_x
                dy = event.y - self.drag_start_y
                self.rect["x1"] = self.rect_start_x1 + dx
                self.rect["y1"] = self.rect_start_y1 + dy
                self.rect["x2"] = self.rect_start_x2 + dx
                self.rect["y2"] = self.rect_start_y2 + dy
            else:
                self.rect["x2"] = event.x
                self.rect["y2"] = event.y
            
            self.draw_rectangle()
            self.dyn_creat_info()

    def on_release(self, event):
        if self.mouse_is_in_canvas:
            if self.is_dragging:
                self.is_dragging = False
                # Final position update for drag
                dx = event.x - self.drag_start_x
                dy = event.y - self.drag_start_y
                self.rect["x1"] = self.rect_start_x1 + dx
                self.rect["y1"] = self.rect_start_y1 + dy
                self.rect["x2"] = self.rect_start_x2 + dx
                self.rect["y2"] = self.rect_start_y2 + dy
            else:
                # Final position for drawing
                self.rect["x2"] = event.x
                self.rect["y2"] = event.y

            self.draw_rectangle()
            
            x1, y1, x2, y2 = self.coordinates
            # Use the normalized coordinates for logging width and height
            width = x2 - x1
            height = y2 - y1
            self.log_print(f"矩形框坐标：{x1-4},{y1-4},{width},{height}")
            self.dyn_creat_info()

    def dyn_creat_info(self, *args, **kwargs):
        # 修改这里：改变矩形框坐标显示框中的格式
        x1, y1, x2, y2 = self.coordinates
        width = x2 - x1
        height = y2 - y1
        self.rect_info.delete(0, "end")
        self.rect_info.insert(0, f"{x1-4},{y1-4},{width},{height}")
        # self.img_info.delete(0, "end")
        # self.img_info.insert(0, f"{self.format_img('image')}")
        # self.page_info.delete(0, "end")
        # self.page_info.insert(0, f"{self.format_img('page')}")
        # self.click_info.delete(0, "end")
        # self.click_info.insert(0, f"{self.format_img('coor')}")

    def draw_rectangle(self):
        self.screen_canvas.delete("rect")
        self.screen_canvas.create_rectangle(self.rect["x1"], self.rect["y1"], self.rect["x2"], self.rect["y2"], outline="red", tags="rect")

    def show_rectangle_from_entry(self, event=None):
        """从坐标输入框获取坐标并在画布上显示矩形框"""
        coord_text = self.rect_info.get().strip()
        if not coord_text:
            # 如果输入框为空，清除画布上的矩形框
            self.screen_canvas.delete("rect")
            return

        # 只有当输入的坐标看起来是完整的时候才尝试绘制
        if coord_text.count(',') != 3:
            # 如果不是完整的4个坐标值，暂时不处理
            return

        try:
            # 解析坐标格式 x,y,w,h
            coords = [int(x.strip()) for x in coord_text.split(',')]
            if len(coords) != 4:
                return  # 不完整的坐标不处理

            x, y, w, h = coords
            # 转换为画布坐标 (加上偏移量4)
            x1 = x + 4
            y1 = y + 4
            x2 = x1 + w
            y2 = y1 + h

            # 检查坐标是否在图像范围内
            if self.np_image is not None:
                if not (0 <= x1 < x2 <= self.np_image.shape[1]+8 and 0 <= y1 < y2 <= self.np_image.shape[0]+8):
                    # 坐标超出范围时不绘制，但不清除现有矩形
                    return

            # 更新矩形坐标
            self.rect["x1"] = x1
            self.rect["y1"] = y1
            self.rect["x2"] = x2
            self.rect["y2"] = y2

            # 绘制矩形
            self.draw_rectangle()

        except ValueError:
            # 输入非数字时不处理
            pass
        except Exception:
            # 其他异常也不处理
            pass




if __name__ == "__main__":
    app = DevTool()
    app.mainloop()