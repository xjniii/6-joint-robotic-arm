#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
运动学模块
"""

import math
import numpy as np

# 尝试导入 ikpy
try:
    from ikpy.chain import Chain
    from ikpy.link import OriginLink, URDFLink
    IKPY_AVAILABLE = True
except ImportError:
    IKPY_AVAILABLE = False
    print("警告: ikpy未安装，逆运动学功能将不可用")


class Kinematics:
    """运动学计算类"""
    
    def __init__(self):
        self.arm_chain = None
        self.last_angles_rad = None
        
        if IKPY_AVAILABLE:
            self.arm_chain = self._create_robot_arm()
            self.last_angles_rad = np.zeros(5)
    
    def _create_robot_arm(self):
        """创建4-DOF机械臂链"""
        if not IKPY_AVAILABLE:
            return None
        
        links = [
            OriginLink(),
            URDFLink(
                name="J0",
                origin_translation=[0, 0, 0.267],
                origin_orientation=[0, 0, 0],
                rotation=[0, 0, 1],
                bounds=(math.radians(-360), math.radians(360))
            ),
            URDFLink(
                name="J1",
                origin_translation=[0, 0, 0.2845],
                origin_orientation=[0, 0, 0],
                rotation=[0, 1, 0],
                bounds=(math.radians(-118), math.radians(120))
            ),
            URDFLink(
                name="J2",
                origin_translation=[0, 0, 0.0775],
                origin_orientation=[0, 0, 0],
                rotation=[0, 0, 1],
                bounds=(math.radians(-225), math.radians(11))
            ),
            URDFLink(
                name="J3",
                origin_translation=[0, 0, 0.3425],
                origin_orientation=[0, 0, 0],
                rotation=[0, 1, 0],
                bounds=(math.radians(-360), math.radians(360))
            ),
        ]
        return Chain(links, active_links_mask=[False, True, True, True, True])
    
    def calculate_ik(self, target_pos, num_arm_joints=4):
        """计算逆运动学"""
        if not IKPY_AVAILABLE or not self.arm_chain:
            raise Exception("ikpy未安装或未初始化")
        
        # 计算逆运动学
        ik_angles_rad = self.arm_chain.inverse_kinematics(
            target_position=target_pos,
            initial_position=self.last_angles_rad
        )
        
        self.last_angles_rad = ik_angles_rad
        
        # 转换为度数
        angles_deg = [math.degrees(angle) for angle in ik_angles_rad[1:num_arm_joints+1]]
        
        return angles_deg
    
    @staticmethod
    def is_available():
        """检查IK是否可用"""
        return IKPY_AVAILABLE
    
    def forward_kinematics(self, joint_angles_deg):
        """正运动学：从关节角度计算末端位置
        
        Args:
            joint_angles_deg: 关节角度列表（度）
            
        Returns:
            [x, y, z] 末端位置（毫米）
        """
        if IKPY_AVAILABLE and self.arm_chain:
            # 转换为弧度
            angles_rad = [0] + [math.radians(a) for a in joint_angles_deg[:4]]
            # 计算正运动学
            matrix = self.arm_chain.forward_kinematics(angles_rad)
            # 提取位置（转换为毫米）
            x = matrix[0, 3] * 1000
            y = matrix[1, 3] * 1000
            z = matrix[2, 3] * 1000
            return [x, y, z]
        else:
            # 简化的正运动学计算（基于DH参数）
            # 这是一个近似计算
            l1 = 267  # 基座高度
            l2 = 284.5  # 第二段长度
            l3 = 342.5  # 第三段长度
            
            j1 = math.radians(joint_angles_deg[0] if len(joint_angles_deg) > 0 else 0)
            j2 = math.radians(joint_angles_deg[1] if len(joint_angles_deg) > 1 else 0)
            j3 = math.radians(joint_angles_deg[2] if len(joint_angles_deg) > 2 else 0)
            
            # 计算XYZ位置
            r = l2 * math.cos(j2) + l3 * math.cos(j2 + j3)
            x = r * math.cos(j1)
            y = r * math.sin(j1)
            z = l1 + l2 * math.sin(j2) + l3 * math.sin(j2 + j3)
            
            return [x, y, z]
    
    def inverse_kinematics(self, x, y, z):
        """逆运动学：从末端位置计算关节角度
        
        Args:
            x, y, z: 目标位置（毫米）
            
        Returns:
            关节角度列表（度），如果无解返回None
        """
        if IKPY_AVAILABLE and self.arm_chain:
            try:
                # 转换为米
                target_pos = [x/1000, y/1000, z/1000]
                angles_deg = self.calculate_ik(target_pos, num_arm_joints=4)
                return angles_deg
            except Exception as e:
                print(f"IKPy逆运动学失败: {e}")
                return None
        else:
            # 简化的逆运动学计算（几何法）
            try:
                l1 = 267  # 基座高度
                l2 = 284.5  # 第二段长度
                l3 = 342.5  # 第三段长度
                
                # 关节1：绕Z轴旋转
                j1 = math.atan2(y, x)
                
                # 计算水平距离和垂直距离
                r = math.sqrt(x*x + y*y)
                h = z - l1
                
                # 计算到目标的距离
                d = math.sqrt(r*r + h*h)
                
                # 检查是否在工作空间内
                if d > (l2 + l3) or d < abs(l2 - l3):
                    print(f"目标位置超出工作空间: d={d:.1f}, max={l2+l3:.1f}")
                    return None
                
                # 使用余弦定理计算关节2和3
                cos_j3 = (d*d - l2*l2 - l3*l3) / (2 * l2 * l3)
                cos_j3 = max(-1, min(1, cos_j3))  # 限制在[-1, 1]
                j3 = math.acos(cos_j3)
                
                # 计算关节2
                alpha = math.atan2(h, r)
                beta = math.acos((l2*l2 + d*d - l3*l3) / (2 * l2 * d))
                j2 = alpha + beta
                
                # 转换为度
                angles = [
                    math.degrees(j1),
                    math.degrees(j2),
                    math.degrees(j3),
                    0  # 关节4保持为0
                ]
                
                return angles
                
            except Exception as e:
                print(f"几何逆运动学失败: {e}")
                return None
