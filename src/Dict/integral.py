from pathlib import Path
from json import loads, dumps
from sqlite3 import connect


output = Path('DictPacker')

integral = []
integral_mini = {}

# 整合词典
for i in output.iterdir():
    if i.suffix == '.json':
        print(f'处理{i.name}中'.encode('gb18030'), end=' ')
        count = 0
        for i in loads(open(i, encoding='utf-8').read()):
            count += 1
            if len(i['origin_name']) > 50: continue
            if i['origin_name'] == '': continue
            integral.append(i)
            integral_mini[i['origin_name']] = i['trans_name']
        print(f'已处理{count}个词条'.encode('gb18030'))

print('开始生成整合文件'.encode('gb18030'))

text = dumps(integral, ensure_ascii=False, indent=4)
mini_text = dumps(integral_mini, ensure_ascii=False, separators=(',',':'))

# 保存词典json文件
if text != '[]':
    Path('DictPacker/Dict-Integral.json').write_text(text, encoding='utf-8')
    print(f'已生成Dict-Integral.json，共有词条{len(integral)}个'.encode('gb18030'))
if mini_text != '{}':
    Path('DictPacker/Dict-Integral-Mini.json').write_text(mini_text, encoding='utf-8')
    print(f'已生成Dict-Integral-Mini.json，共有词条{len(integral_mini)}个'.encode('gb18030'))

# 生成并保存sqlite数据库
dictdb = connect('DictPacker/Dict-Sqlite.db')
exec = dictdb.cursor()
exec.execute('''CREATE TABLE IF NOT EXISTS dict(
        ID INTEGER PRIMARY KEY    AUTOINCREMENT,
        ORIGIN_NAME     TEXT    NOT NULL,
        TRANS_NAME      TEXT    NOT NULL,
        MODID           TEXT    NOT NULL,
        KEY             TEXT    NOT NULL,
        VERSION         TEXT    NOT NULL,
        CURSEFORGE      TEXT    NOT NULL
    );''')
for i in integral:
    o = i['origin_name']
    t = i['trans_name']
    m = i['modid']
    k = i['key']
    v = i['version']
    c = i['curseforge']
    exec.execute('INSERT INTO dict(ORIGIN_NAME,TRANS_NAME,MODID,KEY,VERSION,CURSEFORGE) VALUES (?,?,?,?,?,?);', (o,t,m,k,v,c))
dictdb.commit()
dictdb.close()
print('已生成sqlite数据库，表名为dict'.encode('gb18030'))