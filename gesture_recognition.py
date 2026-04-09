#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
手势识别模块
"""

import cv2
import numpy as np
import threading
import time
from PIL import Image

# 尝试导入 MediaPipe
try:
    import mediapipe as mp
    # 检查是否有solutions属性（旧版本）
    if hasattr(mp, 'solutions'):
        MEDIAPIPE_AVAILABLE = True
        MEDIAPIPE_VERSION = "legacy"
    else:
        # 新版本mediapipe使用不同的导入方式
        try:
            from mediapipe.tasks import python
            from mediapipe.tasks.python import vision
            MEDIAPIPE_AVAILABLE = True
            MEDIAPIPE_VERSION = "new"
        except ImportError:
            MEDIAPIPE_AVAILABLE = False
            MEDIAPIPE_VERSION = None
except ImportError:
    MEDIAPIPE_AVAILABLE = False
    MEDIAPIPE_VERSION = None
    print("警告: MediaPipe未安装，手势识别功能将不可用")


class GestureRecognition:
    """手势识别类"""
    
    def __init__(self):
        self.running = False
        self.cap = None
        self.thread = None
        self.stop_event = threading.Event()
        
        self.mp_hands = None
        self.hands_detector = None
        self.mp_draw = None
        
        self.mode = "字符识别"  # "字符识别" 或 "机械臂控制"
        self.callback = None

    @staticmethod
    def is_available():
        """检查MediaPipe是否可用"""
        return MEDIAPIPE_AVAILABLE
    
    def start(self, canvas, mode="字符识别", callback=None):
        """启动手势识别"""
        if not MEDIAPIPE_AVAILABLE:
            raise Exception("MediaPipe未安装")
        
        self.mode = mode
        self.callback = callback
        
        # 初始化摄像头 - 跨平台支持
        import platform
        system = platform.system()
        
        backends = []
        if system == 'Windows':
            backends = [cv2.CAP_DSHOW, cv2.CAP_MSMF, cv2.CAP_ANY]
        elif system == 'Linux':
            backends = [cv2.CAP_V4L2, cv2.CAP_V4L, cv2.CAP_ANY]
        elif system == 'Darwin':
            backends = [cv2.CAP_AVFOUNDATION, cv2.CAP_ANY]
        else:
            backends = [cv2.CAP_ANY]
        
        # 尝试打开摄像头
        camera_opened = False
        for camera_index in [0, 1, 2]:
            for backend in backends:
                try:
                    self.cap = cv2.VideoCapture(camera_index, backend)
                    if self.cap.isOpened():
                        ret, frame = self.cap.read()
                        if ret and frame is not None:
                            camera_opened = True
                            print(f"手势识别摄像头已打开: 索引={camera_index}, 后端={backend}")
                            break
                        else:
                            self.cap.release()
                except Exception:
                    pass
            if camera_opened:
                break
        
        if not camera_opened or not self.cap.isOpened():
            raise Exception("无法打开摄像头")
        
        # 设置摄像头参数
        try:
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
            self.cap.set(cv2.CAP_PROP_FPS, 30)
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        except Exception as e:
            print(f"设置摄像头参数警告: {e}")

        # 初始化MediaPipe
        if MEDIAPIPE_VERSION == "legacy":
            self.mp_hands = mp.solutions.hands
            self.hands_detector = self.mp_hands.Hands(
                static_image_mode=False,
                max_num_hands=1,
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5
            )
            self.mp_draw = mp.solutions.drawing_utils
        else:
            # 新版本暂不支持，使用降级模式
            raise Exception("MediaPipe版本不兼容，请安装旧版本: pip install mediapipe==0.10.14")
        
        self.running = True
        self.stop_event.clear()
        
        # 启动识别线程
        self.thread = threading.Thread(
            target=self._recognition_loop,
            args=(canvas,),
            daemon=True
        )
        self.thread.start()
        
        print("手势识别已启动")
    
    def stop(self, canvas):
        """停止手势识别"""
        self.running = False
        self.stop_event.set()
        
        if self.thread:
            self.thread.join(timeout=2)
        
        if self.cap:
            try:
                self.cap.release()
            except:
                pass
            self.cap = None
        
        if self.hands_detector:
            try:
                self.hands_detector.close()
            except:
                pass
            self.hands_detector = None
        
        # 清空画布 - PySide6版本
        try:
            canvas.clear()
        except:
            pass
        
        print("手势识别已停止")

    def _recognition_loop(self, canvas):
        """手势识别主循环"""
        while self.running and not self.stop_event.is_set():
            try:
                success, img = self.cap.read()
                if not success:
                    time.sleep(0.01)
                    continue
                
                img = cv2.flip(img, 1)
                image_height, image_width, _ = img.shape
                
                img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                results = self.hands_detector.process(img_rgb)
                
                if results.multi_hand_landmarks:
                    hand = results.multi_hand_landmarks[0]
                    
                    # 绘制手部关键点
                    self.mp_draw.draw_landmarks(
                        img, hand, self.mp_hands.HAND_CONNECTIONS,
                        self.mp_draw.DrawingSpec(color=(0, 255, 0), thickness=2, circle_radius=2),
                        self.mp_draw.DrawingSpec(color=(255, 0, 0), thickness=2)
                    )
                    
                    # 采集关键点
                    list_lms = []
                    for i in range(21):
                        pos_x = hand.landmark[i].x * image_width
                        pos_y = hand.landmark[i].y * image_height
                        list_lms.append([int(pos_x), int(pos_y)])
                    
                    list_lms = np.array(list_lms, dtype=np.int32)
                    
                    # 构造凸包
                    hull_index = [0, 1, 2, 3, 6, 10, 14, 19, 18, 17, 10]
                    hull = cv2.convexHull(list_lms[hull_index, :])
                    cv2.polylines(img, [hull], True, (0, 255, 0), 2)
                    
                    # 查找外部点
                    ll = [4, 8, 12, 16, 20]
                    up_fingers = []
                    for i in ll:
                        pt = (int(list_lms[i][0]), int(list_lms[i][1]))
                        dist = cv2.pointPolygonTest(hull, pt, True)
                        if dist < 0:
                            up_fingers.append(i)
                    
                    # 根据模式处理
                    if self.mode == "字符识别":
                        gesture_text = self._get_gesture_string(up_fingers, list_lms)
                        cv2.putText(img, gesture_text, (10, 40),
                                   cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 0), 3, cv2.LINE_AA)
                        
                        for i in ll:
                            pos_x = hand.landmark[i].x * image_width
                            pos_y = hand.landmark[i].y * image_height
                            cv2.circle(img, (int(pos_x), int(pos_y)), 5, (0, 255, 255), -1)
                    
                    elif self.mode == "机械臂控制" and self.callback:
                        self.callback(hand, image_width, image_height, img)
                
                # 显示图像 - 在主线程中更新
                self._update_canvas_image(canvas, img)
                
                time.sleep(0.03)
                
            except Exception as e:
                print(f"手势识别错误: {e}")
                import traceback
                traceback.print_exc()
                time.sleep(0.1)

    def _update_canvas_image(self, canvas, img):
        """在主线程中更新canvas图像 - PySide6版本"""
        try:
            from PySide6.QtGui import QPixmap, QImage
            from PySide6.QtCore import Qt
            
            # 转换图像
            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            height, width, channel = img_rgb.shape
            bytes_per_line = 3 * width
            
            # 创建QImage
            q_image = QImage(img_rgb.data, width, height, bytes_per_line, QImage.Format_RGB888)
            
            # 转换为QPixmap
            pixmap = QPixmap.fromImage(q_image)
            
            # 获取canvas尺寸并缩放
            try:
                canvas_width = canvas.width()
                canvas_height = canvas.height()
                if canvas_width > 1 and canvas_height > 1:
                    pixmap = pixmap.scaled(canvas_width, canvas_height, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            except:
                pass
            
            # 使用QTimer在主线程中更新
            def update_ui():
                try:
                    canvas.setPixmap(pixmap)
                except:
                    pass
            
            # 如果canvas有QTimer，使用它
            try:
                from PySide6.QtCore import QTimer
                QTimer.singleShot(0, update_ui)
            except:
                update_ui()
            
        except Exception as e:
            print(f"更新canvas图像错误: {e}")
    
    @staticmethod
    def _get_angle(v1, v2):
        """计算两个向量之间的角度"""
        angle = np.dot(v1, v2) / (np.sqrt(np.sum(v1*v1)) * np.sqrt(np.sum(v2*v2)))
        angle = np.arccos(angle) / 3.14 * 180
        return angle
    
    def _get_gesture_string(self, up_fingers, list_lms):
        """识别手势字符"""
        if len(up_fingers) == 1 and up_fingers[0] == 8:
            v1 = list_lms[6] - list_lms[7]
            v2 = list_lms[8] - list_lms[7]
            angle = self._get_angle(v1, v2)
            return "9" if angle < 160 else "1"
        
        elif len(up_fingers) == 1 and up_fingers[0] == 4:
            return "Good"
        elif len(up_fingers) == 1 and up_fingers[0] == 20:
            return "Bad"
        elif len(up_fingers) == 1 and up_fingers[0] == 12:
            return "FXXX"
        elif len(up_fingers) == 2 and up_fingers[0] == 8 and up_fingers[1] == 12:
            return "2"
        elif len(up_fingers) == 2 and up_fingers[0] == 4 and up_fingers[1] == 20:
            return "6"
        elif len(up_fingers) == 2 and up_fingers[0] == 4 and up_fingers[1] == 8:
            return "8"
        elif len(up_fingers) == 3 and up_fingers[0] == 8 and up_fingers[1] == 12 and up_fingers[2] == 16:
            return "3"
        elif len(up_fingers) == 3 and up_fingers[0] == 4 and up_fingers[1] == 8 and up_fingers[2] == 12:
            return "7"
        elif len(up_fingers) == 4 and up_fingers[0] == 8 and up_fingers[1] == 12 and up_fingers[2] == 16 and up_fingers[3] == 20:
            return "4"
        elif len(up_fingers) == 5:
            return "5"
        elif len(up_fingers) == 0:
            return "10"
        else:
            return " "
