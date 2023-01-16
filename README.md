## 关于本项目

这是 CFPA 团队 [Minecraft 模组简体中文翻译项目](https://github.com/CFPAOrg/Minecraft-Mod-Language-Package)的词典化整合，托管在 MC 百科的 [Minecraft 模组翻译参考词典](https://dict.mcmod.cn/) 使用本仓库的数据。

**词典每周五自动更新，未做版本改动校验，不保证每次更新均与上次更新存在差异。**

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
    "key": "block.cazfps_the_dead_sea.cart", // 所属模组Translation Key
    "version": "1.18", // 所属游戏版本
    "curseforge": "cazfps-the-dead-sea" // CurseForge ID
}
```
主要产生用途的便是`origin_name`和`trans_name`这两个键，而其它键主要为译者辅助参考所用，例如条目`Cart`在高版本主流译名为`车`，而在1.12.2版本主流译名为`马车`。

`Dict-Mini.json`主要文件结构则是字典，为了缩小体积，直接将英文原文作为键名，译文作为值，每个条目形如
```json
"Cart":["马车","车","货车","推车","敞篷大车"]
```
作为译名的值必定为一个列表，列表排序的方式为**该译名在词典中出现的次数**，例如在本案例中，`马车`在词典中出现了4次，`车`在词典中出现了2次，其余词汇均只出现了一次。

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

本项目演绎自 CFPA [Minecraft 模组简体中文翻译项目](https://github.com/CFPAOrg/Minecraft-Mod-Language-Package) ，原仓库归属 [CFPA 团队及其他译者](https://github.com/CFPAOrg/Minecraft-Mod-Language-Package/graphs/contributors) ，除词典化外未对任何内容进行修改，该作品采用 [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/) 授权。 

本项目代码部分采用 [MIT LICENSE](https://mit-license.org/) 进行许可。
