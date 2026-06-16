#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
设置页面 - PySide6版本
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QComboBox, QFrame, QGridLayout,
    QLineEdit, QSpinBox, QDoubleSpinBox
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtSerialPort import QSerialPortInfo
import json
import os


class SettingsPage(QWidget):
    """设置页面"""
    
    def __init__(self, parent, main_gui):
        super().__init__(parent)
        self.main_gui = main_gui
        self.config_file = "serial_config.json"
        
        self._init_ui()
        
        # 定时刷新串口列表
        self.port_refresh_timer = QTimer()
        self.port_refresh_timer.timeout.connect(self._refresh_ports)
        self.port_refresh_timer.start(2000)  # 每2秒刷新
    
    def _init_ui(self):
        """初始化UI"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)
        
        # 创建滚动区域
        from PySide6.QtWidgets import QScrollArea
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_area.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        
        # 滚动内容容器
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(15)
        
        # 串口和手柄连接（并排）
        connection_row = QWidget()
        connection_layout = QHBoxLayout(connection_row)
        connection_layout.setContentsMargins(0, 0, 0, 0)
        connection_layout.setSpacing(15)
        
        self._create_serial_section(connection_layout)
        self._create_gamepad_section(connection_layout)
        
        # 设置相同宽度
        connection_layout.setStretch(0, 1)
        connection_layout.setStretch(1, 1)
        
        scroll_layout.addWidget(connection_row)
        
        # 创建其他设置区域
        self._create_robot_params_section(scroll_layout)
        self._create_theme_section(scroll_layout)
        
        # 底部按钮
        bottom_frame = QWidget()
        bottom_layout = QHBoxLayout(bottom_frame)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.setSpacing(10)
        
        bottom_layout.addStretch()
        
        reset_btn = QPushButton("恢复默认")
        reset_btn.setObjectName("secondary_button")
        reset_btn.setMinimumSize(120, 40)
        reset_btn.clicked.connect(self._reset_settings)
        bottom_layout.addWidget(reset_btn)
        
        save_btn = QPushButton("保存设置")
        save_btn.setObjectName("primary_button")
        save_btn.setMinimumSize(120, 40)
        save_btn.clicked.connect(self._save_settings)
        bottom_layout.addWidget(save_btn)
        
        scroll_layout.addWidget(bottom_frame)
        scroll_layout.addStretch()
        
        # 设置滚动内容
        scroll_area.setWidget(scroll_content)
        main_layout.addWidget(scroll_area)
    
    def _create_serial_section(self, layout):
        """创建串口设置区域"""
        serial_frame = QFrame()
        serial_frame.setObjectName("card")
        serial_layout = QVBoxLayout(serial_frame)
        serial_layout.setContentsMargins(20, 20, 20, 20)
        serial_layout.setSpacing(15)
        
        # 标题
        title = QLabel("串口连接")
        title.setObjectName("section_title")
        serial_layout.addWidget(title)
        
        # 串口选择
        port_row = QWidget()
        port_layout = QHBoxLayout(port_row)
        port_layout.setContentsMargins(0, 0, 0, 0)
        port_layout.setSpacing(10)
        
        port_label = QLabel("串口:")
        port_label.setStyleSheet("color: #475569; font-size: 13px; min-width: 80px;")
        port_layout.addWidget(port_label)
        
        self.port_combo = QComboBox()
        self.port_combo.setMinimumHeight(36)
        self.port_combo.setMaximumWidth(200)
        port_layout.addWidget(self.port_combo)
        
        port_layout.addStretch()
        
        detect_btn = QPushButton("🔍 检测")
        detect_btn.setObjectName("secondary_button")
        detect_btn.setFixedSize(90, 36)
        detect_btn.setToolTip("检测ESP32设备")
        detect_btn.clicked.connect(self._detect_esp32)
        port_layout.addWidget(detect_btn)
        
        refresh_btn = QPushButton("🔄 刷新")
        refresh_btn.setObjectName("secondary_button")
        refresh_btn.setFixedSize(90, 36)
        refresh_btn.setToolTip("刷新串口列表")
        refresh_btn.clicked.connect(self._refresh_ports)
        port_layout.addWidget(refresh_btn)
        
        serial_layout.addWidget(port_row)
        
        # 波特率选择
        baud_row = QWidget()
        baud_layout = QHBoxLayout(baud_row)
        baud_layout.setContentsMargins(0, 0, 0, 0)
        baud_layout.setSpacing(10)
        
        baud_label = QLabel("波特率:")
        baud_label.setStyleSheet("color: #475569; font-size: 13px; min-width: 80px;")
        baud_layout.addWidget(baud_label)
        
        self.baud_combo = QComboBox()
        self.baud_combo.addItems(["9600", "19200", "38400", "57600", "115200", "230400", "460800", "921600"])
        self.baud_combo.setCurrentText("115200")
        self.baud_combo.setMinimumHeight(36)
        baud_layout.addWidget(self.baud_combo, 1)
        
        serial_layout.addWidget(baud_row)
        
        # 连接按钮
        btn_row = QWidget()
        btn_layout = QHBoxLayout(btn_row)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(10)
        
        self.connect_btn = QPushButton("连接")
        self.connect_btn.setObjectName("primary_button")
        self.connect_btn.setMinimumHeight(40)
        self.connect_btn.clicked.connect(self._toggle_connection)
        btn_layout.addWidget(self.connect_btn)
        
        self.status_label = QLabel("未连接")
        self.status_label.setStyleSheet("color: #94a3b8; font-size: 13px;")
        self.status_label.setAlignment(Qt.AlignCenter)
        btn_layout.addWidget(self.status_label)
        
        serial_layout.addWidget(btn_row)
        
        layout.addWidget(serial_frame, 1)
        
        # 加载配置并刷新串口列表
        self._load_config()
        self._refresh_ports()
    
    def _create_gamepad_section(self, layout):
        """创建手柄连接区域"""
        gamepad_frame = QFrame()
        gamepad_frame.setObjectName("card")
        gamepad_layout = QVBoxLayout(gamepad_frame)
        gamepad_layout.setContentsMargins(20, 20, 20, 20)
        gamepad_layout.setSpacing(15)
        
        # 标题
        title = QLabel("手柄连接")
        title.setObjectName("section_title")
        gamepad_layout.addWidget(title)
        
        # 手柄选择
        device_row = QWidget()
        device_layout = QHBoxLayout(device_row)
        device_layout.setContentsMargins(0, 0, 0, 0)
        device_layout.setSpacing(10)
        
        device_label = QLabel("设备:")
        device_label.setStyleSheet("color: #475569; font-size: 13px; min-width: 80px;")
        device_layout.addWidget(device_label)
        
        self.gamepad_combo = QComboBox()
        self.gamepad_combo.setMinimumHeight(36)
        self.gamepad_combo.setMaximumWidth(200)
        device_layout.addWidget(self.gamepad_combo)
        
        device_layout.addStretch()
        
        refresh_gamepad_btn = QPushButton("🔄 刷新")
        refresh_gamepad_btn.setObjectName("secondary_button")
        refresh_gamepad_btn.setFixedSize(90, 36)
        refresh_gamepad_btn.clicked.connect(self._refresh_gamepads)
        device_layout.addWidget(refresh_gamepad_btn)
        
        gamepad_layout.addWidget(device_row)
        
        # 连接按钮
        btn_row = QWidget()
        btn_layout = QHBoxLayout(btn_row)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(10)
        
        self.gamepad_connect_btn = QPushButton("连接")
        self.gamepad_connect_btn.setObjectName("primary_button")
        self.gamepad_connect_btn.setMinimumHeight(40)
        self.gamepad_connect_btn.clicked.connect(self._toggle_gamepad_connection)
        btn_layout.addWidget(self.gamepad_connect_btn)
        
        self.gamepad_status_label = QLabel("未连接")
        self.gamepad_status_label.setStyleSheet("color: #94a3b8; font-size: 13px;")
        self.gamepad_status_label.setAlignment(Qt.AlignCenter)
        btn_layout.addWidget(self.gamepad_status_label)
        
        gamepad_layout.addWidget(btn_row)
        
        # 按键映射提示
        info_label = QLabel("💡 左摇杆:底盘 右摇杆+扳机:末端")
        info_label.setStyleSheet("color: #64748b; font-size: 12px; padding: 5px;")
        gamepad_layout.addWidget(info_label)
        
        layout.addWidget(gamepad_frame, 1)
        
        # 初始刷新手柄列表
        self._refresh_gamepads()
    
    def _create_robot_params_section(self, layout):
        """创建机械臂参数区域"""
        params_frame = QFrame()
        params_frame.setObjectName("card")
        params_layout = QVBoxLayout(params_frame)
        params_layout.setContentsMargins(20, 20, 20, 20)
        params_layout.setSpacing(15)
        
        # 标题
        title = QLabel("机械臂参数")
        title.setObjectName("section_title")
        params_layout.addWidget(title)
        
        # 参数网格
        grid = QGridLayout()
        grid.setSpacing(10)
        
        # 减速比
        row = 0
        label = QLabel("关节减速比:")
        label.setStyleSheet("color: #475569; font-size: 13px;")
        grid.addWidget(label, row, 0)
        
        self.gear_ratio_arm_spin = QDoubleSpinBox()
        self.gear_ratio_arm_spin.setRange(1.0, 200.0)
        self.gear_ratio_arm_spin.setValue(100.0)
        self.gear_ratio_arm_spin.setMinimumHeight(36)
        grid.addWidget(self.gear_ratio_arm_spin, row, 1)
        
        row += 1
        label = QLabel("底盘减速比:")
        label.setStyleSheet("color: #475569; font-size: 13px;")
        grid.addWidget(label, row, 0)
        
        self.gear_ratio_base_spin = QDoubleSpinBox()
        self.gear_ratio_base_spin.setRange(1.0, 200.0)
        self.gear_ratio_base_spin.setValue(37.1)
        self.gear_ratio_base_spin.setDecimals(1)
        self.gear_ratio_base_spin.setMinimumHeight(36)
        grid.addWidget(self.gear_ratio_base_spin, row, 1)
        
        row += 1
        label = QLabel("最大速度:")
        label.setStyleSheet("color: #475569; font-size: 13px;")
        grid.addWidget(label, row, 0)
        
        speed_widget = QWidget()
        speed_layout = QHBoxLayout(speed_widget)
        speed_layout.setContentsMargins(0, 0, 0, 0)
        speed_layout.setSpacing(10)
        
        from PySide6.QtWidgets import QSlider
        self.max_speed_slider = QSlider(Qt.Horizontal)
        self.max_speed_slider.setRange(1, 100)
        self.max_speed_slider.setValue(100)
        self.max_speed_slider.setMinimumHeight(36)
        self.max_speed_slider.valueChanged.connect(self._update_speed_label)
        speed_layout.addWidget(self.max_speed_slider, 1)
        
        self.max_speed_label = QLabel("100 %")
        self.max_speed_label.setStyleSheet("color: #667eea; font-size: 14px; font-weight: bold; min-width: 60px;")
        speed_layout.addWidget(self.max_speed_label)
        
        grid.addWidget(speed_widget, row, 1)
        
        params_layout.addLayout(grid)
        layout.addWidget(params_frame)
    
    def _create_theme_section(self, layout):
        """创建主题设置区域"""
        theme_frame = QFrame()
        theme_frame.setObjectName("card")
        theme_layout = QVBoxLayout(theme_frame)
        theme_layout.setContentsMargins(20, 20, 20, 20)
        theme_layout.setSpacing(15)
        
        # 标题
        title = QLabel("界面主题")
        title.setObjectName("section_title")
        theme_layout.addWidget(title)
        
        # 主题选择
        theme_row = QWidget()
        theme_row_layout = QHBoxLayout(theme_row)
        theme_row_layout.setContentsMargins(0, 0, 0, 0)
        theme_row_layout.setSpacing(10)
        
        theme_label = QLabel("主题:")
        theme_label.setStyleSheet("color: #475569; font-size: 13px; min-width: 80px;")
        theme_row_layout.addWidget(theme_label)
        
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["浅色", "深色", "跟随系统"])
        self.theme_combo.setCurrentText("浅色")
        self.theme_combo.setMinimumHeight(36)
        theme_row_layout.addWidget(self.theme_combo, 1)
        
        apply_btn = QPushButton("应用")
        apply_btn.setObjectName("primary_button")
        apply_btn.setFixedSize(80, 36)
        apply_btn.clicked.connect(self._apply_theme)
        theme_row_layout.addWidget(apply_btn)
        
        theme_layout.addWidget(theme_row)
        
        # 提示信息
        info_label = QLabel("💡 提示: 主题更改后需要重启应用生效")
        info_label.setStyleSheet("color: #64748b; font-size: 12px; padding: 10px;")
        theme_layout.addWidget(info_label)
        
        layout.addWidget(theme_frame)
    
    def _load_config(self):
        """加载配置"""
        # 不再自动加载上次连接的端口
        pass
    
    def _save_config(self, port):
        """保存配置"""
        try:
            config = {'last_port': port}
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存配置失败: {e}")
    
    def _refresh_ports(self):
        """刷新串口列表"""
        self.port_combo.clear()
        ports = [port.portName() for port in QSerialPortInfo.availablePorts()]
        if ports:
            self.port_combo.addItems(ports)
        else:
            self.port_combo.addItem("无可用串口")
    
    def _detect_esp32(self):
        """检测ESP32设备"""
        # ESP32常用串口芯片标识
        esp32_chips = [
            'CH340',  # CH340/CH341
            'CP210',  # CP2102/CP2104
            'FTDI',   # FTDI芯片
            'USB-SERIAL',  # 通用USB串口
            'USB SERIAL',
            'UART',
            'Silicon Labs',  # CP210x的制造商
        ]
        
        self.port_combo.clear()
        esp32_ports = []
        other_ports = []
        
        for port_info in QSerialPortInfo.availablePorts():
            port_name = port_info.portName()
            description = port_info.description().upper()
            manufacturer = port_info.manufacturer().upper()
            
            # 检查是否为ESP32设备
            is_esp32 = False
            for chip in esp32_chips:
                if chip.upper() in description or chip.upper() in manufacturer:
                    is_esp32 = True
                    break
            
            if is_esp32:
                # ESP32设备添加标识
                esp32_ports.append(f"🔷 {port_name} ({port_info.description()})")
            else:
                other_ports.append(f"{port_name} ({port_info.description()})")
        
        # 先添加ESP32设备
        if esp32_ports:
            self.port_combo.addItems(esp32_ports)
            # 自动选择第一个ESP32设备
            self.port_combo.setCurrentIndex(0)
            self.status_label.setText(f"检测到 {len(esp32_ports)} 个ESP32设备")
            self.status_label.setStyleSheet("color: #10b981; font-size: 13px;")
        
        # 再添加其他设备
        if other_ports:
            self.port_combo.addItems(other_ports)
        
        # 如果没有任何设备
        if not esp32_ports and not other_ports:
            self.port_combo.addItem("未检测到串口设备")
            self.status_label.setText("未检测到设备")
            self.status_label.setStyleSheet("color: #ef4444; font-size: 13px;")
    
    def _toggle_connection(self):
        """切换串口连接"""
        if not hasattr(self.main_gui, 'serial_comm'):
            self.status_label.setText("串口模块未初始化")
            self.status_label.setStyleSheet("color: #ef4444; font-size: 13px;")
            return
        
        if not self.main_gui.serial_comm.is_connected:
            port_text = self.port_combo.currentText()
            if port_text == "无可用串口" or port_text == "未检测到串口设备":
                self.status_label.setText("无可用串口")
                self.status_label.setStyleSheet("color: #ef4444; font-size: 13px;")
                return
            
            # 提取实际端口名（去除标识符）
            if port_text.startswith("🔷 "):
                port = port_text.split(" ")[1]  # 提取端口名
            else:
                port = port_text.split(" ")[0]  # 提取端口名
            
            baud = int(self.baud_combo.currentText())
            
            if self.main_gui.serial_comm.connect(port, baud):
                self.connect_btn.setText("✓ 已连接")
                self.status_label.setText(f"已连接到 {port}")
                self.status_label.setStyleSheet("color: #10b981; font-size: 13px;")
                # 保存成功连接的端口
                self._save_config(port)
                self.last_port = port
            else:
                self.connect_btn.setText("连接")
                self.status_label.setText("连接失败")
                self.status_label.setStyleSheet("color: #ef4444; font-size: 13px;")
        else:
            self.main_gui.serial_comm.disconnect()
            self.connect_btn.setText("连接")
            self.status_label.setText("未连接")
            self.status_label.setStyleSheet("color: #94a3b8; font-size: 13px;")
    
    def _apply_theme(self):
        """应用主题"""
        theme = self.theme_combo.currentText()
        self.status_label.setText(f"主题已设置为: {theme}")
        self.status_label.setStyleSheet("color: #10b981; font-size: 13px;")
    
    def _refresh_gamepads(self):
        """刷新手柄列表"""
        self.gamepad_combo.clear()
        try:
            import pygame
            pygame.init()
            pygame.joystick.init()
            
            joystick_count = pygame.joystick.get_count()
            if joystick_count == 0:
                self.gamepad_combo.addItem("未检测到手柄")
                self.gamepad_connect_btn.setEnabled(False)
            else:
                for i in range(joystick_count):
                    joy = pygame.joystick.Joystick(i)
                    self.gamepad_combo.addItem(f"{i}: {joy.get_name()}")
                self.gamepad_connect_btn.setEnabled(True)
        except ImportError:
            self.gamepad_combo.addItem("Pygame未安装")
            self.gamepad_connect_btn.setEnabled(False)
        except Exception as e:
            self.gamepad_combo.addItem(f"错误: {str(e)}")
            self.gamepad_connect_btn.setEnabled(False)
    
    def _toggle_gamepad_connection(self):
        """切换手柄连接"""
        if not hasattr(self.main_gui, 'gamepad_connected') or not self.main_gui.gamepad_connected:
            device_text = self.gamepad_combo.currentText()
            if device_text.startswith("未检测到") or device_text.startswith("Pygame") or device_text.startswith("错误"):
                self.gamepad_status_label.setText("无可用设备")
                self.gamepad_status_label.setStyleSheet("color: #ef4444; font-size: 13px;")
                return
            
            try:
                import pygame
                pygame.init()
                pygame.joystick.init()
                
                device_id = int(device_text.split(":")[0])
                self.main_gui.gamepad = pygame.joystick.Joystick(device_id)
                self.main_gui.gamepad.init()
                self.main_gui.gamepad_connected = True
                
                # 启动手柄轮询
                if not hasattr(self.main_gui, 'gamepad_timer'):
                    from PySide6.QtCore import QTimer
                    self.main_gui.gamepad_timer = QTimer()
                    self.main_gui.gamepad_timer.timeout.connect(self.main_gui._poll_gamepad)
                self.main_gui.gamepad_timer.start(50)
                
                self.gamepad_connect_btn.setText("✓ 已连接")
                self.gamepad_status_label.setText(f"已连接")
                self.gamepad_status_label.setStyleSheet("color: #10b981; font-size: 13px;")
            except Exception as e:
                self.gamepad_connect_btn.setText("连接")
                self.gamepad_status_label.setText("连接失败")
                self.gamepad_status_label.setStyleSheet("color: #ef4444; font-size: 13px;")
        else:
            if hasattr(self.main_gui, 'gamepad_timer'):
                self.main_gui.gamepad_timer.stop()
            if hasattr(self.main_gui, 'gamepad'):
                self.main_gui.gamepad.quit()
            self.main_gui.gamepad_connected = False
            
            self.gamepad_connect_btn.setText("连接")
            self.gamepad_status_label.setText("未连接")
            self.gamepad_status_label.setStyleSheet("color: #94a3b8; font-size: 13px;")
    
    def _update_speed_label(self, value):
        """更新速度标签"""
        self.max_speed_label.setText(f"{value} %")
    
    def _save_settings(self):
        """保存设置"""
        # 更新主GUI的参数
        if hasattr(self.main_gui, 'serial_comm'):
            self.main_gui.serial_comm.gear_ratio_arm = self.gear_ratio_arm_spin.value()
            self.main_gui.serial_comm.gear_ratio_base = self.gear_ratio_base_spin.value()
        
        if hasattr(self.main_gui, 'speed_percent'):
            self.main_gui.speed_percent = self.max_speed_slider.value()
        
        # 显示成功消息
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.information(self, "提示", "设置已保存！")
    
    def _reset_settings(self):
        """恢复默认设置"""
        self.baud_combo.setCurrentText("115200")
        self.gear_ratio_arm_spin.setValue(100.0)
        self.gear_ratio_base_spin.setValue(37.1)
        self.max_speed_slider.setValue(100)
        self.theme_combo.setCurrentText("浅色")
        
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.information(self, "提示", "已恢复默认设置！")
