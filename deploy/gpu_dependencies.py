# This Python file uses the following encoding: utf-8
"""
GPU Dependencies Manager
Handles installation of GPU/CPU specific dependencies based on UseGpu configuration
"""

import subprocess
import sys
from deploy.logger import logger


class GPUDependencyManager:
    """Manages GPU/CPU specific dependencies installation"""

    def __init__(self, pip_cmd, arg_str=""):
        self.pip_cmd = pip_cmd
        self.arg_str = arg_str

    def check_cuda_available(self):
        """Check if CUDA is available on the system"""
        try:
            import torch
            return torch.cuda.is_available()
        except ImportError:
            # If torch is not installed, we can't check CUDA availability
            return False

    def uninstall_conflicting_packages(self):
        """Uninstall conflicting torch and onnxruntime packages"""
        packages_to_uninstall = [
            'torch', 'torchvision', 'torchaudio',
            'onnxruntime', 'onnxruntime-gpu'
        ]

        for package in packages_to_uninstall:
            try:
                logger.info(f'Uninstalling {package} if present...')
                subprocess.run(
                    f'{self.pip_cmd} uninstall {package} -y{self.arg_str}',
                    shell=True, check=False, capture_output=True
                )
            except Exception as e:
                logger.debug(f'Failed to uninstall {package}: {e}')

    def install_gpu_dependencies(self):
        """Install GPU-specific dependencies"""
        logger.hr('Installing GPU Dependencies', 1)

        # First uninstall any existing conflicting packages
        self.uninstall_conflicting_packages()

        try:
            # Install PyTorch with CUDA support (CUDA 12.4)
            torch_cmd = (
                f'{self.pip_cmd} install torch torchvision torchaudio '
                f'--index-url https://download.pytorch.org/whl/cu124{self.arg_str}'
            )
            logger.info('Installing PyTorch with CUDA 12.4 support...')
            result = subprocess.run(torch_cmd, shell=True, check=True, capture_output=True, text=True)
            logger.info('PyTorch CUDA installation completed')

            # Install onnxruntime-gpu
            onnx_cmd = f'{self.pip_cmd} install onnxruntime-gpu==1.22.0{self.arg_str}'
            logger.info('Installing onnxruntime-gpu 1.22.0...')
            result = subprocess.run(onnx_cmd, shell=True, check=True, capture_output=True, text=True)
            logger.info('onnxruntime-gpu installation completed')

            # Verify CUDA installation
            if self.verify_cuda_installation():
                logger.info('✓ GPU dependencies installed successfully and CUDA is available')
            else:
                logger.warning('⚠ GPU dependencies installed but CUDA may not be available')

        except subprocess.CalledProcessError as e:
            logger.error(f'Failed to install GPU dependencies: {e}')
            logger.error(f'Command output: {e.stdout if hasattr(e, "stdout") else ""}')
            logger.error(f'Command error: {e.stderr if hasattr(e, "stderr") else ""}')
            # Fallback to CPU installation
            logger.info('Falling back to CPU dependencies...')
            self.install_cpu_dependencies()

    def install_cpu_dependencies(self):
        """Install CPU-only dependencies"""
        logger.hr('Installing CPU Dependencies', 1)

        # First uninstall any existing conflicting packages
        self.uninstall_conflicting_packages()

        try:
            # Install PyTorch CPU version
            torch_cmd = (
                f'{self.pip_cmd} install torch torchvision torchaudio '
                f'--index-url https://download.pytorch.org/whl/cpu{self.arg_str}'
            )
            logger.info('Installing PyTorch CPU version...')
            result = subprocess.run(torch_cmd, shell=True, check=True, capture_output=True, text=True)
            logger.info('PyTorch CPU installation completed')

            # Install onnxruntime CPU version (指定版本以确保兼容性)
            onnx_cmd = f'{self.pip_cmd} install "onnxruntime>=1.16.0,<1.24.0"{self.arg_str}'
            logger.info('Installing onnxruntime CPU version...')
            result = subprocess.run(onnx_cmd, shell=True, check=True, capture_output=True, text=True)
            logger.info('onnxruntime CPU installation completed')

            # 验证安装
            if self.verify_onnx_installation():
                logger.info('✓ CPU dependencies installed successfully')
            else:
                logger.warning('⚠ CPU dependencies installed but verification failed')

        except subprocess.CalledProcessError as e:
            logger.error(f'Failed to install CPU dependencies: {e}')
            logger.error(f'Command output: {e.stdout if hasattr(e, "stdout") else ""}')
            logger.error(f'Command error: {e.stderr if hasattr(e, "stderr") else ""}')
            raise

    def verify_onnx_installation(self):
        """Verify that ONNX Runtime installation is working"""
        try:
            # 清除已导入的模块以获取最新安装
            modules_to_clear = ['onnxruntime', 'onnxruntime.capi._pybind_state']
            for module in modules_to_clear:
                if module in sys.modules:
                    del sys.modules[module]

            import onnxruntime
            logger.info(f'ONNX Runtime verification: version {onnxruntime.__version__}')

            # 测试创建简单会话
            providers = onnxruntime.get_available_providers()
            logger.info(f'Available providers: {providers}')
            return True

        except Exception as e:
            logger.warning(f'ONNX Runtime verification failed: {e}')
            return False

    def verify_cuda_installation(self):
        """Verify that CUDA installation is working"""
        try:
            # Reimport torch to get the updated installation
            if 'torch' in sys.modules:
                del sys.modules['torch']

            import torch
            cuda_available = torch.cuda.is_available()
            if cuda_available:
                device_count = torch.cuda.device_count()
                device_name = torch.cuda.get_device_name(0) if device_count > 0 else "Unknown"
                logger.info(f'CUDA verification: {device_count} GPU(s) detected, primary device: {device_name}')

            # 同时验证 ONNX Runtime
            self.verify_onnx_installation()
            return cuda_available
        except Exception as e:
            logger.warning(f'CUDA verification failed: {e}')
            return False

    def install_dependencies(self, use_gpu=True):
        """Main method to install dependencies based on GPU configuration"""
        if use_gpu:
            logger.info('UseGpu is enabled, installing CUDA dependencies...')
            self.install_gpu_dependencies()
        else:
            logger.info('UseGpu is disabled, installing CPU dependencies...')
            self.install_cpu_dependencies()

if __name__ == "__main__":
    # Example usage
    pip_command = sys.executable + " -m pip"
    arg_string = " --trusted-host pypi.org --trusted-host files.pythonhosted.org"

    manager = GPUDependencyManager(pip_command, arg_string)
    manager.install_dependencies(use_gpu=True)  # Change to False to install CPU dependencies
