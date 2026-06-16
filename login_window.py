#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
登录窗口 - PySide6版本
根据新设计图重构的现代化UI
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QPushButton, QFrame, QGraphicsDropShadowEffect,
    QWidget
)
from PySide6.QtCore import Qt, QSize, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QPixmap, QIcon, QColor, QFont, QFontDatabase, QImage
import os

class LoginWindow(QDialog):
    """现代化登录窗口，灵感来自Dribbble设计"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("登录")
        self.setFixedSize(420, 580)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # 设置窗口背景色（防止透明区域显示为白色）
        self.setStyleSheet("QDialog { background-color: transparent; }")
        
        # 默认凭据
        self.default_username = "admin"
        self.default_password = "123456"
        
        self._init_ui()

    def _init_ui(self):
        """初始化UI"""
        # 主背景
        main_bg = QFrame(self)
        main_bg.setGeometry(0, 0, 420, 580)  # 确保完全覆盖整个窗口
        main_bg.setStyleSheet("background-color: #f0f2f5; border-radius: 20px;")
        main_layout = QVBoxLayout(main_bg)
        main_layout.setContentsMargins(20, 20, 20, 20)  # 增加外边距，给阴影留出空间
        
        # 关闭按钮（放在右上角）
        close_btn = QPushButton("×", self)
        close_btn.setGeometry(370, 10, 40, 40)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #666;
                font-size: 28px;
                font-weight: bold;
                border: none;
                border-radius: 20px;
            }
            QPushButton:hover {
                background-color: rgba(0, 0, 0, 0.05);
                color: #333;
            }
            QPushButton:pressed {
                background-color: rgba(0, 0, 0, 0.1);
            }
        """)
        close_btn.clicked.connect(self.reject)
        close_btn.setCursor(Qt.PointingHandCursor)
        
        # 白色卡片
        card = QFrame()
        card.setObjectName("login_card")
        card.setStyleSheet("""
            QFrame#login_card {
                background-color: #ffffff;
                border-radius: 20px;
            }
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(40, 40, 40, 40)
        card_layout.setSpacing(20)
        
        # 添加更柔和、更具层次感的阴影
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(50)
        shadow.setColor(QColor(0, 0, 0, 40))
        shadow.setOffset(0, 10)
        card.setGraphicsEffect(shadow)
        
        # 创建UI组件
        self._create_header(card_layout)
        self._create_form(card_layout)
        self._create_footer(card_layout)
        
        main_layout.addWidget(card)
        
        # 确保布局填充整个对话框
        dialog_layout = QVBoxLayout(self)
        dialog_layout.setContentsMargins(0, 0, 0, 0)
        dialog_layout.addWidget(main_bg)
        self.setLayout(dialog_layout)

    def _create_header(self, layout):
        """创建标题区域"""
        # Logo图标（优化的透明背景处理）
        logo_label = QLabel()
        icon_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "漂亮图标")
        icon_path = os.path.join(icon_dir, "手.png")
        
        if os.path.exists(icon_path):
            image = QImage(icon_path)
            image = image.convertToFormat(QImage.Format_ARGB32)
            
            # 更精确地将白色和浅色背景设为透明
            for y in range(image.height()):
                for x in range(image.width()):
                    color = image.pixelColor(x, y)
                    # 检测白色和浅灰色背景（更宽松的阈值）
                    if color.red() > 230 and color.green() > 230 and color.blue() > 230:
                        color.setAlpha(0)
                        image.setPixelColor(x, y, color)
            
            logo_pixmap = QPixmap.fromImage(image).scaled(60, 60, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            logo_label.setPixmap(logo_pixmap)
        
        # 确保标签本身也是透明的
        logo_label.setStyleSheet("background-color: transparent;")
        logo_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(logo_label)
        
        title = QLabel("Hello Again!")
        title.setStyleSheet("font-size: 32px; font-weight: 800; color: #333;")
        title.setAlignment(Qt.AlignCenter)
        
        subtitle = QLabel("Enter your credentials and get access")
        subtitle.setStyleSheet("font-size: 14px; color: #888;")
        subtitle.setAlignment(Qt.AlignCenter)
        
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(10)

    def _create_form(self, layout):
        """创建表单区域"""
        icon_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "漂亮图标")
        
        # 用户名
        self.username_input = self._create_input_field(
            "Username", 
            os.path.join(icon_dir, "user.png"), 
            "Enter your username"
        )
        layout.addWidget(self.username_input)
        
        # 密码
        self.password_input = self._create_input_field(
            "Password", 
            os.path.join(icon_dir, "Lock_01.png"), 
            "Enter your password", 
            is_password=True
        )
        layout.addWidget(self.password_input)
        
        # 设置默认值
        self.username_field.setText(self.default_username)
        self.password_field.setText(self.default_password)

    def _create_input_field(self, label_text, icon_path, placeholder, is_password=False):
        """创建带图标的输入框"""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        # 标签
        label = QLabel(label_text)
        label.setStyleSheet("font-size: 13px; font-weight: 600; color: #555; margin-left: 5px;")
        layout.addWidget(label)
        
        # 输入框容器
        input_wrapper = QFrame()
        input_wrapper.setObjectName("input_wrapper")
        input_wrapper.setStyleSheet("""
            QFrame#input_wrapper {
                background-color: #f4f4f4;
                border-radius: 12px;
            }
        """)
        
        # 为输入框添加独立的阴影
        input_shadow = QGraphicsDropShadowEffect()
        input_shadow.setBlurRadius(20)
        input_shadow.setColor(QColor(0, 0, 0, 25))
        input_shadow.setOffset(0, 3)
        input_wrapper.setGraphicsEffect(input_shadow)
        
        input_layout = QHBoxLayout(input_wrapper)
        input_layout.setContentsMargins(15, 10, 15, 10)
        input_layout.setSpacing(10)
        
        # 图标
        icon_label = QLabel()
        if os.path.exists(icon_path):
            pixmap = QPixmap(icon_path).scaled(20, 20, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            icon_label.setPixmap(pixmap)
        input_layout.addWidget(icon_label)
        
        # 输入框
        line_edit = QLineEdit()
        line_edit.setPlaceholderText(placeholder)
        line_edit.setStyleSheet("""
            QLineEdit {
                background-color: transparent;
                border: none;
                font-size: 14px;
                color: #333;
            }
        """)
        if is_password:
            line_edit.setEchoMode(QLineEdit.Password)
            self.password_field = line_edit
        else:
            self.username_field = line_edit
            
        line_edit.returnPressed.connect(self._on_login)
        input_layout.addWidget(line_edit)
        
        layout.addWidget(input_wrapper)
        return container

    def _create_footer(self, layout):
        """创建底部按钮和链接"""
        layout.addSpacing(10)
        
        # 登录按钮
        login_btn = QPushButton("Sign In")
        login_btn.setObjectName("login_button")
        login_btn.setMinimumHeight(50)
        login_btn.setStyleSheet("""
            QPushButton#login_button {
                background-color: #333;
                color: white;
                font-size: 16px;
                font-weight: bold;
                border-radius: 12px;
            }
            QPushButton#login_button:hover {
                background-color: #444;
            }
            QPushButton#login_button:pressed {
                background-color: #222;
            }
        """)
        
        # 按钮阴影
        btn_shadow = QGraphicsDropShadowEffect()
        btn_shadow.setBlurRadius(20)
        btn_shadow.setColor(QColor(0, 0, 0, 80))
        btn_shadow.setOffset(0, 5)
        login_btn.setGraphicsEffect(btn_shadow)
        
        login_btn.clicked.connect(self._on_login)
        layout.addWidget(login_btn)
        
        layout.addSpacing(10)
        
        # 忘记密码链接
        reset_label = QLabel("Forgot your password? <a href='#'>Reset Password</a>")
        reset_label.setStyleSheet("font-size: 12px; color: #888;")
        reset_label.setAlignment(Qt.AlignCenter)
        reset_label.setOpenExternalLinks(False)
        reset_label.linkActivated.connect(self._reset_password)
        layout.addWidget(reset_label)

    def _on_login(self):
        """处理登录逻辑"""
        username = self.username_field.text()
        password = self.password_field.text()
        
        if username == self.default_username and password == self.default_password:
            print("登录成功，准备关闭窗口")
            self.accept()  # 关闭对话框并返回QDialog.Accepted
        else:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "登录失败", "用户名或密码错误！")

    def _reset_password(self):
        """处理重置密码事件"""
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.information(self, "提示", "重置密码功能尚未实现。")

    def show_animated(self):
        """带动画的显示"""
        self.animation = QPropertyAnimation(self, b"windowOpacity")
        self.animation.setDuration(300)
        self.animation.setStartValue(0)
        self.animation.setEndValue(1)
        self.animation.setEasingCurve(QEasingCurve.InOutQuad)
        self.animation.start()
        self.exec()
