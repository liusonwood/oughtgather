
import os
import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock

# Add project root to path so we can import src.config etc.
sys.path.append(os.getcwd())

# ---------------------------------------------------------------------------
# Stub out third-party packages that may not be installed in the CI
# environment running this lightweight script.  We only need to inspect class
# attributes (required_secrets), so real implementations are not needed.
# ---------------------------------------------------------------------------
_THIRD_PARTY_STUBS = [
    "feedparser",
    "trafilatura",
    "requests",
    "bs4",
    "bs4.element",
    "PIL",
    "PIL.Image",
    "openai",
    "ebooklib",
    "ebooklib.epub",
    "lxml",
    "lxml.etree",
    "webdav3",
    "webdav3.client",
    "webdav3.exceptions",
]

for _mod in _THIRD_PARTY_STUBS:
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()

def get_all_required_secrets():
    secrets = {}
    fetchers_dir = Path('src/fetchers')
    
    for file in fetchers_dir.glob('*.py'):
        if file.name == '__init__.py' or file.name == 'base.py':
            continue
            
        module_name = file.stem
        spec = importlib.util.spec_from_file_location(module_name, file)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        # Look for classes that have required_secrets
        for name in dir(module):
            obj = getattr(module, name)
            if hasattr(obj, 'required_secrets') and isinstance(obj.required_secrets, dict):
                secrets.update(obj.required_secrets)
                
    return secrets

def generate_markdown_table(secrets):
    table = "| Secret / 环境变量 | 说明 |\n| --- | --- |\n"
    # SMTP/Kindle/WebDAV are hardcoded, add them
    base_secrets = {
        "SMTP_HOST": "发件邮箱 SMTP 服务器地址，如 `smtp.gmail.com`",
        "SMTP_PORT": "发件邮箱 SMTP 端口；`465` 使用 SSL，`587` 使用 STARTTLS",
        "SMTP_USERNAME": "发件邮箱账号",
        "SMTP_PASSWORD": "发件邮箱密码或应用授权码",
        "KINDLE_EMAIL": "Kindle 接收邮箱（`@kindle.com`）",
        "WEBDAV_ENABLED": "设置为 `true` 以启用 WebDAV 上传",
        "WEBDAV_URL": "WebDAV 服务器地址",
        "WEBDAV_USERNAME": "WebDAV 用户名",
        "WEBDAV_PASSWORD": "WebDAV 密码",
        "WEBDAV_REMOTE_PATH": "远程存储路径，默认 `/`",
        "CONFIG_JSON": "完整的 `config.json` 字符串；优先级高于项目根目录的 `config.json` 文件。推荐在 GitHub Actions 中使用，可避免将私有订阅源写入仓库"
    }
    
    for key, desc in base_secrets.items():
        table += f"| `{key}` | {desc} |\n"
        
    for key, desc in secrets.items():
        clean_key = key.replace('*', '')
        table += f"| `{clean_key}` | {desc} |\n"
        
    return table

def update_readme(table_content):
    readme_path = 'README.md'
    with open(readme_path, 'r', encoding='utf-8') as f:
        content = f.read()
        
    # The table section: starts with | Secret / 环境变量 | 说明 |
    # and ends before the next section (which starts with a new heading like ## or ---)
    # or the text that follows the table.
    # A robust way is to look for the header and then everything that looks like a table row until a line not starting with |
    
    import re
    
    # Define the pattern to match the table
    # It starts with the header and continues with rows until a non-table line
    # The new section starts after '## Secrets 配置' and some text
    
    # The regex matches the header, rows, AND any immediately following blank lines/whitespace
    # until the next content starts.
    table_pattern = r'\| Secret / 环境变量 \| 说明 \|\n\| --- \| --- \|\n(?:\|.*?\|\n)+\s*'

    # Replace the existing table with the new one, followed by two newlines.
    # The regex already consumed the trailing whitespace/blank lines from the old table.
    formatted_table = table_content.rstrip('\n') + '\n\n\n'

    new_content = re.sub(table_pattern, formatted_table, content, flags=re.MULTILINE)
    
    with open(readme_path, 'w', encoding='utf-8') as f:
        f.write(new_content)

if __name__ == '__main__':
    secrets = get_all_required_secrets()
    table = generate_markdown_table(secrets)
    update_readme(table)
