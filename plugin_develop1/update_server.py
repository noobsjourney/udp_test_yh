from flask import Flask, request, jsonify
import hashlib
import shutil  # 添加shutil导入
from pathlib import Path  # 添加Path导入
from core.plugin_manager import PluginManager  # 导入插件管理器

app = Flask(__name__)

# 实现缺失的辅助函数
def get_plugin_path(plugin_name: str) -> Path:
    return Path("plugins") / f"{plugin_name}.py"

def find_backup(plugin_name: str, version: str) -> Path:
    backups_dir = Path("backups") / plugin_name
    return next((f for f in backups_dir.glob("*.py") if version in f.name), None)

# 原有路由保持不变

@app.route('/check-update/<plugin_name>')
def check_update(plugin_name):
    current_version = request.args.get('version')
    latest_version = get_latest_version(plugin_name)

    return jsonify({
        'update_available': compare_versions(current_version, latest_version),
        'latest_version': latest_version,
        'download_url': f'/download/{plugin_name}'
    })


@app.route('/rollback/<plugin_name>')
def rollback(plugin_name):
    version = request.args.get('version')
    try:
        restore_backup(plugin_name, version)
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/check-update/<plugin_name>', methods=["GET"])
def check_update(plugin_name):
    version = request.args.get('version', '0.0.0')
    latest = get_latest_version(plugin_name)
    return jsonify({
        "update_available": compare_versions(version, latest),
        "latest_version": latest
    })



def restore_backup(plugin_name, version):
    backup_file = find_backup(plugin_name, version)
    if not backup_file:
        raise FileNotFoundError("指定版本不存在")

    current_path = get_plugin_path(plugin_name)
    shutil.copy(backup_file, current_path)
    PluginManager.instance().reload_plugin(plugin_name)

def get_latest_version(plugin_name: str):
    """从现有插件文件中提取版本"""
    plugin_path = get_plugin_path(plugin_name)
    if not plugin_path.exists():
        return "0.0.0"

    try:
        spec = importlib.util.spec_from_file_location(plugin_name, plugin_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        metadata = getattr(module.Plugin, "__plugin_metadata__", {})
        return metadata.get("version", "0.0.0")
    except Exception:
        return "0.0.0"


def compare_versions(old: str, new: str):
    """简单版本比较"""
    return old != new

