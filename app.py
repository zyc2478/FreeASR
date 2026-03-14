from flask import Flask, render_template, request, redirect, url_for, flash, send_file, Response
import speech_recognition as sr
from pydub import AudioSegment
import os
import tempfile
import json
import time
import uuid
import threading

# 用于存储处理状态的全局字典
processing_status = {}
# 用于存储处理线程的全局字典
processing_threads = {}
# 线程锁
status_lock = threading.Lock()

# 历史记录文件
HISTORY_FILE = 'transcription_history.json'

# 确保历史记录文件存在
if not os.path.exists(HISTORY_FILE):
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump([], f)

def load_history():
    """加载历史记录"""
    with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_history(history):
    """保存历史记录"""
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

app = Flask(__name__)
app.secret_key = 'supersecretkey'

# 确保uploads目录存在
UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 200 * 1024 * 1024  # 200MB
app.config['PERMANENT_SESSION_LIFETIME'] = 600  # 10分钟
app.config['MAX_CONTENT_PATH'] = None  # 禁用内容路径限制
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0  # 禁用缓存
app.config['UPLOAD_EXTENSIONS'] = ['.wav', '.m4a', '.mp3', '.ogg', '.flac']  # 允许的文件扩展名
app.config['UPLOAD_MAX_SIZE'] = 200 * 1024 * 1024  # 200MB

@app.route('/')
def index():
    # 加载历史记录
    history = load_history()
    # 按时间戳倒序排列
    history.sort(key=lambda x: x['timestamp'], reverse=True)
    # 只显示最近10条记录
    recent_history = history[:10]
    return render_template('index.html', history=recent_history)

@app.route('/progress/<task_id>')
def progress(task_id):
    """SSE端点，用于实时传输处理进度"""
    def generate():
        while True:
            with status_lock:
                if task_id in processing_status:
                    status = processing_status[task_id]
                    # 发送SSE事件
                    yield "data: " + json.dumps(status) + "\n\n"
                    # 如果处理完成，退出循环
                    if status.get('status') == 'completed' or status.get('status') == 'error':
                        break
                else:
                    # 任务不存在
                    yield "data: " + json.dumps({'status': 'error', 'message': '任务不存在'}) + "\n\n"
                    break
            time.sleep(1)  # 每秒发送一次
    
    return Response(generate(), mimetype='text/event-stream', headers={'Content-Type': 'text/event-stream'})

@app.route('/download/<filename>')
def download_file(filename):
    # 构建临时文件路径
    temp_file_path = os.path.join(tempfile.gettempdir(), filename)
    if os.path.exists(temp_file_path):
        return send_file(temp_file_path, as_attachment=True, download_name='transcription.txt')
    else:
        flash('文件不存在')
        return redirect(url_for('index'))

@app.route('/ai-summary', methods=['POST'])
def ai_summary():
    transcription = request.form.get('transcription')
    if not transcription:
        flash('没有转写内容')
        return redirect(url_for('index'))
    
    # 这里可以添加AI总结的逻辑
    # 由于没有AI API，这里返回一个简单的总结
    summary = f"这是对转写内容的AI总结。\n\n转写内容长度：{len(transcription)}字符\n主要内容：{transcription[:200]}..."
    
    return render_template('summary.html', summary=summary, transcription=transcription)

