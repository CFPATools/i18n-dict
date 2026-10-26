## 关于本项目

这是 CFPA 团队[Minecraft 模组简体中文翻译项目](https://github.com/CFPAOrg/Minecraft-Mod-Language-Package)的**非官方**词典化整合，托管在 MC 百科的[Minecraft 模组翻译参考词典](https://dict.mcmod.cn/)使用本仓库的数据。

**词典每周五自动更新，未做版本改动校验，不保证每次更新均与上次更新存在差异。**

## 数据来源与支持的文件

本仓库的 GitHub Actions workflow 会在运行时 checkout 最新的上游仓库 `CFPAOrg/Minecraft-Mod-Language-Package`。词典脚本读取 workflow 工作目录中的 `./Minecraft-Mod-Language-Package`。

每次发布的所有版本使用同一个上游 Git 修订，修订号写入 Release 描述。版本列表从配置中的 `base.version`（或旧配置的 `targetVersion`）和实际数据目录自动发现，新增 MC 版本或加载器无需修改 workflow；同目录中的辅助 JSON 不会被当成版本。数据目录有翻译但尚无独立配置的版本，会复用相同 MC 基础版本的文本规则；没有基础配置时使用默认的双语资源规则，这些版本不会自行继承其他版本的内容。

词典支持 `projects/assets/<mod>/<version>/<namespace>` 和旧的 `projects/<version>/assets/<mod>/<namespace>` 两种布局。按照上游 `fallbackVersions` 的顺序，为每个模组选用第一个可用版本；因此版本词典也包含上游明确允许回退使用的翻译。不同模组共享 namespace 时，各自的词条和来源都会保留。缺少英文的键会尝试使用同一 namespace 内无冲突的英文原文。

每次成功发布后，workflow 自动提交 `.github/release-state.json`，记录发布时间、上游修订和版本列表，同时保持仓库活动，避免公开仓库长期没有提交时定时任务被停用。若定时任务已停用，可运行 `gh workflow enable dict-packer.yml` 恢复，再用 `gh workflow run dict-packer.yml` 补发。

除传统的 `lang/en_us|zh_cn.{lang,json}` 外，当前词典还会处理：
- `packer-policy.json` 的 `direct`、`indirect`、`composition`、`singleton`、`modifyOnly`
- `local-config.json` 的路径和 domain 规则
- 非根 `lang` 路径、根目录 locale 文件
- `.local`、`.hl` 等键值文本资源
- JSON 中的嵌套对象、数组等复杂结构
- `.lang` 的 `#PARSE_ESCAPES`、续行与注释语义

完整词典、小词典和 SQLite 都保留长原文，原文超过 50 字符的指南、说明等内容也会收录。没有英文与中文对应关系的资源不会凭空生成翻译。

## Release文件介绍

### 本仓库的Release页面会每周放出以下文件：

```
Dict.json
Dict-Mini.json
Dict-Sqlite.db
```

其中：
- `Dict.json`即为 [MC百科模组词典](https://dict.mcmod.cn/) 的数据来源。
- `Dict-Mini.json`将`Dict.json`中的数据清洗、筛选，压缩为小词典文件， [MC模组翻译小帮手](https://github.com/CFPATools/Minecraft-Mods-Translator) 使用本文件作为实时的翻译词典功能数据源。
- `Dict-Sqlite.db`将`Dict.json`的全文内容存储在`dict`表中，以备有兴趣的开发者使用。

### 文件结构

`Dict.json`主要文件结构是一个数组，其中存储着词典条目各项内容，条目数据形如
```json5
{
    "origin_name": "Cart", // 英文原文
    "trans_name": "车", // 中文译文
    "modid": "cazfps_the_dead_sea", // 模组ID
    "key": "block.cazfps_the_dead_sea.cart", // 传统语言文件里通常是 Translation Key；复杂资源里可能是“目标路径#结构路径”
    "version": "1.18", // 所属游戏版本
    "curseforge": "cazfps-the-dead-sea" // CurseForge ID
}
```
主要产生用途的便是`origin_name`和`trans_name`这两个键，而其它键主要为译者辅助参考所用，例如条目`Cart`在高版本主流译名为`车`，而在1.12.2版本主流译名为`马车`。

传统语言文件里的 `key` 通常仍然是模组原本的 Translation Key。

guide、journal、`.local`、`.hl`、根目录 locale JSON、以及包含嵌套结构的 JSON 资源，会把 `key` 写成 `目标路径#结构路径`，例如：
```json
"assets/mana-and-artifice/guide/zh_cn.json#Using  this Codex.sections[0].value"
```
这样可以直接看出条目来自哪个文件、哪个位置。

`Dict-Mini.json`主要文件结构则是字典，为了缩小体积，直接将英文原文作为键名，译文作为值，每个条目形如
```json
"Cart":["车","马车","货车","推车","敞篷大车"]
```
作为译名的值必定为一个列表，列表按下面的顺序排序：
- 先看该译名在各个游戏版本里的占比，避免某个版本因为模组更多而把结果带偏。
- 如果占比接近，再给较新的 MC 主版本一点权重。
- 还分不出来时，再看出现过多少个版本、总共出现了多少次等信息。

例如条目`Cart`中，`马车`在`1.12.2`里出现得更多，但`车`在较新的版本里更常见。这种情况下，`车`会排在前面。

*值得注意的是，就算是译名只有一个的条目，值依然是一个列表，取用时需要注意。*
```json
"TEST":["测试"]
```

`Dict-Sqlite.db`是将`Dict.json`打包为SQLite格式的产物，在数据库文件中，表名为`dict`，结构如下：
```sql
CREATE TABLE IF NOT EXISTS dict(
    ID INTEGER PRIMARY KEY    AUTOINCREMENT,
    ORIGIN_NAME     TEXT    NOT NULL,
    TRANS_NAME      TEXT    NOT NULL,
    MODID           TEXT    NOT NULL,
    KEY             TEXT    NOT NULL,
    VERSION         TEXT    NOT NULL,
    CURSEFORGE      TEXT    NOT NULL
);
```
数据库字段名遵循`Dict.json`的键名结构，数据格式全为TEXT。

其中，在建立SQLite数据库时，特意将`ORIGIN_NAME`字段设定为索引字段。若在查询时约束条件为该字段，则查询速度可提升10~200倍。查询命令形如
```sql
SELECT trans_name FROM dict WHERE origin_name = `Cart`
```

## 版权归属

本项目由第三方演绎自 CFPA [Minecraft 模组简体中文翻译项目](https://github.com/CFPAOrg/Minecraft-Mod-Language-Package)，原仓库归属 [CFPA 团队及其他译者](https://github.com/CFPAOrg/Minecraft-Mod-Language-Package/graphs/contributors)，除词典化外未对任何内容进行修改，该作品采用 [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/) 授权，故而在 Release 与 Action 页面分发的词典文件（Dict*）也采用 CC BY-NC-SA 4.0 授权。

本项目代码部分采用 [MIT LICENSE](https://mit-license.org/) 进行许可。
