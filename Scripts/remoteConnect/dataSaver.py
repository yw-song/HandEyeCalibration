import pandas as pd
import csv
import warnings
from pathlib import Path
from typing import List
from datetime import datetime
from threading import Lock
from .socketClient import MeasurePoint
from typing import Dict

# 过滤openpyxl警告
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=DeprecationWarning)


class DataSaver:
    REQUIRED_IDS = set(range(101, 113))  # 101-112必须存在的ID

    def __init__(self):
        self.case_counter = 1
        self.output_dir = Path("../Data")
        self._lock = Lock()
        self._init_storage()

    def _init_storage(self):
        """初始化存储目录和文件结构"""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.file_path = self.output_dir / "targetPoint.xlsx"

        # 创建带初始sheet的文件
        if not self.file_path.exists():
            with pd.ExcelWriter(self.file_path, engine='openpyxl') as writer:
                pd.DataFrame(columns=['ID', 'X', 'Y', 'Z', 'Timestamp']).to_excel(
                    writer, sheet_name='Template', index=False)

    def save_case(self, points: List[MeasurePoint]) -> bool:
        """线程安全的数据保存方法"""
        with self._lock:
            return self._save_case(points)

    def _save_case(self, points: List[MeasurePoint]) -> bool:
        """实际保存逻辑"""
        # 数据完整性校验
        received_ids = {p.ID for p in points}
        if not self.REQUIRED_IDS.issubset(received_ids):
            missing = self.REQUIRED_IDS - received_ids
            existing = received_ids & self.REQUIRED_IDS  # 有效ID中的存在部分

            # 将集合转为排序后的列表便于阅读
            sorted_missing = sorted(missing)
            sorted_received = sorted(received_ids)
            sorted_existing = sorted(existing)

            print(f"× 保存失败：缺失必须点位 {sorted_missing}")
            print(f"   当前收到有效点位: {sorted_existing}（共{len(sorted_existing)}个）")
            print(f"   所有收到点位: {sorted_received}")
            return False

        # 获取精确到毫秒的时间戳
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

        try:
            # 构建数据框架
            sorted_points = sorted(
                [p for p in points if p.ID in self.REQUIRED_IDS],
                key=lambda x: x.ID
            )

            df = pd.DataFrame({
                'ID': [p.ID for p in sorted_points],
                'X': [f"{p.X:.6f}" for p in sorted_points],
                'Y': [f"{p.Y:.6f}" for p in sorted_points],
                'Z': [f"{p.Z:.6f}" for p in sorted_points],
                'Timestamp': [timestamp] * len(sorted_points)
            })

            # 写入Excel文件
            with pd.ExcelWriter(
                    self.file_path,
                    engine='openpyxl',
                    mode='a',
                    if_sheet_exists='replace'
            ) as writer:
                df.to_excel(writer, sheet_name=f'Case{self.case_counter}', index=False)

            print(f"√ Case{self.case_counter} 保存成功 | 时间: {timestamp}")
            self.case_counter += 1
            return True

        except PermissionError:
            print("× 文件被占用，请关闭Excel后重试")
            return False
        except Exception as e:
            print(f"× 保存异常：{str(e)}")
            return False


class CSVDataSaver:
    def __init__(self, file_path: str):
        self.file_path = Path(file_path)
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        self._initialize_csv()

    def _initialize_csv(self):
        """初始化CSV文件并写入标题行"""
        if not self.file_path.exists():
            with self._lock:
                with open(self.file_path, 'w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(['Timestamp', 'ID', 'X', 'Y', 'Z'])

    def save_averages(self, averages: Dict[int, dict], timestamp: str) -> bool:
        """保存平均值到CSV（每个ID单独一行）"""
        with self._lock:
            try:
                with open(self.file_path, 'a', newline='') as f:
                    writer = csv.writer(f)
                    for id in sorted(averages.keys()):
                        avg = averages[id]
                        writer.writerow([
                            timestamp,
                            id,
                            f"{avg['X']:.6f}",
                            f"{avg['Y']:.6f}",
                            f"{avg['Z']:.6f}"
                        ])
                print(f"√ 数据已追加至 {self.file_path}")
                return True
            except Exception as e:
                print(f"× 保存失败: {str(e)}")
                return False


class RobotDataSaver:
    def __init__(self, file_path: str):
        self.file_path = Path(file_path)
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        self._initialize_csv()

    def _initialize_csv(self):
        """初始化机器人数据CSV文件"""
        if not self.file_path.exists():
            with self._lock, open(self.file_path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'Timestamp',
                    'X_avg', 'Y_avg', 'Z_avg',
                    'RX_avg', 'RY_avg', 'RZ_avg'
                ])

    def save_robot_averages(self, averages: dict, timestamp: str) -> bool:
        """保存机器人平均值数据"""
        try:
            with self._lock, open(self.file_path, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    timestamp,
                    f"{averages['x']:.6f}",
                    f"{averages['y']:.6f}",
                    f"{averages['z']:.6f}",
                    f"{averages['rx']:.6f}",
                    f"{averages['ry']:.6f}",
                    f"{averages['rz']:.6f}"
                ])
            return True
        except Exception as e:
            print(f"机器人数据保存失败: {str(e)}")
            return False
        