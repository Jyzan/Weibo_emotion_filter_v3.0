import requests
import pandas as pd
import time
import os
import re
import json
from config import CRAWLER_CONFIG, ERROR_MESSAGES

class WeiboCrawler:
    def __init__(self):
        self.config = CRAWLER_CONFIG
        self.session = requests.Session()
        self.headers = {}
        self.progress_callback = None
        self.is_running = True
        self.current_page = 1
        self.max_id = None
        self.comments = []
        self.url = None
        self.last_max_id = None  # 记录上次爬取的位置
        self.original_post = None  # 添加原文存储
        
    def set_headers(self, user_agent, cookie, referer):
        """设置请求头"""
        self.headers = {
            'User-Agent': user_agent,
            'Cookie': cookie,
            'Referer': referer,
            'X-Requested-With': 'XMLHttpRequest',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive'
        }
        
    def parse_cookies(self, cookie_string):
        """解析Cookie字符串"""
        cookies = {}
        for item in cookie_string.split(';'):
            if '=' in item:
                key, value = item.strip().split('=', 1)
                cookies[key] = value
        return cookies
        
    def _get_original_post(self, mid):
        """获取微博原文"""
        try:
            url = f'https://weibo.com/ajax/statuses/show?id={mid}'
            print(f"正在请求URL: {url}")
            
            response = self.session.get(url, headers=self.headers)
            print(f"响应状态码: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"响应数据: {json.dumps(data, ensure_ascii=False)[:200]}...")
                
                # 检查新的数据结构
                if isinstance(data, dict):
                    post_data = data
                    self.original_post = {
                        'post_id': post_data.get('id', ''),
                        'content': post_data.get('text_raw', ''),
                        'created_at': post_data.get('created_at', ''),
                        'user_name': post_data.get('user', {}).get('screen_name', ''),
                        'repost_count': post_data.get('reposts_count', 0),
                        'comment_count': post_data.get('comments_count', 0),
                        'like_count': post_data.get('attitudes_count', 0),
                        'pics': [pic['url'] for pic in post_data.get('pics', [])] if 'pics' in post_data else []
                    }
                    print(f"处理后的微博信息: {json.dumps(self.original_post, ensure_ascii=False)}")
                    return True
            return False
            
        except Exception as e:
            print(f"获取原文失败: {str(e)}")
            return False
        
    def crawl_comments(self, url):
        """开始爬取评论"""
        self.url = url
        self.is_running = True
        self.comments = []
        self.current_page = 1
        self.max_id = None
        self.original_post = None  # 重置原文
        return self._crawl()
        
    def _crawl(self, start_from_max_id=None):
        """实际的爬取逻辑"""
        try:
            if not all(self.headers.values()):
                raise ValueError(ERROR_MESSAGES['no_headers'])

            # 从URL中提取参数
            try:
                if 'id=' in self.url:
                    mid = re.search(r'id=(\d+)', self.url).group(1)
                    uid = re.search(r'uid=(\d+)', self.url).group(1)
                else:
                    mid_match = re.search(r'/(\d+)\?', self.url)
                    if not mid_match:
                        raise ValueError("无效的URL格式")
                    mid = mid_match.group(1)
                    uid = self.get_uid_from_url(self.url)
                
                # 获取原文
                if not self._get_original_post(mid):
                    print("警告: 获取原文失败，将继续爬取评论")
                    
                while self.is_running:
                    # 构造API请求
                    api_url = "https://weibo.com/ajax/statuses/buildComments"
                    params = {
                        'id': mid,
                        'is_reload': 1,
                        'is_show_bulletin': 2,
                        'is_mix': 0,
                        'count': 20,
                        'uid': uid,
                        'fetch_level': 0,
                        'max_id': start_from_max_id if start_from_max_id else (self.max_id if self.max_id else 0)
                    }
                    
                    response = self.session.get(api_url, headers=self.headers, params=params)
                    data = response.json()
                    
                    if 'data' in data and isinstance(data['data'], list):
                        comments_data = data['data']
                        if not comments_data:
                            break
                            
                        for comment in comments_data:
                            self.comments.append({
                                'comment_id': comment['id'],
                                'content': comment['text_raw'],
                                'created_at': comment['created_at'],
                                'user_name': comment['user']['screen_name'],
                                'like_count': comment.get('like_counts', 0)
                            })
                            
                        # 回调进度
                        if self.progress_callback:
                            self.progress_callback(len(self.comments))
                            
                        # 获取下一页的max_id
                        self.max_id = data.get('max_id')
                        if not self.max_id:
                            break
                            
                        self.current_page += 1
                        time.sleep(self.config['sleep_time'])
                    else:
                        break
                        
            except Exception as e:
                print(f"爬取失败: {str(e)}")
                
            # 保存已爬取的评论
            return self._save_comments()
                
        except Exception as e:
            print(f"爬虫异常: {str(e)}")
            raise
            
    def _save_comments(self):
        """保存评论到文件"""
        if self.comments:
            if not os.path.exists(self.config['output_dir']):
                os.makedirs(self.config['output_dir'])
            
            timestamp = int(time.time())
            
            # 保存原文到单独的CSV文件
            if self.original_post:
                original_post_file = os.path.join(
                    self.config['output_dir'],
                    f'original_post_{timestamp}.csv'
                )
                original_post_df = pd.DataFrame([self.original_post])
                original_post_df.to_csv(original_post_file, index=False, encoding='utf-8-sig')
                print(f"原文已保存至: {original_post_file}")
            
            # 保存评论到CSV文件
            comments_file = os.path.join(
                self.config['output_dir'],
                f'comments_{timestamp}.csv'
            )
            
            df = pd.DataFrame(self.comments)
            df.to_csv(comments_file, index=False, encoding='utf-8-sig')
            return comments_file
        return None
        
    def stop(self):
        """停止爬取"""
        self.is_running = False
        self.last_max_id = self.max_id  # 保存当前位置
        
    def resume(self):
        """继续爬取"""
        if self.url and self.last_max_id:
            self.is_running = True
            return self._crawl(start_from_max_id=self.last_max_id)
        return None