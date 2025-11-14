import os
import pickle
from progress.bar import Bar
from utils import load_data

FILE_NAME = 'yahoo'
# FILE_NAME = 'csdn'
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.abspath(os.path.join(BASE_DIR, '..', 'data'))


def test(file_name):
    data_path = os.path.join(DATA_DIR, f'data_{file_name}.pkl')
    _, test_data = load_data(data_path)
    guesses_path = os.path.join(BASE_DIR, f'{file_name}_genpwds.txt')
    with open(guesses_path, 'r', encoding='utf-8', errors='ignore') as f:
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
    with open(os.path.join(BASE_DIR, 'res.txt'), 'a', encoding='utf-8') as f:
        f.write('{}\n'.format(acc))

    matched_str = '\n'.join([str(item) for item in matched_lst])
    with open(os.path.join(BASE_DIR, 'info.txt'), 'a', encoding='utf-8') as f:
        f.write(matched_str)


def main():
    test(FILE_NAME)

if __name__ == '__main__':
    main()
