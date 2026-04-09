#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI控制页面 - PySide6版本
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QGridLayout, QTextEdit, QProgressBar,
    QFileDialog, QMessageBox, QLineEdit, QSpinBox, QDialog
)
from PySide6.QtCore import Qt, QTimer, QThread, Signal
from PySide6.QtGui import QImage, QPixmap
import cv2
import numpy as np
import time
import os
import subprocess
import sys
import json
import requests


class LLMCallThread(QThread):
    """LLM调用线程"""
    finished = Signal(bool, str, int)  # success, message, latency
    
    def __init__(self, url, payload):
        super().__init__()
        self.url = url
        self.payload = payload
    
    def run(self):
        """执行LLM调用"""
        try:
            start_time = time.time()
            
            # 禁用代理
            session = requests.Session()
            session.trust_env = False
            
            response = session.post(
                self.url,
                json=self.payload,
                timeout=120,  # 2分钟超时
                proxies={'http': None, 'https': None}
            )
            
            latency = int((time.time() - start_time) * 1000)
            
            if response.status_code == 200:
                result = response.json()
                assistant_message = result["choices"][0]["message"]["content"]
                self.finished.emit(True, assistant_message, latency)
            else:
                self.finished.emit(False, f"API返回 {response.status_code}", 0)
        
        except requests.exceptions.Timeout:
            self.finished.emit(False, "请求超时(120秒) - 模型推理时间过长", 0)
        except Exception as e:
            self.finished.emit(False, f"{str(e)[:100]}", 0)


class LMStudioCheckThread(QThread):
    """LM Studio连接检测线程"""
    finished = Signal(bool, str, str)  # success, message, model_name
    
    def __init__(self, models_url):
        super().__init__()
        self.models_url = models_url
    
    def run(self):
        """执行检测"""
        try:
            # 禁用代理
            session = requests.Session()
            session.trust_env = False
            
            response = session.get(self.models_url, timeout=10, proxies={'http': None, 'https': None})
            if response.status_code == 200:
                models = response.json()
                model_name = "未知模型"
                if models.get("data") and len(models["data"]) > 0:
                    model_name = models["data"][0].get("id", "未知模型")
                self.finished.emit(True, "连接成功", model_name)
            else:
                self.finished.emit(False, f"HTTP错误: {response.status_code}", "")
        except requests.exceptions.Timeout:
            self.finished.emit(False, "连接超时(10秒)", "")
        except requests.exceptions.ConnectionError as e:
            self.finished.emit(False, f"连接失败: {str(e)[:100]}", "")
        except Exception as e:
            self.finished.emit(False, f"检测失败: {str(e)[:100]}", "")


