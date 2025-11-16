import pickle
import os
import re
import numpy as np
from progress.bar import Bar
from pathlib import Path
from typing import List, Tuple

# --- 1. 路径和常量定义 ---
ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"

# 默认分割大小
SPLIT_COUNT = 50000


# --- 2. 数据读取与编码修复 ---
# 修复 NameError: data_path 未定义
# 修复 UnicodeDecodeError: 增加 GBK/Latin-1 编码尝试
def init_data(dataset_name: str) -> Tuple[List[str], int]:
    data_path = DATA_DIR / f"{dataset_name}.txt"
    lines = []

    # 尝试使用 GBK 编码，并忽略错误字符
    try:
        with open(data_path, 'r', encoding='gbk', errors='ignore') as f:
            lines = f.readlines()
    except Exception:
        # 如果 GBK 也失败，回退到 latin-1
        with open(data_path, 'r', encoding='latin-1', errors='ignore') as f:
            lines = f.readlines()

    TOTAL_COUNT = len(lines)
    print(f"[{dataset_name}] Total lines read: {TOTAL_COUNT}")

    # 解析密码字段
    if dataset_name == "csdn":
        # 匹配 csdn.txt 的 '#...#' 分隔格式
        passwords = ['#'.join(line.split('#')[1:-1]).strip()
                     for line in lines if line.strip()]
    else:
        # 匹配 yahoo.txt 或其他数据集的 '...:password' 格式
        passwords = [':'.join(line.split(':')[2:]).strip()
                     for line in lines if line.strip()]

    # 进一步过滤空密码
    passwords = [pwd for pwd in passwords if pwd]

    return passwords, TOTAL_COUNT


def _filter_data(passwords: List[str]) -> List[str]:
    filtered_data = []
    bar = Bar('Filtering', max=len(passwords))
    for password in passwords:
        length = len(password)
        # 数字+小写字母 's12345'
        if (length >= 6 and length <= 12 and re.match(r'[0-9a-z]+$', password)):
            filtered_data.append(password)
        bar.next()
    bar.finish()
    print(f"Filtered to {len(filtered_data)} valid passwords.")
    return filtered_data


def _split_data(data: List[str], count=SPLIT_COUNT) -> Tuple[List[str], List[str]]:
    length = len(data)

    # 如果数据不足，则调整分割数量
    split_count = min(count, length // 2)
    if split_count == 0:
        return [], data

    indexes = list(range(length))
    # 确保随机性，打乱索引
    indexes = np.random.permutation(indexes)

    train_indexes = indexes[:-split_count]
    test_indexes = indexes[-split_count:]

    train_data = [data[i] for i in train_indexes]
    test_data = [data[i] for i in test_indexes]

    print(f"Split data: Train={len(train_data)}, Test={len(test_data)}")

    return train_data, test_data


# 接受 dataset_name，用于构造文件名和保存路径
def filter_split_data(dataset_name: str, passwords: List[str]) -> Tuple[List[str], List[str]]:
    data_save_path = DATA_DIR / f"data_{dataset_name}.pkl"

    if not os.path.exists(data_save_path):
        print(f"--- Generating {dataset_name} data (Split Count: {SPLIT_COUNT}) ---")

        filtered_data = _filter_data(passwords)
        train_data, test_data = _split_data(filtered_data, count=SPLIT_COUNT)

        # 修复了之前可能出现的 ValueError: too many values to unpack (expected 2)
        # 确保只 dump (train_data, test_data) 两个元素
        with open(data_save_path, 'wb') as f:
            pickle.dump((train_data, test_data), f)

        print(f"Data saved to {data_save_path}")
        return train_data, test_data
    else:
        print(f"--- Loading {dataset_name} data from {data_save_path} ---")
        with open(data_save_path, 'rb') as f:
            # 使用修正后的安全加载逻辑（假设 utils.py 已修复）
            data = pickle.load(f)
            if isinstance(data, (list, tuple)) and len(data) >= 2:
                return data[0], data[1]
            elif isinstance(data, list) and len(data) == 1 and isinstance(data[0], (list, tuple)) and len(data[0]) >= 2:
                # 处理一些非标准格式的 .pkl 文件
                return data[0][0], data[0][1]
            else:
                raise ValueError("PKL file format error: Expected tuple of (train, test) lists.")


def main():
    datasets_to_split = ['csdn', 'yahoo']

    for dataset in datasets_to_split:
        print(f"\nProcessing Dataset: {dataset.upper()}")

        # 1. 读取数据 (init_data 现在接受 dataset 参数)
        passwords, total_count = init_data(dataset)

        # 2. 过滤和分割数据
        filter_split_data(dataset, passwords)

    print("\nAll data processing complete. You can now run the PCFG A/B tests.")


if __name__ == '__main__':
    # 确保 data 目录存在
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    main()