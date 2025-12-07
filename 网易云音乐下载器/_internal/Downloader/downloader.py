# netease_downloader.py
import requests
import re
import execjs
import os
from pprint import pprint
from prettytable import PrettyTable

class NetEaseMusicDownloader:
    def __init__(self):
        self.js_code = None
        self.cookies = None
        self.headers = {
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36 Edg/141.0.0.0'
        }
        self._load_js_code()
    
    def _load_js_code(self):
        """加载并编译JS加密代码"""
        try:
            self.js_code = execjs.compile(open('Downloader/wangyi.js', 'r', encoding='utf-8').read())
        except FileNotFoundError:
            raise Exception("网易.js文件未找到，请确保加密文件存在")
        except Exception as e:
            raise Exception(f"加载JS加密代码失败: {str(e)}")
    
    def set_cookies(self, cookies):
        """设置Cookies"""
        self.cookies = cookies
        self.headers['cookie'] = cookies
        print(self.headers)
    
    def get_music_info(self, playlist_url=None):
        """获取音乐信息"""
        if not self.cookies:
            raise Exception("请先设置Cookies")
        
        if playlist_url:
            url = playlist_url
        else:
            # 默认热歌榜
            url = 'http://music.163.com/discover/toplist?id=3778678'
        
        try:
            html = requests.get(url=url, headers=self.headers).text
            # 提取歌曲ID / 歌曲名称
            music_info = re.findall(r'<a href="/song\?id=(\d+)">(.*?)</a>', html)
            return music_info
        except Exception as e:
            raise Exception(f"获取音乐信息失败: {str(e)}")
    
    def get_music_url(self, music_id):
        """获取歌曲下载链接"""
        if not self.cookies:
            raise Exception("请先设置Cookies")
        
        try:
            # 歌曲接口
            link = 'https://music.163.com/weapi/song/enhance/player/url/v1'
            
            # 构造加密参数
            i0x = {
                "ids": f"[{music_id}]",
                "level": "exhigh", 
                "encodeType": "aac",
                "csrf_token": self._extract_csrf_token()
            }
            
            data = self.js_code.call('get_data', i0x)
            
            # 发送post请求
            response = requests.post(url=link, headers=self.headers, data=data)
            json_data = response.json()
            
            # 提取歌曲下载链接
            if json_data['data'] and json_data['data'][0]['url']:
                return json_data['data'][0]['url']
            else:
                return None
                
        except Exception as e:
            raise Exception(f"获取音乐URL失败: {str(e)}")
    
    def search_music(self, keyword):
        """搜索音乐"""
        if not self.cookies:
            raise Exception("请先设置Cookies")
        
        try:
            search_link = 'https://music.163.com/weapi/cloudsearch/get/web'
            
            i0x = {
                "hlpretag": "<span class=\"s-fc7\">",
                "hlposttag": "</span>",
                "s": keyword,
                "type": "1",
                "offset": "0",
                "total": "true",
                "limit": "30",
                "csrf_token": self._extract_csrf_token()
            }
            
            data = self.js_code.call('get_data', i0x)
            response = requests.post(url=search_link, headers=self.headers, data=data)
            json_data = response.json()
            
            search_info = []
            if 'result' in json_data and 'songs' in json_data['result']:
                for song in json_data['result']['songs']:
                    artists = '/'.join([artist['name'] for artist in song['ar']])
                    search_info.append({
                        'id': song['id'],
                        'name': song['name'],
                        'artist': artists,
                        'album': song['al']['name'],
                        'duration': self._format_duration(song['dt'] // 1000)
                    })
            
            return search_info
            
        except Exception as e:
            raise Exception(f"搜索音乐失败: {str(e)}")
    
    def show_search_results(self, search_info):
        """显示搜索结果"""
        table = PrettyTable()
        table.field_names = ["序号", "歌曲名称", "歌手", "专辑", "时长"]
        
        for index, song in enumerate(search_info):
            table.add_row([index, song['name'], song['artist'], song['album'], song['duration']])
        
        pprint(table)
        return table

    def download_music(self, music_title, music_url, download_path='music'):
        """下载音乐"""
        try:
            # 自动创建文件夹
            if not os.path.exists(download_path):
                os.makedirs(download_path)
            
            # 清理文件名中的非法字符
            music_title = re.sub(r'[\\/*?:"<>|]', '', music_title)
            
            # 发送请求下载歌曲
            response = requests.get(url=music_url)
            music_data = response.content
            
            # 保存歌曲到本地
            file_path = os.path.join(download_path, music_title + '.mp3')
            with open(file_path, 'wb') as f:
                f.write(music_data)
            
            return True, file_path
            
        except Exception as e:
            return False, f"下载失败: {str(e)}"
    
    def _extract_csrf_token(self):
        """从cookies中提取csrf token"""
        if self.cookies and '__csrf' in self.cookies:
            match = re.search(r'__csrf=([^;]+)', self.cookies)
            if match:
                return match.group(1)
        return ''
    
    def _format_duration(self, seconds):
        """格式化时长"""
        minutes = seconds // 60
        seconds = seconds % 60
        return f"{minutes:02d}:{seconds:02d}"
    
    def validate_cookies(self):
        """验证Cookies是否有效"""
        try:
            test_url = 'http://music.163.com/discover/toplist?id=3778678'
            response = requests.get(url=test_url, headers=self.headers)
            return response.status_code == 200
        except:
            return False
        
def main():
    print("网易云音乐下载器测试")
    downloader = NetEaseMusicDownloader()
    sample_cookies = input('请输入有效的Cookies: ')
    downloader.set_cookies(sample_cookies)
    if downloader.validate_cookies():
        choose = input('请输入下载方式 (1. 榜单下载 2. 搜索下载): ')
        if choose == '1':
            music_info = downloader.get_music_info()
            pprint(music_info)
            for music_id, music_name in music_info:
                print(f'正在下载歌曲: {music_name}')
                music_url = downloader.get_music_url(music_id)
                pprint(music_url)
                downloader.download_music(music_name, music_url)
        elif choose == '2':
            music_info = downloader.search_music(input('请输入搜索关键词: '))  
            downloader.show_search_results(music_info)
            while True:
                index = int(input('请输入要下载的歌曲序号: '))
                music_id = music_info[index]['id']
                music_name = music_info[index]['name']
                print(f'正在下载歌曲: {music_name}')
                music_url = downloader.get_music_url(music_id)
                if not music_url:
                    print('无法下载该歌曲，可能是因为版权问题。')
                    continue
                downloader.download_music(music_name, music_url)
                if input('是否继续下载？(y/n): ') != 'y':
                    break       
    else:
        print("Cookies无效，请检查后重试。")
if __name__ == '__main__':
    main()