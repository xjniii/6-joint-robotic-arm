#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
串口通信模块
"""

import serial
import serial.tools.list_ports
import threading
import queue
import time


class SerialCommunication:
    """串口通信管理类"""
    
    def __init__(self, num_motors=7, gear_ratio_arm=100.0, gear_ratio_base=37.1):
        self.serial_port = None
        self.is_connected = False
        
        self.num_motors = num_motors
        self.gear_ratio_arm = gear_ratio_arm
        self.gear_ratio_base = gear_ratio_base
        
        # 线程和队列
        self.serial_thread = None
        self.thread_stop_event = threading.Event()
        self.feedback_queue = queue.Queue()
        self.raw_serial_queue = queue.Queue()
        
        # 反馈数据
        self.last_feedback_pos = [0.0] * num_motors
        self.last_feedback_pos_raw = [0.0] * num_motors
        self.last_target_angles = [0.0] * num_motors
        
        # 运动同步
        self.move_complete_event = threading.Event()
        self.is_waiting_for_move_completion = False
        self.waiting_joints = []
        self.move_timeout_seconds = 10.0
        self.position_tolerance_deg = 0.05
        self.wait_start_time = None
    
    @staticmethod
    def get_serial_ports():
        """获取可用串口列表"""
        ports = [port.device for port in serial.tools.list_ports.comports()]
        return ports if ports else ["无可用串口"]
    
    def connect(self, port, baudrate=115200):
        """连接串口"""
        try:
            self.serial_port = serial.Serial(port, baudrate, timeout=1)
            self.is_connected = True
            
            # 启动串口读取线程
            self.thread_stop_event.clear()
            self.serial_thread = threading.Thread(target=self._read_serial_data, daemon=True)
            self.serial_thread.start()
            
            print(f"已连接到 {port} @ {baudrate} baud")
            return True
            
        except Exception as e:
            print(f"连接错误: {str(e)}")
            return False
    
    def disconnect(self):
        """断开串口连接"""
        self.thread_stop_event.set()
        if self.serial_thread:
            self.serial_thread.join(timeout=2)
        
        if self.serial_port:
            try:
                self.serial_port.close()
            except:
                pass
        
        self.is_connected = False
        print("已断开串口连接")
    
    def send_angles(self, angles_deg, num_arm_joints=4, wait_for_completion=False):
        """发送角度命令
        
        Args:
            angles_deg: 角度列表，包含所有电机的角度（关节+底盘）
            num_arm_joints: 机械臂关节数量（默认6）
            wait_for_completion: 是否等待运动完成
        """
        if not self.serial_port or not self.serial_port.is_open:
            print("串口未连接，无法发送命令")
            return False
        
        # 应用减速比
        angles_with_ratio = []
        for i in range(self.num_motors):
            if i < num_arm_joints:
                # 关节电机使用关节减速比
                angles_with_ratio.append(angles_deg[i] * self.gear_ratio_arm if i < len(angles_deg) else 0.0)
            else:
                # 底盘电机使用底盘减速比
                angles_with_ratio.append(angles_deg[i] * self.gear_ratio_base if i < len(angles_deg) else 0.0)
        
        self.last_target_angles = angles_deg.copy() if len(angles_deg) >= self.num_motors else angles_deg + [0.0] * (self.num_motors - len(angles_deg))
        
        if wait_for_completion:
            self.move_complete_event.clear()
            self.is_waiting_for_move_completion = True
            self.waiting_joints = list(range(num_arm_joints))
            self.wait_start_time = time.time()
        else:
            self.is_waiting_for_move_completion = False
            self.waiting_joints = []
        
        # 发送命令
        command = ",".join(f"{angle:.2f}" for angle in angles_with_ratio) + "\n"
        try:
            self.serial_port.write(command.encode('utf-8'))
            print(f"发送命令: {command.strip()}")
            return True
        except serial.SerialException as e:
            print(f"串口写入错误: {e}")
            self.is_waiting_for_move_completion = False
            return False
    
    def _read_serial_data(self):
        """串口数据读取线程"""
        while not self.thread_stop_event.is_set() and self.serial_port and self.serial_port.is_open:
            try:
                line = self.serial_port.readline().decode('utf-8').strip()
                if line:
                    self.raw_serial_queue.put(line)
                    self.feedback_queue.put(line)
            except (serial.SerialException, UnicodeDecodeError) as e:
                if not self.thread_stop_event.is_set():
                    print(f"串口读取错误: {e}")
                    self.feedback_queue.put("SERIAL_ERROR")
                break
    
    def process_feedback(self, num_arm_joints=4):
        """处理反馈数据 - 直接显示网关原始反馈值，机械臂需要除以减速比"""
        processed = []
        try:
            while not self.feedback_queue.empty():
                feedback_str = self.feedback_queue.get_nowait().strip()
                
                # 解析格式: "FB:motor_id,position,voltage"
                if not feedback_str.startswith("FB:"):
                    continue
                
                try:
                    data_part = feedback_str[3:]  # 移除"FB:"前缀
                    sub_parts = data_part.split(',')
                    if len(sub_parts) != 3:
                        continue
                    
                    motor_id = int(sub_parts[0])
                    raw_pos_deg = float(sub_parts[1])  # 网关发送的电机轴角度（已乘减速比）
                    volt = float(sub_parts[2])
                    
                    if not (0 <= motor_id < self.num_motors):
                        continue
                    
                    # 保存原始值
                    self.last_feedback_pos_raw[motor_id] = raw_pos_deg
                    
                    # 机械臂关节需要除以减速比得到输出轴角度，底盘直接显示
                    if motor_id < num_arm_joints:
                        output_pos_deg = raw_pos_deg / self.gear_ratio_arm
                    else:
                        output_pos_deg = raw_pos_deg / self.gear_ratio_base
                    
                    self.last_feedback_pos[motor_id] = output_pos_deg
                    processed.append((motor_id, output_pos_deg, volt))
                    
                    # 检查运动完成
                    if self.is_waiting_for_move_completion:
                        self._check_move_completion(num_arm_joints)
                
                except (ValueError, IndexError) as e:
                    print(f"解析反馈数据失败: '{feedback_str}'. 错误: {e}")
        
        except queue.Empty:
            pass
        
        return processed
    
    def _check_move_completion(self, num_arm_joints):
        """检查运动是否完成"""
        active_joints = self.waiting_joints if self.waiting_joints else list(range(num_arm_joints))
        
        all_in_position = True
        for j_id in active_joints:
            if not (0 <= j_id < len(self.last_feedback_pos)):
                all_in_position = False
                break
            
            target = self.last_target_angles[j_id]
            current = self.last_feedback_pos[j_id]
            
            if abs(current - target) > self.position_tolerance_deg:
                all_in_position = False
                break
        
        if all_in_position:
            print("运动完成：所有关节已到位")
            self.move_complete_event.set()
            self.is_waiting_for_move_completion = False
            self.waiting_joints = []
        
        # 超时检测
        if self.wait_start_time and (time.time() - self.wait_start_time) > self.move_timeout_seconds:
            print("警告：运动超时")
            self.is_waiting_for_move_completion = False
            self.waiting_joints = []
            self.wait_start_time = None
