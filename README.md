# FreeASR

免费的在线语音转文本工具，支持上传语音文件并解析为文本。

## 功能特点
- 支持多种音频格式上传（MP3、WAV、OGG等）
- 自动转换音频格式为WAV
- 使用Google Speech Recognition进行语音识别
- 实时显示识别结果
- 简单易用的Web界面

## 技术栈
- Python 3.12+
- Flask 2.0.1
- SpeechRecognition 3.10.0
- PyDub 0.25.1

## 安装步骤

1. 克隆仓库
```bash
git clone https://github.com/zyc2478/FreeASR.git
cd FreeASR
```

2. 激活虚拟环境
```bash
source .venv/bin/activate
```

3. 安装依赖
```bash
pip install -r requirements.txt
```

4. 启动应用
```bash
python app.py
```

应用将在 http://localhost:5700 上运行

## 使用方法
1. 打开浏览器访问 http://localhost:5700
2. 点击「选择文件」按钮上传语音文件
3. 点击「开始转写」按钮
4. 等待识别完成，查看转写结果

## 注意事项
- 首次使用时，Google Speech Recognition可能需要网络连接进行认证
- 语音文件不宜过长，建议控制在1分钟以内以获得最佳识别效果
- 请确保上传的语音清晰，背景噪音较小

## 许可证
MIT License
# FreeAutoClip
