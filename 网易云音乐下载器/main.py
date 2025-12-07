# -*- coding: utf-8 -*-
"""
网易云音乐下载器可视化主程序 - 修复参数问题
"""

import sys
import os
import warnings

# 过滤PyQt5的弃用警告
warnings.filterwarnings("ignore", category=DeprecationWarning)

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import (QApplication, QMainWindow, QMessageBox, QHeaderView, 
                             QProgressBar, QLabel, QAbstractItemView)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QObject, QThread, QAbstractTableModel, QVariant

# 获取当前文件的目录
current_dir = os.path.dirname(os.path.abspath(__file__))

# 导入UI类和下载器类
try:
    from ui.Ui_main import Ui_wangyiyun
except ImportError:
    # 如果在同一目录下
    import sys
    sys.path.append('.')
    from ui.Ui_main import Ui_wangyiyun

try:
    from Downloader.downloader import NetEaseMusicDownloader
except ImportError:
    print("错误: 无法导入downloader模块")
    print("请确保downloader.py文件存在")
    sys.exit(1)


class SongTableModel(QAbstractTableModel):
    """歌曲表格模型"""
    def __init__(self, data, headers, parent=None):
        super().__init__(parent)
        self._data = data
        self._headers = headers
        self._check_states = [Qt.Unchecked] * len(data)
    
    def rowCount(self, parent=None):
        return len(self._data)
    
    def columnCount(self, parent=None):
        return len(self._headers)
    
    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return QVariant()
        
        row = index.row()
        col = index.column()
        
        if row >= len(self._data):
            return QVariant()
        
        song = self._data[row]
        
        if role == Qt.DisplayRole:
            if col == 0:
                return ""
            elif col == 1:
                return song.get('name', '')
            elif col == 2:
                return song.get('artist', '未知')
            elif col == 3 and len(self._headers) == 4:
                return song.get('duration', '--:--')
            elif col == 3 and len(self._headers) == 5:
                return song.get('album', '未知')
            elif col == 4:
                return song.get('duration', '--:--')
        
        elif role == Qt.CheckStateRole and col == 0:
            return self._check_states[row]
        
        elif role == Qt.TextAlignmentRole:
            if col == 0 or col == (len(self._headers) - 1):  # 选择列和时长列居中
                return Qt.AlignCenter
            return Qt.AlignLeft | Qt.AlignVCenter
        
        return QVariant()
    
    def setData(self, index, value, role=Qt.EditRole):
        if not index.isValid():
            return False
        
        row = index.row()
        col = index.column()
        
        if role == Qt.CheckStateRole and col == 0:
            self._check_states[row] = value
            self.dataChanged.emit(index, index, [role])
            return True
        
        return False
    
    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            if section < len(self._headers):
                return self._headers[section]
        
        return QVariant()
    
    def flags(self, index):
        if not index.isValid():
            return Qt.NoItemFlags
        
        if index.column() == 0:
            return Qt.ItemIsEnabled | Qt.ItemIsUserCheckable | Qt.ItemIsSelectable
        
        return Qt.ItemIsEnabled | Qt.ItemIsSelectable
    
    def get_selected_songs(self):
        """获取选中的歌曲"""
        selected = []
        for i in range(len(self._data)):
            if self._check_states[i] == Qt.Checked:
                selected.append(self._data[i])
        return selected
    
    def clear_selection(self):
        """清除所有选择"""
        for i in range(len(self._check_states)):
            self._check_states[i] = Qt.Unchecked
        self.dataChanged.emit(self.index(0, 0), self.index(self.rowCount()-1, 0), [Qt.CheckStateRole])


