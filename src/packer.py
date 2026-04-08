from os import mkdir
from pathlib import Path
from re import findall, MULTILINE
from json import loads
from json import dumps
from sys import argv, stdout
from io import TextIOWrapper
from os.path import exists as folderexists

class ModWord:
    origin_name = ''
    trans_name = ''
    modid = ''
    key = ''
    version = ''
    curseforge = ''

    def writeLine(self):
        print(self.origin_name, self.trans_name, self.modid, self.key, self.version, self.curseforge)

keylist = []

unknownCount = 0


def main(path, version):
    dir = Path(path)
    for i in dir.iterdir():
        if i.name == '1UNKNOWN':
            for o in i.iterdir():
                if (o / 'lang' / 'zh_cn.lang').exists() and (o / 'lang' / 'en_us.lang').exists():
                    en_dict: dict = readFile(o / 'lang' / 'en_us.lang')
                    zh_dict: dict = readFile(o / 'lang' / 'zh_cn.lang')
                    zh_keys = zh_dict.keys()
                    for key, value in en_dict.items():
                        if key in zh_keys:
                            mod = ModWord()
                            mod.key = key
                            mod.origin_name = value
                            mod.trans_name = zh_dict[key]
                            mod.version = version
                            mod.modid = o.name
                            mod.curseforge = 'Unknown'
                            keylist.append(mod)
                            global unknownCount
                            unknownCount += 1
            continue
        lang_pairs = collect_lang_pairs(i)
        for curseforge, modid, en_file, zh_file in lang_pairs:
            en_dict: dict = readFile(en_file)
            zh_dict: dict = readFile(zh_file)
            zh_keys = zh_dict.keys()
            for key, value in en_dict.items():
                if key in zh_keys:
                    mod = ModWord()
                    mod.key = key
                    mod.origin_name = value
                    mod.trans_name = zh_dict[key]
                    mod.version = version
                    mod.modid = modid
                    mod.curseforge = curseforge
                    keylist.append(mod)
    print(f'{version}已处理{len(keylist)}条')

    if unknownCount > 0:
        print(f'注意：本次生成存在{unknownCount}条未知词条')


def readFile(f: Path):
    ret_dict = {}
    if f.name.endswith('.lang'):
        text = f.open(encoding='utf-8').readlines()
        for i in text:
            i = i.split('=', 1)
            for o in range(len(i)):
                if i[o].endswith('\n'):
                    i[o] = i[o][:-1]
            if len(i) == 2:
                ret_dict[i[0]] = i[1]
    elif f.name.endswith('.json'):
        text = f.open(encoding='utf-8').read()
        try:
            json_dict = loads(text)
        except Exception:
            # 兼容历史上可能出现的格式问题（例如尾随逗号）
            pairs = findall('"[^"]+"\:\s*"[^"]+"', text, flags=MULTILINE)
            for i in pairs:
                key, value = findall('"[^"]+"', i, flags=MULTILINE)
                ret_dict[key[1:-1]] = value[1:-1]
            return ret_dict
        if isinstance(json_dict, dict):
            for key, value in json_dict.items():
                if isinstance(value, str):
                    ret_dict[key] = value
    return ret_dict


def collect_lang_pairs(dir: Path):
    ret = []
    for son_dir in dir.iterdir():
        if not son_dir.is_dir():
            continue
        lang = son_dir / 'lang'
        if not lang.is_dir():
            continue
        en_file = None
        zh_file = None
        for i in lang.iterdir():
            if i.stem == 'zh_cn':
                zh_file = i
            if i.stem == 'en_us':
                en_file = i
        if en_file and zh_file:
            ret.append((dir.name, son_dir.name, en_file, zh_file))
    return ret


if __name__ == '__main__':
    # stdout = TextIOWrapper(stdout.buffer, encoding='gbk')

    print('程序初始化')
    if not folderexists('DictPacker'):
        mkdir('DictPacker')
        print('创建文件夹DictPacker')

    folder = f'./Minecraft-Mod-Language-Package/projects/{argv[1]}/assets'
    version = argv[1]
    print(f'开始处理{version}')
    main(folder, version)
    # main('./projects/1.12.2/assets', '1.12.2')
    # main('./projects/1.16/assets', '1.16')
    # main('./projects/1.16-fabric/assets', '1.16-fabric')
    # main('./projects/1.18/assets', '1.18')
    # main('./projects/1.18-fabric/assets', '1.18-fabric')

    savejson = []

    print('开始生成json')
    for i in keylist:
        i: ModWord
        mod = {
            "origin_name": i.origin_name,
            "trans_name": i.trans_name,
            "modid": i.modid,
            "key": i.key,
            "version": i.version,
            "curseforge": i.curseforge
        }
        savejson.append(mod)

    savejson = dumps(savejson, ensure_ascii=False, indent=4)

    file = open(f'DictPacker/Dict-{version}.json', 'w', encoding='utf-8')
    file.write(savejson)
    file.close()

    print(f'已生成Dict-{version}.json')