def process_file_async(task_id, file, safe_filename, temp_path):
    """异步处理文件"""
    try:
        start_time = time.time()
        process_log = []
        process_log.append(f"开始处理文件: {file.filename}")
        process_log.append(f"保存为: {safe_filename}")
        process_log.append(f"文件大小: {os.path.getsize(temp_path) / 1024 / 1024:.2f} MB")
        
        # 更新状态
        with status_lock:
            processing_status[task_id] = {
                'status': 'processing',
                'progress': 0,
                'message': '初始化语音识别器...',
                'log': process_log
            }
        
        # 初始化语音识别器
        r = sr.Recognizer()
        process_log.append("初始化语音识别器完成")
        
        # 更新状态
        with status_lock:
            processing_status[task_id] = {
                'status': 'processing',
                'progress': 5,
                'message': '检查文件类型...',
                'log': process_log
            }
        
        # 检查文件类型并转换为WAV格式
        file_extension = os.path.splitext(temp_path)[1].lower()
        if file_extension == '.wav':
            audio_file = sr.AudioFile(temp_path)
            process_log.append(f"文件格式为WAV，无需转换")
        elif file_extension == '.m4a':
            process_log.append(f"检测到M4A格式，正在转换为WAV")
            # 更新状态
            with status_lock:
                processing_status[task_id] = {
                    'status': 'processing',
                    'progress': 10,
                    'message': '正在转换M4A格式...',
                    'log': process_log
                }
            sound = AudioSegment.from_file(temp_path, format='m4a')
            wav_path = temp_path.replace(file_extension, '.wav')
            sound.export(wav_path, format='wav')
            audio_file = sr.AudioFile(wav_path)
            temp_path = wav_path
            process_log.append("格式转换完成")
        else:
            # 转换为WAV格式
            process_log.append(f"检测到{file_extension}格式，正在转换为WAV")
            # 更新状态
            with status_lock:
                processing_status[task_id] = {
                    'status': 'processing',
                    'progress': 10,
                    'message': f'正在转换{file_extension}格式...',
                    'log': process_log
                }
            sound = AudioSegment.from_file(temp_path)
            wav_path = temp_path.replace(file_extension, '.wav')
            sound.export(wav_path, format='wav')
            audio_file = sr.AudioFile(wav_path)
            temp_path = wav_path
            process_log.append("格式转换完成")
        
        # 更新状态
        with status_lock:
            processing_status[task_id] = {
                'status': 'processing',
                'progress': 15,
                'message': '分析音频文件...',
                'log': process_log
            }
        
        # 读取音频文件并切分处理
        transcriptions = []
        chunk_duration = 60  # 每个片段60秒
        
        try:
            # 更新状态
            with status_lock:
                processing_status[task_id] = {
                    'status': 'processing',
                    'progress': 16,
                    'message': '检查文件存在性...',
                    'log': process_log
                }
            
            # 检查文件是否存在
            if not os.path.exists(temp_path):
                raise Exception(f"文件不存在: {temp_path}")
            
            process_log.append(f"文件存在，大小: {os.path.getsize(temp_path) / 1024 / 1024:.2f} MB")
            print(f"文件存在，大小: {os.path.getsize(temp_path) / 1024 / 1024:.2f} MB")
            
            # 更新状态
            with status_lock:
                processing_status[task_id] = {
                    'status': 'processing',
                    'progress': 17,
                    'message': '正在加载音频文件...',
                    'log': process_log
                }
            
            # 获取音频文件时长
            process_log.append(f"尝试加载音频文件: {temp_path}")
            print(f"尝试加载音频文件: {temp_path}")
            
            # 尝试不同的格式选项
            start_time = time.time()
            sound = None
            
            # 尝试直接加载
            try:
                process_log.append("尝试直接加载音频文件")
                print("尝试直接加载音频文件")
                sound = AudioSegment.from_file(temp_path)
                process_log.append(f"成功加载音频文件，耗时: {time.time() - start_time:.2f}秒")
                print(f"成功加载音频文件，耗时: {time.time() - start_time:.2f}秒")
            except Exception as e:
                process_log.append(f"直接加载失败: {str(e)}")
                print(f"直接加载失败: {str(e)}")
                
                # 尝试根据文件扩展名指定格式
                file_extension = os.path.splitext(temp_path)[1].lower()[1:]  # 去掉点号
                process_log.append(f"尝试使用格式 {file_extension} 加载")
                print(f"尝试使用格式 {file_extension} 加载")
                
                try:
                    sound = AudioSegment.from_file(temp_path, format=file_extension)
                    process_log.append(f"使用指定格式 {file_extension} 成功加载")
                    print(f"使用指定格式 {file_extension} 成功加载")
                except Exception as e2:
                    process_log.append(f"指定格式加载失败: {str(e2)}")
                    print(f"指定格式加载失败: {str(e2)}")
                    raise
            
            # 更新状态
            with status_lock:
                processing_status[task_id] = {
                    'status': 'processing',
                    'progress': 18,
                    'message': '正在计算音频时长...',
                    'log': process_log
                }
            
            total_duration = len(sound) / 1000  # 转换为秒
            process_log.append(f"音频文件时长: {total_duration:.2f}秒")
            process_log.append(f"将音频切分为{chunk_duration}秒的片段")
            print(f"音频文件时长: {total_duration:.2f}秒")
            
            # 切分音频并逐段识别
            total_chunks = (int(total_duration) + chunk_duration - 1) // chunk_duration
            process_log.append(f"共需处理{total_chunks}个片段")
            
            # 更新状态
            with status_lock:
                processing_status[task_id] = {
                    'status': 'processing',
                    'progress': 20,
                    'message': f'准备处理{total_chunks}个片段...',
                    'log': process_log
                }
            
            for i in range(0, int(total_duration) + chunk_duration, chunk_duration):
                chunk_index = i // chunk_duration + 1
                start_time_chunk = i * 1000  # 转换为毫秒
                end_time_chunk = min((i + chunk_duration) * 1000, len(sound))
                
                # 计算当前进度
                current_progress = 20 + (chunk_index / total_chunks) * 70
                
                process_log.append(f"处理第{chunk_index}个片段: {i:.0f}-{min(i+chunk_duration, total_duration):.0f}秒")
                
                # 更新状态
                with status_lock:
                    processing_status[task_id] = {
                        'status': 'processing',
                        'progress': current_progress,
                        'message': f'处理第{chunk_index}/{total_chunks}个片段...',
                        'log': process_log
                    }
                
                # 提取当前片段
                chunk = sound[start_time_chunk:end_time_chunk]
                chunk_path = f"{temp_path}_chunk{i}.wav"
                chunk.export(chunk_path, format='wav')
                
                # 识别当前片段
                with sr.AudioFile(chunk_path) as chunk_audio:
                    audio = r.record(chunk_audio)
                    try:
                        # 更新状态
                        with status_lock:
                            processing_status[task_id] = {
                                'status': 'processing',
                                'progress': current_progress,
                                'message': f'正在识别第{chunk_index}/{total_chunks}个片段...',
                                'log': process_log
                            }
                        
                        # 添加超时设置，防止网络请求卡住
                        import socket
                        socket.setdefaulttimeout(30)  # 30秒超时
                        print(f"开始识别第{chunk_index}个片段...")
                        chunk_transcription = r.recognize_google(audio, language='zh-CN')
                        transcriptions.append(chunk_transcription)
                        process_log.append(f"第{chunk_index}个片段识别成功")
                        print(f"第{chunk_index}个片段识别成功，结果: {chunk_transcription[:50]}...")
                    except sr.UnknownValueError:
                        transcriptions.append('[无法识别]')
                        process_log.append(f"第{chunk_index}个片段无法识别")
                        print(f"第{chunk_index}个片段无法识别")
                    except sr.RequestError as e:
                        transcriptions.append(f'[识别错误: {str(e)}]')
                        process_log.append(f"第{chunk_index}个片段识别错误: {str(e)}")
                        print(f"第{chunk_index}个片段识别错误: {str(e)}")
                    except Exception as e:
                        transcriptions.append(f'[处理错误: {str(e)}]')
                        process_log.append(f"第{chunk_index}个片段处理错误: {str(e)}")
                        print(f"第{chunk_index}个片段处理错误: {str(e)}")
                
                # 删除临时片段文件
                if os.path.exists(chunk_path):
                    os.remove(chunk_path)
            
            # 合并所有片段的识别结果
            transcription = ' '.join(transcriptions)
            process_log.append("所有片段识别完成，正在合并结果")
            print(f"所有片段识别完成，共{len(transcriptions)}个片段")
            print(f"合并后的转写结果长度: {len(transcription)}字符")
        except Exception as e:
            # 如果切分处理失败，尝试整体识别
            process_log.append(f"切分处理失败，尝试整体识别: {str(e)}")
            # 更新状态
            with status_lock:
                processing_status[task_id] = {
                    'status': 'processing',
                    'progress': 50,
                    'message': '切分处理失败，尝试整体识别...',
                    'log': process_log
                }
            try:
                with audio_file as source:
                    audio = r.record(source)
                transcription = r.recognize_google(audio, language='zh-CN')
                process_log.append("整体识别成功")
            except Exception as inner_e:
                raise inner_e
        
        # 计算处理时间
        end_time = time.time()
        process_time = end_time - start_time
        process_log.append(f"处理完成，总耗时: {process_time:.2f}秒")
        print(f"处理完成，总耗时: {process_time:.2f}秒")
        
        # 获取文件大小（在删除之前）
        file_size_mb = os.path.getsize(os.path.join(app.config["UPLOAD_FOLDER"], safe_filename)) / 1024 / 1024
        print(f"原始文件大小: {file_size_mb:.2f} MB")
        
        # 删除临时文件
        if os.path.exists(temp_path):
            os.remove(temp_path)
        process_log.append("临时文件已清理")
        print("临时文件已清理")
        
        # 保存转写结果到临时文件，用于下载
        print("开始保存转写结果...")
        temp_transcription_file = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8')
        temp_transcription_file.write(transcription)
        temp_transcription_file.close()
        print(f"转写结果已保存到: {temp_transcription_file.name}")
        
        # 保存处理日志
        print("开始保存处理日志...")
        temp_log_file = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8')
        temp_log_file.write('\n'.join(process_log))
        temp_log_file.close()
        print(f"处理日志已保存到: {temp_log_file.name}")
        
        # 保存历史记录
        print("开始保存历史记录...")
        history = load_history()
        history_entry = {
            'id': str(uuid.uuid4()),
            'filename': file.filename,
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'duration': f'{total_duration:.2f}秒',
            'file_size': f'{file_size_mb:.2f} MB',
            'transcription_file': os.path.basename(temp_transcription_file.name),
            'log_file': os.path.basename(temp_log_file.name),
            'transcription_preview': transcription[:100] + '...' if len(transcription) > 100 else transcription
        }
        history.append(history_entry)
        print(f"历史记录已添加，当前共{len(history)}条记录")
        # 只保留最近20条记录
        if len(history) > 20:
            history = history[-20:]
        save_history(history)
        print("历史记录已保存")
        
        # 更新状态为完成
        print("更新处理状态为完成...")
        with status_lock:
            processing_status[task_id] = {
                'status': 'completed',
                'progress': 100,
                'message': '处理完成！',
                'log': process_log,
                'transcription': transcription,
                'transcription_file': os.path.basename(temp_transcription_file.name),
                'log_file': os.path.basename(temp_log_file.name)
            }
        print("处理状态已更新为完成")
    except Exception as e:
        print(f"错误：处理文件时出错: {str(e)}")
        import traceback
        traceback.print_exc()
        # 删除临时文件
        if os.path.exists(temp_path):
            os.remove(temp_path)
        # 更新状态为错误
        with status_lock:
            processing_status[task_id] = {
                'status': 'error',
                'progress': 0,
                'message': f'处理错误: {str(e)}',
                'log': process_log
            }

