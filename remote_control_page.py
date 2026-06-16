#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
远程控制页面
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QLineEdit, QTextEdit, QGroupBox, QSpinBox
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont

from .remote_control_server import RemoteControlServer


class RemoteControlPage(QWidget):
    """远程控制页面"""
    
    def __init__(self, parent, main_window):
        super().__init__(parent)
        self.main_window = main_window
        self.server = RemoteControlServer(main_window)
        self.status_timer = None
        
        self._init_ui()
    
    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # 标题
        title = QLabel("远程控制")
        title.setObjectName("section_title")
        layout.addWidget(title)
        
        # 服务器配置
        config_group = QGroupBox("服务器配置")
        config_layout = QHBoxLayout()
        
        config_layout.addWidget(QLabel("监听地址:"))
        self.host_input = QLineEdit("0.0.0.0")
        self.host_input.setMaximumWidth(150)
        config_layout.addWidget(self.host_input)
        
        config_layout.addWidget(QLabel("端口:"))
        self.port_input = QSpinBox()
        self.port_input.setRange(1024, 65535)
        self.port_input.setValue(8765)
        self.port_input.setMaximumWidth(100)
        config_layout.addWidget(self.port_input)
        
        config_layout.addStretch()
        config_group.setLayout(config_layout)
        layout.addWidget(config_group)
        
        # 控制按钮
        button_layout = QHBoxLayout()
        
        self.start_button = QPushButton("启动服务器")
        self.start_button.setObjectName("primary_button")
        self.start_button.setMinimumHeight(40)
        self.start_button.clicked.connect(self._start_server)
        button_layout.addWidget(self.start_button)
        
        self.stop_button = QPushButton("停止服务器")
        self.stop_button.setObjectName("secondary_button")
        self.stop_button.setMinimumHeight(40)
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self._stop_server)
        button_layout.addWidget(self.stop_button)
        
        layout.addLayout(button_layout)
        
        # 连接信息
        info_group = QGroupBox("连接信息")
        info_layout = QVBoxLayout()
        
        self.status_label = QLabel("服务器未启动")
        self.status_label.setStyleSheet("color: #64748b; font-size: 14px;")
        info_layout.addWidget(self.status_label)
        
        self.url_label = QLabel("")
        self.url_label.setStyleSheet("color: #4f46e5; font-size: 13px; font-weight: bold;")
        self.url_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        info_layout.addWidget(self.url_label)
        
        self.clients_label = QLabel("已连接客户端: 0")
        info_layout.addWidget(self.clients_label)
        
        info_group.setLayout(info_layout)
        layout.addWidget(info_group)
        
        # 使用说明
        help_group = QGroupBox("使用说明")
        help_layout = QVBoxLayout()
        
        help_text = QTextEdit()
        help_text.setReadOnly(True)
        help_text.setMaximumHeight(200)
        help_text.setHtml("""
        <h3>手机APP控制</h3>
        <p>1. 确保手机和电脑在同一局域网</p>
        <p>2. 启动服务器后，使用手机浏览器或APP连接显示的WebSocket地址</p>
        <p>3. 支持的功能：</p>
        <ul>
            <li>实时控制机械臂和底盘</li>
            <li>视频监控（需要摄像头）</li>
            <li>语音命令控制</li>
            <li>状态实时推送</li>
        </ul>
        
        <h3>API示例</h3>
        <p><b>控制命令：</b></p>
        <pre>{"type": "control", "command": "move_chassis", "params": {"direction": "forward", "distance": 10}}</pre>
        
        <p><b>语音命令：</b></p>
        <pre>{"type": "voice_command", "text": "前进"}</pre>
        
        <p><b>启动视频：</b></p>
        <pre>{"type": "video_start", "quality": 50}</pre>
        """)
        help_layout.addWidget(help_text)
        
        help_group.setLayout(help_layout)
        layout.addWidget(help_group)
        
        # 日志
        log_group = QGroupBox("服务器日志")
        log_layout = QVBoxLayout()
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(150)
        log_layout.addWidget(self.log_text)
        
        log_group.setLayout(log_layout)
        layout.addWidget(log_group)
        
        layout.addStretch()
        
        # 检查websockets是否可用
        if not RemoteControlServer.is_available():
            self.start_button.setEnabled(False)
            self.status_label.setText("错误: websockets未安装")
            self.status_label.setStyleSheet("color: #ef4444; font-size: 14px;")
            self._log("请安装websockets: pip install websockets")
    
    def _start_server(self):
        """启动服务器"""
        try:
            host = self.host_input.text()
            port = self.port_input.value()
            
            self.server.start(host, port)
            
            self.start_button.setEnabled(False)
            self.stop_button.setEnabled(True)
            self.host_input.setEnabled(False)
            self.port_input.setEnabled(False)
            
            self.status_label.setText("服务器运行中")
            self.status_label.setStyleSheet("color: #10b981; font-size: 14px;")
            
            # 显示连接地址
            import socket
            local_ip = socket.gethostbyname(socket.gethostname())
            self.url_label.setText(f"WebSocket地址: ws://{local_ip}:{port}")
            
            self._log(f"服务器已启动: ws://{host}:{port}")
            self._log(f"局域网地址: ws://{local_ip}:{port}")
            
            # 启动状态更新定时器（更新客户端数量）
            self.status_timer = QTimer()
            self.status_timer.timeout.connect(self._update_status)
            self.status_timer.start(1000)
            
            # 启动状态广播定时器（向所有客户端推送状态）
            self.broadcast_timer = QTimer()
            self.broadcast_timer.timeout.connect(self._broadcast_status)
            self.broadcast_timer.start(200)  # 每200ms广播一次状态
            
        except Exception as e:
            self._log(f"启动失败: {e}")
            self.status_label.setText(f"启动失败: {e}")
            self.status_label.setStyleSheet("color: #ef4444; font-size: 14px;")
    
    def _stop_server(self):
        """停止服务器"""
        try:
            self.server.stop()
            
            if self.status_timer:
                self.status_timer.stop()
                self.status_timer = None
            
            if hasattr(self, 'broadcast_timer') and self.broadcast_timer:
                self.broadcast_timer.stop()
                self.broadcast_timer = None
            
            self.start_button.setEnabled(True)
            self.stop_button.setEnabled(False)
            self.host_input.setEnabled(True)
            self.port_input.setEnabled(True)
            
            self.status_label.setText("服务器已停止")
            self.status_label.setStyleSheet("color: #64748b; font-size: 14px;")
            self.url_label.setText("")
            self.clients_label.setText("已连接客户端: 0")
            
            self._log("服务器已停止")
            
        except Exception as e:
            self._log(f"停止失败: {e}")
    
    def _update_status(self):
        """更新状态"""
        client_count = len(self.server.clients)
        self.clients_label.setText(f"已连接客户端: {client_count}")
    
    def _broadcast_status(self):
        """广播状态到所有客户端"""
        if self.server and self.server.running:
            # 在服务器的事件循环中执行广播
            import asyncio
            try:
                # 获取服务器的事件循环
                if hasattr(self.server, '_loop') and self.server._loop:
                    asyncio.run_coroutine_threadsafe(
                        self.server.broadcast_status(),
                        self.server._loop
                    )
            except Exception as e:
                pass  # 静默失败，避免日志刷屏
    
    def _log(self, message):
        """添加日志"""
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")
