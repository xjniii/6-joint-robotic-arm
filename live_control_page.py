#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
实时控制页面 - PySide6版本
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QSlider, QLineEdit, QFrame, QGridLayout
)
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QPixmap, QImage
import cv2
import numpy as np


class LiveControlPage(QWidget):
    """实时控制页面"""
    
    def __init__(self, parent, main_gui):
        super().__init__(parent)
        self.main_gui = main_gui
        self._updating_from_feedback = False
        
        # 摄像头相关
        self.cap = None
        self._camera_timer = None
        self._camera_running = False
        
        # 键盘控制状态（参照serial_xyz_sender.py）
        self.selected_motor_var = None  # 将在_init_ui中初始化为QSpinBox
        self.arrow_key_pressed = None  # 记录当前按下的方向键
        
        # 关节角度范围
        self.joint_ranges = [
            (-360, 360),   # J1/M0
            (-118, 120),   # J2/M1
            (-225, 11),    # J3/M2
            (-360, 360),   # J4/M3
        ]
        
        # UI组件
        self.joint_sliders = []
        self.joint_entries = []
        self.joint_target_labels = []
        self.joint_feedback_labels = []  # 电压显示标签
        
        # 电压值平滑滤波（参照serial_xyz_sender.py，直接显示但需要稳定）
        self.joint_voltages = [0.0, 0.0, 0.0, 0.0]  # 存储电压值
        self.chassis_voltages = [0.0, 0.0, 0.0]  # 底盘电压值
        self.voltage_history = {i: [] for i in range(7)}  # 电压历史记录
        self.voltage_filter_size = 3  # 电压滤波窗口大小（较小的窗口保持响应性）
        
        # XYZ位置平滑滤波
        self.xyz_history = {'X': [], 'Y': [], 'Z': []}
        self.xyz_filter_size = 5  # 滤波窗口大小
        
        self._init_ui()
    
    def _init_ui(self):
        """初始化UI"""
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)
        
        # 左侧区域
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setSpacing(12)
        self._create_camera_section(left_layout)
        self._create_position_section(left_layout)
        main_layout.addWidget(left_widget, 3)
        
        # 右侧区域
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setSpacing(12)
        self._create_joint_control_section(right_layout)
        self._create_speed_section(right_layout)
        main_layout.addWidget(right_widget, 2)

    
    def _create_camera_section(self, layout):
        """创建摄像头区域"""
        camera_frame = QFrame()
        camera_frame.setObjectName("card")
        camera_layout = QVBoxLayout(camera_frame)
        camera_layout.setContentsMargins(15, 15, 15, 15)
        camera_layout.setSpacing(10)
        
        # 控制按钮行
        controls = QWidget()
        controls_layout = QHBoxLayout(controls)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(8)
        
        self.camera_open_btn = QPushButton("📷 打开摄像头")
        self.camera_open_btn.setObjectName("primary_button")
        self.camera_open_btn.clicked.connect(self._open_camera)
        controls_layout.addWidget(self.camera_open_btn)
        
        self.camera_close_btn = QPushButton("⏹ 关闭")
        self.camera_close_btn.setObjectName("secondary_button")
        self.camera_close_btn.setEnabled(False)
        self.camera_close_btn.clicked.connect(self._close_camera)
        controls_layout.addWidget(self.camera_close_btn)
        
        controls_layout.addStretch()
        camera_layout.addWidget(controls)
        
        # 摄像头显示
        self.camera_label = QLabel("摄像头未启动")
        self.camera_label.setAlignment(Qt.AlignCenter)
        self.camera_label.setMinimumSize(640, 480)
        self.camera_label.setStyleSheet("""
            QLabel {
                background: #2d3748;
                border-radius: 8px;
                color: #a0aec0;
                font-size: 14px;
            }
        """)
        camera_layout.addWidget(self.camera_label)
        
        layout.addWidget(camera_frame)

    
    def _create_position_section(self, layout):
        """创建位置显示区域"""
        pos_frame = QFrame()
        pos_frame.setObjectName("card")
        pos_layout = QHBoxLayout(pos_frame)
        pos_layout.setContentsMargins(15, 15, 15, 15)
        pos_layout.setSpacing(15)
        
        # 左侧：末端位置
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)
        
        title = QLabel("末端位置")
        title.setObjectName("section_title")
        left_layout.addWidget(title)
        
        # XYZ坐标显示
        grid = QGridLayout()
        grid.setSpacing(8)
        
        self.pos_labels = {}
        for i, axis in enumerate(["X", "Y", "Z"]):
            label = QLabel(f"{axis}:")
            label.setStyleSheet("color: #718096; font-size: 12px;")
            grid.addWidget(label, i, 0)
            
            value = QLabel("0")
            value.setObjectName("value_label")
            value.setStyleSheet("font-size: 16px; font-weight: bold; color: #667eea;")
            self.pos_labels[axis] = value
            grid.addWidget(value, i, 1)
            
            unit = QLabel("mm")
            unit.setStyleSheet("color: #a0aec0; font-size: 11px;")
            grid.addWidget(unit, i, 2)
        
        left_layout.addLayout(grid)
        pos_layout.addWidget(left_widget)
        
        # 分隔线
        separator = QFrame()
        separator.setFrameShape(QFrame.VLine)
        separator.setStyleSheet("background: #e2e8f0;")
        separator.setFixedWidth(1)
        pos_layout.addWidget(separator)
        
        # 右侧：底盘位置
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)
        
        chassis_title = QLabel("底盘位置")
        chassis_title.setObjectName("section_title")
        right_layout.addWidget(chassis_title)
        
        # 底盘M4-M6显示
        chassis_grid = QGridLayout()
        chassis_grid.setSpacing(8)
        
        self.chassis_pos_labels = {}
        for i in range(3):
            motor_id = i + 4
            label = QLabel(f"M{motor_id}:")
            label.setStyleSheet("color: #718096; font-size: 12px;")
            chassis_grid.addWidget(label, i, 0)
            
            value = QLabel("0")
            value.setObjectName("value_label")
            value.setStyleSheet("font-size: 16px; font-weight: bold; color: #667eea;")
            self.chassis_pos_labels[f"M{motor_id}"] = value
            chassis_grid.addWidget(value, i, 1)
            
            unit = QLabel("°")
            unit.setStyleSheet("color: #a0aec0; font-size: 11px;")
            chassis_grid.addWidget(unit, i, 2)
        
        right_layout.addLayout(chassis_grid)
        pos_layout.addWidget(right_widget)
        
        layout.addWidget(pos_frame)

    
    def _create_joint_control_section(self, layout):
        """创建关节控制区域"""
        joint_frame = QFrame()
        joint_frame.setObjectName("card")
        joint_layout = QVBoxLayout(joint_frame)
        joint_layout.setContentsMargins(15, 15, 15, 15)
        joint_layout.setSpacing(12)
        
        title = QLabel("关节控制")
        title.setObjectName("section_title")
        joint_layout.addWidget(title)
        
        # 初始化selected_motor_var但不显示（保持兼容性）
        from PySide6.QtWidgets import QSpinBox
        self.selected_motor_var = QSpinBox()
        self.selected_motor_var.setRange(-1, 6)
        self.selected_motor_var.setValue(-1)
        self.selected_motor_var.hide()  # 隐藏不显示
        
        # 添加列标题
        header_widget = QWidget()
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)
        
        # 关节列标题
        joint_header = QLabel("关节")
        joint_header.setStyleSheet("color: #64748b; font-size: 11px; font-weight: bold; min-width: 40px;")
        joint_header.setAlignment(Qt.AlignCenter)
        header_layout.addWidget(joint_header)
        
        # 空白占位（对应滑块）
        header_layout.addWidget(QLabel(""), 1)
        
        # 列标题
        target_header = QLabel("目标")
        target_header.setStyleSheet("color: #64748b; font-size: 11px; font-weight: bold; min-width: 70px;")
        target_header.setAlignment(Qt.AlignCenter)
        header_layout.addWidget(target_header)
        
        feedback_header = QLabel("反馈")
        feedback_header.setStyleSheet("color: #3b82f6; font-size: 11px; font-weight: bold; min-width: 70px;")
        feedback_header.setAlignment(Qt.AlignCenter)
        header_layout.addWidget(feedback_header)
        
        voltage_header = QLabel("电压")
        voltage_header.setStyleSheet("color: #10b981; font-size: 11px; font-weight: bold; min-width: 80px;")
        voltage_header.setAlignment(Qt.AlignCenter)
        header_layout.addWidget(voltage_header)
        
        joint_layout.addWidget(header_widget)
        
        # 创建4个关节控制
        for i in range(4):
            self._create_joint_row(joint_layout, i)
        
        # 底盘电机标题
        chassis_title = QLabel("底盘电机")
        chassis_title.setObjectName("section_title")
        chassis_title.setStyleSheet("margin-top: 10px;")
        joint_layout.addWidget(chassis_title)
        
        # 底盘列标题
        chassis_header_widget = QWidget()
        chassis_header_layout = QHBoxLayout(chassis_header_widget)
        chassis_header_layout.setContentsMargins(0, 0, 0, 0)
        chassis_header_layout.setSpacing(8)
        
        chassis_motor_header = QLabel("电机")
        chassis_motor_header.setStyleSheet("color: #64748b; font-size: 11px; font-weight: bold; min-width: 40px;")
        chassis_motor_header.setAlignment(Qt.AlignCenter)
        chassis_header_layout.addWidget(chassis_motor_header)
        
        chassis_header_layout.addWidget(QLabel(""), 1)
        
        chassis_target_header = QLabel("目标")
        chassis_target_header.setStyleSheet("color: #64748b; font-size: 11px; font-weight: bold; min-width: 70px;")
        chassis_target_header.setAlignment(Qt.AlignCenter)
        chassis_header_layout.addWidget(chassis_target_header)
        
        chassis_feedback_header = QLabel("反馈")
        chassis_feedback_header.setStyleSheet("color: #3b82f6; font-size: 11px; font-weight: bold; min-width: 70px;")
        chassis_feedback_header.setAlignment(Qt.AlignCenter)
        chassis_header_layout.addWidget(chassis_feedback_header)
        
        chassis_voltage_header = QLabel("电压")
        chassis_voltage_header.setStyleSheet("color: #10b981; font-size: 11px; font-weight: bold; min-width: 80px;")
        chassis_voltage_header.setAlignment(Qt.AlignCenter)
        chassis_header_layout.addWidget(chassis_voltage_header)
        
        joint_layout.addWidget(chassis_header_widget)
        
        # 创建3个底盘电机控制
        self.chassis_sliders = []
        self.chassis_entries = []
        for i in range(3):
            self._create_chassis_row(joint_layout, i)
        
        layout.addWidget(joint_frame)
    
    def _create_joint_row(self, layout, index):
        """创建单个关节控制行"""
        row_widget = QWidget()
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(8)
        
        # 标签
        label = QLabel(f"J{index+1}")
        label.setObjectName("joint_label")
        label.setFixedWidth(40)
        label.setAlignment(Qt.AlignCenter)
        row_layout.addWidget(label)
        
        # 滑块
        angle_min, angle_max = self.joint_ranges[index]
        slider = QSlider(Qt.Horizontal)
        slider.setRange(int(angle_min), int(angle_max))
        slider.setValue(0)
        slider.valueChanged.connect(lambda v, idx=index: self._on_slider_change(idx, v))
        self.joint_sliders.append(slider)
        row_layout.addWidget(slider, 1)
        
        # 目标角度值（无标签前缀）
        target_label = QLabel("0°")
        target_label.setStyleSheet("color: #64748b; font-size: 14px; min-width: 70px; font-family: 'Consolas', monospace;")
        target_label.setAlignment(Qt.AlignCenter)
        self.joint_target_labels.append(target_label)
        row_layout.addWidget(target_label)
        
        # 反馈角度值（无标签前缀）
        feedback_label = QLabel("0°")
        feedback_label.setStyleSheet("color: #3b82f6; font-size: 14px; min-width: 70px; font-family: 'Consolas', monospace;")
        feedback_label.setAlignment(Qt.AlignCenter)
        self.joint_entries.append(feedback_label)
        row_layout.addWidget(feedback_label)
        
        # 电压值（无标签前缀）
        voltage_label = QLabel("0.00V")
        voltage_label.setStyleSheet("color: #10b981; font-size: 14px; min-width: 80px; font-family: 'Consolas', monospace;")
        voltage_label.setAlignment(Qt.AlignCenter)
        self.joint_feedback_labels.append(voltage_label)
        row_layout.addWidget(voltage_label)
        
        layout.addWidget(row_widget)

    
    def _create_speed_section(self, layout):
        """创建速度控制区域"""
        speed_frame = QFrame()
        speed_frame.setObjectName("card")
        speed_layout = QVBoxLayout(speed_frame)
        speed_layout.setContentsMargins(15, 15, 15, 15)
        speed_layout.setSpacing(10)
        
        title = QLabel("运动速度")
        title.setObjectName("section_title")
        speed_layout.addWidget(title)
        
        # 速度滑块
        self.speed_slider = QSlider(Qt.Horizontal)
        self.speed_slider.setRange(0, 100)
        self.speed_slider.setValue(23)
        self.speed_slider.valueChanged.connect(self._on_speed_change)
        speed_layout.addWidget(self.speed_slider)
        
        # 速度值显示
        self.speed_label = QLabel("23%")
        self.speed_label.setAlignment(Qt.AlignCenter)
        self.speed_label.setObjectName("value_label")
        speed_layout.addWidget(self.speed_label)
        
        layout.addWidget(speed_frame)
        
        # 底盘控制区域
        self._create_chassis_control_section(layout)
        
        layout.addStretch()
    
    def _create_chassis_control_section(self, layout):
        """创建底盘控制按钮区域"""
        chassis_frame = QFrame()
        chassis_frame.setObjectName("card")
        chassis_layout = QVBoxLayout(chassis_frame)
        chassis_layout.setContentsMargins(15, 15, 15, 15)
        chassis_layout.setSpacing(10)
        
        title = QLabel("底盘控制")
        title.setObjectName("section_title")
        chassis_layout.addWidget(title)
        
        # 提示文字
        hint = QLabel("键盘: WASD移动 QE旋转")
        hint.setStyleSheet("color: #94a3b8; font-size: 11px;")
        hint.setAlignment(Qt.AlignCenter)
        chassis_layout.addWidget(hint)
        
        # 按钮网格
        grid = QGridLayout()
        grid.setSpacing(8)
        
        btn_style = """
            QPushButton {
                background: #f1f5f9;
                border: 2px solid #e2e8f0;
                border-radius: 8px;
                font-size: 16px;
                font-weight: bold;
                color: #475569;
                min-width: 50px;
                min-height: 50px;
            }
            QPushButton:hover {
                background: #e2e8f0;
                border-color: #cbd5e1;
            }
            QPushButton:pressed {
                background: #cbd5e1;
            }
        """
        
        center_btn_style = """
            QPushButton {
                background: white;
                border: 2px solid #667eea;
                border-radius: 8px;
                font-size: 12px;
                font-weight: bold;
                color: #667eea;
                min-width: 50px;
                min-height: 50px;
            }
            QPushButton:hover {
                background: #f0f4ff;
            }
            QPushButton:pressed {
                background: #e0e8ff;
            }
        """
        
        # Q - 左转
        btn_q = QPushButton("Q\n↺")
        btn_q.setStyleSheet(btn_style)
        btn_q.pressed.connect(lambda: self._chassis_key_press('q'))
        btn_q.released.connect(lambda: self._chassis_key_release('q'))
        grid.addWidget(btn_q, 0, 0)
        
        # W - 前进
        btn_w = QPushButton("W\n↑")
        btn_w.setStyleSheet(btn_style)
        btn_w.pressed.connect(lambda: self._chassis_key_press('w'))
        btn_w.released.connect(lambda: self._chassis_key_release('w'))
        grid.addWidget(btn_w, 0, 1)
        
        # E - 右转
        btn_e = QPushButton("E\n↻")
        btn_e.setStyleSheet(btn_style)
        btn_e.pressed.connect(lambda: self._chassis_key_press('e'))
        btn_e.released.connect(lambda: self._chassis_key_release('e'))
        grid.addWidget(btn_e, 0, 2)
        
        # A - 左移
        btn_a = QPushButton("A\n←")
        btn_a.setStyleSheet(btn_style)
        btn_a.pressed.connect(lambda: self._chassis_key_press('a'))
        btn_a.released.connect(lambda: self._chassis_key_release('a'))
        grid.addWidget(btn_a, 1, 0)
        
        # HOME - 归零
        btn_home = QPushButton("HOME")
        btn_home.setStyleSheet(center_btn_style)
        btn_home.clicked.connect(self._chassis_home)
        grid.addWidget(btn_home, 1, 1)
        
        # D - 右移
        btn_d = QPushButton("D\n→")
        btn_d.setStyleSheet(btn_style)
        btn_d.pressed.connect(lambda: self._chassis_key_press('d'))
        btn_d.released.connect(lambda: self._chassis_key_release('d'))
        grid.addWidget(btn_d, 1, 2)
        
        # S - 后退
        btn_s = QPushButton("S\n↓")
        btn_s.setStyleSheet(btn_style)
        btn_s.pressed.connect(lambda: self._chassis_key_press('s'))
        btn_s.released.connect(lambda: self._chassis_key_release('s'))
        grid.addWidget(btn_s, 2, 1)
        
        chassis_layout.addLayout(grid)
        layout.addWidget(chassis_frame)
    
    def _open_camera(self):
        """打开摄像头"""
        try:
            self.cap = cv2.VideoCapture(0)
            if self.cap.isOpened():
                self._camera_running = True
                self.camera_open_btn.setEnabled(False)
                self.camera_close_btn.setEnabled(True)
                
                # 启动定时器
                self._camera_timer = QTimer()
                self._camera_timer.timeout.connect(self._update_camera)
                self._camera_timer.start(33)  # 约30fps
            else:
                self.camera_label.setText("无法打开摄像头")
        except Exception as e:
            self.camera_label.setText(f"错误: {str(e)}")
    
    def _close_camera(self):
        """关闭摄像头"""
        self._camera_running = False
        
        if self._camera_timer:
            self._camera_timer.stop()
            self._camera_timer = None
        
        if self.cap:
            self.cap.release()
            self.cap = None
        
        self.camera_label.clear()
        self.camera_label.setText("摄像头已关闭")
        self.camera_open_btn.setEnabled(True)
        self.camera_close_btn.setEnabled(False)
    
    def _update_camera(self):
        """更新摄像头画面"""
        if not self._camera_running or not self.cap:
            return
        
        ret, frame = self.cap.read()
        if ret:
            # 转换颜色空间
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frame = cv2.flip(frame, 1)  # 镜像
            
            # 调整大小
            h, w, ch = frame.shape
            bytes_per_line = ch * w
            qt_image = QImage(frame.data, w, h, bytes_per_line, QImage.Format_RGB888)
            
            # 缩放到标签大小
            pixmap = QPixmap.fromImage(qt_image)
            scaled_pixmap = pixmap.scaled(
                self.camera_label.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            self.camera_label.setPixmap(scaled_pixmap)

    
    def _on_slider_change(self, index, value):
        """滑块变化"""
        if self._updating_from_feedback:
            return
        
        # 更新目标角度显示（无前缀）
        self.joint_target_labels[index].setText(f"{value}°")
        self.main_gui.joint_angles[index] = float(value)
        self._send_angles()
    
    def _on_entry_change(self, index):
        """输入框变化（已移除，保留方法以兼容）"""
        pass
    
    def _on_speed_change(self, value):
        """速度变化"""
        self.speed_label.setText(f"{value}%")
        self.main_gui.speed_percent = value
    
    def _send_angles(self):
        """发送角度到机械臂"""
        if not self.main_gui.serial_comm.is_connected:
            return
        
        angles = self.main_gui.joint_angles[:4] + self.main_gui.chassis_wheel_angles
        self.main_gui.serial_comm.send_angles(
            angles,
            num_arm_joints=4,
            wait_for_completion=False
        )
    
    def apply_joint_feedback(self, joint_angles, chassis_angles=None):
        """应用反馈数据"""
        self._updating_from_feedback = True
        try:
            for i in range(min(len(joint_angles), len(self.joint_sliders))):
                self.joint_sliders[i].setValue(int(joint_angles[i]))
                self.joint_entries[i].setText(str(int(joint_angles[i])))
        finally:
            self._updating_from_feedback = False

    
    def _create_chassis_row(self, layout, index):
        """创建底盘电机控制行"""
        row_widget = QWidget()
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(8)
        
        # 标签
        label = QLabel(f"M{index+4}")
        label.setObjectName("joint_label")
        label.setFixedWidth(40)
        label.setAlignment(Qt.AlignCenter)
        row_layout.addWidget(label)
        
        # 滑块（底盘电机范围扩大100倍：±72000度）
        slider = QSlider(Qt.Horizontal)
        slider.setRange(-72000, 72000)
        slider.setValue(0)
        slider.valueChanged.connect(lambda v, idx=index: self._on_chassis_slider_change(idx, v))
        self.chassis_sliders.append(slider)
        row_layout.addWidget(slider, 1)
        
        # 目标距离值（无标签前缀）
        target_label = QLabel("0°")
        target_label.setStyleSheet("color: #64748b; font-size: 14px; min-width: 70px; font-family: 'Consolas', monospace;")
        target_label.setAlignment(Qt.AlignCenter)
        if not hasattr(self, 'chassis_target_labels'):
            self.chassis_target_labels = []
        self.chassis_target_labels.append(target_label)
        row_layout.addWidget(target_label)
        
        # 反馈距离值（无标签前缀）
        feedback_label = QLabel("0°")
        feedback_label.setStyleSheet("color: #3b82f6; font-size: 14px; min-width: 70px; font-family: 'Consolas', monospace;")
        feedback_label.setAlignment(Qt.AlignCenter)
        self.chassis_entries.append(feedback_label)
        row_layout.addWidget(feedback_label)
        
        # 电压值（无标签前缀）
        voltage_label = QLabel("0.00V")
        voltage_label.setStyleSheet("color: #10b981; font-size: 14px; min-width: 80px; font-family: 'Consolas', monospace;")
        voltage_label.setAlignment(Qt.AlignCenter)
        if not hasattr(self, 'chassis_voltage_labels'):
            self.chassis_voltage_labels = []
        self.chassis_voltage_labels.append(voltage_label)
        row_layout.addWidget(voltage_label)
        
        layout.addWidget(row_widget)
    
    def _on_chassis_slider_change(self, index, value):
        """底盘滑块变化"""
        if self._updating_from_feedback:
            return
        
        # 更新目标距离显示（无前缀）
        if hasattr(self, 'chassis_target_labels') and index < len(self.chassis_target_labels):
            self.chassis_target_labels[index].setText(f"{value}°")
        
        self.main_gui.chassis_wheel_angles[index] = float(value)
        self._send_angles()
    
    def _on_chassis_entry_change(self, index):
        """底盘输入框变化（已移除，保留方法以兼容）"""
        pass

    
    def _chassis_key_press(self, key):
        """底盘按键按下"""
        print(f"底盘按键按下: {key}")
        
        # 获取速度（使用大距离，参照之前的修复）
        speed_percent = float(self.main_gui.speed_percent)
        max_distance = speed_percent * 20000  # 从10改为20000
        
        # 根据按键计算目标角度
        if key == 'w':  # 前进
            self.main_gui.chassis_wheel_angles[0] -= max_distance * 0.866
            self.main_gui.chassis_wheel_angles[2] += max_distance * 0.866
        elif key == 's':  # 后退
            self.main_gui.chassis_wheel_angles[0] += max_distance * 0.866
            self.main_gui.chassis_wheel_angles[2] -= max_distance * 0.866
        elif key == 'a':  # 左移
            self.main_gui.chassis_wheel_angles[0] -= max_distance * 0.5
            self.main_gui.chassis_wheel_angles[1] += max_distance
            self.main_gui.chassis_wheel_angles[2] -= max_distance * 0.5
        elif key == 'd':  # 右移
            self.main_gui.chassis_wheel_angles[0] += max_distance * 0.5
            self.main_gui.chassis_wheel_angles[1] -= max_distance
            self.main_gui.chassis_wheel_angles[2] += max_distance * 0.5
        elif key == 'q':  # 左转
            self.main_gui.chassis_wheel_angles[0] -= max_distance
            self.main_gui.chassis_wheel_angles[1] -= max_distance
            self.main_gui.chassis_wheel_angles[2] -= max_distance
        elif key == 'e':  # 右转
            self.main_gui.chassis_wheel_angles[0] += max_distance
            self.main_gui.chassis_wheel_angles[1] += max_distance
            self.main_gui.chassis_wheel_angles[2] += max_distance
        
        self._send_angles()
        self._update_chassis_display()
    
    def _chassis_key_release(self, key):
        """底盘按键释放 - 直接停止在当前反馈位置"""
        print(f"底盘按键释放: {key}")
        
        # 强制处理一次反馈，确保获取最新位置
        self.main_gui.serial_comm.process_feedback(self.main_gui.NUM_ARM_JOINTS)
        
        # 直接设置目标为当前反馈位置，立即停止
        for i in range(3):
            motor_id = i + 4  # M4, M5, M6
            if motor_id < len(self.main_gui.serial_comm.last_feedback_pos):
                feedback_pos = self.main_gui.serial_comm.last_feedback_pos[motor_id]
                self.main_gui.chassis_wheel_angles[i] = feedback_pos
                print(f"  M{motor_id} 停止: 目标={feedback_pos:.2f}°")
        
        self._send_angles()
        self._update_chassis_display()
    
    def _chassis_home(self):
        """底盘归零"""
        self.main_gui.chassis_wheel_angles = [0.0, 0.0, 0.0]
        self._send_angles()
        self._update_chassis_display()
    
    def _update_chassis_display(self):
        """更新底盘显示"""
        for i in range(3):
            if i < len(self.chassis_sliders):
                self.chassis_sliders[i].setValue(int(self.main_gui.chassis_wheel_angles[i]))
            if i < len(self.chassis_entries):
                self.chassis_entries[i].setText(str(int(self.main_gui.chassis_wheel_angles[i])))

    def apply_joint_feedback(self, joint_angles, chassis_angles, joint_voltages=None, chassis_voltages=None):
        """应用反馈数据更新显示（简化版本，电压已在robot_control_gui.py中直接更新）"""
        self._updating_from_feedback = True
        
        try:
            # 只需要更新末端位置XYZ（正运动学计算）
            self._update_end_effector_position(joint_angles)
            
        finally:
            self._updating_from_feedback = False
    
    def _update_end_effector_position(self, joint_angles):
        """更新末端执行器位置（使用ikpy正运动学计算）"""
        try:
            # 检查是否有kinematics模块
            if not hasattr(self.main_gui, 'kinematics'):
                return
            
            # 使用ikpy计算正运动学
            # 构建完整的角度数组（包括基座固定关节）
            angles_rad = [0.0]  # 基座固定关节
            for i in range(min(4, len(joint_angles))):
                angles_rad.append(joint_angles[i] * 3.14159265359 / 180.0)  # 转换为弧度
            
            # 补齐到7个关节（如果不足）
            while len(angles_rad) < 8:
                angles_rad.append(0.0)
            
            # 计算正运动学
            tcp_matrix = self.main_gui.kinematics.arm_chain.forward_kinematics(angles_rad)
            tcp_position = tcp_matrix[:3, 3]  # 提取位置向量
            
            # 转换为毫米
            x = float(tcp_position[0] * 1000)
            y = float(tcp_position[1] * 1000)
            z = float(tcp_position[2] * 1000)
            
            # 添加到历史记录进行平滑
            self.xyz_history['X'].append(x)
            self.xyz_history['Y'].append(y)
            self.xyz_history['Z'].append(z)
            
            # 保持历史记录大小
            for axis in ['X', 'Y', 'Z']:
                if len(self.xyz_history[axis]) > self.xyz_filter_size:
                    self.xyz_history[axis].pop(0)
            
            # 计算平均值（平滑滤波）
            if len(self.xyz_history['X']) >= self.xyz_filter_size:
                x_avg = sum(self.xyz_history['X']) / len(self.xyz_history['X'])
                y_avg = sum(self.xyz_history['Y']) / len(self.xyz_history['Y'])
                z_avg = sum(self.xyz_history['Z']) / len(self.xyz_history['Z'])
                
                # 更新显示（保留整数，减少跳动）
                self.pos_labels['X'].setText(f"{int(x_avg)}")
                self.pos_labels['Y'].setText(f"{int(y_avg)}")
                self.pos_labels['Z'].setText(f"{int(z_avg)}")
            
        except Exception as e:
            # 计算失败时保持原值
            pass
