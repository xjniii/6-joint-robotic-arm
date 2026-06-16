#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
机械臂控制主界面 - PySide6版本
现代化设计，流畅动画
"""

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame, QStackedWidget
)
from PySide6.QtCore import Qt, QTimer, QSize
from PySide6.QtGui import QIcon, QFont, QPixmap, QImage

# 导入原有模块
import sys
import os
from modules_pyside6.serial_communication import SerialCommunication
from modules_pyside6.kinematics import Kinematics
from modules_pyside6.gesture_recognition import GestureRecognition


class RobotControlGUI(QMainWindow):
    """机械臂控制主界面"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("XJNIII - 机械臂控制系统")
        self.setMinimumSize(1200, 800)
        
        # 设置窗口图标
        icon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "漂亮图标", "手.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        
        # 硬件配置
        self.NUM_ARM_JOINTS = 4  # 机械臂关节数量（M0-M3）
        self.NUM_BASE_MOTORS = 3  # 底盘电机数量（M4-M6）
        self.TOTAL_MOTORS = 7  # 总电机数量
        
        # 初始化模块
        self.serial_comm = SerialCommunication(
            num_motors=self.TOTAL_MOTORS,
            gear_ratio_arm=100.0,
            gear_ratio_base=37.1
        )
        self.kinematics = Kinematics()
        self.gesture = GestureRecognition()
        
        # 状态变量
        self.current_page = "live_control"
        self.joint_angles = [0.0] * 4  # 4个关节（M0-M3）
        self.speed_percent = 23
        
        # 底盘轮子角度（电机4-6）
        self.chassis_wheel_angles = [0.0, 0.0, 0.0]  # M4, M5, M6
        self.chassis_step_deg = 10.0  # 底盘角度步长
        
        # 键盘和手柄控制状态
        self.key_pressed = {}  # 记录按键状态
        self.chassis_moving = False  # 底盘是否正在移动
        self.chassis_target_angles = [0.0, 0.0, 0.0]  # 底盘目标角度
        self.gamepad_connected = False  # 手柄连接状态
        
        # 创建界面
        self._init_ui()
        
        # 启动反馈处理
        self._start_feedback_loop()
        
        # 应用样式表
        self._apply_stylesheet()
    
    def _init_ui(self):
        """初始化UI"""
        # 中心部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 主布局
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # 创建顶部导航栏
        self._create_navbar(main_layout)
        
        # 创建页面容器
        self.page_container = QStackedWidget()
        main_layout.addWidget(self.page_container)
        
        # 创建页面（暂时使用占位符）
        self._create_pages()
    
    def _create_navbar(self, layout):
        """创建顶部导航栏"""
        navbar = QFrame()
        navbar.setObjectName("navbar")
        navbar.setFixedHeight(70)
        
        navbar_layout = QHBoxLayout(navbar)
        navbar_layout.setContentsMargins(20, 0, 20, 0)
        navbar_layout.setSpacing(10)
        
        # Logo和标题
        logo_widget = QWidget()
        logo_layout = QHBoxLayout(logo_widget)
        logo_layout.setContentsMargins(0, 0, 0, 0)
        logo_layout.setSpacing(15)
        
        # 使用图标替代 emoji（通过编程去除白色背景）
        logo_label = QLabel()
        icon_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "漂亮图标")
        icon_path = os.path.join(icon_dir, "手.png")
        
        if os.path.exists(icon_path):
            image = QImage(icon_path)
            image = image.convertToFormat(QImage.Format_ARGB32)
            
            # 将接近白色的背景设为透明
            for y in range(image.height()):
                for x in range(image.width()):
                    color = image.pixelColor(x, y)
                    if color.red() > 240 and color.green() > 240 and color.blue() > 240:
                        color.setAlpha(0)
                        image.setPixelColor(x, y, color)
            
            logo_pixmap = QPixmap.fromImage(image).scaled(40, 40, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            logo_label.setPixmap(logo_pixmap)
        
        logo_layout.addWidget(logo_label)
        
        title_label = QLabel("XJNIII")
        title_label.setObjectName("title")
        logo_layout.addWidget(title_label)
        
        navbar_layout.addWidget(logo_widget)
        
        # 导航按钮
        nav_buttons_widget = QWidget()
        nav_buttons_layout = QHBoxLayout(nav_buttons_widget)
        nav_buttons_layout.setContentsMargins(0, 0, 0, 0)
        nav_buttons_layout.setSpacing(5)
        
        self.nav_buttons = {}
        nav_items = [
            ("live_control", "实时控制", "Joystick.png"),
            ("blockly", "可视化编程", "Script.png"),
            ("ai_control", "AI控制", "Aria.png"),
            ("remote_control", "远程控制", "Network.png"),
            ("settings", "设置", "Preferences.png")
        ]
        
        for page_id, page_name, icon_file in nav_items:
            btn = QPushButton(f" {page_name}")
            btn.setObjectName("nav_button")
            btn.setCheckable(True)
            btn.setMinimumWidth(130)
            btn.setMinimumHeight(45)
            btn.setCursor(Qt.PointingHandCursor)
            
            # 设置按钮图标
            icon_path = os.path.join(icon_dir, icon_file)
            if os.path.exists(icon_path):
                btn.setIcon(QIcon(icon_path))
                btn.setIconSize(QSize(24, 24))
            
            btn.clicked.connect(lambda checked, p=page_id: self._switch_page(p))
            
            if page_id == "live_control":
                btn.setChecked(True)
            
            nav_buttons_layout.addWidget(btn)
            self.nav_buttons[page_id] = btn
        
        navbar_layout.addWidget(nav_buttons_widget)
        navbar_layout.addStretch()
        
        # AI状态指示器
        ai_status_widget = QWidget()
        ai_status_layout = QHBoxLayout(ai_status_widget)
        ai_status_layout.setContentsMargins(0, 0, 0, 0)
        ai_status_layout.setSpacing(15)
        
        # 语音指示器
        self.voice_indicator = QLabel()
        self.voice_indicator.setObjectName("indicator_off")
        voice_pix = QPixmap(os.path.join(icon_dir, "Microphone.png")).scaled(24, 24, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.voice_indicator.setPixmap(voice_pix)
        ai_status_layout.addWidget(self.voice_indicator)
        
        # 视觉指示器
        self.vision_indicator = QLabel()
        self.vision_indicator.setObjectName("indicator_off")
        vision_pix = QPixmap(os.path.join(icon_dir, "Hardware", "cam.png")).scaled(24, 24, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.vision_indicator.setPixmap(vision_pix)
        ai_status_layout.addWidget(self.vision_indicator)
        
        # AI大脑指示器
        self.llm_indicator = QLabel()
        self.llm_indicator.setObjectName("indicator_off")
        llm_pix = QPixmap(os.path.join(icon_dir, "Aria.png")).scaled(24, 24, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.llm_indicator.setPixmap(llm_pix)
        ai_status_layout.addWidget(self.llm_indicator)
        
        navbar_layout.addWidget(ai_status_widget)
        
        # 紧急停止按钮
        self.stop_button = QPushButton(" STOP")
        self.stop_button.setObjectName("stop_button")
        self.stop_button.setMinimumSize(110, 45)
        self.stop_button.setCursor(Qt.PointingHandCursor)
        
        # 设置停止按钮图标
        stop_icon_path = os.path.join(icon_dir, "Shutdown_01.png")
        if os.path.exists(stop_icon_path):
            self.stop_button.setIcon(QIcon(stop_icon_path))
            self.stop_button.setIconSize(QSize(20, 20))
            
        self.stop_button.clicked.connect(self._emergency_stop)
        navbar_layout.addWidget(self.stop_button)
        
        layout.addWidget(navbar)
    
    def _create_pages(self):
        """创建页面"""
        try:
            # 导入页面
            from .live_control_page import LiveControlPage
            from .blockly_page import BlocklyPage
            from .ai_control_page import AIControlPage
            from .remote_control_page import RemoteControlPage
            from .settings_page import SettingsPage
            
            # 实时控制页面
            live_page = LiveControlPage(self.page_container, self)
            self.page_container.addWidget(live_page)
            
            # Blockly页面
            blockly_page = BlocklyPage(self.page_container, self)
            self.page_container.addWidget(blockly_page)
            
            # AI控制页面
            ai_page = AIControlPage(self.page_container, self)
            self.page_container.addWidget(ai_page)
            
            # 远程控制页面
            remote_page = RemoteControlPage(self.page_container, self)
            self.page_container.addWidget(remote_page)
            
            # 设置页面
            settings_page = SettingsPage(self.page_container, self)
            self.page_container.addWidget(settings_page)
            
            print("所有页面创建成功")
        except Exception as e:
            print(f"创建页面失败: {e}")
            import traceback
            traceback.print_exc()
            
            # 创建错误页面
            error_page = QWidget()
            error_layout = QVBoxLayout(error_page)
            error_label = QLabel(f"页面加载失败\n{str(e)}")
            error_label.setAlignment(Qt.AlignCenter)
            error_label.setStyleSheet("color: #ef4444; font-size: 14px;")
            error_layout.addWidget(error_label)
            self.page_container.addWidget(error_page)
    
    def _switch_page(self, page_id):
        """切换页面"""
        self.current_page = page_id
        
        # 更新按钮状态
        for pid, btn in self.nav_buttons.items():
            btn.setChecked(pid == page_id)
        
        # 切换页面
        page_index = list(self.nav_buttons.keys()).index(page_id)
        self.page_container.setCurrentIndex(page_index)
    
    def _emergency_stop(self):
        """紧急停止"""
        print("紧急停止!")
        # TODO: 实现停止逻辑
    
    def _start_feedback_loop(self):
        """启动反馈处理循环"""
        self.feedback_timer = QTimer()
        self.feedback_timer.timeout.connect(self._process_feedback)
        self.feedback_timer.start(50)  # 50ms间隔
    
    def _process_feedback(self):
        """处理反馈数据（参照serial_xyz_sender.py）"""
        try:
            feedback_list = self.serial_comm.process_feedback(self.NUM_ARM_JOINTS)
            
            # 直接更新界面显示，每个反馈单独处理（参照serial_xyz_sender.py）
            for motor_id, pos_deg, volt in feedback_list:
                # 更新关节角度和电压（M0-M3）
                if motor_id < self.NUM_ARM_JOINTS:
                    self.joint_angles[motor_id] = pos_deg
                    
                    # 立即更新UI显示
                    try:
                        if self.page_container.count() > 0:
                            page = self.page_container.widget(0)
                            if hasattr(page, 'joint_entries') and motor_id < len(page.joint_entries):
                                page.joint_entries[motor_id].setText(f"{pos_deg:.2f}")
                            if hasattr(page, 'joint_feedback_labels') and motor_id < len(page.joint_feedback_labels):
                                page.joint_feedback_labels[motor_id].setText(f"{volt:.2f}")
                    except:
                        pass
                        
                # 更新底盘轮子角度和电压（M4-M6）
                elif motor_id < self.TOTAL_MOTORS:
                    chassis_idx = motor_id - self.NUM_ARM_JOINTS
                    if chassis_idx < 3:
                        self.chassis_wheel_angles[chassis_idx] = pos_deg
                        
                        # 立即更新UI显示
                        try:
                            if self.page_container.count() > 0:
                                page = self.page_container.widget(0)
                                if hasattr(page, 'chassis_entries') and chassis_idx < len(page.chassis_entries):
                                    page.chassis_entries[chassis_idx].setText(f"{pos_deg:.2f}")
                                if hasattr(page, 'chassis_voltage_labels') and chassis_idx < len(page.chassis_voltage_labels):
                                    page.chassis_voltage_labels[chassis_idx].setText(f"{volt:.2f}")
                                # 更新位置显示区域
                                if hasattr(page, 'chassis_pos_labels'):
                                    label_key = f"M{motor_id}"
                                    if label_key in page.chassis_pos_labels:
                                        page.chassis_pos_labels[label_key].setText(f"{pos_deg:.2f}")
                        except:
                            pass
                            
        except Exception as e:
            pass
    
    def _start_gamepad_detection(self):
        """启动手柄检测（手动触发）"""
        try:
            import pygame
            pygame.init()
            pygame.joystick.init()
            
            if pygame.joystick.get_count() > 0:
                self.gamepad = pygame.joystick.Joystick(0)
                self.gamepad.init()
                self.gamepad_connected = True
                print(f"手柄已连接: {self.gamepad.get_name()}")
                
                # 启动手柄轮询
                self.gamepad_timer = QTimer()
                self.gamepad_timer.timeout.connect(self._poll_gamepad)
                self.gamepad_timer.start(50)
                return True
            else:
                print("未检测到手柄")
                return False
        except ImportError:
            print("pygame未安装，手柄功能不可用")
            return False
        except Exception as e:
            print(f"手柄初始化失败: {e}")
            return False
    
    def _poll_gamepad(self):
        """轮询手柄输入"""
        # TODO: 实现手柄轮询逻辑
        pass
    
    def _apply_stylesheet(self):
        """应用样式表"""
        self.setStyleSheet("""
            /* 全局滚动条美化 */
            QScrollBar:vertical {
                border: none;
                background: #f1f5f9;
                width: 8px;
                margin: 0px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: #cbd5e1;
                min-height: 20px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical:hover {
                background: #94a3b8;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }
            
            QScrollBar:horizontal {
                border: none;
                background: #f1f5f9;
                height: 8px;
                margin: 0px;
                border-radius: 4px;
            }
            QScrollBar::handle:horizontal {
                background: #cbd5e1;
                min-width: 20px;
                border-radius: 4px;
            }
            QScrollBar::handle:horizontal:hover {
                background: #94a3b8;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0px;
            }
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
                background: none;
            }

            /* 主窗口 */
            QMainWindow {
                background: #f8fafc;
            }
            
            /* 导航栏 */
            QFrame#navbar {
                background: white;
                border-bottom: 2px solid #f1f5f9;
            }
            
            /* 标题 */
            QLabel#title {
                font-size: 24px;
                font-weight: 800;
                color: #4f46e5;
                letter-spacing: 1px;
            }
            
            /* 导航按钮 */
            QPushButton#nav_button {
                background: transparent;
                border: none;
                border-radius: 10px;
                padding: 10px 18px;
                font-size: 14px;
                font-weight: 600;
                color: #64748b;
                margin: 4px 2px;
            }
            
            QPushButton#nav_button:hover {
                background: #f1f5f9;
                color: #4f46e5;
            }
            
            QPushButton#nav_button:checked {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 #4f46e5,
                    stop:1 #7c3aed
                );
                color: white;
            }
            
            /* AI指示器 */
            QLabel#indicator_off {
                opacity: 0.3;
            }
            
            QLabel#indicator_on {
                opacity: 1.0;
            }
            
            /* 停止按钮 - 增加立体感 */
            QPushButton#stop_button {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #f87171, stop:1 #ef4444);
                color: white;
                border: 1px solid #dc2626;
                border-radius: 10px;
                font-size: 14px;
                font-weight: 800;
                letter-spacing: 1px;
            }
            
            QPushButton#stop_button:hover {
                background: #ef4444;
                border-color: #b91c1c;
            }
            
            QPushButton#stop_button:pressed {
                background: #dc2626;
                padding-top: 2px;
            }
            
            /* 通用卡片样式 - 增加柔和阴影效果 */
            QFrame#card {
                background: white;
                border-radius: 16px;
                border: 1px solid #f1f5f9;
            }
            
            /* 区域标题 */
            QLabel#section_title {
                font-size: 16px;
                font-weight: bold;
                color: #1e293b;
                padding-bottom: 8px;
            }
            
            /* 数值标签 */
            QLabel#value_label {
                font-size: 18px;
                font-weight: bold;
                color: #4f46e5;
            }
            
            /* 关节标签 */
            QLabel#joint_label {
                font-size: 13px;
                font-weight: bold;
                color: #475569;
            }
            
            /* 主要按钮 */
            QPushButton#primary_button {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4f46e5, stop:1 #7c3aed);
                color: white;
                border: none;
                border-radius: 8px;
                font-weight: bold;
                padding: 8px 16px;
                font-size: 13px;
            }
            
            QPushButton#primary_button:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4338ca, stop:1 #6d28d9);
            }
            
            QPushButton#primary_button:disabled {
                background: #cbd5e1;
                color: #94a3b8;
            }
            
            /* 次要按钮 */
            QPushButton#secondary_button {
                background: #f8fafc;
                color: #475569;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                font-weight: 600;
                padding: 8px 16px;
                font-size: 13px;
            }
            
            QPushButton#secondary_button:hover {
                background: #f1f5f9;
                border-color: #cbd5e1;
                color: #1e293b;
            }
            
            QPushButton#secondary_button:disabled {
                color: #cbd5e1;
                border-color: #f1f5f9;
                background: #fafafa;
            }
            
            /* 滑块 */
            QSlider::groove:horizontal {
                height: 6px;
                background: #e2e8f0;
                border-radius: 3px;
            }
            
            QSlider::handle:horizontal {
                background: #4f46e5;
                width: 16px;
                height: 16px;
                margin: -5px 0;
                border-radius: 8px;
            }
            
            QSlider::handle:horizontal:hover {
                background: #4338ca;
            }
            
            /* 输入框 */
            QLineEdit {
                background: #f8fafc;
                border: 2px solid #e2e8f0;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 13px;
                color: #1e293b;
            }
            
            QLineEdit:focus {
                border-color: #4f46e5;
                background: white;
            }
            
            /* 下拉框 */
            QComboBox {
                background: #f8fafc;
                border: 2px solid #e2e8f0;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 13px;
                color: #1e293b;
            }
            
            QComboBox:hover {
                border-color: #cbd5e1;
            }
            
            QComboBox:focus {
                border-color: #4f46e5;
                background: white;
            }
            
            /* 数字输入框 */
            QSpinBox, QDoubleSpinBox {
                background: #f8fafc;
                border: 2px solid #e2e8f0;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 13px;
                color: #1e293b;
            }
            
            QSpinBox:focus, QDoubleSpinBox:focus {
                border-color: #4f46e5;
                background: white;
            }
        """)
    
    def keyPressEvent(self, event):
        """键盘按下事件"""
        from PySide6.QtCore import Qt
        
        # 只在实时控制页面响应键盘
        if self.current_page != "live_control":
            return
        
        key = event.key()
        
        # 底盘控制键：W/A/S/D/Q/E
        chassis_keys = {
            Qt.Key_W: 'w',
            Qt.Key_A: 'a',
            Qt.Key_S: 's',
            Qt.Key_D: 'd',
            Qt.Key_Q: 'q',
            Qt.Key_E: 'e'
        }
        
        if key in chassis_keys:
            key_name = chassis_keys[key]
            if key_name not in self.key_pressed or not self.key_pressed[key_name]:
                self.key_pressed[key_name] = True
                self._start_chassis_continuous_move(key_name)
        
        # 机械臂末端控制键：方向键 + +/-
        arm_keys = {
            Qt.Key_Left: 'left',
            Qt.Key_Right: 'right',
            Qt.Key_Up: 'up',
            Qt.Key_Down: 'down',
            Qt.Key_Plus: 'plus',
            Qt.Key_Minus: 'minus',
            Qt.Key_Equal: 'plus'  # =键作为+的备选
        }
        
        if key in arm_keys:
            key_name = arm_keys[key]
            if key_name not in self.key_pressed or not self.key_pressed[key_name]:
                self.key_pressed[key_name] = True
                self._start_arm_cartesian_move(key_name)
    
    def keyReleaseEvent(self, event):
        """键盘释放事件"""
        from PySide6.QtCore import Qt
        
        key = event.key()
        
        # 底盘控制键
        chassis_keys = {
            Qt.Key_W: 'w',
            Qt.Key_A: 'a',
            Qt.Key_S: 's',
            Qt.Key_D: 'd',
            Qt.Key_Q: 'q',
            Qt.Key_E: 'e'
        }
        
        if key in chassis_keys:
            key_name = chassis_keys[key]
            if key_name in self.key_pressed:
                self.key_pressed[key_name] = False
                self._stop_chassis_continuous_move(key_name)
        
        # 机械臂末端控制键
        arm_keys = {
            Qt.Key_Left: 'left',
            Qt.Key_Right: 'right',
            Qt.Key_Up: 'up',
            Qt.Key_Down: 'down',
            Qt.Key_Plus: 'plus',
            Qt.Key_Minus: 'minus',
            Qt.Key_Equal: 'plus'
        }
        
        if key in arm_keys:
            key_name = arm_keys[key]
            if key_name in self.key_pressed:
                self.key_pressed[key_name] = False
                self._stop_arm_cartesian_move(key_name)
    
    def _start_chassis_continuous_move(self, key):
        """开始底盘连续移动"""
        if not self.serial_comm.is_connected:
            print("底盘控制：串口未连接")
            return
        
        speed_percent = float(self.speed_percent)
        max_distance = speed_percent * 10
        
        direction_map = {
            'w': 'forward',
            's': 'backward',
            'a': 'left',
            'd': 'right',
            'q': 'rotate_left',
            'e': 'rotate_right'
        }
        
        direction = direction_map.get(key)
        if direction:
            self._chassis_move_to_max(direction, max_distance)
            self._check_key_state(key, direction, max_distance)
    
    def _check_key_state(self, key, direction, max_distance):
        """检查按键状态，持续移动"""
        if self.key_pressed.get(key, False):
            self._chassis_move_to_max(direction, max_distance)
            QTimer.singleShot(100, lambda: self._check_key_state(key, direction, max_distance))
    
    def _stop_chassis_continuous_move(self, key):
        """停止底盘连续移动"""
        direction_map = {
            'w': 'forward',
            's': 'backward',
            'a': 'left',
            'd': 'right',
            'q': 'rotate_left',
            'e': 'rotate_right'
        }
        
        direction = direction_map.get(key)
        if direction:
            self._chassis_add_offset(direction, 10.0)
    
    def _chassis_move_to_max(self, direction, max_distance):
        """底盘移动到最大距离"""
        if direction == "forward":
            self.chassis_target_angles[0] = self.chassis_wheel_angles[0] - max_distance * 0.866
            self.chassis_target_angles[1] = self.chassis_wheel_angles[1]
            self.chassis_target_angles[2] = self.chassis_wheel_angles[2] + max_distance * 0.866
        elif direction == "backward":
            self.chassis_target_angles[0] = self.chassis_wheel_angles[0] + max_distance * 0.866
            self.chassis_target_angles[1] = self.chassis_wheel_angles[1]
            self.chassis_target_angles[2] = self.chassis_wheel_angles[2] - max_distance * 0.866
        elif direction == "left":
            self.chassis_target_angles[0] = self.chassis_wheel_angles[0] - max_distance * 0.5
            self.chassis_target_angles[1] = self.chassis_wheel_angles[1] + max_distance
            self.chassis_target_angles[2] = self.chassis_wheel_angles[2] - max_distance * 0.5
        elif direction == "right":
            self.chassis_target_angles[0] = self.chassis_wheel_angles[0] + max_distance * 0.5
            self.chassis_target_angles[1] = self.chassis_wheel_angles[1] - max_distance
            self.chassis_target_angles[2] = self.chassis_wheel_angles[2] + max_distance * 0.5
        elif direction == "rotate_left":
            self.chassis_target_angles[0] = self.chassis_wheel_angles[0] - max_distance
            self.chassis_target_angles[1] = self.chassis_wheel_angles[1] - max_distance
            self.chassis_target_angles[2] = self.chassis_wheel_angles[2] - max_distance
        elif direction == "rotate_right":
            self.chassis_target_angles[0] = self.chassis_wheel_angles[0] + max_distance
            self.chassis_target_angles[1] = self.chassis_wheel_angles[1] + max_distance
            self.chassis_target_angles[2] = self.chassis_wheel_angles[2] + max_distance
        
        self._send_chassis_command(self.chassis_target_angles)
    
    def _chassis_add_offset(self, direction, offset):
        """在当前反馈位置基础上添加偏移量"""
        current_angles = self.chassis_wheel_angles.copy()
        
        if direction == "forward":
            current_angles[0] -= offset * 0.866
            current_angles[2] += offset * 0.866
        elif direction == "backward":
            current_angles[0] += offset * 0.866
            current_angles[2] -= offset * 0.866
        elif direction == "left":
            current_angles[0] -= offset * 0.5
            current_angles[1] += offset
            current_angles[2] -= offset * 0.5
        elif direction == "right":
            current_angles[0] += offset * 0.5
            current_angles[1] -= offset
            current_angles[2] += offset * 0.5
        elif direction == "rotate_left":
            current_angles[0] -= offset
            current_angles[1] -= offset
            current_angles[2] -= offset
        elif direction == "rotate_right":
            current_angles[0] += offset
            current_angles[1] += offset
            current_angles[2] += offset
        
        self._send_chassis_command(current_angles)
    
    def _send_chassis_command(self, angles):
        """发送底盘命令"""
        if self.serial_comm.is_connected:
            all_angles = list(self.joint_angles) + list(angles)
            self.serial_comm.send_angles(all_angles, num_arm_joints=self.NUM_ARM_JOINTS, wait_for_completion=False)
    
    def _start_arm_cartesian_move(self, key):
        """开始机械臂末端笛卡尔空间移动"""
        if not self.serial_comm.is_connected:
            print("机械臂控制：串口未连接")
            return
        
        step = 50.0  # 每次移动50mm
        
        try:
            current_pos = self.kinematics.forward_kinematics(self.joint_angles)
            target_pos = current_pos.copy()
            
            if key == 'left':
                target_pos[0] -= step
            elif key == 'right':
                target_pos[0] += step
            elif key == 'up':
                target_pos[1] += step
            elif key == 'down':
                target_pos[1] -= step
            elif key == 'plus':
                target_pos[2] += step
            elif key == 'minus':
                target_pos[2] -= step
            
            new_angles = self.kinematics.inverse_kinematics(target_pos)
            if new_angles:
                self.joint_angles = new_angles
                all_angles = list(self.joint_angles) + list(self.chassis_wheel_angles)
                self.serial_comm.send_angles(all_angles, num_arm_joints=self.NUM_ARM_JOINTS, wait_for_completion=False)
                self._check_arm_key_state(key)
        except Exception as e:
            print(f"机械臂移动错误: {e}")
    
    def _check_arm_key_state(self, key):
        """检查机械臂按键状态"""
        if self.key_pressed.get(key, False):
            self._start_arm_cartesian_move(key)
    
    def _stop_arm_cartesian_move(self, key):
        """停止机械臂末端移动"""
        pass  # 松开按键即停止
    
    def closeEvent(self, event):
        """关闭事件"""
        try:
            # 断开串口
            self.serial_comm.disconnect()
        except Exception as e:
            print(f"清理资源时出错: {e}")
        
        event.accept()
