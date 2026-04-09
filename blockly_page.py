#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Blockly编程页面 - PySide6版本
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QGridLayout, QTextEdit, QScrollArea,
    QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox
)
from PySide6.QtCore import Qt, QMimeData, QPoint, QTimer
from PySide6.QtGui import QDrag
import datetime
import json
import os


class DropTargetWidget(QWidget):
    """可接受拖放的画布区域"""
    
    def __init__(self, blockly_page):
        super().__init__()
        self.blockly_page = blockly_page
        self.setAcceptDrops(True)
        self.drop_indicator = None
        self.drop_index = -1
    
    def dragEnterEvent(self, event):
        """拖拽进入事件"""
        if event.mimeData().hasText():
            event.acceptProposedAction()
            self._show_drop_indicator()
    
    def dragMoveEvent(self, event):
        """拖拽移动事件"""
        if event.mimeData().hasText():
            event.acceptProposedAction()
            # 更新插入指示线位置
            self._update_drop_indicator(event.pos())
    
    def dragLeaveEvent(self, event):
        """拖拽离开事件"""
        self._hide_drop_indicator()
    
    def dropEvent(self, event):
        """放置事件"""
        try:
            self._hide_drop_indicator()
        except:
            pass
        
        mime_text = event.mimeData().text()
        
        if mime_text.startswith("MOVE:"):
            # 移动现有积木块
            try:
                old_index = int(mime_text.split(":")[1])
                
                # 验证索引有效性
                if old_index < 0 or old_index >= len(self.blockly_page.blocks):
                    print(f"无效的索引: {old_index}, 总数: {len(self.blockly_page.blocks)}")
                    event.ignore()
                    return
                
                # 计算新位置
                drop_pos = event.pos()
                new_index = self._calculate_drop_index(drop_pos)
                
                # 如果位置没变，不做任何操作
                if new_index == old_index or (new_index == old_index + 1):
                    event.acceptProposedAction()
                    return
                
                # 获取要移动的积木块
                block = self.blockly_page.blocks[old_index]
                
                # 调整索引（如果新位置在旧位置之后）
                if new_index > old_index:
                    new_index -= 1
                
                # 从列表中移除
                self.blockly_page.blocks.pop(old_index)
                
                # 从布局中移除（但不删除对象）
                self.blockly_page.canvas_layout.removeWidget(block)
                
                # 插入到新位置
                self.blockly_page.blocks.insert(new_index, block)
                self.blockly_page.canvas_layout.insertWidget(new_index, block)
                
                # 确保显示
                block.setVisible(True)
                
                # 更新代码预览
                try:
                    self.blockly_page._update_code_preview()
                except Exception as e:
                    print(f"更新代码预览失败: {e}")
                
                # 记录日志
                try:
                    self.blockly_page._log(f"积木块已移动: 从位置{old_index+1}到位置{new_index+1}")
                except Exception as e:
                    print(f"记录日志失败: {e}")
                
                event.acceptProposedAction()
                
            except Exception as e:
                print(f"移动积木块失败: {e}")
                import traceback
                traceback.print_exc()
                event.ignore()
        else:
            # 新建积木块（从工具箱拖入）
            event.ignore()
    
    def _calculate_drop_index(self, pos):
        """根据放置位置计算插入索引"""
        # 遍历所有积木块，找到最接近的位置
        for i, block in enumerate(self.blockly_page.blocks):
            block_pos = block.pos()
            block_center_y = block_pos.y() + block.height() / 2
            
            if pos.y() < block_center_y:
                return i
        
        # 如果在所有积木块之后，返回末尾位置
        return len(self.blockly_page.blocks)
    
    def _show_drop_indicator(self):
        """显示插入指示线"""
        if not self.drop_indicator:
            self.drop_indicator = QFrame(self)
            self.drop_indicator.setStyleSheet("""
                QFrame {
                    background: #667eea;
                    border-radius: 2px;
                }
            """)
            self.drop_indicator.setFixedHeight(4)
            self.drop_indicator.hide()
    
    def _update_drop_indicator(self, pos):
        """更新插入指示线位置"""
        if not self.drop_indicator:
            return
        
        if not self.blockly_page.blocks:
            # 没有积木块时，显示在顶部
            self.drop_indicator.setGeometry(15, 10, self.width() - 30, 4)
            self.drop_indicator.show()
            self.drop_indicator.raise_()
            return
        
        # 计算插入位置
        insert_index = self._calculate_drop_index(pos)
        
        if insert_index != self.drop_index:
            self.drop_index = insert_index
            
            try:
                # 计算指示线的Y坐标
                if insert_index == 0:
                    # 插入到第一个位置
                    y_pos = self.blockly_page.blocks[0].pos().y() - 7
                elif insert_index >= len(self.blockly_page.blocks):
                    # 插入到最后
                    last_block = self.blockly_page.blocks[-1]
                    y_pos = last_block.pos().y() + last_block.height() + 3
                else:
                    # 插入到中间
                    prev_block = self.blockly_page.blocks[insert_index - 1]
                    y_pos = prev_block.pos().y() + prev_block.height() + 3
                
                # 设置指示线位置和宽度
                self.drop_indicator.setGeometry(15, y_pos, self.width() - 30, 4)
                self.drop_indicator.show()
                self.drop_indicator.raise_()
            except Exception as e:
                print(f"更新指示线失败: {e}")
                self.drop_indicator.hide()
    
    def _hide_drop_indicator(self):
        """隐藏插入指示线"""
        if self.drop_indicator:
            self.drop_indicator.hide()
        self.drop_index = -1


