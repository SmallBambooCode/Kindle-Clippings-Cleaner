# Kindle Clippings Cleaner

一个用于清理、去重、整理 Kindle `My Clippings.txt` 文件的 Python 脚本。

## ✨ 功能

- 自动分割并解析 `My Clippings.txt`
- 按书籍分组，去除重复的标注、笔记和书签
- 支持中英文标注去重
- 针对短文本标注，保留时间最后的条目
- 输出为 Markdown 格式，方便整理与备份
- 自动过滤空白标注（有时 Kindle 会生成空行的 highlight）

## 📦 安装

不需要额外依赖，只需 Python 3.6+：

```bash
git clone https://github.com/SmallBambooCode/Kindle-Clippings-Cleaner.git
cd kindle-clippings-cleaner
```



## 🚀 使用方法

默认输入文件是 `My Clippings.txt`，输出为 `Clipping_cleaned.md`：

```bash
python clean_clippings.py
```

或者手动指定输入和输出：

```bash
python clean_clippings.py My\ Clippings.txt cleaned.md
```

也可以直接在代码中修改路径后直接运行。

## 📂 输出示例

```
## 西方哲学史讲演录 (赵林)

在古希腊，哲学体现了一种生机盎然的智慧，虽然这种智慧带有一些童稚的旨趣，但是它却几乎涉及了人类思维所能关注到的一切深刻问题，而且是在一种没有前人的参照系统、从而也没有圭臬约束的情况下来思考这些问题的。因此，希腊哲学家们的哲学观点往往都带有清新通达的特点，表现了自由心灵对于宇宙、人生的思考和关怀。

一个生活在两百多年以前的康德，在今天就可以养活成千上万个把康德哲学研究得比康德本人还要清楚的康德哲学家；而那些关于《精神现象学》的解读文本，已经多得足以把任何一个敢于研究黑格尔哲学的人弄得晕头转向！

```

## 📝 注意

- 脚本目前支持中英文 Kindle 导出的 `My Clippings.txt`
- 短标注条目会通过时间戳判定，保留最新的一条。
- 原始文件不会修改，结果保存为新文件
- 我只在Kindle Paperwhite 5上进行过测试
