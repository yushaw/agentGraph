# uploads/ 目录说明

这个目录用于存放要上传给 agent 的文件。

## 快速开始

### 1. 将文件放到这个目录

```bash
# 复制文件到 uploads/
cp /path/to/your/file.pdf uploads/
cp /path/to/image.png uploads/
```

### 2. 在对话中使用 #filename

启动 agent：
```bash
python main.py
```

在对话中引用文件：
```
You> 分析这张图 #test_image.png
You> 处理这个文档 #1.pdf @pdf
You> 帮我看看 #test.txt 里面写了什么
```

## 当前文件

可用的测试文件：
- `test_image.png` - 100x100 红色图片（284 B）
- `test.txt` - 测试文本文件（116 B）
- `1.pdf` - PDF 文档（858 KB）

## 示例对话

### 示例 1：图片分析
```
You> 这张图是什么颜色 #test_image.png

[已上传 1 个文件]

Agent> 这是一张纯红色的图片，尺寸为 100x100 像素。
```

### 示例 2：文本文件
```
You> 读取 #test.txt 的内容

[已上传 1 个文件]

Agent> 我已经读取了文件内容：
这是一个测试文本文件。

内容：
- 第一行
- 第二行
- 第三行

用于测试文件上传功能。
```

### 示例 3：PDF + Skill
```
You> 帮我分析 #1.pdf @pdf

[已上传 1 个文件]
[已加载技能: pdf]

Agent> 我已经收到 PDF 文档。让我先读取 PDF skill 的文档...
(Agent 会使用 @pdf skill 中的工具处理 PDF)
```

## 注意事项

- 文件会被复制到工作区的 `uploads/` 目录
- 图片会自动触发 vision 模型
- 小文本文件（<10KB）内容会直接注入到消息
- 大文件会保存到工作区，agent 使用工具处理
- 不存在的文件会被静默跳过
- 太大的文件会报错跳过

## 清理

使用完成后可以手动清理：
```bash
rm uploads/*.pdf uploads/*.png uploads/*.txt
```

或保留测试文件供后续使用。
