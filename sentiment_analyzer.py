import pandas as pd
import requests
import os
import time
from config import ANALYZER_CONFIG, ERROR_MESSAGES

class SentimentAnalyzer:
    def __init__(self):
        self.config = ANALYZER_CONFIG
        self.api_key = None
        self.progress_callback = None
        self.is_running = True
        self.current_index = 0
        self.last_file = None
        self.partial_results = []
        self.post_content = None  # 添加post_content属性初始化
    
    def set_api_key(self, api_key):
        """设置API密钥"""
        self.api_key = api_key
        
    def resume(self):
        """继续分析"""
        self.is_running = True
        if self.last_file and os.path.exists(self.last_file):
            return self.analyze_comments(self.last_file, start_from=self.current_index)
        return None
        
    def stop(self):
        """停止分析"""
        self.is_running = False
        
    def analyze_comments(self, comments_file, start_from=0):
        """分析评论"""
        try:
            if not self.api_key:
                raise ValueError(ERROR_MESSAGES['no_api_key'])
                
            self.last_file = comments_file
            self.current_index = start_from
            df = pd.read_csv(comments_file)
            
            # 如果是继续分析，使用之前保存的部分结果
            if start_from > 0 and self.partial_results:
                results = self.partial_results
            else:
                results = []
            
            total = len(df)
            
            # 获取原文内容（如果存在）
            if 'original_post_content' in df.columns:
                self.post_content = df['original_post_content'].iloc[0]
                print(f"找到原文内容: {self.post_content[:100]}...")
            
            # 创建评论ID和内容的联合键到情感值的映射，确保相同评论有相同的情感值
            comment_sentiment_map = {}
            
            # 从指定位置继续分析
            for idx in range(start_from, len(df)):
                if not self.is_running:
                    self.current_index = idx
                    self.partial_results = results
                    if results:
                        return self._save_partial_results(results)
                    break
                    
                row = df.iloc[idx]
                try:
                    text_to_analyze = row['content']
                    comment_id = row['comment_id']
                    content = row['content']
                    # 使用评论ID和内容的组合作为键，确保相同内容的评论得到相同的情感判断
                    comment_key = f"{comment_id}_{content}"
                    
                    # 检查是否已经分析过这条评论
                    if comment_key in comment_sentiment_map:
                        sentiment = comment_sentiment_map[comment_key]
                    else:
                        sentiment = self._analyze_text(text_to_analyze)
                        comment_sentiment_map[comment_key] = sentiment
                    
                    result = {
                        'comment_id': comment_id,
                        'content': content,
                        'created_at': row['created_at'],
                        'user_name': row['user_name'],
                        'like_count': row['like_count'],
                        'sentiment': sentiment
                    }
                    
                    results.append(result)
                    
                    if self.progress_callback:
                        progress = (idx + 1) / total * 100
                        self.progress_callback(progress)
                        
                    time.sleep(0.5)  # 避免请求过快
                    
                except Exception as e:
                    print(f"单条评论分析失败: {str(e)}")
                    # 如果分析失败，使用中性情感
                    sentiment = 1
                    comment_sentiment_map[comment_key] = sentiment
                    results.append({
                        'comment_id': comment_id,
                        'content': content,
                        'created_at': row['created_at'],
                        'user_name': row['user_name'],
                        'like_count': row['like_count'],
                        'sentiment': sentiment
                    })
            
            # 保存完整结果
            if results:
                # 在保存之前去除重复的评论
                unique_results = []
                seen_comments = set()
                for result in results:
                    comment_key = f"{result['comment_id']}_{result['content']}"
                    if comment_key not in seen_comments:
                        seen_comments.add(comment_key)
                        unique_results.append(result)
                
                self.partial_results = []  # 清空部分结果
                return self._save_results(unique_results)
                
        except Exception as e:
            print(f"分析失败: {str(e)}")
            return None
        finally:
            self.is_running = False  # 确保分析器停止
            
    def _save_partial_results(self, results):
        """保存部分分析结果"""
        try:
            if not os.path.exists(self.config['output_dir']):
                os.makedirs(self.config['output_dir'])
                
            output_file = os.path.join(
                self.config['output_dir'],
                f'analyzed_partial_{int(time.time())}.csv'
            )
            
            df_result = pd.DataFrame(results)
            df_result.to_csv(output_file, index=False, encoding='utf-8-sig')
            return output_file
            
        except Exception as e:
            print(f"保存部分结果失败: {str(e)}")
            return None
            
    def _analyze_text(self, text):
        """调用DeepSeek R1 API进行情感分析"""
        try:
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            }
            
            # 构建带有原文上下文的提示
            prompt = f'''作为一个微博内容发布者,请根据原文和评论的语境灵活判断每条评论的真实情感倾向。注意要结合当下的语境,特别是一些间接的表达方式(如反讽、阴阳怪气等)。

不要被表面的词语迷惑,要理解评论背后真实的态度。

微博原文:
{self.post_content}

评论内容:
{text}

请基于评论的真实态度返回对应数字:
0: 积极态度
1: 中性态度 
2: 消极态度

(注:忽略[]内的表情、链接等内容)'''
            
            data = {
                'model': 'deepseek-reasoner',  # 使用正确的R1模型名称
                'messages': [{
                    'role': 'user',
                    'content': prompt
                }],
                'temperature': 0.1,  # 降低温度以获得更确定性的输出
                'max_tokens': 10,    # 限制输出长度，因为我们只需要一个数字
                'top_p': 0.1,        # 降低采样范围以获得更确定性的输出
                'stream': False      # 关闭流式传输
            }
            
            # 添加重试机制
            max_retries = 3
            retry_delay = 2  # 秒
            
            for attempt in range(max_retries):
                try:
                    response = requests.post(
                        'https://api.deepseek.com/chat/completions',
                        headers=headers,
                        json=data,
                        timeout=30
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        content = result['choices'][0]['message']['content'].strip()
                        
                        # 更严格的输出验证
                        if content not in ['0', '1', '2']:
                            print(f"模型返回了意外的结果: {content}")
                            return 1
                            
                        sentiment = int(content)
                        return sentiment
                        
                except requests.exceptions.Timeout:
                    if attempt < max_retries - 1:
                        print(f"API调用超时，正在进行第{attempt + 2}次尝试...")
                        time.sleep(retry_delay)
                        continue
                    else:
                        print("API调用多次超时，返回中性结果")
                        return 1
                        
                except Exception as e:
                    print(f"API调用失败: {str(e)}")
                    if attempt < max_retries - 1:
                        print(f"正在进行第{attempt + 2}次尝试...")
                        time.sleep(retry_delay)
                        continue
                    else:
                        return 1
            
            return 1  # 如果所有重试都失败，返回中性结果
            
        except Exception as e:
            print(f"分析过程出错: {str(e)}")
            return 1  # 出错时返回中性
    
    def _save_results(self, results):
        """保存完整分析结果"""
        try:
            if not os.path.exists(self.config['output_dir']):
                os.makedirs(self.config['output_dir'])
                
            output_file = os.path.join(
                self.config['output_dir'],
                f'analyzed_{int(time.time())}.csv'
            )
            
            df_result = pd.DataFrame(results)
            df_result.to_csv(output_file, index=False, encoding='utf-8-sig')
            return output_file
            
        except Exception as e:
            print(f"保存分析结果失败: {str(e)}")