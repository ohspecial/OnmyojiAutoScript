# GPU依赖管理功能使用说明

本文档说明如何使用OnmyojiAutoScript项目中新增的GPU依赖管理功能。

## 功能概述

当配置文件中的`UseGpu`设置为`true`时，系统会自动下载并安装CUDA版本的PyTorch和onnxruntime-gpu，以利用GPU加速OCR处理。当设置为`false`时，会安装CPU版本的依赖。

## 配置方法

### 1. 修改配置文件

在`deploy/config.py`中找到`UseGpu`配置项：

```python
class ConfigModel:
    # ...其他配置...
    
    # OCR相关配置
    UseOcrServer: bool = True
    StartOcrServer: bool = True
    OcrServerPort: int = 22268
    OcrClientAddress: str = "127.0.0.1:22268"
    UseGpu: bool = True  # <-- 这里设置GPU使用
    UseOcrServerModel: bool = False
```

- 设置 `UseGpu: bool = True` 启用GPU加速
- 设置 `UseGpu: bool = False` 使用CPU处理

### 2. 或者通过配置模板修改

在`deploy/template`文件中也可以找到相应配置：

```
UseGpu: bool = true
```

## 使用方法

### 自动安装（推荐）

系统在启动或更新依赖时会自动检测`UseGpu`配置并安装相应版本的依赖：

1. 运行项目的安装或更新脚本
2. 系统会自动读取`UseGpu`配置
3. 根据配置安装GPU或CPU版本的依赖

### 手动管理依赖

如果需要手动管理依赖，可以使用以下方法：

```python
from deploy.gpu_dependencies import GPUDependencyManager
from deploy.config import DeployConfig

# 创建配置实例
config = DeployConfig()

# 创建GPU依赖管理器
gpu_manager = GPUDependencyManager(
    pip_cmd=f'"{config.python}" -m pip',
    arg_str=""  # 或者添加其他pip参数
)

# 根据配置安装依赖
use_gpu = config.UseGpu
gpu_manager.install_dependencies(use_gpu)
```

## 安装过程说明

### GPU模式 (UseGpu = True)

当启用GPU模式时，系统会：

1. **检查环境**：验证CUDA是否可用
2. **清理旧版本**：自动卸载现有的torch和onnxruntime包
3. **安装GPU版本**：
   - 安装PyTorch CUDA 12.1版本
   - 安装onnxruntime-gpu
4. **验证安装**：检查CUDA是否正常工作并显示GPU信息
5. **错误处理**：如果安装失败，自动回退到CPU版本

安装日志示例：
```
======================================== Install GPU Dependencies ========================================
Installing PyTorch with CUDA 12.1 support...
PyTorch CUDA installation completed
Installing onnxruntime-gpu...
onnxruntime-gpu installation completed
CUDA verification: 1 GPU(s) detected, primary device: NVIDIA GeForce RTX 3080
✓ GPU dependencies installed successfully and CUDA is available
```

### CPU模式 (UseGpu = False)

当使用CPU模式时，系统会：

1. **清理旧版本**：卸载现有的torch和onnxruntime包
2. **安装CPU版本**：
   - 安装PyTorch CPU版本
   - 安装onnxruntime CPU版本
3. **确认安装**：验证CPU版本安装成功

安装日志示例：
```
======================================== Install CPU Dependencies ========================================
Installing PyTorch CPU version...
PyTorch CPU installation completed
Installing onnxruntime CPU version...
onnxruntime CPU installation completed
✓ CPU dependencies installed successfully
```

## 硬件要求

### GPU模式要求

- **NVIDIA GPU**：支持CUDA 12.1或更高版本
- **显存**：建议至少4GB显存
- **驱动程序**：NVIDIA驱动版本 >= 525.60.13
- **CUDA工具包**：CUDA 12.1或兼容版本

### CPU模式要求

- **处理器**：任何支持的x86_64处理器
- **内存**：建议至少8GB RAM
- **操作系统**：Windows/Linux/macOS

## 性能对比

| 模式 | OCR处理速度 | 内存使用 | 适用场景 |
|------|-------------|----------|----------|
| GPU | 快速 (2-5倍提升) | 较高 | 有NVIDIA GPU的系统 |
| CPU | 中等 | 较低 | 无GPU或显存不足的系统 |

## 故障排除

### 常见问题

1. **CUDA不可用**
   ```
   解决方案：
   - 检查NVIDIA驱动是否正确安装
   - 验证CUDA工具包版本
   - 确认GPU支持CUDA 12.1
   ```

2. **依赖安装失败**
   ```
   解决方案：
   - 检查网络连接
   - 尝试使用国内PyPI镜像
   - 手动安装失败的包
   ```

3. **显存不足**
   ```
   解决方案：
   - 关闭其他使用GPU的程序
   - 切换到CPU模式
   - 降低处理批次大小
   ```

### 验证安装

运行以下代码验证安装是否成功：

```python
import torch
print(f"PyTorch版本: {torch.__version__}")
print(f"CUDA可用: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"GPU数量: {torch.cuda.device_count()}")
    print(f"GPU名称: {torch.cuda.get_device_name(0)}")

try:
    import onnxruntime as ort
    print(f"ONNXRuntime版本: {ort.__version__}")
    providers = ort.get_available_providers()
    print(f"可用提供者: {providers}")
    if 'CUDAExecutionProvider' in providers:
        print("✓ GPU加速可用")
    else:
        print("✓ CPU模式运行")
except ImportError:
    print("ONNXRuntime未安装")
```

## 配置建议

### 推荐配置

- **有NVIDIA GPU且显存>=4GB**：设置 `UseGpu = True`
- **无GPU或显存不足**：设置 `UseGpu = False`
- **混合环境**：可以动态调整配置

### 性能优化

1. **GPU模式优化**：
   - 确保GPU温度正常
   - 关闭不必要的GPU占用程序
   - 定期清理显存

2. **CPU模式优化**：
   - 确保足够的系统内存
   - 关闭其他占用CPU的程序
   - 考虑多线程处理

## 更新说明

该功能会自动处理依赖版本管理，当系统更新时：

1. 检查当前配置
2. 自动安装匹配的依赖版本
3. 保持配置一致性

如需手动更新依赖，删除现有安装并重新运行安装脚本即可。
