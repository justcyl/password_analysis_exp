from tqdm import tqdm
import itertools
import gc
import os
from test import test
from generate_rules import FILE_NAME

# FILE_NAME = 'yahoo'
FILE_NAME = 'csdn'
FILE_PATH = f"./data/data_{FILE_NAME}.pkl"

def print_lst(lst):

    max_size=max(max(len(j) for j in i) for i in lst)
    max_col=max(len(i) for i in lst)
    
    for i in range(len(lst)):
        for j in range(max_col):
            print(eval("'{: ^"+str(max_size)+"}'.format(lst[i][j] if j < len(lst[i]) else '')"),end='|')
        print('\n'+'='*((max_size+1)*max_col))


class PCFG:
    def __init__(self,data_dir=f'./{FILE_NAME}', 
                # char_rule_filename='char_rule.txt', 
                char_rule_filename='char_lib.txt', 
                number_rule_filename='number_rule.txt',
                pattern_rule_filename='pattern_rule.txt',
                username_token_filename='lib/username_tokens.txt'):

        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        if not os.path.isabs(data_dir):
            data_dir = os.path.join(self.base_dir, data_dir)
        self.data_dir = data_dir
        env_flag = os.getenv('ENABLE_USERNAME_TOKENS', '1').lower()
        self.enable_username_tokens = env_flag not in ('0', 'false', 'off', 'no')

        char_rule = self.get_data(data_dir, char_rule_filename)
        number_rule = self.get_data(data_dir, number_rule_filename)
        pattern_rule = self.get_data(data_dir, pattern_rule_filename)
        self.pattern_rules = [ self._str2tuple(rule) for rule in pattern_rule]

        self.rule_char = self.get_rule(char_rule) # 长度与内容的映射
        self.rule_number = self.get_rule(number_rule)
        self.username_tokens = []
        if self.enable_username_tokens:
            self.username_tokens = self.load_username_tokens(username_token_filename)

        self.limit = 1000
        self.username_token_limit = 50
        self.username_numeric_limit = 25
        self.username_char_limit = 25

        with open(os.path.join(self.base_dir, 'res.txt'), 'a', encoding='utf-8') as f:
            f.write('{}, {}, {}, result = '.format(FILE_NAME, char_rule_filename, number_rule_filename))
        with open(os.path.join(self.base_dir, 'info.txt'), 'a', encoding='utf-8') as f:
            f.write('{}, {}, {}, infos:\n'.format(FILE_NAME, char_rule_filename, number_rule_filename))

    def _str2tuple(self, rule):
        pattern_str, p = rule
        pattern_lst = pattern_str.split(',')
        res = []
        for i in range(0, len(pattern_lst), 2):
            res.append((pattern_lst[i], int(pattern_lst[i+1])))
        res.append(p)
        return res

    def get_data(self, data_dir, filename):
        with open(os.path.join(data_dir, filename), 'r') as f:
            lines = f.readlines()
        return [line.strip().split(' ') for line in lines if not line.isspace()]

    def get_rule(self, items):
        rule = {}
        for item in items:
            content = str(item[0]) # 内容
            p = float(item[1]) # 概率
            length = len(content) # 长度

            if(length not in rule):
                rule[length] = []

            rule[length].append([content, p])
        return rule

    def load_username_tokens(self, rel_path):
        filepath = rel_path
        if not os.path.isabs(filepath):
            filepath = os.path.join(self.base_dir, rel_path)
        if not os.path.exists(filepath):
            return []
        tokens = []
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                parts = line.strip().split(' ')
                if len(parts) != 2:
                    continue
                token, prob = parts
                try:
                    tokens.append([token, float(prob)])
                except ValueError:
                    continue
        tokens.sort(key=lambda item: item[1], reverse=True)
        return tokens

    def generate(self):
        res = []
        for rule in tqdm(self.pattern_rules):
            patterns = rule[:-1]
            if(FILE_NAME == 'yahoo'):
                if(len(patterns) == 3): self.limit = 100
                elif(len(patterns) < 3): self.limit = 1000
                else: continue
            elif(FILE_NAME == 'csdn'):
                if(len(patterns) == 1): self.limit = 1000
                elif(len(patterns) <= 3): self.limit = 100
                else: continue
            p = rule[-1]
            gen_pwds = self._generate_by_pattern(patterns, p)
            res.extend(gen_pwds)

            del gen_pwds
            gc.collect()
        if self.enable_username_tokens:
            username_pwds = self._generate_username_token_candidates()
            res.extend(username_pwds)
        res.sort(key=lambda item : item[1], reverse=True)
        return res

    def _generate_by_pattern(self, patterns, p):
        pattern = patterns[0]
        key = pattern[0]
        value = pattern[1]
        try:
            if key == "L":
                first_pwds = self.rule_char[value]
            elif key == "D":
                first_pwds = self.rule_number[value]
        except:
            first_pwds = []

        if(len(patterns) > 1):
            last_pwds = self._generate_by_pattern(patterns[1:], p)
   
            res = []
            for first_pwd in first_pwds[:self.limit]:
                for last_pwd in last_pwds[:self.limit]:
                    res.append([first_pwd[0] + last_pwd[0], first_pwd[1] * last_pwd[1]])
            return res
        else:
            return first_pwds

    def _generate_username_token_candidates(self):
        if not self.username_tokens:
            return []
        tokens = self.username_tokens[:self.username_token_limit]
        numeric_rules = self._get_top_rule_entries(self.rule_number, self.username_numeric_limit)
        char_rules = self._get_top_rule_entries(self.rule_char, self.username_char_limit)

        res = []
        for token, token_prob in tokens:
            res.append([token, token_prob])
            for number, number_prob in numeric_rules:
                combined = token_prob * number_prob
                res.append([token + number, combined])
                res.append([number + token, combined])
            for word, word_prob in char_rules:
                combined = token_prob * word_prob
                res.append([token + word, combined])
        return res

    def _get_top_rule_entries(self, rule_dict, limit):
        entries = []
        for items in rule_dict.values():
            entries.extend(items)
        entries.sort(key=lambda item: item[1], reverse=True)
        return entries[:limit]

if __name__ == "__main__":
    pcfg = PCFG()
    gen_pwds = pcfg.generate()
    output_path = os.path.join(pcfg.base_dir, f'{FILE_NAME}_genpwds.txt')
    with open(output_path, 'w') as f:
        for gen_pwd in gen_pwds[:200000]:
            f.write(f'{gen_pwd[0]} {gen_pwd[1]}\n')
    
    test(FILE_NAME)