class DownloadWorker(QObject):
    """下载工作线程类"""
    # 定义信号
    status_update = pyqtSignal(str, str)  # 修改：添加table_type参数
    progress_update = pyqtSignal(int, int)
    download_complete = pyqtSignal(str, bool, str)
    playlist_loaded = pyqtSignal(list)
    search_results_ready = pyqtSignal(list)
    validation_complete = pyqtSignal(bool, str)
    
    def __init__(self):
        super().__init__()
        self.downloader = None
        self._running = True
    
    def init_downloader(self):
        """初始化下载器"""
        try:
            self.downloader = NetEaseMusicDownloader()
            return True
        except Exception as e:
            self.status_update.emit(f"初始化下载器失败: {str(e)}", "playlist")
            return False
    
    def set_cookies(self, cookies):
        """设置Cookies"""
        if self.downloader:
            self.downloader.set_cookies(cookies)
    
    def validate_cookies(self):
        """验证Cookies"""
        try:
            if self.downloader:
                valid = self.downloader.validate_cookies()
                if valid:
                    self.validation_complete.emit(True, "Cookies验证成功！")
                else:
                    self.validation_complete.emit(False, "Cookies验证失败！")
            else:
                self.validation_complete.emit(False, "下载器未初始化！")
        except Exception as e:
            self.validation_complete.emit(False, f"验证失败: {str(e)}")
    
    def get_playlist_songs(self, playlist_url):
        """获取榜单歌曲"""
        try:
            if self.downloader:
                music_info = self.downloader.get_music_info(playlist_url)
                songs = []
                for mid, name in music_info:
                    songs.append({
                        'id': mid,
                        'name': name,
                        'artist': '未知',
                        'duration': '--:--',
                        'selected': False
                    })
                self.playlist_loaded.emit(songs)
            else:
                self.status_update.emit("下载器未初始化！", "playlist")
        except Exception as e:
            self.status_update.emit(f"获取榜单失败: {str(e)}", "playlist")
            self.playlist_loaded.emit([])
    
    def search_songs(self, keyword):
        """搜索歌曲"""
        try:
            if self.downloader:
                search_results = self.downloader.search_music(keyword)
                self.search_results_ready.emit(search_results)
            else:
                self.status_update.emit("下载器未初始化！", "search")
        except Exception as e:
            self.status_update.emit(f"搜索失败: {str(e)}", "search")
            self.search_results_ready.emit([])
    
    def download_single_song(self, song_id, song_name):
        """下载单首歌曲"""
        try:
            if self.downloader:
                # 获取下载链接
                music_url = self.downloader.get_music_url(song_id)
                
                if music_url:
                    # 下载歌曲
                    success, message = self.downloader.download_music(song_name, music_url)
                    self.download_complete.emit(song_name, success, message)
                else:
                    self.download_complete.emit(song_name, False, "无法获取下载链接")
            else:
                self.download_complete.emit(song_name, False, "下载器未初始化")
        except Exception as e:
            self.download_complete.emit(song_name, False, str(e))
    
    def stop(self):
        """停止工作线程"""
        self._running = False


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # 初始化UI
        self.ui = Ui_wangyiyun()
        
        # 先设置图标
        self.setup_icon()
        
        # 然后调用setupUi
        self.ui.setupUi(self)
        
        # 初始化工作线程
        self.worker_thread = None
        self.worker = None
        self.init_worker_thread()
        
        # 初始化数据
        self.playlist_model = None
        self.search_model = None
        self.current_table_type = "playlist"  # 当前表格类型
        
        # 设置UI属性
        self.setup_ui()
        
        # 连接信号槽
        self.connect_signals()
        
        # 初始化表格
        self.init_tables()
    
    def setup_icon(self):
        """设置窗口图标"""
        # 尝试多种路径
        icon_paths = [
            os.path.join(current_dir, "sourse", "conan.ico"),  # 注意：根据您的目录是sourse不是source
            os.path.join(current_dir, "source", "conan.ico"),  # 也尝试source
            os.path.join(current_dir, "conan.ico"),             # 当前目录
            "sourse/conan.ico",                                # 相对路径
            "source/conan.ico",                                # 另一种拼写
            "./sourse/conan.ico",                              # 当前目录的相对路径
        ]
        
        icon = None
        for path in icon_paths:
            if os.path.exists(path):
                try:
                    icon = QtGui.QIcon(path)
                    self.setWindowIcon(icon)
                    print(f"成功加载图标: {path}")
                    break
                except Exception as e:
                    print(f"加载图标失败 {path}: {e}")
        
        if icon is None:
            print("警告: 未找到图标文件，使用默认图标")
            # 使用默认图标或系统图标
            icon = self.style().standardIcon(QtWidgets.QStyle.SP_ComputerIcon)
            self.setWindowIcon(icon)
    
    def init_worker_thread(self):
        """初始化工作线程"""
        # 创建工作线程
        self.worker_thread = QThread()
        self.worker = DownloadWorker()
        
        # 将工作对象移动到线程
        self.worker.moveToThread(self.worker_thread)
        
        # 连接工作线程信号 - 修正：status_update现在接收两个参数
        self.worker.status_update.connect(self.update_status)
        self.worker.progress_update.connect(self.update_progress)
        self.worker.download_complete.connect(self.on_download_complete)
        self.worker.playlist_loaded.connect(self.on_playlist_loaded)
        self.worker.search_results_ready.connect(self.on_search_results_ready)
        self.worker.validation_complete.connect(self.on_validation_complete)
        
        # 启动线程
        self.worker_thread.start()
        
        # 初始化下载器
        QTimer.singleShot(0, self.worker.init_downloader)
    
    def setup_ui(self):
        """设置UI属性和样式"""
        # 设置输入框占位符
        self.ui.lineEdit.setPlaceholderText("粘贴从浏览器复制的Cookies...")
        self.ui.lineEdit_2.setPlaceholderText("例如: https://music.163.com/#/discover/toplist?id=3778678")
        self.ui.lineEdit_3.setPlaceholderText("输入歌曲名、歌手或专辑...")
        
        # 设置按钮样式
        self.setup_button_styles()
        
        # 创建状态标签 - 修正：使用已有的label
        self.status_label = self.ui.label_3
        self.status_label_2 = self.ui.label_6
        
        # 设置初始状态文本
        self.status_label.setText("就绪")
        self.status_label_2.setText("就绪")
        
        # 创建进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumWidth(200)
        self.progress_bar.hide()
        
        # 将进度条添加到状态栏
        # self.ui.statusbar.addPermanentWidget(self.progress_bar)
    
    def setup_button_styles(self):
        """设置按钮样式"""
        red_button_style = """
            QPushButton {
                background-color: #d43c33;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #b83229;
            }
            QPushButton:pressed {
                background-color: #9c2c24;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """
        
        blue_button_style = """
            QPushButton {
                background-color: #4285f4;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #3367d6;
            }
            QPushButton:pressed {
                background-color: #2a56c6;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """
        
        # 应用样式
        self.ui.pushButton_2.setStyleSheet(red_button_style)
        self.ui.pushButton_3.setStyleSheet(blue_button_style)
        self.ui.pushButton_4.setStyleSheet(red_button_style)
        self.ui.pushButton_5.setStyleSheet(blue_button_style)
        self.ui.pushButton.setStyleSheet(blue_button_style)  # Cookies测试按钮
    
    def connect_signals(self):
        """连接信号和槽"""
        # Cookies测试按钮
        self.ui.pushButton.clicked.connect(self.on_test_cookies)
        
        # 榜单下载按钮
        self.ui.pushButton_2.clicked.connect(self.on_get_playlist)
        self.ui.pushButton_3.clicked.connect(self.on_download_selected_playlist)
        
        # 搜索下载按钮
        self.ui.pushButton_4.clicked.connect(self.on_get_search_results)
        self.ui.pushButton_5.clicked.connect(self.on_download_selected_search)
        
        # 标签页切换事件
        self.ui.tabWidget.currentChanged.connect(self.on_tab_changed)
    
    def init_tables(self):
        """初始化表格"""
        # 设置榜单表格
        self.setup_table_view(self.ui.tableView_2)
        
        # 设置搜索表格
        self.setup_table_view(self.ui.tableView)
    
    def setup_table_view(self, table_view):
        """设置表格视图"""
        # 设置选择行为
        table_view.setSelectionBehavior(QAbstractItemView.SelectRows)
        table_view.setSelectionMode(QAbstractItemView.SingleSelection)
        
        # 设置编辑行为
        table_view.setEditTriggers(QAbstractItemView.NoEditTriggers)
        
        # 设置交替行颜色
        table_view.setAlternatingRowColors(True)
        
        # 设置网格线
        table_view.setShowGrid(True)
        
        # 设置表头
        header = table_view.horizontalHeader()
        header.setStretchLastSection(True)
        
        # 设置行高
        table_view.verticalHeader().setDefaultSectionSize(35)
        
        # 隐藏垂直表头
        table_view.verticalHeader().setVisible(False)
    
    def on_test_cookies(self):
        """测试Cookies按钮点击事件"""
        cookies = self.ui.lineEdit.text().strip()
        if not cookies:
            QMessageBox.warning(self, "警告", "请输入Cookies！")
            return
        
        # 禁用按钮防止重复点击
        self.ui.pushButton.setEnabled(False)
        self.ui.pushButton.setText("验证中...")
        
        self.update_status("正在验证Cookies...", "playlist")
        
        # 设置Cookies并开始验证
        self.worker.set_cookies(cookies)
        QTimer.singleShot(0, self.worker.validate_cookies)
    
    def on_validation_complete(self, success, message):
        """验证完成回调"""
        # 恢复按钮状态
        self.ui.pushButton.setEnabled(True)
        self.ui.pushButton.setText("测试cookies")
        
        # 更新状态
        self.update_status(message, "playlist")
        
        if success:
            QMessageBox.information(self, "成功", message)
        else:
            QMessageBox.warning(self, "失败", message)
    
    def on_get_playlist(self):
        """获取榜单歌曲按钮点击事件"""
        playlist_url = self.ui.lineEdit_2.text().strip()
        if not playlist_url:
            # 默认热歌榜
            playlist_url = 'http://music.163.com/discover/toplist?id=3778678'
            self.ui.lineEdit_2.setText(playlist_url)
        
        # 禁用按钮防止重复点击
        self.ui.pushButton_2.setEnabled(False)
        self.ui.pushButton_2.setText("获取中...")
        
        self.update_status("正在获取榜单歌曲...", "playlist")
        
        # 在线程中获取榜单歌曲
        QTimer.singleShot(0, lambda: self.worker.get_playlist_songs(playlist_url))
    
    def on_playlist_loaded(self, songs):
        """榜单歌曲加载完成"""
        # 恢复按钮状态
        self.ui.pushButton_2.setEnabled(True)
        self.ui.pushButton_2.setText("获取榜单歌曲")
        
        if songs:
            # 创建并设置模型
            self.playlist_model = SongTableModel(songs, ["选择", "歌曲名", "歌手", "时长"])
            self.ui.tableView_2.setModel(self.playlist_model)
            
            # 调整列宽
            self.ui.tableView_2.setColumnWidth(0, 50)
            self.ui.tableView_2.setColumnWidth(1, 200)
            self.ui.tableView_2.setColumnWidth(2, 120)
            self.ui.tableView_2.setColumnWidth(3, 80)
            
            # 更新状态
            self.update_status(f"获取到 {len(songs)} 首歌曲", "playlist")
        else:
            self.update_status("未获取到歌曲", "playlist")
            QMessageBox.warning(self, "警告", "未获取到歌曲，请检查网络或Cookies！")
    
    def on_get_search_results(self):
        """获取搜索歌曲按钮点击事件"""
        keyword = self.ui.lineEdit_3.text().strip()
        if not keyword:
            QMessageBox.warning(self, "警告", "请输入搜索关键词！")
            return
        
        # 禁用按钮防止重复点击
        self.ui.pushButton_4.setEnabled(False)
        self.ui.pushButton_4.setText("搜索中...")
        
        self.update_status(f"正在搜索: {keyword}", "search")
        
        # 在线程中搜索歌曲
        QTimer.singleShot(0, lambda: self.worker.search_songs(keyword))
    
    def on_search_results_ready(self, songs):
        """搜索歌曲加载完成"""
        # 恢复按钮状态
        self.ui.pushButton_4.setEnabled(True)
        self.ui.pushButton_4.setText("获取歌曲列表")
        
        if songs:
            # 创建并设置模型
            self.search_model = SongTableModel(songs, ["选择", "歌曲名", "歌手", "专辑", "时长"])
            self.ui.tableView.setModel(self.search_model)
            
            # 调整列宽
            self.ui.tableView.setColumnWidth(0, 50)
            self.ui.tableView.setColumnWidth(1, 150)
            self.ui.tableView.setColumnWidth(2, 100)
            self.ui.tableView.setColumnWidth(3, 120)
            self.ui.tableView.setColumnWidth(4, 80)
            
            # 更新状态
            self.update_status(f"搜索到 {len(songs)} 首歌曲", "search")
        else:
            self.update_status("未搜索到歌曲", "search")
            QMessageBox.warning(self, "警告", "未搜索到歌曲，请检查关键词或网络！")
    
    def on_download_selected_playlist(self):
        """下载选中的榜单歌曲"""
        if not self.playlist_model:
            QMessageBox.warning(self, "警告", "请先获取榜单歌曲！")
            return
        
        selected_songs = self.playlist_model.get_selected_songs()
        if not selected_songs:
            QMessageBox.warning(self, "警告", "请先选择要下载的歌曲！")
            return
        
        self.download_multiple_songs(selected_songs, "playlist")
    
    def on_download_selected_search(self):
        """下载选中的搜索歌曲"""
        if not self.search_model:
            QMessageBox.warning(self, "警告", "请先搜索歌曲！")
            return
        
        selected_songs = self.search_model.get_selected_songs()
        if not selected_songs:
            QMessageBox.warning(self, "警告", "请先选择要下载的歌曲！")
            return
        
        self.download_multiple_songs(selected_songs, "search")
    
    def download_multiple_songs(self, songs, table_type):
        """批量下载歌曲"""
        total = len(songs)
        if total == 0:
            return
        
        # 显示进度条
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(0)
        self.progress_bar.show()
        
        # 禁用按钮
        if table_type == "playlist":
            self.ui.pushButton_3.setEnabled(False)
        else:
            self.ui.pushButton_5.setEnabled(False)
        
        self.update_status(f"准备下载 {total} 首歌曲", table_type)
        
        # 逐个下载歌曲
        for i, song in enumerate(songs):
            self.update_status(f"正在下载: {song['name']}", table_type)
            QTimer.singleShot(i * 1000, lambda s=song: self.worker.download_single_song(s['id'], s['name']))
            
            # 更新进度条
            self.progress_bar.setValue(i + 1)
            QApplication.processEvents()  # 处理事件，更新UI
        
        # 恢复按钮状态
        QTimer.singleShot(total * 1000 + 1000, lambda: self.restore_buttons(table_type))
    
    def restore_buttons(self, table_type):
        """恢复按钮状态"""
        if table_type == "playlist":
            self.ui.pushButton_3.setEnabled(True)
        else:
            self.ui.pushButton_5.setEnabled(True)
        
        self.progress_bar.hide()
    
    def on_download_complete(self, song_name, success, message):
        """单首歌曲下载完成回调"""
        if success:
            self.update_status(f"'{song_name}' 下载成功", self.current_table_type)
            # 可以添加成功提示
        else:
            self.update_status(f"'{song_name}' 下载失败", self.current_table_type)
            QMessageBox.warning(self, "下载失败", f"歌曲 '{song_name}' 下载失败！\n错误: {message}")
    
    def on_tab_changed(self, index):
        """标签页切换事件"""
        if index == 0:
            self.current_table_type = "playlist"
            self.update_status("就绪", "playlist")
        else:
            self.current_table_type = "search"
            self.update_status("就绪", "search")
    
    def update_status(self, status, table_type):
        """更新状态 - 修正：现在接收两个参数"""
        if table_type == "playlist":
            self.status_label.setText(f"状态：{status}")
        else:
            self.status_label_2.setText(f"状态：{status}")
        
        # 可选：打印到控制台
        print(f"[{table_type}] {status}")
    
    def update_progress(self, current, total):
        """更新进度条"""
        if total > 0:
            self.progress_bar.setMaximum(total)
            self.progress_bar.setValue(current)
            self.progress_bar.show()
        else:
            self.progress_bar.hide()
    
    def closeEvent(self, event):
        """窗口关闭事件"""
        if self.worker:
            # 停止工作线程
            self.worker.stop()
            self.worker_thread.quit()
            self.worker_thread.wait()
        
        reply = QMessageBox.question(
            self, "确认退出",
            "确定要退出网易云音乐下载器吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            event.accept()
        else:
            event.ignore()


def main():
    """主程序入口"""
    # 创建应用程序实例
    app = QApplication(sys.argv)
    
    # 设置应用程序样式
    app.setStyle("Fusion")
    
    # 设置应用程序字体
    font = QtGui.QFont()
    font.setFamily("Microsoft YaHei")
    font.setPointSize(10)
    app.setFont(font)
    
    # 创建主窗口
    window = MainWindow()
    
    # 显示主窗口
    window.show()
    
    # 进入应用程序主循环
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()