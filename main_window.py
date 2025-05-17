import tkinter as tk
from tkinter import ttk, messagebox, filedialog  # 修改导入方式
from PIL import Image, ImageTk
from weibo_crawler import WeiboCrawler
from sentiment_analyzer import SentimentAnalyzer
from chart_maker import ChartMaker
from config import UI_CONFIG, ERROR_MESSAGES  # 确保配置文件中有这些配置
import threading
import os
import pandas as pd

class MainWindow:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title(UI_CONFIG['title'])
        self.root.geometry(UI_CONFIG['window_size'])
        self.root.minsize(*UI_CONFIG['min_size'])
        
        self.crawler = WeiboCrawler()
        self.analyzer = SentimentAnalyzer()
        self.chart_maker = ChartMaker()
        
        self.setup_ui()
        
    def setup_ui(self):
        """设置UI界面"""
        # 创建主框架
        main_frame = ttk.Frame(self.root, padding=UI_CONFIG['padding'])
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 创建输入区域
        input_frame = ttk.LabelFrame(main_frame, text="配置信息")
        input_frame.pack(fill=tk.X, pady=5)
        
        # URL输入
        ttk.Label(input_frame, text="URL:").grid(row=0, column=0, padx=5, pady=2)
        self.url_entry = ttk.Entry(input_frame, width=50)
        self.url_entry.grid(row=0, column=1, padx=5, pady=2)
        
        # Headers输入
        ttk.Label(input_frame, text="Headers:").grid(row=1, column=0, padx=5, pady=2)
        self.headers_text = tk.Text(input_frame, height=5, width=50)
        self.headers_text.grid(row=1, column=1, padx=5, pady=2)
        
        # API Key输入
        ttk.Label(input_frame, text="API Key:").grid(row=2, column=0, padx=5, pady=2)
        self.api_key_entry = ttk.Entry(input_frame, width=50)
        self.api_key_entry.grid(row=2, column=1, padx=5, pady=2)
        
        # 按钮区域
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(button_frame, text="开始爬取", command=self.start_crawl).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="开始分析", command=self.start_analysis).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="生成图表", command=self.generate_chart).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="清空显示", command=self.clear_all).pack(side=tk.LEFT, padx=5)
        
        # 进度条
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(
            main_frame, 
            variable=self.progress_var,
            maximum=100
        )
        self.progress_bar.pack(fill=tk.X, pady=5)
        
        # 结果展示区域
        result_frame = ttk.LabelFrame(main_frame, text="结果展示")
        result_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # 文本展示
        self.result_text = tk.Text(result_frame, wrap=tk.WORD)
        self.result_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # 图表展示区域
        chart_frame = ttk.Frame(result_frame)
        chart_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        # 饼图标签
        self.pie_label = ttk.Label(chart_frame)
        self.pie_label.pack(fill=tk.BOTH, expand=True)
        
        # 词云图标签
        self.wordcloud_label = ttk.Label(chart_frame)
        self.wordcloud_label.pack(fill=tk.BOTH, expand=True)
        
        # 状态栏
        self.status_var = tk.StringVar()
        self.status_var.set("就绪")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # 绑定大小变化事件
        self.pie_label.bind('<Configure>', self._update_pie_display)
        self.wordcloud_label.bind('<Configure>', self._update_wordcloud_display)

    def start_crawl(self):
        """开始爬取评论"""
        threading.Thread(target=self._crawl_thread).start()
        
    def start_analysis(self):
        """开始情感分析"""
        threading.Thread(target=self._analysis_thread).start()
        
    def generate_chart(self):
        """生成图表"""
        chart_type = self.chart_type_combobox.get()
        if chart_type == "饼图":
            self.generate_pie_chart()
        elif chart_type == "词云图":
            self.generate_wordcloud()
        else:
            self.show_message("错误", "未知的图表类型")
        
    def _crawl_thread(self):
        """爬虫线程"""
        try:
            url = self.url_entry.get()
            if not url:
                self.show_message("错误", "请输入URL")
                return
                
            headers = self.parse_headers()
            if not all(headers.values()):
                self.show_message("错误", "请填写完整的Headers信息")
                return
                
            # 设置进度回调
            def progress_callback(count):
                self.progress_var.set(min(count, 100))
                self.result_text.insert(tk.END, f"已爬取 {count} 条评论\n")
                self.result_text.see(tk.END)
                
            self.crawler.progress_callback = progress_callback
            self.crawler.set_headers(**headers)
            
            # 清空显示
            self.result_text.delete(1.0, tk.END)
            self.progress_var.set(0)
            
            # 开始爬取
            output_file = self.crawler.crawl_comments(url)
            if output_file:
                self.last_crawl_file = output_file
                self.show_message("完成", f"评论已保存至: {output_file}")
                
        except Exception as e:
            self.show_message("错误", str(e))
        finally:
            self.is_crawling = False

    def _analysis_thread(self):
        """分析线程"""
        try:
            if not self.last_crawl_file:  # 使用实例属性
                self.show_message("错误", "请先爬取评论")
                return
                
            self.update_status("正在进行情感分析...")
            self.analyzer.is_running = True
            
            api_key = self.api_key_entry.get().strip()
            if not api_key:
                self.show_message("错误", "请输入API Key")
                return
                
            # 设置API key
            self.analyzer.set_api_key(api_key)
            
            # 清空显示
            self.result_text.delete(1.0, tk.END)
            self.progress_var.set(0)
            
            # 定义进度回调
            def progress_callback(progress):
                if not self.is_analyzing:
                    raise Exception("分析已停止")
                self.progress_var.set(progress)
                self.result_text.insert(tk.END, f"分析进度: {progress:.1f}%\n")
                self.result_text.see(tk.END)
                self.root.update()
                
            self.analyzer.progress_callback = progress_callback
            
            # 开始分析
            output_file = self.analyzer.analyze_comments(self.last_crawl_file)
            
            if output_file and os.path.exists(output_file):
                self.last_analysis_file = output_file  # 更新分析结果文件路径
                print(f"分析结果文件保存在: {output_file}")
                
                # 显示分析结果
                df = pd.read_csv(output_file)
                self.result_text.delete(1.0, tk.END)
                
                # 统计各类情感数量
                sentiment_counts = df['sentiment'].value_counts()
                total = len(df)
                
                # 显示统计信息
                self.result_text.insert(tk.END, "情感分析结果统计：\n")
                self.result_text.insert(tk.END, "=" * 30 + "\n")
                for sentiment, count in sentiment_counts.items():
                    percentage = count / total * 100
                    label = self.chart_maker.labels[sentiment]
                    self.result_text.insert(tk.END, f"{label}: {count}条 ({percentage:.1f}%)\n")
                self.result_text.insert(tk.END, "=" * 30 + "\n\n")
                
                # 显示详细结果
                for _, row in df.iterrows():
                    sentiment = self.chart_maker.labels[row['sentiment']]
                    comment_info = (
                        f"[{sentiment}]\n"
                        f"用户: {row['user_name']}\n"
                        f"时间: {row['created_at']}\n"
                        f"点赞: {row['like_count']}\n"
                        f"内容: {row['content']}\n"
                        f"{'-'*50}\n"
                    )
                    self.result_text.insert(tk.END, comment_info)
                    
                self.update_status("分析完成")
                self.show_message("完成", "情感分析已完成")
            else:
                raise Exception("分析结果文件生成失败")
                
        except Exception as e:
            print(f"分析错误: {str(e)}")
            self.show_message("错误", str(e))
            self.update_status("分析失败")
        finally:
            self.is_analyzing = False

    def generate_pie_chart(self):
        """生成饼图"""
        try:
            if not hasattr(self, 'last_analysis_file'):
                self.show_message("错误", "请先进行情感分析")
                return
                
            chart_file = self.chart_maker.create_pie_chart(self.last_analysis_file)
            if chart_file:
                self.show_chart(chart_file)
                
        except Exception as e:
            self.show_message("错误", str(e))

    def generate_wordcloud(self):
        """生成词云图"""
        try:
            if not hasattr(self, 'last_analysis_file'):
                self.show_message("错误", "请先进行情感分析")
                return
                
            chart_file = self.chart_maker.create_wordcloud(self.last_analysis_file)
            if chart_file:
                self.show_chart(chart_file)
                
        except Exception as e:
            self.show_message("错误", str(e))
        
    def parse_headers(self):
        """解析Headers文本"""
        headers_text = self.headers_text.get("1.0", tk.END)
        headers = {}
        for line in headers_text.split('\n'):
            if ':' in line:
                key, value = line.split(':', 1)
                headers[key.strip()] = value.strip()
        return headers
        
    def show_message(self, title, message):
        """显示消息框"""
        messagebox.showinfo(title, message)
        
    def show_chart(self, chart_file):
        """显示图表"""
        try:
            image = Image.open(chart_file)
            # 保持宽高比
            aspect_ratio = image.width / image.height
            target_size = (300, 300)
            if target_size[0] / target_size[1] > aspect_ratio:
                new_width = int(target_size[1] * aspect_ratio)
                new_height = target_size[1]
            else:
                new_width = target_size[0]
                new_height = int(target_size[0] / aspect_ratio)
            
            image = image.resize((new_width, new_height), Image.LANCZOS)
            photo = ImageTk.PhotoImage(image)
            self.pie_label.configure(image=photo)
            self.pie_label.image = photo
        except Exception as e:
            print(f"显示图表错误: {str(e)}")
            self.show_message("错误", "显示图表失败")
        
    def clear_all(self):
        """清空所有显示"""
        try:
            # 清空文本显示
            self.result_text.delete(1.0, tk.END)
            
            # 清空图表显示
            if hasattr(self, 'current_pie_file'):
                delattr(self, 'current_pie_file')
            if hasattr(self, 'current_wordcloud_file'):
                delattr(self, 'current_wordcloud_file')
            
            # 清空图表标签
            self.pie_label.configure(image='')
            self.wordcloud_label.configure(image='')
            
            # 更新状态
            self.update_status("显示已清空")
            
        except Exception as e:
            print(f"清空显示失败: {str(e)}")
            self.show_message("错误", "清空显示失败")
        
    def run(self):
        """运行程序"""
        self.root.mainloop()