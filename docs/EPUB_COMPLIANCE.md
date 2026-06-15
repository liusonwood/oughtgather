# EPUB Compliance Guide

本文档详细记录了生成符合EPUB规范的电子书文件的经验教训，特别是使用ebooklib库时遇到的常见问题和解决方案。

## 目录

- [EPUB版本与规范](#epub版本与规范)
- [常见错误与解决方案](#常见错误与解决方案)
- [验证工具](#验证工具)
- [最佳实践](#最佳实践)

---

## EPUB版本与规范

### EPUB 2.0 vs EPUB 3.0

| 特性 | EPUB 2.0 | EPUB 3.0 |
|------|---------|---------|
| 导航系统 | NCX文件（必需） | NCX + Nav Document（nav必需） |
| 元数据格式 | Dublin Core | Dublin Core + 新属性 |
| HTML版本 | XHTML 1.1 | HTML5/XHTML 1.1 |
| 文件目录 | 可选OEBPS/OPS | 推荐 `EPUB/` 目录 |
| 验证工具 | EPUBCheck 2.0规则 | EPUBCheck 3.3规则（默认） |

### ebooklib的限制

**重要发现**：ebooklib 0.20版本**无法生成EPUB 2.0格式文件**。

```python
# ❌ 以下设置无效
book.version = '2.0'  # ebooklib忽略此设置

# ✅ 实际生成的OPF文件
# <package version="3.0">  # 硬编码为3.0
```

**原因分析**：
- `EpubWriter._write_opf()` 方法中硬编码了 `"version": "3.0"`
- 无法通过设置 `book.version` 属性来改变版本号
- 必须接受EPUB 3.0格式并满足其规范要求

---

## 常见错误与解决方案

### 错误1: RSC-026 - URL泄露到容器外部

**错误信息**：
```
ERROR(RSC-026): URL "/content.opf" leaks outside the container
(it is not a valid-relative-ocf-URL-with-fragment string)
```

**问题描述**：
生成的EPUB文件中所有路径都以 `/` 开头（绝对路径），违反OCF规范。

**错误示例**：
```python
# ❌ 错误的设置
book.FOLDER_NAME = ''
book.DEFAULT_PUBLICATION_DIR = ''

# 生成的文件结构（错误）
# - /content.opf       <- 绝对路径！
# - /cover.jpg
# - /cover.xhtml
# - /chapter_0.xhtml
```

**根本原因**：
ebooklib内部使用字符串拼接 `"FOLDER_NAME/{file_name}"`。当 `FOLDER_NAME=''` 时：
```python
# 内部拼接逻辑
path = f"{FOLDER_NAME}/{file_name}"
# 结果: "" + "/" + "content.opf" = "/content.opf"  <- 绝对路径
```

**解决方案**：
```python
# ✅ 正确的做法 - 保留默认值
# 不设置 FOLDER_NAME，使用默认值 'EPUB'

# 生成的文件结构（正确）
# - EPUB/content.opf   <- 相对路径
# - EPUB/cover.jpg
# - EPUB/cover.xhtml
# - EPUB/chapter_0.xhtml
```

**验证方法**：
```bash
unzip -l your_epub.epub | grep "^.*EPUB/"
# 应看到所有文件都在 EPUB/ 目录下
```

---

### 错误2: RSC-005 - 缺少nav属性声明

**错误信息**：
```
ERROR(RSC-005): Exactly one manifest item must declare the "nav" property
(number of "nav" items: 0)
```

**问题描述**：
EPUB 3.0规范要求manifest中必须有**且仅有**一个item声明 `properties="nav"`。

**错误代码**：
```python
# ❌ 只添加NCX，缺少nav document
book.add_item(epub.EpubNcx())

# 生成的manifest（错误）
# <item href="toc.ncx" id="ncx" media-type="application/x-dtbncx+xml"/>
# 缺少 nav 属性的声明
```

**解决方案**：
```python
# ✅ 同时添加NCX和Nav Document
book.add_item(epub.EpubNcx())     # EPUB 2.0兼容导航
book.add_item(epub.EpubNav())     # EPUB 3.0必需导航

# 生成的manifest（正确）
# <item href="nav.xhtml" id="nav" media-type="application/xhtml+xml" properties="nav"/>
# <item href="toc.ncx" id="ncx" media-type="application/x-dtbncx+xml"/>
```

**为什么需要两者**：
- `EpubNcx()`: 提供传统的NCX导航，兼容旧设备和EPUB 2.0阅读器
- `EpubNav()`: EPUB 3.0新增的导航文档，提供更丰富的导航功能和语义结构

---

### 错误3: CSS语法错误 - Python f-string中的大括号

**错误信息**：
```python
NameError: name 'margin' is not defined
```

**问题描述**：
在Python f-string中编写CSS代码时，CSS的大括号 `{}` 被Python解析为表达式占位符。

**错误代码**：
```python
# ❌ CSS中的大括号被Python解析为表达式
cover_html = f"""<!DOCTYPE html>
<html>
<head>
    <style>
        body { margin: 0; padding: 0; }  <- Python尝试执行 "margin"
        img { max-width: 100%; }        <- Python尝试执行 "max-width"
    </style>
</head>
<body>...</body>
</html>"""
```

**解决方案**：
```python
# ✅ 使用双大括号 {{}} 转义
cover_html = f"""<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ margin: 0; padding: 0; }}  <- 字面意义的大括号
        img {{ max-width: 100%; }}
    </style>
</head>
<body>...</body>
</html>"""
```

**记忆技巧**：
- Python f-string: `{expression}` 用于表达式
- CSS语法: `{{property}}` 用于字面大括号
- 双写转义规则适用于所有f-string中的JSON、CSS等需要大括号的文本

---

### 错误4: RSC-016 - 封面文件过早结束

**错误信息**：
```
FATAL(RSC-016): cover.xhtml(-1,-1): Fatal Error while parsing file: Premature end of file.
```

**问题描述**：
生成的 `cover.xhtml` 文件为空（0字节），或内容未正确写入。

**错误示例**：
```bash
unzip -l your_epub.epub
# Length      Date    Time    Name
# ---------  ---------- -----   ----
#       0  06-15-2026 22:09   /cover.xhtml  <- 0字节！
```

**可能原因**：
1. SVG封装方式在某些情况下未正确写入内容
2. `EpubHtml.content` 属性未正确设置
3. 使用了过于复杂的HTML结构导致解析失败

**解决方案**：
```python
# ❌ 复杂的SVG封装（可能失败）
cover_html = """<svg xmlns="http://www.w3.org/2000/svg">
    <image xlink:href="cover.jpg" width="1440" height="1920"/>
</svg>"""

# ✅ 简单可靠的HTML结构
cover_html = f"""<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
    <title>Cover</title>
    <style type="text/css">
        body {{ margin: 0; padding: 0; text-align: center; }}
        img {{ max-width: 100%; height: auto; }}
    </style>
</head>
<body>
    <img src="{cover_filename}" alt="Cover"/>
</body>
</html>"""

cover_page = epub.EpubHtml(title='Cover', file_name='cover.xhtml', uid='cover')
cover_page.content = cover_html  # 确保设置content属性
book.add_item(cover_page)
```

---

### 错误5: EPUB 3.0属性误用

**问题描述**：
EPUB 3.0引入了 `properties` 属性，但ebooklib在某些版本中处理不当。

**错误示例**：
```python
# ❌ EPUB 3.0特有属性（可能不兼容旧设备）
cover_item.properties = ['cover-image']

# 如果目标是最大化兼容性，应避免使用EPUB 3.0特有属性
```

**解决方案**：
```python
# ✅ 使用标准方式添加封面（兼容性好）
cover_item = epub.EpubItem(
    uid='cover-img',
    file_name=cover_filename,
    media_type='image/jpeg',
    content=cover_data
)
# 不设置 properties 属性，让ebooklib自动处理

# 在guide中声明封面（EPUB 2.0兼容方式）
book.guide = [
    {'href': 'cover.xhtml', 'title': 'Cover', 'type': 'cover'}
]
```

---

## 验证工具

### EPUBCheck

**官方工具**：W3C EPUBCheck是验证EPUB文件是否符合规范的权威工具。

#### 安装方法

1. **下载EPUBCheck**：
   ```bash
   # 从官方GitHub下载最新版本
   wget https://github.com/w3c/epubcheck/releases/download/v5.3.0/epubcheck-5.3.0.zip
   unzip epubcheck-5.3.0.zip
   ```

2. **确保Java环境**：
   ```bash
   java -version  # 需要Java 8或更高版本
   ```

#### 使用方法

```bash
# 基本验证（默认使用EPUB 3.3规则）
java -jar epubcheck.jar your_epub.epub

# 详细输出
java -jar epubcheck.jar your_epub.epub --mode exp -v 3.0

# 输出JSON报告
java -jar epubcheck.jar your_epub.epub --json report.json

# 输出XML报告
java -jar epubcheck.jar your_epub.epub --out report.xml
```

#### 验证结果解读

```
Messages: 0 fatals / 0 errors / 0 warnings / 0 infos
EPUBCheck completed

✓ 上述输出表示完全符合规范
```

```
Messages: 1 fatal / 2 errors / 0 warnings / 0 infos
EPUBCheck completed

✗ 存在致命错误或错误，必须修复
```

### 常见EPUBCheck错误代码

| 错误代码 | 说明 | 严重程度 |
|---------|------|---------|
| RSC-005 | OPF manifest缺少必需属性 | Error |
| RSC-016 | XHTML文件解析失败 | Fatal |
| RSC-026 | URL路径泄露到容器外部 | Error |
| OPF-031 | guide元素引用未声明的文件 | Error |
| RSC-007 | 引用的资源未找到 | Error |

---

## 最佳实践

### 1. 文件结构规范

```
your_epub.epub (ZIP压缩包)
├── mimetype                     (必需，第1个文件，不压缩)
├── META-INF/
│   └── container.xml           (必需，指向OPF文件)
└── EPUB/                        (推荐目录名)
    ├── content.opf              (必需，元数据和manifest)
    ├── toc.ncx                  (EPUB 2.0导航)
    ├── nav.xhtml                (EPUB 3.0导航，必需)
    ├── cover.jpg                (封面图片)
    ├── cover.xhtml              (封面页面)
    ├── chapter_0.xhtml          (内容文件)
    ├── chapter_1.xhtml
    ├── style/
    │   └── default.css          (样式文件)
    └── images/
        ├── image1.jpg           (图片资源)
        └── image2.jpg
```

### 2. ebooklib最佳配置

```python
from ebooklib import epub

# ✅ 推荐配置
book = epub.EpubBook()

# 元数据设置
book.set_identifier(str(uuid.uuid4()))
book.set_title('Book Title')
book.set_language('zh')
book.add_author('Author Name')

# 导航文件（EPUB 3.0必需）
book.add_item(epub.EpubNcx())  # NCX导航
book.add_item(epub.EpubNav())  # Nav Document（必需）

# Guide元素（兼容性）
book.guide = [
    {'href': 'cover.xhtml', 'title': 'Cover', 'type': 'cover'}
]

# 不修改FOLDER_NAME，保留默认 'EPUB'
# book.FOLDER_NAME = 'EPUB'  # 默认值

# 保存
epub.write_epub('output.epub', book, {})
```

### 3. XHTML文件模板

```python
# ✅ EPUB 3.0兼容的XHTML模板
def generate_xhtml_content(title, body_content):
    safe_title = html.escape(title)
    
    return f"""<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="zh">
<head>
    <title>{safe_title}</title>
    <link rel="stylesheet" type="text/css" href="style/default.css"/>
</head>
<body>
    <h1>{safe_title}</h1>
    <div class='content'>
        {body_content}
    </div>
</body>
</html>"""
```

### 4. CSS样式模板

```python
# ✅ f-string中的CSS编写
css_content = """
body {{
    font-family: serif;
    line-height: 1.6;
    margin: 1em;
}}
h1 {{
    font-size: 1.5em;
    color: #333;
}}
.content {{
    text-align: justify;
}}
img {{
    max-width: 100%;
    height: auto;
}}
"""
```

### 5. 图片处理最佳实践

```python
# ✅ 图片添加到EPUB的正确方式
def add_image_to_epub(book, image_url, article_url, chapter_content):
    # 下载和处理图片
    filename, img_data = download_and_process_image(image_url, article_url)
    
    # 检查是否已添加（避免重复）
    image_uid = f"image_{filename}"
    if not any(item.id == image_uid for item in book.items):
        # 添加图片item
        epub_image = epub.EpubItem(
            uid=image_uid,
            file_name=f"images/{filename}",
            media_type="image/jpeg",
            content=img_data
        )
        book.add_item(epub_image)
    
    # 更新HTML中的图片引用（相对路径）
    # <img src="images/filename.jpg"/>
```

---

## 问题排查流程

当EPUBCheck报告错误时，按以下流程排查：

### Step 1: 检查文件结构
```bash
unzip -l your_epub.epub
```
- 确认所有文件都在 `EPUB/` 目录下（无 `/` 前缀的绝对路径）
- 确认 `mimetype` 是第一个文件
- 确认文件大小合理（无0字节文件）

### Step 2: 检查OPF文件
```bash
unzip -p your_epub.epub EPUB/content.opf
```
- 确认 `version="3.0"`（无法改为2.0）
- 确认manifest中有 `properties="nav"` 的item
- 确认所有XHTML文件都在manifest中声明

### Step 3: 检查XHTML文件
```bash
unzip -p your_epub.epub EPUB/cover.xhtml | head -20
```
- 确认有正确的DOCTYPE声明
- 确认有完整的 `<html>` 结构
- 确认内容不为空

### Step 4: 使用EPUBCheck详细输出
```bash
java -jar epubcheck.jar your_epub.epub --json report.json
cat report.json
```

---

## 参考资源

- [EPUB 3.3 规范](https://www.w3.org/TR/epub-33/) - W3C官方规范文档
- [EPUBCheck官方文档](https://github.com/w3c/epubcheck) - 验证工具文档
- [ebooklib GitHub](https://github.com/aerkalov/ebooklib) - Python库源码
- [EPUB最佳实践](https://github.com/IDPF/epub3-samples) - 官方示例文件

---

## 总结

### 关键要点

1. ✅ **接受EPUB 3.0格式** - ebooklib无法生成EPUB 2.0
2. ✅ **使用标准目录结构** - 保留 `FOLDER_NAME='EPUB'` 默认值
3. ✅ **添加nav document** - EPUB 3.0必需，用 `EpubNav()`
4. ✅ **转义CSS大括号** - 在f-string中使用 `{{}}`
5. ✅ **简化HTML结构** - 避免复杂的SVG封装
6. ✅ **验证EPUB文件** - 使用EPUBCheck确保合规

### 验证成功的标志

```bash
$ java -jar epubcheck.jar output.epub
Validating using EPUB version 3.3 rules.
No errors or warnings detected.
Messages: 0 fatals / 0 errors / 0 warnings / 0 infos
EPUBCheck completed
```

看到上述输出，说明EPUB文件完全符合规范，可以安全地发送到Kindle和其他电子阅读器。