import os
import pickle
from pathlib import Path
from progress.bar import Bar
from utils import load_data

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
PCFG_MID_DIR = ROOT / "mid" / "pcfg_advance"
PCFG_MID_DIR.mkdir(parents=True, exist_ok=True)

FILE_NAME = 'yahoo'
# FILE_NAME = 'csdn'
MID_DIR = PCFG_MID_DIR


def test(file_name):
    data_path = DATA_DIR / f'data_{file_name}.pkl'
    _, test_data = load_data(data_path)
    guesses_path = MID_DIR / f'{file_name}_genpwds.txt'
    with guesses_path.open('r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
    gen_pwds = [line.split(' ')[0].strip() for line in lines]

    total_count = len(test_data)
    match_count = 0
    matched_lst = []

    bar = Bar(max=len(test_data))
    for data in test_data:
        if(data in gen_pwds):
            match_count += 1
            matched_lst.append(data)
        bar.next()
    bar.finish()

    acc = float(match_count) / float(total_count)
    print(acc)
    with (MID_DIR / 'res.txt').open('a', encoding='utf-8') as f:
        f.write('{}\n'.format(acc))

    matched_str = '\n'.join([str(item) for item in matched_lst])
    with (MID_DIR / 'info.txt').open('a', encoding='utf-8') as f:
        f.write(matched_str)


def main():
    test(FILE_NAME)

if __name__ == '__main__':
    main()
