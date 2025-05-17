import matplotlib.pyplot as plt
import pandas as pd
from wordcloud import WordCloud
import jieba
import os
from matplotlib.font_manager import FontProperties
import re

class ChartMaker:
    def __init__(self):
        # 固定的颜色映射
        self.colors = {
            'positive': '#3498db',  # 蓝色
            'neutral': '#95a5a6',   # 灰色
            'negative': '#e74c3c'   # 红色
        }
        self.labels = {
            0: '积极',
            1: '中性',
            2: '消极' 
        }
        # 使用系统自带的中文字体或尝试多个字体路径
        self.font = self._get_chinese_font()
        
    def _get_chinese_font(self):
        """获取可用的中文字体路径"""
        try:
            # Windows系统常见中文字体路径
            font_paths = [
                'C:/Windows/Fonts/simhei.ttf',  # 黑体
                'C:/Windows/Fonts/SIMYOU.TTF',  # 幼圆
                'C:/Windows/Fonts/simsun.ttc',  # 宋体
                'C:/Windows/Fonts/msyh.ttc',    # 微软雅黑
            ]
            
            # 返回第一个存在的字体路径
            for path in font_paths:
                if os.path.exists(path):
                    return path
                    
            raise Exception("未找到可用的中文字体")
            
        except Exception as e:
            print(f"加载中文字体失败: {str(e)}")
            return None
    
    def create_pie_chart(self, analyzed_file):
        """生成情感分布饼图"""
        try:
            # 设置中文字体
            plt.rcParams['font.sans-serif'] = ['SimHei']
            plt.rcParams['axes.unicode_minus'] = False
            
            # 读取数据
            df = pd.read_csv(analyzed_file)
            
            # 按固定顺序统计情感，确保每条评论只被统计一次
            df_deduplicated = df.drop_duplicates(subset=['comment_id', 'content'], keep='last')
            
            # 初始化所有情感类别的计数
            sentiment_counts = {0: 0, 1: 0, 2: 0}
            
            # 统计每个类别的数量
            for sentiment in sentiment_counts.keys():
                count = len(df_deduplicated[df_deduplicated['sentiment'] == sentiment])
                sentiment_counts[sentiment] = count
            
            # 准备绘图数据
            sentiment_data = []
            sentiment_labels = []
            sentiment_colors = []
            
            # 按固定顺序添加数据
            for sentiment in [0, 1, 2]:
                if sentiment_counts[sentiment] > 0:  # 只添加有数据的类别
                    sentiment_data.append(sentiment_counts[sentiment])
                    sentiment_labels.append(self.labels[sentiment])
                    color = self.colors['positive' if sentiment == 0 else 'neutral' if sentiment == 1 else 'negative']
                    sentiment_colors.append(color)
            
            # 如果没有数据，返回None
            if not sentiment_data:
                return None
            
            # 创建一个图形对象，避免动画效果
            plt.ioff()  # 关闭交互模式
            fig, ax = plt.subplots(figsize=(8, 6))
            
            # 直接绘制完整的饼图（不使用动画）
            wedges, texts, autotexts = ax.pie(
                sentiment_data,
                labels=sentiment_labels,
                colors=sentiment_colors,
                autopct='%1.1f%%',
                shadow=False,
                textprops={'fontsize': 12, 'weight': 'bold'},
                startangle=90
            )
            
            ax.set_title('评论情感分布', fontsize=14, weight='bold', pad=20)
            
            # 确保图表被完全渲染
            fig.canvas.draw()
            
            # 保存图片
            if not os.path.exists('charts'):
                os.makedirs('charts')
            output_file = 'charts/sentiment_pie.png'
            plt.savefig(output_file, bbox_inches='tight', dpi=300, transparent=False)
            plt.close(fig)
            
            return output_file
            
        except Exception as e:
            print(f"生成饼图失败: {str(e)}")
            return None
            
    def create_wordcloud(self, analyzed_file, sentiment=None):
        """生成词云图"""
        try:
            # 获取字体路径
            font_path = self._get_chinese_font()
            if not font_path:
                raise Exception("未找到可用的中文字体")
            
            # 读取分析结果
            df = pd.read_csv(analyzed_file)
            if sentiment is not None:
                df = df[df['sentiment'] == sentiment]
            
            # 合并评论文本并过滤URL
            text = ' '.join(df['content'].astype(str))
            
            # 过滤URL
            text = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', text)
            
            # 添加停用词
            stop_words = set(['了', '的', '是', '啊', '吗', '呢', '吧', '呀', '着', '啦', '么', 
                             '都', '就', '也', '要', '这', '那', '不', '还', '有', '和', '我',
                             '你', '他', '她', '它', '们', '个', '年', '月', '日', 'http', 'https',
                             'com', 'cn', 'www', 'html', 'org', 'net'])
            
            # 分词并过滤
            words = []
            for word in jieba.cut(text):
                if len(word) > 1 and word not in stop_words and not word.isascii():
                    words.append(word)
            
            text = ' '.join(words)
            
            # 生成词云
            wordcloud = WordCloud(
                font_path=font_path,
                width=800,
                height=400,
                background_color='white',
                max_words=100,
                collocations=False,
                colormap='viridis',
                min_font_size=10,
                max_font_size=80,
                prefer_horizontal=0.9
            ).generate(text)
            
            # 创建图形
            plt.figure(figsize=(10, 5))
            plt.imshow(wordcloud, interpolation='bilinear')
            plt.axis('off')
            
            if not os.path.exists('charts'):
                os.makedirs('charts')
            output_file = f'charts/wordcloud{"_" + str(sentiment) if sentiment is not None else ""}.png'
            plt.savefig(output_file, bbox_inches='tight', dpi=300)
            plt.close()
            
            return output_file
            
        except Exception as e:
            print(f"生成词云图失败: {str(e)}")
            return None

    def save_sentiment_stats(self, analyzed_file):
        """保存情感分析统计结果
        
        Args:
            analyzed_file: 分析结果文件路径
        """
        try:
            # 读取分析结果
            df = pd.read_csv(analyzed_file)
            
            # 统计各情感数量及占比
            stats = df['sentiment'].value_counts()
            total = len(df)
            
            # 生成统计报告
            report = "情感分析统计报告\n"
            report += "=" * 20 + "\n"
            for sentiment, count in stats.items():
                percentage = count / total * 100
                report += f"{self.labels[sentiment]}: {count} 条 ({percentage:.1f}%)\n"
            report += "=" * 20 + "\n"
            
            # 保存报告
            if not os.path.exists('charts'):
                os.makedirs('charts')
            output_file = 'charts/sentiment_stats.txt'
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(report)
                
            return output_file, report
            
        except Exception as e:
            print(f"保存统计结果失败: {str(e)}")
            return None, None