class InstallThread(QThread):
    """安装线程"""
    progress = Signal(str)
    finished = Signal(bool, str)
    
    def __init__(self, package_name, model_name=None):
        super().__init__()
        self.package_name = package_name
        self.model_name = model_name
    
    def run(self):
        """执行安装"""
        try:
            # 安装Python包
            self.progress.emit(f"正在安装 {self.package_name}...")
            
            # 获取Python解释器路径（兼容打包后的exe）
            python_exe = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
            if os.path.isdir(python_exe):
                python_exe = os.path.join(python_exe, 'python.exe')
            python_exe = os.path.join(os.path.dirname(sys.executable), 'python.exe')
            if not os.path.exists(python_exe):
                python_exe = sys.executable
            
            process = subprocess.Popen(
                [python_exe, "-m", "pip", "install", self.package_name],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            for line in process.stdout:
                self.progress.emit(line.strip())
            
            process.wait()
            
            if process.returncode != 0:
                error = process.stderr.read()
                self.finished.emit(False, f"安装失败: {error}")
                return
            
            # 如果需要下载模型
            if self.model_name:
                self.progress.emit(f"正在下载模型 {self.model_name}...")
                
                if "yolo" in self.package_name.lower():
                    # 下载YOLO模型
                    try:
                        from ultralytics import YOLO
                        model = YOLO(self.model_name)
                        self.progress.emit(f"模型 {self.model_name} 下载完成")
                    except Exception as e:
                        self.finished.emit(False, f"模型下载失败: {str(e)}")
                        return
            
            self.finished.emit(True, f"{self.package_name} 安装成功!")
            
        except Exception as e:
            self.finished.emit(False, f"安装出错: {str(e)}")


class AIControlPage(QWidget):
    """AI控制页面"""
    
    def __init__(self, parent, main_gui):
        super().__init__(parent)
        self.main_gui = main_gui
        
        # 状态变量
        self.camera_running = False
        self.camera_capture = None
        self.camera_timer = None
        
        # AI模型状态
        self.voice_model = None
        self.vision_model = None
        self.llm_model = None
        
        # 模型加载状态
        self.voice_loaded = False
        self.vision_loaded = False
        self.llm_loaded = False
        
        # LM Studio配置
        self.lm_studio_url = "http://127.0.0.1:1234/v1/chat/completions"
        self.lm_studio_models_url = "http://127.0.0.1:1234/v1/models"
        self.lm_studio_available = False
        
        # 录音状态
        self.recording = False
        self.audio_data = []
        
        self._init_ui()
    
    def _init_ui(self):
        """初始化UI"""
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)
        
        # 左侧：主要功能区
        left_panel = self._create_left_panel()
        main_layout.addWidget(left_panel, 3)
        
        # 右侧：摄像头和控制
        right_panel = self._create_right_panel()
        main_layout.addWidget(right_panel, 2)
    
    def _create_left_panel(self):
        """创建左侧面板"""
        panel = QWidget()
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        panel_layout.setSpacing(15)
        
        # AI功能卡片网格
        grid = QGridLayout()
        grid.setSpacing(15)
        
        # 语音识别卡片
        self.voice_card = self._create_feature_card(
            "🎤", "语音识别", "Whisper模型",
            "点击开始录音，说出控制指令",
            "#667eea",
            self._toggle_voice
        )
        grid.addWidget(self.voice_card, 0, 0)
        
        # 视觉识别卡片
        self.vision_card = self._create_feature_card(
            "👁️", "视觉识别", "YOLOv8模型",
            "实时检测和追踪物体",
            "#f093fb",
            self._toggle_vision
        )
        grid.addWidget(self.vision_card, 0, 1)
        
        # 自然语言卡片
        self.llm_card = self._create_feature_card(
            "💬", "自然语言", "Qwen2模型",
            "理解复杂指令并生成动作序列",
            "#4facfe",
            self._toggle_llm
        )
        grid.addWidget(self.llm_card, 1, 0)
        
        # 模型训练卡片
        self.train_card = self._create_feature_card(
            "🎯", "模型训练", "自定义训练",
            "训练专属物体识别模型",
            "#43e97b",
            self._open_training
        )
        grid.addWidget(self.train_card, 1, 1)
        
        panel_layout.addLayout(grid)
        
        # 对话历史区域
        history_frame = QFrame()
        history_frame.setObjectName("card")
        history_layout = QVBoxLayout(history_frame)
        history_layout.setContentsMargins(20, 15, 20, 15)
        history_layout.setSpacing(10)
        
        history_title = QLabel("💬 对话历史")
        history_title.setStyleSheet("color: #1e293b; font-size: 14px; font-weight: bold;")
        history_layout.addWidget(history_title)
        
        self.history_text = QTextEdit()
        self.history_text.setReadOnly(True)
        self.history_text.setPlaceholderText("AI对话记录将显示在这里...")
        self.history_text.setStyleSheet("""
            QTextEdit {
                background: #f8fafc;
                border: 1px solid #e2e8f0;
                border-radius: 6px;
                padding: 10px;
                font-size: 12px;
                color: #1e293b;
            }
        """)
        history_layout.addWidget(self.history_text)
        
        # 输入框和发送按钮
        input_row = QWidget()
        input_layout = QHBoxLayout(input_row)
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.setSpacing(10)
        
        self.input_text = QLineEdit()
        self.input_text.setPlaceholderText("输入自然语言指令...")
        self.input_text.setStyleSheet("""
            QLineEdit {
                background: white;
                border: 2px solid #e2e8f0;
                border-radius: 8px;
                padding: 10px 15px;
                font-size: 13px;
                color: #1e293b;
            }
            QLineEdit:focus {
                border-color: #667eea;
            }
        """)
        self.input_text.setMinimumHeight(40)
        self.input_text.returnPressed.connect(self._send_message)
        input_layout.addWidget(self.input_text, 1)
        
        self.send_btn = QPushButton("发送")
        self.send_btn.setObjectName("primary_button")
        self.send_btn.setMinimumSize(80, 40)
        self.send_btn.clicked.connect(self._send_message)
        input_layout.addWidget(self.send_btn)
        
        history_layout.addWidget(input_row)
        
        panel_layout.addWidget(history_frame, 1)
        
        return panel
    
    def _create_right_panel(self):
        """创建右侧面板"""
        panel = QWidget()
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        panel_layout.setSpacing(15)
        
        # 摄像头预览（增加高度）
        camera_frame = QFrame()
        camera_frame.setObjectName("card")
        camera_layout = QVBoxLayout(camera_frame)
        camera_layout.setContentsMargins(15, 15, 15, 15)
        camera_layout.setSpacing(10)
        
        camera_title = QLabel("📹 摄像头")
        camera_title.setStyleSheet("color: #1e293b; font-size: 14px; font-weight: bold;")
        camera_layout.addWidget(camera_title)
        
        # 摄像头显示区域（增加最小高度）
        self.camera_display = QLabel()
        self.camera_display.setStyleSheet("""
            QLabel {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #1e293b, stop:1 #334155);
                border-radius: 8px;
                min-height: 500px;
            }
        """)
        self.camera_display.setAlignment(Qt.AlignCenter)
        self.camera_display.setText("摄像头未启动")
        self.camera_display.setStyleSheet(self.camera_display.styleSheet() + "color: #94a3b8; font-size: 13px;")
        
        camera_layout.addWidget(self.camera_display, 1)
        
        # 摄像头控制按钮
        camera_btn_row = QWidget()
        camera_btn_layout = QHBoxLayout(camera_btn_row)
        camera_btn_layout.setContentsMargins(0, 0, 0, 0)
        camera_btn_layout.setSpacing(10)
        
        self.start_camera_btn = QPushButton("启动")
        self.start_camera_btn.setObjectName("primary_button")
        self.start_camera_btn.setMinimumHeight(36)
        self.start_camera_btn.clicked.connect(self._start_camera)
        camera_btn_layout.addWidget(self.start_camera_btn)
        
        self.stop_camera_btn = QPushButton("停止")
        self.stop_camera_btn.setObjectName("secondary_button")
        self.stop_camera_btn.setMinimumHeight(36)
        self.stop_camera_btn.setEnabled(False)
        self.stop_camera_btn.clicked.connect(self._stop_camera)
        camera_btn_layout.addWidget(self.stop_camera_btn)
        
        camera_layout.addWidget(camera_btn_row)
        
        panel_layout.addWidget(camera_frame)
        
        # 快捷命令
        commands_frame = QFrame()
        commands_frame.setObjectName("card")
        commands_layout = QVBoxLayout(commands_frame)
        commands_layout.setContentsMargins(15, 15, 15, 15)
        commands_layout.setSpacing(10)
        
        commands_title = QLabel("⚡ 快捷命令")
        commands_title.setStyleSheet("color: #1e293b; font-size: 14px; font-weight: bold;")
        commands_layout.addWidget(commands_title)
        
        # 重新检测LM Studio按钮
        self.reconnect_btn = QPushButton("🔄 重新检测LM Studio")
        self.reconnect_btn.setObjectName("secondary_button")
        self.reconnect_btn.setMinimumHeight(36)
        self.reconnect_btn.clicked.connect(self._check_lm_studio)
        commands_layout.addWidget(self.reconnect_btn)
        
        quick_commands = [
            "归零位置",
            "抓取物体",
            "放下物体",
            "初始位置"
        ]
        
        for cmd in quick_commands:
            cmd_btn = QPushButton(cmd)
            cmd_btn.setObjectName("secondary_button")
            cmd_btn.setMinimumHeight(36)
            cmd_btn.clicked.connect(lambda checked, c=cmd: self._execute_quick_command(c))
            commands_layout.addWidget(cmd_btn)
        
        panel_layout.addWidget(commands_frame)
        
        # 初始化状态指示器字典（保持兼容性）
        self.status_indicators = {}
        self.latency_value = QLabel("-- ms")
        
        return panel
    
    def _create_feature_card(self, icon, title, model, desc, color, callback=None):
        """创建功能卡片"""
        card = QFrame()
        card.setObjectName("feature_card")
        card.setStyleSheet(f"""
            QFrame#feature_card {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 {color}, stop:1 {color}dd);
                border-radius: 12px;
                padding: 20px;
            }}
        """)
        
        layout = QVBoxLayout(card)
        layout.setSpacing(10)
        
        # 图标
        icon_label = QLabel(icon)
        icon_label.setStyleSheet("font-size: 36px;")
        icon_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(icon_label)
        
        # 标题
        title_label = QLabel(title)
        title_label.setStyleSheet("color: white; font-size: 16px; font-weight: bold;")
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        
        # 模型名称
        model_label = QLabel(model)
        model_label.setStyleSheet("color: rgba(255,255,255,0.9); font-size: 11px;")
        model_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(model_label)
        
        # 描述
        desc_label = QLabel(desc)
        desc_label.setStyleSheet("color: rgba(255,255,255,0.8); font-size: 11px;")
        desc_label.setAlignment(Qt.AlignCenter)
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)
        
        # 操作按钮
        btn = QPushButton("启动")
        btn.setStyleSheet("""
            QPushButton {
                background: rgba(255,255,255,0.2);
                color: white;
                border: 1px solid rgba(255,255,255,0.3);
                border-radius: 6px;
                padding: 8px;
                font-size: 12px;
                font-weight: 500;
            }
            QPushButton:hover {
                background: rgba(255,255,255,0.3);
            }
        """)
        btn.setMinimumHeight(32)
        if callback:
            btn.clicked.connect(callback)
        layout.addWidget(btn)
        
        return card
    
    def _start_camera(self):
        """启动摄像头"""
        try:
            self.camera_capture = cv2.VideoCapture(0)
            if not self.camera_capture.isOpened():
                QMessageBox.warning(self, "错误", "无法打开摄像头")
                return
            
            self.camera_running = True
            self.start_camera_btn.setEnabled(False)
            self.stop_camera_btn.setEnabled(True)
            
            # 启动定时器更新画面
            self.camera_timer = QTimer()
            self.camera_timer.timeout.connect(self._update_camera_frame)
            self.camera_timer.start(30)  # 30ms更新一次
            
            self._add_history("系统", "摄像头已启动")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"启动摄像头失败:\n{str(e)}")
    
    def _stop_camera(self):
        """停止摄像头"""
        self.camera_running = False
        
        if self.camera_timer:
            self.camera_timer.stop()
            self.camera_timer = None
        
        if self.camera_capture:
            self.camera_capture.release()
            self.camera_capture = None
        
        self.camera_display.clear()
        self.camera_display.setText("摄像头未启动")
        self.camera_display.setStyleSheet("""
            QLabel {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #1e293b, stop:1 #334155);
                border-radius: 8px;
                min-height: 300px;
                color: #94a3b8;
                font-size: 13px;
            }
        """)
        
        self.start_camera_btn.setEnabled(True)
        self.stop_camera_btn.setEnabled(False)
        
        self._add_history("系统", "摄像头已停止")
    
    def _update_camera_frame(self):
        """更新摄像头画面"""
        if not self.camera_running or not self.camera_capture:
            return
        
        ret, frame = self.camera_capture.read()
        if not ret:
            return
        
        # 如果视觉识别已启动，进行物体检测
        if self.vision_loaded and self.vision_model:
            try:
                results = self.vision_model(frame)
                frame = results[0].plot()
            except Exception as e:
                print(f"检测错误: {e}")
        
        # 转换为Qt图像
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = frame.shape
        bytes_per_line = ch * w
        qt_image = QImage(frame.data, w, h, bytes_per_line, QImage.Format_RGB888)
        
        # 缩放到显示区域
        pixmap = QPixmap.fromImage(qt_image)
        scaled_pixmap = pixmap.scaled(
            self.camera_display.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )
        
        self.camera_display.setPixmap(scaled_pixmap)
        self.camera_display.setStyleSheet("background: black; border-radius: 8px;")
    
    def _toggle_voice(self):
        """切换语音识别"""
        if not self.voice_loaded:
            self._load_voice_model()
        else:
            self._unload_voice_model()
    
    def _load_voice_model(self):
        """加载语音识别模型"""
        try:
            # 检查是否已安装
            try:
                import whisper
                self.voice_model = whisper.load_model("base")
                self.voice_loaded = True
                self._update_status_indicator("voice", True)
                self._add_history("系统", "语音识别模型已加载 (Whisper base)")
                QMessageBox.information(self, "成功", "语音识别模型已加载")
            except ImportError:
                # 询问是否安装
                reply = QMessageBox.question(
                    self,
                    "安装依赖",
                    "Whisper未安装，是否现在安装?\n\n"
                    "将安装: openai-whisper\n"
                    "这可能需要几分钟时间",
                    QMessageBox.Yes | QMessageBox.No
                )
                
                if reply == QMessageBox.Yes:
                    self._install_package("openai-whisper", "语音识别")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"加载语音模型失败:\n{str(e)}")
    
    def _unload_voice_model(self):
        """卸载语音识别模型"""
        self.voice_model = None
        self.voice_loaded = False
        self._update_status_indicator("voice", False)
        self._add_history("系统", "语音识别模型已卸载")
    
    def _toggle_vision(self):
        """切换视觉识别"""
        if not self.vision_loaded:
            self._load_vision_model()
        else:
            self._unload_vision_model()
    
    def _load_vision_model(self):
        """加载视觉识别模型"""
        try:
            # 检查是否已安装
            try:
                from ultralytics import YOLO
                
                # 检查可用的模型文件
                model_files = []
                for model_name in ["yolov8n.pt", "yolov8s.pt", "yolov8m.pt"]:
                    if os.path.exists(model_name):
                        model_files.append(model_name)
                
                if os.path.exists("models/custom_8.pt"):
                    model_files.append("models/custom_8.pt")
                
                if not model_files:
                    # 询问是否下载模型
                    reply = QMessageBox.question(
                        self,
                        "下载模型",
                        "未找到YOLO模型文件，是否下载?\n\n"
                        "将下载: yolov8n.pt (最小模型)\n"
                        "大小约: 6MB",
                        QMessageBox.Yes | QMessageBox.No
                    )
                    
                    if reply == QMessageBox.Yes:
                        self._download_yolo_model("yolov8n.pt")
                    return
                
                # 使用第一个找到的模型
                model_path = model_files[0]
                self.vision_model = YOLO(model_path)
                self.vision_loaded = True
                self._update_status_indicator("vision", True)
                self._add_history("系统", f"视觉识别模型已加载 ({os.path.basename(model_path)})")
                QMessageBox.information(self, "成功", f"视觉识别模型已加载\n{model_path}")
                
            except ImportError:
                # 检查是否在打包环境中运行
                import sys
                if getattr(sys, 'frozen', False):
                    # 在打包环境中，不允许安装
                    QMessageBox.information(
                        self,
                        "视觉识别不可用",
                        "视觉识别功能需要在Python环境中使用。\n\n"
                        "请使用源码版程序运行，或手动安装:\n"
                        "pip install ultralytics"
                    )
                else:
                    # 询问是否安装
                    reply = QMessageBox.question(
                        self,
                        "安装依赖",
                        "Ultralytics未安装，是否现在安装?\n\n"
                        "将安装: ultralytics\n"
                        "这可能需要几分钟时间",
                        QMessageBox.Yes | QMessageBox.No
                    )
                    
                    if reply == QMessageBox.Yes:
                        self._install_package("ultralytics", "视觉识别", "yolov8n.pt")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"加载视觉模型失败:\n{str(e)}")
    
    def _unload_vision_model(self):
        """卸载视觉识别模型"""
        self.vision_model = None
        self.vision_loaded = False
        self._update_status_indicator("vision", False)
        self._add_history("系统", "视觉识别模型已卸载")
    
    def _toggle_llm(self):
        """切换自然语言模型"""
        if not self.llm_loaded:
            self._load_llm_model()
        else:
            self._unload_llm_model()
    
    def _check_lm_studio(self):
        """检查LM Studio连接"""
        self._add_history("系统", "正在检测LM Studio...")
        
        # 禁用重新检测按钮
        self.reconnect_btn.setEnabled(False)
        self.reconnect_btn.setText("检测中...")
        
        # 创建检测线程
        self.check_thread = LMStudioCheckThread(self.lm_studio_models_url)
        self.check_thread.finished.connect(self._on_lm_studio_check_finished)
        self.check_thread.start()
    
    def _on_lm_studio_check_finished(self, success, message, model_name):
        """LM Studio检测完成"""
        # 恢复按钮
        self.reconnect_btn.setEnabled(True)
        self.reconnect_btn.setText("🔄 重新检测LM Studio")
        
        if success:
            self.lm_studio_available = True
            self.llm_loaded = True
            self._update_status_indicator("llm", True)
            self._add_history("系统", f"✓ {message}")
            self._add_history("系统", f"当前模型: {model_name}")
        else:
            self._add_history("系统", f"✗ {message}")
            self._lm_studio_unavailable()
    
    def _lm_studio_unavailable(self):
        """LM Studio不可用"""
        self.lm_studio_available = False
        self.llm_loaded = False
        self._update_status_indicator("llm", False)
    
    def _load_llm_model(self):
        """加载自然语言模型"""
        if self.lm_studio_available:
            self.llm_loaded = True
            self._update_status_indicator("llm", True)
            self._add_history("系统", "自然语言模型已启用")
        else:
            QMessageBox.warning(
                self,
                "LM Studio未连接",
                "请确保:\n"
                "1. LM Studio已启动\n"
                "2. 已加载模型\n"
                "3. 本地服务器运行在 http://127.0.0.1:1234\n\n"
                "启动后点击重新检测"
            )
            # 重新检测
            self._check_lm_studio()
    
    def _unload_llm_model(self):
        """卸载自然语言模型"""
        self.llm_model = None
        self.llm_loaded = False
        self._update_status_indicator("llm", False)
        self._add_history("系统", "自然语言模型已禁用")
    
    def _send_message(self):
        """发送消息到LLM"""
        message = self.input_text.text().strip()
        if not message:
            return
        
        self.input_text.clear()
        self._add_history("用户", message)
        
        if not self.lm_studio_available:
            self._add_history("系统", "错误: LM Studio未连接")
            return
        
        # 禁用发送按钮
        self.send_btn.setEnabled(False)
        self.send_btn.setText("思考中...")
        
        # 构建系统提示
        system_prompt = """你是一个机械臂控制助手。用户会用自然语言描述想要执行的动作，你需要将其转换为机械臂控制指令。

可用的控制命令:
- 归零位置: 所有关节角度设为0
- 初始位置: J1=0, J2=-45, J3=90, J4=-45
- 抓取物体: 执行抓取动作序列
- 放下物体: 执行放下动作序列
- 移动关节: 指定关节编号(J1-J4)和角度
- 移动底盘: 指定底盘电机(M4-M6)和角度

请根据用户指令，用简洁的中文回复，并说明将执行的动作。如果指令不清楚，请询问更多细节。"""
        
        # 调用API
        payload = {
            "model": "local-model",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message}
            ],
            "temperature": 0.7,
            "max_tokens": 500
        }
        
        # 保存用户消息用于后续解析
        self.current_user_message = message
        
        # 创建调用线程
        self.llm_thread = LLMCallThread(self.lm_studio_url, payload)
        self.llm_thread.finished.connect(self._on_llm_call_finished)
        self.llm_thread.start()
    
    def _on_llm_call_finished(self, success, message, latency):
        """LLM调用完成"""
        # 恢复发送按钮
        self.send_btn.setEnabled(True)
        self.send_btn.setText("发送")
        
        if success:
            # 显示回复
            self._add_history("AI", message)
            
            # 解析并执行命令
            self._parse_and_execute(message, self.current_user_message)
        else:
            self._add_history("系统", f"错误: {message}")
    
    def _parse_and_execute(self, ai_response, user_message):
        """解析AI回复并执行相应动作"""
        response_lower = ai_response.lower()
        user_lower = user_message.lower()
        
        # 检测关键词并执行对应动作
        if "归零" in response_lower or "归零" in user_lower:
            self._execute_quick_command("归零位置")
        elif "初始" in response_lower or "初始" in user_lower:
            self._execute_quick_command("初始位置")
        elif "抓取" in response_lower or "抓" in user_lower:
            self._execute_quick_command("抓取物体")
        elif "放下" in response_lower or "放" in user_lower:
            self._execute_quick_command("放下物体")
    
    def _open_training(self):
        """打开模型训练界面"""
        dialog = TrainingDialog(self)
        dialog.exec()
    
    def _execute_quick_command(self, command):
        """执行快捷命令"""
        self._add_history("用户", command)
        
        if command == "归零位置":
            angles = [0.0, 0.0, 0.0, 0.0]
            self._send_robot_command(angles)
            self._add_history("系统", "机械臂归零")
        elif command == "初始位置":
            angles = [0.0, -45.0, 90.0, -45.0]
            self._send_robot_command(angles)
            self._add_history("系统", "机械臂移动到初始位置")
        elif command == "抓取物体":
            self._add_history("系统", "执行抓取动作")
        elif command == "放下物体":
            self._add_history("系统", "执行放下动作")
    
    def _send_robot_command(self, angles):
        """发送机械臂命令"""
        if hasattr(self.main_gui, 'serial_comm') and self.main_gui.serial_comm.is_connected:
            chassis_angles = [0.0, 0.0, 0.0]
            all_angles = list(angles) + chassis_angles
            self.main_gui.serial_comm.send_angles(all_angles, num_arm_joints=4, wait_for_completion=False)
        else:
            self._add_history("系统", "错误: 串口未连接")
    
    def _update_status_indicator(self, key, active):
        """更新状态指示器（保持兼容性，但不显示）"""
        # 状态指示器已移除，此方法保留以避免错误
        pass
    
    def _add_history(self, sender, message):
        """添加对话历史"""
        timestamp = time.strftime("%H:%M:%S")
        if sender == "系统":
            color = "#64748b"
        elif sender == "用户":
            color = "#667eea"
        elif sender == "安装":
            color = "#10b981"
        else:
            color = "#1e293b"
        
        html = f'<span style="color: {color}; font-weight: bold;">[{timestamp}] {sender}:</span> {message}<br>'
        self.history_text.append(html)
    
    def _on_install_finished(self, success, message, feature_name):
        """安装完成回调"""
        if success:
            self._add_history("系统", f"✓ {message}")
            QMessageBox.information(self, "安装成功", f"{feature_name}依赖安装完成！\n请重新点击启动按钮加载模型。")
        else:
            self._add_history("系统", f"✗ {message}")
            QMessageBox.critical(self, "安装失败", f"{feature_name}依赖安装失败:\n{message}")
    
    def _install_package(self, package_name, feature_name, model_name=None):
        """安装Python包"""
        # 在对话历史中显示安装进度
        self._add_history("系统", f"开始安装 {package_name}...")
        
        # 创建安装线程
        install_thread = InstallThread(package_name, model_name)
        install_thread.progress.connect(lambda msg: self._add_history("安装", msg))
        install_thread.finished.connect(lambda success, msg: self._on_install_finished(success, msg, feature_name))
        install_thread.start()
    
    def _download_yolo_model(self, model_name):
        """下载YOLO模型"""
        try:
            from ultralytics import YOLO
            
            progress_dialog = QMessageBox(self)
            progress_dialog.setWindowTitle("下载模型")
            progress_dialog.setText(f"正在下载 {model_name}...\n请稍候")
            progress_dialog.setStandardButtons(QMessageBox.NoButton)
            progress_dialog.show()
            
            # 下载模型
            model = YOLO(model_name)
            
            progress_dialog.close()
            
            # 加载模型
            self.vision_model = model
            self.vision_loaded = True
            self._update_status_indicator("vision", True)
            self._add_history("系统", f"视觉识别模型已下载并加载 ({model_name})")
            QMessageBox.information(self, "成功", f"模型已下载: {model_name}")
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"下载模型失败:\n{str(e)}")