@app.route('/upload', methods=['POST'])
def upload_file():
    try:
        print(f"收到上传请求")
        
        # 检查请求内容
        print(f"请求方法: {request.method}")
        print(f"请求文件: {request.files}")
        print(f"请求表单: {request.form}")
        print(f"请求头: {dict(request.headers)}")
        print(f"开始处理请求...")
        
        if 'file' not in request.files:
            print("错误：没有文件部分")
            flash('No file part')
            return redirect(request.url)
        
        file = request.files['file']
        print(f"文件名: {file.filename}")
        print(f"文件类型: {file.content_type}")
        print(f"文件大小: {file.content_length}")
        print(f"开始读取文件内容...")
        
        if file.filename == '':
            print("错误：文件名为空")
            flash('No selected file')
            return redirect(request.url)
        
        if file:
            print("开始处理文件")
            
            # 生成任务ID
            task_id = str(uuid.uuid4())
            print(f"任务ID: {task_id}")
            
            # 生成安全的文件名
            safe_filename = f"upload_{uuid.uuid4().hex}{os.path.splitext(file.filename)[1]}"
            print(f"安全文件名: {safe_filename}")
            
            # 保存文件到临时目录
            temp_path = os.path.join(app.config['UPLOAD_FOLDER'], safe_filename)
            print(f"保存路径: {temp_path}")
            
            # 确保上传目录存在
            if not os.path.exists(app.config['UPLOAD_FOLDER']):
                os.makedirs(app.config['UPLOAD_FOLDER'])
                print(f"创建上传目录: {app.config['UPLOAD_FOLDER']}")
            
            # 保存文件
            print("开始保存文件...")
            start_time = time.time()
            file.save(temp_path)
            save_time = time.time() - start_time
            print(f"文件已保存，耗时: {save_time:.2f}秒")
            
            # 检查文件是否保存成功
            if os.path.exists(temp_path):
                file_size = os.path.getsize(temp_path)
                print(f"文件保存成功，大小: {file_size / 1024 / 1024:.2f} MB")
            else:
                print("错误：文件保存失败")
                return json.dumps({'error': '文件保存失败'}), 500
            
            print("准备启动处理线程...")
            
            # 初始化处理状态
            with status_lock:
                processing_status[task_id] = {
                    'status': 'starting',
                    'progress': 0,
                    'message': '开始处理文件...',
                    'log': []
                }
            
            print("处理状态已初始化")
            
            # 启动异步处理线程
            print("启动处理线程...")
            thread = threading.Thread(target=process_file_async, args=(task_id, file, safe_filename, temp_path))
            thread.daemon = True
            thread.start()
            print(f"处理线程已启动，线程ID: {thread.ident}")
            
            # 保存线程引用
            processing_threads[task_id] = thread
            print("线程引用已保存")
            
            print("准备返回任务ID...")
            # 返回任务ID，前端通过SSE获取进度
            response = json.dumps({'task_id': task_id})
            print(f"返回响应: {response}")
            return response, 200, {'Content-Type': 'application/json'}
    except Exception as e:
        print(f"错误：上传文件时出错: {str(e)}")
        import traceback
        traceback.print_exc()
        return json.dumps({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5700)