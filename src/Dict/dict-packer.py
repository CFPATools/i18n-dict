from os import mkdir
from pathlib import Path
from re import findall, MULTILINE
from json import dumps
from sys import argv, stdout
from io import TextIOWrapper

class ModWord:
    origin_name = ''
    trans_name = ''
    modid = ''
    key = ''
    version = ''
    curseforge = ''

    def writeLine(self):
        print(self.origin_name, self.trans_name, self.modid, self.key, self.version, self.curseforge.encode('charmap'))

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
        e = exists(i)
        if e == False: continue
        en_dict: dict = readFile(e[2])
        zh_dict: dict = readFile(e[3])
        zh_keys = zh_dict.keys()
        for key, value in en_dict.items():
            if key in zh_keys:
                mod = ModWord()
                mod.key = key
                mod.origin_name = value
                mod.trans_name = zh_dict[key]
                mod.version = version
                mod.modid = e[1]
                mod.curseforge = e[0]
                keylist.append(mod)
    print(f'{version}已处理{len(keylist)}条'.encode('charmap'))

    if unknownCount > 0:
        print(f'注意：本次生成存在{unknownCount}条未知词条'.encode('charmap'))


def readFile(f: Path):
    ret_dict = {}
    if f.name.endswith('.lang'):
        text = f.open(encoding='utf-8').readlines()
        for i in text:
            i = i.split('=')
            for o in range(len(i)):
                if i[o].endswith('\n'):
                    i[o] = i[o][:-1]
            if len(i) == 2:
                ret_dict[i[0]] = i[1]
    elif f.name.endswith('.json'):
        text = findall('"[^"]+"\:\s*"[^"]+"', f.open(encoding='utf-8').read(), flags=MULTILINE)
        for i in text:
            key, value = findall('"[^"]+"', i, flags=MULTILINE)
            ret_dict[key[1:-1]] = value[1:-1]
    return ret_dict


def exists(dir: Path):
    count = 0
    son_dir: Path
    for i in dir.iterdir():
        if count > 0: return False
        son_dir = i
        count += 1
    lang: Path = None
    for i in son_dir.iterdir():
        if i.name == 'lang':
            lang = i
            break
    else:
        return False
    en = False
    zh = False
    file = [None, None]
    for i in lang.iterdir():
        if i.stem == 'zh_cn':
            zh = True
            file[1] = i
        if i.stem == 'en_us':
            en = True
            file[0] = i
    if not (zh and en): return False
    
    return (dir.name, son_dir.name, file[0], file[1])


if __name__ == '__main__':
    # stdout = TextIOWrapper(stdout.buffer, encoding='gbk')

    print('程序初始化'.encode('charmap'))
    mkdir('DictPacker')
    print('创建文件夹DictPacker'.encode('charmap'))

    folder = f'./projects/{argv[1]}/assets'
    version = argv[1]
    print(f'开始处理{version}'.encode('charmap'))
    main(folder, version)
    # main('./projects/1.12.2/assets', '1.12.2')
    # main('./projects/1.16/assets', '1.16')
    # main('./projects/1.16-fabric/assets', '1.16-fabric')
    # main('./projects/1.18/assets', '1.18')
    # main('./projects/1.18-fabric/assets', '1.18-fabric')

    savejson = []

    print('开始生成json'.encode('charmap'))
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

    print(f'已生成Dict-{version}.json'.encode('charmap'))