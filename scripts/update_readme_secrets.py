
import os
import importlib.util
import sys
import re
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

    # Combine and sort
    all_secrets = {**base_secrets, **secrets}
    for key in sorted(all_secrets.keys()):
        desc = all_secrets[key]
        clean_key = key.replace('*', '')
        table += f"| `{clean_key}` | {desc} |\n"

    return table

def update_readme(table_content):
    readme_path = 'README.md'
    with open(readme_path, 'r', encoding='utf-8') as f:
        content = f.read()
        
    table_pattern = r'\| Secret / 环境变量 \| 说明 \|\n\| --- \| --- \|\n(?:\|.*?\|\n)+\s*'
    formatted_table = table_content.rstrip('\n') + '\n\n\n'

    new_content = re.sub(table_pattern, formatted_table, content, flags=re.MULTILINE)
    
    with open(readme_path, 'w', encoding='utf-8') as f:
        f.write(new_content)

def update_workflow(secrets):
    workflow_path = '.github/workflows/daily-gather.yml'
    with open(workflow_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 构造新的 env 块
    new_env = "        env:\n"
    new_env += "          # 时区设置：使用北京时间 UTC+8\n"
    new_env += "          TZ: Asia/Shanghai\n\n"
    new_env += "          # SMTP 配置（必需）\n"
    new_env += "          SMTP_HOST: ${{ secrets.SMTP_HOST }}\n"
    new_env += "          SMTP_PORT: ${{ secrets.SMTP_PORT }}\n"
    new_env += "          SMTP_USERNAME: ${{ secrets.SMTP_USERNAME }}\n"
    new_env += "          SMTP_PASSWORD: ${{ secrets.SMTP_PASSWORD }}\n"
    new_env += "          KINDLE_EMAIL: ${{ secrets.KINDLE_EMAIL }}\n\n"
    new_env += "          # 自动注入 Secrets\n"
    
    # Sort keys
    for key in sorted(secrets.keys()):
        new_env += f"          {key}: ${{{{ secrets.{key} }}}}\n"
    
    # 正则替换 env 块
    # 匹配 "Run Ought Gather" 步骤下的 env 块
    env_pattern = r'name: Run Ought Gather\n\s*env:[\s\S]*?run: \|'
    
    new_content = re.sub(env_pattern, f"name: Run Ought Gather\n{new_env}\n        run: |", content)
    
    with open(workflow_path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    print(f"Updated {workflow_path}")

if __name__ == '__main__':
    secrets = get_all_required_secrets()
    table = generate_markdown_table(secrets)
    update_readme(table)
    update_workflow(secrets)