class DraggableBlock(QFrame):
    """可拖拽的积木块"""
    
    def __init__(self, block_type, title, color, parent=None):
        super().__init__(parent)
        self.block_type = block_type
        self.block_data = {}
        self.drag_start_position = None
        
        self.setObjectName("draggable_block")
        self.setStyleSheet(f"""
            QFrame#draggable_block {{
                background: {color};
                border-radius: 8px;
                padding: 8px;
            }}
        """)
        self.setMinimumWidth(200)
        self.setMaximumWidth(400)
        
        # 主布局 - 横向
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(6, 5, 6, 5)
        main_layout.setSpacing(8)
        
        # 标题
        title_label = QLabel(title)
        title_label.setStyleSheet("color: white; font-size: 10px; font-weight: bold;")
        title_label.setWordWrap(False)
        main_layout.addWidget(title_label)
        
        # 内容区域
        self.content_widget = QWidget()
        self.content_layout = QHBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(4)
        main_layout.addWidget(self.content_widget, 1)
        
        # 关闭按钮
        delete_btn = QPushButton("×")
        delete_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255,255,255,0.3);
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 12px;
                font-weight: bold;
                padding: 0px;
            }
            QPushButton:hover {
                background: rgba(255,255,255,0.5);
            }
        """)
        delete_btn.setFixedSize(16, 16)
        delete_btn.clicked.connect(self.deleteLater)
        main_layout.addWidget(delete_btn)
    
    def use_vertical_layout(self):
        """切换到垂直布局（用于多行内容）"""
        # 移除横向内容布局
        self.content_layout.deleteLater()
        
        # 创建垂直内容布局
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(3)
    
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_start_position = event.pos()
            # 检查是否点击在子控件上（输入框、按钮等）
            child = self.childAt(event.pos())
            if child and not isinstance(child, QLabel):
                # 如果点击在输入控件上，不启动拖拽
                self.drag_start_position = None
    
    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.LeftButton):
            return
        if self.drag_start_position is None:
            return
        if (event.pos() - self.drag_start_position).manhattanLength() < 10:
            return
        
        # 创建拖拽操作
        drag = QDrag(self)
        mime_data = QMimeData()
        
        # 保存当前积木块的索引
        try:
            # 查找当前积木块在blocks列表中的索引
            blockly_page = self
            while blockly_page and not isinstance(blockly_page, BlocklyPage):
                blockly_page = blockly_page.parent()
            
            if blockly_page and hasattr(blockly_page, 'blocks'):
                if self in blockly_page.blocks:
                    index = blockly_page.blocks.index(self)
                    mime_data.setText(f"MOVE:{index}")
                else:
                    mime_data.setText(self.block_type)
            else:
                mime_data.setText(self.block_type)
        except Exception as e:
            print(f"获取索引失败: {e}")
            mime_data.setText(self.block_type)
        
        drag.setMimeData(mime_data)
        
        # 执行拖拽（不设置预览图，避免崩溃）
        drag.exec_(Qt.MoveAction)
    
    def get_instruction(self):
        """获取积木块指令"""
        return {"type": self.block_type, "data": self.block_data}


class BlocklyPage(QWidget):
    """Blockly编程页面"""
    
    def __init__(self, parent, main_gui):
        super().__init__(parent)
        self.main_gui = main_gui
        self.blocks = []  # 存储画布上的积木块
        self.execution_index = 0
        self.execution_timer = None
        self.is_paused = False  # 暂停状态
        self.is_looping = False  # 循环状态
        
        # 循环控制 - 简化方案
        self.loop_info = {}  # {loop_start_index: {'count': N, 'current': 0, 'end': end_index}}
        
        # 等待到达相关变量
        self.waiting_for_arrival = False
        self.target_angles = None
        self.target_chassis_angles = None
        self.arrival_check_count = 0
        self.max_arrival_checks = 600  # 最大检查次数（60秒）
        
        self._init_ui()
    
    def _init_ui(self):
        """初始化UI"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)
        
        # 顶部工具栏
        toolbar = self._create_toolbar()
        main_layout.addWidget(toolbar)
        
        # 主内容区域
        content = QWidget()
        content_layout = QHBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(15)
        
        # 左侧：积木块工具箱
        toolbox = self._create_toolbox()
        content_layout.addWidget(toolbox, 1)
        
        # 中间：编程画布
        canvas = self._create_canvas()
        content_layout.addWidget(canvas, 3)
        
        # 右侧：代码预览和执行日志
        right_panel = self._create_right_panel()
        content_layout.addWidget(right_panel, 1)
        
        main_layout.addWidget(content, 1)
    
    def _create_toolbar(self):
        """创建工具栏"""
        toolbar = QFrame()
        toolbar.setObjectName("card")
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(15, 10, 15, 10)
        toolbar_layout.setSpacing(10)
        
        title = QLabel("🧩 Blockly 可视化编程")
        title.setStyleSheet("color: #1e293b; font-size: 18px; font-weight: bold;")
        toolbar_layout.addWidget(title)
        
        toolbar_layout.addStretch()
        
        new_btn = QPushButton("新建项目")
        new_btn.setObjectName("secondary_button")
        new_btn.setMinimumSize(100, 36)
        new_btn.clicked.connect(self._new_project)
        toolbar_layout.addWidget(new_btn)
        
        load_btn = QPushButton("加载项目")
        load_btn.setObjectName("secondary_button")
        load_btn.setMinimumSize(100, 36)
        load_btn.clicked.connect(self._load_project)
        toolbar_layout.addWidget(load_btn)
        
        save_btn = QPushButton("保存项目")
        save_btn.setObjectName("primary_button")
        save_btn.setMinimumSize(100, 36)
        save_btn.clicked.connect(self._save_project)
        toolbar_layout.addWidget(save_btn)
        
        self.run_btn = QPushButton("▶ 运行")
        self.run_btn.setObjectName("primary_button")
        self.run_btn.setMinimumSize(100, 36)
        self.run_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #10b981, stop:1 #059669);
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #059669, stop:1 #047857);
            }
        """)
        self.run_btn.clicked.connect(self._run_program)
        toolbar_layout.addWidget(self.run_btn)
        
        self.pause_btn = QPushButton("⏸ 暂停")
        self.pause_btn.setObjectName("secondary_button")
        self.pause_btn.setMinimumSize(100, 36)
        self.pause_btn.setEnabled(False)
        self.pause_btn.clicked.connect(self._toggle_pause)
        toolbar_layout.addWidget(self.pause_btn)
        
        self.stop_btn = QPushButton("⏹ 停止")
        self.stop_btn.setObjectName("secondary_button")
        self.stop_btn.setMinimumSize(100, 36)
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background: #ef4444;
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #dc2626;
            }
            QPushButton:disabled {
                background: #cbd5e1;
                color: #94a3b8;
            }
        """)
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._stop_program)
        toolbar_layout.addWidget(self.stop_btn)
        
        self.loop_btn = QPushButton("🔁 循环")
        self.loop_btn.setObjectName("secondary_button")
        self.loop_btn.setMinimumSize(100, 36)
        self.loop_btn.setCheckable(True)
        self.loop_btn.setStyleSheet("""
            QPushButton {
                background: #f8fafc;
                color: #64748b;
                border: 2px solid #e2e8f0;
                border-radius: 8px;
                font-size: 13px;
                font-weight: 500;
            }
            QPushButton:hover {
                background: #f1f5f9;
                border-color: #cbd5e1;
                color: #475569;
            }
            QPushButton:checked {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #667eea, stop:1 #764ba2);
                color: white;
                border: none;
            }
        """)
        self.loop_btn.clicked.connect(self._toggle_loop)
        toolbar_layout.addWidget(self.loop_btn)
        
        return toolbar
    
    def _create_toolbox(self):
        """创建积木块工具箱"""
        toolbox = QFrame()
        toolbox.setObjectName("card")
        toolbox_layout = QVBoxLayout(toolbox)
        toolbox_layout.setContentsMargins(15, 15, 15, 15)
        toolbox_layout.setSpacing(10)
        
        title = QLabel("积木块")
        title.setStyleSheet("color: #1e293b; font-size: 14px; font-weight: bold;")
        toolbox_layout.addWidget(title)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(5)
        
        # 所有积木块分类
        block_categories = [
            ("🎯 运动", "#6b9fa3", [
                ("joint_move", "关节运动"),
                ("chassis_move", "底盘移动"),
                ("movel", "直线运动"),
                ("movec", "圆弧运动"),
            ]),
            ("⚙️ 设置", "#4CAF50", [
                ("speed", "设置速度"),
                ("acceleration", "设置加速度"),
            ]),
            ("🔌 IO控制", "#FF9800", [
                ("digital_out", "数字输出"),
                ("digital_in", "数字输入"),
                ("analog_out", "模拟输出"),
                ("analog_in", "模拟输入"),
            ]),
            ("🤏 末端执行器", "#9C27B0", [
                ("gripper", "夹爪控制"),
                ("suction", "吸盘控制"),
            ]),
            ("🔄 循环", "#8e6bb0", [
                ("while_loop", "条件循环"),
                ("break", "跳出循环"),
            ]),
            ("🔀 逻辑", "#607D8B", [
                ("if_condition", "条件判断"),
                ("compare", "比较"),
            ]),
            ("📊 数学", "#1976D2", [
                ("variable", "设置变量"),
                ("math_op", "数学运算"),
                ("random", "随机数"),
            ]),
            ("⏱️ 时间", "#0097A7", [
                ("delay", "延时"),
                ("wait_condition", "等待条件"),
            ]),
            ("📦 应用", "#388E3C", [
                ("pick_place", "抓取放置"),
                ("palletizing", "码垛"),
            ]),
            ("🔧 其他", "#795548", [
                ("comment", "注释"),
                ("print", "打印"),
            ])
        ]
        
        for cat_name, color, blocks in block_categories:
            # 创建可折叠分类
            category_widget = self._create_collapsible_category(cat_name, color, blocks)
            scroll_layout.addWidget(category_widget)
        
        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        toolbox_layout.addWidget(scroll, 1)
        
        return toolbox
    
    def _create_collapsible_category(self, cat_name, color, blocks):
        """创建可折叠的分类"""
        category_frame = QFrame()
        category_layout = QVBoxLayout(category_frame)
        category_layout.setContentsMargins(0, 0, 0, 0)
        category_layout.setSpacing(3)
        
        # 分类标题按钮（可点击展开/折叠）
        cat_btn = QPushButton(f"▶ {cat_name}")
        cat_btn.setStyleSheet(f"""
            QPushButton {{
                background: {color};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 10px;
                text-align: left;
                font-size: 11px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: {color}dd;
            }}
        """)
        cat_btn.setMinimumHeight(36)
        cat_btn.setCursor(Qt.PointingHandCursor)
        category_layout.addWidget(cat_btn)
        
        # 积木块容器（默认隐藏）
        blocks_container = QWidget()
        blocks_layout = QVBoxLayout(blocks_container)
        blocks_layout.setContentsMargins(10, 0, 0, 0)
        blocks_layout.setSpacing(3)
        
        for block_type, block_name in blocks:
            btn = QPushButton(f"  ➕ {block_name}")
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {color}cc;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 6px 8px;
                    text-align: left;
                    font-size: 10px;
                    font-weight: 600;
                }}
                QPushButton:hover {{
                    background: {color}ee;
                }}
            """)
            btn.setMinimumHeight(28)
            btn.clicked.connect(lambda checked, bt=block_type, bn=block_name, c=color: self._add_block(bt, bn, c))
            blocks_layout.addWidget(btn)
        
        blocks_container.setVisible(False)
        category_layout.addWidget(blocks_container)
        
        # 点击标题切换展开/折叠
        def toggle_category():
            is_visible = blocks_container.isVisible()
            blocks_container.setVisible(not is_visible)
            if is_visible:
                cat_btn.setText(f"▶ {cat_name}")
            else:
                cat_btn.setText(f"▼ {cat_name}")
        
        cat_btn.clicked.connect(toggle_category)
        
        return category_frame
    
    def _add_block(self, block_type, block_name, color):
        """添加积木块到画布"""
        block = self._create_block(block_type, block_name, color)
        if block:
            self.canvas_layout.insertWidget(self.canvas_layout.count() - 1, block)
            self.blocks.append(block)
            self._update_code_preview()

    def _create_block(self, block_type, block_name, color):
        """创建积木块"""
        block = DraggableBlock(block_type, block_name, color)
        
        # 通用样式
        input_style = """
            background: rgba(255,255,255,0.2);
            color: white;
            border: 1px solid rgba(255,255,255,0.3);
            border-radius: 4px;
            padding: 3px;
            font-size: 10px;
        """
        
        # QComboBox专用样式（修复下拉菜单文字颜色问题）
        combo_style = """
            QComboBox {
                background: rgba(255,255,255,0.2);
                color: white;
                border: 1px solid rgba(255,255,255,0.3);
                border-radius: 4px;
                padding: 3px;
                font-size: 10px;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 4px solid white;
            }
            QComboBox QAbstractItemView {
                background: white;
                color: #1e293b;
                selection-background-color: #667eea;
                selection-color: white;
                border: 1px solid #e2e8f0;
            }
        """
        
        if block_type == "joint_move":
            # 关节运动积木块 - 4个关节横向排列
            for i in range(4):
                col = QWidget()
                col_layout = QVBoxLayout(col)
                col_layout.setContentsMargins(0, 0, 0, 0)
                col_layout.setSpacing(2)
                
                label = QLabel(f"J{i+1}")
                label.setStyleSheet("color: white; font-size: 9px;")
                label.setAlignment(Qt.AlignCenter)
                col_layout.addWidget(label)
                
                spin = QDoubleSpinBox()
                spin.setRange(-180, 180)
                spin.setValue(0)
                spin.setSuffix("°")
                spin.setStyleSheet(input_style)
                spin.setMinimumHeight(20)
                spin.setMinimumWidth(60)
                spin.setMaximumWidth(70)
                col_layout.addWidget(spin)
                
                block.content_layout.addWidget(col)
                block.block_data[f"j{i+1}"] = spin
            
            # 添加等待到达勾选框
            from PySide6.QtWidgets import QCheckBox
            wait_check = QCheckBox("等待")
            wait_check.setStyleSheet("color: white; font-size: 10px;")
            wait_check.setChecked(True)  # 默认勾选
            wait_check.setToolTip("等待机械臂到达目标角度(±1°)")
            block.content_layout.addWidget(wait_check)
            block.block_data["wait_arrival"] = wait_check
        
        elif block_type == "chassis_move":
            # 底盘移动积木块
            direction_combo = QComboBox()
            direction_combo.addItems(["前进", "后退", "左移", "右移", "左转", "右转"])
            direction_combo.setStyleSheet(combo_style)
            direction_combo.setMinimumHeight(20)
            direction_combo.setMinimumWidth(60)
            direction_combo.setMaximumWidth(70)
            block.content_layout.addWidget(direction_combo)
            block.block_data["direction"] = direction_combo
            
            value_spin = QDoubleSpinBox()
            value_spin.setRange(0, 1000)
            value_spin.setValue(100)
            value_spin.setStyleSheet(input_style)
            value_spin.setMinimumHeight(20)
            value_spin.setMinimumWidth(70)
            value_spin.setMaximumWidth(80)
            block.content_layout.addWidget(value_spin)
            block.block_data["value"] = value_spin
            
            # 添加等待到达勾选框
            from PySide6.QtWidgets import QCheckBox
            wait_check = QCheckBox("等待")
            wait_check.setStyleSheet("color: white; font-size: 10px;")
            wait_check.setChecked(True)  # 默认勾选
            wait_check.setToolTip("等待底盘到达目标位置(±1°)")
            block.content_layout.addWidget(wait_check)
            block.block_data["wait_arrival"] = wait_check
        
        elif block_type == "movel":
            # 直线运动
            for axis in ["X", "Y", "Z"]:
                label = QLabel(f"{axis}:")
                label.setStyleSheet("color: white; font-size: 9px;")
                block.content_layout.addWidget(label)
                
                spin = QDoubleSpinBox()
                spin.setRange(-1000, 1000)
                spin.setValue(0)
                spin.setStyleSheet(input_style)
                spin.setMinimumHeight(20)
                spin.setMaximumWidth(50)
                block.content_layout.addWidget(spin)
                block.block_data[axis.lower()] = spin
        
        elif block_type == "movec":
            # 圆弧运动 - 需要两行
            block.use_vertical_layout()
            
            row1 = QWidget()
            row1_layout = QHBoxLayout(row1)
            row1_layout.setContentsMargins(0, 0, 0, 0)
            row1_layout.setSpacing(2)
            
            label1 = QLabel("中:")
            label1.setStyleSheet("color: white; font-size: 9px;")
            row1_layout.addWidget(label1)
            
            for axis in ["X", "Y", "Z"]:
                spin = QDoubleSpinBox()
                spin.setRange(-1000, 1000)
                spin.setValue(0)
                spin.setSuffix("mm")
                spin.setStyleSheet(input_style)
                spin.setMinimumHeight(20)
                spin.setMaximumWidth(60)
                row1_layout.addWidget(spin)
                block.block_data[f"via_{axis.lower()}"] = spin
            
            block.content_layout.addWidget(row1)
            
            row2 = QWidget()
            row2_layout = QHBoxLayout(row2)
            row2_layout.setContentsMargins(0, 0, 0, 0)
            row2_layout.setSpacing(2)
            
            label2 = QLabel("目:")
            label2.setStyleSheet("color: white; font-size: 9px;")
            row2_layout.addWidget(label2)
            
            for axis in ["X", "Y", "Z"]:
                spin = QDoubleSpinBox()
                spin.setRange(-1000, 1000)
                spin.setValue(0)
                spin.setSuffix("mm")
                spin.setStyleSheet(input_style)
                spin.setMinimumHeight(20)
                spin.setMaximumWidth(60)
                row2_layout.addWidget(spin)
                block.block_data[f"to_{axis.lower()}"] = spin
            
            block.content_layout.addWidget(row2)
        
        elif block_type == "speed":
            # 设置速度
            label = QLabel("速度:")
            label.setStyleSheet("color: white; font-size: 9px;")
            block.content_layout.addWidget(label)
            
            spin = QDoubleSpinBox()
            spin.setRange(1, 100)
            spin.setValue(50)
            spin.setSuffix("%")
            spin.setStyleSheet(input_style)
            spin.setMinimumHeight(20)
            spin.setMaximumWidth(60)
            block.content_layout.addWidget(spin)
            block.block_data["speed"] = spin
        
        elif block_type == "acceleration":
            # 设置加速度
            label = QLabel("加速度:")
            label.setStyleSheet("color: white; font-size: 9px;")
            block.content_layout.addWidget(label)
            
            spin = QDoubleSpinBox()
            spin.setRange(100, 2000)
            spin.setValue(500)
            spin.setStyleSheet(input_style)
            spin.setMinimumHeight(20)
            spin.setMaximumWidth(65)
            block.content_layout.addWidget(spin)
            block.block_data["acceleration"] = spin
        
        elif block_type == "digital_out":
            # 数字输出
            label1 = QLabel("IO:")
            label1.setStyleSheet("color: white; font-size: 9px;")
            block.content_layout.addWidget(label1)
            
            io_spin = QSpinBox()
            io_spin.setRange(0, 15)
            io_spin.setValue(0)
            io_spin.setStyleSheet(input_style)
            io_spin.setMinimumHeight(20)
            io_spin.setMaximumWidth(40)
            block.content_layout.addWidget(io_spin)
            block.block_data["io"] = io_spin
            
            value_combo = QComboBox()
            value_combo.addItems(["HIGH", "LOW"])
            value_combo.setStyleSheet(combo_style)
            value_combo.setMinimumHeight(20)
            value_combo.setMaximumWidth(60)
            block.content_layout.addWidget(value_combo)
            block.block_data["value"] = value_combo
        
        elif block_type == "digital_in":
            # 数字输入
            label = QLabel("IO:")
            label.setStyleSheet("color: white; font-size: 9px;")
            block.content_layout.addWidget(label)
            
            io_spin = QSpinBox()
            io_spin.setRange(0, 15)
            io_spin.setValue(0)
            io_spin.setStyleSheet(input_style)
            io_spin.setMinimumHeight(20)
            io_spin.setMaximumWidth(45)
            block.content_layout.addWidget(io_spin)
            block.block_data["io"] = io_spin
        
        elif block_type == "analog_out":
            # 模拟输出
            label1 = QLabel("IO:")
            label1.setStyleSheet("color: white; font-size: 9px;")
            block.content_layout.addWidget(label1)
            
            io_spin = QSpinBox()
            io_spin.setRange(0, 15)
            io_spin.setValue(0)
            io_spin.setStyleSheet(input_style)
            io_spin.setMinimumHeight(20)
            io_spin.setMaximumWidth(40)
            block.content_layout.addWidget(io_spin)
            block.block_data["io"] = io_spin
            
            label2 = QLabel("值:")
            label2.setStyleSheet("color: white; font-size: 9px;")
            block.content_layout.addWidget(label2)
            
            value_spin = QDoubleSpinBox()
            value_spin.setRange(0, 10)
            value_spin.setValue(0)
            value_spin.setDecimals(2)
            value_spin.setStyleSheet(input_style)
            value_spin.setMinimumHeight(20)
            value_spin.setMaximumWidth(50)
            block.content_layout.addWidget(value_spin)
            block.block_data["value"] = value_spin
        
        elif block_type == "analog_in":
            # 模拟输入
            label = QLabel("IO:")
            label.setStyleSheet("color: white; font-size: 9px;")
            block.content_layout.addWidget(label)
            
            io_spin = QSpinBox()
            io_spin.setRange(0, 15)
            io_spin.setValue(0)
            io_spin.setStyleSheet(input_style)
            io_spin.setMinimumHeight(20)
            io_spin.setMaximumWidth(45)
            block.content_layout.addWidget(io_spin)
            block.block_data["io"] = io_spin
        
        elif block_type == "gripper":
            # 夹爪控制
            action_combo = QComboBox()
            action_combo.addItems(["打开", "关闭", "设置位置"])
            action_combo.setStyleSheet(combo_style)
            action_combo.setMinimumHeight(20)
            action_combo.setMaximumWidth(75)
            block.content_layout.addWidget(action_combo)
            block.block_data["action"] = action_combo
            
            # 位置输入（仅在"设置位置"时显示）
            pos_spin = QDoubleSpinBox()
            pos_spin.setRange(0, 100)
            pos_spin.setValue(50)
            pos_spin.setSuffix("%")
            pos_spin.setStyleSheet(input_style)
            pos_spin.setMinimumHeight(20)
            pos_spin.setMaximumWidth(55)
            pos_spin.setVisible(False)
            block.content_layout.addWidget(pos_spin)
            block.block_data["position"] = pos_spin
            
            action_combo.currentTextChanged.connect(lambda text: pos_spin.setVisible(text == "设置位置"))
        
        elif block_type == "suction":
            # 吸盘控制
            action_combo = QComboBox()
            action_combo.addItems(["开启", "关闭"])
            action_combo.setStyleSheet(combo_style)
            action_combo.setMinimumHeight(20)
            action_combo.setMaximumWidth(55)
            block.content_layout.addWidget(action_combo)
            block.block_data["action"] = action_combo
        
        elif block_type == "while_loop":
            # 条件循环
            label1 = QLabel("循环:")
            label1.setStyleSheet("color: white; font-size: 9px;")
            block.content_layout.addWidget(label1)
            
            count_spin = QSpinBox()
            count_spin.setRange(1, 999)
            count_spin.setValue(10)
            count_spin.setSuffix(" 次")
            count_spin.setStyleSheet(input_style)
            count_spin.setMinimumHeight(20)
            count_spin.setMaximumWidth(70)
            block.content_layout.addWidget(count_spin)
            block.block_data["count"] = count_spin
        
        elif block_type == "break":
            # 跳出循环（无参数）
            pass
        
        elif block_type == "if_condition":
            # 条件判断
            label = QLabel("条件:")
            label.setStyleSheet("color: white; font-size: 9px;")
            block.content_layout.addWidget(label)
            
            condition_entry = QLineEdit()
            condition_entry.setText("True")
            condition_entry.setStyleSheet(input_style)
            condition_entry.setMinimumHeight(20)
            condition_entry.setMaximumWidth(80)
            block.content_layout.addWidget(condition_entry)
            block.block_data["condition"] = condition_entry
        
        elif block_type == "compare":
            # 比较
            val1_entry = QLineEdit()
            val1_entry.setText("0")
            val1_entry.setStyleSheet(input_style)
            val1_entry.setMinimumHeight(20)
            val1_entry.setMaximumWidth(40)
            block.content_layout.addWidget(val1_entry)
            block.block_data["value1"] = val1_entry
            
            op_combo = QComboBox()
            op_combo.addItems(["==", "!=", ">", "<", ">=", "<="])
            op_combo.setStyleSheet(combo_style)
            op_combo.setMinimumHeight(20)
            op_combo.setMaximumWidth(40)
            block.content_layout.addWidget(op_combo)
            block.block_data["operator"] = op_combo
            
            val2_entry = QLineEdit()
            val2_entry.setText("0")
            val2_entry.setStyleSheet(input_style)
            val2_entry.setMinimumHeight(20)
            val2_entry.setMaximumWidth(40)
            block.content_layout.addWidget(val2_entry)
            block.block_data["value2"] = val2_entry
        
        elif block_type == "variable":
            # 设置变量
            name_entry = QLineEdit()
            name_entry.setText("var1")
            name_entry.setStyleSheet(input_style)
            name_entry.setMinimumHeight(20)
            name_entry.setMaximumWidth(45)
            block.content_layout.addWidget(name_entry)
            block.block_data["name"] = name_entry
            
            label = QLabel("=")
            label.setStyleSheet("color: white; font-size: 9px;")
            block.content_layout.addWidget(label)
            
            value_entry = QLineEdit()
            value_entry.setText("0")
            value_entry.setStyleSheet(input_style)
            value_entry.setMinimumHeight(20)
            value_entry.setMaximumWidth(50)
            block.content_layout.addWidget(value_entry)
            block.block_data["value"] = value_entry
        
        elif block_type == "math_op":
            # 数学运算
            val1_entry = QLineEdit()
            val1_entry.setText("0")
            val1_entry.setStyleSheet(input_style)
            val1_entry.setMinimumHeight(20)
            val1_entry.setMaximumWidth(40)
            block.content_layout.addWidget(val1_entry)
            block.block_data["value1"] = val1_entry
            
            op_combo = QComboBox()
            op_combo.addItems(["+", "-", "*", "/", "%"])
            op_combo.setStyleSheet(combo_style)
            op_combo.setMinimumHeight(20)
            op_combo.setMaximumWidth(35)
            block.content_layout.addWidget(op_combo)
            block.block_data["operator"] = op_combo
            
            val2_entry = QLineEdit()
            val2_entry.setText("0")
            val2_entry.setStyleSheet(input_style)
            val2_entry.setMinimumHeight(20)
            val2_entry.setMaximumWidth(40)
            block.content_layout.addWidget(val2_entry)
            block.block_data["value2"] = val2_entry
        
        elif block_type == "random":
            # 随机数
            label1 = QLabel("从:")
            label1.setStyleSheet("color: white; font-size: 9px;")
            block.content_layout.addWidget(label1)
            
            min_spin = QSpinBox()
            min_spin.setRange(-1000, 1000)
            min_spin.setValue(0)
            min_spin.setStyleSheet(input_style)
            min_spin.setMinimumHeight(20)
            min_spin.setMaximumWidth(45)
            block.content_layout.addWidget(min_spin)
            block.block_data["min"] = min_spin
            
            label2 = QLabel("到:")
            label2.setStyleSheet("color: white; font-size: 9px;")
            block.content_layout.addWidget(label2)
            
            max_spin = QSpinBox()
            max_spin.setRange(-1000, 1000)
            max_spin.setValue(100)
            max_spin.setStyleSheet(input_style)
            max_spin.setMinimumHeight(20)
            max_spin.setMaximumWidth(45)
            block.content_layout.addWidget(max_spin)
            block.block_data["max"] = max_spin
        
        elif block_type == "delay":
            # 延时
            label = QLabel("时间:")
            label.setStyleSheet("color: white; font-size: 9px;")
            block.content_layout.addWidget(label)
            
            spin = QDoubleSpinBox()
            spin.setRange(0.1, 60)
            spin.setValue(1.0)
            spin.setSuffix(" 秒")
            spin.setDecimals(1)
            spin.setStyleSheet(input_style)
            spin.setMinimumHeight(20)
            spin.setMaximumWidth(60)
            block.content_layout.addWidget(spin)
            block.block_data["time"] = spin
        
        elif block_type == "wait_condition":
            # 等待条件
            label = QLabel("条件:")
            label.setStyleSheet("color: white; font-size: 9px;")
            block.content_layout.addWidget(label)
            
            condition_entry = QLineEdit()
            condition_entry.setText("True")
            condition_entry.setStyleSheet(input_style)
            condition_entry.setMinimumHeight(20)
            condition_entry.setMaximumWidth(80)
            block.content_layout.addWidget(condition_entry)
            block.block_data["condition"] = condition_entry
        
        elif block_type == "pick_place":
            # 抓取放置（无参数）
            label = QLabel("抓取→放置")
            label.setStyleSheet("color: white; font-size: 9px;")
            block.content_layout.addWidget(label)
        
        elif block_type == "palletizing":
            # 码垛
            label1 = QLabel("行:")
            label1.setStyleSheet("color: white; font-size: 9px;")
            block.content_layout.addWidget(label1)
            
            rows_spin = QSpinBox()
            rows_spin.setRange(1, 10)
            rows_spin.setValue(3)
            rows_spin.setStyleSheet(input_style)
            rows_spin.setMinimumHeight(20)
            rows_spin.setMaximumWidth(40)
            block.content_layout.addWidget(rows_spin)
            block.block_data["rows"] = rows_spin
            
            label2 = QLabel("列:")
            label2.setStyleSheet("color: white; font-size: 9px;")
            block.content_layout.addWidget(label2)
            
            cols_spin = QSpinBox()
            cols_spin.setRange(1, 10)
            cols_spin.setValue(3)
            cols_spin.setStyleSheet(input_style)
            cols_spin.setMinimumHeight(20)
            cols_spin.setMaximumWidth(40)
            block.content_layout.addWidget(cols_spin)
            block.block_data["cols"] = cols_spin
        
        elif block_type == "comment":
            # 注释
            comment_entry = QLineEdit()
            comment_entry.setText("# 注释")
            comment_entry.setStyleSheet(input_style)
            comment_entry.setMinimumHeight(20)
            comment_entry.setMaximumWidth(120)
            block.content_layout.addWidget(comment_entry)
            block.block_data["text"] = comment_entry
        
        elif block_type == "print":
            # 打印
            label = QLabel("内容:")
            label.setStyleSheet("color: white; font-size: 9px;")
            block.content_layout.addWidget(label)
            
            text_entry = QLineEdit()
            text_entry.setText("Hello")
            text_entry.setStyleSheet(input_style)
            text_entry.setMinimumHeight(20)
            text_entry.setMaximumWidth(80)
            block.content_layout.addWidget(text_entry)
            block.block_data["text"] = text_entry
        
        return block
        """创建积木块"""
        block = DraggableBlock(block_type, block_name, color)
        
        # 通用样式
        input_style = """
            background: rgba(255,255,255,0.2);
            color: white;
            border: 1px solid rgba(255,255,255,0.3);
            border-radius: 4px;
            padding: 3px;
            font-size: 10px;
        """
        
        if block_type == "joint_move":
            # 关节运动积木块
            for i in range(4):
                row = QWidget()
                row_layout = QHBoxLayout(row)
                row_layout.setContentsMargins(0, 0, 0, 0)
                row_layout.setSpacing(5)
                
                label = QLabel(f"J{i+1}:")
                label.setStyleSheet("color: white; font-size: 10px; min-width: 25px;")
                row_layout.addWidget(label)
                
                spin = QDoubleSpinBox()
                spin.setRange(-180, 180)
                spin.setValue(0)
                spin.setSuffix("°")
                spin.setStyleSheet(input_style)
                spin.setMinimumHeight(24)
                row_layout.addWidget(spin, 1)
                
                block.content_layout.addWidget(row)
                block.block_data[f"j{i+1}"] = spin
        
        elif block_type == "chassis_move":
            # 底盘移动积木块（带方向选择）
            row1 = QWidget()
            row1_layout = QHBoxLayout(row1)
            row1_layout.setContentsMargins(0, 0, 0, 0)
            row1_layout.setSpacing(5)
            
            label1 = QLabel("方向:")
            label1.setStyleSheet("color: white; font-size: 10px;")
            row1_layout.addWidget(label1)
            
            direction_combo = QComboBox()
            direction_combo.addItems(["前进", "后退", "左移", "右移", "左转", "右转"])
            direction_combo.setStyleSheet(combo_style)
            direction_combo.setMinimumHeight(24)
            row1_layout.addWidget(direction_combo, 1)
            block.content_layout.addWidget(row1)
            block.block_data["direction"] = direction_combo
            
            row2 = QWidget()
            row2_layout = QHBoxLayout(row2)
            row2_layout.setContentsMargins(0, 0, 0, 0)
            row2_layout.setSpacing(5)
            
            label2 = QLabel("数值:")
            label2.setStyleSheet("color: white; font-size: 10px;")
            row2_layout.addWidget(label2)
            
            value_spin = QDoubleSpinBox()
            value_spin.setRange(0, 1000)
            value_spin.setValue(100)
            value_spin.setStyleSheet(input_style)
            value_spin.setMinimumHeight(24)
            row2_layout.addWidget(value_spin, 1)
            block.content_layout.addWidget(row2)
            block.block_data["value"] = value_spin
        
        elif block_type == "movel":
            # 直线运动
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(5)
            
            for axis in ["X", "Y", "Z"]:
                label = QLabel(f"{axis}:")
                label.setStyleSheet("color: white; font-size: 10px; min-width: 18px;")
                row_layout.addWidget(label)
                
                spin = QDoubleSpinBox()
                spin.setRange(-1000, 1000)
                spin.setValue(0)
                spin.setStyleSheet(input_style)
                spin.setMinimumHeight(24)
                row_layout.addWidget(spin)
                block.block_data[axis.lower()] = spin
            
            block.content_layout.addWidget(row)
        
        elif block_type == "movec":
            # 圆弧运动
            row1 = QWidget()
            row1_layout = QHBoxLayout(row1)
            row1_layout.setContentsMargins(0, 0, 0, 0)
            row1_layout.setSpacing(3)
            
            label1 = QLabel("中间:")
            label1.setStyleSheet("color: white; font-size: 10px;")
            row1_layout.addWidget(label1)
            
            for axis in ["X", "Y", "Z"]:
                spin = QDoubleSpinBox()
                spin.setRange(-1000, 1000)
                spin.setValue(0)
                spin.setStyleSheet(input_style)
                spin.setMinimumHeight(24)
                spin.setMaximumWidth(50)
                row1_layout.addWidget(spin)
                block.block_data[f"via_{axis.lower()}"] = spin
            
            block.content_layout.addWidget(row1)
            
            row2 = QWidget()
            row2_layout = QHBoxLayout(row2)
            row2_layout.setContentsMargins(0, 0, 0, 0)
            row2_layout.setSpacing(3)
            
            label2 = QLabel("目标:")
            label2.setStyleSheet("color: white; font-size: 10px;")
            row2_layout.addWidget(label2)
            
            for axis in ["X", "Y", "Z"]:
                spin = QDoubleSpinBox()
                spin.setRange(-1000, 1000)
                spin.setValue(0)
                spin.setStyleSheet(input_style)
                spin.setMinimumHeight(24)
                spin.setMaximumWidth(50)
                row2_layout.addWidget(spin)
                block.block_data[f"to_{axis.lower()}"] = spin
            
            block.content_layout.addWidget(row2)
        
        elif block_type == "speed":
            # 设置速度
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(5)
            
            label = QLabel("速度:")
            label.setStyleSheet("color: white; font-size: 10px;")
            row_layout.addWidget(label)
            
            spin = QDoubleSpinBox()
            spin.setRange(1, 100)
            spin.setValue(50)
            spin.setSuffix("%")
            spin.setStyleSheet(input_style)
            spin.setMinimumHeight(24)
            row_layout.addWidget(spin, 1)
            
            block.content_layout.addWidget(row)
            block.block_data["speed"] = spin
        
        elif block_type == "acceleration":
            # 设置加速度
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(5)
            
            label = QLabel("加速度:")
            label.setStyleSheet("color: white; font-size: 10px;")
            row_layout.addWidget(label)
            
            spin = QDoubleSpinBox()
            spin.setRange(100, 2000)
            spin.setValue(500)
            spin.setStyleSheet(input_style)
            spin.setMinimumHeight(24)
            row_layout.addWidget(spin, 1)
            
            block.content_layout.addWidget(row)
            block.block_data["acceleration"] = spin
        
        elif block_type == "digital_out":
            # 数字输出
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(5)
            
            label1 = QLabel("IO:")
            label1.setStyleSheet("color: white; font-size: 10px;")
            row_layout.addWidget(label1)
            
            io_spin = QSpinBox()
            io_spin.setRange(0, 15)
            io_spin.setValue(0)
            io_spin.setStyleSheet(input_style)
            io_spin.setMinimumHeight(24)
            row_layout.addWidget(io_spin)
            block.block_data["io"] = io_spin
            
            label2 = QLabel("值:")
            label2.setStyleSheet("color: white; font-size: 10px;")
            row_layout.addWidget(label2)
            
            value_combo = QComboBox()
            value_combo.addItems(["HIGH", "LOW"])
            value_combo.setStyleSheet(combo_style)
            value_combo.setMinimumHeight(24)
            row_layout.addWidget(value_combo)
            block.block_data["value"] = value_combo
            
            block.content_layout.addWidget(row)
        
        elif block_type == "digital_in":
            # 数字输入
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(5)
            
            label = QLabel("IO:")
            label.setStyleSheet("color: white; font-size: 10px;")
            row_layout.addWidget(label)
            
            io_spin = QSpinBox()
            io_spin.setRange(0, 15)
            io_spin.setValue(0)
            io_spin.setStyleSheet(input_style)
            io_spin.setMinimumHeight(24)
            row_layout.addWidget(io_spin, 1)
            block.block_data["io"] = io_spin
            
            block.content_layout.addWidget(row)
        
        elif block_type == "analog_out":
            # 模拟输出
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(5)
            
            label1 = QLabel("IO:")
            label1.setStyleSheet("color: white; font-size: 10px;")
            row_layout.addWidget(label1)
            
            io_spin = QSpinBox()
            io_spin.setRange(0, 15)
            io_spin.setValue(0)
            io_spin.setStyleSheet(input_style)
            io_spin.setMinimumHeight(24)
            row_layout.addWidget(io_spin)
            block.block_data["io"] = io_spin
            
            label2 = QLabel("值:")
            label2.setStyleSheet("color: white; font-size: 10px;")
            row_layout.addWidget(label2)
            
            value_spin = QDoubleSpinBox()
            value_spin.setRange(0, 10)
            value_spin.setValue(0)
            value_spin.setDecimals(2)
            value_spin.setStyleSheet(input_style)
            value_spin.setMinimumHeight(24)
            row_layout.addWidget(value_spin)
            block.block_data["value"] = value_spin
            
            block.content_layout.addWidget(row)
        
        elif block_type == "analog_in":
            # 模拟输入
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(5)
            
            label = QLabel("IO:")
            label.setStyleSheet("color: white; font-size: 10px;")
            row_layout.addWidget(label)
            
            io_spin = QSpinBox()
            io_spin.setRange(0, 15)
            io_spin.setValue(0)
            io_spin.setStyleSheet(input_style)
            io_spin.setMinimumHeight(24)
            row_layout.addWidget(io_spin, 1)
            block.block_data["io"] = io_spin
            
            block.content_layout.addWidget(row)
        
        elif block_type == "gripper":
            # 夹爪控制
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(5)
            
            label = QLabel("动作:")
            label.setStyleSheet("color: white; font-size: 10px;")
            row_layout.addWidget(label)
            
            action_combo = QComboBox()
            action_combo.addItems(["打开", "关闭", "设置位置"])
            action_combo.setStyleSheet(combo_style)
            action_combo.setMinimumHeight(24)
            row_layout.addWidget(action_combo, 1)
            block.block_data["action"] = action_combo
            
            block.content_layout.addWidget(row)
            
            # 位置输入（仅在"设置位置"时显示）
            row2 = QWidget()
            row2_layout = QHBoxLayout(row2)
            row2_layout.setContentsMargins(0, 0, 0, 0)
            row2_layout.setSpacing(5)
            
            label2 = QLabel("位置:")
            label2.setStyleSheet("color: white; font-size: 10px;")
            row2_layout.addWidget(label2)
            
            pos_spin = QDoubleSpinBox()
            pos_spin.setRange(0, 100)
            pos_spin.setValue(50)
            pos_spin.setSuffix("%")
            pos_spin.setStyleSheet(input_style)
            pos_spin.setMinimumHeight(24)
            row2_layout.addWidget(pos_spin, 1)
            block.block_data["position"] = pos_spin
            
            block.content_layout.addWidget(row2)
            row2.setVisible(False)
            
            action_combo.currentTextChanged.connect(lambda text: row2.setVisible(text == "设置位置"))
        
        elif block_type == "suction":
            # 吸盘控制
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(5)
            
            label = QLabel("动作:")
            label.setStyleSheet("color: white; font-size: 10px;")
            row_layout.addWidget(label)
            
            action_combo = QComboBox()
            action_combo.addItems(["开启", "关闭"])
            action_combo.setStyleSheet(combo_style)
            action_combo.setMinimumHeight(24)
            row_layout.addWidget(action_combo, 1)
            block.block_data["action"] = action_combo
            
            block.content_layout.addWidget(row)
        
        elif block_type == "while_loop":
            # 条件循环
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(5)
            
            label = QLabel("条件:")
            label.setStyleSheet("color: white; font-size: 10px;")
            row_layout.addWidget(label)
            
            condition_entry = QLineEdit()
            condition_entry.setText("True")
            condition_entry.setStyleSheet(input_style)
            condition_entry.setMinimumHeight(24)
            row_layout.addWidget(condition_entry, 1)
            block.block_data["condition"] = condition_entry
            
            block.content_layout.addWidget(row)
        
        elif block_type == "break":
            # 跳出循环（无参数）
            pass
        
        elif block_type == "if_condition":
            # 条件判断
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(5)
            
            label = QLabel("条件:")
            label.setStyleSheet("color: white; font-size: 10px;")
            row_layout.addWidget(label)
            
            condition_entry = QLineEdit()
            condition_entry.setText("True")
            condition_entry.setStyleSheet(input_style)
            condition_entry.setMinimumHeight(24)
            row_layout.addWidget(condition_entry, 1)
            block.block_data["condition"] = condition_entry
            
            block.content_layout.addWidget(row)
        
        elif block_type == "compare":
            # 比较
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(3)
            
            val1_entry = QLineEdit()
            val1_entry.setText("0")
            val1_entry.setStyleSheet(input_style)
            val1_entry.setMinimumHeight(24)
            val1_entry.setMaximumWidth(50)
            row_layout.addWidget(val1_entry)
            block.block_data["value1"] = val1_entry
            
            op_combo = QComboBox()
            op_combo.addItems(["==", "!=", ">", "<", ">=", "<="])
            op_combo.setStyleSheet(combo_style)
            op_combo.setMinimumHeight(24)
            op_combo.setMaximumWidth(50)
            row_layout.addWidget(op_combo)
            block.block_data["operator"] = op_combo
            
            val2_entry = QLineEdit()
            val2_entry.setText("0")
            val2_entry.setStyleSheet(input_style)
            val2_entry.setMinimumHeight(24)
            val2_entry.setMaximumWidth(50)
            row_layout.addWidget(val2_entry)
            block.block_data["value2"] = val2_entry
            
            block.content_layout.addWidget(row)
        
        elif block_type == "variable":
            # 设置变量
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(5)
            
            name_entry = QLineEdit()
            name_entry.setText("var1")
            name_entry.setStyleSheet(input_style)
            name_entry.setMinimumHeight(24)
            name_entry.setMaximumWidth(60)
            row_layout.addWidget(name_entry)
            block.block_data["name"] = name_entry
            
            label = QLabel("=")
            label.setStyleSheet("color: white; font-size: 10px;")
            row_layout.addWidget(label)
            
            value_entry = QLineEdit()
            value_entry.setText("0")
            value_entry.setStyleSheet(input_style)
            value_entry.setMinimumHeight(24)
            row_layout.addWidget(value_entry, 1)
            block.block_data["value"] = value_entry
            
            block.content_layout.addWidget(row)
        
        elif block_type == "math_op":
            # 数学运算
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(3)
            
            val1_entry = QLineEdit()
            val1_entry.setText("0")
            val1_entry.setStyleSheet(input_style)
            val1_entry.setMinimumHeight(24)
            val1_entry.setMaximumWidth(50)
            row_layout.addWidget(val1_entry)
            block.block_data["value1"] = val1_entry
            
            op_combo = QComboBox()
            op_combo.addItems(["+", "-", "*", "/", "%"])
            op_combo.setStyleSheet(combo_style)
            op_combo.setMinimumHeight(24)
            op_combo.setMaximumWidth(45)
            row_layout.addWidget(op_combo)
            block.block_data["operator"] = op_combo
            
            val2_entry = QLineEdit()
            val2_entry.setText("0")
            val2_entry.setStyleSheet(input_style)
            val2_entry.setMinimumHeight(24)
            val2_entry.setMaximumWidth(50)
            row_layout.addWidget(val2_entry)
            block.block_data["value2"] = val2_entry
            
            block.content_layout.addWidget(row)
        
        elif block_type == "random":
            # 随机数
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(5)
            
            label1 = QLabel("从:")
            label1.setStyleSheet("color: white; font-size: 10px;")
            row_layout.addWidget(label1)
            
            min_spin = QSpinBox()
            min_spin.setRange(-1000, 1000)
            min_spin.setValue(0)
            min_spin.setStyleSheet(input_style)
            min_spin.setMinimumHeight(24)
            row_layout.addWidget(min_spin)
            block.block_data["min"] = min_spin
            
            label2 = QLabel("到:")
            label2.setStyleSheet("color: white; font-size: 10px;")
            row_layout.addWidget(label2)
            
            max_spin = QSpinBox()
            max_spin.setRange(-1000, 1000)
            max_spin.setValue(100)
            max_spin.setStyleSheet(input_style)
            max_spin.setMinimumHeight(24)
            row_layout.addWidget(max_spin)
            block.block_data["max"] = max_spin
            
            block.content_layout.addWidget(row)
        
        elif block_type == "delay":
            # 延时
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(5)
            
            label = QLabel("时间:")
            label.setStyleSheet("color: white; font-size: 10px;")
            row_layout.addWidget(label)
            
            spin = QDoubleSpinBox()
            spin.setRange(0.1, 60)
            spin.setValue(1.0)
            spin.setSuffix(" 秒")
            spin.setDecimals(1)
            spin.setStyleSheet(input_style)
            spin.setMinimumHeight(24)
            row_layout.addWidget(spin, 1)
            
            block.content_layout.addWidget(row)
            block.block_data["time"] = spin
        
        elif block_type == "wait_condition":
            # 等待条件
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(5)
            
            label = QLabel("条件:")
            label.setStyleSheet("color: white; font-size: 10px;")
            row_layout.addWidget(label)
            
            condition_entry = QLineEdit()
            condition_entry.setText("True")
            condition_entry.setStyleSheet(input_style)
            condition_entry.setMinimumHeight(24)
            row_layout.addWidget(condition_entry, 1)
            block.block_data["condition"] = condition_entry
            
            block.content_layout.addWidget(row)
        
        elif block_type == "pick_place":
            # 抓取放置（无参数）
            label = QLabel("抓取点 → 放置点")
            label.setStyleSheet("color: white; font-size: 10px;")
            block.content_layout.addWidget(label)
        
        elif block_type == "palletizing":
            # 码垛
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(5)
            
            label1 = QLabel("行:")
            label1.setStyleSheet("color: white; font-size: 10px;")
            row_layout.addWidget(label1)
            
            rows_spin = QSpinBox()
            rows_spin.setRange(1, 10)
            rows_spin.setValue(3)
            rows_spin.setStyleSheet(input_style)
            rows_spin.setMinimumHeight(24)
            row_layout.addWidget(rows_spin)
            block.block_data["rows"] = rows_spin
            
            label2 = QLabel("列:")
            label2.setStyleSheet("color: white; font-size: 10px;")
            row_layout.addWidget(label2)
            
            cols_spin = QSpinBox()
            cols_spin.setRange(1, 10)
            cols_spin.setValue(3)
            cols_spin.setStyleSheet(input_style)
            cols_spin.setMinimumHeight(24)
            row_layout.addWidget(cols_spin)
            block.block_data["cols"] = cols_spin
            
            block.content_layout.addWidget(row)
        
        elif block_type == "comment":
            # 注释
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(5)
            
            comment_entry = QLineEdit()
            comment_entry.setText("# 注释内容")
            comment_entry.setStyleSheet(input_style)
            comment_entry.setMinimumHeight(24)
            row_layout.addWidget(comment_entry, 1)
            block.block_data["text"] = comment_entry
            
            block.content_layout.addWidget(row)
        
        elif block_type == "print":
            # 打印
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(5)
            
            label = QLabel("内容:")
            label.setStyleSheet("color: white; font-size: 10px;")
            row_layout.addWidget(label)
            
            text_entry = QLineEdit()
            text_entry.setText("Hello")
            text_entry.setStyleSheet(input_style)
            text_entry.setMinimumHeight(24)
            row_layout.addWidget(text_entry, 1)
            block.block_data["text"] = text_entry
            
            block.content_layout.addWidget(row)
        
        return block

    def _create_canvas(self):
        """创建编程画布"""
        canvas = QFrame()
        canvas.setObjectName("card")
        canvas_layout = QVBoxLayout(canvas)
        canvas_layout.setContentsMargins(20, 20, 20, 20)
        canvas_layout.setSpacing(15)
        
        # 画布标题
        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        
        title = QLabel("编程区域")
        title.setStyleSheet("color: #64748b; font-size: 13px; font-weight: 500;")
        header_layout.addWidget(title)
        
        header_layout.addStretch()
        
        clear_btn = QPushButton("清空")
        clear_btn.setObjectName("secondary_button")
        clear_btn.setFixedSize(70, 30)
        clear_btn.clicked.connect(self._clear_canvas)
        header_layout.addWidget(clear_btn)
        
        canvas_layout.addWidget(header)
        
        # 可滚动画布区域
        self.canvas_scroll = QScrollArea()
        self.canvas_scroll.setWidgetResizable(True)
        self.canvas_scroll.setFrameShape(QFrame.NoFrame)
        self.canvas_scroll.setStyleSheet("""
            QScrollArea {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #f8fafc, stop:1 #f1f5f9);
                border: 2px dashed #cbd5e1;
                border-radius: 8px;
            }
        """)
        
        # 创建可接受拖放的画布内容区域
        self.canvas_content = DropTargetWidget(self)
        self.canvas_layout = QVBoxLayout(self.canvas_content)
        self.canvas_layout.setContentsMargins(15, 15, 15, 15)
        self.canvas_layout.setSpacing(10)
        self.canvas_layout.addStretch()
        
        self.canvas_scroll.setWidget(self.canvas_content)
        canvas_layout.addWidget(self.canvas_scroll, 1)
        
        return canvas
    
    def _create_right_panel(self):
        """创建右侧面板"""
        panel = QFrame()
        panel.setObjectName("card")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(15, 15, 15, 15)
        panel_layout.setSpacing(10)
        
        # 代码预览
        code_title = QLabel("代码预览")
        code_title.setStyleSheet("color: #1e293b; font-size: 13px; font-weight: bold;")
        panel_layout.addWidget(code_title)
        
        self.code_preview = QTextEdit()
        self.code_preview.setReadOnly(True)
        self.code_preview.setPlaceholderText("生成的代码将显示在这里...")
        self.code_preview.setStyleSheet("""
            QTextEdit {
                background: #f8fafc;
                border: 1px solid #e2e8f0;
                border-radius: 6px;
                padding: 8px;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 11px;
                color: #1e293b;
            }
        """)
        panel_layout.addWidget(self.code_preview, 1)
        
        # 执行日志
        log_title = QLabel("执行日志")
        log_title.setStyleSheet("color: #1e293b; font-size: 13px; font-weight: bold;")
        panel_layout.addWidget(log_title)
        
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setPlaceholderText("执行日志将显示在这里...")
        self.log_area.setStyleSheet("""
            QTextEdit {
                background: #0f172a;
                border: 1px solid #1e293b;
                border-radius: 6px;
                padding: 8px;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 11px;
                color: #10b981;
            }
        """)
        panel_layout.addWidget(self.log_area, 1)
        
        return panel
    
    def _clear_canvas(self):
        """清空画布"""
        from PySide6.QtWidgets import QMessageBox
        
        if not self.blocks:
            self._log("画布已经是空的")
            return
        
        # 确认对话框
        reply = QMessageBox.question(
            self,
            "确认清空",
            f"确定要清空画布吗？\n当前有 {len(self.blocks)} 个积木块将被删除。",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            for block in self.blocks:
                block.deleteLater()
            self.blocks.clear()
            self._update_code_preview()
            self._log("画布已清空")
    
    def _new_project(self):
        """新建项目"""
        from PySide6.QtWidgets import QMessageBox
        
        if self.blocks:
            # 确认对话框
            reply = QMessageBox.question(
                self,
                "确认新建",
                f"新建项目将清空当前画布。\n当前有 {len(self.blocks)} 个积木块，是否继续？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply == QMessageBox.No:
                return
        
        # 清空画布
        for block in self.blocks:
            block.deleteLater()
        self.blocks.clear()
        self._update_code_preview()
        self.log_area.clear()
        self._log("新建项目")
    
    def _update_code_preview(self):
        """更新代码预览"""
        if not self.blocks:
            self.code_preview.setPlainText("# 暂无积木块")
            return
        
        code_lines = ["# Blockly生成的代码", ""]
        
        for i, block in enumerate(self.blocks):
            instruction = block.get_instruction()
            block_type = instruction["type"]
            data = instruction.get("data", {})
            
            if block_type == "joint_move":
                angles = [data[f"j{i+1}"].value() for i in range(4)]
                code_lines.append(f"# 步骤 {i+1}: 关节运动")
                code_lines.append(f"joint_angles = {angles}")
                code_lines.append(f"robot.move_joint(joint_angles)")
                code_lines.append("")
            
            elif block_type == "chassis_move":
                direction = data["direction"].currentText()
                value = data["value"].value()
                code_lines.append(f"# 步骤 {i+1}: 底盘{direction}")
                code_lines.append(f"chassis.move('{direction}', {value})")
                code_lines.append("")
            
            elif block_type == "delay":
                time_val = data["time"].value()
                code_lines.append(f"# 步骤 {i+1}: 延时")
                code_lines.append(f"time.sleep({time_val})")
                code_lines.append("")
        
        self.code_preview.setPlainText("\n".join(code_lines))
    
    def _toggle_loop(self):
        """切换循环模式"""
        self.is_looping = self.loop_btn.isChecked()
        if self.is_looping:
            self._log("循环模式已启用")
        else:
            self._log("循环模式已关闭")
    
    def _run_program(self):
        """运行程序"""
        if not self.blocks:
            self._log("错误: 没有积木块可执行", error=True)
            return
        
        if not self.main_gui.serial_comm.is_connected:
            self._log("错误: 串口未连接", error=True)
            return
        
        self._log("=" * 40)
        if self.is_looping:
            self._log("开始循环执行程序...")
        else:
            self._log("开始执行程序...")
        self.run_btn.setEnabled(False)
        self.pause_btn.setEnabled(True)
        self.stop_btn.setEnabled(True)
        self.loop_btn.setEnabled(False)
        self.is_paused = False
        
        # 预处理：找到所有循环的起止位置
        self.loop_info = {}
        for i, block in enumerate(self.blocks):
            if block.block_type == "while_loop":
                # 找到对应的break或程序末尾
                end_index = len(self.blocks)  # 默认到程序末尾
                for j in range(i + 1, len(self.blocks)):
                    if self.blocks[j].block_type == "break":
                        end_index = j
                        break
                
                loop_count = block.block_data.get("count")
                if loop_count:
                    count_value = loop_count.value()
                    self.loop_info[i] = {
                        'count': count_value,
                        'current': 0,
                        'end': end_index
                    }
        
        # 在后台线程执行
        self.execution_index = 0
        self.execution_timer = QTimer()
        self.execution_timer.timeout.connect(self._execute_next_block)
        self.execution_timer.start(100)
    
    def _toggle_pause(self):
        """切换暂停/继续"""
        if self.is_paused:
            # 继续执行
            self.is_paused = False
            self.pause_btn.setText("⏸ 暂停")
            if self.execution_timer:
                self.execution_timer.start()
            self._log("继续执行...")
        else:
            # 暂停执行
            self.is_paused = True
            self.pause_btn.setText("▶ 继续")
            if self.execution_timer:
                self.execution_timer.stop()
            self._log("程序已暂停")
    
    def _stop_program(self):
        """停止程序"""
        if self.execution_timer:
            self.execution_timer.stop()
            self.execution_timer = None
        
        self.is_paused = False
        self.execution_index = 0
        self.run_btn.setEnabled(True)
        self.pause_btn.setEnabled(False)
        self.pause_btn.setText("⏸ 暂停")
        self.stop_btn.setEnabled(False)
        self.loop_btn.setEnabled(True)
        self._log("程序已停止")
        self._log("=" * 40)
    
    def _execute_next_block(self):
        """执行下一个积木块"""
        # 如果正在等待到达，检查是否已到达
        if self.waiting_for_arrival:
            if self._check_arrival():
                self._log("已到达目标位置")
                self.waiting_for_arrival = False
                self.target_angles = None
                self.target_chassis_angles = None
                self.arrival_check_count = 0
                self.execution_index += 1
            else:
                self.arrival_check_count += 1
                if self.arrival_check_count >= self.max_arrival_checks:
                    self._log(f"等待超时({self.max_arrival_checks * 0.1:.0f}秒)，继续执行下一步", error=True)
                    self.waiting_for_arrival = False
                    self.target_angles = None
                    self.target_chassis_angles = None
                    self.arrival_check_count = 0
                    self.execution_index += 1
                return  # 继续等待
        
        if self.execution_index >= len(self.blocks):
            # 检查是否循环执行
            if self.is_looping:
                self.execution_index = 0
                self._log("--- 循环重新开始 ---")
                return
            
            # 非循环模式，执行完成
            self.execution_timer.stop()
            self._log("程序执行完成!")
            self._log("=" * 40)
            self.run_btn.setEnabled(True)
            self.pause_btn.setEnabled(False)
            self.pause_btn.setText("⏸ 暂停")
            self.stop_btn.setEnabled(False)
            self.loop_btn.setEnabled(True)
            return
        
        block = self.blocks[self.execution_index]
        instruction = block.get_instruction()
        block_type = instruction["type"]
        data = instruction.get("data", {})
        
        try:
            if block_type == "joint_move":
                angles = [data[f"j{i+1}"].value() for i in range(4)]
                wait_arrival = data.get("wait_arrival", None)
                wait = wait_arrival.isChecked() if wait_arrival else False
                
                self._log(f"步骤 {self.execution_index + 1}: 关节运动 {angles} {'(等待到达)' if wait else ''}")
                
                # 发送关节角度
                all_angles = angles + list(self.main_gui.chassis_wheel_angles)
                self.main_gui.serial_comm.send_angles(
                    all_angles,
                    num_arm_joints=self.main_gui.NUM_ARM_JOINTS,
                    wait_for_completion=False
                )
                
                # 如果需要等待到达
                if wait:
                    self.waiting_for_arrival = True
                    self.target_angles = angles
                    self.arrival_check_count = 0
                    return  # 不立即执行下一步
            
            elif block_type == "chassis_move":
                direction = data["direction"].currentText()
                value = data["value"].value()
                wait_arrival = data.get("wait_arrival", None)
                wait = wait_arrival.isChecked() if wait_arrival else False
                
                self._log(f"步骤 {self.execution_index + 1}: 底盘{direction} {value} {'(等待到达)' if wait else ''}")
                
                # 计算底盘目标角度
                current_angles = self.main_gui.chassis_wheel_angles.copy()
                angle_change = value / 10.0  # 简化计算
                
                if direction == "前进":
                    current_angles[0] -= angle_change * 0.866
                    current_angles[2] += angle_change * 0.866
                elif direction == "后退":
                    current_angles[0] += angle_change * 0.866
                    current_angles[2] -= angle_change * 0.866
                elif direction == "左移":
                    current_angles[0] -= angle_change * 0.5
                    current_angles[1] += angle_change
                    current_angles[2] -= angle_change * 0.5
                elif direction == "右移":
                    current_angles[0] += angle_change * 0.5
                    current_angles[1] -= angle_change
                    current_angles[2] += angle_change * 0.5
                elif direction == "左转":
                    current_angles[0] -= angle_change
                    current_angles[1] -= angle_change
                    current_angles[2] -= angle_change
                elif direction == "右转":
                    current_angles[0] += angle_change
                    current_angles[1] += angle_change
                    current_angles[2] += angle_change
                
                all_angles = list(self.main_gui.joint_angles) + current_angles
                self.main_gui.serial_comm.send_angles(
                    all_angles,
                    num_arm_joints=self.main_gui.NUM_ARM_JOINTS,
                    wait_for_completion=False
                )
                
                # 如果需要等待到达
                if wait:
                    self.waiting_for_arrival = True
                    self.target_chassis_angles = current_angles
                    self.arrival_check_count = 0
                    return  # 不立即执行下一步
            
            elif block_type == "delay":
                time_val = data["time"].value()
                self._log(f"步骤 {self.execution_index + 1}: 延时 {time_val}秒")
                # 延时通过定时器实现
                self.execution_timer.setInterval(int(time_val * 1000))
            
            elif block_type == "movel":
                # 直线运动 - 使用逆运动学（只使用前3个关节）
                x = data["x"].value()
                y = data["y"].value()
                z = data["z"].value()
                self._log(f"步骤 {self.execution_index + 1}: 直线运动到 X={x}, Y={y}, Z={z}")
                
                try:
                    # 使用逆运动学计算关节角度（只使用前3个关节）
                    target_pos = [x / 1000.0, y / 1000.0, z / 1000.0]  # 转换为米
                    ik_angles_rad = self.main_gui.kinematics.arm_chain.inverse_kinematics(
                        target_position=target_pos
                    )
                    # 只取前3个关节，第4个关节固定为0
                    angles_deg = [angle * 180.0 / 3.14159265359 for angle in ik_angles_rad[1:4]]  # 只取J0,J1,J2
                    angles_deg.append(0.0)  # J3固定为0
                    
                    # 发送关节角度
                    all_angles = angles_deg + list(self.main_gui.chassis_wheel_angles)
                    self.main_gui.serial_comm.send_angles(
                        all_angles,
                        num_arm_joints=self.main_gui.NUM_ARM_JOINTS,
                        wait_for_completion=False
                    )
                    self._log(f"  → 关节角度: J0={angles_deg[0]:.1f}°, J1={angles_deg[1]:.1f}°, J2={angles_deg[2]:.1f}°, J3=0.0°")
                except Exception as e:
                    self._log(f"  ✗ 逆运动学计算失败: {str(e)}", error=True)
            
            elif block_type == "movec":
                # 圆弧运动 - 简化实现：通过中间点和目标点（只使用前3个关节）
                via_x = data["via_x"].value()
                via_y = data["via_y"].value()
                via_z = data["via_z"].value()
                to_x = data["to_x"].value()
                to_y = data["to_y"].value()
                to_z = data["to_z"].value()
                self._log(f"步骤 {self.execution_index + 1}: 圆弧运动 中间点({via_x},{via_y},{via_z}) → 目标点({to_x},{to_y},{to_z})")
                
                try:
                    # 先移动到中间点（只使用前3个关节）
                    via_pos = [via_x / 1000.0, via_y / 1000.0, via_z / 1000.0]
                    ik_angles_rad = self.main_gui.kinematics.arm_chain.inverse_kinematics(
                        target_position=via_pos
                    )
                    # 只取前3个关节，第4个关节固定为0
                    angles_deg = [angle * 180.0 / 3.14159265359 for angle in ik_angles_rad[1:4]]
                    angles_deg.append(0.0)  # J3固定为0
                    
                    all_angles = angles_deg + list(self.main_gui.chassis_wheel_angles)
                    self.main_gui.serial_comm.send_angles(
                        all_angles,
                        num_arm_joints=self.main_gui.NUM_ARM_JOINTS,
                        wait_for_completion=False
                    )
                    self._log(f"  → 中间点: J0={angles_deg[0]:.1f}°, J1={angles_deg[1]:.1f}°, J2={angles_deg[2]:.1f}°, J3=0.0°")
                    
                    # 移动到目标点
                    to_pos = [to_x / 1000.0, to_y / 1000.0, to_z / 1000.0]
                    ik_angles_rad = self.main_gui.kinematics.arm_chain.inverse_kinematics(
                        target_position=to_pos
                    )
                    angles_deg = [angle * 180.0 / 3.14159265359 for angle in ik_angles_rad[1:4]]
                    angles_deg.append(0.0)  # J3固定为0
                    
                    all_angles = angles_deg + list(self.main_gui.chassis_wheel_angles)
                    self.main_gui.serial_comm.send_angles(
                        all_angles,
                        num_arm_joints=self.main_gui.NUM_ARM_JOINTS,
                        wait_for_completion=False
                    )
                    self._log(f"  → 目标点: J0={angles_deg[0]:.1f}°, J1={angles_deg[1]:.1f}°, J2={angles_deg[2]:.1f}°, J3=0.0°")
                    
                    # 注意：完整的圆弧插补需要更复杂的算法，这里简化为两点直线
                except Exception as e:
                    self._log(f"  ✗ 圆弧运动失败: {str(e)}", error=True)
            
            elif block_type == "speed":
                speed_val = data["speed"].value()
                self._log(f"步骤 {self.execution_index + 1}: 设置速度 {speed_val}%")
                self.main_gui.speed_percent = speed_val
            
            elif block_type == "while_loop":
                # 循环开始
                if self.execution_index in self.loop_info:
                    info = self.loop_info[self.execution_index]
                    # 只在第一次进入或重新开始时重置
                    if info['current'] == 0:
                        self._log(f"步骤 {self.execution_index + 1}: 开始循环 (共{info['count']}次)")
                    else:
                        self._log(f"  → 循环第 {info['current'] + 1}/{info['count']} 次")
            
            elif block_type == "break":
                # 循环结束标记
                # 查找对应的循环起点
                loop_start = None
                for start_idx, info in self.loop_info.items():
                    if info['end'] == self.execution_index:
                        loop_start = start_idx
                        break
                
                if loop_start is not None:
                    info = self.loop_info[loop_start]
                    info['current'] += 1
                    
                    self._log(f"步骤 {self.execution_index + 1}: 完成第 {info['current']}/{info['count']} 次循环")
                    
                    if info['current'] < info['count']:
                        # 还需要继续循环，跳回循环起点
                        self.execution_index = loop_start - 1  # -1是因为后面会+1
                        self._log(f"  → 继续循环...")
                    else:
                        # 循环完成，重置计数器以便下次使用
                        self._log(f"  → 循环全部完成！")
                        info['current'] = 0
                else:
                    self._log(f"步骤 {self.execution_index + 1}: 跳出循环")
        
        except Exception as e:
            self._log(f"错误: {str(e)}", error=True)
        
        self.execution_index += 1
        # 恢复正常间隔
        if block_type != "delay":
            self.execution_timer.setInterval(100)
    
    def _log(self, message, error=False):
        """添加日志"""
        import datetime
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        
        if error:
            log_text = f'<span style="color: #ef4444;">[{timestamp}] {message}</span>'
        else:
            log_text = f'<span style="color: #10b981;">[{timestamp}] {message}</span>'
        
        self.log_area.append(log_text)
    
    def _check_arrival(self):
        """检查是否到达目标位置"""
        tolerance = 1.0  # 角度偏差容忍度：±1度
        
        # 检查关节角度
        if self.target_angles is not None:
            current_angles = self.main_gui.joint_angles
            for i in range(len(self.target_angles)):
                if abs(current_angles[i] - self.target_angles[i]) > tolerance:
                    return False
            return True
        
        # 检查底盘角度
        if self.target_chassis_angles is not None:
            current_chassis = self.main_gui.chassis_wheel_angles
            for i in range(len(self.target_chassis_angles)):
                if abs(current_chassis[i] - self.target_chassis_angles[i]) > tolerance:
                    return False
            return True
        
        return True
    
    def _save_project(self):
        """保存项目"""
        from PySide6.QtWidgets import QFileDialog, QInputDialog, QMessageBox
        
        if not self.blocks:
            QMessageBox.warning(self, "提示", "没有积木块可保存")
            return
        
        # 询问项目名称
        project_name, ok = QInputDialog.getText(
            self,
            "保存项目",
            "请输入项目名称:",
            text="我的项目"
        )
        
        if not ok or not project_name:
            return
        
        # 收集所有积木块数据
        blocks_data = []
        for block in self.blocks:
            block_info = {
                "type": block.block_type,
                "data": {}
            }
            
            # 提取数据值
            for key, widget in block.block_data.items():
                if hasattr(widget, 'value'):
                    block_info["data"][key] = widget.value()
                elif hasattr(widget, 'text'):
                    block_info["data"][key] = widget.text()
                elif hasattr(widget, 'currentText'):
                    block_info["data"][key] = widget.currentText()
                elif hasattr(widget, 'isChecked'):
                    block_info["data"][key] = widget.isChecked()
            
            blocks_data.append(block_info)
        
        # 创建项目数据
        project_data = {
            "name": project_name,
            "blocks": blocks_data,
            "created": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        # 选择保存位置
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "保存项目",
            f"{project_name}.json",
            "JSON文件 (*.json)"
        )
        
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(project_data, f, ensure_ascii=False, indent=2)
                self._log(f"✓ 项目已保存: {os.path.basename(file_path)}")
                QMessageBox.information(self, "成功", f"项目已保存到:\n{file_path}")
            except Exception as e:
                self._log(f"✗ 保存失败: {str(e)}", error=True)
                QMessageBox.critical(self, "错误", f"保存失败:\n{str(e)}")
    
    def _load_project(self):
        """加载项目"""
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        
        # 选择文件
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "加载项目",
            "",
            "JSON文件 (*.json);;所有文件 (*.*)"
        )
        
        if not file_path:
            return
        
        if not os.path.exists(file_path):
            QMessageBox.critical(self, "错误", f"文件不存在:\n{file_path}")
            return
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                project_data = json.load(f)
            
            # 清空当前画布
            self._clear_canvas()
            
            # 加载积木块
            blocks_data = project_data.get("blocks", [])
            
            if not blocks_data:
                QMessageBox.warning(self, "提示", "项目中没有积木块")
                return
            
            # 积木块颜色映射
            color_map = {
                "joint_move": "#6b9fa3",
                "chassis_move": "#6b9fa3",
                "movel": "#6b9fa3",
                "movec": "#6b9fa3",
                "speed": "#4CAF50",
                "acceleration": "#4CAF50",
                "digital_out": "#FF9800",
                "digital_in": "#FF9800",
                "analog_out": "#FF9800",
                "analog_in": "#FF9800",
                "gripper": "#9C27B0",
                "suction": "#9C27B0",
                "while_loop": "#8e6bb0",
                "break": "#8e6bb0",
                "if_condition": "#607D8B",
                "compare": "#607D8B",
                "variable": "#1976D2",
                "math_op": "#1976D2",
                "random": "#1976D2",
                "delay": "#0097A7",
                "wait_condition": "#0097A7",
                "pick_place": "#388E3C",
                "palletizing": "#388E3C",
                "comment": "#795548",
                "print": "#795548",
            }
            
            # 积木块名称映射
            name_map = {
                "joint_move": "关节运动",
                "chassis_move": "底盘移动",
                "movel": "直线运动",
                "movec": "圆弧运动",
                "speed": "设置速度",
                "acceleration": "设置加速度",
                "digital_out": "数字输出",
                "digital_in": "数字输入",
                "analog_out": "模拟输出",
                "analog_in": "模拟输入",
                "gripper": "夹爪控制",
                "suction": "吸盘控制",
                "while_loop": "条件循环",
                "break": "跳出循环",
                "if_condition": "条件判断",
                "compare": "比较",
                "variable": "设置变量",
                "math_op": "数学运算",
                "random": "随机数",
                "delay": "延时",
                "wait_condition": "等待条件",
                "pick_place": "抓取放置",
                "palletizing": "码垛",
                "comment": "注释",
                "print": "打印",
            }
            
            loaded_count = 0
            for block_data in blocks_data:
                block_type = block_data.get("type")
                if not block_type:
                    continue
                
                block_name = name_map.get(block_type, block_type)
                color = color_map.get(block_type, "#607D8B")
                
                # 创建积木块
                block = self._create_block(block_type, block_name, color)
                if block:
                    # 恢复数据
                    saved_data = block_data.get("data", {})
                    for key, value in saved_data.items():
                        if key in block.block_data:
                            widget = block.block_data[key]
                            try:
                                if hasattr(widget, 'setValue'):
                                    widget.setValue(value)
                                elif hasattr(widget, 'setText'):
                                    widget.setText(str(value))
                                elif hasattr(widget, 'setCurrentText'):
                                    widget.setCurrentText(str(value))
                                elif hasattr(widget, 'setChecked'):
                                    widget.setChecked(bool(value))
                            except Exception as e:
                                print(f"恢复数据失败 {key}: {e}")
                    
                    self.canvas_layout.insertWidget(self.canvas_layout.count() - 1, block)
                    self.blocks.append(block)
                    loaded_count += 1
            
            self._update_code_preview()
            project_name = project_data.get('name', '未命名')
            self._log(f"✓ 项目已加载: {project_name} ({loaded_count}个积木块)")
            QMessageBox.information(self, "成功", f"项目已加载:\n{project_name}\n共{loaded_count}个积木块")
            
        except json.JSONDecodeError as e:
            self._log(f"✗ 加载失败: JSON格式错误", error=True)
            QMessageBox.critical(self, "加载失败", f"JSON格式错误:\n{str(e)}")
        except Exception as e:
            self._log(f"✗ 加载失败: {str(e)}", error=True)
            QMessageBox.critical(self, "加载失败", f"无法加载项目:\n{str(e)}")
