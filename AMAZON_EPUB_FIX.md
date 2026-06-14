# Amazon Send to Kindle EPUB 兼容性修复说明

## 问题描述

生成的 EPUB 文件无法被 Amazon Send to Kindle 服务正常发送和接收。

## 修复内容

### 1. 完整的元数据（`_set_metadata` 方法）

Amazon Send to Kindle 要求以下必须的元数据字段：

- **dc:title**: 书籍标题 ✅
- **dc:creator**: 作者 ✅
- **dc:language**: 语言（zh-CN） ✅
- **dc:publisher**: 出版商（新增）✅
- **dc:date**: 出版日期（新增）✅

```python
def _set_metadata(self, book: epub.EpubBook):
    book.set_identifier('ought-gather-epub')
    book.set_title(self.config.title.get_plain_text())
    book.set_language('zh-CN')
    book.add_author('Ought Gather')
    
    # 新增：Amazon 要求的元数据
    book.add_metadata('DC', 'publisher', 'Ought Gather')
    from datetime import datetime
    now = datetime.now().strftime('%Y-%m-%d')
    book.add_metadata('DC', 'date', now)
```

### 2. NCX 和 Nav 导航文件（`generate` 方法）

Amazon 要求同时提供：

- **toc.ncx**: EPUB 2 兼容的导航文件
- **nav.xhtml**: EPUB 3 标准的导航文件

```python
# 添加导航文件（必须在保存之前）
book.add_item(epub.EpubNcx())  # EPUB 2 兼容
book.add_item(epub.EpubNav())  # EPUB 3 标准
```

### 3. EPUB 版本

ebooklib 默认生成 **EPUB 3.0** 格式，这符合 Amazon 的要求。

### 4. 封面处理

使用 `book.set_cover()` 方法添加封面，这会自动生成符合标准的封面页面和图片。

### 5. Spine 阅读顺序

修改了 `_add_chapters` 方法，确保 spine 顺序正确：

```python
# 阅读顺序：封面 → 目录 → 正文章节
spine = ['cover']  # 先添加封面
# 添加目录章节
spine.append(toc_chapter)  # 或 'nav'
# 添加所有章节
for chapter in chapters:
    spine.append(chapter)
book.spine = spine
```

## 验证结果

使用 `epub_validator.py` 验证 EPUB 文件：

```bash
python epub_validator.py output/Daily\ News\ 2026-06-14.epub
```

验证结果：
- ✅ mimetype: application/epub+zip
- ✅ EPUB 版本: 3.0
- ✅ 元数据完整（title, creator, language, publisher, date）
- ✅ NCX 导航文件存在
- ✅ nav.xhtml 导航文件存在
- ✅ 封面存在
- ✅ 文件大小: 0.43 MB（远低于 50MB 限制）

## 测试方法

### 1. 运行测试脚本

```bash
python test_epub_amazon.py
```

该脚本会：
- 创建测试配置
- 生成包含 2 篇测试文章的 EPUB
- 验证文件生成成功
- 输出文件路径

### 2. 验证 EPUB 结构

```bash
python epub_validator.py <epub_path>
```

### 3. 使用 Calibre 验证（推荐）

```bash
# 使用 Calibre 查看
ebook-viewer output/Daily\ News\ 2026-06-14.epub

# 使用 Calibre 转换（确保最大兼容性）
ebook-convert output/Daily\ News\ 2026-06-14.epub output/converted.epub \
  --pretty-print --epub-version 3
```

### 4. 上传到 Amazon Send to Kindle

1. 访问 https://sendtokindle.amazon.com/
2. 上传 EPUB 文件
3. 检查是否成功发送到 Kindle 设备

## 其他注意事项

### 文件大小限制
- Amazon 限制：**50MB**
- 图片限制：每张 ≤ 500KB，总计 ≤ 50MB
- 当前实现已包含图片压缩（ImageProcessor）

### 图片处理
确保使用 `ImageProcessor` 处理所有图片：
- 自动下载并压缩到 ≤ 500KB
- 支持 JPG/PNG 格式
- 替换文章中的图片链接为本地路径

### 字符编码
所有 HTML 文件使用 UTF-8 编码，确保中文正常显示。

## 故障排查

### 如果仍然无法上传

1. **使用 Calibre 转换**：
   ```bash
   ebook-convert input.epub output.epub --epub-version 3
   ```

2. **检查 Amazon 收件人邮箱**：
   - 确保在 Kindle 设备的"已认可的发件人电子邮箱列表"中添加了发送邮箱

3. **检查文件大小**：
   - 使用 `epub_validator.py` 检查是否超过 50MB

4. **检查网络连接**：
   - 确保 SMTP 配置正确
   - 确保可以访问 Amazon Send to Kindle 服务

## 相关文件

- `src/epub/generator.py`: EPUB 生成器（已修改）
- `epub_validator.py`: EPUB 验证脚本（新增）
- `test_epub_amazon.py`: 测试脚本（新增）

## 参考资料

- [Amazon Kindle Publishing Guidelines](https://kdp.amazon.com/en_US/help/topic/G202131170)
- [EPUB 3.0 Specification](https://www.w3.org/TR/epub-33/)
- [ebooklib Documentation](https://ebooklib.readthedocs.io/)
