#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
远程控制服务器
支持WebSocket连接、视频流、状态推送
"""

import asyncio
import json
import base64
import cv2
import numpy as np
from datetime import datetime
import threading
import queue

try:
    import websockets
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False
    print("警告: websockets未安装，远程控制功能不可用")
    print("安装: pip install websockets")


class RemoteControlServer:
    """远程控制服务器"""
    
    def __init__(self, robot_control_gui):
        self.gui = robot_control_gui
        self.server = None
        self.clients = set()
        self.running = False
        self.thread = None
        self._loop = None  # 存储事件循环引用
        
        # 视频流
        self.video_enabled = False
        self.video_cap = None
        self.video_quality = 50  # JPEG质量 1-100
        
        # 状态推送
        self.status_queue = queue.Queue()
        self.last_status = {}
        
        # 配置
        self.host = "0.0.0.0"  # 监听所有网络接口
        self.port = 8765
    
    @staticmethod
    def is_available():
        """检查websockets是否可用"""
        return WEBSOCKETS_AVAILABLE
    
    def start(self, host="0.0.0.0", port=8765):
        """启动服务器"""
        if not WEBSOCKETS_AVAILABLE:
            raise Exception("websockets未安装")
        
        self.host = host
        self.port = port
        self.running = True
        
        # 在新线程中启动异步服务器
        self.thread = threading.Thread(target=self._run_server, daemon=True)
        self.thread.start()
        
        print(f"远程控制服务器已启动: ws://{host}:{port}")
    
    def stop(self):
        """停止服务器"""
        self.running = False
        self.video_enabled = False
        
        if self.video_cap:
            self.video_cap.release()
            self.video_cap = None
        
        # 关闭所有客户端连接
        for client in self.clients.copy():
            try:
                asyncio.run(client.close())
            except:
                pass
        
        self.clients.clear()
        print("远程控制服务器已停止")
    
    def _run_server(self):
        """运行服务器（在独立线程中）"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop  # 保存事件循环引用
        
        try:
            loop.run_until_complete(self._start_websocket_server())
        except Exception as e:
            print(f"服务器错误: {e}")
        finally:
            self._loop = None
            loop.close()
    
    async def _start_websocket_server(self):
        """启动WebSocket服务器"""
        async with websockets.serve(self._handle_client, self.host, self.port):
            while self.running:
                await asyncio.sleep(0.1)
    
    async def _handle_client(self, websocket):
        """处理客户端连接"""
        client_addr = websocket.remote_address
        print(f"[远程控制] 客户端连接: {client_addr}")
        
        self.clients.add(websocket)
        
        try:
            # 发送欢迎消息
            print(f"[远程控制] 发送欢迎消息")
            await self._send_message(websocket, {
                "type": "welcome",
                "message": "XJNIII机械臂控制系统",
                "version": "1.0.0",
                "timestamp": datetime.now().isoformat()
            })
            
            # 发送当前状态
            print(f"[远程控制] 发送初始状态")
            await self._send_status(websocket)
            
            print(f"[远程控制] 开始接收消息")
            # 处理客户端消息
            async for message in websocket:
                print(f"[远程控制] 收到消息: {message[:100]}...")
                await self._process_message(websocket, message)
                
        except websockets.exceptions.ConnectionClosed as e:
            print(f"[远程控制] 客户端断开: {client_addr} - {e}")
        except Exception as e:
            print(f"[远程控制] 处理客户端错误: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.clients.discard(websocket)
            print(f"[远程控制] 客户端移除: {client_addr}")
    
    async def _process_message(self, websocket, message):
        """处理客户端消息"""
        try:
            data = json.loads(message)
            msg_type = data.get("type")
            
            if msg_type == "control":
                # 控制命令
                await self._handle_control(websocket, data)
            
            elif msg_type == "video_start":
                # 启动视频流
                await self._handle_video_start(websocket, data)
            
            elif msg_type == "video_stop":
                # 停止视频流
                self.video_enabled = False
                await self._send_message(websocket, {
                    "type": "video_stopped",
                    "timestamp": datetime.now().isoformat()
                })
            
            elif msg_type == "get_status":
                # 获取状态
                await self._send_status(websocket)
            
            elif msg_type == "voice_command":
                # 语音命令
                await self._handle_voice_command(websocket, data)
            
            else:
                await self._send_message(websocket, {
                    "type": "error",
                    "message": f"未知消息类型: {msg_type}"
                })
        
        except json.JSONDecodeError:
            await self._send_message(websocket, {
                "type": "error",
                "message": "无效的JSON格式"
            })
        except Exception as e:
            await self._send_message(websocket, {
                "type": "error",
                "message": str(e)
            })
    
    async def _handle_control(self, websocket, data):
        """处理控制命令"""
        command = data.get("command")
        params = data.get("params", {})
        
        try:
            if command == "move_joint":
                # 关节移动
                joint_id = params.get("joint_id")
                angle = params.get("angle")
                if joint_id is not None and angle is not None:
                    print(f"[远程控制] 收到关节移动命令: 关节{joint_id}, 角度{angle}°")
                    # 直接调用，不使用线程调度
                    self._move_joint(joint_id, angle)
                    await self._send_message(websocket, {
                        "type": "control_response",
                        "command": command,
                        "status": "success"
                    })
            
            elif command == "move_chassis":
                # 底盘移动
                direction = params.get("direction")
                distance = params.get("distance", 10.0)
                target_angles = params.get("target_angles")  # 新增：直接目标角度
                
                if direction == "stop" and target_angles:
                    # 停止命令：直接设置目标为当前位置
                    print(f"[远程控制] 收到底盘停止命令: 目标={target_angles}")
                    self.gui.chassis_wheel_angles = list(target_angles)
                    all_angles = list(self.gui.joint_angles) + list(target_angles)
                    self.gui.serial_comm.send_angles(all_angles, num_arm_joints=self.gui.NUM_ARM_JOINTS)
                elif direction:
                    print(f"[远程控制] 收到底盘移动命令: {direction}, 距离{distance}")
                    # 直接调用，不使用线程调度
                    self._move_chassis(direction, distance)
                
                await self._send_message(websocket, {
                    "type": "control_response",
                    "command": command,
                    "status": "success"
                })
            
            elif command == "emergency_stop":
                # 紧急停止
                print(f"[远程控制] 收到紧急停止命令")
                # 直接调用
                if hasattr(self.gui, '_emergency_stop'):
                    self.gui._emergency_stop()
                await self._send_message(websocket, {
                    "type": "control_response",
                    "command": command,
                    "status": "success"
                })
            
            elif command == "home":
                # 归零命令（机械臂+底盘）
                print(f"[远程控制] 收到归零命令")
                self._move_to_home()
                # 发送状态更新
                await self._send_status(websocket)
                await self._send_message(websocket, {
                    "type": "control_response",
                    "command": command,
                    "status": "success"
                })
            
            elif command == "chassis_home":
                # 底盘归零命令（仅底盘）
                print(f"[远程控制] 收到底盘归零命令")
                self.gui.chassis_wheel_angles = [0.0, 0.0, 0.0]
                all_angles = list(self.gui.joint_angles) + list(self.gui.chassis_wheel_angles)
                self.gui.serial_comm.send_angles(all_angles, num_arm_joints=self.gui.NUM_ARM_JOINTS)
                # 发送状态更新
                await self._send_status(websocket)
                await self._send_message(websocket, {
                    "type": "control_response",
                    "command": command,
                    "status": "success"
                })
            
            elif command == "set_speed":
                # 设置速度
                speed = params.get("speed")
                if speed is not None:
                    self.gui.speed_percent = speed
                    await self._send_message(websocket, {
                        "type": "control_response",
                        "command": command,
                        "status": "success"
                    })
            
            else:
                await self._send_message(websocket, {
                    "type": "control_response",
                    "command": command,
                    "status": "error",
                    "message": f"未知命令: {command}"
                })
        
        except Exception as e:
            await self._send_message(websocket, {
                "type": "control_response",
                "command": command,
                "status": "error",
                "message": str(e)
            })
    
    async def _handle_video_start(self, websocket, data):
        """启动视频流"""
        quality = data.get("quality", 50)
        self.video_quality = max(1, min(100, quality))
        
        # 打开摄像头
        if not self.video_cap:
            self.video_cap = cv2.VideoCapture(0)
            if not self.video_cap.isOpened():
                await self._send_message(websocket, {
                    "type": "error",
                    "message": "无法打开摄像头"
                })
                return
        
        self.video_enabled = True
        
        await self._send_message(websocket, {
            "type": "video_started",
            "quality": self.video_quality,
            "timestamp": datetime.now().isoformat()
        })
        
        # 启动视频流发送
        asyncio.create_task(self._send_video_stream(websocket))
    
    async def _send_video_stream(self, websocket):
        """发送视频流"""
        while self.video_enabled and websocket in self.clients:
            try:
                ret, frame = self.video_cap.read()
                if not ret:
                    break
                
                # 调整大小以减少带宽
                frame = cv2.resize(frame, (640, 480))
                
                # 编码为JPEG
                _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, self.video_quality])
                
                # Base64编码
                frame_base64 = base64.b64encode(buffer).decode('utf-8')
                
                # 发送帧
                await self._send_message(websocket, {
                    "type": "video_frame",
                    "data": frame_base64,
                    "timestamp": datetime.now().isoformat()
                })
                
                # 控制帧率（约15fps）
                await asyncio.sleep(0.066)
                
            except Exception as e:
                print(f"视频流错误: {e}")
                break
        
        self.video_enabled = False
    
    async def _handle_voice_command(self, websocket, data):
        """处理语音命令"""
        command_text = data.get("text", "")
        
        # 简单的命令解析
        response = self._parse_voice_command(command_text)
        
        await self._send_message(websocket, {
            "type": "voice_response",
            "command": command_text,
            "response": response,
            "timestamp": datetime.now().isoformat()
        })
    
    def _parse_voice_command(self, text):
        """解析语音命令"""
        text = text.lower()
        
        if "前进" in text or "forward" in text:
            self._execute_in_main_thread(lambda: self._move_chassis("forward", 10))
            return "正在前进"
        
        elif "后退" in text or "backward" in text:
            self._execute_in_main_thread(lambda: self._move_chassis("backward", 10))
            return "正在后退"
        
        elif "左转" in text or "left" in text:
            self._execute_in_main_thread(lambda: self._move_chassis("rotate_left", 10))
            return "正在左转"
        
        elif "右转" in text or "right" in text:
            self._execute_in_main_thread(lambda: self._move_chassis("rotate_right", 10))
            return "正在右转"
        
        elif "停止" in text or "stop" in text:
            self._execute_in_main_thread(lambda: self.gui._emergency_stop())
            return "已停止"
        
        elif "回到原点" in text or "home" in text:
            self._execute_in_main_thread(lambda: self._move_to_home())
            return "正在回到原点"
        
        else:
            return "未识别的命令"
    
    async def _send_status(self, websocket):
        """发送状态信息"""
        try:
            # 安全获取属性
            joint_angles = getattr(self.gui, 'joint_angles', [0.0] * 4)
            chassis_angles = getattr(self.gui, 'chassis_wheel_angles', [0.0] * 3)
            speed = getattr(self.gui, 'speed_percent', 23)
            
            # 安全获取串口连接状态
            serial_connected = False
            if hasattr(self.gui, 'serial_comm') and hasattr(self.gui.serial_comm, 'is_connected'):
                serial_connected = self.gui.serial_comm.is_connected
            
            status = {
                "type": "status",
                "joint_angles": list(joint_angles),
                "chassis_angles": list(chassis_angles),
                "speed": speed,
                "serial_connected": serial_connected,
                "timestamp": datetime.now().isoformat()
            }
            
            print(f"[远程控制] 发送状态: 关节={joint_angles}, 底盘={chassis_angles}, 串口={serial_connected}")
            await self._send_message(websocket, status)
        except Exception as e:
            print(f"[远程控制] 发送状态失败: {e}")
            import traceback
            traceback.print_exc()
    
    async def _send_message(self, websocket, data):
        """发送消息到客户端"""
        try:
            await websocket.send(json.dumps(data))
        except Exception as e:
            print(f"发送消息失败: {e}")
    
    async def broadcast_status(self):
        """广播状态到所有客户端"""
        if not self.clients:
            return
        
        try:
            # 安全获取属性
            joint_angles = getattr(self.gui, 'joint_angles', [0.0] * 4)
            chassis_angles = getattr(self.gui, 'chassis_wheel_angles', [0.0] * 3)
            speed = getattr(self.gui, 'speed_percent', 23)
            
            serial_connected = False
            if hasattr(self.gui, 'serial_comm') and hasattr(self.gui.serial_comm, 'is_connected'):
                serial_connected = self.gui.serial_comm.is_connected
            
            status = {
                "type": "status_update",
                "joint_angles": list(joint_angles),
                "chassis_angles": list(chassis_angles),
                "speed": speed,
                "serial_connected": serial_connected,
                "timestamp": datetime.now().isoformat()
            }
            
            print(f"[广播] 关节={joint_angles}, 底盘={chassis_angles}")
            
            # 发送到所有客户端
            disconnected = set()
            for client in self.clients:
                try:
                    await self._send_message(client, status)
                except:
                    disconnected.add(client)
            
            # 移除断开的客户端
            self.clients -= disconnected
        except Exception as e:
            print(f"[远程控制] 广播状态失败: {e}")
            import traceback
            traceback.print_exc()
    
    def _execute_in_main_thread(self, func):
        """在主线程中执行函数"""
        try:
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, func)
        except:
            func()
    
    def _move_joint(self, joint_id, angle):
        """移动关节"""
        if 0 <= joint_id < len(self.gui.joint_angles):
            self.gui.joint_angles[joint_id] = angle
            all_angles = list(self.gui.joint_angles) + list(self.gui.chassis_wheel_angles)
            self.gui.serial_comm.send_angles(all_angles, num_arm_joints=self.gui.NUM_ARM_JOINTS)
    
    def _move_chassis(self, direction, distance):
        """移动底盘"""
        # 增加移动距离系数，使控制更明显
        distance = distance * 5.0
        
        current_angles = self.gui.chassis_wheel_angles.copy()
        
        if direction == "forward":
            current_angles[0] -= distance * 0.866
            current_angles[2] += distance * 0.866
        elif direction == "backward":
            current_angles[0] += distance * 0.866
            current_angles[2] -= distance * 0.866
        elif direction == "left":
            current_angles[0] -= distance * 0.5
            current_angles[1] += distance
            current_angles[2] -= distance * 0.5
        elif direction == "right":
            current_angles[0] += distance * 0.5
            current_angles[1] -= distance
            current_angles[2] += distance * 0.5
        elif direction == "rotate_left":
            current_angles[0] -= distance
            current_angles[1] -= distance
            current_angles[2] -= distance
        elif direction == "rotate_right":
            current_angles[0] += distance
            current_angles[1] += distance
            current_angles[2] += distance
        
        # 更新GUI状态
        self.gui.chassis_wheel_angles = current_angles
        
        all_angles = list(self.gui.joint_angles) + list(current_angles)
        self.gui.serial_comm.send_angles(all_angles, num_arm_joints=self.gui.NUM_ARM_JOINTS)
    
    def _move_to_home(self):
        """回到原点"""
        self.gui.joint_angles = [0.0] * 4
        self.gui.chassis_wheel_angles = [0.0] * 3
        all_angles = list(self.gui.joint_angles) + list(self.gui.chassis_wheel_angles)
        self.gui.serial_comm.send_angles(all_angles, num_arm_joints=self.gui.NUM_ARM_JOINTS)