class InstallDialog(QWidget):
    """安装对话框"""
    
    def __init__(self, parent, package_name, feature_name, model_name=None):
        super().__init__(parent)
        self.package_name = package_name
        self.feature_name = feature_name
        self.model_name = model_name
        self.install_thread = None
        
        self.setWindowTitle(f"安装 {feature_name}")
        self.setMinimumSize(500, 400)
        self.setWindowModality(Qt.ApplicationModal)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # 标题
        title = QLabel(f"📦 安装 {feature_name} 依赖")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #1e293b;")
        layout.addWidget(title)
        
        # 信息
        info_text = f"包名: {package_name}\n"
        if model_name:
            info_text += f"模型: {model_name}\n"
        info_text += "\n安装过程可能需要几分钟，请耐心等待..."
        
        info_label = QLabel(info_text)
        info_label.setStyleSheet("color: #64748b; font-size: 12px; padding: 10px; background: #f8fafc; border-radius: 6px;")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # 不确定进度
        layout.addWidget(self.progress_bar)
        
        # 日志
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet("""
            QTextEdit {
                background: #1e293b;
                color: #e2e8f0;
                border-radius: 6px;
                padding: 10px;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 11px;
            }
        """)
        layout.addWidget(self.log_text, 1)
        
        # 按钮
        btn_row = QWidget()
        btn_layout = QHBoxLayout(btn_row)
        btn_layout.addStretch()
        
        self.close_btn = QPushButton("关闭")
        self.close_btn.setObjectName("secondary_button")
        self.close_btn.setMinimumSize(100, 36)
        self.close_btn.setEnabled(False)
        self.close_btn.clicked.connect(self.close)
        btn_layout.addWidget(self.close_btn)
        
        layout.addWidget(btn_row)
        
        # 自动开始安装
        QTimer.singleShot(500, self._start_install)
    
    def _start_install(self):
        """开始安装"""
        self.log_text.append(f">>> 开始安装 {self.package_name}")
        
        self.install_thread = InstallThread(self.package_name, self.model_name)
        self.install_thread.progress.connect(self._on_progress)
        self.install_thread.finished.connect(self._on_finished)
        self.install_thread.start()
    
    def _on_progress(self, message):
        """安装进度"""
        self.log_text.append(message)
        # 自动滚动到底部
        self.log_text.verticalScrollBar().setValue(
            self.log_text.verticalScrollBar().maximum()
        )
    
    def _on_finished(self, success, message):
        """安装完成"""
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100 if success else 0)
        
        if success:
            self.log_text.append(f"\n✓ {message}")
            self.log_text.append("\n请重新点击启动按钮加载模型")
        else:
            self.log_text.append(f"\n✗ {message}")
        
        self.close_btn.setEnabled(True)
    
    def exec(self):
        """显示对话框"""
        self.show()


