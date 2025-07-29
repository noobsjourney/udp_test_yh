#基于 Flask 构建的 插件上传/下载/回滚/版本检查 的后端服务接口
# 配合插件管理系统，可以实现插件的动态更新、版本管理与回滚。
#前提：插件统一存放在：<项目根目录>/plugins/
# 回滚备份存放在：<项目根目录>/backups/<plugin_name>/
# 插件以 Python 文件形式存在（如 hello_plugin.py）
# 插件类中包含 __plugin_metadata__ 字典，描述插件元信息（如版本）

from flask import Flask, request, jsonify, send_file
import shutil
from pathlib import Path
from core.plugin_manager import PluginManager

#初始化一个 Flask Web 服务，提供 REST API 接口供前端或其他模块使用。
app = Flask(__name__)
UPLOAD_FOLDER = Path(__file__).resolve().parent.parent / "plugins"#设置上传目录为 plugins 文件夹
UPLOAD_FOLDER.mkdir(exist_ok=True)

# 上传插件接口
# 输入：前端通过 form-data 提交的 Python 文件（.py 插件文件）
@app.route("/upload", methods=["POST"])
def upload_plugin():
    file = request.files.get("file")
    if not file:
        return jsonify({"error": "未提供文件"}), 400

    save_path = UPLOAD_FOLDER / file.filename
    file.save(str(save_path))

    try:
        PluginManager.instance().reload_plugin(file.filename.replace(".py", ""))
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# 下载插件接口
#前端可通过点击下载按钮，将插件 .py 文件下载到本地。
@app.route("/download/<plugin_name>", methods=["GET"])
def download_plugin(plugin_name):
    path = UPLOAD_FOLDER / f"{plugin_name}.py"
    if not path.exists():
        return jsonify({"error": f"插件文件不存在: {path}"}), 404
    return send_file(str(path), as_attachment=True)


# 插件回滚接口
#输入：
# plugin_name: 插件名
# version: 目标版本（通过 GET 参数传入）
@app.route('/rollback/<plugin_name>')
def rollback(plugin_name):
    version = request.args.get('version')
    try:
        restore_backup(plugin_name, version)
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


from flask import jsonify, request

#插件版本检查接口
#输入：
# plugin_name: 插件名
# version: 当前版本号（默认 0.0.0）
@app.route('/check-update/<plugin_name>', methods=["GET"])
def check_update(plugin_name):
    version = request.args.get('version', '0.0.0')
    latest = get_latest_version(plugin_name)
    return jsonify({
        "update_available": compare_versions(version, latest),
        "latest_version": latest
    })

#返回插件的绝对路径
def get_plugin_path(plugin_name: str):
    return Path(__file__).resolve().parent.parent / "plugins" / f"{plugin_name}.py"
#动态加载插件模块，并读取其类中的 __plugin_metadata__["version"]。
def get_latest_version(plugin_name: str):
    plugin_path = get_plugin_path(plugin_name)
    if not plugin_path.exists():
        return "0.0.0"

    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(plugin_name, plugin_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        metadata = getattr(module.Plugin, "__plugin_metadata__", {})
        return metadata.get("version", "0.0.0")
    except Exception:
        return "0.0.0"

def compare_versions(old: str, new: str):
    return old != new

#从 backups/<plugin_name>/ 中查找包含指定 version 的 .py 文件
def find_backup(plugin_name: str, version: str) -> Path:
    backups_dir = Path("backups") / plugin_name
    return next((f for f in backups_dir.glob("*.py") if version in f.name), None)

#将备份文件拷贝到插件目录，并调用 reload_plugin() 重加载使其生效
def restore_backup(plugin_name, version):
    backup_file = find_backup(plugin_name, version)
    if not backup_file:
        raise FileNotFoundError("指定版本不存在")

    current_path = get_plugin_path(plugin_name)
    shutil.copy(backup_file, current_path)
    PluginManager.instance().reload_plugin(plugin_name)
