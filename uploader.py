# -*- coding: utf-8 -*-
import os
import shutil
import subprocess  # 用于调用外部迁移脚本
from fastapi import FastAPI, File, UploadFile, BackgroundTasks
from fastapi.responses import HTMLResponse

app = FastAPI()

# S3 挂载路径
UPLOAD_DIR = "/home/opc/tg_data/videos"
# 你之前的迁移脚本路径 (请确保路径正确)
MIGRATION_SCRIPT = "/home/opc/scripts/auto_transfer.sh" 

os.makedirs(UPLOAD_DIR, exist_ok=True)

# --- 后台迁移逻辑 ---
def run_migration(file_name: str):
    """
    文件保存到 S3 后，后台执行此函数：
    1. 调用迁移脚本将文件送往夸克
    2. 脚本运行完后（通常脚本里已经写了删除），确保 S3 副本清理
    """
    print(f"开始迁移文件: {file_name}")
    try:
        # 执行你跑通的迁移脚本
        # 如果脚本不需要参数，直接这样调用：
        result = subprocess.run([MIGRATION_SCRIPT], capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"迁移任务成功完成: {file_name}")
        else:
            print(f"迁移脚本报错: {result.stderr}")
            
    except Exception as e:
        print(f"后台任务执行异常: {e}")

# --- HTML 页面部分 (保持不变) ---
HTML_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>S3 Direct Uploader</title>
    <style>
        body { font-family: sans-serif; background: #1a1a1a; color: #00ff41; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
        .container { border: 1px solid #00ff41; padding: 2rem; border-radius: 8px; width: 90%; max-width: 400px; text-align: center; }
        progress { width: 100%; height: 20px; margin: 15px 0; }
        .btn { background: #00ff41; color: black; border: none; padding: 12px; width: 100%; border-radius: 4px; cursor: pointer; font-weight: bold; }
        #status { margin-top: 15px; font-size: 0.9rem; }
    </style>
</head>
<body>
    <div class="container">
        <h3>S3 Transfer Channel</h3>
        <input type="file" id="fileInput" style="margin-bottom: 20px; display: block; width: 100%;">
        <button class="btn" onclick="startUpload()">Upload to S3</button>
        <progress id="progressBar" value="0" max="100" style="display:none;"></progress>
        <div id="status">Ready</div>
    </div>
    <script>
        function startUpload() {
            const file = document.getElementById('fileInput').files[0];
            if(!file) return alert("Select a file first");
            const formData = new FormData();
            formData.append("file", file);
            const xhr = new XMLHttpRequest();
            xhr.open("POST", "/upload", true);
            document.getElementById('progressBar').style.display = 'block';
            xhr.upload.onprogress = (e) => {
                if (e.lengthComputable) {
                    const percent = (e.loaded / e.total) * 100;
                    document.getElementById('progressBar').value = percent;
                    document.getElementById('status').innerText = "Uploading: " + Math.round(percent) + "%";
                }
            };
            xhr.onload = () => {
                if(xhr.status === 200) {
                    document.getElementById('status').innerText = "SUCCESS: File synced to S3. Migration started.";
                } else {
                    document.getElementById('status').innerText = "ERROR: Upload failed";
                }
            };
            xhr.send(formData);
        }
    </script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
async def index():
    return HTML_PAGE

@app.post("/upload")
async def upload_file(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    file_path = os.path.join(UPLOAD_DIR, file.filename)
    
    # 1. 物理保存文件到 S3 挂载点
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # 2. 核心改动：添加后台任务
    # 这样函数会直接 return 给前端，迁移逻辑在后台跑
    background_tasks.add_task(run_migration, file.filename)
    
    return {"status": "success"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
