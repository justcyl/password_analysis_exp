from pyecharts import options as opts
from pyecharts.charts import Pie
import pickle
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from project_paths import analysis_mid_dir, report_assets_dir

PKL_DIR = analysis_mid_dir("analysis_task_3")
CHART_DIR = report_assets_dir("analysis_task_3")


def show_pie(title, labels, values, output_name):
    pie = (
        Pie()
            .add("", [list(z) for z in zip(labels, values)], radius=["30%","50%"], center=["40%","60%"])
            .set_global_opts(title_opts=opts.TitleOpts(title=title),
                            legend_opts=opts.LegendOpts(
                                orient="vertical", pos_top="5%", pos_right="2%"  # 左面比例尺
                                ),
                            )
            .set_series_opts(label_opts=opts.LabelOpts(formatter="{b}: {d}%"))
        )
    pie.render(str((CHART_DIR / f"{output_name}.html").resolve()))


# FILE_NAME = 'csdn'
FILE_NAME = 'yahoo'


def main():
    with open(PKL_DIR / f'{FILE_NAME}_sorted_pinyin_lib.pkl', 'rb') as f:
        sorted_lib = pickle.load(f)

    len_lib = {}
    for item in sorted_lib:
        length = len(item[0])
        len_lib[length] = len_lib.get(length, 0) + item[1]
    # print(len_lib)
    # exit()
    f.close()

    show_pie(f'{FILE_NAME} 拼音长度分布', list(len_lib.keys()), list(len_lib.values()), f'{FILE_NAME}_length_pinyin_analysis')
    
    with open(PKL_DIR / f'{FILE_NAME}_sorted_word_lib.pkl', 'rb') as f:
        sorted_lib = pickle.load(f)

    len_lib = {}
    for item in sorted_lib:
        length = len(item[0])
        len_lib[length] = len_lib.get(length, 0) + item[1]

    f.close()

    show_pie(f'{FILE_NAME} 单词长度分布', list(len_lib.keys()), list(len_lib.values()), f'{FILE_NAME}_length_word_analysis')


if __name__ == "__main__":
    main()
