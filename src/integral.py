from collections import Counter, defaultdict
from json import dumps, loads
from pathlib import Path
from sqlite3 import connect

OUTPUT = Path('DictPacker')
VERSION_BIAS_RANGE = 0.25


def parse_version(version: str) -> tuple[int, int, int]:
    base = version.split('-', 1)[0]
    parts = base.split('.')
    nums = []
    for part in parts[:3]:
        try:
            nums.append(int(part))
        except ValueError:
            nums.append(0)
    while len(nums) < 3:
        nums.append(0)
    return tuple(nums)


def build_version_scores(entries: list[dict]) -> tuple[dict[str, float], dict[str, int]]:
    versions = sorted({entry['version'] for entry in entries}, key=lambda item: (parse_version(item), item))
    base_versions = sorted({version.split('-', 1)[0] for version in versions}, key=parse_version)
    base_ranks = {base_version: index for index, base_version in enumerate(base_versions)}
    max_rank = max(len(base_versions) - 1, 1)

    version_weights = {}
    version_ranks = {}
    for version in versions:
        base_version = version.split('-', 1)[0]
        rank = base_ranks[base_version]
        version_ranks[version] = rank
        version_weights[version] = 1 + VERSION_BIAS_RANGE * rank / max_rank
    return version_weights, version_ranks


def rank_translations(rows: list[dict], version_weights: dict[str, float], version_ranks: dict[str, int]) -> list[str]:
    version_totals = Counter()
    translation_versions = defaultdict(Counter)

    for row in rows:
        version = row['version']
        trans_name = row['trans_name']
        version_totals[version] += 1
        translation_versions[trans_name][version] += 1

    # 每个版本只按“该译名在本版本中的占比”贡献分数，避免单一大版本靠模组数量碾压。
    def sort_key(trans_name: str):
        version_counts = translation_versions[trans_name]
        weighted_share = sum(
            version_weights[version] * count / version_totals[version]
            for version, count in version_counts.items()
        )
        coverage = len(version_counts)
        share = sum(count / version_totals[version] for version, count in version_counts.items())
        raw_count = sum(version_counts.values())
        newest_rank = max(version_ranks[version] for version in version_counts)
        return (-weighted_share, -coverage, -share, -raw_count, -newest_rank, trans_name)

    return sorted(translation_versions, key=sort_key)


def main():
    integral = []
    origin_rows = defaultdict(list)

    # 整合词典
    for path in OUTPUT.iterdir():
        if path.suffix != '.json':
            continue
        print(f'处理{path.name}中', end=' ')
        count = 0
        for row in loads(path.read_text(encoding='utf-8')):
            count += 1
            if len(row['origin_name']) > 50:
                continue
            if row['origin_name'] == '':
                continue
            integral.append(row)
            if row['origin_name'] != row['trans_name']:
                origin_rows[row['origin_name']].append(row)
        print(f'已处理{count}个词条')

    version_weights, version_ranks = build_version_scores(integral)
    integral_mini = {
        origin_name: rank_translations(rows, version_weights, version_ranks)
        for origin_name, rows in origin_rows.items()
    }

    print('开始生成整合文件')

    text = dumps(integral, ensure_ascii=False, indent=4)
    mini_text = dumps(integral_mini, ensure_ascii=False, separators=(',', ':'))

    # 保存词典json文件
    if text != '[]':
        Path('Dict.json').write_text(text, encoding='utf-8')
        print(f'已生成Dict-Integral.json，共有词条{len(integral)}个')
    if mini_text != '{}':
        Path('Dict-Mini.json').write_text(mini_text, encoding='utf-8')
        print(f'已生成Dict-Integral-Mini.json，共有词条{len(integral_mini)}个')

    # 生成并保存sqlite数据库
    dictdb = connect('Dict-Sqlite.db')
    cursor = dictdb.cursor()
    cursor.execute('DROP TABLE IF EXISTS dict')
    cursor.execute('''CREATE TABLE dict(
            ID INTEGER PRIMARY KEY    AUTOINCREMENT,
            ORIGIN_NAME     TEXT    NOT NULL,
            TRANS_NAME      TEXT    NOT NULL,
            MODID           TEXT    NOT NULL,
            KEY             TEXT    NOT NULL,
            VERSION         TEXT    NOT NULL,
            CURSEFORGE      TEXT    NOT NULL
        );''')
    for row in integral:
        cursor.execute(
            'INSERT INTO dict(ORIGIN_NAME,TRANS_NAME,MODID,KEY,VERSION,CURSEFORGE) VALUES (?,?,?,?,?,?);',
            (row['origin_name'], row['trans_name'], row['modid'], row['key'], row['version'], row['curseforge']),
        )
    cursor.execute('CREATE INDEX dict_index ON dict(origin_name)')
    dictdb.commit()
    dictdb.close()
    print('已生成sqlite数据库，表名为dict')


if __name__ == '__main__':
    main()