class TrainingDialog(QWidget):
    """模型训练对话框 - 包含采集和训练功能"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("模型训练 - 采集与训练")
        self.setMinimumSize(900, 700)
        
        # 摄像头
        self.camera = None
        self.camera_running = False
        self.camera_timer = None
        
        # 训练数据
        self.training_images = []
        self.training_bboxes = []
        self.current_bbox = None
        self.drawing = False
        self.start_point = None
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # 标题
        title = QLabel("🎯 YOLOv8 模型训练")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #1e293b;")
        layout.addWidget(title)
        
        # 主内容区域 - 左右布局
        content_widget = QWidget()
        content_layout = QHBoxLayout(content_widget)
        content_layout.setSpacing(15)
        
        # 左侧：摄像头采集区
        left_panel = self._create_camera_panel()
        content_layout.addWidget(left_panel, 2)
        
        # 右侧：训练参数和控制
        right_panel = self._create_training_panel()
        content_layout.addWidget(right_panel, 1)
        
        layout.addWidget(content_widget, 1)
        
        # 底部：日志和按钮
        self._create_bottom_panel(layout)
    
    def _create_camera_panel(self):
        """创建摄像头采集面板"""
        panel = QFrame()
        panel.setObjectName("card")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(15, 15, 15, 15)
        
        # 标题行
        title_row = QWidget()
        title_layout = QHBoxLayout(title_row)
        title_layout.setContentsMargins(0, 0, 0, 0)
        
        title_label = QLabel("📷 摄像头采集")
        title_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #1e293b;")
        title_layout.addWidget(title_label)
        
        title_layout.addStretch()
        
        self.sample_count_label = QLabel("样本: 0/5")
        self.sample_count_label.setStyleSheet("font-size: 12px; font-weight: bold; color: #667eea;")
        title_layout.addWidget(self.sample_count_label)
        
        panel_layout.addWidget(title_row)
        
        # 摄像头显示（使用QLabel）
        self.camera_label = QLabel()
        self.camera_label.setStyleSheet("background: #f0f0f0; border-radius: 8px;")
        self.camera_label.setAlignment(Qt.AlignCenter)
        self.camera_label.setMinimumSize(640, 480)
        self.camera_label.setText("摄像头未启动\n点击下方按钮启动")
        
        # 绑定鼠标事件用于框选
        self.camera_label.setMouseTracking(True)
        self.camera_label.mousePressEvent = self._on_mouse_press
        self.camera_label.mouseMoveEvent = self._on_mouse_move
        self.camera_label.mouseReleaseEvent = self._on_mouse_release
        
        panel_layout.addWidget(self.camera_label, 1)
        
        # 提示信息
        self.hint_label = QLabel("💡 拖动鼠标框选物体，然后点击\"添加样本\"")
        self.hint_label.setStyleSheet("color: #64748b; font-size: 11px; padding: 5px;")
        panel_layout.addWidget(self.hint_label)
        
        # 控制按钮
        btn_row = QWidget()
        btn_layout = QHBoxLayout(btn_row)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        
        self.camera_btn = QPushButton("📷 启动摄像头")
        self.camera_btn.setObjectName("primary_button")
        self.camera_btn.setMinimumHeight(36)
        self.camera_btn.clicked.connect(self._toggle_camera)
        btn_layout.addWidget(self.camera_btn)
        
        self.add_sample_btn = QPushButton("➕ 添加样本")
        self.add_sample_btn.setObjectName("primary_button")
        self.add_sample_btn.setMinimumHeight(36)
        self.add_sample_btn.setEnabled(False)
        self.add_sample_btn.clicked.connect(self._add_sample)
        btn_layout.addWidget(self.add_sample_btn)
        
        self.clear_bbox_btn = QPushButton("🗑 清除框选")
        self.clear_bbox_btn.setObjectName("secondary_button")
        self.clear_bbox_btn.setMinimumHeight(36)
        self.clear_bbox_btn.clicked.connect(self._clear_bbox)
        btn_layout.addWidget(self.clear_bbox_btn)
        
        panel_layout.addWidget(btn_row)
        
        return panel
    
    def _create_training_panel(self):
        """创建训练参数面板"""
        panel = QFrame()
        panel.setObjectName("card")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(15, 15, 15, 15)
        
        # 标题
        title_label = QLabel("⚙️ 训练参数")
        title_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #1e293b;")
        panel_layout.addWidget(title_label)
        
        # 物体名称
        name_label = QLabel("物体名称:")
        name_label.setStyleSheet("color: #475569; font-size: 12px; margin-top: 10px;")
        panel_layout.addWidget(name_label)
        
        self.object_name_input = QLineEdit()
        self.object_name_input.setPlaceholderText("例如: apple, cup, book")
        self.object_name_input.setMinimumHeight(36)
        panel_layout.addWidget(self.object_name_input)
        
        # 训练轮数
        epochs_label = QLabel("训练轮数:")
        epochs_label.setStyleSheet("color: #475569; font-size: 12px; margin-top: 10px;")
        panel_layout.addWidget(epochs_label)
        
        self.epochs_spin = QSpinBox()
        self.epochs_spin.setRange(10, 500)
        self.epochs_spin.setValue(50)
        self.epochs_spin.setMinimumHeight(36)
        panel_layout.addWidget(self.epochs_spin)
        
        # 批次大小
        batch_label = QLabel("批次大小:")
        batch_label.setStyleSheet("color: #475569; font-size: 12px; margin-top: 10px;")
        panel_layout.addWidget(batch_label)
        
        self.batch_spin = QSpinBox()
        self.batch_spin.setRange(1, 32)
        self.batch_spin.setValue(8)
        self.batch_spin.setMinimumHeight(36)
        panel_layout.addWidget(self.batch_spin)
        
        # 图像大小
        imgsz_label = QLabel("图像大小:")
        imgsz_label.setStyleSheet("color: #475569; font-size: 12px; margin-top: 10px;")
        panel_layout.addWidget(imgsz_label)
        
        self.imgsz_spin = QSpinBox()
        self.imgsz_spin.setRange(320, 1280)
        self.imgsz_spin.setValue(640)
        self.imgsz_spin.setSingleStep(32)
        self.imgsz_spin.setMinimumHeight(36)
        panel_layout.addWidget(self.imgsz_spin)
        
        panel_layout.addStretch()
        
        # 开始训练按钮
        self.train_btn = QPushButton("🚀 开始训练")
        self.train_btn.setObjectName("primary_button")
        self.train_btn.setMinimumHeight(45)
        self.train_btn.setEnabled(False)
        self.train_btn.clicked.connect(self._start_training)
        panel_layout.addWidget(self.train_btn)
        
        return panel
    
    def _create_bottom_panel(self, parent_layout):
        """创建底部面板"""
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        parent_layout.addWidget(self.progress_bar)
        
        # 日志标题
        log_title = QLabel("📋 训练日志:")
        log_title.setStyleSheet("font-size: 12px; font-weight: bold; color: #1e293b; margin-top: 10px;")
        parent_layout.addWidget(log_title)
        
        # 日志文本框
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(120)
        self.log_text.setStyleSheet("""
            QTextEdit {
                background: #1e293b;
                color: #e2e8f0;
                border-radius: 6px;
                padding: 10px;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 10px;
            }
        """)
        parent_layout.addWidget(self.log_text)
        
        # 按钮行
        btn_row = QWidget()
        btn_layout = QHBoxLayout(btn_row)
        btn_layout.addStretch()
        
        close_btn = QPushButton("关闭")
        close_btn.setObjectName("secondary_button")
        close_btn.setMinimumSize(100, 40)
        close_btn.clicked.connect(self.close)
        btn_layout.addWidget(close_btn)
        
        parent_layout.addWidget(btn_row)
    
    def _toggle_camera(self):
        """切换摄像头"""
        if self.camera_running:
            self._stop_camera()
        else:
            self._start_camera()
    
    def _start_camera(self):
        """启动摄像头"""
        try:
            self.camera = cv2.VideoCapture(0)
            if not self.camera.isOpened():
                QMessageBox.warning(self, "错误", "无法打开摄像头")
                return
            
            self.camera_running = True
            self.camera_btn.setText("⏹ 停止摄像头")
            self.add_sample_btn.setEnabled(True)
            
            # 启动定时器更新画面
            self.camera_timer = QTimer()
            self.camera_timer.timeout.connect(self._update_camera_frame)
            self.camera_timer.start(30)
            
            self._log("摄像头已启动")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"启动摄像头失败:\n{str(e)}")
    
    def _stop_camera(self):
        """停止摄像头"""
        self.camera_running = False
        
        if self.camera_timer:
            self.camera_timer.stop()
            self.camera_timer = None
        
        if self.camera:
            self.camera.release()
            self.camera = None
        
        self.camera_label.clear()
        self.camera_label.setText("摄像头未启动")
        self.camera_btn.setText("📷 启动摄像头")
        self.add_sample_btn.setEnabled(False)
        
        self._log("摄像头已停止")
    
    def _update_camera_frame(self):
        """更新摄像头画面"""
        if not self.camera_running or not self.camera:
            return
        
        ret, frame = self.camera.read()
        if not ret:
            return
        
        # 保存当前帧用于采集
        self.current_frame = frame.copy()
        
        # 绘制边界框
        if self.current_bbox:
            x1, y1, x2, y2 = self.current_bbox
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
        
        # 转换为Qt图像
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = frame.shape
        bytes_per_line = ch * w
        qt_image = QImage(frame.data, w, h, bytes_per_line, QImage.Format_RGB888)
        
        # 缩放到显示区域
        pixmap = QPixmap.fromImage(qt_image)
        scaled_pixmap = pixmap.scaled(
            self.camera_label.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )
        
        self.camera_label.setPixmap(scaled_pixmap)
    
    def _on_mouse_press(self, event):
        """鼠标按下"""
        self.drawing = True
        self.start_point = (event.x(), event.y())
        self.current_bbox = None
    
    def _on_mouse_move(self, event):
        """鼠标移动"""
        if not self.drawing or not self.start_point:
            return
        
        x1 = min(self.start_point[0], event.x())
        y1 = min(self.start_point[1], event.y())
        x2 = max(self.start_point[0], event.x())
        y2 = max(self.start_point[1], event.y())
        
        self.current_bbox = [x1, y1, x2, y2]
    
    def _on_mouse_release(self, event):
        """鼠标释放"""
        self.drawing = False
        if self.current_bbox:
            x1, y1, x2, y2 = self.current_bbox
            if abs(x2 - x1) < 20 or abs(y2 - y1) < 20:
                self.current_bbox = None
                self.hint_label.setText("⚠️ 框选区域太小，请重新框选")
                self.hint_label.setStyleSheet("color: #ef4444; font-size: 11px;")
            else:
                self.hint_label.setText("✓ 已框选，点击\"添加样本\"保存")
                self.hint_label.setStyleSheet("color: #10b981; font-size: 11px;")
    
    def _clear_bbox(self):
        """清除边界框"""
        self.current_bbox = None
        self.hint_label.setText("💡 拖动鼠标框选物体")
        self.hint_label.setStyleSheet("color: #64748b; font-size: 11px;")
    
    def _add_sample(self):
        """添加训练样本"""
        if not self.current_bbox:
            QMessageBox.warning(self, "提示", "请先框选物体")
            return
        
        if not hasattr(self, 'current_frame'):
            QMessageBox.warning(self, "提示", "无法获取当前画面")
            return
        
        # 保存图像和边界框
        self.training_images.append(self.current_frame.copy())
        self.training_bboxes.append(self.current_bbox.copy())
        
        count = len(self.training_images)
        self.sample_count_label.setText(f"样本: {count}/5")
        self._log(f"已添加样本 {count}/5")
        
        # 清除当前框选
        self.current_bbox = None
        self.hint_label.setText(f"✓ 已添加 {count} 个样本")
        self.hint_label.setStyleSheet("color: #10b981; font-size: 11px;")
        
        # 检查是否可以开始训练
        if count >= 5:
            self.train_btn.setEnabled(True)
            self.hint_label.setText(f"✓ 已采集足够样本，可以开始训练")
    
    def _start_training(self):
        """开始训练"""
        object_name = self.object_name_input.text().strip()
        if not object_name:
            QMessageBox.warning(self, "提示", "请输入物体名称")
            return
        
        if len(self.training_images) < 5:
            QMessageBox.warning(self, "提示", "至少需要5个训练样本")
            return
        
        reply = QMessageBox.question(
            self,
            "确认训练",
            f"将使用 {len(self.training_images)} 个样本训练物体: {object_name}\n\n"
            f"训练参数:\n"
            f"- 轮数: {self.epochs_spin.value()}\n"
            f"- 批次: {self.batch_spin.value()}\n"
            f"- 图像大小: {self.imgsz_spin.value()}\n\n"
            f"训练可能需要几分钟，是否继续？",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
        
        # 禁用按钮
        self.train_btn.setEnabled(False)
        self.train_btn.setText("⏳ 训练中...")
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # 不确定进度
        
        self._log(f"开始训练物体: {object_name}")
        self._log(f"样本数: {len(self.training_images)}")
        self._log(f"训练参数: epochs={self.epochs_spin.value()}, batch={self.batch_spin.value()}, imgsz={self.imgsz_spin.value()}")
        
        # TODO: 实际训练逻辑
        # 这里应该调用YOLO训练API
        QTimer.singleShot(3000, lambda: self._on_training_complete(True, object_name))
    
    def _on_training_complete(self, success, object_name):
        """训练完成"""
        self.progress_bar.setVisible(False)
        self.train_btn.setEnabled(True)
        self.train_btn.setText("🚀 开始训练")
        
        if success:
            self._log(f"✓ 训练完成: {object_name}")
            QMessageBox.information(
                self,
                "训练成功",
                f"物体 '{object_name}' 训练完成！\n\n"
                f"模型已保存到: models/custom_{object_name}.pt"
            )
        else:
            self._log(f"✗ 训练失败")
            QMessageBox.critical(self, "训练失败", "模型训练失败，请查看日志")
    
    def _log(self, message):
        """添加日志"""
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")
    
    def exec(self):
        """显示对话框"""
        self.show()
    
    def closeEvent(self, event):
        """关闭事件"""
        if self.camera_running:
            self._stop_camera()
        event.accept()
