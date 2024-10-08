from pathlib import Path
from json import loads, dumps
from sqlite3 import connect

output = Path('DictPacker')

integral = []
integral_mini = {}

# 整合词典
for i in output.iterdir():
    if i.suffix == '.json':
        print(f'处理{i.name}中', end=' ')
        count = 0
        for i in loads(open(i, encoding='utf-8').read()):
            count += 1
            if len(i['origin_name']) > 50: continue
            if i['origin_name'] == '': continue
            integral.append(i)
            if i['origin_name'] != i['trans_name']:
                if not i['origin_name'] in integral_mini.keys():
                    integral_mini[i['origin_name']] = []
                integral_mini[i['origin_name']].append(i['trans_name'])
        print(f'已处理{count}个词条')

for i in integral_mini.keys():
    nlist: list = integral_mini[i]
    nset = set(nlist)
    integral_mini[i] = sorted(nset, key=lambda x: nlist.count(x), reverse=True)

print('开始生成整合文件')

text = dumps(integral, ensure_ascii=False, indent=4)
mini_text = dumps(integral_mini, ensure_ascii=False, separators=(',',':'))

# 保存词典json文件
if text != '[]':
    Path('Dict.json').write_text(text, encoding='utf-8')
    print(f'已生成Dict-Integral.json，共有词条{len(integral)}个')
if mini_text != '{}':
    Path('Dict-Mini.json').write_text(mini_text, encoding='utf-8')
    print(f'已生成Dict-Integral-Mini.json，共有词条{len(integral_mini)}个')

# 生成并保存sqlite数据库
dictdb = connect('Dict-Sqlite.db')
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
exec.execute('CREATE INDEX dict_index ON dict(origin_name)')
dictdb.commit()
dictdb.close()
print('已生成sqlite数据库，表名为dict')
