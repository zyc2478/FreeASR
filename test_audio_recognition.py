#!/usr/bin/env python
# -*- coding: utf-8 -*-

import speech_recognition as sr
from pydub import AudioSegment
import os
import tempfile

# 测试音频文件路径
audio_file = "/Users/zyc/Desktop/京北围棋培训中心(回龙观校区).m4a"

print(f"开始测试音频文件: {audio_file}")

# 检查文件是否存在
if not os.path.exists(audio_file):
    print(f"错误：文件不存在")
    exit(1)

print(f"文件存在，大小: {os.path.getsize(audio_file) / 1024 / 1024:.2f} MB")

# 转换为WAV格式
print("开始转换音频格式...")
sound = AudioSegment.from_file(audio_file)
print(f"音频时长: {len(sound) / 1000:.2f}秒")

# 保存为临时WAV文件
with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_wav:
    temp_path = temp_wav.name
    sound.export(temp_path, format='wav')
    print(f"已转换为WAV格式: {temp_path}")

# 初始化语音识别器
print("初始化语音识别器...")
r = sr.Recognizer()

# 识别音频
print("开始识别音频...")
with sr.AudioFile(temp_path) as source:
    audio = r.record(source)
    try:
        print("调用Google语音识别API...")
        result = r.recognize_google(audio, language='zh-CN')
        print(f"识别成功！")
        print(f"识别结果: {result}")
    except sr.UnknownValueError:
        print("错误：无法识别音频内容")
    except sr.RequestError as e:
        print(f"错误：API请求失败: {str(e)}")
    except Exception as e:
        print(f"错误：{str(e)}")

# 清理临时文件
os.remove(temp_path)
print("测试完成")