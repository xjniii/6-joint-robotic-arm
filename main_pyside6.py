#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
机械臂控制系统 - PySide6版本主程序入口
"""

import sys
import os
from PySide6.QtWidgets import QApplication, QDialog
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QIcon

# 添加项目路径
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)
    sys.path.insert(0, os.path.join(current_dir, 'modules'))

from modules_pyside6.login_window import LoginWindow
from modules_pyside6.robot_control_gui import RobotControlGUI


def main():
    """主函数"""
    try:
        # 启用高DPI支持（必须在创建QApplication之前）
        QApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )
        
        # 创建应用程序
        app = QApplication(sys.argv)
        
        # 设置应用程序属性
        app.setApplicationName("XJNIII机械臂控制系统")
        app.setOrganizationName("XJNIII")
        
        # 设置窗口图标
        icon_path = os.path.join(current_dir, "漂亮图标", "手.png")
        if os.path.exists(icon_path):
            app.setWindowIcon(QIcon(icon_path))
        
        # 设置全局字体
        font = QFont("Microsoft YaHei UI", 10)  # Windows
        if sys.platform == "darwin":  # macOS
            font = QFont("PingFang SC", 10)
        elif sys.platform == "linux":  # Linux
            font = QFont("Noto Sans CJK SC", 10)
        app.setFont(font)
        
        # 显示登录窗口
        login_window = LoginWindow()
        if login_window.exec() == 1:  # QDialog.Accepted = 1
            # 登录成功，启动主程序
            main_window = RobotControlGUI()
            main_window.show()
            
            # 运行主循环
            sys.exit(app.exec())
        else:
            print("登录失败或用户取消")
            sys.exit(0)
        
    except Exception as e:
        print(f"程序启动失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
