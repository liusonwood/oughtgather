
import os
import importlib.util
import sys
from pathlib import Path

# Add project root to path so we can import src.config etc.
sys.path.append(os.getcwd())

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
        lines = f.readlines()
        
    new_lines = []
    in_table_section = False
    table_replaced = False
    
    for line in lines:
        if line.startswith('## Secrets 配置'):
            new_lines.append(line)
            new_lines.append('\n')
            new_lines.append('在 GitHub 仓库的 `Settings -> Secrets and variables -> Actions` 中配置，本地开发时通过环境变量设置。\n\n')
            new_lines.append(table_content)
            in_table_section = True
            table_replaced = True
            continue
            
        if in_table_section:
            if line.startswith('|') or line.strip() == '':
                continue
            else:
                in_table_section = False
                new_lines.append(line)
        else:
            new_lines.append(line)
            
    with open(readme_path, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)

if __name__ == '__main__':
    secrets = get_all_required_secrets()
    table = generate_markdown_table(secrets)
    update_readme(table)
